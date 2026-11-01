#ifndef GUARD_CONSTANTS_FRONTIER_RULES_H
#define GUARD_CONSTANTS_FRONTIER_RULES_H

// BPE: the rules a battle facility challenge runs under. A rule set is packed into
// a u16, see FRONTIER_RULE().

enum FrontierRuleKind
{
    FRONTIER_RULES_VANILLA,
    FRONTIER_RULES_FULL_DEX,
    FRONTIER_RULES_SMOGON,
};

// Smogon rules choose a generation's limits. Battles always use BPE's mechanics.
#define FRONTIER_GEN_NATIONAL_DEX 0
#define FRONTIER_GEN_COUNT        10 // National Dex, then Gens 1-9

enum FrontierTier
{
    FRONTIER_TIER_ANYTHING_GOES,
    FRONTIER_TIER_UBERS,
    FRONTIER_TIER_OU,
    FRONTIER_TIER_UU,
    FRONTIER_TIER_RU,
    FRONTIER_TIER_COUNT,
};

enum FrontierTeamSize
{
    FRONTIER_TEAM_USUAL, // What the facility normally uses
    FRONTIER_TEAM_6V6,
    FRONTIER_TEAM_SIZE_COUNT,
};

#define FRONTIER_RULE_TOWER    0
#define FRONTIER_RULE_FACTORY  1
#define FRONTIER_RULE_DOME     2
#define FRONTIER_RULE_FACILITY_COUNT 3
#define FRONTIER_RULE_MODE_COUNT     2 // Singles and doubles

#define FRONTIER_RULE(kind, gen, tier, size) ((kind) | ((gen) << 2) | ((tier) << 6) | ((size) << 9))
#define FRONTIER_RULE_KIND(rule) ((rule) & 3)
#define FRONTIER_RULE_GEN(rule)  (((rule) >> 2) & 0xF)
#define FRONTIER_RULE_TIER(rule) (((rule) >> 6) & 7)
#define FRONTIER_RULE_SIZE(rule) (((rule) >> 9) & 1)

#define FRONTIER_BEST_STREAK_MAX 255

#endif // GUARD_CONSTANTS_FRONTIER_RULES_H
