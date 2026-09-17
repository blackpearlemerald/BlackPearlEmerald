#ifdef SAVE_ENGINE_HOST
#include <string.h>
#define EWRAM_DATA
#define ALIGNED(n) _Alignas(n)
#else
#include "global.h"
#endif
#include "save_engine.h"

// See include/save_engine.h for the format and the commit rules.

enum
{
    STEP_BACKUP,
    STEP_WRITE_BOX,       // Final image of a box sector
    STEP_WRITE_BOX_UNION, // Interim image that keeps Pokémon leaving the sector
    STEP_WRITE_PROGRESS,
    STEP_COMMIT_BYTE,
};

#define STEP(type, arg) (((type) << 5) | (arg))
#define STEP_TYPE(step) ((step) >> 5)
#define STEP_ARG(step)  ((step) & 0x1F)

// How a changed box sector is written
enum
{
    WRITE_AFTER_COMMIT,          // Only loses data
    WRITE_BEFORE_COMMIT,         // Only gains data, or nothing on flash to protect
    WRITE_UNION_THEN_FINAL,      // Gains and loses: interim image before, final image after
};

#define NO_SECTOR 0xFF
#define NO_COPY   0xFF

struct SaveEngineState
{
    u32 counter;
    u32 gameId;
    u32 committedCrc[SAVE_BOX_SECTOR_COUNT];
    u32 loadFlags;
    u32 damaged;
    u8 newestCopy;
    // Cached description of the backup sector's contents
    bool8 backupValid;
    u8 backupId;
    u32 backupCrc;
    u32 backupGameId;
    // Save in progress
    bool8 saving;
    bool8 committed;
    u8 flags;
    u8 targetCopy;
    u8 numSteps;
    u8 stepIndex;
    u32 newCounter;
    u32 pendingCrc[SAVE_BOX_SECTOR_COUNT];
    u8 steps[SAVE_ENGINE_MAX_STEPS];
};

ALIGNED(4) EWRAM_DATA u8 gSaveEngineBuffer[SAVE_SECTOR_SIZE] = {0};
static EWRAM_DATA struct SaveEngineState sEngine = {0};
static EWRAM_DATA const struct SaveEngineLayout *sLayout = NULL;

