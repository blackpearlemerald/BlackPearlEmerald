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
#include "constants/trainer_hill.h"

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
    // Tents are mid-game, so they use the lowest tier's sets.
    if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_FULL_DEX && gSaveBlock2Ptr->frontier.lvlMode == FRONTIER_LVL_TENT)
        return &gFrontierSetPools[FRONTIER_GEN_NATIONAL_DEX][FRONTIER_TIER_RU];
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
    const struct FrontierSetPool *pool = GetFrontierSetPool(GetActiveFrontierRule(), battleMode != FRONTIER_MODE_SINGLES);
    u32 round = (gSaveBlock2Ptr->frontier.lvlMode == FRONTIER_LVL_TENT) ? 0 : GetCurrentFacilityWinStreak();
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

// Gens 1-9 have no written teams: their Brains use the strongest sets of the tier,
// with Gold's six first and Silver's the next six.
static u16 GetStrongestBrainSetId(u16 rule, u32 monId, u32 symbol)
{
    const struct FrontierSetPool *pool = GetFrontierSetPool(rule, FALSE);
    u16 species[PARTY_SIZE * 2];
    u32 wanted = monId + (symbol == 0 ? PARTY_SIZE : 0);
    u32 count = 0;
    u32 i, j;

    for (i = 0; i < pool->count; i++)
    {
        u16 setSpecies = gFrontierSetMons[pool->sets[i]].species;

        for (j = 0; j < count; j++)
        {
            if (species[j] == setSpecies)
                break;
        }
        if (j != count)
            continue;
        if (count == wanted)
            return pool->sets[i];
        species[count++] = setSpecies;
    }
    return pool->sets[0];
}

u16 GetFrontierBrainSetId(u32 monId)
{
    u16 rule = GetActiveFrontierRule();
    u32 facility = VarGet(VAR_FRONTIER_FACILITY);
    u32 symbol = GetFronterBrainSymbol();

    if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_FULL_DEX)
        return gFrontierBrainFullDexTeams[facility][symbol][monId];
    if (FRONTIER_RULE_GEN(rule) == FRONTIER_GEN_NATIONAL_DEX)
        return gFrontierBrainTierTeams[facility == FRONTIER_FACILITY_DOME][FRONTIER_RULE_TIER(rule)][symbol][monId];
    return GetStrongestBrainSetId(rule, monId, symbol);
}

#define HILL_LAST_FLOOR ((NUM_TRAINER_HILL_MODES * NUM_TRAINER_HILL_FLOORS) - 1)

// The same floor always has the same teams, so that times can be compared. Modes and
// floors climb from the middle of the pool to the top quarter.
void CreateFullDexHillMon(struct Pokemon *party, u32 slot, u32 mode, u32 floor, u32 trainerNum, u32 level, u32 otId)
{
    const struct FrontierSetPool *pool = GetFrontierSetPool(FRONTIER_RULE(FRONTIER_RULES_FULL_DEX, 0, 0, 0), FALSE);
    u32 step = mode * NUM_TRAINER_HILL_FLOORS + floor;
    u32 quarter = pool->count / 4;
    u32 start = 2 * quarter * (HILL_LAST_FLOOR - step) / HILL_LAST_FLOOR;
    u32 attempt, i;

    for (attempt = 0; ; attempt++)
    {
        u32 hash = (step * 64 + trainerNum * 8 + slot) * 2654435761u + attempt * 40503u;
        const struct TrainerMon *set = &gFrontierSetMons[pool->sets[start + (hash >> 8) % quarter]];

        for (i = 0; i < slot; i++)
        {
            if (GetMonData(&party[i], MON_DATA_SPECIES) == set->species)
                break;
        }
        if (i == slot)
        {
            CreateFacilityMon(set, level, MAX_PER_STAT_IVS, otId, 0, &party[slot]);
            return;
        }
    }
}

bool32 IsMonLegalForFrontierRule(struct Pokemon *mon, struct FrontierProblemInfo *problem)
{
    u16 rule = GetActiveFrontierRule();
    bool32 doubles = (VarGet(VAR_FRONTIER_BATTLE_MODE) == FRONTIER_MODE_DOUBLES);
    enum Item item = GetMonData(mon, MON_DATA_HELD_ITEM);
    enum Ability ability = GetMonAbility(mon);
    struct FrontierProblemInfo found = {FRONTIER_PROBLEM_NONE, 0};
    u32 i;

    enum Species species = GetMonData(mon, MON_DATA_SPECIES);
    u32 genBit = 1u << FRONTIER_RULE_GEN(rule);
    u16 anythingGoes = FRONTIER_RULE(FRONTIER_RULES_SMOGON, FRONTIER_RULE_GEN(rule), FRONTIER_TIER_ANYTHING_GOES, 0);

    if (FRONTIER_RULE_KIND(rule) != FRONTIER_RULES_SMOGON)
        return TRUE;

    // Anything Goes holds every Pokémon the generation has, so the rest are in higher tiers.
    if (!FrontierRuleAllowsSpecies(anythingGoes, doubles, species))
        found.kind = FRONTIER_PROBLEM_SPECIES_GEN;
    else if (!FrontierRuleAllowsSpecies(rule, doubles, species))
        found.kind = FRONTIER_PROBLEM_SPECIES;
    else if (!FrontierRuleAllowsItem(rule, doubles, item))
        found = (struct FrontierProblemInfo){(gFrontierItemGens[item] & genBit) ? FRONTIER_PROBLEM_ITEM : FRONTIER_PROBLEM_ITEM_GEN, item};
    else if (!FrontierRuleAllowsAbility(rule, doubles, ability))
        found = (struct FrontierProblemInfo){FRONTIER_PROBLEM_ABILITY, ability};

    for (i = 0; i < MAX_MON_MOVES && found.kind == FRONTIER_PROBLEM_NONE; i++)
    {
        enum Move move = GetMonData(mon, MON_DATA_MOVE1 + i);

        if (move != MOVE_NONE && !FrontierRuleAllowsMove(rule, doubles, move))
            found = (struct FrontierProblemInfo){(gFrontierMoveGens[move] & genBit) ? FRONTIER_PROBLEM_MOVE : FRONTIER_PROBLEM_MOVE_GEN, move};
    }
    if (problem != NULL)
        *problem = found;
    return found.kind == FRONTIER_PROBLEM_NONE;
}
