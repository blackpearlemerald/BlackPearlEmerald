#include "global.h"
#include "test/test.h"
#include "battle.h"
#include "battle_dome.h"
#include "battle_factory.h"
#include "battle_frontier.h"
#include "battle_setup.h"
#include "battle_tower.h"
#include "battle_util.h"
#include "event_data.h"
#include "frontier_rules.h"
#include "frontier_sets.h"
#include "frontier_util.h"

#include "trainer_hill.h"
#include "constants/battle_dome.h"
#include "constants/battle_factory.h"
#include "constants/battle_frontier.h"
#include "constants/frontier_util.h"

#define VANILLA       FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0)
#define FULL_DEX      FRONTIER_RULE(FRONTIER_RULES_FULL_DEX, 0, 0, 0)
#define SMOGON(g, t)  FRONTIER_RULE(FRONTIER_RULES_SMOGON, g, t, FRONTIER_TEAM_USUAL)
#define NAT_DEX_OU    SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_OU)
#define SMOGON_6V6(g, t) FRONTIER_RULE(FRONTIER_RULES_SMOGON, g, t, FRONTIER_TEAM_6V6)

static void SetChallenge(u32 facility, u32 battleMode, u16 rule)
{
    VarSet(VAR_FRONTIER_FACILITY, facility);
    VarSet(VAR_FRONTIER_BATTLE_MODE, battleMode);
    gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_OPEN;
    gSaveBlock2Ptr->frontier.curChallengeBattleNum = 0;
    InitFrontierRuleData();
    SetFrontierRule(rule);
}

static void GivePlayerMon(u32 slot, u32 species, u32 level, u32 item, u32 move)
{
    CreateMon(&gParties[B_TRAINER_PLAYER][slot], species, level, 0, OTID_STRUCT_PLAYER_ID);
    CalculateMonStats(&gParties[B_TRAINER_PLAYER][slot]);
    SetMonData(&gParties[B_TRAINER_PLAYER][slot], MON_DATA_HELD_ITEM, &item);
    SetMonData(&gParties[B_TRAINER_PLAYER][slot], MON_DATA_MOVE1, &move);
}

TEST("Vanilla challenges keep the vanilla sets, levels and item clause")
{
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, VANILLA);
    EXPECT(!FrontierUsesSetPools());
    EXPECT(GetFrontierMonTable() == gBattleFrontierMons);
    EXPECT(IsFrontierItemClauseOn());
    EXPECT_EQ(GetFrontierEnemyMonLevel(FRONTIER_LVL_50), FRONTIER_MAX_LEVEL_50);
}