static const u32 sCrc32Table[256] =
{
    0x00000000, 0x77073096, 0xEE0E612C, 0x990951BA, 0x076DC419, 0x706AF48F, 0xE963A535, 0x9E6495A3,
    0x0EDB8832, 0x79DCB8A4, 0xE0D5E91E, 0x97D2D988, 0x09B64C2B, 0x7EB17CBD, 0xE7B82D07, 0x90BF1D91,
    0x1DB71064, 0x6AB020F2, 0xF3B97148, 0x84BE41DE, 0x1ADAD47D, 0x6DDDE4EB, 0xF4D4B551, 0x83D385C7,
    0x136C9856, 0x646BA8C0, 0xFD62F97A, 0x8A65C9EC, 0x14015C4F, 0x63066CD9, 0xFA0F3D63, 0x8D080DF5,
    0x3B6E20C8, 0x4C69105E, 0xD56041E4, 0xA2677172, 0x3C03E4D1, 0x4B04D447, 0xD20D85FD, 0xA50AB56B,
    0x35B5A8FA, 0x42B2986C, 0xDBBBC9D6, 0xACBCF940, 0x32D86CE3, 0x45DF5C75, 0xDCD60DCF, 0xABD13D59,
    0x26D930AC, 0x51DE003A, 0xC8D75180, 0xBFD06116, 0x21B4F4B5, 0x56B3C423, 0xCFBA9599, 0xB8BDA50F,
    0x2802B89E, 0x5F058808, 0xC60CD9B2, 0xB10BE924, 0x2F6F7C87, 0x58684C11, 0xC1611DAB, 0xB6662D3D,
    0x76DC4190, 0x01DB7106, 0x98D220BC, 0xEFD5102A, 0x71B18589, 0x06B6B51F, 0x9FBFE4A5, 0xE8B8D433,
    0x7807C9A2, 0x0F00F934, 0x9609A88E, 0xE10E9818, 0x7F6A0DBB, 0x086D3D2D, 0x91646C97, 0xE6635C01,
    0x6B6B51F4, 0x1C6C6162, 0x856530D8, 0xF262004E, 0x6C0695ED, 0x1B01A57B, 0x8208F4C1, 0xF50FC457,
    0x65B0D9C6, 0x12B7E950, 0x8BBEB8EA, 0xFCB9887C, 0x62DD1DDF, 0x15DA2D49, 0x8CD37CF3, 0xFBD44C65,
    0x4DB26158, 0x3AB551CE, 0xA3BC0074, 0xD4BB30E2, 0x4ADFA541, 0x3DD895D7, 0xA4D1C46D, 0xD3D6F4FB,
    0x4369E96A, 0x346ED9FC, 0xAD678846, 0xDA60B8D0, 0x44042D73, 0x33031DE5, 0xAA0A4C5F, 0xDD0D7CC9,
    0x5005713C, 0x270241AA, 0xBE0B1010, 0xC90C2086, 0x5768B525, 0x206F85B3, 0xB966D409, 0xCE61E49F,
    0x5EDEF90E, 0x29D9C998, 0xB0D09822, 0xC7D7A8B4, 0x59B33D17, 0x2EB40D81, 0xB7BD5C3B, 0xC0BA6CAD,
    0xEDB88320, 0x9ABFB3B6, 0x03B6E20C, 0x74B1D29A, 0xEAD54739, 0x9DD277AF, 0x04DB2615, 0x73DC1683,
    0xE3630B12, 0x94643B84, 0x0D6D6A3E, 0x7A6A5AA8, 0xE40ECF0B, 0x9309FF9D, 0x0A00AE27, 0x7D079EB1,
    0xF00F9344, 0x8708A3D2, 0x1E01F268, 0x6906C2FE, 0xF762575D, 0x806567CB, 0x196C3671, 0x6E6B06E7,
    0xFED41B76, 0x89D32BE0, 0x10DA7A5A, 0x67DD4ACC, 0xF9B9DF6F, 0x8EBEEFF9, 0x17B7BE43, 0x60B08ED5,
    0xD6D6A3E8, 0xA1D1937E, 0x38D8C2C4, 0x4FDFF252, 0xD1BB67F1, 0xA6BC5767, 0x3FB506DD, 0x48B2364B,
    0xD80D2BDA, 0xAF0A1B4C, 0x36034AF6, 0x41047A60, 0xDF60EFC3, 0xA867DF55, 0x316E8EEF, 0x4669BE79,
    0xCB61B38C, 0xBC66831A, 0x256FD2A0, 0x5268E236, 0xCC0C7795, 0xBB0B4703, 0x220216B9, 0x5505262F,
    0xC5BA3BBE, 0xB2BD0B28, 0x2BB45A92, 0x5CB36A04, 0xC2D7FFA7, 0xB5D0CF31, 0x2CD99E8B, 0x5BDEAE1D,
    0x9B64C2B0, 0xEC63F226, 0x756AA39C, 0x026D930A, 0x9C0906A9, 0xEB0E363F, 0x72076785, 0x05005713,
    0x95BF4A82, 0xE2B87A14, 0x7BB12BAE, 0x0CB61B38, 0x92D28E9B, 0xE5D5BE0D, 0x7CDCEFB7, 0x0BDBDF21,
    0x86D3D2D4, 0xF1D4E242, 0x68DDB3F8, 0x1FDA836E, 0x81BE16CD, 0xF6B9265B, 0x6FB077E1, 0x18B74777,
    0x88085AE6, 0xFF0F6A70, 0x66063BCA, 0x11010B5C, 0x8F659EFF, 0xF862AE69, 0x616BFFD3, 0x166CCF45,
    0xA00AE278, 0xD70DD2EE, 0x4E048354, 0x3903B3C2, 0xA7672661, 0xD06016F7, 0x4969474D, 0x3E6E77DB,
    0xAED16A4A, 0xD9D65ADC, 0x40DF0B66, 0x37D83BF0, 0xA9BCAE53, 0xDEBB9EC5, 0x47B2CF7F, 0x30B5FFE9,
    0xBDBDF21C, 0xCABAC28A, 0x53B39330, 0x24B4A3A6, 0xBAD03605, 0xCDD70693, 0x54DE5729, 0x23D967BF,
    0xB3667A2E, 0xC4614AB8, 0x5D681B02, 0x2A6F2B94, 0xB40BBE37, 0xC30C8EA1, 0x5A05DF1B, 0x2D02EF8D,
};

u32 SaveEngine_Crc32(const u8 *data, u32 size, u32 crc)
{
    u32 i;
    for (i = 0; i < size; i++)
        crc = sCrc32Table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    return crc;
}

static u32 ReadU32(const u8 *p)
{
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((u32)p[3] << 24);
}

static void WriteU32(u8 *p, u32 value)
{
    p[0] = value;
    p[1] = value >> 8;
    p[2] = value >> 16;
    p[3] = value >> 24;
}

// The CRC covers the whole sector except the CRC field itself.
u32 SaveEngine_SectorCrc(const u8 *sector)
{
    u32 crc = 0xFFFFFFFF;
    crc = SaveEngine_Crc32(sector, SAVE_SECTOR_FOOTER_OFFSET, crc);
    crc = SaveEngine_Crc32(sector + SAVE_SECTOR_KIND_OFFSET, SAVE_SECTOR_SIZE - SAVE_SECTOR_KIND_OFFSET, crc);
    return ~crc;
}

bool8 SaveEngine_IsSectorValid(const u8 *sector, u8 kind, u8 id)
{
    if (ReadU32(sector + SAVE_SECTOR_SIGNATURE_OFFSET2) != SAVE_SIGNATURE_V2)
        return FALSE;
    if (sector[SAVE_SECTOR_KIND_OFFSET] != kind || sector[SAVE_SECTOR_ID_OFFSET] != id)
        return FALSE;
    if ((sector[SAVE_SECTOR_VERSION_OFFSET] | (sector[SAVE_SECTOR_VERSION_OFFSET + 1] << 8)) != SAVE_FORMAT_VERSION)
        return FALSE;
    return ReadU32(sector + SAVE_SECTOR_FOOTER_OFFSET) == SaveEngine_SectorCrc(sector);
}

