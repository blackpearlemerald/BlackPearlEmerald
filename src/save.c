#include "global.h"
#include "agb_flash.h"
#include "gba/flash_internal.h"
#include "fieldmap.h"
#include "save.h"
#include "save_engine.h"
#include "task.h"
#include "decompress.h"
#include "event_data.h"
#include "load_save.h"
#include "overworld.h"
#include "hall_of_fame.h"
#include "packed_box_mon.h"
#include "pokemon_storage_system.h"
#include "random.h"
#include "trainer_hill.h"
#include "link.h"
#include "constants/game_stat.h"

// BPE 2.1 save format. The format itself and its crash-safety rules live in
// src/save_engine.c (see include/save_engine.h); this file connects the engine
// to the game's save blocks, the flash chip and the Hall of Fame sectors.

STATIC_ASSERT(sizeof(struct PackedBoxMon) == SAVE_BOX_MON_SIZE, PackedBoxMonSize);
STATIC_ASSERT(TOTAL_BOXES_COUNT * IN_BOX_COUNT <= SAVE_BOX_MAX_MONS, BoxSectorSpace);
STATIC_ASSERT(SAVE_META_SIZE + sizeof(struct SaveBlock2) + POKEMON_STORAGE_HEADER_SIZE + sizeof(struct SaveBlock3) <= SAVE_SECTOR_PAYLOAD_SIZE, ProgressPart0FreeSpace);
STATIC_ASSERT(sizeof(struct SaveBlock1) <= SAVE_SECTOR_PAYLOAD_SIZE * (SAVE_PROGRESS_PARTS - 1), SaveBlock1FreeSpace);

COMMON_DATA u32 gDamagedSaveSectors = 0;
COMMON_DATA u16 gSaveFileStatus = 0;
COMMON_DATA MainCallback gGameContinueCallback = NULL;

static EWRAM_DATA struct SaveEngineLayout sLayout = {0};

// Flash access --------------------------------------------------------------

#if TESTING
// Tests can cut the power: when enabled, after gSaveTestFlashBudget byte
// writes and erases nothing more reaches the flash chip.
EWRAM_DATA bool8 gSaveTestPowerCutEnabled = FALSE;
EWRAM_DATA u32 gSaveTestFlashBudget = 0;
EWRAM_DATA bool8 gSaveTestPowerLost = FALSE;

static bool32 ConsumeFlashBudget(void)
{
    if (gSaveTestPowerLost)
        return FALSE;
    if (!gSaveTestPowerCutEnabled)
        return TRUE;
    if (gSaveTestFlashBudget == 0)
    {
        gSaveTestPowerLost = TRUE;
        return FALSE;
    }
    gSaveTestFlashBudget--;
    return TRUE;
}
#else
#define ConsumeFlashBudget() TRUE
#endif

void SaveIo_ReadSector(u8 sector, u8 *dst)
{
    ReadFlash(sector, 0, dst, SAVE_SECTOR_SIZE);
}

static bool8 VerifySector(u8 sector, const u8 *src, u16 skipOffset)
{
    u16 offset;
    u8 buffer[64];

    for (offset = 0; offset < SAVE_SECTOR_SIZE; offset += sizeof(buffer))
    {
        u16 i;
        ReadFlash(sector, offset, buffer, sizeof(buffer));
        for (i = 0; i < sizeof(buffer); i++)
        {
            if (offset + i != skipOffset && buffer[i] != src[offset + i])
                return TRUE;
        }
    }
    return FALSE;
}

bool8 SaveIo_ProgramSectorSkipByte(u8 sector, const u8 *src, u16 skipOffset)
{
    u16 i;

    if (!ConsumeFlashBudget())
        return FALSE;
    if (EraseFlashSector(sector))
        return TRUE;
    for (i = 0; i < SAVE_SECTOR_SIZE; i++)
    {
        if (i == skipOffset)
            continue;
        if (!ConsumeFlashBudget())
            return FALSE;
        if (ProgramFlashByte(sector, i, src[i]))
            return TRUE;
    }
    return VerifySector(sector, src, skipOffset);
}

