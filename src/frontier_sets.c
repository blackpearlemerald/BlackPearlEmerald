#include "global.h"
#include "frontier_sets.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokeball.h"
#include "constants/pokemon.h"

#include "data/battle_frontier/frontier_sets.h"

static const u8 sSpeciesBits[FRONTIER_POOL_COUNT] =
{
    FRONTIER_SPECIES_AG,
    FRONTIER_SPECIES_UBERS,
    FRONTIER_SPECIES_OU,
    FRONTIER_SPECIES_UU,
    FRONTIER_SPECIES_RU,
    FRONTIER_SPECIES_AG,
    FRONTIER_SPECIES_D_UBERS,
    FRONTIER_SPECIES_D_OU,
};

static u32 GetPoolIndex(u16 rule, bool32 doubles)
{
    return FRONTIER_RULE_TIER(rule) + (doubles ? FRONTIER_POOL_DOUBLES : 0);
}

const struct FrontierSetPool *GetFrontierSetPool(u16 rule, bool32 doubles)
{
    if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_FULL_DEX)
        return &gFrontierFullDexPools[doubles != FALSE];
    return &gFrontierSetPools[FRONTIER_RULE_GEN(rule)][GetPoolIndex(rule, doubles)];
}

bool32 IsFrontierRuleAvailable(u16 rule, bool32 doubles)
{
    // Doubles have AG, Ubers and OU only.
    if (doubles && FRONTIER_RULE_TIER(rule) > FRONTIER_TIER_OU)
        return FALSE;
    return GetFrontierSetPool(rule, doubles)->count != 0;
}

static bool32 IsOnList(const u16 *list, u32 count, u32 value)
{
    u32 i;

    for (i = 0; i < count; i++)
    {
        if (list[i] == value)
            return TRUE;
    }
    return FALSE;
}

bool32 FrontierRuleAllowsSpecies(u16 rule, bool32 doubles, enum Species species)
{
    return (gFrontierSpeciesRules[species][FRONTIER_RULE_GEN(rule)] & sSpeciesBits[GetPoolIndex(rule, doubles)]) != 0;
}

bool32 FrontierRuleAllowsMove(u16 rule, bool32 doubles, enum Move move)
{
    u32 gen = FRONTIER_RULE_GEN(rule);
    const struct FrontierBans *bans = &gFrontierBans[gen][GetPoolIndex(rule, doubles)];

    if (!(gFrontierMoveGens[move] & (1u << gen)))
        return FALSE;
    return !IsOnList(bans->moves, bans->moveCount, move);
}

bool32 FrontierRuleAllowsItem(u16 rule, bool32 doubles, enum Item item)
{
    u32 gen = FRONTIER_RULE_GEN(rule);
    const struct FrontierBans *bans = &gFrontierBans[gen][GetPoolIndex(rule, doubles)];

    if (item == ITEM_NONE)
        return TRUE;
    if (!(gFrontierItemGens[item] & (1u << gen)))
        return FALSE;
    return !IsOnList(bans->items, bans->itemCount, item);
}

// Abilities have no era limit, because the player's Pokémon can't drop them.
bool32 FrontierRuleAllowsAbility(u16 rule, bool32 doubles, enum Ability ability)
{
    const struct FrontierBans *bans = &gFrontierBans[FRONTIER_RULE_GEN(rule)][GetPoolIndex(rule, doubles)];

    return !IsOnList(bans->abilities, bans->abilityCount, ability);
}
