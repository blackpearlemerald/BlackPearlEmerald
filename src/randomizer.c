// BPE's built-in randomizer. See BPEDocumentation/RANDOMIZER_PLAN.md.
//
// Nothing here keeps state in RAM. Every result is worked out from the seed and
// the thing being randomized, so the same seed always gives the same game, and
// saving or reloading never changes anything. One-for-one swaps use a keyed
// Feistel network with cycle-walking, which is a true permutation of the chosen
// set and can also be run backwards.
#include "global.h"
#include "battle.h"
#include "battle_util.h"
#include "data.h"
#include "event_data.h"
#include "item.h"
#include "move.h"
#include "pokedex.h"
#include "pokemon.h"
#include "random.h"
#include "randomizer.h"
#include "ui_birch_case.h"
#include "wild_encounter.h"
#include "constants/abilities.h"
#include "constants/battle.h"
#include "constants/battle_move_effects.h"
#include "constants/form_change_types.h"
#include "constants/characters.h"
#include "constants/event_objects.h"
#include "constants/map_groups.h"
#include "constants/hold_effects.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/species.h"
#include "constants/trade.h"
#include "constants/trainers.h"

struct RandomizerTradeRequest
{
    u16 map;
    u8 area;
};

struct RandomizerFieldItem
{
    u16 flag;
    u16 item;
    u8 amount;
    u8 tier;
};

#include "data/randomizer/generated.h"

// Hash streams. Each option hashes in its own stream so switching one option on
// never changes another option's results. These values are part of the
// algorithm: never renumber them.
enum RandomizerStream
{
    STREAM_SPECIES_SWAP = 1,
    STREAM_SPECIES_MAP = 2,
    STREAM_WILD_ROUTE = 3,
    STREAM_GIFT = 4,
    STREAM_STATIC = 5,
    STREAM_TRADE = 6,
    STREAM_STARTER = 7,
    STREAM_TRAINER = 8,
    STREAM_ABILITY = 9,
    STREAM_LEVEL_UP = 10,
    STREAM_TM_COMPATIBILITY = 11,
    STREAM_TM_CONTENTS = 12,
    STREAM_FIELD_ITEMS = 13,
    STREAM_TYPES = 14,
    STREAM_EVOLUTIONS = 15,
    STREAM_BASE_STATS = 16,
    STREAM_TYPE_CHART = 17,
    STREAM_TRAINER_EVOLUTION = 18,
    STREAM_STORY = 19,
};

// ── Settings ──────────────────────────────────────────────────────────────────

struct OptionLayout
{
    u8 shift;
    u8 bits;
};

// The 36 option bits, in the order they are stored and encoded in seed codes.
static const struct OptionLayout sOptionLayout[RANDOMIZER_OPTION_COUNT] =
{
    [RANDOMIZER_OPTION_STARTERS]         = { 0, 2},
    [RANDOMIZER_OPTION_WILD]             = { 2, 1},
    [RANDOMIZER_OPTION_WILD_CONSISTENCY] = { 3, 1},
    [RANDOMIZER_OPTION_GIFTS]            = { 4, 1},
    [RANDOMIZER_OPTION_STATICS]          = { 5, 1},
    [RANDOMIZER_OPTION_LEGENDARIES]      = { 6, 2},
    [RANDOMIZER_OPTION_STRENGTH]         = { 8, 1},
    [RANDOMIZER_OPTION_GENERATIONS]      = { 9, 9},
    [RANDOMIZER_OPTION_REGULAR_TRAINERS] = {18, 1},
    [RANDOMIZER_OPTION_BOSS_TRAINERS]    = {19, 2},
    [RANDOMIZER_OPTION_ABILITIES]        = {21, 1},
    [RANDOMIZER_OPTION_TROLL_ABILITIES]  = {22, 1},
    [RANDOMIZER_OPTION_LEVEL_UP_MOVES]   = {23, 1},
    [RANDOMIZER_OPTION_TM_COMPATIBILITY] = {24, 1},
    [RANDOMIZER_OPTION_TM_CONTENTS]      = {25, 1},
    [RANDOMIZER_OPTION_FIELD_ITEMS]      = {26, 1},
    [RANDOMIZER_OPTION_TYPES]            = {27, 1},
    [RANDOMIZER_OPTION_EVOLUTIONS]       = {28, 1},
    [RANDOMIZER_OPTION_BASE_STATS]       = {29, 1},
    [RANDOMIZER_OPTION_TYPE_CHART]       = {30, 1},
    [RANDOMIZER_OPTION_MONOTYPE]         = {31, 5},
};

#define OPTION_BITS_TOTAL 36
#define VERSION_SHIFT 4          // in VAR_RANDOMIZER_OPTIONS_2
#define HM_FALLBACK_SHIFT 8      // in VAR_RANDOMIZER_OPTIONS_2

static const u16 sOptionMax[RANDOMIZER_OPTION_COUNT] =
{
    [RANDOMIZER_OPTION_STARTERS]         = RANDOMIZER_STARTERS_LEGENDARY,
    [RANDOMIZER_OPTION_WILD]             = 1,
    [RANDOMIZER_OPTION_WILD_CONSISTENCY] = RANDOMIZER_CONSISTENCY_PER_ROUTE,
    [RANDOMIZER_OPTION_GIFTS]            = 1,
    [RANDOMIZER_OPTION_STATICS]          = 1,
    [RANDOMIZER_OPTION_LEGENDARIES]      = RANDOMIZER_LEGENDARIES_MIXED,
    [RANDOMIZER_OPTION_STRENGTH]         = RANDOMIZER_STRENGTH_FULLY_RANDOM,
    [RANDOMIZER_OPTION_GENERATIONS]      = (1 << RANDOMIZER_GENERATION_COUNT) - 1,
    [RANDOMIZER_OPTION_REGULAR_TRAINERS] = 1,
    [RANDOMIZER_OPTION_BOSS_TRAINERS]    = RANDOMIZER_BOSSES_FULLY_RANDOM,
    [RANDOMIZER_OPTION_ABILITIES]        = 1,
    [RANDOMIZER_OPTION_TROLL_ABILITIES]  = 1,
    [RANDOMIZER_OPTION_LEVEL_UP_MOVES]   = 1,
    [RANDOMIZER_OPTION_TM_COMPATIBILITY] = 1,
    [RANDOMIZER_OPTION_TM_CONTENTS]      = 1,
    [RANDOMIZER_OPTION_FIELD_ITEMS]      = 1,
    [RANDOMIZER_OPTION_TYPES]            = 1,
    [RANDOMIZER_OPTION_EVOLUTIONS]       = 1,
    [RANDOMIZER_OPTION_BASE_STATS]       = 1,
    [RANDOMIZER_OPTION_TYPE_CHART]       = 1,
    [RANDOMIZER_OPTION_MONOTYPE]         = TYPE_FAIRY,
};

static const u16 sPresets[RANDOMIZER_PRESET_CUSTOM][RANDOMIZER_OPTION_COUNT] =
{
    [RANDOMIZER_PRESET_RANDOMLOCKE] =
    {
        [RANDOMIZER_OPTION_STARTERS]         = RANDOMIZER_STARTERS_SAME_ROLES,
        [RANDOMIZER_OPTION_WILD]             = TRUE,
        [RANDOMIZER_OPTION_WILD_CONSISTENCY] = RANDOMIZER_CONSISTENCY_WHOLE_GAME,
        [RANDOMIZER_OPTION_GIFTS]            = TRUE,
        [RANDOMIZER_OPTION_STATICS]          = TRUE,
        [RANDOMIZER_OPTION_LEGENDARIES]      = RANDOMIZER_LEGENDARIES_AMONG_THEMSELVES,
        [RANDOMIZER_OPTION_STRENGTH]         = RANDOMIZER_STRENGTH_SIMILAR,
        [RANDOMIZER_OPTION_REGULAR_TRAINERS] = TRUE,
        [RANDOMIZER_OPTION_BOSS_TRAINERS]    = RANDOMIZER_BOSSES_UNCHANGED,
    },
    [RANDOMIZER_PRESET_FULL] =
    {
        [RANDOMIZER_OPTION_STARTERS]         = RANDOMIZER_STARTERS_SAME_ROLES,
        [RANDOMIZER_OPTION_WILD]             = TRUE,
        [RANDOMIZER_OPTION_WILD_CONSISTENCY] = RANDOMIZER_CONSISTENCY_WHOLE_GAME,
        [RANDOMIZER_OPTION_GIFTS]            = TRUE,
        [RANDOMIZER_OPTION_STATICS]          = TRUE,
        [RANDOMIZER_OPTION_LEGENDARIES]      = RANDOMIZER_LEGENDARIES_AMONG_THEMSELVES,
        [RANDOMIZER_OPTION_STRENGTH]         = RANDOMIZER_STRENGTH_SIMILAR,
        [RANDOMIZER_OPTION_REGULAR_TRAINERS] = TRUE,
        [RANDOMIZER_OPTION_BOSS_TRAINERS]    = RANDOMIZER_BOSSES_KEEP_TYPE,
        [RANDOMIZER_OPTION_ABILITIES]        = TRUE,
        [RANDOMIZER_OPTION_LEVEL_UP_MOVES]   = TRUE,
        [RANDOMIZER_OPTION_TM_COMPATIBILITY] = TRUE,
        [RANDOMIZER_OPTION_TM_CONTENTS]      = TRUE,
        [RANDOMIZER_OPTION_FIELD_ITEMS]      = TRUE,
    },
    [RANDOMIZER_PRESET_CHAOS] =
    {
        [RANDOMIZER_OPTION_STARTERS]         = RANDOMIZER_STARTERS_RANDOM,
        [RANDOMIZER_OPTION_WILD]             = TRUE,
        [RANDOMIZER_OPTION_WILD_CONSISTENCY] = RANDOMIZER_CONSISTENCY_PER_ROUTE,
        [RANDOMIZER_OPTION_GIFTS]            = TRUE,
        [RANDOMIZER_OPTION_STATICS]          = TRUE,
        [RANDOMIZER_OPTION_LEGENDARIES]      = RANDOMIZER_LEGENDARIES_MIXED,
        [RANDOMIZER_OPTION_STRENGTH]         = RANDOMIZER_STRENGTH_FULLY_RANDOM,
        [RANDOMIZER_OPTION_REGULAR_TRAINERS] = TRUE,
        [RANDOMIZER_OPTION_BOSS_TRAINERS]    = RANDOMIZER_BOSSES_FULLY_RANDOM,
        [RANDOMIZER_OPTION_ABILITIES]        = TRUE,
        [RANDOMIZER_OPTION_TROLL_ABILITIES]  = TRUE,
        [RANDOMIZER_OPTION_LEVEL_UP_MOVES]   = TRUE,
        [RANDOMIZER_OPTION_TM_COMPATIBILITY] = TRUE,
        [RANDOMIZER_OPTION_TM_CONTENTS]      = TRUE,
        [RANDOMIZER_OPTION_FIELD_ITEMS]      = TRUE,
        [RANDOMIZER_OPTION_TYPES]            = TRUE,
        [RANDOMIZER_OPTION_EVOLUTIONS]       = TRUE,
        [RANDOMIZER_OPTION_BASE_STATS]       = TRUE,
        [RANDOMIZER_OPTION_TYPE_CHART]       = TRUE,
    },
};

// Species lookups check the options constantly, so the variables are read directly.
#define RANDOMIZER_VAR(var) (gSaveBlock1Ptr->vars[(var) - VARS_START])

static u64 GetOptionBits(void)
{
    return RANDOMIZER_VAR(VAR_RANDOMIZER_OPTIONS_0)
         | ((u64)RANDOMIZER_VAR(VAR_RANDOMIZER_OPTIONS_1) << 16)
         | ((u64)(RANDOMIZER_VAR(VAR_RANDOMIZER_OPTIONS_2) & 0xF) << 32);
}

