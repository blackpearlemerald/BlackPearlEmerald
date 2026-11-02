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
#include "constants/battle_dome.h"
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

// The rule set the current challenge runs under. Every lobby sets it, but only the
// Tower, Factory and Dome have Smogon rules, and only outside Multis and Tents,
// so a rule left in the save can't reach anything that doesn't offer it.
u16 GetActiveFrontierRule(void)
{
    u32 facility = VarGet(VAR_FRONTIER_FACILITY);
    u32 battleMode = VarGet(VAR_FRONTIER_BATTLE_MODE);
    u16 rule = gSaveBlock2Ptr->frontier.activeRule;

    if (facility >= NUM_FRONTIER_FACILITIES)
        return FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0);
    if (FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_SMOGON
     && (gSaveBlock2Ptr->frontier.lvlMode == FRONTIER_LVL_TENT
      || (facility != FRONTIER_FACILITY_TOWER && facility != FRONTIER_FACILITY_FACTORY && facility != FRONTIER_FACILITY_DOME)
      || battleMode > FRONTIER_MODE_DOUBLES))
        return FRONTIER_RULE(FRONTIER_RULES_VANILLA, 0, 0, 0);
    return rule;
}

bool32 FrontierUsesSetPools(void)
{
    return FRONTIER_RULE_KIND(GetActiveFrontierRule()) != FRONTIER_RULES_VANILLA;
}

bool32 IsFrontierSmogonRule(void)
{
    return FRONTIER_RULE_KIND(GetActiveFrontierRule()) == FRONTIER_RULES_SMOGON;
}

bool32 IsFrontier6v6(void)
{
    u16 rule = GetActiveFrontierRule();

    return FRONTIER_RULE_KIND(rule) == FRONTIER_RULES_SMOGON && FRONTIER_RULE_SIZE(rule) == FRONTIER_TEAM_6V6;
}

// How many Pokémon each side brings to the challenge.
u32 GetFrontierTeamSize(void)
{
    u32 battleMode = VarGet(VAR_FRONTIER_BATTLE_MODE);

    if (IsFrontier6v6())
        return PARTY_SIZE;
    if (battleMode == FRONTIER_MODE_MULTIS || battleMode == FRONTIER_MODE_LINK_MULTIS)
        return FRONTIER_MULTI_PARTY_SIZE;
    if (battleMode == FRONTIER_MODE_DOUBLES && VarGet(VAR_FRONTIER_FACILITY) == FRONTIER_FACILITY_TOWER)
        return FRONTIER_DOUBLES_PARTY_SIZE;
    return FRONTIER_PARTY_SIZE;
}

// 6v6 keeps the last two picks in the rule data, since the save's list holds four.
u16 GetFrontierSelectedMon(u32 id)
{
    if (id < MAX_FRONTIER_PARTY_SIZE)
        return gSaveBlock2Ptr->frontier.selectedPartyMons[id];
    return gSaveBlock2Ptr->frontier.ruleData.extraSelectedMons[id - MAX_FRONTIER_PARTY_SIZE];
}

void SetFrontierSelectedMon(u32 id, u16 value)
{
    if (id < MAX_FRONTIER_PARTY_SIZE)
        gSaveBlock2Ptr->frontier.selectedPartyMons[id] = value;
    else
        gSaveBlock2Ptr->frontier.ruleData.extraSelectedMons[id - MAX_FRONTIER_PARTY_SIZE] = value;
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
    u32 slot;

    switch (facility)
    {
    default:
        slot = FULL_DEX_TOWER + battleMode;
        break;
    case FRONTIER_FACILITY_DOME:
        slot = FULL_DEX_DOME + battleMode;
        break;
    case FRONTIER_FACILITY_PALACE:
        slot = FULL_DEX_PALACE + battleMode;
        break;
    case FRONTIER_FACILITY_ARENA:
        slot = FULL_DEX_ARENA;
        break;
    case FRONTIER_FACILITY_FACTORY:
        slot = FULL_DEX_FACTORY + battleMode;
        break;
    case FRONTIER_FACILITY_PIKE:
        slot = FULL_DEX_PIKE;
        break;
    case FRONTIER_FACILITY_PYRAMID:
        slot = FULL_DEX_PYRAMID;
        break;
    }
    // Tents have no streak.
    return gSaveBlock2Ptr->frontier.ruleData.fullDexStreaks[slot][min(lvlMode, FRONTIER_LVL_OPEN)];
}

