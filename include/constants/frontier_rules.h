#ifndef GUARD_CONSTANTS_FRONTIER_RULES_H
#define GUARD_CONSTANTS_FRONTIER_RULES_H

// BPE: the rules a battle facility challenge runs under. A rule set is packed into
// a u16, see FRONTIER_RULE().

#define FRONTIER_RULES_VANILLA  0
#define FRONTIER_RULES_FULL_DEX 1
#define FRONTIER_RULES_SMOGON   2

// Smogon rules choose a generation's limits. Battles always use BPE's mechanics.
#define FRONTIER_GEN_NATIONAL_DEX 0
#define FRONTIER_GEN_COUNT        10 // National Dex, then Gens 1-9

#define FRONTIER_TIER_ANYTHING_GOES 0
#define FRONTIER_TIER_UBERS         1
#define FRONTIER_TIER_OU            2
#define FRONTIER_TIER_UU            3
#define FRONTIER_TIER_RU            4
#define FRONTIER_TIER_COUNT         5

#define FRONTIER_TEAM_USUAL      0 // What the facility normally uses
#define FRONTIER_TEAM_6V6        1
#define FRONTIER_TEAM_SIZE_COUNT 2

#define FACTORY_RENTALS_6V6 12 // 6 for the player and 6 for the opponent

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

// For the Ranking Hall's records, see ShowFrontierRuleRecords.
#define FRONTIER_RECORDS_HILL     7
#define FRONTIER_RECORDS_FULL_DEX 0xFF

#endif // GUARD_CONSTANTS_FRONTIER_RULES_H