static u32 GetSeed(void)
{
    return RANDOMIZER_VAR(VAR_RANDOMIZER_SEED_LO) | ((u32)RANDOMIZER_VAR(VAR_RANDOMIZER_SEED_HI) << 16);
}

bool32 Randomizer_IsActive(void)
{
    return GetOptionBits() != 0;
}

u32 Randomizer_GetOption(enum RandomizerOption option)
{
    return (GetOptionBits() >> sOptionLayout[option].shift) & ((1u << sOptionLayout[option].bits) - 1);
}

u32 Randomizer_GetOptionMax(enum RandomizerOption option)
{
    return sOptionMax[option];
}

u32 Randomizer_GetSavedVersion(void)
{
    return (VarGet(VAR_RANDOMIZER_OPTIONS_2) >> VERSION_SHIFT) & 0xF;
}

static u64 PackOptions(const struct RandomizerSettings *settings)
{
    u64 bits = 0;
    for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
        bits |= (u64)(settings->options[i] & ((1u << sOptionLayout[i].bits) - 1)) << sOptionLayout[i].shift;
    return bits;
}

static void UnpackOptions(u64 bits, struct RandomizerSettings *settings)
{
    for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
        settings->options[i] = (bits >> sOptionLayout[i].shift) & ((1u << sOptionLayout[i].bits) - 1);
}

void Randomizer_ApplyPreset(struct RandomizerSettings *settings, enum RandomizerPreset preset)
{
    if (preset >= RANDOMIZER_PRESET_CUSTOM)
        preset = RANDOMIZER_PRESET_RANDOMLOCKE;
    for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
        settings->options[i] = sPresets[preset][i];
}

enum RandomizerPreset Randomizer_GetPreset(const struct RandomizerSettings *settings)
{
    for (u32 preset = 0; preset < RANDOMIZER_PRESET_CUSTOM; preset++)
    {
        u32 i;
        for (i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
        {
            if (settings->options[i] != sPresets[preset][i])
                break;
        }
        if (i == RANDOMIZER_OPTION_COUNT)
            return preset;
    }
    return RANDOMIZER_PRESET_CUSTOM;
}

void Randomizer_LoadSettings(struct RandomizerSettings *settings)
{
    settings->seed = GetSeed();
    UnpackOptions(GetOptionBits(), settings);
}

static u32 ComputeHMFallbacks(void);

void Randomizer_SaveSettings(const struct RandomizerSettings *settings)
{
    u64 bits = PackOptions(settings);

    if (bits == 0)
    {
        Randomizer_ClearSettings();
        return;
    }
    VarSet(VAR_RANDOMIZER_SEED_LO, settings->seed & 0xFFFF);
    VarSet(VAR_RANDOMIZER_SEED_HI, settings->seed >> 16);
    VarSet(VAR_RANDOMIZER_OPTIONS_0, bits & 0xFFFF);
    VarSet(VAR_RANDOMIZER_OPTIONS_1, (bits >> 16) & 0xFFFF);
    VarSet(VAR_RANDOMIZER_OPTIONS_2, ((bits >> 32) & 0xF) | (RANDOMIZER_ALGORITHM_VERSION << VERSION_SHIFT));
    // The HM check reads the settings back from the variables, so it runs last.
    VarSet(VAR_RANDOMIZER_OPTIONS_2, VarGet(VAR_RANDOMIZER_OPTIONS_2) | (ComputeHMFallbacks() << HM_FALLBACK_SHIFT));
}

void Randomizer_ClearSettings(void)
{
    VarSet(VAR_RANDOMIZER_SEED_LO, 0);
    VarSet(VAR_RANDOMIZER_SEED_HI, 0);
    VarSet(VAR_RANDOMIZER_OPTIONS_0, 0);
    VarSet(VAR_RANDOMIZER_OPTIONS_1, 0);
    VarSet(VAR_RANDOMIZER_OPTIONS_2, 0);
}

u32 Randomizer_NewSeed(void)
{
    return Random32() ^ (gMain.vblankCounter1 * 0x9E3779B9);
}

// ── Seed codes ───────────────────────────────────────────────────────────────

// 32 characters with no look-alikes: no 0/O or 1/I.
static const u8 sCodeAlphabet[] =
{
    CHAR_A, CHAR_B, CHAR_C, CHAR_D, CHAR_E, CHAR_F, CHAR_G, CHAR_H,
    CHAR_J, CHAR_K, CHAR_L, CHAR_M, CHAR_N, CHAR_P, CHAR_Q, CHAR_R,
    CHAR_S, CHAR_T, CHAR_U, CHAR_V, CHAR_W, CHAR_X, CHAR_Y, CHAR_Z,
    CHAR_2, CHAR_3, CHAR_4, CHAR_5, CHAR_6, CHAR_7, CHAR_8, CHAR_9,
};

STATIC_ASSERT(ARRAY_COUNT(sCodeAlphabet) == 32, RandomizerCodeAlphabetSize);

#define CODE_BYTES 10 // 16 characters x 5 bits

static u32 Mix32(u32 x);

u8 Randomizer_GetCodeChar(u32 index)
{
    return sCodeAlphabet[index % ARRAY_COUNT(sCodeAlphabet)];
}

u32 Randomizer_GetCodeAlphabetSize(void)
{
    return ARRAY_COUNT(sCodeAlphabet);
}

static u32 CodeChecksum(u32 seed, u64 options, u32 version)
{
    return Mix32(seed ^ Mix32((u32)options ^ Mix32((u32)(options >> 32) + (version << 8)))) & 0xFF;
}

static void WriteBits(u8 *buffer, u32 *position, u64 value, u32 count)
{
    for (u32 i = 0; i < count; i++, (*position)++)
    {
        if ((value >> i) & 1)
            buffer[*position / 8] |= 1 << (*position % 8);
    }
}

static u64 ReadBits(const u8 *buffer, u32 *position, u32 count)
{
    u64 value = 0;
    for (u32 i = 0; i < count; i++, (*position)++)
        value |= (u64)((buffer[*position / 8] >> (*position % 8)) & 1) << i;
    return value;
}

// Layout: 36 option bits, 4 version bits, 32 seed bits, 8 checksum bits.
void Randomizer_EncodeSeedCode(const struct RandomizerSettings *settings, u8 *dest)
{
    u8 buffer[CODE_BYTES] = {0};
    u32 position = 0;
    u64 options = PackOptions(settings);

    WriteBits(buffer, &position, options, OPTION_BITS_TOTAL);
    WriteBits(buffer, &position, RANDOMIZER_ALGORITHM_VERSION, 4);
    WriteBits(buffer, &position, settings->seed, 32);
    WriteBits(buffer, &position, CodeChecksum(settings->seed, options, RANDOMIZER_ALGORITHM_VERSION), 8);
    position = 0;
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
        dest[i] = sCodeAlphabet[ReadBits(buffer, &position, 5)];
    dest[RANDOMIZER_CODE_LENGTH] = EOS;
}

enum RandomizerCodeResult Randomizer_DecodeSeedCode(const u8 *code, struct RandomizerSettings *settings)
{
    u8 buffer[CODE_BYTES] = {0};
    u32 position = 0;
    u64 options;
    u32 version, seed, checksum;

    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        u32 value;
        for (value = 0; value < ARRAY_COUNT(sCodeAlphabet); value++)
        {
            if (sCodeAlphabet[value] == code[i])
                break;
        }
        if (value == ARRAY_COUNT(sCodeAlphabet))
            return RANDOMIZER_CODE_INVALID;
        WriteBits(buffer, &position, value, 5);
    }
    position = 0;
    options = ReadBits(buffer, &position, OPTION_BITS_TOTAL);
    version = ReadBits(buffer, &position, 4);
    seed = ReadBits(buffer, &position, 32);
    checksum = ReadBits(buffer, &position, 8);
    if (checksum != CodeChecksum(seed, options, version))
        return RANDOMIZER_CODE_INVALID;
    if (version != RANDOMIZER_ALGORITHM_VERSION)
        return RANDOMIZER_CODE_OTHER_VERSION;
    settings->seed = seed;
    UnpackOptions(options, settings);
    for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
    {
        if (settings->options[i] > sOptionMax[i])
            return RANDOMIZER_CODE_INVALID;
    }
    return RANDOMIZER_CODE_OK;
}

// The current game's code, grouped as XXXX-XXXX-XXXX-XXXX.
void Randomizer_BufferSeedCode(u8 *dest)
{
    struct RandomizerSettings settings;
    u8 code[RANDOMIZER_CODE_LENGTH + 1];
    u32 out = 0;

    Randomizer_LoadSettings(&settings);
    Randomizer_EncodeSeedCode(&settings, code);
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        if (i != 0 && i % 4 == 0)
            dest[out++] = CHAR_HYPHEN;
        dest[out++] = code[i];
    }
    dest[out] = EOS;
}

// ── Hashing and permutations ─────────────────────────────────────────────────

static u32 Mix32(u32 x)
{
    x ^= x >> 16;
    x *= 0x7FEB352D;
    x ^= x >> 15;
    x *= 0x846CA68B;
    x ^= x >> 16;
    return x;
}

static u32 HashWithSeed(u32 seed, u32 stream, u32 a, u32 b)
{
    u32 h = Mix32(seed ^ Mix32(stream * 0x9E3779B9 + 0x7F4A7C15));
    h = Mix32(h ^ (a * 0xC2B2AE35 + 0x165667B1));
    return Mix32(h ^ (b * 0x85EBCA6B + 0x27D4EB2F));
}

static u32 Hash(u32 stream, u32 a, u32 b)
{
    return HashWithSeed(GetSeed(), stream, a, b);
}

static u32 FeistelRound(u32 key, u32 round, u32 half, u32 mask)
{
    return Mix32(key ^ (round * 0x9E3779B9) ^ (half * 0x632BE5AB)) & mask;
}

static u32 PermuteForward(u32 value, u32 key, u32 halfBits)
{
    u32 mask = (1u << halfBits) - 1;
    u32 left = value >> halfBits;
    u32 right = value & mask;

    for (u32 round = 0; round < 4; round++)
    {
        u32 next = left ^ FeistelRound(key, round, right, mask);
        left = right;
        right = next;
    }
    return (left << halfBits) | right;
}

static u32 PermuteBackward(u32 value, u32 key, u32 halfBits)
{
    u32 mask = (1u << halfBits) - 1;
    u32 left = value >> halfBits;
    u32 right = value & mask;

    for (u32 round = 4; round-- > 0;)
    {
        u32 previous = right ^ FeistelRound(key, round, left, mask);
        right = left;
        left = previous;
    }
    return (left << halfBits) | right;
}

typedef bool32 (*SetPredicate)(u32 value, const void *context);

// Cycle-walking: step the permutation until the value lands back in the set.
// Restricted to a set, a permutation of the whole range is still a permutation.
static u32 WalkPermutation(u32 value, u32 key, u32 halfBits, bool32 forward, SetPredicate inSet, const void *context)
{
    u32 start = value;
    u32 limit = 1u << (2 * halfBits);

    for (u32 steps = 0; steps < limit; steps++)
    {
        value = forward ? PermuteForward(value, key, halfBits) : PermuteBackward(value, key, halfBits);
        if (inSet(value, context))
            return value;
    }
    return start;
}

static u32 HalfBitsFor(u32 count)
{
    u32 bits = 1;
    while ((1u << (2 * bits)) < count)
        bits++;
    return bits;
}

// ── Species pool ─────────────────────────────────────────────────────────────

#define SPECIES_HALF_BITS 6 // the species permutation covers 4096 IDs

static u32 GetSpeciesLimit(void)
{
    // Every version so far uses the version 1 species list.
    return min(NUM_SPECIES, RANDOMIZER_V1_SPECIES_LIMIT);
}

