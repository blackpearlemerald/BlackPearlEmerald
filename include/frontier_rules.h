#ifndef GUARD_FRONTIER_RULES_H
#define GUARD_FRONTIER_RULES_H

#include "constants/frontier_rules.h"

struct Pokemon;
struct TrainerMon;

enum FrontierProblem
{
    FRONTIER_PROBLEM_NONE,
    FRONTIER_PROBLEM_SPECIES,
    FRONTIER_PROBLEM_MOVE,
    FRONTIER_PROBLEM_ITEM,
    FRONTIER_PROBLEM_ABILITY,
};

struct FrontierProblemInfo
{
    enum FrontierProblem kind;
    u16 value; // The move, item or ability
};

void InitFrontierRuleData(void);
void ResetFrontierRuleDataOnce(void);
u16 GetFrontierRule(void);
void SetFrontierRule(u16 rule);
u32 GetFrontierBestStreak(u32 facility, u32 battleMode, u16 rule);
void RecordFrontierStreak(u32 facility, u32 battleMode, u16 rule, u32 streak);
u32 GetFrontierCurrentStreak(u32 facility, u32 battleMode, u16 rule);
u16 GetActiveFrontierRule(void);
bool32 FrontierUsesSetPools(void);
bool32 IsFrontierSmogonRule(void);
bool32 IsFrontierItemClauseOn(void);
bool32 IsFrontierSleepClauseOn(void);
u16 *GetFrontierWinStreakPtr(u32 facility, u32 battleMode, u32 lvlMode);
void StartFrontierRuleStreak(u32 facility, u32 battleMode);
void RecordFrontierRuleStreak(u32 facility, u32 battleMode, u32 lvlMode);
void RaiseFrontierBattleLevels(void);
void RestoreFrontierBattleLevels(void);
const struct TrainerMon *GetFrontierMonTable(void);
u16 GetRandomFrontierSetId(void);
bool32 IsMonLegalForFrontierRule(struct Pokemon *mon, struct FrontierProblemInfo *problem);
void SetFrontierRuleForChallenge(void);
void BufferNextIllegalFrontierMon(void);
void ScriptCheckSmogonRulesAllowed(void);
void ScriptIsSmogonRule(void);

#endif // GUARD_FRONTIER_RULES_H
