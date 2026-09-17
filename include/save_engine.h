#ifndef GUARD_SAVE_ENGINE_H
#define GUARD_SAVE_ENGINE_H

// BPE 2.1 save format engine.
//
// This file has no game dependencies so that the exact same code can be
// compiled for the GBA and for the host-side power-cut simulator in
// BPETools/save_sim. The game-facing wrapper is src/save.c.
//
// Flash layout (32 x 4 KiB sectors):
//   0 - 4    Progress copy A (part 0: meta + SaveBlock2 + box header + SaveBlock3,
//            parts 1-4: SaveBlock1)
//   5 - 9    Progress copy B
//   10 - 28  Box sectors 0-18, 66 packed Pokémon each, stored once
//   29       Box backup (exact image of the box sector being rewritten)
//   30 - 31  Hall of Fame (unchanged legacy format)
//
// Every progress/box sector ends with a 16-byte footer:
//   u32 crc32 (covers the whole sector except this field), u8 kind, u8 id,
//   u16 version, u32 signature, u32 counter
// The signature sits at the same offset as the legacy one so that older
// saves can be recognized.
//
// The newest valid progress copy is the commit point. It records the game id
// and the CRC of every box sector image that belongs to that commit. A save
// writes, in order: box sectors that gain data, the progress copy, then box
// sectors that only lose data. A sector that both gains and loses data gets an
// interim image before the commit that still holds what is leaving it, and its
// final image after the commit. Each box sector write is preceded by a copy of
// its current image to the backup sector. When loading, a box sector that
// does not match the commit is rolled back from the backup when the backup
// does match; torn sectors are also restored from the backup.

#ifdef SAVE_ENGINE_HOST
#include <stdint.h>
#include <stdbool.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef uint8_t bool8;
typedef uint32_t bool32;
#ifndef TRUE
#define TRUE 1
#define FALSE 0
#endif
#endif

#define SAVE_SECTOR_SIZE              4096
#define SAVE_SECTOR_PAYLOAD_SIZE      4080
#define SAVE_SECTOR_FOOTER_OFFSET     SAVE_SECTOR_PAYLOAD_SIZE
#define SAVE_SECTOR_KIND_OFFSET       4084
#define SAVE_SECTOR_ID_OFFSET         4085
#define SAVE_SECTOR_VERSION_OFFSET    4086
#define SAVE_SECTOR_SIGNATURE_OFFSET2 4088
#define SAVE_SECTOR_COUNTER_OFFSET2   4092

#define SAVE_SIGNATURE_V2             0x32455042 // "BPE2"
#define SAVE_SIGNATURE_LEGACY         0x08012025
#define SAVE_FORMAT_VERSION           1

#define SAVE_SECTOR_KIND_PROGRESS     1
#define SAVE_SECTOR_KIND_BOX          2

#define SAVE_PROGRESS_PARTS           5
#define SAVE_SECTOR_PROGRESS_A        0
#define SAVE_SECTOR_PROGRESS_B        5
#define SAVE_SECTOR_BOX_FIRST         10
#define SAVE_BOX_SECTOR_COUNT         19
#define SAVE_SECTOR_BOX_BACKUP        29
#define SAVE_SECTOR_HOF_1             30
#define SAVE_SECTOR_HOF_2             31
#define SAVE_SECTOR_COUNT             32

#define SAVE_BOX_MON_SIZE             60
#define SAVE_BOX_MONS_PER_SECTOR      66
// Every non-empty record starts with bytes that identify the Pokémon
// (personality and original trainer id).
#define SAVE_BOX_MON_IDENTITY_SIZE    8
#define SAVE_BOX_GAME_ID_OFFSET       (SAVE_BOX_MON_SIZE * SAVE_BOX_MONS_PER_SECTOR)
#define SAVE_BOX_MAX_MONS             (SAVE_BOX_MONS_PER_SECTOR * SAVE_BOX_SECTOR_COUNT)

// Progress part 0 begins with this metadata block.
#define SAVE_META_GAME_ID_OFFSET      0
#define SAVE_META_BOX_CRC_OFFSET      4
#define SAVE_META_FLAGS_OFFSET        (4 + 4 * SAVE_BOX_SECTOR_COUNT)
#define SAVE_META_SIZE                (SAVE_META_FLAGS_OFFSET + 4)

#define SAVE_ENGINE_MAX_FRAGMENTS     4
#define SAVE_ENGINE_MAX_STEPS         (SAVE_BOX_SECTOR_COUNT * 4 + SAVE_PROGRESS_PARTS + 1)

