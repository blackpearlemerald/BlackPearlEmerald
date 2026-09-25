// Host-side power-cut simulator for the BPE 2.1 save engine.
//
// Compiles src/save_engine.c unchanged against a fake 32-sector flash chip,
// plays random PC, party and progress changes between saves, cuts power
// during saves at every sector boundary and at random bytes, reloads, and
// checks the result. It also damages committed saves on purpose, feeds the
// loader random flash contents, and simulates failed flash verification.
//
// Build and run (see BPETools/save_sim/run_save_sim.py):
//   cc -O2 -g -fsanitize=address,undefined -DSAVE_ENGINE_HOST -iquote include
//      -o save_sim BPETools/save_sim/save_sim.c src/save_engine.c
//   ./save_sim <seed> <sessions>
//
// Exit status is 0 only when every check passes.

#ifndef SAVE_ENGINE_HOST
#define SAVE_ENGINE_HOST
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "save_engine.h"

// Sizes mirror the game (checked against the game build by test/save.c).
#define SB2_SIZE        2852
#define HEADER_SIZE     812
#define SB3_SIZE        4
#define SB1_SIZE        16176
#define BOXES           41
#define IN_BOX          30
#define MON_COUNT       (BOXES * IN_BOX)
#define MON_SIZE        SAVE_BOX_MON_SIZE
#define PARTY_OFFSET    1000 // fake party inside SaveBlock1
#define PARTY_SIZE      6
#define ITEM_BYTE       20   // fake held item inside a Pokémon record
#define BAG_OFFSET      3000 // fake bag inside SaveBlock1: 256 item counts
#define NUM_ITEMS       256

struct Game
{
    u8 sb2[SB2_SIZE];
    u8 header[HEADER_SIZE];
    u8 sb3[SB3_SIZE];
    u8 sb1[SB1_SIZE];
    u8 boxes[MON_COUNT * MON_SIZE];
    u32 gameId;
};

u32 SaveEngine_HostStateSize(void);
void SaveEngine_HostSaveState(void *dst);
void SaveEngine_HostLoadState(const void *src);

static struct Game ram;
static struct SaveEngineLayout layout;
static void *engineStateA, *engineStateB;

// ---------------------------------------------------------------------------
// Statistics and failures

static unsigned long long statSaves, statCrashTrials, statCorruptionTrials, statFuzzTrials;
static unsigned long long statRecoverySaves, statDoubleCrashTrials, statVerifyFailTrials;
static unsigned long long statRolledBack, statUncommittedKept, statDuplicates, statKnownRiskLosses;
static unsigned long long statMultiPreSaves, statTwoPhaseSaves, statNewGames, statBoxLostReports;
static unsigned long long failures;
static u32 currentSeed;
static unsigned currentSession;

#define CHECK(cond, ...)                                                       \
do {                                                                           \
    if (!(cond))                                                               \
    {                                                                          \
        failures++;                                                            \
        if (failures <= 25)                                                    \
        {                                                                      \
            fprintf(stderr, "FAIL seed=%u session=%u %s:%d: ",                  \
                    currentSeed, currentSession, __FILE__, __LINE__);          \
            fprintf(stderr, __VA_ARGS__);                                      \
            fprintf(stderr, "\n");                                             \
        }                                                                      \
    }                                                                          \
} while (0)

// ---------------------------------------------------------------------------
// Random numbers (xorshift64*)

static unsigned long long rngState;

static u32 Rand(void)
{
    rngState ^= rngState >> 12;
    rngState ^= rngState << 25;
    rngState ^= rngState >> 27;
    return (u32)((rngState * 2685821657736338717ULL) >> 32);
}

static u32 RandN(u32 n)
{
    return n ? Rand() % n : 0;
}

static void RandBytes(u8 *dst, u32 size)
{
    for (u32 i = 0; i < size; i++)
        dst[i] = Rand();
}

// ---------------------------------------------------------------------------
// Fake flash

static u8 flash[SAVE_SECTOR_COUNT][SAVE_SECTOR_SIZE];
static long long opBudget = -1; // Byte programs + erases allowed before power loss
static int powerLost;
static long long opsUsed;
static u32 failVerifyOnce;      // Next program of these sectors fails verification

#define MAX_BOUNDARIES 128
static long long sectorBoundaries[MAX_BOUNDARIES];
static int numBoundaries;
static int recordBoundaries;

static int Consume(void)
{
    if (powerLost)
        return 0;
    if (opBudget >= 0)
    {
        if (opBudget == 0)
        {
            powerLost = 1;
            return 0;
        }
        opBudget--;
    }
    opsUsed++;
    return 1;
}

void SaveIo_ReadSector(u8 sector, u8 *dst)
{
    memcpy(dst, flash[sector], SAVE_SECTOR_SIZE);
}

static bool8 Program(u8 sector, const u8 *src, int skip)
{
    if (powerLost)
        return FALSE;
    if (recordBoundaries && numBoundaries < MAX_BOUNDARIES)
        sectorBoundaries[numBoundaries++] = opsUsed;
    if (!Consume())
    {
        // Interrupted erase: some bits erased, some not.
        for (int i = 0; i < SAVE_SECTOR_SIZE; i++)
            flash[sector][i] |= (u8)Rand();
        return FALSE;
    }
    memset(flash[sector], 0xFF, SAVE_SECTOR_SIZE);
    for (int i = 0; i < SAVE_SECTOR_SIZE; i++)
    {
        if (i == skip)
            continue;
        if (!Consume())
        {
            // Interrupted mid-byte: only some bits programmed.
            flash[sector][i] &= src[i] | (u8)Rand();
            return FALSE;
        }
        flash[sector][i] &= src[i];
    }
    if (failVerifyOnce & (1u << sector))
    {
        failVerifyOnce &= ~(1u << sector);
        flash[sector][RandN(SAVE_SECTOR_SIZE)] ^= 1 << RandN(8);
        return TRUE;
    }
    for (int i = 0; i < SAVE_SECTOR_SIZE; i++)
    {
        if (i != skip && flash[sector][i] != src[i])
            return TRUE;
    }
    return FALSE;
}