TEST("A rule left in the save can't reach Multis or other facilities")
{
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_MULTIS, NAT_DEX_OU);
    EXPECT(!FrontierUsesSetPools());
    SetChallenge(FRONTIER_FACILITY_PALACE, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    EXPECT(!FrontierUsesSetPools());
    SetChallenge(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_TENT;
    EXPECT(!FrontierUsesSetPools());
    gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_OPEN;
}

TEST("Smogon challenges use the set table at Level 100 with no item clause")
{
    SetChallenge(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    EXPECT(FrontierUsesSetPools());
    EXPECT(GetFrontierMonTable() == gFrontierSetMons);
    EXPECT(!IsFrontierItemClauseOn());
    EXPECT_EQ(SetFacilityPtrsGetLevel(), MAX_LEVEL);
    EXPECT(gFacilityTrainerMons == gFrontierSetMons);
}

TEST("Full Dex challenges use the set table and keep their level mode and item clause")
{
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, FULL_DEX);
    EXPECT(FrontierUsesSetPools());
    EXPECT(IsFrontierItemClauseOn());
    EXPECT_EQ(GetFrontierEnemyMonLevel(FRONTIER_LVL_50), FRONTIER_MAX_LEVEL_50);
}

TEST("Rule set streaks leave vanilla streaks alone")
{
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    gSaveBlock2Ptr->frontier.towerWinStreaks[FRONTIER_MODE_SINGLES][FRONTIER_LVL_OPEN] = 14;
    StartFrontierRuleStreak(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, FRONTIER_LVL_OPEN) = 5;
    EXPECT_EQ(gSaveBlock2Ptr->frontier.towerWinStreaks[FRONTIER_MODE_SINGLES][FRONTIER_LVL_OPEN], 14);
    EXPECT_EQ(GetCurrentFacilityWinStreak(), 5);

    SetFrontierRule(VANILLA);
    EXPECT_EQ(GetCurrentFacilityWinStreak(), 14);
    SetFrontierRule(FULL_DEX);
    EXPECT_EQ(GetCurrentFacilityWinStreak(), 0);
}

TEST("Picking another Smogon option ends the streak and keeps the best one")
{
    u16 other = SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_UU);

    SetChallenge(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_DOUBLES, NAT_DEX_OU);
    StartFrontierRuleStreak(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_DOUBLES);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_DOUBLES, FRONTIER_LVL_OPEN) = 9;
    RecordFrontierRuleStreak(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_DOUBLES, FRONTIER_LVL_OPEN);

    StartFrontierRuleStreak(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_DOUBLES);
    EXPECT_EQ(GetCurrentFacilityWinStreak(), 9);
    SetFrontierRule(other);
    StartFrontierRuleStreak(FRONTIER_FACILITY_FACTORY, FRONTIER_MODE_DOUBLES);
    EXPECT_EQ(GetCurrentFacilityWinStreak(), 0);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_FACTORY, FRONTIER_MODE_DOUBLES, NAT_DEX_OU), 9);
}

TEST("Full Dex streaks count separately for each level mode and keep their best")
{
    u16 *streak;

    SetChallenge(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, FULL_DEX);
    streak = GetFrontierWinStreakPtr(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, FRONTIER_LVL_OPEN);
    *streak = 3;
    RecordFrontierRuleStreak(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, FRONTIER_LVL_OPEN);
    *streak = 1;
    RecordFrontierRuleStreak(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, FRONTIER_LVL_OPEN);
    EXPECT_EQ(streak[1], 3);
    EXPECT_EQ(*GetFrontierWinStreakPtr(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50), 0);
}

TEST("The Level 100 raise lasts for the battle and changes nothing after it")
{
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];
    u32 exp, attack;

    ZeroPlayerPartyMons();
    GivePlayerMon(0, SPECIES_GARCHOMP, 50, ITEM_NONE, MOVE_EARTHQUAKE);
    exp = GetMonData(mon, MON_DATA_EXP);
    attack = GetMonData(mon, MON_DATA_ATK);

    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    RaiseFrontierBattleLevels();
    EXPECT_EQ(GetMonData(mon, MON_DATA_LEVEL), MAX_LEVEL);
    EXPECT_GT(GetMonData(mon, MON_DATA_ATK), attack);
    EXPECT_EQ(GetMonData(mon, MON_DATA_EXP), exp);

    RestoreFrontierBattleLevels();
    EXPECT(!FlagGet(FLAG_FRONTIER_LEVEL_RAISED));
    EXPECT_EQ(GetMonData(mon, MON_DATA_LEVEL), 50);
    EXPECT_EQ(GetMonData(mon, MON_DATA_ATK), attack);
}

TEST("Vanilla battles never raise levels")
{
    ZeroPlayerPartyMons();
    GivePlayerMon(0, SPECIES_GARCHOMP, 50, ITEM_NONE, MOVE_EARTHQUAKE);
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, VANILLA);
    RaiseFrontierBattleLevels();
    EXPECT(!FlagGet(FLAG_FRONTIER_LEVEL_RAISED));
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 50);
}

