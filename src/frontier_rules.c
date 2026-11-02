#include "global.h"
#include "battle.h"
#include "event_data.h"
#include "frontier_rules.h"
#include "frontier_sets.h"
#include "item.h"
#include "move.h"
#include "party_menu.h"
#include "pokemon.h"
#include "random.h"
#include "randomizer.h"
#include "string_util.h"
#include "strings.h"
#include "constants/abilities.h"
#include "constants/battle_frontier.h"
#include "constants/items.h"
#include "constants/moves.h"

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

// Every facility mode that can have a Full Dex streak, in save order.
enum
{
    FULL_DEX_TOWER,
    FULL_DEX_DOME = FULL_DEX_TOWER + 4,
    FULL_DEX_PALACE = FULL_DEX_DOME + 2,
    FULL_DEX_ARENA = FULL_DEX_PALACE + 2,
    FULL_DEX_FACTORY,
    FULL_DEX_PIKE = FULL_DEX_FACTORY + 2,
    FULL_DEX_PYRAMID,
};

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

// The rule set the current challenge runs under. Facilities that have no rule menu
// are always vanilla, so a rule left in the save can't reach them.
u16 GetActiveFrontierRule(void)
{
    u32 facility = VarGet(VAR_FRONTIER_FACILITY);

    if (gSaveBlock2Ptr->frontier.lvlMode == FRONTIER_LVL_TENT)
        return FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0);
    if (facility != FRONTIER_FACILITY_TOWER && facility != FRONTIER_FACILITY_FACTORY && facility != FRONTIER_FACILITY_DOME)
        return FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0);
    if (VarGet(VAR_FRONTIER_BATTLE_MODE) > FRONTIER_MODE_DOUBLES)
        return FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0);
    return gSaveBlock2Ptr->frontier.activeRule;
}

bool32 FrontierUsesSetPools(void)
{
    return FRONTIER_RULE_KIND(GetActiveFrontierRule()) != FRONTIER_RULES_VANILLA;
}

bool32 IsFrontierSmogonRule(void)
{
    return FRONTIER_RULE_KIND(GetActiveFrontierRule()) == FRONTIER_RULES_SMOGON;
}

bool32 IsFrontierItemClauseOn(void)
{
    return !IsFrontierSmogonRule();
}

// Anything Goes has no clauses, and banned moves cover OHKO moves and evasion elsewhere.
bool32 IsFrontierSleepClauseOn(void)
{
    u16 rule = GetActiveFrontierRule();

    return (gBattleTypeFlags & BATTLE_TYPE_FRONTIER)
        && FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_SMOGON
        && FRONTIER_RULE_TIER(rule) != FRONTIER_TIER_ANYTHING_GOES;
}

static u32 GetRuleFacility(u32 facility)
{
    if (facility == FRONTIER_FACILITY_DOME)
        return FRONTIER_RULE_DOME;
    if (facility == FRONTIER_FACILITY_FACTORY)
        return FRONTIER_RULE_FACTORY;
    return FRONTIER_RULE_TOWER;
}

static u16 *GetFullDexStreakPtr(u32 facility, u32 battleMode, u32 lvlMode)
{
    u32 slot = FULL_DEX_TOWER + battleMode;

    if (facility == FRONTIER_FACILITY_DOME)
        slot = FULL_DEX_DOME + battleMode;
    else if (facility == FRONTIER_FACILITY_FACTORY)
        slot = FULL_DEX_FACTORY + battleMode;
    return gSaveBlock2Ptr->frontier.ruleData.fullDexStreaks[slot][lvlMode];
}

// Each rule set keeps its own streak, so playing one can't change a vanilla streak.
u16 *GetFrontierWinStreakPtr(u32 facility, u32 battleMode, u32 lvlMode)
{
    switch (FRONTIER_RULE_KIND(GetActiveFrontierRule()))
    {
    case FRONTIER_RULES_SMOGON:
        return &gSaveBlock2Ptr->frontier.ruleData.currentStreak[GetRuleFacility(facility)][battleMode];
    case FRONTIER_RULES_FULL_DEX:
        return GetFullDexStreakPtr(facility, battleMode, lvlMode);
    }

    if (facility == FRONTIER_FACILITY_DOME)
        return &gSaveBlock2Ptr->frontier.domeWinStreaks[battleMode][lvlMode];
    if (facility == FRONTIER_FACILITY_FACTORY)
        return &gSaveBlock2Ptr->frontier.factoryWinStreaks[battleMode][lvlMode];
    return &gSaveBlock2Ptr->frontier.towerWinStreaks[battleMode][lvlMode];
}

// Called when a challenge starts. Picking another Smogon option ends the running streak.
void StartFrontierRuleStreak(u32 facility, u32 battleMode)
{
    struct FrontierRuleData *data = &gSaveBlock2Ptr->frontier.ruleData;
    u16 rule = GetActiveFrontierRule();

    if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_SMOGON && data->currentRule[GetRuleFacility(facility)][battleMode] != rule)
    {
        data->currentRule[GetRuleFacility(facility)][battleMode] = rule;
        data->currentStreak[GetRuleFacility(facility)][battleMode] = 0;
    }
}