bool8 SaveIo_ProgramSector(u8 sector, const u8 *src)
{
    return Program(sector, src, -1);
}

bool8 SaveIo_ProgramSectorSkipByte(u8 sector, const u8 *src, u16 skipOffset)
{
    return Program(sector, src, skipOffset);
}

bool8 SaveIo_ProgramByte(u8 sector, u16 offset, u8 value)
{
    if (powerLost)
        return FALSE;
    if (recordBoundaries && numBoundaries < MAX_BOUNDARIES)
        sectorBoundaries[numBoundaries++] = opsUsed;
    if (!Consume())
        return FALSE;
    flash[sector][offset] &= value;
    return flash[sector][offset] != value;
}

bool8 SaveIo_MonChangeGainsData(const u8 *oldMon, const u8 *newMon)
{
    if (memcmp(oldMon, newMon, 4) != 0)
        return TRUE; // A different Pokémon
    if (newMon[ITEM_BYTE] != 0 && newMon[ITEM_BYTE] != oldMon[ITEM_BYTE])
        return TRUE; // Received an item
    return FALSE;
}

// ---------------------------------------------------------------------------
// Game model

static u32 nextMonId = 1;

static void UseGame(struct Game *game)
{
    layout.part0[0].data = game->sb2;
    layout.part0[0].size = SB2_SIZE;
    layout.part0[1].data = game->header;
    layout.part0[1].size = HEADER_SIZE;
    layout.part0[2].data = game->sb3;
    layout.part0[2].size = SB3_SIZE;
    layout.part0Count = 3;
    layout.progressTail = game->sb1;
    layout.progressTailSize = SB1_SIZE;
    layout.boxData = game->boxes;
    layout.boxMonCount = MON_COUNT;
    SaveEngine_SetLayout(&layout);
}

static u8 *BoxMon(struct Game *game, int index)
{
    return game->boxes + index * MON_SIZE;
}

static u8 *PartyMon(struct Game *game, int index)
{
    return game->sb1 + PARTY_OFFSET + index * MON_SIZE;
}

static int IsEmpty(const u8 *mon)
{
    for (int i = 0; i < MON_SIZE; i++)
    {
        if (mon[i])
            return 0;
    }
    return 1;
}

static u32 MonId(const u8 *mon)
{
    return mon[0] | (mon[1] << 8) | (mon[2] << 16) | ((u32)mon[3] << 24);
}

static void MakeMon(u8 *mon)
{
    u32 id = nextMonId++;
    RandBytes(mon, MON_SIZE);
    mon[0] = id;
    mon[1] = id >> 8;
    mon[2] = id >> 16;
    mon[3] = id >> 24;
    mon[ITEM_BYTE] = (RandN(3) == 0) ? 1 + RandN(NUM_ITEMS - 1) : 0;
}

static int RandomBoxSlot(struct Game *game, int wantEmpty)
{
    int start = RandN(MON_COUNT);
    // Prefer clustering in the first few boxes, like real play, sometimes.
    if (RandN(2))
        start = RandN(IN_BOX * 4);
    for (int k = 0; k < MON_COUNT; k++)
    {
        int i = (start + k) % MON_COUNT;
        if (IsEmpty(BoxMon(game, i)) == wantEmpty)
            return i;
    }
    return -1;
}

static int RandomPartySlot(struct Game *game, int wantEmpty)
{
    int start = RandN(PARTY_SIZE);
    for (int k = 0; k < PARTY_SIZE; k++)
    {
        int i = (start + k) % PARTY_SIZE;
        if (IsEmpty(PartyMon(game, i)) == wantEmpty)
            return i;
    }
    return -1;
}

static void Move(u8 *dst, u8 *src)
{
    memcpy(dst, src, MON_SIZE);
    memset(src, 0, MON_SIZE);
}

static void Swap(u8 *a, u8 *b)
{
    u8 tmp[MON_SIZE];
    memcpy(tmp, a, MON_SIZE);
    memcpy(a, b, MON_SIZE);
    memcpy(b, tmp, MON_SIZE);
}

static void NewGame(struct Game *game)
{
    u32 oldId = game->gameId;
    memset(game, 0, sizeof(*game));
    RandBytes(game->sb2, SB2_SIZE);
    RandBytes(game->header, HEADER_SIZE);
    RandBytes(game->sb1, SB1_SIZE);
    memset(game->sb1 + PARTY_OFFSET, 0, PARTY_SIZE * MON_SIZE);
    memset(game->sb1 + BAG_OFFSET, 0, NUM_ITEMS);
    do
    {
        game->gameId = Rand();
    } while (game->gameId == 0 || game->gameId == oldId);
    MakeMon(PartyMon(game, 0));
    SaveEngine_SetGameId(game->gameId);
    statNewGames++;
}