TEST("The team checker names what breaks the rules")
{
    struct FrontierProblemInfo problem;

    ZeroPlayerPartyMons();
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, NAT_DEX_OU);

    GivePlayerMon(0, SPECIES_MEWTWO, 50, ITEM_NONE, MOVE_PSYCHIC);
    EXPECT(!IsMonLegalForFrontierRule(&gParties[B_TRAINER_PLAYER][0], &problem));
    EXPECT_EQ(problem.kind, FRONTIER_PROBLEM_SPECIES);

    GivePlayerMon(4, SPECIES_GARCHOMP, 50, ITEM_NONE, MOVE_EARTHQUAKE); // Sand Veil
    EXPECT(!IsMonLegalForFrontierRule(&gParties[B_TRAINER_PLAYER][4], &problem));
    EXPECT_EQ(problem.kind, FRONTIER_PROBLEM_ABILITY);
    EXPECT_EQ(problem.value, ABILITY_SAND_VEIL);
    ZeroMonData(&gParties[B_TRAINER_PLAYER][4]);

    GivePlayerMon(1, SPECIES_CHARIZARD, 50, ITEM_NONE, MOVE_FISSURE);
    EXPECT(!IsMonLegalForFrontierRule(&gParties[B_TRAINER_PLAYER][1], &problem));
    EXPECT_EQ(problem.kind, FRONTIER_PROBLEM_MOVE);
    EXPECT_EQ(problem.value, MOVE_FISSURE);

    GivePlayerMon(2, SPECIES_CHARIZARD, 50, ITEM_BRIGHT_POWDER, MOVE_EARTHQUAKE);
    EXPECT(!IsMonLegalForFrontierRule(&gParties[B_TRAINER_PLAYER][2], &problem));
    EXPECT_EQ(problem.kind, FRONTIER_PROBLEM_ITEM);
    EXPECT_EQ(problem.value, ITEM_BRIGHT_POWDER);

    GivePlayerMon(3, SPECIES_CHARIZARD, 50, ITEM_LEFTOVERS, MOVE_EARTHQUAKE);
    EXPECT(IsMonLegalForFrontierRule(&gParties[B_TRAINER_PLAYER][3], &problem));

    gSpecialVar_0x8004 = 0;
    BufferNextIllegalFrontierMon();
    EXPECT_EQ(gSpecialVar_Result, TRUE);
    EXPECT_EQ(gSpecialVar_0x8004, 1);
    BufferNextIllegalFrontierMon();
    BufferNextIllegalFrontierMon();
    EXPECT_EQ(gSpecialVar_0x8004, 3);
    BufferNextIllegalFrontierMon();
    EXPECT_EQ(gSpecialVar_Result, FALSE);
}

TEST("Only Smogon tiers under Anything Goes have Sleep Clause")
{
    gBattleTypeFlags = BATTLE_TYPE_TRAINER | BATTLE_TYPE_BATTLE_TOWER;
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    EXPECT(IsSleepClauseEnabled());
    SetFrontierRule(SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_ANYTHING_GOES));
    EXPECT(!IsSleepClauseEnabled());
    SetFrontierRule(VANILLA);
    EXPECT(!IsSleepClauseEnabled());
    gBattleTypeFlags = 0;
}

TEST("Enemy sets start in the middle of the pool and end at the top")
{
    const struct FrontierSetPool *pool;
    u32 i, j, firstEarly = 0xFFFF, firstLate = 0xFFFF;

    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    pool = GetFrontierSetPool(NAT_DEX_OU, FALSE);
    for (i = 0; i < 300; i++)
    {
        u16 id = GetRandomFrontierSetId();

        for (j = 0; j < pool->count && pool->sets[j] != id; j++)
            ;
        EXPECT_LT(j, pool->count);
        firstEarly = min(firstEarly, j);
    }
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, FRONTIER_LVL_OPEN) = 49;
    for (i = 0; i < 300; i++)
    {
        u16 id = GetRandomFrontierSetId();

        for (j = 0; j < pool->count && pool->sets[j] != id; j++)
            ;
        firstLate = min(firstLate, j);
    }
    EXPECT_GT(firstEarly, firstLate);
}