bool8 SaveIo_ProgramSector(u8 sector, const u8 *src)
{
#if TESTING
    if (gSaveTestPowerCutEnabled || gSaveTestPowerLost)
        return SaveIo_ProgramSectorSkipByte(sector, src, 0xFFFF);
#endif
    if (ProgramFlashSectorAndVerify(sector, (u8 *)src))
        return TRUE;
    return FALSE;
}

bool8 SaveIo_ProgramByte(u8 sector, u16 offset, u8 value)
{
    u8 check;

    if (!ConsumeFlashBudget())
        return FALSE;
    if (ProgramFlashByte(sector, offset, value))
        return TRUE;
    ReadFlash(sector, offset, &check, 1);
    return check != value;
}

// A PC record gains data if it holds a different Pokémon, or the same Pokémon
// changed in any way other than losing its held item.
bool8 SaveIo_MonChangeGainsData(const u8 *oldMon, const u8 *newMon)
{
    u8 oldCopy[SAVE_BOX_MON_SIZE], newCopy[SAVE_BOX_MON_SIZE];

    if (memcmp(oldMon, newMon, SAVE_BOX_MON_IDENTITY_SIZE) != 0)
        return TRUE;
    if (GetPackedBits(newMon, PB_HELD_ITEM) != ITEM_NONE)
        return TRUE;
    memcpy(oldCopy, oldMon, SAVE_BOX_MON_SIZE);
    memcpy(newCopy, newMon, SAVE_BOX_MON_SIZE);
    SetPackedBits(oldCopy, PB_HELD_ITEM, ITEM_NONE);
    return memcmp(oldCopy, newCopy, SAVE_BOX_MON_SIZE) != 0;
}

// Layout ---------------------------------------------------------------------

static void UpdateSaveAddresses(void)
{
    sLayout.part0[0].data = (u8 *)gSaveBlock2Ptr;
    sLayout.part0[0].size = sizeof(struct SaveBlock2);
    sLayout.part0[1].data = (u8 *)gPokemonStoragePtr;
    sLayout.part0[1].size = POKEMON_STORAGE_HEADER_SIZE;
    sLayout.part0[2].data = (u8 *)gSaveBlock3Ptr;
    sLayout.part0[2].size = sizeof(struct SaveBlock3);
    sLayout.part0Count = 3;
    sLayout.progressTail = (u8 *)gSaveBlock1Ptr;
    sLayout.progressTailSize = sizeof(struct SaveBlock1);
    sLayout.boxData = (u8 *)gPokemonStoragePtr->boxes;
    sLayout.boxMonCount = TOTAL_BOXES_COUNT * IN_BOX_COUNT;
    SaveEngine_SetLayout(&sLayout);
}

// Gives a new game its own identity, so that PC data left on the flash chip by
// an earlier game is never mistaken for this game's.
void Save_StartNewGameIdentity(void)
{
    u32 oldId = SaveEngine_GetGameId();
    u32 gameId;

    do
    {
        gameId = Random32() ^ (gMain.vblankCounter1 * 0x9E3779B9) ^ (gMain.vblankCounter2 << 16);
    } while (gameId == 0 || gameId == oldId);
    SaveEngine_SetGameId(gameId);
}

void ClearSaveData(void)
{
    u16 i;

    if (gSaveFileStatus == SAVE_STATUS_OUTDATED)
        gSaveFileStatus = SAVE_STATUS_EMPTY;

    // Clear the full save two sectors at a time
    for (i = 0; i < SECTORS_COUNT / 2; i++)
    {
        EraseFlashSector(i);
        EraseFlashSector(i + SECTORS_COUNT / 2);
    }
    SaveEngine_ResetState();
}

void Save_ResetSaveCounters(void)
{
    SaveEngine_ResetState();
    gDamagedSaveSectors = 0;
}

// Saving ---------------------------------------------------------------------

// A save from before the 2.1 format is on the flash chip. Nothing may be
// written over it; the player converts it on the website or clears it with
// the clear save data screen.
bool8 Save_IsBlockedByOutdatedSave(void)
{
    return gSaveFileStatus == SAVE_STATUS_OUTDATED;
}