static bool8 IsBoxSectorValidAnyId(const u8 *sector, u8 *id)
{
    if (sector[SAVE_SECTOR_ID_OFFSET] >= SAVE_BOX_SECTOR_COUNT)
        return FALSE;
    if (!SaveEngine_IsSectorValid(sector, SAVE_SECTOR_KIND_BOX, sector[SAVE_SECTOR_ID_OFFSET]))
        return FALSE;
    *id = sector[SAVE_SECTOR_ID_OFFSET];
    return TRUE;
}

static void FinishSectorFooter(u8 *sector, u8 kind, u8 id, u32 counter)
{
    sector[SAVE_SECTOR_KIND_OFFSET] = kind;
    sector[SAVE_SECTOR_ID_OFFSET] = id;
    sector[SAVE_SECTOR_VERSION_OFFSET] = SAVE_FORMAT_VERSION & 0xFF;
    sector[SAVE_SECTOR_VERSION_OFFSET + 1] = SAVE_FORMAT_VERSION >> 8;
    WriteU32(sector + SAVE_SECTOR_SIGNATURE_OFFSET2, SAVE_SIGNATURE_V2);
    WriteU32(sector + SAVE_SECTOR_COUNTER_OFFSET2, counter);
    WriteU32(sector + SAVE_SECTOR_FOOTER_OFFSET, SaveEngine_SectorCrc(sector));
}

void SaveEngine_SetLayout(const struct SaveEngineLayout *layout)
{
    sLayout = layout;
}

void SaveEngine_ResetState(void)
{
    memset(&sEngine, 0, sizeof(sEngine));
    sEngine.newestCopy = NO_COPY;
    sEngine.backupId = NO_SECTOR;
}

void SaveEngine_SetGameId(u32 gameId)
{
    sEngine.gameId = gameId;
}

u32 SaveEngine_GetGameId(void)
{
    return sEngine.gameId;
}

u32 SaveEngine_GetCounter(void)
{
    return sEngine.counter;
}

u32 SaveEngine_GetLoadFlags(void)
{
    return sEngine.loadFlags;
}

bool8 SaveEngine_IsSaving(void)
{
    return sEngine.saving;
}

u32 SaveEngine_GetDamagedSectors(void)
{
    return sEngine.damaged;
}

void SaveEngine_ClearDamagedSectors(void)
{
    sEngine.damaged = 0;
}

static u16 BoxSectorMonCount(u8 boxSector)
{
    s32 first = boxSector * SAVE_BOX_MONS_PER_SECTOR;
    s32 count = (s32)sLayout->boxMonCount - first;
    if (count < 0)
        return 0;
    if (count > SAVE_BOX_MONS_PER_SECTOR)
        return SAVE_BOX_MONS_PER_SECTOR;
    return count;
}

static const u8 *BoxSectorRam(u8 boxSector)
{
    return sLayout->boxData + boxSector * SAVE_BOX_MONS_PER_SECTOR * SAVE_BOX_MON_SIZE;
}

// Builds the complete image of a box sector from RAM into gSaveEngineBuffer.
static u32 BuildBoxSector(u8 boxSector, u32 counter)
{
    u32 size = BoxSectorMonCount(boxSector) * SAVE_BOX_MON_SIZE;
    memset(gSaveEngineBuffer, 0, SAVE_SECTOR_SIZE);
    memcpy(gSaveEngineBuffer, BoxSectorRam(boxSector), size);
    WriteU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET, sEngine.gameId);
    FinishSectorFooter(gSaveEngineBuffer, SAVE_SECTOR_KIND_BOX, boxSector, counter);
    return ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET);
}

// Copies the box payload in gSaveEngineBuffer into RAM.
static void LoadBoxSectorToRam(u8 boxSector)
{
    memcpy(sLayout->boxData + boxSector * SAVE_BOX_MONS_PER_SECTOR * SAVE_BOX_MON_SIZE,
           gSaveEngineBuffer,
           BoxSectorMonCount(boxSector) * SAVE_BOX_MON_SIZE);
}

static void ClearBoxSectorRam(u8 boxSector)
{
    memset(sLayout->boxData + boxSector * SAVE_BOX_MONS_PER_SECTOR * SAVE_BOX_MON_SIZE,
           0,
           BoxSectorMonCount(boxSector) * SAVE_BOX_MON_SIZE);
}

u32 SaveEngine_GetPart0FragmentOffset(u8 fragment)
{
    u32 offset = SAVE_META_SIZE;
    u8 i;
    for (i = 0; i < fragment && i < sLayout->part0Count; i++)
        offset += sLayout->part0[i].size;
    return offset;
}

