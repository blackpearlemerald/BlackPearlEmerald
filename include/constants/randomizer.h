#ifndef GUARD_CONSTANTS_RANDOMIZER_H
#define GUARD_CONSTANTS_RANDOMIZER_H

// BPE's built-in randomizer. The settings live in VAR_RANDOMIZER_SEED_LO/HI and
// VAR_RANDOMIZER_OPTIONS_0/1/2. Every option's value 0 means "off" (or the
// default), so a save that never chose the randomizer, including every converted
// pre-2.1 save, reads as off.

// Raise this when a change would give an existing seed different results, such
// as a new hash, a different pool rule or a reordered table. A save keeps the
// version it was started with, and a seed code only loads on its own version.
#define RANDOMIZER_ALGORITHM_VERSION 1

// Species with an ID at or above this limit were added after algorithm version 1
// and never appear in a version 1 game, so new species don't reshuffle old runs.
#define RANDOMIZER_V1_SPECIES_LIMIT 1573

enum RandomizerOption
{
    RANDOMIZER_OPTION_STARTERS,
    RANDOMIZER_OPTION_WILD,
    RANDOMIZER_OPTION_WILD_CONSISTENCY,
    RANDOMIZER_OPTION_GIFTS,
    RANDOMIZER_OPTION_STATICS,
    RANDOMIZER_OPTION_LEGENDARIES,
    RANDOMIZER_OPTION_STRENGTH,
    RANDOMIZER_OPTION_GENERATIONS,
    RANDOMIZER_OPTION_REGULAR_TRAINERS,
    RANDOMIZER_OPTION_BOSS_TRAINERS,
    RANDOMIZER_OPTION_ABILITIES,
    RANDOMIZER_OPTION_TROLL_ABILITIES,
    RANDOMIZER_OPTION_LEVEL_UP_MOVES,
    RANDOMIZER_OPTION_TM_COMPATIBILITY,
    RANDOMIZER_OPTION_TM_CONTENTS,
    RANDOMIZER_OPTION_FIELD_ITEMS,
    RANDOMIZER_OPTION_TYPES,
    RANDOMIZER_OPTION_EVOLUTIONS,
    RANDOMIZER_OPTION_BASE_STATS,
    RANDOMIZER_OPTION_TYPE_CHART,
    RANDOMIZER_OPTION_MONOTYPE,
    RANDOMIZER_OPTION_COUNT
};

// RANDOMIZER_OPTION_STARTERS
#define RANDOMIZER_STARTERS_OFF        0
#define RANDOMIZER_STARTERS_SAME_ROLES 1
#define RANDOMIZER_STARTERS_RANDOM     2

// RANDOMIZER_OPTION_WILD_CONSISTENCY
#define RANDOMIZER_CONSISTENCY_WHOLE_GAME 0
#define RANDOMIZER_CONSISTENCY_PER_ROUTE  1

// RANDOMIZER_OPTION_LEGENDARIES
#define RANDOMIZER_LEGENDARIES_UNCHANGED        0
#define RANDOMIZER_LEGENDARIES_AMONG_THEMSELVES 1
#define RANDOMIZER_LEGENDARIES_MIXED            2

// RANDOMIZER_OPTION_STRENGTH
#define RANDOMIZER_STRENGTH_SIMILAR      0
#define RANDOMIZER_STRENGTH_FULLY_RANDOM 1

// RANDOMIZER_OPTION_GENERATIONS is a mask of the generations that are switched
// OFF (bit 0 = Gen 1), so 0 keeps every generation.
#define RANDOMIZER_GENERATION_COUNT 9

// RANDOMIZER_OPTION_BOSS_TRAINERS
#define RANDOMIZER_BOSSES_UNCHANGED    0
#define RANDOMIZER_BOSSES_KEEP_TYPE    1
#define RANDOMIZER_BOSSES_FULLY_RANDOM 2

// RANDOMIZER_OPTION_MONOTYPE holds TYPE_NONE (off) or the chosen type.

enum RandomizerPreset
{
    RANDOMIZER_PRESET_RANDOMLOCKE,
    RANDOMIZER_PRESET_FULL,
    RANDOMIZER_PRESET_CHAOS,
    RANDOMIZER_PRESET_CUSTOM,
    RANDOMIZER_PRESET_COUNT
};

// Where the normal game hands out a species (src/data/randomizer/generated.h).
#define RANDOMIZER_SOURCE_WILD   (1 << 0)
#define RANDOMIZER_SOURCE_GIFT   (1 << 1)
#define RANDOMIZER_SOURCE_STATIC (1 << 2)

// A seed code is 16 characters from a 32-character alphabet.
#define RANDOMIZER_CODE_LENGTH 16

enum RandomizerCodeResult
{
    RANDOMIZER_CODE_OK,
    RANDOMIZER_CODE_INVALID,
    RANDOMIZER_CODE_OTHER_VERSION,
};

// Badge tiers for item sources: 0-8 badges, then the post-game.
#define RANDOMIZER_TIER_POSTGAME 9
#define RANDOMIZER_TIER_NEVER    255

#endif // GUARD_CONSTANTS_RANDOMIZER_H