static void PrepareSave(void)
{
    UpdateSaveAddresses();
    FlushBoxCache();
    CopyPartyAndObjectsToSave();
}

static u8 RunFullSave(void)
{
    u8 result = SaveEngine_SaveAll();
    gDamagedSaveSectors |= SaveEngine_GetDamagedSectors();
    return result;
}

static u16 CalculateChecksum(void *data, u16 size)
{
    u16 i;
    u32 checksum = 0;

    for (i = 0; i < (size / 4); i++)
    {
        checksum += *((u32 *)data);
        data += sizeof(u32);
    }

    return ((checksum >> 16) + checksum);
}

// Hall of Fame sectors keep the legacy format: data, checksum in the id field.
static u8 HandleWriteSectorNBytes(u8 sectorId, u8 *data, u16 size)
{
    u16 i;
    struct SaveSector *sector = (struct SaveSector *)gSaveEngineBuffer;

    for (i = 0; i < SECTOR_SIZE; i++)
        ((u8 *)sector)[i] = 0;

    sector->signature = SECTOR_SIGNATURE;
    for (i = 0; i < size; i++)
        sector->data[i] = data[i];
    sector->id = CalculateChecksum(data, size);

    if (SaveIo_ProgramSector(sectorId, sector->data))
    {
        gDamagedSaveSectors |= (1u << sectorId);
        return SAVE_STATUS_ERROR;
    }
    return SAVE_STATUS_OK;
}

static u8 TryLoadSaveSector(u8 sectorId, u8 *data, u16 size)
{
    u16 i;
    struct SaveSector *sector = (struct SaveSector *)gSaveEngineBuffer;

    SaveIo_ReadSector(sectorId, sector->data);
    if (sector->signature != SECTOR_SIGNATURE)
        return SAVE_STATUS_EMPTY;
    if (sector->id != CalculateChecksum(sector->data, size))
        return SAVE_STATUS_CORRUPT;
    for (i = 0; i < size; i++)
        data[i] = sector->data[i];
    return SAVE_STATUS_OK;
}

u8 HandleSavingData(u8 saveType)
{
    u8 i;
    u32 *backupVar = gTrainerHillVBlankCounter;

    gTrainerHillVBlankCounter = NULL;
    gDamagedSaveSectors = 0;
    if (Save_IsBlockedByOutdatedSave())
    {
        gTrainerHillVBlankCounter = backupVar;
        return 0;
    }
    switch (saveType)
    {
    case SAVE_HALL_OF_FAME_ERASE_BEFORE:
        for (i = SECTOR_ID_HOF_1; i < SECTORS_COUNT; i++)
            EraseFlashSector(i);
        // fallthrough
    case SAVE_HALL_OF_FAME:
        if (GetGameStat(GAME_STAT_ENTERED_HOF) < 999)
            IncrementGameStat(GAME_STAT_ENTERED_HOF);

        PrepareSave();
        RunFullSave();

        if (gHoFSaveBuffer != NULL)
        {
            u8 *tempAddr = (void *) gHoFSaveBuffer;
            HandleWriteSectorNBytes(SECTOR_ID_HOF_1, tempAddr, SECTOR_DATA_SIZE);
            HandleWriteSectorNBytes(SECTOR_ID_HOF_2, tempAddr + SECTOR_DATA_SIZE, SECTOR_DATA_SIZE);
        }
        break;
    case SAVE_OVERWRITE_DIFFERENT_FILE:
        for (i = SECTOR_ID_HOF_1; i < SECTORS_COUNT; i++)
            EraseFlashSector(i);
        PrepareSave();
        RunFullSave();
        break;
    case SAVE_NORMAL:
    case SAVE_LINK:    // The 2.1 format always saves the PC with the rest
    case SAVE_EREADER: // Dummied, now duplicate of SAVE_LINK
    default:
        PrepareSave();
        RunFullSave();
        break;
    }
    gTrainerHillVBlankCounter = backupVar;
    return 0;
}