static void RandomOperation(struct Game *game)
{
    int a, b;
    u8 *mon;

    switch (RandN(15))
    {
    case 0: // Catch
        a = RandomPartySlot(game, 1);
        if (a >= 0)
            MakeMon(PartyMon(game, a));
        else if ((b = RandomBoxSlot(game, 1)) >= 0)
            MakeMon(BoxMon(game, b));
        break;
    case 1: // Deposit
        a = RandomPartySlot(game, 0);
        b = RandomBoxSlot(game, 1);
        if (a >= 0 && b >= 0)
            Move(BoxMon(game, b), PartyMon(game, a));
        break;
    case 2: // Withdraw
        a = RandomBoxSlot(game, 0);
        b = RandomPartySlot(game, 1);
        if (a >= 0 && b >= 0)
            Move(PartyMon(game, b), BoxMon(game, a));
        break;
    case 3: // Move between PC slots
        a = RandomBoxSlot(game, 0);
        b = RandomBoxSlot(game, 1);
        if (a >= 0 && b >= 0)
            Move(BoxMon(game, b), BoxMon(game, a));
        break;
    case 4: // Swap two PC Pokémon, often in different sectors
        a = RandomBoxSlot(game, 0);
        b = RandomBoxSlot(game, 0);
        if (a >= 0 && b >= 0 && a != b)
            Swap(BoxMon(game, a), BoxMon(game, b));
        break;
    case 5: // Release
        a = RandomBoxSlot(game, 0);
        if (a >= 0)
            memset(BoxMon(game, a), 0, MON_SIZE);
        break;
    case 6: // Rename or otherwise modify a PC Pokémon
        a = RandomBoxSlot(game, 0);
        if (a >= 0)
            RandBytes(BoxMon(game, a) + 30, 10);
        break;
    case 7: // Give a held item from the bag
        a = RandomBoxSlot(game, 0);
        b = 1 + RandN(NUM_ITEMS - 1);
        if (a >= 0 && BoxMon(game, a)[ITEM_BYTE] == 0 && game->sb1[BAG_OFFSET + b] > 0)
        {
            game->sb1[BAG_OFFSET + b]--;
            BoxMon(game, a)[ITEM_BYTE] = b;
        }
        break;
    case 8: // Take a held item
        a = RandomBoxSlot(game, 0);
        if (a >= 0 && (mon = BoxMon(game, a))[ITEM_BYTE] != 0 && game->sb1[BAG_OFFSET + mon[ITEM_BYTE]] < 255)
        {
            game->sb1[BAG_OFFSET + mon[ITEM_BYTE]]++;
            mon[ITEM_BYTE] = 0;
        }
        break;
    case 9: // Sort a box
        a = RandN(BOXES);
        for (int i = IN_BOX - 1; i > 0; i--)
            Swap(BoxMon(game, a * IN_BOX + i), BoxMon(game, a * IN_BOX + RandN(i + 1)));
        break;
    case 10: // Walk around: progress data only
        RandBytes(game->sb2 + RandN(SB2_SIZE - 8), 8);
        RandBytes(game->sb1 + 4000 + RandN(SB1_SIZE - 4100), 16);
        RandBytes(game->sb3, SB3_SIZE);
        break;
    case 11: // Move a whole box into another box
        a = RandN(BOXES);
        b = RandN(BOXES);
        for (int i = 0; i < IN_BOX && a != b; i++)
        {
            if (!IsEmpty(BoxMon(game, a * IN_BOX + i)) && IsEmpty(BoxMon(game, b * IN_BOX + i)))
                Move(BoxMon(game, b * IN_BOX + i), BoxMon(game, a * IN_BOX + i));
        }
        break;
    case 12: // Box names and wallpapers
        RandBytes(game->header + RandN(HEADER_SIZE - 9), 9);
        break;
    case 13: // Fill many slots at once (fills the PC up over time)
        for (int n = RandN(80); n > 0; n--)
        {
            if ((a = RandomBoxSlot(game, 1)) >= 0)
                MakeMon(BoxMon(game, a));
        }
        break;
    case 14: // Buy items
        game->sb1[BAG_OFFSET + 1 + RandN(NUM_ITEMS - 1)] += 1 + RandN(5);
        break;
    }
}

// ---------------------------------------------------------------------------
// Comparisons

static int ProgressEqual(const struct Game *a, const struct Game *b)
{
    return memcmp(a->sb2, b->sb2, SB2_SIZE) == 0
        && memcmp(a->header, b->header, HEADER_SIZE) == 0
        && memcmp(a->sb3, b->sb3, SB3_SIZE) == 0
        && memcmp(a->sb1, b->sb1, SB1_SIZE) == 0
        && a->gameId == b->gameId;
}

static int SectorMonCount(int sector)
{
    int count = MON_COUNT - sector * SAVE_BOX_MONS_PER_SECTOR;
    return count > SAVE_BOX_MONS_PER_SECTOR ? SAVE_BOX_MONS_PER_SECTOR : count;
}

static int SectorEqual(const struct Game *a, const struct Game *b, int sector)
{
    int start = sector * SAVE_BOX_MONS_PER_SECTOR * MON_SIZE;
    return memcmp(a->boxes + start, b->boxes + start, SectorMonCount(sector) * MON_SIZE) == 0;
}

// The interim image the engine writes before the commit (see save_engine.h).
static int UnionKeepsOld(const u8 *oldMon, const u8 *newMon)
{
    if (memcmp(oldMon, newMon, MON_SIZE) == 0 || IsEmpty(oldMon))
        return 0;
    if (IsEmpty(newMon))
        return 1;
    return !SaveIo_MonChangeGainsData(oldMon, newMon);
}

static int IsDisplaced(struct Game *oldGame, struct Game *newGame, int slot, int first, int count)
{
    const u8 *oldMon = BoxMon(oldGame, slot);
    const u8 *newMon = BoxMon(newGame, slot);
    if (IsEmpty(oldMon) || IsEmpty(newMon) || memcmp(oldMon, newMon, 8) == 0)
        return 0;
    for (int i = first; i < first + count; i++)
    {
        if (memcmp(oldMon, BoxMon(newGame, i), 8) == 0)
            return 0;
    }
    return 1;
}

// Builds the expected interim image of a sector into out->boxes. Returns the
// number of displaced Pokémon that found no free slot.
static int BuildExpectedUnion(struct Game *out, struct Game *oldGame, struct Game *newGame, int sector)
{
    int first = sector * SAVE_BOX_MONS_PER_SECTOR;
    int count = SectorMonCount(sector);
    int freeSlot = first, overflow = 0;

    memcpy(BoxMon(out, first), BoxMon(oldGame, first), count * MON_SIZE);
    for (int i = first; i < first + count; i++)
    {
        if (UnionKeepsOld(BoxMon(out, i), BoxMon(newGame, i)))
            continue;
        if (IsDisplaced(out, newGame, i, first, count))
        {
            while (freeSlot < first + count && !(IsEmpty(BoxMon(out, freeSlot)) && IsEmpty(BoxMon(newGame, freeSlot))))
                freeSlot++;
            if (freeSlot < first + count)
                memcpy(BoxMon(out, freeSlot), BoxMon(out, i), MON_SIZE);
            else
                overflow++;
        }
        memcpy(BoxMon(out, i), BoxMon(newGame, i), MON_SIZE);
    }
    return overflow;
}