// Builds progress part `part` into gSaveEngineBuffer.
static void BuildProgressPart(u8 part, u32 counter)
{
    memset(gSaveEngineBuffer, 0, SAVE_SECTOR_SIZE);
    if (part == 0)
    {
        u32 offset = SAVE_META_SIZE;
        u8 i;
        WriteU32(gSaveEngineBuffer + SAVE_META_GAME_ID_OFFSET, sEngine.gameId);
        for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
            WriteU32(gSaveEngineBuffer + SAVE_META_BOX_CRC_OFFSET + 4 * i, sEngine.pendingCrc[i]);
        for (i = 0; i < sLayout->part0Count; i++)
        {
            memcpy(gSaveEngineBuffer + offset, sLayout->part0[i].data, sLayout->part0[i].size);
            offset += sLayout->part0[i].size;
        }
    }
    else
    {
        u32 start = (part - 1) * SAVE_SECTOR_PAYLOAD_SIZE;
        if (start < sLayout->progressTailSize)
        {
            u32 size = sLayout->progressTailSize - start;
            if (size > SAVE_SECTOR_PAYLOAD_SIZE)
                size = SAVE_SECTOR_PAYLOAD_SIZE;
            memcpy(gSaveEngineBuffer, sLayout->progressTail + start, size);
        }
    }
    FinishSectorFooter(gSaveEngineBuffer, SAVE_SECTOR_KIND_PROGRESS, part, counter);
}

static void LoadProgressPartToRam(u8 part)
{
    if (part == 0)
    {
        u32 offset = SAVE_META_SIZE;
        u8 i;
        sEngine.gameId = ReadU32(gSaveEngineBuffer + SAVE_META_GAME_ID_OFFSET);
        for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
            sEngine.committedCrc[i] = ReadU32(gSaveEngineBuffer + SAVE_META_BOX_CRC_OFFSET + 4 * i);
        for (i = 0; i < sLayout->part0Count; i++)
        {
            memcpy(sLayout->part0[i].data, gSaveEngineBuffer + offset, sLayout->part0[i].size);
            offset += sLayout->part0[i].size;
        }
    }
    else
    {
        u32 start = (part - 1) * SAVE_SECTOR_PAYLOAD_SIZE;
        if (start < sLayout->progressTailSize)
        {
            u32 size = sLayout->progressTailSize - start;
            if (size > SAVE_SECTOR_PAYLOAD_SIZE)
                size = SAVE_SECTOR_PAYLOAD_SIZE;
            memcpy(sLayout->progressTail + start, gSaveEngineBuffer, size);
        }
    }
}

static u8 CopyFirstSector(u8 copy)
{
    return copy == 0 ? SAVE_SECTOR_PROGRESS_A : SAVE_SECTOR_PROGRESS_B;
}

// Returns TRUE if all parts of the copy are valid, and sets *counter.
static bool8 CheckProgressCopy(u8 copy, u32 *counter, bool8 *anySignature)
{
    u8 part;
    bool8 valid = TRUE;
    u32 firstCounter = 0;

    for (part = 0; part < SAVE_PROGRESS_PARTS; part++)
    {
        SaveIo_ReadSector(CopyFirstSector(copy) + part, gSaveEngineBuffer);
        if (ReadU32(gSaveEngineBuffer + SAVE_SECTOR_SIGNATURE_OFFSET2) == SAVE_SIGNATURE_V2)
            *anySignature = TRUE;
        if (!SaveEngine_IsSectorValid(gSaveEngineBuffer, SAVE_SECTOR_KIND_PROGRESS, part))
        {
            valid = FALSE;
            continue;
        }
        if (part == 0)
            firstCounter = ReadU32(gSaveEngineBuffer + SAVE_SECTOR_COUNTER_OFFSET2);
        else if (ReadU32(gSaveEngineBuffer + SAVE_SECTOR_COUNTER_OFFSET2) != firstCounter)
            valid = FALSE;
    }
    *counter = firstCounter;
    return valid;
}

static bool8 FindNewestCopy(u8 *copyOut, u32 *counterOut, bool8 *otherDamaged, bool8 *anySignature)
{
    u32 counters[2];
    bool8 valid[2];
    bool8 signature[2] = {FALSE, FALSE};
    u8 best;

    valid[0] = CheckProgressCopy(0, &counters[0], &signature[0]);
    valid[1] = CheckProgressCopy(1, &counters[1], &signature[1]);
    *anySignature = signature[0] || signature[1];

    if (!valid[0] && !valid[1])
        return FALSE;

    if (valid[0] && valid[1])
        best = (counters[1] > counters[0]) ? 1 : 0;
    else
        best = valid[0] ? 0 : 1;

    *copyOut = best;
    *counterOut = counters[best];
    *otherDamaged = !valid[1 - best] && signature[1 - best];
    return TRUE;
}

bool8 SaveEngine_ReadNewestPart0(void)
{
    u8 copy;
    u32 counter;
    bool8 otherDamaged, anySignature;

    if (!FindNewestCopy(&copy, &counter, &otherDamaged, &anySignature))
        return FALSE;
    SaveIo_ReadSector(CopyFirstSector(copy), gSaveEngineBuffer);
    return TRUE;
}

static void ReadBackupState(void)
{
    u8 id;
    SaveIo_ReadSector(SAVE_SECTOR_BOX_BACKUP, gSaveEngineBuffer);
    if (IsBoxSectorValidAnyId(gSaveEngineBuffer, &id))
    {
        sEngine.backupValid = TRUE;
        sEngine.backupId = id;
        sEngine.backupCrc = ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET);
        sEngine.backupGameId = ReadU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET);
    }
    else
    {
        sEngine.backupValid = FALSE;
        sEngine.backupId = NO_SECTOR;
        sEngine.backupCrc = 0;
        sEngine.backupGameId = 0;
    }
}

