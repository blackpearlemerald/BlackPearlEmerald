#include "global.h"
#include "test/test.h"
#include "battle.h"
#include "battle_dome.h"
#include "battle_factory.h"
#include "battle_frontier.h"
#include "battle_setup.h"
#include "battle_util.h"
#include "event_data.h"
#include "frontier_rules.h"
#include "frontier_sets.h"
#include "frontier_util.h"
#include "constants/battle_dome.h"
#include "constants/battle_factory.h"
#include "constants/battle_frontier.h"

#define VANILLA       FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0)
#define FULL_DEX      FRONTIER_RULE(FRONTIER_RULES_FULL_DEX, 0, 0, 0)
#define SMOGON(g, t)  FRONTIER_RULE(FRONTIER_RULES_SMOGON, g, t, FRONTIER_TEAM_USUAL)
#define NAT_DEX_OU    SMOGON(FRONTIER_GEN_NATIONAL_DEX, FRONTIER_TIER_OU)

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
    u32 i, j;

    SetChallenge(FRONTIER_FACILITY_TOWER, battleMode, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_TOWER, battleMode, FRONTIER_LVL_OPEN) = streak;
    TRAINER_BATTLE_PARAM.opponentA = 0;
    FillFrontierTrainerParty(doubles ? FRONTIER_DOUBLES_PARTY_SIZE : FRONTIER_PARTY_SIZE);
    for (i = 0; i < FRONTIER_PARTY_SIZE; i++)
    {
        EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_LEVEL), MAX_LEVEL);
        for (j = 0; j < i; j++)
            EXPECT_NE(GetMonData(&gParties[B_TRAINER_OPPONENT_A][i], MON_DATA_SPECIES), GetMonData(&gParties[B_TRAINER_OPPONENT_A][j], MON_DATA_SPECIES));
    }

    SetChallenge(FRONTIER_FACILITY_FACTORY, battleMode, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_FACTORY, battleMode, FRONTIER_LVL_OPEN) = streak;
    for (i = 0; i < ARRAY_COUNT(gSaveBlock2Ptr->frontier.rentalMons); i++)
        gSaveBlock2Ptr->frontier.rentalMons[i].monId = 0xFFFF;
    SetFacilityPtrsGetLevel();
    gSpecialVar_0x8004 = BATTLE_FACTORY_FUNC_GENERATE_RENTAL_MONS;
    CallBattleFactoryFunction();
    gSpecialVar_0x8004 = BATTLE_FACTORY_FUNC_GENERATE_OPPONENT_MONS;
    CallBattleFactoryFunction();
    for (i = 0; i < PARTY_SIZE; i++)
        EXPECT_LT(gSaveBlock2Ptr->frontier.rentalMons[i].monId, gFrontierSetMonsCount);

    SetChallenge(FRONTIER_FACILITY_DOME, battleMode, rule);
    *GetFrontierWinStreakPtr(FRONTIER_FACILITY_DOME, battleMode, FRONTIER_LVL_OPEN) = streak / FRONTIER_STAGES_PER_CHALLENGE;
    gSpecialVar_0x8004 = BATTLE_DOME_FUNC_INIT_TRAINERS;
    CallBattleDomeFunction();
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