static struct Game *unionScratch;

static int SectorEqualsUnion(struct Game *result, struct Game *oldGame, struct Game *newGame, int sector)
{
    if (oldGame->gameId != newGame->gameId)
        return 0;
    BuildExpectedUnion(unionScratch, oldGame, newGame, sector);
    return SectorEqual(result, unionScratch, sector);
}

static int SectorIsZero(const struct Game *a, int sector)
{
    int start = sector * SAVE_BOX_MONS_PER_SECTOR * MON_SIZE;
    for (int i = 0; i < SectorMonCount(sector) * MON_SIZE; i++)
    {
        if (a->boxes[start + i])
            return 0;
    }
    return 1;
}

static int BoxesEqual(const struct Game *a, const struct Game *b)
{
    return memcmp(a->boxes, b->boxes, sizeof(a->boxes)) == 0;
}

static int GamesEqual(const struct Game *a, const struct Game *b)
{
    return ProgressEqual(a, b) && BoxesEqual(a, b);
}

#define MAX_IDS (MON_COUNT + PARTY_SIZE)

static int CollectIds(struct Game *game, u32 *ids)
{
    int n = 0;
    for (int i = 0; i < PARTY_SIZE; i++)
    {
        if (!IsEmpty(PartyMon(game, i)))
            ids[n++] = MonId(PartyMon(game, i));
    }
    for (int i = 0; i < MON_COUNT; i++)
    {
        if (!IsEmpty(BoxMon(game, i)))
            ids[n++] = MonId(BoxMon(game, i));
    }
    return n;
}

static int CompareU32(const void *a, const void *b)
{
    u32 x = *(const u32 *)a, y = *(const u32 *)b;
    return (x > y) - (x < y);
}

static int Contains(const u32 *sorted, int n, u32 id)
{
    return bsearch(&id, sorted, n, sizeof(u32), CompareU32) != NULL;
}

// ---------------------------------------------------------------------------
// Save helpers

static struct Game *loaded, *scratch, *committed, *previousCommitted, *startOfSave;
static u8 flashSnapshot[SAVE_SECTOR_COUNT][SAVE_SECTOR_SIZE];
static u8 flashCommitted[SAVE_SECTOR_COUNT][SAVE_SECTOR_SIZE];

// Runs a save. Returns the final engine result, or SAVE_ENGINE_BUSY if power
// was lost part way.
static u8 RunSave(int twoPhase, u8 *numPre, u8 *numPost)
{
    u8 result;

    SaveEngine_BeginSave(twoPhase ? SAVE_ENGINE_FLAG_TWO_PHASE : 0);
    if (numPre)
        SaveEngine_GetPlanCounts(numPre, numPost);
    for (;;)
    {
        result = SaveEngine_Step();
        if (powerLost)
            return SAVE_ENGINE_BUSY;
        if (result == SAVE_ENGINE_WAITING_FOR_COMMIT)
        {
            result = SaveEngine_FinishCommit();
            if (powerLost)
                return SAVE_ENGINE_BUSY;
        }
        if (result != SAVE_ENGINE_BUSY)
            return result;
    }
}

// Simulates switching the console off and on: RAM is lost, then the game loads.
static u8 Reboot(struct Game *into)
{
    u8 status;
    opBudget = -1;
    powerLost = 0;
    memset(into, 0xA5, sizeof(*into)); // Stale RAM must never leak into a loaded save
    UseGame(into);
    status = SaveEngine_Load();
    into->gameId = SaveEngine_GetGameId();
    return status;
}

// A Pokémon in both the old and the new save may only go missing when its old
// PC slot was taken by a different Pokémon, its sector had no free slot left
// to keep it in during the save, and more than one sector had to be written
// before the commit.
static int LossAllowed(struct Game *oldGame, struct Game *newGame, u32 id)
{
    for (int i = 0; i < MON_COUNT; i++)
    {
        if (!IsEmpty(BoxMon(oldGame, i)) && MonId(BoxMon(oldGame, i)) == id)
        {
            int sector = i / SAVE_BOX_MONS_PER_SECTOR;
            if (IsEmpty(BoxMon(newGame, i)) || MonId(BoxMon(newGame, i)) == id)
                return 0;
            return BuildExpectedUnion(unionScratch, oldGame, newGame, sector) > 0;
        }
    }
    return 0;
}

static void CheckMonConservation(struct Game *oldGame, struct Game *newGame, struct Game *result, u8 numPre)
{
    static u32 oldIds[MAX_IDS], newIds[MAX_IDS], resultIds[MAX_IDS];
    int nOld = CollectIds(oldGame, oldIds);
    int nNew = CollectIds(newGame, newIds);
    int nResult = CollectIds(result, resultIds);

    qsort(oldIds, nOld, sizeof(u32), CompareU32);
    qsort(newIds, nNew, sizeof(u32), CompareU32);
    qsort(resultIds, nResult, sizeof(u32), CompareU32);

    for (int i = 0; i < nResult; i++)
    {
        CHECK(Contains(oldIds, nOld, resultIds[i]) || Contains(newIds, nNew, resultIds[i]),
              "loaded Pokémon %u that was never saved", resultIds[i]);
        if (i > 0 && resultIds[i] == resultIds[i - 1])
            statDuplicates++;
    }
    for (int i = 0; i < nOld; i++)
    {
        if (!Contains(newIds, nNew, oldIds[i]) || Contains(resultIds, nResult, oldIds[i]))
            continue;
        if (numPre >= 2 && LossAllowed(oldGame, newGame, oldIds[i]))
            statKnownRiskLosses++;
        else
            CHECK(0, "Pokémon %u was lost (sectors written before commit: %u)", oldIds[i], numPre);
    }
}