static bool8 IsBackupFor(u8 boxSector)
{
    return sEngine.backupValid
        && sEngine.backupId == boxSector
        && sEngine.backupGameId == sEngine.gameId;
}

static void LoadBoxSectors(void)
{
    u8 i;

    for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
    {
        bool8 valid;
        u32 crc, gameId;

        SaveIo_ReadSector(SAVE_SECTOR_BOX_FIRST + i, gSaveEngineBuffer);
        valid = SaveEngine_IsSectorValid(gSaveEngineBuffer, SAVE_SECTOR_KIND_BOX, i);
        crc = ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET);
        gameId = ReadU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET);

        if (valid && gameId == sEngine.gameId && crc == sEngine.committedCrc[i])
        {
            // Matches the commit
            LoadBoxSectorToRam(i);
        }
        else if (IsBackupFor(i) && sEngine.backupCrc == sEngine.committedCrc[i])
        {
            // An interrupted save changed this sector; roll back to the commit
            SaveIo_ReadSector(SAVE_SECTOR_BOX_BACKUP, gSaveEngineBuffer);
            LoadBoxSectorToRam(i);
            sEngine.loadFlags |= SAVE_LOAD_FLAG_BOX_RESTORED;
        }
        else if (valid && gameId == sEngine.gameId)
        {
            // Written by an interrupted save that changed several sectors
            LoadBoxSectorToRam(i);
            sEngine.loadFlags |= SAVE_LOAD_FLAG_BOX_UNCOMMITTED;
        }
        else if (IsBackupFor(i))
        {
            // Torn write
            SaveIo_ReadSector(SAVE_SECTOR_BOX_BACKUP, gSaveEngineBuffer);
            LoadBoxSectorToRam(i);
            sEngine.loadFlags |= SAVE_LOAD_FLAG_BOX_RESTORED;
        }
        else
        {
            ClearBoxSectorRam(i);
            // A valid sector from another game was left by an interrupted
            // first save of a new game; it is not part of this game.
            if (!valid)
                sEngine.loadFlags |= SAVE_LOAD_FLAG_BOX_LOST;
        }
    }
}

static bool8 HasLegacySave(void)
{
    u8 sector;
    for (sector = 0; sector < SAVE_SECTOR_BOX_BACKUP; sector++)
    {
        SaveIo_ReadSector(sector, gSaveEngineBuffer);
        if (ReadU32(gSaveEngineBuffer + SAVE_SECTOR_SIGNATURE_OFFSET2) == SAVE_SIGNATURE_LEGACY)
            return TRUE;
    }
    return FALSE;
}

u8 SaveEngine_Load(void)
{
    u8 copy, part;
    u32 counter;
    bool8 otherDamaged, anySignature;

    SaveEngine_ResetState();

    if (!FindNewestCopy(&copy, &counter, &otherDamaged, &anySignature))
    {
        ReadBackupState();
        if (anySignature)
            return SAVE_ENGINE_LOAD_CORRUPT;
        if (HasLegacySave())
            return SAVE_ENGINE_LOAD_OUTDATED;
        return SAVE_ENGINE_LOAD_EMPTY;
    }

    for (part = 0; part < SAVE_PROGRESS_PARTS; part++)
    {
        SaveIo_ReadSector(CopyFirstSector(copy) + part, gSaveEngineBuffer);
        LoadProgressPartToRam(part);
    }
    sEngine.newestCopy = copy;
    sEngine.counter = counter;

    ReadBackupState();
    LoadBoxSectors();

    return otherDamaged ? SAVE_ENGINE_LOAD_OK_BACKUP : SAVE_ENGINE_LOAD_OK;
}

static bool8 IsMonEmpty(const u8 *mon)
{
    u32 i;
    for (i = 0; i < SAVE_BOX_MON_SIZE; i++)
    {
        if (mon[i] != 0)
            return FALSE;
    }
    return TRUE;
}

// Chooses the interim value of one record while a save is in progress: keep
// the old record if the new one only removes something, otherwise take the
// new one. Returns TRUE if the old record is kept although it differs.
static bool8 UnionKeepsOld(const u8 *oldMon, const u8 *newMon)
{
    if (memcmp(oldMon, newMon, SAVE_BOX_MON_SIZE) == 0)
        return FALSE;
    if (IsMonEmpty(oldMon))
        return FALSE;
    if (IsMonEmpty(newMon))
        return TRUE;
    return !SaveIo_MonChangeGainsData(oldMon, newMon);
}

// Whether the old record's Pokémon would vanish from this sector's interim
// image because its slot is taken by a different Pokémon and it does not
// appear anywhere else in the sector's new contents.
static bool8 IsDisplaced(const u8 *oldMon, const u8 *newMon, const u8 *ramSector, u16 count)
{
    u16 i;

    if (IsMonEmpty(oldMon) || IsMonEmpty(newMon))
        return FALSE;
    if (memcmp(oldMon, newMon, SAVE_BOX_MON_IDENTITY_SIZE) == 0)
        return FALSE;
    for (i = 0; i < count; i++)
    {
        if (memcmp(oldMon, ramSector + i * SAVE_BOX_MON_SIZE, SAVE_BOX_MON_IDENTITY_SIZE) == 0)
            return FALSE;
    }
    return TRUE;
}