u32 GetFacilityBestStreak(u32 facility, u32 battleMode, u16 rule)
{
    return GetFrontierBestStreak(GetRuleFacility(facility), battleMode, rule);
}

u32 GetFullDexStreak(u32 facility, u32 battleMode, u32 lvlMode, bool32 best)
{
    return GetFullDexStreakPtr(facility, battleMode, lvlMode)[best != FALSE];
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

    switch (facility)
    {
    case FRONTIER_FACILITY_DOME:
        return &gSaveBlock2Ptr->frontier.domeWinStreaks[battleMode][lvlMode];
    case FRONTIER_FACILITY_PALACE:
        return &gSaveBlock2Ptr->frontier.palaceWinStreaks[battleMode][lvlMode];
    case FRONTIER_FACILITY_ARENA:
        return &gSaveBlock2Ptr->frontier.arenaWinStreaks[lvlMode];
    case FRONTIER_FACILITY_FACTORY:
        return &gSaveBlock2Ptr->frontier.factoryWinStreaks[battleMode][lvlMode];
    case FRONTIER_FACILITY_PIKE:
        return &gSaveBlock2Ptr->frontier.pikeWinStreaks[lvlMode];
    case FRONTIER_FACILITY_PYRAMID:
        return &gSaveBlock2Ptr->frontier.pyramidWinStreaks[lvlMode];
    default:
        return &gSaveBlock2Ptr->frontier.towerWinStreaks[battleMode][lvlMode];
    }
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
    SetFrontierRule(FRONTIER_RULE(gSpecialVar_0x8004, gSpecialVar_0x8005, gSpecialVar_0x8006, gSpecialVar_0x8007));
    // A Tent's level mode left in the save would hide the rule from the checks that follow.
    if (gSaveBlock2Ptr->frontier.lvlMode == FRONTIER_LVL_TENT)
        gSaveBlock2Ptr->frontier.lvlMode = FRONTIER_LVL_50;
}

// The checks one Pokémon must pass on its own to enter. Whether the team repeats
// a species or an item is left to the caller.
bool32 CanMonEnterFrontier(struct Pokemon *mon, u32 lvlMode, struct FrontierProblemInfo *problem)
{
    struct FrontierProblemInfo found = {FRONTIER_PROBLEM_NONE, 0};
    enum Species species = GetMonData(mon, MON_DATA_SPECIES_OR_EGG);
    enum Item item = GetMonData(mon, MON_DATA_HELD_ITEM);

    if (species == SPECIES_EGG)
        found.kind = FRONTIER_PROBLEM_EGG;
    else if (GetMonData(mon, MON_DATA_HP) == 0 && FlagGet(FLAG_NUZLOCKE))
        found.kind = FRONTIER_PROBLEM_FAINTED;
    else if (VarGet(VAR_FRONTIER_FACILITY) == FRONTIER_FACILITY_PYRAMID && item != ITEM_NONE)
        found = (struct FrontierProblemInfo){FRONTIER_PROBLEM_HELD_ITEM, item};
    else if (!IsMonLegalForFrontierRule(mon, &found))
        ;
    else if (gSpeciesInfo[species].isFrontierBanned && !IsFrontierSmogonRule())
        found.kind = FRONTIER_PROBLEM_LEGENDARY;
    else if (lvlMode == FRONTIER_LVL_50 && GetMonData(mon, MON_DATA_LEVEL) > FRONTIER_MAX_LEVEL_50)
        found.kind = FRONTIER_PROBLEM_LEVEL;

    if (problem != NULL)
        *problem = found;
    return found.kind == FRONTIER_PROBLEM_NONE;
}

static const u8 sText_RuleGen[] = _("Gen {STR_VAR_3}");
static const u8 sText_RuleNationalDex[] = _("National Dex");
static const u8 *const sRuleTierNames[FRONTIER_TIER_COUNT] =
{
    [FRONTIER_TIER_ANYTHING_GOES] = COMPOUND_STRING(" AG"),
    [FRONTIER_TIER_UBERS]         = COMPOUND_STRING(" Ubers"),
    [FRONTIER_TIER_OU]            = COMPOUND_STRING(" OU"),
    [FRONTIER_TIER_UU]            = COMPOUND_STRING(" UU"),
    [FRONTIER_TIER_RU]            = COMPOUND_STRING(" RU"),
};

