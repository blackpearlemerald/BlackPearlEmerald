#include "global.h"
#include "test/test.h"
#include "frontier_sets.h"
#include "frontier_rules.h"
#include "pokemon.h"
#include "constants/frontier_rules.h"

#define SMOGON(gen, tier) FRONTIER_RULE(FRONTIER_RULES_SMOGON, gen, tier, FRONTIER_TEAM_USUAL)

static bool32 IsOnMoveList(const u16 *list, u32 move)
{
    u32 i;

    if (list == NULL)
        return FALSE;
    for (i = 0; list[i] != MOVE_UNAVAILABLE; i++)
    {
        if (list[i] == move)
            return TRUE;
    }
    return FALSE;
}

static bool32 CanLearnBySomeMeans(u32 species, u32 move)
{
    u32 i, tries;

    // Rotom gains its form's move on changing form, and form changes keep other moves.
    if (GET_BASE_SPECIES_ID(species) == SPECIES_ROTOM)
        return TRUE;
    if (species != GET_BASE_SPECIES_ID(species) && CanLearnBySomeMeans(GET_BASE_SPECIES_ID(species), move))
        return TRUE;
    for (tries = 0; tries < 4 && species != SPECIES_NONE; tries++)
    {
        const struct LevelUpMove *learnset = GetSpeciesLevelUpLearnset(species);

        for (i = 0; learnset[i].move != LEVEL_UP_MOVE_END; i++)
        {
            if (learnset[i].move == move)
                return TRUE;
        }
        if (IsOnMoveList(GetSpeciesTeachableLearnset(species), move) || IsOnMoveList(GetSpeciesEggMoves(species), move))
            return TRUE;
        species = GetSpeciesPreEvolution(species);
    }
    return FALSE;
}

TEST("Every Frontier set has a real Pokémon with four different moves and legal EVs")
{
    u32 i, j, k;

    for (i = 0; i < gFrontierSetMonsCount; i++)
    {
        const struct TrainerMon *mon = &gFrontierSetMons[i];
        u32 evs = 0;

        EXPECT_GT(mon->species, SPECIES_NONE);
        EXPECT_LT(mon->species, NUM_SPECIES);
        EXPECT(IsSpeciesEnabled(mon->species));
        for (j = 0; j < NUM_STATS; j++)
            evs += mon->ev[j];
        EXPECT_LE(evs, MAX_TOTAL_EVS);
        for (j = 0; j < MAX_MON_MOVES; j++)
        {
            if (mon->moves[j] == MOVE_NONE)
                continue;
            for (k = j + 1; k < MAX_MON_MOVES; k++)
                EXPECT_NE(mon->moves[j], mon->moves[k]);
        }
    }
}

TEST("Every Frontier set uses an ability its species has")
{
    u32 i, j, failures = 0;

    for (i = 0; i < gFrontierSetMonsCount; i++)
    {
        const struct TrainerMon *mon = &gFrontierSetMons[i];
        bool32 found = (mon->ability == ABILITY_NONE);

        for (j = 0; j < NUM_ABILITY_SLOTS; j++)
            found |= (GetSpeciesAbility(mon->species, j) == mon->ability);
        if (!found)
        {
            Test_MgbaPrintf("set %d: species %d ability %d", i, mon->species, mon->ability);
            failures++;
        }
    }
    EXPECT_EQ(failures, 0);
}

TEST("Players can learn every move in the Frontier sets")
{
    u32 i, j, failures = 0;

    for (i = 0; i < gFrontierSetMonsCount; i++)
    {
        const struct TrainerMon *mon = &gFrontierSetMons[i];

        for (j = 0; j < MAX_MON_MOVES; j++)
        {
            if (mon->moves[j] != MOVE_NONE && !CanLearnBySomeMeans(mon->species, mon->moves[j]))
            {
                Test_MgbaPrintf("set %d: species %d move %d", i, mon->species, mon->moves[j]);
                failures++;
            }
        }
    }
    EXPECT_EQ(failures, 0);
}

TEST("Every Frontier pool holds valid sets without repeats")
{
    u32 gen, pool, i;

    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (pool = 0; pool < FRONTIER_POOL_COUNT; pool++)
        {
            const struct FrontierSetPool *setPool = &gFrontierSetPools[gen][pool];

            for (i = 0; i < setPool->count; i++)
                EXPECT_LT(setPool->sets[i], gFrontierSetMonsCount);
        }
    }
}