// The facilities retry until a pick fits, so a pool that can't fit would hang here.
static void BuildEveryTeam(u32 rule, bool32 doubles, u32 streak)
{
    u32 battleMode = doubles ? FRONTIER_MODE_DOUBLES : FRONTIER_MODE_SINGLES;
    u32 i, j, teamSize;

    SetChallenge(FRONTIER_FACILITY_TOWER, battleMode, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_TOWER, battleMode, FRONTIER_LVL_OPEN) = streak;
    TRAINER_BATTLE_PARAM.opponentA = 0;
    teamSize = GetFrontierTeamSize();
    FillFrontierTrainerParty(teamSize);
    for (i = 0; i < teamSize; i++)
    {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_LEVEL), MAX_LEVEL);
        for (j = 0; j < i; j++)
            EXPECT_NE(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES), GetMonData(&gParties[B_TRAINER_OPPONENT_A][j], MON_DATA_SPECIES));
    }

    SetChallenge(FRONTIER_FACILITY_FACTORY, battleMode, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_FACTORY, battleMode, FRONTIER_LVL_OPEN) = streak;
    for (i = 0; i < FACTORY_RENTALS_6V6; i++)
        GetFactoryRental(i)->monId = 0xFFFF;
    SetFacilityPtrsGetLevel();
    gSpecialVar_0x8004 = BATTLE_FACTORY_FUNC_GENERATE_RENTAL_MONS;
    CallBattleFactoryFunction();
    gSpecialVar_0x8004 = BATTLE_FACTORY_FUNC_GENERATE_OPPONENT_MONS;
    CallBattleFactoryFunction();
    for (i = 0; i < GetFactoryRentalCount(); i++)
        EXPECT_LT(GetFactoryRental(i)->monId, gFrontierSetMonsCount);
    for (i = 0; i < GetFactoryTeamSize(); i++)
    {
        for (j = 0; j < GetFactoryRentalCount(); j++)
            EXPECT_NE(gFacilityTrainerMons[gFrontierTempParty[i]].species, gFacilityTrainerMons[GetFactoryRental(j)->monId].species);
    }

    SetChallenge(FRONTIER_FACILITY_DOME, battleMode, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_DOME, battleMode, FRONTIER_LVL_OPEN) = streak / FRONTIER_STAGES_PER_CHALLENGE;
    gSpecialVar_0x8004 = BATTLE_DOME_FUNC_INIT_TRAINERS;
    CallBattleDomeFunction();
    TRAINER_BATTLE_PARAM.opponentA = gSaveBlock2Ptr->frontier.domeTrainers[1].trainerId;
    gSpecialVar_0x8004 = BATTLE_DOME_FUNC_INIT_OPPONENT_PARTY;
    CallBattleDomeFunction();
    if (FRONTIER_RULE_SIZE(rule) == FRONTIER_TEAM_6V6)
    {
        for (i = 0; i < PARTY_SIZE; i++)
        {
            EXPECT_NE(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES), SPECIES_NONE);
            for (j = 0; j < i; j++)
                EXPECT_NE(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES), GetMonData(&gParties[B_TRAINER_OPPONENT_A][j], MON_DATA_SPECIES));
        }
    }
}

TEST("Every singles rule set can fill the Tower, Factory and Dome")
{
    u32 gen, tier;

    ZeroPlayerPartyMons();
    for (gen = 0; gen < 3; gen++)
        GivePlayerMon(gen, SPECIES_GARCHOMP + gen, 50, ITEM_NONE, MOVE_TACKLE);
    gSaveBlock2Ptr->frontier.selectedPartyMons[0] = 1;
    gSaveBlock2Ptr->frontier.selectedPartyMons[1] = 2;
    gSaveBlock2Ptr->frontier.selectedPartyMons[2] = 3;
    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (tier = 0; tier < FRONTIER_TIER_COUNT; tier++)
        {
            BuildEveryTeam(SMOGON(gen, tier), FALSE, 0);
            BuildEveryTeam(SMOGON(gen, tier), FALSE, 49);
        }
    }
}

