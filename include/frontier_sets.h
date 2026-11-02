#ifndef GUARD_FRONTIER_SETS_H
#define GUARD_FRONTIER_SETS_H

#include "constants/frontier_rules.h"
#include "data.h"

// BPE: tested Pokémon sets and what each Smogon rule set allows. The tables come from
// src/data/battle_frontier/frontier_sets.h, which BPETools/generate_frontier_sets.py writes.

// A tier's index in singles, then the doubles tiers, which are AG, Ubers and OU.
#define FRONTIER_POOL_DOUBLES 5
#define FRONTIER_POOL_COUNT   8

// gFrontierSpeciesRules holds these per generation. A set bit means the species may enter.
#define FRONTIER_SPECIES_AG       (1 << 0)
#define FRONTIER_SPECIES_UBERS    (1 << 1)
#define FRONTIER_SPECIES_OU       (1 << 2)
#define FRONTIER_SPECIES_UU       (1 << 3)
#define FRONTIER_SPECIES_RU       (1 << 4)
#define FRONTIER_SPECIES_D_UBERS  (1 << 5)
#define FRONTIER_SPECIES_D_OU     (1 << 6)

// Indexes into gFrontierSetMons, strongest first. Small tiers end with sets from the tiers below.
struct FrontierSetPool
{
    const u16 *sets;
    u16 count;
};

struct FrontierBans
{
    const u16 *moves;
    const u16 *items;
    const u16 *abilities;
    u8 moveCount;
    u8 itemCount;
    u8 abilityCount;
};

extern const struct TrainerMon gFrontierSetMons[];
extern const u32 gFrontierSetMonsCount;
extern const struct FrontierSetPool gFrontierSetPools[FRONTIER_GEN_COUNT][FRONTIER_POOL_COUNT];
extern const struct FrontierSetPool gFrontierFullDexPools[2];
extern const u8 gFrontierSpeciesRules[][FRONTIER_GEN_COUNT];
extern const u16 gFrontierMoveGens[];
extern const u16 gFrontierItemGens[];
extern const struct FrontierBans gFrontierBans[FRONTIER_GEN_COUNT][FRONTIER_POOL_COUNT];

const struct FrontierSetPool *GetFrontierSetPool(u16 rule, bool32 doubles);
bool32 IsFrontierRuleAvailable(u16 rule, bool32 doubles);
bool32 FrontierRuleAllowsSpecies(u16 rule, bool32 doubles, enum Species species);
bool32 FrontierRuleAllowsMove(u16 rule, bool32 doubles, enum Move move);
bool32 FrontierRuleAllowsItem(u16 rule, bool32 doubles, enum Item item);
bool32 FrontierRuleAllowsAbility(u16 rule, bool32 doubles, enum Ability ability);

#endif // GUARD_FRONTIER_SETS_H