// oldCounter is the commit counter before the save; the counter after loading
// tells whether the interrupted save reached its commit.
static void CheckInterruptedSave(struct Game *oldGame, struct Game *newGame, int hadSave, u32 oldCounter,
                                 u8 status, struct Game *result, u8 numPre, u8 numPost)
{
    int progressOld, progressNew;

    if (!hadSave)
    {
        CHECK(status == SAVE_ENGINE_LOAD_EMPTY || status == SAVE_ENGINE_LOAD_CORRUPT || status == SAVE_ENGINE_LOAD_OK,
              "first save interrupted: unexpected status %u", status);
        if (status == SAVE_ENGINE_LOAD_OK)
        {
            CHECK(ProgressEqual(result, newGame), "first save: loaded progress is not the new progress");
            CHECK(BoxesEqual(result, newGame), "first save: loaded boxes are not the new boxes");
        }
        return;
    }

    CHECK(status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP,
          "interrupted save: status %u", status);
    if (status != SAVE_ENGINE_LOAD_OK && status != SAVE_ENGINE_LOAD_OK_BACKUP)
        return;

    progressNew = SaveEngine_GetCounter() == oldCounter + 1;
    progressOld = SaveEngine_GetCounter() == oldCounter;
    CHECK(progressOld || progressNew, "loaded counter %u, expected %u or %u", SaveEngine_GetCounter(), oldCounter, oldCounter + 1);
    if (progressOld)
        CHECK(ProgressEqual(result, oldGame), "old commit loaded but progress differs from the old save");
    if (progressNew)
        CHECK(ProgressEqual(result, newGame), "new commit loaded but progress differs from the new save");

    for (int s = 0; s < SAVE_BOX_SECTOR_COUNT; s++)
    {
        int ok = SectorEqual(result, oldGame, s) || SectorEqual(result, newGame, s)
              || SectorEqualsUnion(result, oldGame, newGame, s);
        // After the first save of a new game commits, the old game's sectors
        // read as empty.
        if (!ok && progressNew && oldGame->gameId != newGame->gameId)
            ok = SectorIsZero(result, s);
        CHECK(ok, "box sector %d is neither old nor new (progressOld=%d)", s, progressOld);
    }

    if (progressOld)
    {
        if (numPre <= 1)
            CHECK(BoxesEqual(result, oldGame), "not rolled back: %u sector(s) written before commit", numPre);
        if (numPre == 0)
            CHECK(BoxesEqual(result, oldGame), "boxes changed before the commit although none were written");
        if (!BoxesEqual(result, oldGame))
            statUncommittedKept++;
        else if (!BoxesEqual(oldGame, newGame))
            statRolledBack++;
    }
    if (progressNew && numPost == 0)
        CHECK(BoxesEqual(result, newGame), "committed save with no later writes did not load exactly");
    if (progressNew && oldGame->gameId != newGame->gameId)
    {
        // Nothing from the old game may appear in the new game's PC.
        for (int s = 0; s < SAVE_BOX_SECTOR_COUNT; s++)
            CHECK(SectorEqual(result, newGame, s) || SectorIsZero(result, s),
                  "old game's box sector %d appeared in the new game", s);
    }

    CheckMonConservation(oldGame, newGame, result, numPre);
}

// ---------------------------------------------------------------------------
// Trials

static int hadCommittedSave;
static int hadPreviousCommittedSave;

static void RestoreBeforeSave(void)
{
    memcpy(flash, flashSnapshot, sizeof(flash));
    SaveEngine_HostLoadState(engineStateA);
    ram = *startOfSave;
    UseGame(&ram);
    opBudget = -1;
    powerLost = 0;
    failVerifyOnce = 0;
}

static u32 counterBeforeSave;

static void CrashTrial(long long crashAt, int twoPhase)
{
    u8 numPre = 0, numPost = 0, status, result;

    RestoreBeforeSave();
    opsUsed = 0;
    opBudget = crashAt;
    result = RunSave(twoPhase, &numPre, &numPost);
    if (!powerLost)
        return; // The save finished before the cut

    statCrashTrials++;
    status = Reboot(loaded);
    CheckInterruptedSave(committed, startOfSave, hadCommittedSave, counterBeforeSave, status, loaded, numPre, numPost);

    // Play on from what was loaded: the next save must restore consistency.
    if (RandN(3) == 0 && (status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP))
    {
        u8 status2;
        static u8 flashAfterCrash[SAVE_SECTOR_COUNT][SAVE_SECTOR_SIZE];

        memcpy(flashAfterCrash, flash, sizeof(flash));
        SaveEngine_HostSaveState(engineStateB);

        // Double crash: power lost again during the recovery save.
        if (RandN(2) == 0)
        {
            ram = *loaded;
            UseGame(&ram);
            opsUsed = 0;
            opBudget = RandN(60000);
            RunSave(RandN(2), &numPre, &numPost);
            if (powerLost)
            {
                statDoubleCrashTrials++;
                status2 = Reboot(scratch);
                CHECK(status2 == SAVE_ENGINE_LOAD_OK || status2 == SAVE_ENGINE_LOAD_OK_BACKUP,
                      "double crash: status %u", status2);
                // The recovery save wrote the same data that was loaded, so
                // any outcome must equal it exactly.
                CHECK(GamesEqual(scratch, loaded), "double crash changed the loaded game");
            }
            memcpy(flash, flashAfterCrash, sizeof(flash));
            SaveEngine_HostLoadState(engineStateB);
        }

        ram = *loaded;
        UseGame(&ram);
        opBudget = -1;
        powerLost = 0;
        result = RunSave(RandN(2), NULL, NULL);
        CHECK(result == SAVE_ENGINE_DONE, "recovery save failed: %u", result);
        status2 = Reboot(scratch);
        CHECK(status2 == SAVE_ENGINE_LOAD_OK, "after recovery save: status %u", status2);
        CHECK(GamesEqual(scratch, loaded), "recovery save did not persist the loaded game");
        CHECK(SaveEngine_GetLoadFlags() == 0, "recovery save left load flags 0x%x", SaveEngine_GetLoadFlags());
        statRecoverySaves++;
    }
}