TEST("Every doubles rule set can fill the Tower, Factory and Dome")
{
    u32 gen, tier;

    ZeroPlayerPartyMons();
    for (gen = 0; gen < 3; gen++)
        GivePlayerMon(gen, SPECIES_GARCHOMP + gen, 50, ITEM_NONE, MOVE_TACKLE);
    gSaveBlock2Ptr->frontier.selectedPartyMons[0] = 1;
    gSaveBlock2Ptr->frontier.selectedPartyMons[1] = 2;
    gSaveBlock2Ptr->frontier.selectedPartyMons[2] = 3;
    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        if (gen == 1 || gen == 2)
            continue;
        for (tier = 0; tier <= FRONTIER_TIER_OU; tier++)
        {
            BuildEveryTeam(SMOGON(gen, tier), TRUE, 0);
            BuildEveryTeam(SMOGON(gen, tier), TRUE, 49);
        }
    }
}

TEST("Every singles rule set can fill six-Pokémon teams")
{
    u32 gen, tier;

    ZeroPlayerPartyMons();
    for (gen = 0; gen < 3; gen++)
        GivePlayerMon(gen, SPECIES_GARCHOMP + gen, 50, ITEM_NONE, MOVE_TACKLE);
    gSaveBlock2Ptr->frontier.selectedPartyMons[0] = 1;
    gSaveBlock2Ptr->frontier.selectedPartyMons[1] = 2;
    gSaveBlock2Ptr->frontier.selectedPartyMons[2] = 3;
    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (tier = 0; tier < FRONTIER_TIER_COUNT; tier++)
        {
            BuildEveryTeam(SMOGON_6V6(gen, tier), FALSE, 0);
            BuildEveryTeam(SMOGON_6V6(gen, tier), FALSE, 49);
        }
    }
}

TEST("Every doubles rule set can fill six-Pokémon teams")
{
    u32 gen, tier;

    ZeroPlayerPartyMons();
    for (gen = 0; gen < 3; gen++)
        GivePlayerMon(gen, SPECIES_GARCHOMP + gen, 50, ITEM_NONE, MOVE_TACKLE);
    gSaveBlock2Ptr->frontier.selectedPartyMons[0] = 1;
    gSaveBlock2Ptr->frontier.selectedPartyMons[1] = 2;
    gSaveBlock2Ptr->frontier.selectedPartyMons[2] = 3;
    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        if (gen == 1 || gen == 2)
            continue;
        for (tier = 0; tier <= FRONTIER_TIER_OU; tier++)
        {
            BuildEveryTeam(SMOGON_6V6(gen, tier), TRUE, 0);
            BuildEveryTeam(SMOGON_6V6(gen, tier), TRUE, 49);
        }
    }
}

TEST("Team sizes follow the battle type and the rule")
{
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, NAT_DEX_OU);
    EXPECT_EQ(GetFrontierTeamSize(), FRONTIER_PARTY_SIZE);
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_DOUBLES, NAT_DEX_OU);
    EXPECT_EQ(GetFrontierTeamSize(), FRONTIER_DOUBLES_PARTY_SIZE);
    SetChallenge(FRONTIER_FACILITY_DOME, FRONTIER_MODE_DOUBLES, NAT_DEX_OU);
    EXPECT_EQ(GetFrontierTeamSize(), FRONTIER_PARTY_SIZE);
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_MULTIS, SMOGON_6V6(0, 2));
    EXPECT_EQ(GetFrontierTeamSize(), FRONTIER_MULTI_PARTY_SIZE);
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_DOUBLES, SMOGON_6V6(0, 2));
    EXPECT_EQ(GetFrontierTeamSize(), PARTY_SIZE);
    SetChallenge(FRONTIER_FACILITY_PALACE, FRONTIER_MODE_SINGLES, SMOGON_6V6(0, 2));
    EXPECT_EQ(GetFrontierTeamSize(), FRONTIER_PARTY_SIZE);
}