u8 TrySavingData(u8 saveType)
{
    if (gFlashMemoryPresent != TRUE || Save_IsBlockedByOutdatedSave())
        return SAVE_STATUS_ERROR;

    HandleSavingData(saveType);
    if (!gDamagedSaveSectors)
    {
        return SAVE_STATUS_OK;
    }
    else
    {
        DoSaveFailedScreen(saveType);
        return SAVE_STATUS_ERROR;
    }
}

// Saves spread over several frames. The link trade flow writes everything but
// one byte of the commit sector, waits for the partner, then commits.

static bool8 StepIncrementalSave(void)
{
    u8 result = SaveEngine_Step();
    gDamagedSaveSectors |= SaveEngine_GetDamagedSectors();
    return result != SAVE_ENGINE_BUSY;
}

bool8 LinkFullSave_Init(void)
{
    if (gFlashMemoryPresent != TRUE || Save_IsBlockedByOutdatedSave())
        return TRUE;
    gDamagedSaveSectors = 0;
    PrepareSave();
    SaveEngine_BeginSave(SAVE_ENGINE_FLAG_TWO_PHASE);
    return FALSE;
}

bool8 LinkFullSave_WriteSector(void)
{
    bool8 finished = StepIncrementalSave();
    if (gDamagedSaveSectors)
        DoSaveFailedScreen(SAVE_NORMAL);
    return finished;
}

bool8 LinkFullSave_ReplaceLastSector(void)
{
    // The commit sector was already written without its commit byte by
    // LinkFullSave_WriteSector.
    if (gDamagedSaveSectors)
        DoSaveFailedScreen(SAVE_NORMAL);
    return FALSE;
}

bool8 LinkFullSave_SetLastSectorSignature(void)
{
    u8 result = SaveEngine_FinishCommit();
    while (result == SAVE_ENGINE_BUSY)
        result = SaveEngine_Step();
    gDamagedSaveSectors |= SaveEngine_GetDamagedSectors();
    if (gDamagedSaveSectors)
        DoSaveFailedScreen(SAVE_NORMAL);
    return FALSE;
}

bool8 WriteSaveBlock2(void)
{
    if (gFlashMemoryPresent != TRUE || Save_IsBlockedByOutdatedSave())
        return TRUE;
    gDamagedSaveSectors = 0;
    PrepareSave();
    SaveEngine_BeginSave(0);
    StepIncrementalSave();
    return FALSE;
}

// Called once per frame after WriteSaveBlock2 until it returns TRUE.
bool8 WriteSaveBlock1Sector(void)
{
    bool8 finished = TRUE;

    if (SaveEngine_IsSaving())
        finished = StepIncrementalSave();
    if (gDamagedSaveSectors)
        DoSaveFailedScreen(SAVE_LINK);
    return finished;
}

#if TESTING
// Plans a normal save without writing anything and returns how many sectors it
// would program.
u32 Save_TestCountSectorWrites(void)
{
    u8 beforeCommit, afterCommit;

    PrepareSave();
    SaveEngine_BeginSave(0);
    SaveEngine_GetPlanCounts(&beforeCommit, &afterCommit);
    return 2 * (beforeCommit + afterCommit) + SAVE_PROGRESS_PARTS;
}
#endif

// Loading --------------------------------------------------------------------