// gSaveEngineBuffer holds the valid flash image of a sector of this game.
static u8 ClassifySectorChange(u8 boxSector)
{
    const u8 *ram = BoxSectorRam(boxSector);
    u16 count = BoxSectorMonCount(boxSector);
    bool8 gains = FALSE, keeps = FALSE;
    u16 i;

    for (i = 0; i < count; i++)
    {
        const u8 *oldMon = gSaveEngineBuffer + i * SAVE_BOX_MON_SIZE;
        const u8 *newMon = ram + i * SAVE_BOX_MON_SIZE;
        if (memcmp(oldMon, newMon, SAVE_BOX_MON_SIZE) == 0)
            continue;
        if (UnionKeepsOld(oldMon, newMon))
        {
            keeps = TRUE;
        }
        else
        {
            gains = TRUE;
            if (IsDisplaced(oldMon, newMon, ram, count))
                keeps = TRUE;
        }
    }

    if (!gains)
        return WRITE_AFTER_COMMIT;
    if (!keeps)
        return WRITE_BEFORE_COMMIT;
    return WRITE_UNION_THEN_FINAL;
}

// Builds the interim image of a box sector by merging its flash image with
// RAM, so that a record leaving the sector stays until the commit. A Pokémon
// whose slot is taken by a different Pokémon is moved to a slot that is empty
// both before and after the save, if there is one.
static void BuildUnionBoxSector(u8 boxSector, u32 counter)
{
    const u8 *ram = BoxSectorRam(boxSector);
    u16 count = BoxSectorMonCount(boxSector);
    u16 i, freeSlot = 0;

    SaveIo_ReadSector(SAVE_SECTOR_BOX_FIRST + boxSector, gSaveEngineBuffer);
    if (!SaveEngine_IsSectorValid(gSaveEngineBuffer, SAVE_SECTOR_KIND_BOX, boxSector)
     || ReadU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET) != sEngine.gameId)
    {
        BuildBoxSector(boxSector, counter);
        return;
    }

    for (i = 0; i < count; i++)
    {
        u8 *oldMon = gSaveEngineBuffer + i * SAVE_BOX_MON_SIZE;
        const u8 *newMon = ram + i * SAVE_BOX_MON_SIZE;

        if (UnionKeepsOld(oldMon, newMon))
            continue;
        if (IsDisplaced(oldMon, newMon, ram, count))
        {
            while (freeSlot < count
                && !(IsMonEmpty(gSaveEngineBuffer + freeSlot * SAVE_BOX_MON_SIZE)
                  && IsMonEmpty(ram + freeSlot * SAVE_BOX_MON_SIZE)))
                freeSlot++;
            if (freeSlot < count)
                memcpy(gSaveEngineBuffer + freeSlot * SAVE_BOX_MON_SIZE, oldMon, SAVE_BOX_MON_SIZE);
        }
        memcpy(oldMon, newMon, SAVE_BOX_MON_SIZE);
    }
    FinishSectorFooter(gSaveEngineBuffer, SAVE_SECTOR_KIND_BOX, boxSector, counter);
}