// Alternate forms that are real, distinct Pokémon rather than cosmetic variants.
static bool32 IsAllowedAlternateForm(enum Species species)
{
    switch (species)
    {
    case SPECIES_ROTOM_HEAT:
    case SPECIES_ROTOM_WASH:
    case SPECIES_ROTOM_FROST:
    case SPECIES_ROTOM_FAN:
    case SPECIES_ROTOM_MOW:
    case SPECIES_WORMADAM_SANDY:
    case SPECIES_WORMADAM_TRASH:
    case SPECIES_ORICORIO_POM_POM:
    case SPECIES_ORICORIO_PAU:
    case SPECIES_ORICORIO_SENSU:
    case SPECIES_LYCANROC_MIDNIGHT:
    case SPECIES_LYCANROC_DUSK:
    case SPECIES_BASCULIN_WHITE_STRIPED:
    case SPECIES_URSALUNA_BLOODMOON:
        return TRUE;
    default:
        return FALSE;
    }
}

// Regional forms that only exist during a battle.
static bool32 IsBattleOnlyRegionalForm(enum Species species)
{
    switch (species)
    {
    case SPECIES_DARMANITAN_GALAR_ZEN:
        return TRUE;
    default:
        return FALSE;
    }
}

bool32 Randomizer_IsSpeciesInPool(enum Species species)
{
    const struct SpeciesInfo *info;

    if (species == SPECIES_NONE || species >= GetSpeciesLimit() || !IsSpeciesEnabled(species))
        return FALSE;
    info = &gSpeciesInfo[species];
    if (info->isMegaEvolution || info->isPrimalReversion || info->isUltraBurst
     || info->isGigantamax || info->isTeraForm || info->isTotem)
        return FALSE;
    if (info->frontPic == NULL || info->iconSprite == NULL || info->levelUpLearnset == NULL)
        return FALSE;
    if (info->isAlolanForm || info->isGalarianForm || info->isHisuianForm || info->isPaldeanForm)
        return !IsBattleOnlyRegionalForm(species);
    if (info->formSpeciesIdTable != NULL && info->formSpeciesIdTable[0] != species)
        return IsAllowedAlternateForm(species);
    return TRUE;
}

bool32 Randomizer_IsLegendary(enum Species species)
{
    const struct SpeciesInfo *info = &gSpeciesInfo[species];
    return info->isRestrictedLegendary || info->isSubLegendary || info->isMythical || info->isUltraBeast;
}

u32 Randomizer_GetSpeciesGeneration(enum Species species)
{
    static const u16 sLastDexNumOfGeneration[RANDOMIZER_GENERATION_COUNT] = {151, 251, 386, 493, 649, 721, 809, 905, 1025};
    const struct SpeciesInfo *info = &gSpeciesInfo[species];

    if (info->isAlolanForm)
        return 7;
    if (info->isGalarianForm || info->isHisuianForm)
        return 8;
    if (info->isPaldeanForm)
        return 9;
    for (u32 i = 0; i < RANDOMIZER_GENERATION_COUNT; i++)
    {
        if (info->natDexNum <= sLastDexNumOfGeneration[i])
            return i + 1;
    }
    return RANDOMIZER_GENERATION_COUNT;
}

static u32 GetOriginalBST(enum Species species)
{
    const struct SpeciesInfo *info = &gSpeciesInfo[species];
    return info->baseHP + info->baseAttack + info->baseDefense + info->baseSpeed + info->baseSpAttack + info->baseSpDefense;
}

static enum Type GetOriginalType(enum Species species, u32 slot)
{
    return gSpeciesInfo[species].types[slot];
}

static bool32 CanOriginallyLearnTeachable(enum Species species, enum Move move)
{
    const u16 *learnset = gSpeciesInfo[species].teachableLearnset;
    if (learnset == NULL)
        return FALSE;
    for (u32 i = 0; learnset[i] != MOVE_UNAVAILABLE; i++)
    {
        if (learnset[i] == move)
            return TRUE;
    }
    return FALSE;
}

static const struct Evolution *GetOriginalEvolutions(enum Species species)
{
    return gSpeciesInfo[species].evolutions;
}

enum Species Randomizer_GetFamilyRoot(enum Species species)
{
    if (species >= NUM_SPECIES || sRandomizerFamilyRoot[species] == SPECIES_NONE)
        return species;
    return sRandomizerFamilyRoot[species];
}

