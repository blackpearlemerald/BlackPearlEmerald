#ifndef GUARD_FRONTIER_RULES_H
#define GUARD_FRONTIER_RULES_H

#include "constants/frontier_rules.h"

void InitFrontierRuleData(void);
void ResetFrontierRuleDataOnce(void);
u16 GetFrontierRule(void);
void SetFrontierRule(u16 rule);
u32 GetFrontierBestStreak(u32 facility, u32 battleMode, u16 rule);
void RecordFrontierStreak(u32 facility, u32 battleMode, u16 rule, u32 streak);
u32 GetFrontierCurrentStreak(u32 facility, u32 battleMode, u16 rule);

#endif // GUARD_FRONTIER_RULES_H