void RecordFrontierRuleStreak(u32 facility, u32 battleMode, u32 lvlMode)
{
    u16 rule = GetActiveFrontierRule();
    u16 streak = *GetFrontierWinStreakPtr(facility, battleMode, lvlMode);

    if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_SMOGON)
    {
        RecordFrontierStreak(GetRuleFacility(facility), battleMode, rule, streak);
    }
    else if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_FULL_DEX)
    {
        u16 *streaks = GetFullDexStreakPtr(facility, battleMode, lvlMode);

        if (streak > streaks[1])
            streaks[1] = streak;
    }
}

static void RecalculatePlayerParty(void)
{
    u32 i;

    for (i = 0; i < PARTY_SIZE; i++)
    {
        if (GetMonData(&gParties[B_TRAINER_PLAYER][i], MON_DATA_SPECIES) != SPECIES_NONE)
            CalculateMonStats(&gParties[B_TRAINER_PLAYER][i]);
    }
}

// The raise is only ever in the party in RAM: Exp. doesn't change, the flag isn't
// saved, and nothing saves while a battle runs.
void RaiseFrontierBattleLevels(void)
{
    if (IsFrontierSmogonRule())
    {
        FlagSet(FLAG_FRONTIER_LEVEL_RAISED);
        RecalculatePlayerParty();
    }
}

void RestoreFrontierBattleLevels(void)
{
    if (FlagGet(FLAG_FRONTIER_LEVEL_RAISED))
    {
        FlagClear(FLAG_FRONTIER_LEVEL_RAISED);
        RecalculatePlayerParty();
    }
}

void SetFrontierRuleForChallenge(void)
{
    SetFrontierRule(FRONTIER_RULE(gSpecialVar_0x8004, gSpecialVar_0x8005, gSpecialVar_0x8006, FRONTIER_TEAM_USUAL));
    // A Tent's level mode left in the save would hide the rule from the checks that follow.
    if (gSaveBlock2Ptr->frontier.lvlMode == FRONTIER_LVL_TENT)
        gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_50;
}

static const u8 sText_SpeciesIllegal[] = _("{STR_VAR_1} isn't allowed\nunder these rules.");
static const u8 sText_MoveIllegal[] = _("{STR_VAR_1} knows {STR_VAR_2},\nwhich these rules don't allow.");
static const u8 sText_ItemIllegal[] = _("{STR_VAR_1} holds {STR_VAR_2},\nwhich these rules don't allow.");
static const u8 sText_AbilityIllegal[] = _("{STR_VAR_1} has {STR_VAR_2},\nwhich these rules don't allow.");

// Puts the reason the next illegal party Pokémon can't enter in gStringVar4.
// VAR_0x8004 is the slot to look from, and VAR_RESULT says whether there was one.
void BufferNextIllegalFrontierMon(void)
{
    u32 i;

    for (i = gSpecialVar_0x8004; i < PARTY_SIZE; i++)
    {
        struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][i];
        struct FrontierProblemInfo problem;

        if (GetMonData(mon, MON_DATA_SPECIES_OR_EGG) == SPECIES_NONE || GetMonData(mon, MON_DATA_IS_EGG))
            continue;
        if (IsMonLegalForFrontierRule(mon, &problem))
            continue;

        GetMonNickname(mon, gStringVar1);
        switch (problem.kind)
        {
        default:
            StringExpandPlaceholders(gStringVar4, sText_SpeciesIllegal);
            break;
        case FRONTIER_PROBLEM_MOVE:
            StringCopy(gStringVar2, GetMoveName(problem.value));
            StringExpandPlaceholders(gStringVar4, sText_MoveIllegal);
            break;
        case FRONTIER_PROBLEM_ITEM:
            CopyItemName(problem.value, gStringVar2);
            StringExpandPlaceholders(gStringVar4, sText_ItemIllegal);
            break;
        case FRONTIER_PROBLEM_ABILITY:
            StringCopy(gStringVar2, gAbilitiesInfo[problem.value].name);
            StringExpandPlaceholders(gStringVar4, sText_AbilityIllegal);
            break;
        }
        gSpecialVar_0x8004 = i + 1;
        gSpecialVar_Result = TRUE;
        return;
    }
    gSpecialVar_Result = FALSE;
}

// Tiers assume Pokémon's real stats, types and abilities.
void ScriptCheckSmogonRulesAllowed(void)
{
    gSpecialVar_Result = !Randomizer_IsActive()
                      || !(Randomizer_GetOption(RANDOMIZER_OPTION_ABILITIES)
                        || Randomizer_GetOption(RANDOMIZER_OPTION_TROLL_ABILITIES)
                        || Randomizer_GetOption(RANDOMIZER_OPTION_TYPES)
                        || Randomizer_GetOption(RANDOMIZER_OPTION_BASE_STATS)
                        || Randomizer_GetOption(RANDOMIZER_OPTION_TYPE_CHART)
                        || Randomizer_GetOption(RANDOMIZER_OPTION_MONOTYPE));
}

void ScriptIsSmogonRule(void)
{
    gSpecialVar_0x8006 = IsFrontierSmogonRule();
}