static void VerifyFailureTrial(void)
{
    u8 result, status;
    int attempts = 0;

    RestoreBeforeSave();
    failVerifyOnce = 1u << RandN(SAVE_SECTOR_BOX_BACKUP + 1);
    result = RunSave(RandN(2), NULL, NULL);
    while (result == SAVE_ENGINE_ERROR && attempts++ < 3)
    {
        // What the save-failed screen does: wipe damaged sectors, save again.
        u32 damaged = SaveEngine_GetDamagedSectors();
        static const u8 zeros[SAVE_SECTOR_SIZE];
        CHECK(damaged != 0, "error without damaged sectors");
        for (int s = 0; s < SAVE_SECTOR_COUNT; s++)
        {
            if (damaged & (1u << s))
                SaveIo_ProgramSector(s, zeros);
        }
        SaveEngine_ClearDamagedSectors();
        result = RunSave(RandN(2), NULL, NULL);
    }
    statVerifyFailTrials++;
    CHECK(result == SAVE_ENGINE_DONE, "save did not succeed after a verify failure: %u", result);
    status = Reboot(loaded);
    CHECK(status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP, "after verify failure: status %u", status);
    CHECK(GamesEqual(loaded, startOfSave), "after verify failure: saved game differs");
}

// Damage one sector of a committed save and reload.
static void CorruptionTrial(void)
{
    int sector = RandN(SAVE_SECTOR_COUNT);
    u8 status;
    u8 backupId;
    int backupHasSector;

    memcpy(flash, flashCommitted, sizeof(flash));
    backupId = flash[SAVE_SECTOR_BOX_BACKUP][SAVE_SECTOR_ID_OFFSET];
    backupHasSector = SaveEngine_IsSectorValid(flash[SAVE_SECTOR_BOX_BACKUP], SAVE_SECTOR_KIND_BOX, backupId);

    switch (RandN(4))
    {
    case 0:
        flash[sector][RandN(SAVE_SECTOR_SIZE)] ^= 1 << RandN(8);
        break;
    case 1:
        memset(flash[sector], 0xFF, SAVE_SECTOR_SIZE);
        break;
    case 2:
        RandBytes(flash[sector], SAVE_SECTOR_SIZE);
        break;
    case 3:
        memset(flash[sector], 0, SAVE_SECTOR_SIZE);
        break;
    }
    statCorruptionTrials++;
    status = Reboot(loaded);

    if (sector >= SAVE_SECTOR_HOF_1 || memcmp(flash[sector], flashCommitted[sector], SAVE_SECTOR_SIZE) == 0)
    {
        CHECK(status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP, "undamaged save: status %u", status);
        CHECK(GamesEqual(loaded, committed), "damage outside the save changed it (sector %d)", sector);
        return;
    }

    if (sector == SAVE_SECTOR_BOX_BACKUP)
    {
        CHECK(status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP, "backup damaged: status %u", status);
        CHECK(GamesEqual(loaded, committed), "damaged backup changed the loaded game");
        return;
    }

    if (sector >= SAVE_SECTOR_BOX_FIRST)
    {
        int boxSector = sector - SAVE_SECTOR_BOX_FIRST;
        CHECK(status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP, "box damaged: status %u", status);
        CHECK(ProgressEqual(loaded, committed), "box damage changed progress");
        for (int s = 0; s < SAVE_BOX_SECTOR_COUNT; s++)
        {
            if (s != boxSector)
                CHECK(SectorEqual(loaded, committed, s), "damage to box sector %d changed sector %d", boxSector, s);
        }
        if (backupHasSector && backupId == boxSector)
        {
            // The backup holds this sector's image from before its last
            // write; that image is what must be restored.
            int start = boxSector * SAVE_BOX_MONS_PER_SECTOR * MON_SIZE;
            CHECK(memcmp(loaded->boxes + start, flashCommitted[SAVE_SECTOR_BOX_BACKUP],
                         SectorMonCount(boxSector) * MON_SIZE) == 0,
                  "box sector %d not restored from backup", boxSector);
            CHECK(SaveEngine_GetLoadFlags() & SAVE_LOAD_FLAG_BOX_RESTORED, "restore not reported");
        }
        else
        {
            CHECK(SectorIsZero(loaded, boxSector) || SectorEqual(loaded, committed, boxSector),
                  "unrecoverable box sector %d loaded garbage", boxSector);
            if (SectorIsZero(loaded, boxSector) && !SectorIsZero(committed, boxSector))
                statBoxLostReports++;
            CHECK(SaveEngine_GetLoadFlags() & SAVE_LOAD_FLAG_BOX_LOST, "lost box sector not reported");
        }
        return;
    }

    // Progress sector damaged
    {
        int copyDamaged = sector / SAVE_PROGRESS_PARTS;
        u32 counterA = flashCommitted[SAVE_SECTOR_PROGRESS_A][SAVE_SECTOR_COUNTER_OFFSET2]
                    | (flashCommitted[SAVE_SECTOR_PROGRESS_A][SAVE_SECTOR_COUNTER_OFFSET2 + 1] << 8);
        u32 counterB = flashCommitted[SAVE_SECTOR_PROGRESS_B][SAVE_SECTOR_COUNTER_OFFSET2]
                    | (flashCommitted[SAVE_SECTOR_PROGRESS_B][SAVE_SECTOR_COUNTER_OFFSET2 + 1] << 8);
        int validA = SaveEngine_IsSectorValid(flashCommitted[SAVE_SECTOR_PROGRESS_A], SAVE_SECTOR_KIND_PROGRESS, 0);
        int validB = SaveEngine_IsSectorValid(flashCommitted[SAVE_SECTOR_PROGRESS_B], SAVE_SECTOR_KIND_PROGRESS, 0);
        int newestCopy = (validB && (!validA || counterB > counterA)) ? 1 : 0;

        if (copyDamaged != newestCopy)
        {
            CHECK(status == SAVE_ENGINE_LOAD_OK_BACKUP || status == SAVE_ENGINE_LOAD_OK, "older copy damaged: status %u", status);
            CHECK(GamesEqual(loaded, committed), "damage to the older copy changed the game");
        }
        else if (hadPreviousCommittedSave)
        {
            CHECK(status == SAVE_ENGINE_LOAD_OK_BACKUP, "newest copy damaged: status %u", status);
            CHECK(ProgressEqual(loaded, previousCommitted), "newest copy damaged: older progress not loaded");
            for (int s = 0; s < SAVE_BOX_SECTOR_COUNT; s++)
            {
                int ok = SectorEqual(loaded, previousCommitted, s) || SectorEqual(loaded, committed, s);
                if (!ok && previousCommitted->gameId != committed->gameId)
                    ok = SectorIsZero(loaded, s);
                CHECK(ok, "newest copy damaged: box sector %d is from no saved state", s);
            }
        }
        else
        {
            CHECK(status == SAVE_ENGINE_LOAD_CORRUPT, "only copy damaged: status %u", status);
        }
    }
}