// Load results
enum
{
    SAVE_ENGINE_LOAD_EMPTY,      // No save of any format
    SAVE_ENGINE_LOAD_OK,         // Newest copy loaded, the other copy is fine or unused
    SAVE_ENGINE_LOAD_OK_BACKUP,  // A progress copy was damaged; the other copy was loaded
    SAVE_ENGINE_LOAD_CORRUPT,    // Format sectors exist but no copy is valid
    SAVE_ENGINE_LOAD_OUTDATED,   // Only saves from an older BPE format exist
};

// Load flags (SaveEngine_GetLoadFlags)
#define SAVE_LOAD_FLAG_BOX_RESTORED  (1 << 0) // A box sector was restored from the backup
#define SAVE_LOAD_FLAG_BOX_LOST      (1 << 1) // A box sector was unreadable and had no backup
#define SAVE_LOAD_FLAG_BOX_UNCOMMITTED (1 << 2) // A box sector newer than the commit was kept

// Step results
enum
{
    SAVE_ENGINE_BUSY,
    SAVE_ENGINE_DONE,
    SAVE_ENGINE_ERROR,
    SAVE_ENGINE_WAITING_FOR_COMMIT, // Two-phase save: call SaveEngine_FinishCommit
};

// SaveEngine_BeginSave flags
#define SAVE_ENGINE_FLAG_TWO_PHASE    (1 << 0)

struct SaveEngineFragment
{
    u8 *data;
    u32 size;
};

struct SaveEngineLayout
{
    // Progress part 0 contents after the metadata block
    struct SaveEngineFragment part0[SAVE_ENGINE_MAX_FRAGMENTS];
    u8 part0Count;
    // SaveBlock1, split across parts 1-4
    u8 *progressTail;
    u32 progressTailSize;
    // Packed PC Pokémon
    u8 *boxData;
    u16 boxMonCount;
};

// Flash access, implemented by the platform (src/save.c on the GBA).
// Read a whole sector.
void SaveIo_ReadSector(u8 sector, u8 *dst);
// Erase and program a whole sector, then verify. Returns TRUE on failure.
bool8 SaveIo_ProgramSector(u8 sector, const u8 *src);
// Erase and program a whole sector except for the byte at skipOffset, which
// is left erased. Verifies everything else. Returns TRUE on failure.
bool8 SaveIo_ProgramSectorSkipByte(u8 sector, const u8 *src, u16 skipOffset);
// Program one byte of an already-written sector. Returns TRUE on failure.
bool8 SaveIo_ProgramByte(u8 sector, u16 offset, u8 value);
// Both records are non-empty and differ. Returns TRUE if the new record could
// hold something that is not present anywhere else in the old save, such as a
// different Pokémon or a newly given held item. Such sectors are written
// before the commit; sectors that only lose data are written after it.
bool8 SaveIo_MonChangeGainsData(const u8 *oldMon, const u8 *newMon);

extern u8 gSaveEngineBuffer[SAVE_SECTOR_SIZE];

u32 SaveEngine_Crc32(const u8 *data, u32 size, u32 crc);
u32 SaveEngine_SectorCrc(const u8 *sector);
bool8 SaveEngine_IsSectorValid(const u8 *sector, u8 kind, u8 id);

void SaveEngine_SetLayout(const struct SaveEngineLayout *layout);
void SaveEngine_ResetState(void);
void SaveEngine_SetGameId(u32 gameId);
u32 SaveEngine_GetGameId(void);
u32 SaveEngine_GetCounter(void);
u8 SaveEngine_Load(void);
u32 SaveEngine_GetLoadFlags(void);
u8 SaveEngine_BeginSave(u8 flags);
u8 SaveEngine_Step(void);
u8 SaveEngine_FinishCommit(void);
u8 SaveEngine_SaveAll(void);
bool8 SaveEngine_IsSaving(void);
// Number of box sectors the current save writes before and after the commit.
void SaveEngine_GetPlanCounts(u8 *beforeCommit, u8 *afterCommit);
u32 SaveEngine_GetDamagedSectors(void);
void SaveEngine_ClearDamagedSectors(void);
// Reads part 0 of the newest valid progress copy into gSaveEngineBuffer.
// Returns FALSE if there is no valid copy.
bool8 SaveEngine_ReadNewestPart0(void);
u32 SaveEngine_GetPart0FragmentOffset(u8 fragment);

#endif // GUARD_SAVE_ENGINE_H