TEST("The last two of six selected Pokémon stay separate from the save's list")
{
    u32 i;

    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, SMOGON_6V6(0, 2));
    for (i = 0; i < PARTY_SIZE; i++)
        SetFrontierSelectedMon(i, i + 1);
    for (i = 0; i < PARTY_SIZE; i++)
        EXPECT_EQ(GetFrontierSelectedMon(i), i + 1);
    EXPECT_EQ(gSaveBlock2Ptr->frontier.selectedPartyMons[3], 4);
    EXPECT_EQ(gSaveBlock2Ptr->frontier.ruleData.extraSelectedMons[1], 6);
}

static u32 GetBattlePointsForWin(u16 rule)
{
    u32 before;

    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_SINGLES, FRONTIER_LVL_OPEN) = 21;
    TRAINER_BATTLE_PARAM.opponentA = 0;
    before = gSaveBlock2Ptr->frontier.battlePoints;
    gSpecialVar_0x8004 = FRONTIER_UTIL_FUNC_GIVE_BATTLE_POINTS;
    CallFrontierUtilFunc();
    return gSaveBlock2Ptr->frontier.battlePoints - before;
}

TEST("6v6 pays double Battle Points and other rule sets pay the same")
{
    u32 usual;

    gSaveBlock2Ptr->frontier.battlePoints = 0;
    usual = GetBattlePointsForWin(VANILLA);
    EXPECT_GT(usual, 0);
    EXPECT_EQ(GetBattlePointsForWin(NAT_DEX_OU), usual);
    EXPECT_EQ(GetBattlePointsForWin(FULL_DEX), usual);
    EXPECT_EQ(GetBattlePointsForWin(SMOGON_6V6(0, 2)), usual * 2);
}

TEST("Every facility offers Full Dex with its own streak")
{
    static const u8 facilities[] = {
        FRONTIER_FACILITY_TOWER, FRONTIER_FACILITY_DOME, FRONTIER_FACILITY_PALACE, FRONTIER_FACILITY_ARENA,
        FRONTIER_FACILITY_FACTORY, FRONTIER_FACILITY_PIKE, FRONTIER_FACILITY_PYRAMID,
    };
    u32 i, j;

    for (i = 0; i < ARRAY_COUNT(facilities); i++)
    {
        u32 facility = facilities[i];

        SetChallenge(facility, FRONTIER_MODE_SINGLES, VANILLA);
        *GetFrontierWinStreakPtr(facility, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50) = 3;
        SetFrontierRule(FULL_DEX);
        EXPECT(FrontierUsesSetPools());
        EXPECT_EQ(*GetFrontierWinStreakPtr(facility, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50), 0);
        *GetFrontierWinStreakPtr(facility, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50) = 9;
        RecordFrontierRuleStreak(facility, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50);
        for (j = 0; j < ARRAY_COUNT(facilities); j++)
        {
            if (i != j)
                EXPECT_EQ(*GetFrontierWinStreakPtr(facilities[j], FRONTIER_MODE_SINGLES, FRONTIER_LVL_50), 0);
        }
        SetFrontierRule(VANILLA);
        EXPECT_EQ(*GetFrontierWinStreakPtr(facility, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50), 3);
        *GetFrontierWinStreakPtr(facility, FRONTIER_MODE_SINGLES, FRONTIER_LVL_50) = 0;
    }
}

TEST("Full Dex reaches Multis, but not Link Multis")
{
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_MULTIS, FULL_DEX);
    EXPECT(FrontierUsesSetPools());
    SetChallenge(FRONTIER_FACILITY_TOWER, FRONTIER_MODE_LINK_MULTIS, FULL_DEX);
    EXPECT(!FrontierUsesSetPools());
}