static void FuzzTrial(void)
{
    u8 status;
    switch (RandN(4))
    {
    case 0: // Pure noise
        for (int s = 0; s < SAVE_SECTOR_COUNT; s++)
            RandBytes(flash[s], SAVE_SECTOR_SIZE);
        break;
    case 1: // Committed save with many random bytes changed
        memcpy(flash, flashCommitted, sizeof(flash));
        for (int n = RandN(200); n > 0; n--)
            flash[RandN(SAVE_SECTOR_COUNT)][RandN(SAVE_SECTOR_SIZE)] = Rand();
        break;
    case 2: // Sectors shuffled into the wrong positions
        memcpy(flash, flashCommitted, sizeof(flash));
        for (int n = RandN(10); n > 0; n--)
            memcpy(flash[RandN(SAVE_SECTOR_COUNT)], flashCommitted[RandN(SAVE_SECTOR_COUNT)], SAVE_SECTOR_SIZE);
        break;
    case 3: // Valid-looking footers with random contents
        for (int s = 0; s < SAVE_SECTOR_COUNT; s++)
        {
            RandBytes(flash[s], SAVE_SECTOR_SIZE);
            flash[s][SAVE_SECTOR_KIND_OFFSET] = 1 + RandN(2);
            flash[s][SAVE_SECTOR_ID_OFFSET] = RandN(24);
            flash[s][SAVE_SECTOR_VERSION_OFFSET] = SAVE_FORMAT_VERSION;
            flash[s][SAVE_SECTOR_VERSION_OFFSET + 1] = 0;
            flash[s][SAVE_SECTOR_SIGNATURE_OFFSET2] = (u8)SAVE_SIGNATURE_V2;
            flash[s][SAVE_SECTOR_SIGNATURE_OFFSET2 + 1] = (u8)(SAVE_SIGNATURE_V2 >> 8);
            flash[s][SAVE_SECTOR_SIGNATURE_OFFSET2 + 2] = (u8)(SAVE_SIGNATURE_V2 >> 16);
            flash[s][SAVE_SECTOR_SIGNATURE_OFFSET2 + 3] = (u8)(SAVE_SIGNATURE_V2 >> 24);
            u32 crc = SaveEngine_SectorCrc(flash[s]);
            if (RandN(2))
            {
                flash[s][SAVE_SECTOR_FOOTER_OFFSET] = crc;
                flash[s][SAVE_SECTOR_FOOTER_OFFSET + 1] = crc >> 8;
                flash[s][SAVE_SECTOR_FOOTER_OFFSET + 2] = crc >> 16;
                flash[s][SAVE_SECTOR_FOOTER_OFFSET + 3] = crc >> 24;
            }
        }
        break;
    }
    statFuzzTrials++;
    status = Reboot(loaded);
    CHECK(status <= SAVE_ENGINE_LOAD_OUTDATED, "fuzz: invalid status %u", status);
    // Whatever was loaded, saving and reloading must reproduce it exactly.
    if (status == SAVE_ENGINE_LOAD_OK || status == SAVE_ENGINE_LOAD_OK_BACKUP)
    {
        u8 result;
        ram = *loaded;
        UseGame(&ram);
        result = RunSave(RandN(2), NULL, NULL);
        CHECK(result == SAVE_ENGINE_DONE, "fuzz: save after load failed");
        status = Reboot(scratch);
        CHECK(status == SAVE_ENGINE_LOAD_OK, "fuzz: reload status %u", status);
        CHECK(GamesEqual(scratch, loaded), "fuzz: save after load did not round-trip");
    }
}

static void LegacyTrial(void)
{
    u8 status;
    // A 2.0.x save: vanilla footers with the legacy signature.
    memset(flash, 0xFF, sizeof(flash));
    for (int s = 0; s < 28; s++)
    {
        RandBytes(flash[s], SAVE_SECTOR_SIZE);
        flash[s][4088] = 0x25;
        flash[s][4089] = 0x20;
        flash[s][4090] = 0x01;
        flash[s][4091] = 0x08;
    }
    status = Reboot(loaded);
    CHECK(status == SAVE_ENGINE_LOAD_OUTDATED, "legacy save: status %u", status);
    memset(flash, 0xFF, sizeof(flash));
    status = Reboot(loaded);
    CHECK(status == SAVE_ENGINE_LOAD_EMPTY, "erased flash: status %u", status);
    memset(flash, 0x00, sizeof(flash));
    status = Reboot(loaded);
    CHECK(status == SAVE_ENGINE_LOAD_EMPTY, "zeroed flash: status %u", status);
}