u32 Randomizer_GetEvolutionStage(enum Species species)
{
    enum Species root = Randomizer_GetFamilyRoot(species);
    const struct Evolution *evolutions;

    if (root == species)
        return 0;
    evolutions = GetOriginalEvolutions(root);
    for (u32 i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
    {
        if (evolutions[i].targetSpecies == species)
            return 1;
    }
    return 2;
}

static u32 CountStages(enum Species species, u32 depth)
{
    const struct Evolution *evolutions = GetOriginalEvolutions(species);
    u32 longest = 0;

    if (depth >= 3 || evolutions == NULL)
        return 1;
    for (u32 i = 0; evolutions[i].method != EVOLUTIONS_END; i++)
    {
        enum Species target = evolutions[i].targetSpecies;
        if (target != species && target < NUM_SPECIES)
            longest = max(longest, CountStages(target, depth + 1));
    }
    return 1 + longest;
}

u32 Randomizer_GetFamilyLength(enum Species species)
{
    return CountStages(Randomizer_GetFamilyRoot(species), 1);
}

static u32 GetHighestFinalBST(enum Species species, u32 depth)
{
    const struct Evolution *evolutions = GetOriginalEvolutions(species);
    u32 best = 0;

    if (depth < 3 && evolutions != NULL)
    {
        for (u32 i = 0; evolutions[i].method != EVOLUTIONS_END; i++)
        {
            enum Species target = evolutions[i].targetSpecies;
            if (target != species && target < NUM_SPECIES && Randomizer_IsSpeciesInPool(target))
                best = max(best, GetHighestFinalBST(target, depth + 1));
        }
    }
    return best != 0 ? best : GetOriginalBST(species);
}

// Walks from the family root to the member at the wanted stage, picking a branch
// with the hash where a family splits.
static enum Species GetFamilyMemberAtStage(enum Species root, u32 stage, u32 hash)
{
    enum Species species = root;

    for (u32 i = 0; i < stage; i++)
    {
        const struct Evolution *evolutions = GetOriginalEvolutions(species);
        enum Species options[8];
        u32 count = 0;

        for (u32 j = 0; evolutions != NULL && evolutions[j].method != EVOLUTIONS_END && count < ARRAY_COUNT(options); j++)
        {
            enum Species target = evolutions[j].targetSpecies;
            u32 k;
            if (target == species || target >= NUM_SPECIES || !Randomizer_IsSpeciesInPool(target))
                continue;
            for (k = 0; k < count; k++)
            {
                if (options[k] == target)
                    break;
            }
            if (k == count)
                options[count++] = target;
        }
        if (count == 0)
            break;
        species = options[Mix32(hash + i) % count];
    }
    return species;
}

// ── Picking species ──────────────────────────────────────────────────────────

enum LegendaryPool
{
    POOL_REGULAR,
    POOL_LEGENDARY,
    POOL_ANY,
};

struct SpeciesFilter
{
    enum Species original;
    u16 targetBst;           // the strength to match; 0 means any strength
    u8 legendaryPool;
    u8 requiredType;         // TYPE_NONE for any
    u8 requiredType2;        // a second type that also satisfies requiredType
    u8 requiredStages;       // exact family length, 0 for any
    u8 minStages;            // shortest allowed family, 0 for any
    u8 megaStage;            // with requireMega: the family stage that must Mega Evolve
    bool8 requireBasic:1;
    bool8 requireSurf:1;
    bool8 useFinalBst:1;     // compare the strongest final evolution's strength
    bool8 requireEarlyAttack:1;
    bool8 useGenerations:1;  // apply the Generations option
    bool8 useMonotype:1;     // apply the Monotype option
    bool8 requireMega:1;
    u32 branchHash;          // which branch a split family takes, with requireMega
    u16 avoidFamily;         // a family to leave out, such as the original's; 0 for none
    const u16 *excludedFamilies;
    u8 excludedCount;
    u32 excludedTypes;       // bit per main type that is already taken
};

static bool32 HasEarlyAttack(enum Species species);
static enum Species GetFamilyMemberAtStage(enum Species root, u32 stage, u32 hash);
static enum Item GetMegaStone(enum Species species);

static u32 GetGenerationMask(void)
{
    return Randomizer_GetOption(RANDOMIZER_OPTION_GENERATIONS);
}

static bool32 PassesGenerations(enum Species species)
{
    return !(GetGenerationMask() & (1u << (Randomizer_GetSpeciesGeneration(species) - 1)));
}

static bool32 PassesMonotype(enum Species species)
{
    u32 monotype = Randomizer_GetOption(RANDOMIZER_OPTION_MONOTYPE);

    return monotype == TYPE_NONE
        || Randomizer_GetSpeciesType(species, 0, GetOriginalType(species, 0)) == monotype
        || Randomizer_GetSpeciesType(species, 1, GetOriginalType(species, 1)) == monotype;
}

static bool32 PassesFilters(enum Species species)
{
    return PassesGenerations(species) && PassesMonotype(species);
}

static bool32 FiltersActive(void)
{
    return GetGenerationMask() != 0 || Randomizer_GetOption(RANDOMIZER_OPTION_MONOTYPE) != TYPE_NONE;
}

static bool32 SpeciesMatchesFilter(enum Species species, const struct SpeciesFilter *filter, u32 windowPercent, bool32 relaxed)
{
    bool32 legendary;
    u32 bst;

    if (!Randomizer_IsSpeciesInPool(species))
        return FALSE;
    legendary = Randomizer_IsLegendary(species);
    if ((filter->legendaryPool == POOL_REGULAR && legendary) || (filter->legendaryPool == POOL_LEGENDARY && !legendary))
        return FALSE;
    if (filter->requireBasic && Randomizer_GetFamilyRoot(species) != species)
        return FALSE;
    if (filter->minStages != 0 && !relaxed && Randomizer_GetFamilyLength(species) < filter->minStages)
        return FALSE;
    for (u32 i = 0; i < filter->excludedCount; i++)
    {
        if (Randomizer_GetFamilyRoot(species) == filter->excludedFamilies[i])
            return FALSE;
    }
    if (filter->avoidFamily != SPECIES_NONE && !relaxed && Randomizer_GetFamilyRoot(species) == filter->avoidFamily)
        return FALSE;
    if (filter->targetBst != 0 && windowPercent < 100)
    {
        u32 window = filter->targetBst * windowPercent / 100;
        bst = filter->useFinalBst ? GetHighestFinalBST(species, 0) : GetOriginalBST(species);
        if (bst + window < filter->targetBst || bst > filter->targetBst + window)
            return FALSE;
    }
    if (!relaxed)
    {
        enum Type mainType = Randomizer_GetSpeciesType(species, 0, GetOriginalType(species, 0));
        enum Type otherType = Randomizer_GetSpeciesType(species, 1, GetOriginalType(species, 1));
        if (filter->requiredType != TYPE_NONE
         && mainType != filter->requiredType && otherType != filter->requiredType
         && (filter->requiredType2 == TYPE_NONE || (mainType != filter->requiredType2 && otherType != filter->requiredType2)))
            return FALSE;
        if (filter->excludedTypes & (1u << mainType))
            return FALSE;
        if (filter->requiredStages != 0 && Randomizer_GetFamilyLength(species) != filter->requiredStages)
            return FALSE;
    }
    if (filter->useGenerations && !PassesGenerations(species))
        return FALSE;
    if (filter->useMonotype && !PassesMonotype(species))
        return FALSE;
    if (filter->requireMega && !relaxed
     && GetMegaStone(GetFamilyMemberAtStage(species, filter->megaStage, filter->branchHash)) == ITEM_NONE)
        return FALSE;
    if (filter->requireSurf && !CanOriginallyLearnTeachable(species, MOVE_SURF))
        return FALSE;
    if (filter->requireEarlyAttack && !HasEarlyAttack(species))
        return FALSE;
    return TRUE;
}

// Picks a species that passes the filter. Tries random candidates first, then
// counts every candidate so a narrow filter still gets a fair pick. When nothing
// fits, the strength range widens, then the type and role rules are dropped.
static enum Species PickSpecies(const struct SpeciesFilter *filter, u32 stream, u32 keyA, u32 keyB)
{
    static const u8 sWindows[] = {10, 20, 30, 50, 100};
    u32 limit = GetSpeciesLimit();

    for (u32 relaxed = 0; relaxed < 2; relaxed++)
    {
        for (u32 w = (filter->targetBst != 0 ? 0 : ARRAY_COUNT(sWindows) - 1); w < ARRAY_COUNT(sWindows); w++)
        {
            u32 count = 0;
            u32 salt = relaxed * 0x10 + w;

            for (u32 attempt = 0; attempt < 96; attempt++)
            {
                enum Species species = 1 + Hash(stream, keyA, keyB ^ Mix32((salt << 8) | attempt)) % (limit - 1);
                if (SpeciesMatchesFilter(species, filter, sWindows[w], relaxed))
                    return species;
            }
            for (enum Species species = 1; species < limit; species++)
            {
                if (SpeciesMatchesFilter(species, filter, sWindows[w], relaxed))
                    count++;
            }
            if (count != 0)
            {
                u32 index = Hash(stream, keyA ^ 0x5A5A5A5A, keyB ^ salt) % count;
                for (enum Species species = 1; species < limit; species++)
                {
                    if (SpeciesMatchesFilter(species, filter, sWindows[w], relaxed) && index-- == 0)
                        return species;
                }
            }
        }
    }
    return filter->original;
}

static u32 GetLegendaryRule(void)
{
    return Randomizer_GetOption(RANDOMIZER_OPTION_LEGENDARIES);
}

static bool32 IsSimilarStrength(void)
{
    return Randomizer_GetOption(RANDOMIZER_OPTION_STRENGTH) == RANDOMIZER_STRENGTH_SIMILAR;
}

static u8 GetLegendaryPoolFor(enum Species original)
{
    if (GetLegendaryRule() == RANDOMIZER_LEGENDARIES_MIXED)
        return POOL_ANY;
    return Randomizer_IsLegendary(original) ? POOL_LEGENDARY : POOL_REGULAR;
}

static void InitFilter(struct SpeciesFilter *filter, enum Species original)
{
    memset(filter, 0, sizeof(*filter));
    filter->original = original;
    filter->legendaryPool = GetLegendaryPoolFor(original);
    filter->targetBst = IsSimilarStrength() ? GetOriginalBST(original) : 0;
    filter->useGenerations = TRUE;
    filter->useMonotype = TRUE;
}

// ── The whole-game swap ──────────────────────────────────────────────────────

static const u16 sStrengthBands[] = {210, 252, 302, 363, 435, 522, 627, 0xFFFF};

static u32 GetStrengthBand(enum Species species)
{
    u32 bst = GetOriginalBST(species);
    u32 band = 0;
    while (bst >= sStrengthBands[band])
        band++;
    return band;
}

struct SwapClass
{
    bool8 legendary;
    bool8 anyGroup;
    bool8 canSurf;
    u8 band;
    bool8 anyBand;
};

static bool32 IsSourceRandomized(enum Species species)
{
    u32 sources = sRandomizerSpeciesSources[species];

    if (sources == 0)
        return FALSE;
    if (Randomizer_IsLegendary(species))
        return GetLegendaryRule() != RANDOMIZER_LEGENDARIES_UNCHANGED;
    return ((sources & RANDOMIZER_SOURCE_WILD) && Randomizer_GetOption(RANDOMIZER_OPTION_WILD))
        || ((sources & RANDOMIZER_SOURCE_GIFT) && Randomizer_GetOption(RANDOMIZER_OPTION_GIFTS))
        || ((sources & RANDOMIZER_SOURCE_STATIC) && Randomizer_GetOption(RANDOMIZER_OPTION_STATICS));
}

static bool32 IsInSwapClass(u32 value, const void *context)
{
    const struct SwapClass *swapClass = context;
    enum Species species = value;

    if (species == SPECIES_NONE || species >= GetSpeciesLimit() || sRandomizerSpeciesSources[species] == 0)
        return FALSE;
    if (!IsSourceRandomized(species) || !Randomizer_IsSpeciesInPool(species))
        return FALSE;
    if (!swapClass->anyGroup && Randomizer_IsLegendary(species) != swapClass->legendary)
        return FALSE;
    if (!swapClass->anyBand && GetStrengthBand(species) != swapClass->band)
        return FALSE;
    return CanOriginallyLearnTeachable(species, MOVE_SURF) == swapClass->canSurf;
}

static void GetSwapClass(enum Species species, struct SwapClass *swapClass)
{
    swapClass->legendary = Randomizer_IsLegendary(species);
    swapClass->anyGroup = (GetLegendaryRule() == RANDOMIZER_LEGENDARIES_MIXED);
    swapClass->canSurf = CanOriginallyLearnTeachable(species, MOVE_SURF);
    swapClass->band = GetStrengthBand(species);
    swapClass->anyBand = !IsSimilarStrength();
}

// Swaps species one for one across the whole game: every species in the swap
// becomes exactly one other, and is the replacement for exactly one. The classes
// keep legendaries with legendaries, similar strengths together, and Pokémon that
// can learn Surf with each other, so everything the normal game offers (including
// something to Surf with) is still offered somewhere.
static enum Species SwapSpecies(enum Species species, bool32 forward)
{
    struct SwapClass swapClass;

    GetSwapClass(species, &swapClass);
    if (!IsInSwapClass(species, &swapClass))
        return species;
    return WalkPermutation(species, Hash(STREAM_SPECIES_SWAP, 0, 0), SPECIES_HALF_BITS, forward, IsInSwapClass, &swapClass);
}

// With Generations or Monotype set there are fewer candidates than originals, so
// each original maps to one fixed replacement instead of a one-for-one swap.
static enum Species MapSpeciesWholeGame(enum Species species, bool32 needsSurf)
{
    struct SpeciesFilter filter;

    if (!FiltersActive() && !needsSurf)
        return SwapSpecies(species, TRUE);
    InitFilter(&filter, species);
    filter.requireSurf = needsSurf;
    return PickSpecies(&filter, STREAM_SPECIES_MAP, species, needsSurf);
}

static bool32 IsWaterArea(u32 area)
{
    return area == WILD_AREA_WATER || area == WILD_AREA_FISHING;
}

static bool32 IsLegendaryKept(enum Species species)
{
    return Randomizer_IsLegendary(species) && GetLegendaryRule() == RANDOMIZER_LEGENDARIES_UNCHANGED;
}

static u16 GetCurrentMapId(void)
{
    return (gSaveBlock1Ptr->location.mapGroup << 8) | gSaveBlock1Ptr->location.mapNum;
}

enum Species Randomizer_GetWildSpecies(enum Species species, u16 mapId, u32 area)
{
    struct SpeciesFilter filter;

    if (species == SPECIES_NONE || species >= NUM_SPECIES || !Randomizer_GetOption(RANDOMIZER_OPTION_WILD) || IsLegendaryKept(species))
        return species;
    if (Randomizer_GetOption(RANDOMIZER_OPTION_WILD_CONSISTENCY) == RANDOMIZER_CONSISTENCY_WHOLE_GAME)
        return MapSpeciesWholeGame(species, IsWaterArea(area) && FiltersActive());
    InitFilter(&filter, species);
    filter.requireSurf = IsWaterArea(area);
    return PickSpecies(&filter, STREAM_WILD_ROUTE, mapId | (area << 16), species);
}

enum Species Randomizer_GetCurrentMapWildSpecies(enum Species species, u32 area)
{
    return Randomizer_GetWildSpecies(species, GetCurrentMapId(), area);
}

// For screens that search the wild tables for a species. When every wild slot
// goes through the one-for-one swap, returns the original species that became this
// one (or the species itself when it isn't swapped). Returns SPECIES_NONE when the
// slots have to be randomized one by one instead.
enum Species Randomizer_GetWildSwapOriginal(enum Species species)
{
    if (!Randomizer_GetOption(RANDOMIZER_OPTION_WILD) || IsLegendaryKept(species))
        return species;
    if (Randomizer_GetOption(RANDOMIZER_OPTION_WILD_CONSISTENCY) != RANDOMIZER_CONSISTENCY_WHOLE_GAME || FiltersActive())
        return SPECIES_NONE;
    return SwapSpecies(species, FALSE);
}


static enum Species RandomizeHandedOutSpecies(enum Species species, bool32 optionOn, u32 stream, u32 key)
{
    struct SpeciesFilter filter;

    if (species == SPECIES_NONE || species >= NUM_SPECIES || IsLegendaryKept(species))
        return species;
    if (!Randomizer_IsLegendary(species) && !optionOn)
        return species;
    if (Randomizer_GetOption(RANDOMIZER_OPTION_WILD_CONSISTENCY) == RANDOMIZER_CONSISTENCY_WHOLE_GAME)
        return MapSpeciesWholeGame(species, FALSE);
    InitFilter(&filter, species);
    return PickSpecies(&filter, stream, key, species);
}

enum Species Randomizer_GetGiftSpecies(enum Species species)
{
    return RandomizeHandedOutSpecies(species, Randomizer_GetOption(RANDOMIZER_OPTION_GIFTS), STREAM_GIFT, GetCurrentMapId());
}

enum Species Randomizer_GetStaticSpeciesOnMap(enum Species species, u16 mapId)
{
    return RandomizeHandedOutSpecies(species, Randomizer_GetOption(RANDOMIZER_OPTION_STATICS), STREAM_STATIC, mapId);
}

enum Species Randomizer_GetStaticSpecies(enum Species species)
{
    return Randomizer_GetStaticSpeciesOnMap(species, GetCurrentMapId());
}

enum Species Randomizer_GetTradeSpecies(u32 trade, enum Species species)
{
    return RandomizeHandedOutSpecies(species, Randomizer_GetOption(RANDOMIZER_OPTION_GIFTS), STREAM_TRADE, trade);
}

// A trader asks for whatever replaced their requested Pokémon in the wild, so the
// trade stays possible.
enum Species Randomizer_GetTradeRequestedSpecies(u32 trade, enum Species species)
{
    if (!Randomizer_GetOption(RANDOMIZER_OPTION_WILD))
        return species;
    // Use the area where the requested Pokémon is first found, so a water-only
    // Pokémon maps the way its water slots do.
    if (trade < ARRAY_COUNT(sRandomizerTradeRequests) && sRandomizerTradeRequests[trade].map != 0)
        return Randomizer_GetWildSpecies(species, sRandomizerTradeRequests[trade].map, sRandomizerTradeRequests[trade].area);
    if (Randomizer_GetOption(RANDOMIZER_OPTION_WILD_CONSISTENCY) == RANDOMIZER_CONSISTENCY_WHOLE_GAME)
        return Randomizer_GetWildSpecies(species, 0, WILD_AREA_LAND);
    return species;
}

// ── Static encounters ────────────────────────────────────────────────────────

struct StaticEncounter
{
    u16 map;
    u16 species;
    u16 graphicsId; // the object showing this Pokémon, or 0 when it is disguised
    bool8 story;    // a scripted story battle rather than a static encounter
};

// Every static encounter, so its cry and (where the object shows the Pokémon) its
// overworld sprite match what the battle becomes. Statues and item-ball disguises
// keep their look. Rayquaza is left out: its map also holds the story cutscene.
static const struct StaticEncounter sStaticEncounters[] =
{
    {MAP_ABANDONED_SHIP_DECK, SPECIES_SPIRITOMB, 0},
    {MAP_ANCIENT_TOMB, SPECIES_REGISTEEL, OBJ_EVENT_GFX_REGISTEEL},
    {MAP_AQUA_HIDEOUT_B1F, SPECIES_ELECTRODE, 0},
    {MAP_AQUA_HIDEOUT_B1F, SPECIES_ELECTRODE_HISUIAN, 0},
    {MAP_BATTLE_FRONTIER_OUTSIDE_EAST, SPECIES_SUDOWOODO, OBJ_EVENT_GFX_SUDOWOODO},
    {MAP_DESERT_RUINS, SPECIES_REGIROCK, OBJ_EVENT_GFX_REGIROCK},
    {MAP_FALLARBOR_TOWN_MOVE_RELEARNERS_HOUSE, SPECIES_ROTOM, 0},
    {MAP_FORTREE_CITY, SPECIES_KECLEON, OBJ_EVENT_GFX_KECLEON},
    {MAP_ISLAND_CAVE, SPECIES_REGICE, OBJ_EVENT_GFX_REGICE},
    {MAP_JAGGED_PASS, SPECIES_ENTEI, 0},
    {MAP_LILYCOVE_CITY, SPECIES_RAIKOU, 0},
    {MAP_MARINE_CAVE_END, SPECIES_KYOGRE, OBJ_EVENT_GFX_KYOGRE_FRONT},
    {MAP_METEOR_FALLS_B1F_2R, SPECIES_JIRACHI, 0},
    {MAP_MT_CHIMNEY, SPECIES_MOLTRES, 0},
    {MAP_NEW_MAUVILLE_INSIDE, SPECIES_VOLTORB, 0},
    {MAP_NEW_MAUVILLE_INSIDE, SPECIES_VOLTORB_HISUIAN, 0},
    {MAP_NEW_MAUVILLE_INSIDE, SPECIES_ZAPDOS, 0},
    {MAP_PETALBURG_CITY, SPECIES_SNORLAX, OBJ_EVENT_GFX_BIG_SNORLAX_DOLL},
    {MAP_PETALBURG_WOODS, SPECIES_CELEBI, 0},
    {MAP_ROUTE110_TRICK_HOUSE_END, SPECIES_SNORLAX, 0},
    {MAP_ROUTE119, SPECIES_KECLEON, OBJ_EVENT_GFX_KECLEON},
    {MAP_ROUTE120, SPECIES_KECLEON, OBJ_EVENT_GFX_KECLEON},
    {MAP_ROUTE134, SPECIES_SUICUNE, 0},
    {MAP_SHOAL_CAVE_LOW_TIDE_ICE_ROOM, SPECIES_ARTICUNO, 0},
    {MAP_SOOTOPOLIS_CITY_HOUSE7, SPECIES_TYPE_NULL, 0},
    {MAP_SOUTHERN_ISLAND_INTERIOR, SPECIES_LATIAS, OBJ_EVENT_GFX_LATIAS},
    {MAP_SOUTHERN_ISLAND_INTERIOR, SPECIES_LATIOS, OBJ_EVENT_GFX_LATIOS},
    {MAP_TERRA_CAVE_END, SPECIES_GROUDON, OBJ_EVENT_GFX_GROUDON_FRONT},
    // The Zigzagoon chasing Birch on Route 101.
    {MAP_ROUTE101, SPECIES_ZIGZAGOON, OBJ_EVENT_GFX_ZIGZAGOON_1, TRUE},
};

static enum Species GetEncounterSpecies(const struct StaticEncounter *encounter)
{
    if (encounter->story)
        return Randomizer_GetStoryWildSpecies(encounter->species, encounter->map);
    return Randomizer_GetStaticSpeciesOnMap(encounter->species, encounter->map);
}

// The overworld object for a static encounter shows the Pokémon it has become.
u16 Randomizer_GetStaticObjectGraphics(u16 mapId, u16 graphicsId)
{
    if (!Randomizer_IsActive())
        return graphicsId;
    for (u32 i = 0; i < ARRAY_COUNT(sStaticEncounters); i++)
    {
        if (sStaticEncounters[i].map == mapId && sStaticEncounters[i].graphicsId == graphicsId && graphicsId != 0)
        {
            enum Species species = GetEncounterSpecies(&sStaticEncounters[i]);
            if (species != sStaticEncounters[i].species)
                return species + OBJ_EVENT_MON;
        }
    }
    return graphicsId;
}

// Static encounter scripts play the Pokémon's cry before the battle.
enum Species Randomizer_GetStaticCrySpecies(enum Species species)
{
    u16 mapId = GetCurrentMapId();

    if (!Randomizer_IsActive())
        return species;
    for (u32 i = 0; i < ARRAY_COUNT(sStaticEncounters); i++)
    {
        if (sStaticEncounters[i].map == mapId && sStaticEncounters[i].species == species)
            return GetEncounterSpecies(&sStaticEncounters[i]);
    }
    return species;
}

// A randomized egg hatches into the first stage of its new family.
enum Species Randomizer_GetEggSpecies(enum Species species)
{
    enum Species randomized = Randomizer_GetGiftSpecies(species);
    return randomized == species ? species : Randomizer_GetFamilyRoot(randomized);
}

// Scripts: VAR_RESULT holds a gift species and becomes the Pokémon given instead.
void RandomizeGiftSpecies(void)
{
    gSpecialVar_Result = Randomizer_GetGiftSpecies(gSpecialVar_Result);
}

void RandomizeEggSpecies(void)
{
    gSpecialVar_Result = Randomizer_GetEggSpecies(gSpecialVar_Result);
}

// Story battles that must stay easy (the Route 101 Zigzagoon and Wally's catch)
// always use Similar strength, whatever the Strength option says.
enum Species Randomizer_GetStoryWildSpecies(enum Species species, u16 mapId)
{
    struct SpeciesFilter filter;

    if (!Randomizer_GetOption(RANDOMIZER_OPTION_WILD))
        return species;
    InitFilter(&filter, species);
    filter.legendaryPool = POOL_REGULAR;
    filter.targetBst = GetOriginalBST(species);
    return PickSpecies(&filter, STREAM_STORY, mapId, species);
}

// ── Starters ─────────────────────────────────────────────────────────────────

#define BIRCH_CASE_BALLS 9
#define STARTER_BALLS (BIRCH_CASE_BALLS + 3)

static const u16 sJohtoStarters[STARTER_BALLS - BIRCH_CASE_BALLS] = {SPECIES_CHIKORITA, SPECIES_CYNDAQUIL, SPECIES_TOTODILE};

static enum Species GetOriginalStarter(u32 ball)
{
    if (ball < BIRCH_CASE_BALLS)
        return BirchCase_GetOriginalSpecies(ball);
    return sJohtoStarters[ball - BIRCH_CASE_BALLS];
}

static bool32 HasEarlyAttack(enum Species species)
{
    const struct LevelUpMove *learnset = gSpeciesInfo[species].levelUpLearnset;

    for (u32 i = 0; learnset != NULL && learnset[i].move != LEVEL_UP_MOVE_END && learnset[i].level <= 5; i++)
    {
        enum Move move = Randomizer_GetLevelUpMove(species, i, learnset[i].move);
        if (GetMoveCategory(move) != DAMAGE_CATEGORY_STATUS && GetMovePower(move) > 1)
            return TRUE;
    }
    return FALSE;
}

static enum Species PickStarter(u32 ball, const u16 *taken, u32 takenCount, u32 takenTypes)
{
    struct SpeciesFilter filter;
    enum Species original = GetOriginalStarter(ball);
    u32 mode = Randomizer_GetOption(RANDOMIZER_OPTION_STARTERS);
    u32 monotype = Randomizer_GetOption(RANDOMIZER_OPTION_MONOTYPE);

    InitFilter(&filter, original);
    if (mode == RANDOMIZER_STARTERS_LEGENDARY)
        filter.legendaryPool = POOL_LEGENDARY;
    else
        filter.legendaryPool = (GetLegendaryRule() == RANDOMIZER_LEGENDARIES_MIXED) ? POOL_ANY : POOL_REGULAR;
    filter.requireBasic = TRUE;
    // A Birch Case starter that cannot attack yet is given Tackle, so those balls
    // hold any Pokemon. The Johto gift has no such fallback and still needs one
    // that can fight at level 5.
    filter.requireEarlyAttack = (ball >= BIRCH_CASE_BALLS);
    filter.useFinalBst = TRUE;
    filter.targetBst = IsSimilarStrength() ? GetHighestFinalBST(original, 0) : 0;
    filter.excludedFamilies = taken;
    filter.excludedCount = takenCount;
    filter.avoidFamily = Randomizer_GetFamilyRoot(original);
    if (monotype != TYPE_NONE)
    {
        filter.requiredType = monotype;
    }
    else if (mode == RANDOMIZER_STARTERS_SAME_ROLES)
    {
        filter.requiredType = GetOriginalType(original, 0);
        filter.requiredStages = Randomizer_GetFamilyLength(original);
    }
    else if (ball < BIRCH_CASE_BALLS)
    {
        filter.excludedTypes = takenTypes;
    }
    return PickSpecies(&filter, STREAM_STARTER, ball, 0);
}

// Fills the first count balls: the nine Birch Case balls, then the Johto balls.
// Each ball excludes the families of the balls before it, so they all differ.
void Randomizer_FillStarters(u16 *species, u32 count)
{
    u16 taken[STARTER_BALLS];
    u32 takenTypes = 0;
    bool32 randomized = Randomizer_GetOption(RANDOMIZER_OPTION_STARTERS) != RANDOMIZER_STARTERS_OFF;

    for (u32 i = 0; i < count && i < STARTER_BALLS; i++)
    {
        species[i] = randomized ? PickStarter(i, taken, i, takenTypes) : GetOriginalStarter(i);
        taken[i] = Randomizer_GetFamilyRoot(species[i]);
        takenTypes |= 1u << Randomizer_GetSpeciesType(species[i], 0, GetOriginalType(species[i], 0));
    }
}

enum Species Randomizer_GetStarterSpecies(u32 ball, enum Species original)
{
    u16 species[STARTER_BALLS];

    if (ball >= STARTER_BALLS || Randomizer_GetOption(RANDOMIZER_OPTION_STARTERS) == RANDOMIZER_STARTERS_OFF)
        return original;
    Randomizer_FillStarters(species, ball + 1);
    return species[ball];
}

// Splash, Teleport and Transform cannot win the first battle, so a Birch Case
// starter with nothing else at level 5 is handed Tackle. This is why the ball
// pool takes every Pokémon rather than only the ones that already attack.
void Randomizer_EnsureStarterCanAttack(struct Pokemon *mon)
{
    u32 slot = 0;

    for (u32 i = 0; i < MAX_MON_MOVES; i++)
    {
        enum Move move = GetMonData(mon, MON_DATA_MOVE1 + i);

        if (move == MOVE_NONE)
            break;
        if (GetMoveCategory(move) != DAMAGE_CATEGORY_STATUS && GetMovePower(move) > 1)
            return;
        slot = i + 1;
    }
    if (slot >= MAX_MON_MOVES)
        slot = MAX_MON_MOVES - 1; // A full set of status moves loses its last one.
    SetMonMoveSlot(mon, MOVE_TACKLE, slot);
}

// Scripts: VAR_0x8004 is the Johto ball in Birch's lab (0 Chikorita, 1 Cyndaquil,
// 2 Totodile); VAR_RESULT becomes the Pokémon it holds in this game.
void GetRandomizedJohtoStarter(void)
{
    u32 ball = BIRCH_CASE_BALLS + min(gSpecialVar_0x8004, (u16)(STARTER_BALLS - BIRCH_CASE_BALLS - 1));
    gSpecialVar_Result = Randomizer_GetStarterSpecies(ball, GetOriginalStarter(ball));
}

// ── Pokédex goals ────────────────────────────────────────────────────────────

// The whole-game swap keeps every species the normal game offers, so the full
// Hoenn Dex stays possible. Per-route rolls, Generations, Monotype and random
// evolutions can leave species out.
bool32 Randomizer_IsFullHoennDexPossible(void)
{
    bool32 speciesRandomized;

    if (!Randomizer_IsActive())
        return TRUE;
    if (Randomizer_GetOption(RANDOMIZER_OPTION_EVOLUTIONS) || FiltersActive())
        return FALSE;
    speciesRandomized = Randomizer_GetOption(RANDOMIZER_OPTION_WILD) || Randomizer_GetOption(RANDOMIZER_OPTION_GIFTS)
                     || Randomizer_GetOption(RANDOMIZER_OPTION_STATICS) || GetLegendaryRule() != RANDOMIZER_LEGENDARIES_UNCHANGED;
    return !speciesRandomized || Randomizer_GetOption(RANDOMIZER_OPTION_WILD_CONSISTENCY) == RANDOMIZER_CONSISTENCY_WHOLE_GAME;
}

// Birch's Johto starters normally need the full Hoenn Dex. When the settings can
// make that impossible they are ready right after the Hall of Fame instead.
u16 IsReadyForJohtoStarter(void)
{
    return HasAllHoennMons() || !Randomizer_IsFullHoennDexPossible();
}

// ── Field items ──────────────────────────────────────────────────────────────

enum FieldItemKind
{
    FIELD_ITEM_FIXED,   // key items, HMs and empty placeholders never move
    FIELD_ITEM_TM,      // TMs only trade places with other TMs
    FIELD_ITEM_OTHER,
};

static u32 GetFieldItemKind(u32 index)
{
    enum Item item = sRandomizerFieldItems[index].item;
    enum Pocket pocket;

    if (item == ITEM_NONE || item >= ITEMS_COUNT)
        return FIELD_ITEM_FIXED;
    pocket = GetItemPocket(item);
    if (pocket == POCKET_KEY_ITEMS)
        return FIELD_ITEM_FIXED;
    if (pocket == POCKET_TM_HM)
        return GetItemTMHMIndex(item) > NUM_TECHNICAL_MACHINES ? FIELD_ITEM_FIXED : FIELD_ITEM_TM;
    return FIELD_ITEM_OTHER;
}

static bool32 IsFieldItemOfKind(u32 value, const void *context)
{
    return value < ARRAY_COUNT(sRandomizerFieldItems) && GetFieldItemKind(value) == *(const u32 *)context;
}

// The location whose normal item this location holds in this game.
static u32 GetShuffledFieldItemSource(u32 index)
{
    u32 kind;

    if (!Randomizer_GetOption(RANDOMIZER_OPTION_FIELD_ITEMS))
        return index;
    kind = GetFieldItemKind(index);
    if (kind == FIELD_ITEM_FIXED)
        return index;
    return WalkPermutation(index, Hash(STREAM_FIELD_ITEMS, 0, 0), HalfBitsFor(ARRAY_COUNT(sRandomizerFieldItems)), TRUE, IsFieldItemOfKind, &kind);
}

static s32 FindFieldItem(u16 flag)
{
    s32 low = 0, high = ARRAY_COUNT(sRandomizerFieldItemsByFlag) - 1;

    while (low <= high)
    {
        s32 middle = (low + high) / 2;
        u16 index = sRandomizerFieldItemsByFlag[middle];
        if (sRandomizerFieldItems[index].flag == flag)
            return index;
        if (sRandomizerFieldItems[index].flag < flag)
            low = middle + 1;
        else
            high = middle - 1;
    }
    return -1;
}

// Item balls and hidden items, by their flag. Returns TRUE with the item and
// amount the location holds in this game when the shuffle changed it.
bool32 Randomizer_GetFieldItem(u16 flag, u16 *item, u16 *amount)
{
    s32 index;
    u32 source;

    if (!Randomizer_GetOption(RANDOMIZER_OPTION_FIELD_ITEMS))
        return FALSE;
    index = FindFieldItem(flag);
    if (index < 0)
        return FALSE;
    source = GetShuffledFieldItemSource(index);
    if (source == (u32)index)
        return FALSE;
    *item = sRandomizerFieldItems[source].item;
    *amount = sRandomizerFieldItems[source].amount;
    return TRUE;
}

// ── TMs ──────────────────────────────────────────────────────────────────────

static bool32 IsTMSlot(u32 value, const void *context)
{
    return value < NUM_TECHNICAL_MACHINES;
}

// TM indexes start at 1. Returns the TM whose normal move this TM teaches in this
// game. HMs never change.
u32 Randomizer_GetTMIndexContents(u32 tmIndex)
{
    if (tmIndex == 0 || tmIndex > NUM_TECHNICAL_MACHINES || !Randomizer_GetOption(RANDOMIZER_OPTION_TM_CONTENTS))
        return tmIndex;
    return 1 + WalkPermutation(tmIndex - 1, Hash(STREAM_TM_CONTENTS, 0, 0), HalfBitsFor(NUM_TECHNICAL_MACHINES), TRUE, IsTMSlot, NULL);
}

// The reverse: which TM teaches the normal move of this TM in this game.
u32 Randomizer_GetTMIndexTeaching(u32 contentsIndex)
{
    if (contentsIndex == 0 || contentsIndex > NUM_TECHNICAL_MACHINES || !Randomizer_GetOption(RANDOMIZER_OPTION_TM_CONTENTS))
        return contentsIndex;
    return 1 + WalkPermutation(contentsIndex - 1, Hash(STREAM_TM_CONTENTS, 0, 0), HalfBitsFor(NUM_TECHNICAL_MACHINES), FALSE, IsTMSlot, NULL);
}

static u32 GetPlayerTier(void)
{
    u32 badges = 0;

    if (FlagGet(FLAG_SYS_GAME_CLEAR))
        return RANDOMIZER_TIER_POSTGAME;
    for (u32 flag = FLAG_BADGE01_GET; flag <= FLAG_BADGE08_GET; flag++)
    {
        if (FlagGet(flag))
            badges++;
    }
    return badges;
}

#define TM_MASK_WORDS ((NUM_TECHNICAL_MACHINES + 31) / 32)

// Marks every TM the player could have obtained with their current badges: from
// a gym leader, an NPC, a shop, or wherever the field item shuffle put it.
static void GetAvailableTMs(u32 *mask)
{
    u32 tier = GetPlayerTier();

    memset(mask, 0, TM_MASK_WORDS * sizeof(u32));
    for (u32 i = 0; i < NUM_TECHNICAL_MACHINES; i++)
    {
        if (sRandomizerTMTier[i] <= tier)
            mask[i / 32] |= 1u << (i % 32);
    }
    for (u32 i = 0; i < ARRAY_COUNT(sRandomizerFieldItems); i++)
    {
        if (sRandomizerFieldItems[i].tier <= tier && GetFieldItemKind(i) == FIELD_ITEM_TM)
        {
            u32 tm = GetItemTMHMIndex(sRandomizerFieldItems[GetShuffledFieldItemSource(i)].item) - 1;
            mask[tm / 32] |= 1u << (tm % 32);
        }
    }
}

// ── Trainers ─────────────────────────────────────────────────────────────────

static bool32 IsBossTrainer(const struct Trainer *trainer)
{
    switch (trainer->trainerClass)
    {
    case TRAINER_CLASS_LEADER:
    case TRAINER_CLASS_ELITE_FOUR:
    case TRAINER_CLASS_CHAMPION:
    case TRAINER_CLASS_RIVAL:
    case TRAINER_CLASS_MAGMA_LEADER:
    case TRAINER_CLASS_AQUA_LEADER:
    case TRAINER_CLASS_MAGMA_ADMIN:
    case TRAINER_CLASS_AQUA_ADMIN:
        return TRUE;
    default:
        return FALSE;
    }
}

bool32 Randomizer_ShouldRandomizeTrainer(const struct Trainer *trainer)
{
    if (IsBossTrainer(trainer))
        return Randomizer_GetOption(RANDOMIZER_OPTION_BOSS_TRAINERS) != RANDOMIZER_BOSSES_UNCHANGED;
    return Randomizer_GetOption(RANDOMIZER_OPTION_REGULAR_TRAINERS);
}

// Unchanged bosses keep the abilities they were given, even when abilities are random.
bool32 Randomizer_KeepsTrainerAbilities(const struct Trainer *trainer)
{
    return IsBossTrainer(trainer) && Randomizer_GetOption(RANDOMIZER_OPTION_BOSS_TRAINERS) == RANDOMIZER_BOSSES_UNCHANGED;
}

// Trainers who fight more than once (rivals, bosses, rematches) share a name and
// class, so their Pokémon keep the same replacements between fights.
static u32 HashTrainer(const struct Trainer *trainer)
{
    u32 hash = trainer->trainerClass;

    for (u32 i = 0; i < ARRAY_COUNT(trainer->trainerName) && trainer->trainerName[i] != EOS; i++)
        hash = Mix32(hash ^ trainer->trainerName[i]);
    return hash;
}

static enum Item GetMegaStone(enum Species species)
{
    const struct FormChange *formChanges = gSpeciesInfo[species].formChangeTable;

    for (u32 i = 0; formChanges != NULL && formChanges[i].method != FORM_CHANGE_TERMINATOR; i++)
    {
        if (formChanges[i].method == FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM)
            return formChanges[i].param1;
    }
    return ITEM_NONE;
}

// The species a trainer's Pokémon becomes. A replacement family is picked for each
// of the trainer's original families, and the Pokémon takes the member at the same
// evolution stage, so a rival's Gible, Gabite and Garchomp become one new family.
enum Species Randomizer_GetTrainerSpecies(const struct Trainer *trainer, u32 monIndex)
{
    struct SpeciesFilter filter;
    const struct TrainerMon *mon = &trainer->party[monIndex];
    enum Species original = mon->species;
    enum Species root = Randomizer_GetFamilyRoot(original);
    u32 stage = Randomizer_GetEvolutionStage(original);
    u32 trainerHash = HashTrainer(trainer);
    u32 occurrence = 0;
    u32 branchHash;
    enum Species newRoot;

    // Wally's Ralts line becomes the line of whatever he caught in the tutorial.
    if (trainer->trainerPic == TRAINER_PIC_WALLY && root == SPECIES_RALTS && Randomizer_GetOption(RANDOMIZER_OPTION_WILD))
    {
        newRoot = Randomizer_GetFamilyRoot(Randomizer_GetStoryWildSpecies(SPECIES_RALTS, MAP_ROUTE102));
        if (newRoot == root)
            return original;
        return GetFamilyMemberAtStage(newRoot, stage, Hash(STREAM_TRAINER_EVOLUTION, trainerHash, newRoot));
    }
    if (original == SPECIES_NONE || !Randomizer_ShouldRandomizeTrainer(trainer) || IsLegendaryKept(original))
        return original;

    for (u32 i = 0; i < monIndex; i++)
    {
        if (Randomizer_GetFamilyRoot(trainer->party[i].species) == root)
            occurrence++;
    }

    // Every fight with this family uses the same filter, built from the family root,
    // so a Pokémon that has evolved since the last fight keeps its replacement.
    InitFilter(&filter, root);
    filter.requireBasic = TRUE;
    filter.minStages = Randomizer_GetFamilyLength(root);
    filter.avoidFamily = root;
    filter.targetBst = IsSimilarStrength() ? GetOriginalBST(root) : 0;
    filter.useMonotype = FALSE;
    if (IsBossTrainer(trainer) && Randomizer_GetOption(RANDOMIZER_OPTION_BOSS_TRAINERS) == RANDOMIZER_BOSSES_KEEP_TYPE)
    {
        filter.requiredType = GetOriginalType(root, 0);
        filter.requiredType2 = GetOriginalType(root, 1);
    }
    // Keep Mega Evolution: a Mega Stone holder becomes something that can use one.
    if (GetItemHoldEffect(mon->heldItem) == HOLD_EFFECT_MEGA_STONE)
    {
        filter.requireMega = TRUE;
        filter.megaStage = stage;
        filter.branchHash = Hash(STREAM_TRAINER_EVOLUTION, trainerHash, 0);
    }
    newRoot = PickSpecies(&filter, STREAM_TRAINER, trainerHash, root | (occurrence << 16));
    branchHash = filter.requireMega ? filter.branchHash : Hash(STREAM_TRAINER_EVOLUTION, trainerHash, newRoot);
    return GetFamilyMemberAtStage(newRoot, stage, branchHash);
}

// A randomized trainer Pokémon keeps its held item, except items that only work for
// one species: a Mega Stone becomes the new Pokémon's own, the rest Leftovers.
enum Item Randomizer_GetTrainerHeldItem(enum Species original, enum Species species, enum Item item)
{
    if (species == original || item == ITEM_NONE)
        return item;
    switch (GetItemHoldEffect(item))
    {
    case HOLD_EFFECT_MEGA_STONE:
    {
        enum Item stone = GetMegaStone(species);
        return stone != ITEM_NONE ? stone : ITEM_LEFTOVERS;
    }
    case HOLD_EFFECT_LIGHT_BALL:
    case HOLD_EFFECT_THICK_CLUB:
    case HOLD_EFFECT_LEEK:
    case HOLD_EFFECT_SOUL_DEW:
    case HOLD_EFFECT_DEEP_SEA_TOOTH:
    case HOLD_EFFECT_DEEP_SEA_SCALE:
    case HOLD_EFFECT_LUCKY_PUNCH:
    case HOLD_EFFECT_METAL_POWDER:
    case HOLD_EFFECT_QUICK_POWDER:
    case HOLD_EFFECT_ADAMANT_ORB:
    case HOLD_EFFECT_LUSTROUS_ORB:
    case HOLD_EFFECT_GRISEOUS_ORB:
    case HOLD_EFFECT_PRIMAL_ORB:
    case HOLD_EFFECT_MEMORY:
    case HOLD_EFFECT_DRIVE:
    case HOLD_EFFECT_BOOSTER_ENERGY:
    case HOLD_EFFECT_OGERPON_MASK:
        return ITEM_LEFTOVERS;
    default:
        return item;
    }
}

// ── Trainer movesets ─────────────────────────────────────────────────────────

#define MAX_MOVE_CANDIDATES 64

// Attacks a trainer never picks: self-KO, situational or one-hit KO moves.
static bool32 IsBannedTrainerMove(enum Move move)
{
    if (IsExplosionMove(move))
        return TRUE;
    switch (GetMoveEffect(move))
    {
    case EFFECT_OHKO:
    case EFFECT_FOCUS_PUNCH:
    case EFFECT_DREAM_EATER:
    case EFFECT_SNORE:
    case EFFECT_LAST_RESORT:
    case EFFECT_FINAL_GAMBIT:
    case EFFECT_BELCH:
    case EFFECT_SYNCHRONOISE:
    case EFFECT_MEMENTO:
    case EFFECT_HEALING_WISH:
    case EFFECT_LUNAR_DANCE:
    case EFFECT_SPIT_UP:
    case EFFECT_NATURAL_GIFT:
    case EFFECT_FLING:
    case EFFECT_BIDE:
    case EFFECT_REFLECT_DAMAGE:
        return TRUE;
    default:
        return FALSE;
    }
}

// Status moves worth a slot, best first.
static const u16 sGoodStatusMoves[] =
{
    MOVE_SHELL_SMASH, MOVE_DRAGON_DANCE, MOVE_QUIVER_DANCE, MOVE_SWORDS_DANCE, MOVE_NASTY_PLOT,
    MOVE_CALM_MIND, MOVE_BULK_UP, MOVE_SPORE, MOVE_RECOVER, MOVE_ROOST, MOVE_SLACK_OFF,
    MOVE_SOFT_BOILED, MOVE_STEALTH_ROCK, MOVE_WILL_O_WISP, MOVE_TOXIC, MOVE_THUNDER_WAVE,
    MOVE_LEECH_SEED, MOVE_SLEEP_POWDER, MOVE_SPIKES, MOVE_TOXIC_SPIKES, MOVE_TAILWIND,
    MOVE_SYNTHESIS, MOVE_MOONLIGHT, MOVE_MORNING_SUN,
};

static bool32 IsAttack(enum Move move)
{
    return GetMoveCategory(move) != DAMAGE_CATEGORY_STATUS && GetMovePower(move) != 0 && !IsBannedTrainerMove(move);
}

static bool32 HasType(enum Species species, enum Type type)
{
    return GetSpeciesType(species, 0) == type || GetSpeciesType(species, 1) == type;
}

static u32 ScoreAttack(enum Species species, enum Move move)
{
    u32 power = GetMovePower(move);
    u32 accuracy = GetMoveAccuracy(move);
    u32 attack = GetSpeciesBaseAttack(species);
    u32 spAttack = GetSpeciesBaseSpAttack(species);
    u32 score;

    if (power == 1) // variable power or fixed damage
        power = 60;
    if (accuracy == 0) // never misses
        accuracy = 100;
    score = power * accuracy;
    if (gMovesInfo[move].multiHit)
        score *= 3;
    else if (GetMoveStrikeCount(move) > 1)
        score *= GetMoveStrikeCount(move);
    if (HasType(species, GetMoveType(move)))
        score = score * 3 / 2;
    // Favor the stronger attacking stat.
    score = score * (GetMoveCategory(move) == DAMAGE_CATEGORY_PHYSICAL ? attack : spAttack) / max(1, max(attack, spAttack));
    if (MoveHasAdditionalEffectSelf(move, MOVE_EFFECT_RECHARGE))
        score = score * 3 / 5;
    if (GetMoveEffect(move) == EFFECT_TWO_TURNS_ATTACK || GetMoveEffect(move) == EFFECT_SOLAR_BEAM)
        score /= 2;
    return score;
}

static void AddCandidate(u16 *moves, u32 *count, enum Move move)
{
    if (move == MOVE_NONE || *count >= MAX_MOVE_CANDIDATES)
        return;
    for (u32 i = 0; i < *count; i++)
    {
        if (moves[i] == move)
            return;
    }
    moves[(*count)++] = move;
}

static bool32 IsChosen(const u16 *chosen, u32 count, enum Move move)
{
    for (u32 i = 0; i < count; i++)
    {
        if (chosen[i] == move)
            return TRUE;
    }
    return FALSE;
}

static bool32 CoversType(const u16 *chosen, u32 count, enum Type type)
{
    for (u32 i = 0; i < count; i++)
    {
        if (IsAttack(chosen[i]) && GetMoveType(chosen[i]) == type)
            return TRUE;
    }
    return FALSE;
}

// The best attack among the candidates, optionally of one type or of a type the
// set does not cover yet. MOVE_NONE when there is none.
static enum Move BestAttack(enum Species species, const u16 *moves, u32 count, const u16 *chosen, u32 chosenCount, enum Type type, bool32 newTypeOnly)
{
    enum Move best = MOVE_NONE;
    u32 bestScore = 0;

    for (u32 i = 0; i < count; i++)
    {
        u32 score;
        if (!IsAttack(moves[i]) || IsChosen(chosen, chosenCount, moves[i]))
            continue;
        if (type != TYPE_NONE && GetMoveType(moves[i]) != type)
            continue;
        if (newTypeOnly && CoversType(chosen, chosenCount, GetMoveType(moves[i])))
            continue;
        score = ScoreAttack(species, moves[i]);
        if (score > bestScore)
        {
            best = moves[i];
            bestScore = score;
        }
    }
    return best;
}

// The strongest sensible set for a randomized trainer Pokémon: its best attacks of
// its own types, then coverage, then one useful status move, from the level-up
// moves it knows by now and the TMs the player could have obtained by now.
void Randomizer_GiveTrainerMonMoves(struct Pokemon *mon)
{
    enum Species species = GetMonData(mon, MON_DATA_SPECIES);
    u32 level = GetMonData(mon, MON_DATA_LEVEL);
    const struct LevelUpMove *learnset = gSpeciesInfo[species].levelUpLearnset;
    u16 moves[MAX_MOVE_CANDIDATES];
    u16 chosen[MAX_MON_MOVES] = {MOVE_NONE};
    u32 availableTMs[TM_MASK_WORDS];
    u32 count = 0, chosenCount = 0;
    enum Move move;

    for (u32 i = 0; learnset != NULL && learnset[i].move != LEVEL_UP_MOVE_END; i++)
    {
        if (learnset[i].level <= level)
            AddCandidate(moves, &count, Randomizer_GetLevelUpMove(species, i, learnset[i].move));
    }
    GetAvailableTMs(availableTMs);
    for (u32 i = 0; i < NUM_TECHNICAL_MACHINES; i++)
    {
        if (!(availableTMs[i / 32] & (1u << (i % 32))))
            continue;
        move = GetTMHMMoveId(i + 1);
        if (CanLearnTeachableMove(species, move))
            AddCandidate(moves, &count, move);
    }

    // Best attacks of the Pokémon's own types.
    for (u32 slot = 0; slot < 2 && chosenCount < MAX_MON_MOVES; slot++)
    {
        enum Type type = GetSpeciesType(species, slot);
        if (slot == 1 && type == GetSpeciesType(species, 0))
            break;
        move = BestAttack(species, moves, count, chosen, chosenCount, type, FALSE);
        if (move != MOVE_NONE)
            chosen[chosenCount++] = move;
    }
    // Coverage, leaving the last slot for a status move.
    while (chosenCount < MAX_MON_MOVES - 1)
    {
        move = BestAttack(species, moves, count, chosen, chosenCount, TYPE_NONE, TRUE);
        if (move == MOVE_NONE)
            break;
        chosen[chosenCount++] = move;
    }
    // One useful status move, if the Pokémon has one.
    for (u32 i = 0; i < ARRAY_COUNT(sGoodStatusMoves) && chosenCount < MAX_MON_MOVES; i++)
    {
        if (IsChosen(moves, count, sGoodStatusMoves[i]))
        {
            chosen[chosenCount++] = sGoodStatusMoves[i];
            break;
        }
    }
    // Fill what is left with the next best attacks, then anything else.
    while (chosenCount < MAX_MON_MOVES)
    {
        move = BestAttack(species, moves, count, chosen, chosenCount, TYPE_NONE, FALSE);
        if (move == MOVE_NONE)
            break;
        chosen[chosenCount++] = move;
    }
    for (u32 i = 0; i < count && chosenCount < MAX_MON_MOVES; i++)
    {
        if (!IsChosen(chosen, chosenCount, moves[i]) && !IsBannedTrainerMove(moves[i]))
            chosen[chosenCount++] = moves[i];
    }
    if (chosenCount == 0)
    {
        GiveMonInitialMoveset(mon);
        return;
    }
    for (u32 i = 0; i < MAX_MON_MOVES; i++)
    {
        u32 pp = GetMovePP(chosen[i]);
        SetMonData(mon, MON_DATA_MOVE1 + i, &chosen[i]);
        SetMonData(mon, MON_DATA_PP1 + i, &pp);
    }
}

// ── HMs ──────────────────────────────────────────────────────────────────────

static const u16 sHMMoves[] = {MOVE_CUT, MOVE_FLY, MOVE_SURF, MOVE_STRENGTH, MOVE_FLASH, MOVE_ROCK_SMASH, MOVE_WATERFALL, MOVE_DIVE};

// Monotype or a narrow Generations choice can leave an HM that nothing the player
// can find is able to learn. Those HMs then work from the Bag for any Pokémon.
static u32 ComputeHMFallbacks(void)
{
    u32 missing = (1u << ARRAY_COUNT(sHMMoves)) - 1;

    if (!FiltersActive())
        return 0;
    for (enum Species species = 1; species < GetSpeciesLimit() && missing != 0; species++)
    {
        if (!Randomizer_IsSpeciesInPool(species) || !PassesFilters(species))
            continue;
        for (u32 i = 0; i < ARRAY_COUNT(sHMMoves); i++)
        {
            if ((missing & (1u << i)) && CanOriginallyLearnTeachable(species, sHMMoves[i]))
                missing &= ~(1u << i);
        }
    }
    return missing;
}

bool32 Randomizer_HasHMFallback(enum Move move)
{
    u32 fallbacks = VarGet(VAR_RANDOMIZER_OPTIONS_2) >> HM_FALLBACK_SHIFT;

    for (u32 i = 0; i < ARRAY_COUNT(sHMMoves); i++)
    {
        if (sHMMoves[i] == move)
            return (fallbacks >> i) & 1;
    }
    return FALSE;
}

// ── Species data ─────────────────────────────────────────────────────────────

// Both players of a link battle compute every Pokemon's data themselves, so it
// stays normal there; otherwise players with different settings would disagree.
static bool32 IsSpeciesDataRandomized(enum RandomizerOption option)
{
    if (gMain.inBattle && (gBattleTypeFlags & BATTLE_TYPE_LINK))
        return FALSE;
    return Randomizer_GetOption(option);
}

// ── Abilities ────────────────────────────────────────────────────────────────

// Abilities tied to a species or a form change. Species that have one keep it, and
// no other species is given one.
static bool32 IsSignatureAbility(enum Ability ability)
{
    switch (ability)
    {
    case ABILITY_MULTITYPE:
    case ABILITY_RKS_SYSTEM:
    case ABILITY_ZEN_MODE:
    case ABILITY_STANCE_CHANGE:
    case ABILITY_SCHOOLING:
    case ABILITY_DISGUISE:
    case ABILITY_BATTLE_BOND:
    case ABILITY_POWER_CONSTRUCT:
    case ABILITY_SHIELDS_DOWN:
    case ABILITY_COMATOSE:
    case ABILITY_ICE_FACE:
    case ABILITY_GULP_MISSILE:
    case ABILITY_HUNGER_SWITCH:
    case ABILITY_ZERO_TO_HERO:
    case ABILITY_COMMANDER:
    case ABILITY_TERA_SHIFT:
    case ABILITY_FORECAST:
    case ABILITY_FLOWER_GIFT:
        return TRUE;
    default:
        return gAbilitiesInfo[ability].cantBeCopied && gAbilitiesInfo[ability].cantBeSwapped;
    }
}

static bool32 CanGiveAbility(enum Ability ability, bool32 allowTroll)
{
    if (ability == ABILITY_NONE || ability >= ABILITIES_COUNT || gAbilitiesInfo[ability].name[0] == EOS)
        return FALSE;
    if (ability == ABILITY_WONDER_GUARD || ability == ABILITY_HUGE_POWER || ability == ABILITY_PURE_POWER)
        return FALSE;
    if (IsSignatureAbility(ability))
        return FALSE;
    // Troll abilities are the ones the battle AI rates as harmful.
    return allowTroll || gAbilitiesInfo[ability].aiRating >= 0;
}

// Each evolution family gets one new ability per slot, so evolving keeps it.
enum Ability Randomizer_GetSpeciesAbility(enum Species species, u32 slot, enum Ability ability)
{
    bool32 allowTroll;
    u32 root, key;

    if (ability == ABILITY_NONE || species >= NUM_SPECIES || !IsSpeciesDataRandomized(RANDOMIZER_OPTION_ABILITIES))
        return ability;
    if (IsSignatureAbility(ability) || (species == SPECIES_SHEDINJA && ability == ABILITY_WONDER_GUARD))
        return ability;
    allowTroll = Randomizer_GetOption(RANDOMIZER_OPTION_TROLL_ABILITIES);
    root = Randomizer_GetFamilyRoot(species);
    for (u32 attempt = 0; attempt < 256; attempt++)
    {
        key = Hash(STREAM_ABILITY, root, (slot << 16) | attempt);
        enum Ability candidate = 1 + key % (ABILITIES_COUNT - 1);
        if (CanGiveAbility(candidate, allowTroll))
            return candidate;
    }
    return ability;
}

// ── Types ────────────────────────────────────────────────────────────────────

static enum Type RandomType(u32 key, enum Type other)
{
    for (u32 attempt = 0; ; attempt++)
    {
        enum Type type = 1 + Hash(STREAM_TYPES, key, attempt) % (TYPE_FAIRY);
        if (type != TYPE_MYSTERY && type != other)
            return type;
    }
}

// Each evolution family gets new types. Evolutions keep them; one that gained a type
// in the normal game gains a random extra type.
enum Type Randomizer_GetSpeciesType(enum Species species, u32 slot, enum Type type)
{
    enum Species root;
    enum Type first, second;

    if (species >= NUM_SPECIES || species == SPECIES_NONE || !IsSpeciesDataRandomized(RANDOMIZER_OPTION_TYPES))
        return type;
    root = Randomizer_GetFamilyRoot(species);
    first = RandomType(root, TYPE_NONE);
    if (GetOriginalType(root, 0) != GetOriginalType(root, 1))
        second = RandomType(root | 0x10000, first);
    else if (species != root && (GetOriginalType(species, 0) != GetOriginalType(root, 0) || GetOriginalType(species, 1) != GetOriginalType(root, 1)))
        second = RandomType(species | 0x20000, first);
    else
        second = first;
    return slot == 0 ? first : second;
}

// ── Base stats ───────────────────────────────────────────────────────────────

// Each family's six base stats are shuffled with one shared pattern.
u32 Randomizer_GetSpeciesBaseStat(enum Species species, u32 stat, u32 value)
{
    const struct SpeciesInfo *info;
    u8 order[NUM_STATS];
    u32 values[NUM_STATS];

    if (species >= NUM_SPECIES || stat >= NUM_STATS || !IsSpeciesDataRandomized(RANDOMIZER_OPTION_BASE_STATS))
        return value;
    info = &gSpeciesInfo[species];
    values[STAT_HP] = info->baseHP;
    values[STAT_ATK] = info->baseAttack;
    values[STAT_DEF] = info->baseDefense;
    values[STAT_SPEED] = info->baseSpeed;
    values[STAT_SPATK] = info->baseSpAttack;
    values[STAT_SPDEF] = info->baseSpDefense;
    for (u32 i = 0; i < NUM_STATS; i++)
        order[i] = i;
    for (u32 i = NUM_STATS - 1; i > 0; i--)
    {
        u32 j = Hash(STREAM_BASE_STATS, Randomizer_GetFamilyRoot(species), i) % (i + 1);
        u8 temp = order[i];
        order[i] = order[j];
        order[j] = temp;
    }
    return values[order[stat]];
}

// ── Level-up moves ───────────────────────────────────────────────────────────

static bool32 CanGiveLevelUpMove(enum Move move)
{
    if (move == MOVE_NONE || move >= MOVES_COUNT || GetMoveEffect(move) == EFFECT_PLACEHOLDER)
        return FALSE;
    switch (move)
    {
    case MOVE_STRUGGLE:
    case MOVE_HYPERSPACE_FURY:
    case MOVE_AURA_WHEEL:
    case MOVE_CUT:
    case MOVE_FLY:
    case MOVE_SURF:
    case MOVE_STRENGTH:
    case MOVE_FLASH:
    case MOVE_ROCK_SMASH:
    case MOVE_WATERFALL:
    case MOVE_DIVE:
        return FALSE;
    default:
        return !IsBannedTrainerMove(move) || IsExplosionMove(move);
    }
}

// New level-up moves: about 40% of the Pokémon's own types, 20% Normal, the rest
// anything. The first move is always an attack, so every Pokémon can fight at once.
u16 Randomizer_GetLevelUpMove(enum Species species, u32 index, u16 move)
{
    u32 roll;

    if (move == MOVE_NONE || move == LEVEL_UP_MOVE_END || species >= NUM_SPECIES || !Randomizer_GetOption(RANDOMIZER_OPTION_LEVEL_UP_MOVES))
        return move;
    roll = Hash(STREAM_LEVEL_UP, species, index) % 100;
    for (u32 attempt = 0; attempt < 512; attempt++)
    {
        enum Move candidate = 1 + Hash(STREAM_LEVEL_UP, species, (index << 16) | (attempt + 1)) % (MOVES_COUNT - 1);
        enum Type type = GetMoveType(candidate);

        if (!CanGiveLevelUpMove(candidate))
            continue;
        if (index == 0 && (GetMoveCategory(candidate) == DAMAGE_CATEGORY_STATUS || GetMovePower(candidate) == 0 || GetMovePower(candidate) > 60))
            continue;
        if (attempt < 384)
        {
            if (roll < 40 && !HasType(species, type))
                continue;
            if (roll >= 40 && roll < 60 && type != TYPE_NORMAL)
                continue;
        }
        return candidate;
    }
    return move;
}

// ── TM and tutor compatibility ───────────────────────────────────────────────

static bool32 IsHMMove(enum Move move)
{
    for (u32 i = 0; i < ARRAY_COUNT(sHMMoves); i++)
    {
        if (sHMMoves[i] == move)
            return TRUE;
    }
    return FALSE;
}

// Each species learns about as many TMs and tutor moves as before, re-rolled with a
// lean towards its own types. HMs never change, so the Bag's HMs stay usable.
bool32 Randomizer_CanLearnTeachableMove(enum Species species, enum Move move, bool32 canLearn)
{
    const u16 *learnset;
    u32 count = 0, chance;

    if (species >= NUM_SPECIES || IsHMMove(move) || !Randomizer_GetOption(RANDOMIZER_OPTION_TM_COMPATIBILITY))
        return canLearn;
    learnset = gSpeciesInfo[species].teachableLearnset;
    for (u32 i = 0; learnset != NULL && learnset[i] != MOVE_UNAVAILABLE; i++)
        count++;
    // About 150 moves are teachable, so this keeps the species' usual share.
    chance = min(count * 100 / 150, 90);
    if (HasType(species, GetMoveType(move)))
        chance = min(chance * 2, 95);
    return Hash(STREAM_TM_COMPATIBILITY, species, move) % 100 < chance;
}

// ── Evolutions ───────────────────────────────────────────────────────────────

// A Pokémon evolves into a random Pokémon about as strong as its normal evolution.
// The method, level and item stay the same.
enum Species Randomizer_GetEvolutionTarget(enum Species species, enum Species target)
{
    struct SpeciesFilter filter;
    enum Species picked;

    if (target == SPECIES_NONE || target >= NUM_SPECIES || !Randomizer_GetOption(RANDOMIZER_OPTION_EVOLUTIONS))
        return target;
    InitFilter(&filter, target);
    filter.targetBst = GetOriginalBST(target);
    filter.useMonotype = FALSE;
    picked = PickSpecies(&filter, STREAM_EVOLUTIONS, species, target);
    return picked == species ? target : picked;
}

// ── Type chart ───────────────────────────────────────────────────────────────

static bool32 IsChartType(u32 value, const void *context)
{
    return value >= TYPE_NORMAL && value <= TYPE_FAIRY && value != TYPE_MYSTERY;
}

// The type chart is relabelled: a move of type A against type D uses the normal
// matchup of relabelled A against relabelled D, so every type keeps as many
// strengths and weaknesses as before.
u32 Randomizer_GetTypeChartType(u32 type)
{
    if (!IsChartType(type, NULL) || !IsSpeciesDataRandomized(RANDOMIZER_OPTION_TYPE_CHART))
        return type;
    return WalkPermutation(type, Hash(STREAM_TYPE_CHART, 0, 0), 3, TRUE, IsChartType, NULL);
}

#if TESTING
// For test/randomizer.c.
u32 Randomizer_Test_GetFieldItemCount(void)
{
    return ARRAY_COUNT(sRandomizerFieldItems);
}

u16 Randomizer_Test_GetFieldItemFlag(u32 index)
{
    return sRandomizerFieldItems[index].flag;
}

u16 Randomizer_Test_GetFieldItem(u32 index)
{
    return sRandomizerFieldItems[index].item;
}
#endif // TESTING