TEST("Full Dex fills every facility's Trainers from the sets")
{
    static const u8 facilities[] = {FRONTIER_FACILITY_PALACE, FRONTIER_FACILITY_ARENA, FRONTIER_FACILITY_PIKE, FRONTIER_FACILITY_PYRAMID};
    u32 i, j;

    ZeroPlayerPartyMons();
    GivePlayerMon(0, SPECIES_GARCHOMP, 50, ITEM_NONE, MOVE_TACKLE);
    for (i = 0; i < ARRAY_COUNT(facilities); i++)
    {
        SetChallenge(facilities[i], FRONTIER_MODE_SINGLES, FULL_DEX);
        gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_50;
        TRAINER_BATTLE_PARAM.opponentA = 0;
        FillFrontierTrainerParty(FRONTIER_PARTY_SIZE);
        for (j = 0; j < FRONTIER_PARTY_SIZE; j++)
        {
            EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][j], MON_DATA_LEVEL), FRONTIER_MAX_LEVEL_50);
            EXPECT(!gSpeciesInfo[GetMonData(&gParties[B_TRAINER_OPPONENT_A][j], MON_DATA_SPECIES)].isFrontierBanned);
        }
    }
}

TEST("Full Dex Tents use the lowest tier's sets at the Tent's level")
{
    const struct FrontierSetPool *pool;
    u32 i;

    ZeroPlayerPartyMons();
    GivePlayerMon(0, SPECIES_GARCHOMP, 35, ITEM_NONE, MOVE_TACKLE);
    SetChallenge(FRONTIER_FACILITY_PALACE, FRONTIER_MODE_SINGLES, FULL_DEX);
    gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_TENT;
    EXPECT(FrontierUsesSetPools());
    pool = GetFrontierSetPool(FULL_DEX, FALSE);
    EXPECT(pool == GetFrontierSetPool(SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_RU), FALSE));
    SetTentPtrsGetLevel();
    EXPECT(gFacilityTrainerMons == gFrontierSetMons);
    gSaveBlock2Ptr->frontier.curChallengeBattleNum = 0;
    TRAINER_BATTLE_PARAM.opponentA = 0;
    FillTentTrainerParty(FRONTIER_PARTY_SIZE);
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_LEVEL), 35);
    gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_OPEN;
}

TEST("Full Dex Hill teams never change and hold no repeats")
{
    u32 mode, floor, trainer, i, j;

    for (mode = 0; mode < NUM_TRAINER_HILL_MODES; mode++)
    {
        for (floor = 0; floor < NUM_TRAINER_HILL_FLOORS; floor++)
        {
            for (trainer = 0; trainer < HILL_TRAINERS_PER_FLOOR; trainer++)
            {
                u16 species[MULTI_PARTY_SIZE];

                for (i = 0; i < MULTI_PARTY_SIZE; i++)
                {
                    CreateFullDexHillMon(gParties[B_TRAINER_OPPONENT_A], i, mode, floor, trainer, 50, 0);
                    species[i] = GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES);
                    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_LEVEL), 50);
                    EXPECT(!gSpeciesInfo[species[i]].isFrontierBanned);
                    for (j = 0; j < i; j++)
                        EXPECT_NE(species[i], species[j]);
                }
                ZeroEnemyPartyMons();
                for (i = 0; i < MULTI_PARTY_SIZE; i++)
                {
                    CreateFullDexHillMon(gParties[B_TRAINER_OPPONENT_A], i, mode, floor, trainer, 50, 0);
                    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES), species[i]);
                }
                ZeroEnemyPartyMons();
            }
        }
    }
}