static void RunSession(void)
{
    int numOps = RandN(4) == 0 ? RandN(40) : RandN(6);
    u8 numPre, numPost, result, status;
    int twoPhase = RandN(4) == 0;
    long long totalOps;

    if (RandN(400) == 0 && hadCommittedSave)
        NewGame(&ram);
    for (int i = 0; i < numOps; i++)
        RandomOperation(&ram);

    // Occasionally continue from a fresh load, as after turning the game on.
    if (hadCommittedSave && RandN(5) == 0)
    {
        status = Reboot(scratch);
        CHECK(status == SAVE_ENGINE_LOAD_OK, "reload between sessions: status %u", status);
        CHECK(GamesEqual(scratch, committed), "reload between sessions differs");
        UseGame(&ram);
        SaveEngine_SetGameId(ram.gameId);
    }

    *startOfSave = ram;
    memcpy(flashSnapshot, flash, sizeof(flash));
    SaveEngine_HostSaveState(engineStateA);
    counterBeforeSave = SaveEngine_GetCounter();

    // Dry run to find the sector boundaries
    opsUsed = 0;
    numBoundaries = 0;
    recordBoundaries = 1;
    result = RunSave(twoPhase, &numPre, &numPost);
    recordBoundaries = 0;
    totalOps = opsUsed;
    CHECK(result == SAVE_ENGINE_DONE, "save failed: %u", result);
    statSaves++;
    if (numPre >= 2)
        statMultiPreSaves++;
    if (twoPhase)
        statTwoPhaseSaves++;

    // Interrupt the same save at every sector boundary and at random bytes
    for (int b = 0; b < numBoundaries; b++)
    {
        long long at = sectorBoundaries[b];
        CrashTrial(at, twoPhase);
        CrashTrial(at + 1, twoPhase);
        CrashTrial(at + 1 + RandN(SAVE_SECTOR_SIZE), twoPhase);
        CrashTrial(at + SAVE_SECTOR_FOOTER_OFFSET - RandN(8), twoPhase);
        CrashTrial(at + SAVE_SECTOR_SIZE - RandN(4), twoPhase);
    }
    for (int n = 0; n < 4; n++)
        CrashTrial(RandN(totalOps + 1), twoPhase);
    if (RandN(8) == 0)
        VerifyFailureTrial();

    // Commit the session for real
    RestoreBeforeSave();
    result = RunSave(twoPhase, NULL, NULL);
    CHECK(result == SAVE_ENGINE_DONE, "final save failed: %u", result);
    status = Reboot(loaded);
    CHECK(status == SAVE_ENGINE_LOAD_OK, "after save: status %u", status);
    CHECK(GamesEqual(loaded, startOfSave), "saved game did not load exactly");

    // Continue with the engine state left by the save itself (not by the load)
    memcpy(flash, flashSnapshot, sizeof(flash));
    SaveEngine_HostLoadState(engineStateA);
    ram = *startOfSave;
    UseGame(&ram);
    RunSave(twoPhase, NULL, NULL);

    if (hadCommittedSave)
    {
        *previousCommitted = *committed;
        hadPreviousCommittedSave = 1;
    }
    *committed = ram;
    hadCommittedSave = 1;
    memcpy(flashCommitted, flash, sizeof(flash));

    if (RandN(6) == 0)
    {
        static u8 keepFlash[SAVE_SECTOR_COUNT][SAVE_SECTOR_SIZE];
        memcpy(keepFlash, flash, sizeof(flash));
        SaveEngine_HostSaveState(engineStateB);
        CorruptionTrial();
        if (RandN(4) == 0)
            FuzzTrial();
        memcpy(flash, keepFlash, sizeof(flash));
        SaveEngine_HostLoadState(engineStateB);
        UseGame(&ram);
    }
}

int main(int argc, char **argv)
{
    unsigned sessions;

    currentSeed = argc > 1 ? strtoul(argv[1], NULL, 0) : 1;
    sessions = argc > 2 ? strtoul(argv[2], NULL, 0) : 200;
    rngState = 0x9E3779B97F4A7C15ULL ^ ((unsigned long long)currentSeed << 17) ^ currentSeed;
    if (rngState == 0)
        rngState = 1;

    loaded = calloc(1, sizeof(struct Game));
    scratch = calloc(1, sizeof(struct Game));
    committed = calloc(1, sizeof(struct Game));
    previousCommitted = calloc(1, sizeof(struct Game));
    startOfSave = calloc(1, sizeof(struct Game));
    unionScratch = calloc(1, sizeof(struct Game));
    engineStateA = calloc(1, SaveEngine_HostStateSize());
    engineStateB = calloc(1, SaveEngine_HostStateSize());

    memset(flash, 0xFF, sizeof(flash));
    LegacyTrial();
    memset(flash, 0xFF, sizeof(flash));

    SaveEngine_ResetState();
    memset(&ram, 0, sizeof(ram));
    NewGame(&ram);
    UseGame(&ram);

    for (currentSession = 0; currentSession < sessions; currentSession++)
        RunSession();

    printf("seed %u: sessions=%u saves=%llu crashes=%llu doubleCrashes=%llu recoverySaves=%llu "
           "verifyFailures=%llu corruptions=%llu fuzz=%llu rolledBack=%llu uncommittedKept=%llu "
           "duplicates=%llu knownRiskLosses=%llu multiPreSaves=%llu twoPhase=%llu newGames=%llu "
           "boxLost=%llu failures=%llu\n",
           currentSeed, sessions, statSaves, statCrashTrials, statDoubleCrashTrials, statRecoverySaves,
           statVerifyFailTrials, statCorruptionTrials, statFuzzTrials, statRolledBack, statUncommittedKept,
           statDuplicates, statKnownRiskLosses, statMultiPreSaves, statTwoPhaseSaves, statNewGames,
           statBoxLostReports, failures);
    return failures ? 1 : 0;
}