u8 SaveEngine_BeginSave(u8 flags)
{
    u8 i;
    u8 pre[SAVE_BOX_SECTOR_COUNT], post[SAVE_BOX_SECTOR_COUNT];
    bool8 useUnion[SAVE_BOX_SECTOR_COUNT];
    u8 numPre = 0, numPost = 0;

    sEngine.saving = TRUE;
    sEngine.committed = FALSE;
    sEngine.flags = flags;
    sEngine.newCounter = sEngine.counter + 1;
    sEngine.targetCopy = (sEngine.newestCopy == 0) ? 1 : 0;
    sEngine.stepIndex = 0;
    sEngine.numSteps = 0;
    sEngine.damaged = 0;

    ReadBackupState();

    for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
    {
        bool8 valid, flashCommitted;
        u32 gameId;
        u16 size = BoxSectorMonCount(i) * SAVE_BOX_MON_SIZE;

        useUnion[i] = FALSE;
        SaveIo_ReadSector(SAVE_SECTOR_BOX_FIRST + i, gSaveEngineBuffer);
        valid = SaveEngine_IsSectorValid(gSaveEngineBuffer, SAVE_SECTOR_KIND_BOX, i);
        gameId = ReadU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET);
        flashCommitted = valid
                      && gameId == sEngine.gameId
                      && ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET) == sEngine.committedCrc[i];

        if (valid
         && gameId == sEngine.gameId
         && memcmp(gSaveEngineBuffer, BoxSectorRam(i), size) == 0)
        {
            sEngine.pendingCrc[i] = ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET);
            continue;
        }

        if (IsBackupFor(i) && !flashCommitted)
        {
            // The backup still holds data this sector was loaded from. Write
            // this sector first, before any other sector reuses the backup.
            if (numPre > 0)
                pre[numPre] = pre[0];
            numPre++;
            pre[0] = i;
        }
        else if (!valid)
        {
            pre[numPre++] = i;        // Nothing usable on flash to protect
        }
        else if (gameId != sEngine.gameId)
        {
            post[numPost++] = i;      // Keep another game's data until the commit
        }
        else
        {
            switch (ClassifySectorChange(i))
            {
            case WRITE_AFTER_COMMIT:
                post[numPost++] = i;
                break;
            case WRITE_BEFORE_COMMIT:
                pre[numPre++] = i;
                break;
            case WRITE_UNION_THEN_FINAL:
                useUnion[i] = TRUE;
                pre[numPre++] = i;
                post[numPost++] = i;
                break;
            }
        }

        sEngine.pendingCrc[i] = BuildBoxSector(i, sEngine.newCounter);
    }

    for (i = 0; i < numPre; i++)
    {
        sEngine.steps[sEngine.numSteps++] = STEP(STEP_BACKUP, pre[i]);
        sEngine.steps[sEngine.numSteps++] = STEP(useUnion[pre[i]] ? STEP_WRITE_BOX_UNION : STEP_WRITE_BOX, pre[i]);
    }
    for (i = 1; i < SAVE_PROGRESS_PARTS; i++)
        sEngine.steps[sEngine.numSteps++] = STEP(STEP_WRITE_PROGRESS, i);
    sEngine.steps[sEngine.numSteps++] = STEP(STEP_WRITE_PROGRESS, 0);
    if (flags & SAVE_ENGINE_FLAG_TWO_PHASE)
        sEngine.steps[sEngine.numSteps++] = STEP(STEP_COMMIT_BYTE, 0);
    for (i = 0; i < numPost; i++)
    {
        sEngine.steps[sEngine.numSteps++] = STEP(STEP_BACKUP, post[i]);
        sEngine.steps[sEngine.numSteps++] = STEP(STEP_WRITE_BOX, post[i]);
    }

    return SAVE_ENGINE_BUSY;
}

void SaveEngine_GetPlanCounts(u8 *beforeCommit, u8 *afterCommit)
{
    u8 i;
    bool8 afterProgress = FALSE;

    *beforeCommit = 0;
    *afterCommit = 0;
    for (i = 0; i < sEngine.numSteps; i++)
    {
        u8 type = STEP_TYPE(sEngine.steps[i]);
        if (type == STEP_WRITE_PROGRESS)
            afterProgress = TRUE;
        else if ((type == STEP_WRITE_BOX || type == STEP_WRITE_BOX_UNION) && afterProgress)
            (*afterCommit)++;
        else if (type == STEP_WRITE_BOX || type == STEP_WRITE_BOX_UNION)
            (*beforeCommit)++;
    }
}

static void MarkDamaged(u8 sector)
{
    sEngine.damaged |= (1u << sector);
}

static bool8 DoBackup(u8 boxSector)
{
    bool8 flashValid, flashCommitted, backupCommitted;
    u32 flashCrc, flashGameId;

    SaveIo_ReadSector(SAVE_SECTOR_BOX_FIRST + boxSector, gSaveEngineBuffer);
    flashValid = SaveEngine_IsSectorValid(gSaveEngineBuffer, SAVE_SECTOR_KIND_BOX, boxSector);
    flashCrc = ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET);
    flashGameId = ReadU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET);

    flashCommitted = flashValid && flashCrc == sEngine.committedCrc[boxSector] && flashGameId == sEngine.gameId;
    backupCommitted = IsBackupFor(boxSector) && sEngine.backupCrc == sEngine.committedCrc[boxSector];

    if (!flashCommitted)
    {
        // Never replace the only copy of what the current commit refers to,
        // or the only valid copy of this sector.
        if (backupCommitted)
            return FALSE;
        if (!flashValid && sEngine.backupValid && sEngine.backupId == boxSector)
            return FALSE;
        if (!flashValid)
        {
            // Nothing valid to preserve; back up the new image so a torn
            // write can still be completed from the backup.
            BuildBoxSector(boxSector, sEngine.newCounter);
        }
    }

    if (sEngine.backupValid
     && sEngine.backupId == boxSector
     && ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET) == sEngine.backupCrc)
        return FALSE; // Already backed up

    // The backup sector is about to change; forget the old description first.
    sEngine.backupValid = FALSE;
    sEngine.backupId = NO_SECTOR;
    if (SaveIo_ProgramSector(SAVE_SECTOR_BOX_BACKUP, gSaveEngineBuffer))
    {
        MarkDamaged(SAVE_SECTOR_BOX_BACKUP);
        return TRUE;
    }
    sEngine.backupValid = TRUE;
    sEngine.backupId = boxSector;
    sEngine.backupCrc = ReadU32(gSaveEngineBuffer + SAVE_SECTOR_FOOTER_OFFSET);
    sEngine.backupGameId = ReadU32(gSaveEngineBuffer + SAVE_BOX_GAME_ID_OFFSET);
    return FALSE;
}