static void ExpectBrainTeam(u32 facility, u16 rule, bool32 gold)
{
    u32 i, j, teamSize;

    SetChallenge(facility, FRONTIER_MODE_SINGLES, rule);
    if (gold)
        FlagSet(FLAG_SYS_TOWER_SILVER + facility * 2);
    else
        FlagClear(FLAG_SYS_TOWER_SILVER + facility * 2);
    teamSize = GetFrontierTeamSize();
    TRAINER_BATTLE_PARAM.opponentA = TRAINER_FRONTIER_BRAIN;
    FillFrontierTrainerParty(teamSize);
    for (i = 0; i < teamSize; i++)
    {
        u32 species = GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES);

        EXPECT_NE(species, SPECIES_NONE);
        EXPECT_EQ(species, GetFrontierBrainMonSpecies(i));
        if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_SMOGON)
            EXPECT(FrontierRuleAllowsSpecies(rule, FALSE, species));
        else
            EXPECT(!gSpeciesInfo[species].isFrontierBanned);
        for (j = 0; j < i; j++)
            EXPECT_NE(species, GetMonData(&gParties[B_TRAINER_OPPONENT_A][j], MON_DATA_SPECIES));
    }
    FlagClear(FLAG_SYS_TOWER_SILVER + facility * 2);
}

TEST("Frontier Brains have legal teams under every rule set")
{
    static const u8 facilities[] = {FRONTIER_FACILITY_TOWER, FRONTIER_FACILITY_PALACE, FRONTIER_FACILITY_ARENA, FRONTIER_FACILITY_PIKE, FRONTIER_FACILITY_PYRAMID};
    u32 i, gen, tier, symbol;

    ZeroPlayerPartyMons();
    GivePlayerMon(0, SPECIES_GARCHOMP, 50, ITEM_NONE, MOVE_TACKLE);
    for (symbol = 0; symbol < 2; symbol++)
    {
        for (i = 0; i < ARRAY_COUNT(facilities); i++)
            ExpectBrainTeam(facilities[i], FULL_DEX, symbol);
        for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
        {
            for (tier = 0; tier < FRONTIER_TIER_COUNT; tier++)
            {
                ExpectBrainTeam(FRONTIER_FACILITY_TOWER, SMOGON(gen, tier), symbol);
                ExpectBrainTeam(FRONTIER_FACILITY_TOWER, SMOGON_6V6(gen, tier), symbol);
            }
        }
    }
}

TEST("The Dome's Brain picks two Pokémon, or brings all six in 6v6")
{
    u32 i;

    ZeroPlayerPartyMons();
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
        GivePlayerMon(i, SPECIES_GARCHOMP + i, 50, ITEM_NONE, MOVE_TACKLE);
    gSaveBlock2Ptr->frontier.selectedPartyMons[0] = 1;
    gSaveBlock2Ptr->frontier.selectedPartyMons[1] = 2;
    gSaveBlock2Ptr->frontier.selectedPartyMons[2] = 3;
    SetChallenge(FRONTIER_FACILITY_DOME, FRONTIER_MODE_SINGLES, FULL_DEX);
    gSpecialVar_0x8004 = BATTLE_DOME_FUNC_INIT_TRAINERS;
    CallBattleDomeFunction();
    gSaveBlock2Ptr->frontier.domeTrainers[1].trainerId = TRAINER_FRONTIER_BRAIN;
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
        gSaveBlock2Ptr->frontier.domeMonIds[1][i] = GetFrontierBrainMonSpecies(i);
    TRAINER_BATTLE_PARAM.opponentA = TRAINER_FRONTIER_BRAIN;
    FillFrontierTrainerParty(DOME_BATTLE_PARTY_SIZE);
    EXPECT_NE(GetMonData(&gParties[B_TRAINER_OPPONENT_A][1], MON_DATA_SPECIES), SPECIES_NONE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][2], MON_DATA_SPECIES), SPECIES_NONE);

    ExpectBrainTeam(FRONTIER_FACILITY_DOME, SMOGON_6V6(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_OU), FALSE);
}