static const u8 *const sProblemTexts[] =
{
    [FRONTIER_PROBLEM_SPECIES]      = COMPOUND_STRING("{STR_VAR_1} is in a higher tier\nthan {STR_VAR_3}."),
    [FRONTIER_PROBLEM_SPECIES_GEN]  = COMPOUND_STRING("{STR_VAR_1} can't be used in\n{STR_VAR_3}."),
    [FRONTIER_PROBLEM_MOVE]         = COMPOUND_STRING("{STR_VAR_1} knows {STR_VAR_2},\nwhich {STR_VAR_3} bans."),
    [FRONTIER_PROBLEM_MOVE_GEN]     = COMPOUND_STRING("{STR_VAR_1} knows {STR_VAR_2},\nwhich isn't in {STR_VAR_3}."),
    [FRONTIER_PROBLEM_ITEM]         = COMPOUND_STRING("{STR_VAR_1} holds {STR_VAR_2},\nwhich {STR_VAR_3} bans."),
    [FRONTIER_PROBLEM_ITEM_GEN]     = COMPOUND_STRING("{STR_VAR_1} holds {STR_VAR_2},\nwhich isn't in {STR_VAR_3}."),
    [FRONTIER_PROBLEM_ABILITY]      = COMPOUND_STRING("{STR_VAR_1} has {STR_VAR_2},\nwhich {STR_VAR_3} bans."),
    [FRONTIER_PROBLEM_EGG]          = COMPOUND_STRING("An EGG can't enter."),
    [FRONTIER_PROBLEM_FAINTED]      = COMPOUND_STRING("{STR_VAR_1} has fainted for good\nand can't enter."),
    [FRONTIER_PROBLEM_LEGENDARY]    = COMPOUND_STRING("{STR_VAR_1} is a legendary\nPOKéMON these rules don't allow."),
    [FRONTIER_PROBLEM_LEVEL]        = COMPOUND_STRING("{STR_VAR_1} is above Level 50."),
    [FRONTIER_PROBLEM_HELD_ITEM]    = COMPOUND_STRING("{STR_VAR_1} holds {STR_VAR_2}.\nNo items may be brought in."),
    [FRONTIER_PROBLEM_SAME_SPECIES] = COMPOUND_STRING("Only one {STR_VAR_2} can enter,\nbut you have more than one."),
    [FRONTIER_PROBLEM_SAME_ITEM]    = COMPOUND_STRING("{STR_VAR_2} is held more than\nonce, but items can't repeat."),
};

// The generation, and the tier for bans: "Gen 4 OU" or "National Dex".
static void BufferRuleName(bool32 withTier)
{
    u16 rule = GetActiveFrontierRule();

    if (FRONTIER_RULE_GEN(rule) == FRONTIER_GEN_NATIONAL_DEX)
    {
        StringCopy(gStringVar4, sText_RuleNationalDex);
    }
    else
    {
        ConvertIntToDecimalStringN(gStringVar3, FRONTIER_RULE_GEN(rule), STR_CONV_MODE_LEFT_ALIGN, 1);
        StringExpandPlaceholders(gStringVar4, sText_RuleGen);
    }
    if (withTier)
        StringAppend(gStringVar4, sRuleTierNames[FRONTIER_RULE_TIER(rule)]);
    StringCopy(gStringVar3, gStringVar4);
}