u8 LoadGameSave(u8 saveType)
{
    u8 status;

    if (gFlashMemoryPresent != TRUE)
    {
        gSaveFileStatus = SAVE_STATUS_NO_FLASH;
        return SAVE_STATUS_ERROR;
    }

    switch (saveType)
    {
    case SAVE_NORMAL:
    default:
        InvalidateBoxCache();
        UpdateSaveAddresses();
        switch (SaveEngine_Load())
        {
        case SAVE_ENGINE_LOAD_OK:
            status = SAVE_STATUS_OK;
            break;
        case SAVE_ENGINE_LOAD_OK_BACKUP:
            status = SAVE_STATUS_ERROR;
            break;
        case SAVE_ENGINE_LOAD_CORRUPT:
            status = SAVE_STATUS_CORRUPT;
            break;
        case SAVE_ENGINE_LOAD_OUTDATED:
            status = SAVE_STATUS_OUTDATED;
            break;
        case SAVE_ENGINE_LOAD_EMPTY:
        default:
            status = SAVE_STATUS_EMPTY;
            break;
        }
        if (status == SAVE_STATUS_OK && (SaveEngine_GetLoadFlags() & SAVE_LOAD_FLAG_BOX_LOST))
            status = SAVE_STATUS_ERROR;
        if (status == SAVE_STATUS_OK || status == SAVE_STATUS_ERROR)
            CopyPartyAndObjectsFromSave();
        // BPE gives the National Pokédex with the regular Pokédex. Upgrade
        // saves created before this behavior was introduced.
        if (status == SAVE_STATUS_OK
         && FlagGet(FLAG_SYS_POKEDEX_GET)
         && !IsNationalPokedexEnabled())
            EnableNationalPokedex();
        gSaveFileStatus = status;
        gGameContinueCallback = NULL;
        break;
    case SAVE_HALL_OF_FAME:
        if (gHoFSaveBuffer != NULL)
        {
            u8 *hofData = (u8 *) gHoFSaveBuffer;
            status = TryLoadSaveSector(SECTOR_ID_HOF_1, hofData, SECTOR_DATA_SIZE);
            if (status == SAVE_STATUS_OK)
                status = TryLoadSaveSector(SECTOR_ID_HOF_2, &hofData[SECTOR_DATA_SIZE], SECTOR_DATA_SIZE);
        }
        else
        {
            status = SAVE_STATUS_ERROR;
        }
        break;
    }

    return status;
}

u16 GetSaveBlocksPointersBaseOffset(void)
{
    const u8 *sb2;

    if (gFlashMemoryPresent != TRUE)
        return 0;
    UpdateSaveAddresses();
    if (!SaveEngine_ReadNewestPart0())
        return 0;

    // Base offset for SaveBlock2 is calculated using the trainer id
    sb2 = gSaveEngineBuffer + SaveEngine_GetPart0FragmentOffset(0);
    return sb2[offsetof(struct SaveBlock2, playerTrainerId[0])] +
           sb2[offsetof(struct SaveBlock2, playerTrainerId[1])] +
           sb2[offsetof(struct SaveBlock2, playerTrainerId[2])] +
           sb2[offsetof(struct SaveBlock2, playerTrainerId[3])];
}

#define tState         data[0]
#define tTimer         data[1]
#define tInBattleTower data[2]

// Note that this is very different from TrySavingData(SAVE_LINK).
// Most notably it does save the PC data.
void Task_LinkFullSave(u8 taskId)
{
    s16 *data = gTasks[taskId].data;

    switch (tState)
    {
    case 0:
        gSoftResetDisabled = TRUE;
        tState = 1;
        break;
    case 1:
        SetLinkStandbyCallback();
        tState = 2;
        break;
    case 2:
        if (IsLinkTaskFinished())
        {
            if (!tInBattleTower)
                SaveMapView();
            tState = 3;
        }
        break;
    case 3:
        if (!tInBattleTower)
            SetContinueGameWarpStatusToDynamicWarp();
        LinkFullSave_Init();
        tState = 4;
        break;
    case 4:
        if (++tTimer == 5)
        {
            tTimer = 0;
            tState = 5;
        }
        break;
    case 5:
        if (LinkFullSave_WriteSector())
            tState = 6;
        else
            tState = 4; // Not finished, delay again
        break;
    case 6:
        LinkFullSave_ReplaceLastSector();
        tState = 7;
        break;
    case 7:
        if (!tInBattleTower)
            ClearContinueGameWarpStatus2();
        SetLinkStandbyCallback();
        tState = 8;
        break;
    case 8:
        if (IsLinkTaskFinished())
        {
            LinkFullSave_SetLastSectorSignature();
            tState = 9;
        }
        break;
    case 9:
        SetLinkStandbyCallback();
        tState = 10;
        break;
    case 10:
        if (IsLinkTaskFinished())
            tState++;
        break;
    case 11:
        if (++tTimer > 5)
        {
            gSoftResetDisabled = FALSE;
            DestroyTask(taskId);
        }
        break;
    }
}
