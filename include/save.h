#ifndef GUARD_SAVE_H
#define GUARD_SAVE_H

#include "main.h"
#include "save_engine.h"

// See include/save_engine.h for the BPE 2.1 flash layout.

// Legacy sector format, still used by the Hall of Fame sectors: 3968 bytes of
// data, 116 unused bytes, then a 12-byte footer.
#define SECTOR_DATA_SIZE 3968
#define SAVE_BLOCK_3_CHUNK_SIZE 116
#define SECTOR_FOOTER_SIZE 12
#define SECTOR_SIZE (SECTOR_DATA_SIZE + SAVE_BLOCK_3_CHUNK_SIZE + SECTOR_FOOTER_SIZE)

// If the sector's signature field is not this value then the sector is either invalid or empty.
#define SECTOR_SIGNATURE SAVE_SIGNATURE_LEGACY

#define SECTOR_ID_HOF_1              SAVE_SECTOR_HOF_1
#define SECTOR_ID_HOF_2              SAVE_SECTOR_HOF_2
#define SECTORS_COUNT                SAVE_SECTOR_COUNT

#define NUM_HOF_SECTORS 2

#define SAVE_STATUS_EMPTY    0
#define SAVE_STATUS_OK       1
#define SAVE_STATUS_CORRUPT  2
#define SAVE_STATUS_OUTDATED 3 // BPE: only a save from before the 2.1 format exists
#define SAVE_STATUS_NO_FLASH 4
#define SAVE_STATUS_ERROR    0xFF

// Do save types
enum
{
    SAVE_NORMAL,
    SAVE_LINK, // Link / Battle Frontier
    SAVE_EREADER, // deprecated in Emerald
    SAVE_HALL_OF_FAME,
    SAVE_OVERWRITE_DIFFERENT_FILE,
    SAVE_HALL_OF_FAME_ERASE_BEFORE // unused
};

struct SaveSector
{
    u8 data[SECTOR_DATA_SIZE];
    u8 saveBlock3Chunk[SAVE_BLOCK_3_CHUNK_SIZE];
    u16 id;
    u16 checksum;
    u32 signature;
    u32 counter;
}; // size is SECTOR_SIZE (0x1000)

extern u32 gDamagedSaveSectors;
extern u16 gSaveFileStatus;
extern MainCallback gGameContinueCallback;

#if TESTING
extern bool8 gSaveTestPowerCutEnabled;
extern u32 gSaveTestFlashBudget;
extern bool8 gSaveTestPowerLost;
u32 Save_TestCountSectorWrites(void);
#endif

void ClearSaveData(void);
void Save_ResetSaveCounters(void);
void Save_StartNewGameIdentity(void);
bool8 Save_IsBlockedByOutdatedSave(void);
u8 HandleSavingData(u8 saveType);
u8 TrySavingData(u8 saveType);
bool8 LinkFullSave_Init(void);
bool8 LinkFullSave_WriteSector(void);
bool8 LinkFullSave_ReplaceLastSector(void);
bool8 LinkFullSave_SetLastSectorSignature(void);
bool8 WriteSaveBlock2(void);
bool8 WriteSaveBlock1Sector(void);
u8 LoadGameSave(u8 saveType);
u16 GetSaveBlocksPointersBaseOffset(void);
void Task_LinkFullSave(u8 taskId);

// save_failed_screen.c
void DoSaveFailedScreen(u8 saveType);

#endif // GUARD_SAVE_H