static void BufferFrontierProblem(struct Pokemon *mon, struct FrontierProblemInfo *problem)
{
    GetMonNickname(mon, gStringVar1);
    switch (problem->kind)
    {
    case FRONTIER_PROBLEM_MOVE:
    case FRONTIER_PROBLEM_MOVE_GEN:
        StringCopy(gStringVar2, GetMoveName(problem->value));
        break;
    case FRONTIER_PROBLEM_ITEM:
    case FRONTIER_PROBLEM_ITEM_GEN:
    case FRONTIER_PROBLEM_HELD_ITEM:
    case FRONTIER_PROBLEM_SAME_ITEM:
        CopyItemName(problem->value, gStringVar2);
        break;
    case FRONTIER_PROBLEM_ABILITY:
        StringCopy(gStringVar2, gAbilitiesInfo[problem->value].name);
        break;
    case FRONTIER_PROBLEM_SAME_SPECIES:
        StringCopy(gStringVar2, GetSpeciesName(problem->value));
        break;
    default:
        break;
    }
    switch (problem->kind)
    {
    case FRONTIER_PROBLEM_SPECIES_GEN:
    case FRONTIER_PROBLEM_MOVE_GEN:
    case FRONTIER_PROBLEM_ITEM_GEN:
        BufferRuleName(FALSE);
        break;
    case FRONTIER_PROBLEM_SPECIES:
    case FRONTIER_PROBLEM_MOVE:
    case FRONTIER_PROBLEM_ITEM:
    case FRONTIER_PROBLEM_ABILITY:
        BufferRuleName(TRUE);
        break;
    default:
        break;
    }
    StringExpandPlaceholders(gStringVar4, sProblemTexts[problem->kind]);
}

// Puts the reason the next party Pokémon breaking the Smogon rules can't enter in
// gStringVar4. VAR_0x8004 is the slot to look from, and VAR_RESULT says whether there was one.
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

        BufferFrontierProblem(mon, &problem);
        gSpecialVar_0x8004 = i + 1;
        gSpecialVar_Result = TRUE;
        return;
    }
    gSpecialVar_Result = FALSE;
}

// What stops this Pokémon from entering, given the ones before it. A repeated species
// or item is only named at its second Pokémon, among those that pass on their own.
static void GetFrontierEntryProblem(u32 slot, u32 lvlMode, struct FrontierProblemInfo *problem)
{
    struct Pokemon *party = gParties[B_TRAINER_PLAYER];
    enum Species species = GetMonData(&party[slot], MON_DATA_SPECIES_OR_EGG);
    enum Item item = GetMonData(&party[slot], MON_DATA_HELD_ITEM);
    u32 i, sameSpecies = 0, sameItem = 0;

    if (!CanMonEnterFrontier(&party[slot], lvlMode, problem))
        return;
    for (i = 0; i < slot; i++)
    {
        if (GetMonData(&party[i], MON_DATA_SPECIES_OR_EGG) == SPECIES_NONE || !CanMonEnterFrontier(&party[i], lvlMode, NULL))
            continue;
        if (GetMonData(&party[i], MON_DATA_SPECIES_OR_EGG) == species)
            sameSpecies++;
        else if (item != ITEM_NONE && GetMonData(&party[i], MON_DATA_HELD_ITEM) == item)
            sameItem++;
    }
    if (sameSpecies == 1)
        *problem = (struct FrontierProblemInfo){FRONTIER_PROBLEM_SAME_SPECIES, species};
    else if (sameSpecies == 0 && sameItem == 1 && IsFrontierItemClauseOn())
        *problem = (struct FrontierProblemInfo){FRONTIER_PROBLEM_SAME_ITEM, item};
}

// The same for every reason a party Pokémon can't enter, after the entry check
// failed. VAR_0x8005 is the level mode.
void BufferNextIneligibleFrontierMon(void)
{
    u32 i;

    for (i = gSpecialVar_0x8004; i < PARTY_SIZE; i++)
    {
        struct FrontierProblemInfo problem;

        if (GetMonData(&gParties[B_TRAINER_PLAYER][i], MON_DATA_SPECIES_OR_EGG) == SPECIES_NONE)
            continue;
        GetFrontierEntryProblem(i, gSpecialVar_0x8005, &problem);
        if (problem.kind == FRONTIER_PROBLEM_NONE)
            continue;

        BufferFrontierProblem(&gParties[B_TRAINER_PLAYER][i], &problem);
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

void SetFrontierPartySizeVar(void)
{
    gSpecialVar_0x8005 = GetFrontierTeamSize();
}

// In 6v6 the player brings everyone, so this only sets their order for the round.
void SetDomeRoundPartySize(void)
{
    gSpecialVar_0x8005 = IsFrontier6v6() ? PARTY_SIZE : DOME_BATTLE_PARTY_SIZE;
}
