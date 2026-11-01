#include "global.h"
#include "event_data.h"
#include "frontier_rules.h"

// BPE: storage for battle facility rule sets. It lives in the space the Tower's
// record mixing teams used, so the save layout and EWRAM use stay the same.
STATIC_ASSERT(sizeof(struct FrontierRuleData) <= sizeof(((struct BattleFrontier *)0)->towerRecords), FrontierRuleDataFits);

void InitFrontierRuleData(void)
{
    memset(&gSaveBlock2Ptr->frontier.ruleData, 0, sizeof(gSaveBlock2Ptr->frontier.ruleData));
    gSaveBlock2Ptr->frontier.activeRule = FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0);
    FlagSet(FLAG_FRONTIER_RULE_DATA_READY);
}

// Saves from before rule sets hold old record mixing teams in this space.
void ResetFrontierRuleDataOnce(void)
{
    if (!FlagGet(FLAG_FRONTIER_RULE_DATA_READY))
        InitFrontierRuleData();
}

u16 GetFrontierRule(void)
{
    return gSaveBlock2Ptr->frontier.activeRule;
}

void SetFrontierRule(u16 rule)
{
    gSaveBlock2Ptr->frontier.activeRule = rule;
}

static u8 *GetBestStreakPtr(u32 facility, u32 battleMode, u16 rule)
{
    return &gSaveBlock2Ptr->frontier.ruleData.bestStreaks[facility][battleMode][FRONTIER_RULE_SIZE(rule)][FRONTIER_RULE_GEN(rule)][FRONTIER_RULE_TIER(rule)];
}

u32 GetFrontierBestStreak(u32 facility, u32 battleMode, u16 rule)
{
    return *GetBestStreakPtr(facility, battleMode, rule);
}

// One current streak is kept per facility and battle type, so starting a different
// rule set there ends it. The best streak for each rule set stays.
void RecordFrontierStreak(u32 facility, u32 battleMode, u16 rule, u32 streak)
{
    struct FrontierRuleData *data = &gSaveBlock2Ptr->frontier.ruleData;
    u8 *best = GetBestStreakPtr(facility, battleMode, rule);

    data->currentRule[facility][battleMode] = rule;
    data->currentStreak[facility][battleMode] = streak;
    if (streak > *best)
        *best = min(streak, FRONTIER_BEST_STREAK_MAX);
}

u32 GetFrontierCurrentStreak(u32 facility, u32 battleMode, u16 rule)
{
    struct FrontierRuleData *data = &gSaveBlock2Ptr->frontier.ruleData;

    if (data->currentRule[facility][battleMode] != rule)
        return 0;
    return data->currentStreak[facility][battleMode];
}
