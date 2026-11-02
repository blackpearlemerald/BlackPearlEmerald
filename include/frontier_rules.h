#ifndef GUARD_FRONTIER_RULES_H
#define GUARD_FRONTIER_RULES_H

#include "constants/frontier_rules.h"

struct Pokemon;
struct TrainerMon;

enum FrontierProblem
{
    FRONTIER_PROBLEM_NONE,
    // Smogon rules
    FRONTIER_PROBLEM_SPECIES,     // In a higher tier
    FRONTIER_PROBLEM_SPECIES_GEN, // Not in that generation
    FRONTIER_PROBLEM_MOVE,
    FRONTIER_PROBLEM_MOVE_GEN,
    FRONTIER_PROBLEM_ITEM,
    FRONTIER_PROBLEM_ITEM_GEN,
    FRONTIER_PROBLEM_ABILITY,
    // Every facility
    FRONTIER_PROBLEM_EGG,
    FRONTIER_PROBLEM_FAINTED,
    FRONTIER_PROBLEM_LEGENDARY,
    FRONTIER_PROBLEM_LEVEL,
    FRONTIER_PROBLEM_HELD_ITEM, // The Pyramid takes no items
    FRONTIER_PROBLEM_SAME_SPECIES,
    FRONTIER_PROBLEM_SAME_ITEM,
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
u32 GetFacilityBestStreak(u32 facility, u32 battleMode, u16 rule);
u32 GetFullDexStreak(u32 facility, u32 battleMode, u32 lvlMode, bool32 best);
void RecordFrontierStreak(u32 facility, u32 battleMode, u16 rule, u32 streak);
u32 GetFrontierCurrentStreak(u32 facility, u32 battleMode, u16 rule);
u16 GetActiveFrontierRule(void);
bool32 FrontierUsesSetPools(void);
bool32 IsFrontierSmogonRule(void);
bool32 IsFrontier6v6(void);
u32 GetFrontierTeamSize(void);
u16 GetFrontierSelectedMon(u32 id);
void SetFrontierSelectedMon(u32 id, u16 value);
bool32 IsFrontierItemClauseOn(void);
bool32 IsFrontierSleepClauseOn(void);
u16 *GetFrontierWinStreakPtr(u32 facility, u32 battleMode, u32 lvlMode);
void StartFrontierRuleStreak(u32 facility, u32 battleMode);
void RecordFrontierRuleStreak(u32 facility, u32 battleMode, u32 lvlMode);
void RaiseFrontierBattleLevels(void);
void RestoreFrontierBattleLevels(void);
const struct TrainerMon *GetFrontierMonTable(void);
u16 GetRandomFrontierSetId(void);
u16 GetFrontierBrainSetId(u32 monId);
void CreateFullDexHillMon(struct Pokemon *party, u32 slot, u32 mode, u32 floor, u32 trainerNum, u32 level, u32 otId);
bool32 IsMonLegalForFrontierRule(struct Pokemon *mon, struct FrontierProblemInfo *problem);
bool32 CanMonEnterFrontier(struct Pokemon *mon, u32 lvlMode, struct FrontierProblemInfo *problem);
void SetFrontierRuleForChallenge(void);
void BufferNextIllegalFrontierMon(void);
void BufferNextIneligibleFrontierMon(void);
void ScriptCheckSmogonRulesAllowed(void);
void ScriptIsSmogonRule(void);
void SetFrontierPartySizeVar(void);
void SetDomeRoundPartySize(void);

#endif // GUARD_FRONTIER_RULES_H