TEST("Each generation offers the tiers the plan promises")
{
    u32 gen, tier;

    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (tier = 0; tier < FRONTIER_TIER_COUNT; tier++)
        {
            bool32 doubles = (gen == FRONTIER_GEN_NATIONAL_DEX || gen >= 3) && tier <= FRONTIER_TIER_OU;

            EXPECT(IsFrontierRuleAvailable(SMOGON(gen, tier), FALSE));
            EXPECT_EQ(IsFrontierRuleAvailable(SMOGON(gen, tier), TRUE), doubles);
        }
    }
}

TEST("Pool sets obey their own rule set")
{
    u32 gen, tier, doubles, i, j, failures = 0;

    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (tier = 0; tier < FRONTIER_TIER_COUNT; tier++)
        {
            for (doubles = 0; doubles < 2; doubles++)
            {
                u16 rule = SMOGON(gen, tier);

                if (!IsFrontierRuleAvailable(rule, doubles))
                    continue;
                const struct FrontierSetPool *pool = GetFrontierSetPool(rule, doubles);
                for (i = 0; i < pool->count; i++)
                {
                    const struct TrainerMon *mon = &gFrontierSetMons[pool->sets[i]];
                    bool32 legal = FrontierRuleAllowsSpecies(rule, doubles, mon->species)
                                && FrontierRuleAllowsItem(rule, doubles, mon->heldItem)
                                && FrontierRuleAllowsAbility(rule, doubles, mon->ability);

                    for (j = 0; j < MAX_MON_MOVES; j++)
                    {
                        if (mon->moves[j] != MOVE_NONE)
                            legal &= FrontierRuleAllowsMove(rule, doubles, mon->moves[j]);
                    }
                    if (!legal)
                    {
                        Test_MgbaPrintf("gen %d tier %d doubles %d: species %d item %d", gen, tier, doubles, mon->species, mon->heldItem);
                        failures++;
                    }
                }
            }
        }
    }
    EXPECT_EQ(failures, 0);
}

TEST("Full Dex pools keep out banned legendaries")
{
    u32 doubles, i, failures = 0;

    for (doubles = 0; doubles < 2; doubles++)
    {
        const struct FrontierSetPool *pool = &gFrontierFullDexPools[doubles];

        EXPECT_GT(pool->count, 500);
        for (i = 0; i < pool->count; i++)
        {
            u32 species = gFrontierSetMons[pool->sets[i]].species;

            if (gSpeciesInfo[species].isFrontierBanned)
            {
                Test_MgbaPrintf("banned species %d", species);
                failures++;
            }
        }
    }
    EXPECT_EQ(failures, 0);
}

TEST("Smogon rule sets follow each generation's tier list")
{
    u16 genThreeOU = SMOGON(3, FRONTIER_TIER_OU);
    u16 genNineOU = SMOGON(9, FRONTIER_TIER_OU);
    u16 natDexOU = SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_OU);
    u16 natDexAG = SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_ANYTHING_GOES);

    EXPECT(FrontierRuleAllowsSpecies(natDexOU, FALSE, SPECIES_GARCHOMP));
    EXPECT(!FrontierRuleAllowsSpecies(natDexOU, FALSE, SPECIES_MEWTWO));
    EXPECT(FrontierRuleAllowsSpecies(natDexAG, FALSE, SPECIES_MEWTWO));
    EXPECT(!FrontierRuleAllowsSpecies(genThreeOU, FALSE, SPECIES_GARCHOMP));
    EXPECT(FrontierRuleAllowsMove(natDexOU, FALSE, MOVE_THUNDERBOLT));
    EXPECT(!FrontierRuleAllowsMove(natDexOU, FALSE, MOVE_FISSURE));
    EXPECT(FrontierRuleAllowsMove(natDexAG, FALSE, MOVE_FISSURE));
    EXPECT(!FrontierRuleAllowsMove(genThreeOU, FALSE, MOVE_CLOSE_COMBAT));
    EXPECT(!FrontierRuleAllowsMove(genNineOU, FALSE, MOVE_PURSUIT));
    EXPECT(!FrontierRuleAllowsItem(genThreeOU, FALSE, ITEM_HEAVY_DUTY_BOOTS));
    EXPECT(FrontierRuleAllowsItem(natDexOU, FALSE, ITEM_LEFTOVERS));
    EXPECT(!FrontierRuleAllowsItem(SMOGON(1, FRONTIER_TIER_OU), FALSE, ITEM_LEFTOVERS));
    EXPECT(FrontierRuleAllowsItem(SMOGON(1, FRONTIER_TIER_OU), FALSE, ITEM_NONE));
    EXPECT(!FrontierRuleAllowsAbility(natDexOU, FALSE, ABILITY_MOODY));
    EXPECT(FrontierRuleAllowsAbility(natDexAG, FALSE, ABILITY_MOODY));
}
