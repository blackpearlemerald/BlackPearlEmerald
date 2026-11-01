#include "global.h"
#include "test/test.h"
#include "event_data.h"
#include "frontier_rules.h"

#define RULE_OU FRONTIER_RULE(FRONTIER_RULES_SMOGON, 4, FRONTIER_TIER_OU, FRONTIER_TEAM_USUAL)
#define RULE_UU FRONTIER_RULE(FRONTIER_RULES_SMOGON, 4, FRONTIER_TIER_UU, FRONTIER_TEAM_USUAL)
#define RULE_6V6 FRONTIER_RULE(FRONTIER_RULES_SMOGON, 4, FRONTIER_TIER_OU, FRONTIER_TEAM_6V6)

TEST("Frontier rule sets pack every field")
{
    u16 rule = FRONTIER_RULE(FRONTIER_RULES_SMOGON, 9, FRONTIER_TIER_RU, FRONTIER_TEAM_6V6);

    EXPECT_EQ(FRONTIER_RULE_KIND(rule), FRONTIER_RULES_SMOGON);
    EXPECT_EQ(FRONTIER_RULE_GEN(rule), 9);
    EXPECT_EQ(FRONTIER_RULE_TIER(rule), FRONTIER_TIER_RU);
    EXPECT_EQ(FRONTIER_RULE_SIZE(rule), FRONTIER_TEAM_6V6);
}

TEST("Frontier rule data replaces old record mixing data once")
{
    FlagClear(FLAG_FRONTIER_RULE_DATA_READY);
    memset(&gSaveBlock2Ptr->frontier.ruleData, 0xAA, sizeof(gSaveBlock2Ptr->frontier.ruleData));
    ResetFrontierRuleDataOnce();
    EXPECT(FlagGet(FLAG_FRONTIER_RULE_DATA_READY));
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_TOWER, 0, RULE_OU), 0);

    RecordFrontierStreak(FRONTIER_RULE_TOWER, 0, RULE_OU, 14);
    ResetFrontierRuleDataOnce();
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_TOWER, 0, RULE_OU), 14);
}

TEST("Each rule set keeps its own best streak, capped at 255")
{
    InitFrontierRuleData();
    RecordFrontierStreak(FRONTIER_RULE_TOWER, 0, RULE_OU, 21);
    RecordFrontierStreak(FRONTIER_RULE_TOWER, 0, RULE_UU, 7);
    RecordFrontierStreak(FRONTIER_RULE_TOWER, 0, RULE_6V6, 300);
    RecordFrontierStreak(FRONTIER_RULE_TOWER, 0, RULE_OU, 3);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_TOWER, 0, RULE_OU), 21);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_TOWER, 0, RULE_UU), 7);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_TOWER, 0, RULE_6V6), FRONTIER_BEST_STREAK_MAX);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_FACTORY, 0, RULE_OU), 0);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_TOWER, 1, RULE_OU), 0);
}

TEST("Starting a different rule set ends the current streak")
{
    InitFrontierRuleData();
    RecordFrontierStreak(FRONTIER_RULE_DOME, 0, RULE_OU, 5);
    EXPECT_EQ(GetFrontierCurrentStreak(FRONTIER_RULE_DOME, 0, RULE_OU), 5);
    RecordFrontierStreak(FRONTIER_RULE_DOME, 0, RULE_UU, 1);
    EXPECT_EQ(GetFrontierCurrentStreak(FRONTIER_RULE_DOME, 0, RULE_OU), 0);
    EXPECT_EQ(GetFrontierCurrentStreak(FRONTIER_RULE_DOME, 0, RULE_UU), 1);
    EXPECT_EQ(GetFrontierBestStreak(FRONTIER_RULE_DOME, 0, RULE_OU), 5);
}
