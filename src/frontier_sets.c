#include "global.h"
#include "event_data.h"
#include "frontier_rules.h"
#include "frontier_sets.h"
#include "frontier_util.h"
#include "battle_frontier.h"
#include "pokemon.h"
#include "random.h"
#include "constants/battle_frontier.h"
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

const struct TrainerMon *GetFrontierMonTable(void)
{
    return FrontierUsesSetPools() ? gFrontierSetMons : gBattleFrontierMons;
}

#define RAMP_ROUNDS     7  // Rounds until enemies reach the strongest sets
#define RAMP_MIN_WINDOW 96 // Enough sets for a full Factory field of different species

// Pools are strongest first. A run starts in the middle half of the pool and
// narrows to the top quarter by the seventh round.
u16 GetRandomFrontierSetId(void)
{
    u32 battleMode = VarGet(VAR_FRONTIER_BATTLE_MODE);
    const struct FrontierSetPool *pool = GetFrontierSetPool(GetActiveFrontierRule(), battleMode == FRONTIER_MODE_DOUBLES);
    u32 round = GetCurrentFacilityWinStreak();
    u32 quarter = pool->count / 4;
    u32 start, length;

    if (VarGet(VAR_FRONTIER_FACILITY) != FRONTIER_FACILITY_DOME)
        round /= FRONTIER_STAGES_PER_CHALLENGE;
    if (round > RAMP_ROUNDS)
        round = RAMP_ROUNDS;

    start = quarter * (RAMP_ROUNDS - round) / RAMP_ROUNDS;
    length = quarter + quarter * (RAMP_ROUNDS - round) / RAMP_ROUNDS;
    if (length < RAMP_MIN_WINDOW)
        length = min(RAMP_MIN_WINDOW, pool->count);
    if (start + length > pool->count)
        start = pool->count - length;
    return pool->sets[start + Random() % length];
}

bool32 IsMonLegalForFrontierRule(struct Pokemon *mon, struct FrontierProblemInfo *problem)
{
    u16 rule = GetActiveFrontierRule();
    bool32 doubles = (VarGet(VAR_FRONTIER_BATTLE_MODE) == FRONTIER_MODE_DOUBLES);
    enum Item item = GetMonData(mon, MON_DATA_HELD_ITEM);
    enum Ability ability = GetMonAbility(mon);
    struct FrontierProblemInfo found = {FRONTIER_PROBLEM_NONE, 0};
    u32 i;

    if (FRONTIER_RULE_KIND(rule) != FRONTIER_RULES_SMOGON)
        return TRUE;

    if (!FrontierRuleAllowsSpecies(rule, doubles, GetMonData(mon, MON_DATA_SPECIES)))
        found.kind = FRONTIER_PROBLEM_SPECIES;
    else if (!FrontierRuleAllowsItem(rule, doubles, item))
        found = (struct FrontierProblemInfo){FRONTIER_PROBLEM_ITEM, item};
    else if (!FrontierRuleAllowsAbility(rule, doubles, ability))
        found = (struct FrontierProblemInfo){FRONTIER_PROBLEM_ABILITY, ability};

    for (i = 0; i < MAX_MON_MOVES && found.kind == FRONTIER_PROBLEM_NONE; i++)
    {
        enum Move move = GetMonData(mon, MON_DATA_MOVE1 + i);

        if (move != MOVE_NONE && !FrontierRuleAllowsMove(rule, doubles, move))
            found = (struct FrontierProblemInfo){FRONTIER_PROBLEM_MOVE, move};
    }
    if (problem != NULL)
        *problem = found;
    return found.kind == FRONTIER_PROBLEM_NONE;
}