static bool8 DoWriteBox(u8 boxSector, bool8 useUnion)
{
    if (useUnion)
    {
        // The commit refers to the final image, which is written afterwards.
        BuildUnionBoxSector(boxSector, sEngine.newCounter);
    }
    else
    {
        u32 crc = BuildBoxSector(boxSector, sEngine.newCounter);
        if (!sEngine.committed)
            sEngine.pendingCrc[boxSector] = crc;
    }

    if (SaveIo_ProgramSector(SAVE_SECTOR_BOX_FIRST + boxSector, gSaveEngineBuffer))
    {
        MarkDamaged(SAVE_SECTOR_BOX_FIRST + boxSector);
        return TRUE;
    }
    return FALSE;
}

static void ApplyCommit(void)
{
    u8 i;
    sEngine.committed = TRUE;
    sEngine.counter = sEngine.newCounter;
    sEngine.newestCopy = sEngine.targetCopy;
    for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
        sEngine.committedCrc[i] = sEngine.pendingCrc[i];
}

static bool8 DoWriteProgress(u8 part)
{
    u8 sector = CopyFirstSector(sEngine.targetCopy) + part;
    bool8 failed;

    BuildProgressPart(part, sEngine.newCounter);
    if (part == 0 && (sEngine.flags & SAVE_ENGINE_FLAG_TWO_PHASE))
        failed = SaveIo_ProgramSectorSkipByte(sector, gSaveEngineBuffer, SAVE_SECTOR_SIGNATURE_OFFSET2);
    else
        failed = SaveIo_ProgramSector(sector, gSaveEngineBuffer);

    if (failed)
    {
        MarkDamaged(sector);
        return TRUE;
    }
    if (part == 0 && !(sEngine.flags & SAVE_ENGINE_FLAG_TWO_PHASE))
        ApplyCommit();
    return FALSE;
}

static bool8 DoCommitByte(void)
{
    u8 sector = CopyFirstSector(sEngine.targetCopy);
    if (SaveIo_ProgramByte(sector, SAVE_SECTOR_SIGNATURE_OFFSET2, SAVE_SIGNATURE_V2 & 0xFF))
    {
        MarkDamaged(sector);
        return TRUE;
    }
    ApplyCommit();
    return FALSE;
}

u8 SaveEngine_Step(void)
{
    u8 step;
    bool8 failed = FALSE;

    if (!sEngine.saving)
        return SAVE_ENGINE_ERROR;
    if (sEngine.stepIndex >= sEngine.numSteps)
    {
        sEngine.saving = FALSE;
        return SAVE_ENGINE_DONE;
    }

    step = sEngine.steps[sEngine.stepIndex];
    if (STEP_TYPE(step) == STEP_COMMIT_BYTE)
        return SAVE_ENGINE_WAITING_FOR_COMMIT;

    switch (STEP_TYPE(step))
    {
    case STEP_BACKUP:
        failed = DoBackup(STEP_ARG(step));
        break;
    case STEP_WRITE_BOX:
        failed = DoWriteBox(STEP_ARG(step), FALSE);
        break;
    case STEP_WRITE_BOX_UNION:
        failed = DoWriteBox(STEP_ARG(step), TRUE);
        break;
    case STEP_WRITE_PROGRESS:
        failed = DoWriteProgress(STEP_ARG(step));
        break;
    }

    if (failed)
    {
        sEngine.saving = FALSE;
        return SAVE_ENGINE_ERROR;
    }

    sEngine.stepIndex++;
    if (sEngine.stepIndex >= sEngine.numSteps)
    {
        sEngine.saving = FALSE;
        return SAVE_ENGINE_DONE;
    }
    if (STEP_TYPE(sEngine.steps[sEngine.stepIndex]) == STEP_COMMIT_BYTE)
        return SAVE_ENGINE_WAITING_FOR_COMMIT;
    return SAVE_ENGINE_BUSY;
}

u8 SaveEngine_FinishCommit(void)
{
    if (!sEngine.saving
     || sEngine.stepIndex >= sEngine.numSteps
     || STEP_TYPE(sEngine.steps[sEngine.stepIndex]) != STEP_COMMIT_BYTE)
        return SAVE_ENGINE_ERROR;

    if (DoCommitByte())
    {
        sEngine.saving = FALSE;
        return SAVE_ENGINE_ERROR;
    }
    sEngine.stepIndex++;
    if (sEngine.stepIndex >= sEngine.numSteps)
    {
        sEngine.saving = FALSE;
        return SAVE_ENGINE_DONE;
    }
    return SAVE_ENGINE_BUSY;
}

#ifdef SAVE_ENGINE_HOST
u32 SaveEngine_HostStateSize(void)
{
    return sizeof(sEngine);
}

void SaveEngine_HostSaveState(void *dst)
{
    memcpy(dst, &sEngine, sizeof(sEngine));
}

void SaveEngine_HostLoadState(const void *src)
{
    memcpy(&sEngine, src, sizeof(sEngine));
}
#endif

u8 SaveEngine_SaveAll(void)
{
    u8 result;

    SaveEngine_BeginSave(0);
    do
    {
        result = SaveEngine_Step();
    } while (result == SAVE_ENGINE_BUSY);
    return result;
}
