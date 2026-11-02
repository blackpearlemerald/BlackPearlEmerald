#include "global.h"
#include "test/battle.h"
#include "frontier_sets.h"

// The menus can't be driven from here, so these run each rule set's strongest sets through
// real battles with the facility AI, to catch sets the battle engine or AI can't handle.
static const struct TrainerMon *GetPoolSet(const struct FrontierSetPool *pool, u32 id)
{
    return &gFrontierSetMons[pool->sets[id % pool->count]];
}

#define SET_OPPONENT(set)                                                                                  \
    OPPONENT((set)->species)                                                                               \
    {                                                                                                      \
        Level(100);                                                                                        \
        Item((set)->heldItem);                                                                             \
        Ability((set)->ability != ABILITY_NONE ? (set)->ability : GetSpeciesAbility((set)->species, 0));   \
        Nature((set)->nature);                                                                             \
        Moves((set)->moves[0], (set)->moves[1], (set)->moves[2], (set)->moves[3]);                         \
    }

AI_SINGLE_BATTLE_TEST("Every singles rule set's strongest sets can battle")
{
    const struct FrontierSetPool *pool = NULL;
    u32 gen, tier, first = 0;

    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (tier = 0; tier < FRONTIER_TIER_COUNT; tier++)
            PARAMETRIZE { pool = &gFrontierSetPools[gen][tier]; }
    }
    for (first = 0; first < 12; first += 3)
        PARAMETRIZE { pool = &gFrontierFullDexPools[0]; }

    GIVEN {
        AI_FLAGS(AI_FLAG_SMART_TRAINER);
        PLAYER(SPECIES_SHUCKLE) { Level(100); HP(9999); MaxHP(9999); Moves(MOVE_CELEBRATE); }
        SET_OPPONENT(GetPoolSet(pool, first));
        SET_OPPONENT(GetPoolSet(pool, first + 1));
        SET_OPPONENT(GetPoolSet(pool, first + 2));
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); }
        TURN { MOVE(player, MOVE_CELEBRATE); }
    }
}

AI_DOUBLE_BATTLE_TEST("Every doubles rule set's strongest sets can battle")
{
    const struct FrontierSetPool *pool = NULL;
    u32 gen, tier;

    for (gen = 0; gen < FRONTIER_GEN_COUNT; gen++)
    {
        for (tier = 0; tier < 3; tier++)
        {
            if (gFrontierSetPools[gen][FRONTIER_POOL_DOUBLES + tier].count != 0)
                PARAMETRIZE { pool = &gFrontierSetPools[gen][FRONTIER_POOL_DOUBLES + tier]; }
        }
    }
    PARAMETRIZE { pool = &gFrontierFullDexPools[1]; }

    GIVEN {
        AI_FLAGS(AI_FLAG_SMART_TRAINER);
        PLAYER(SPECIES_SHUCKLE) { Level(100); HP(9999); MaxHP(9999); Moves(MOVE_CELEBRATE); }
        PLAYER(SPECIES_SHUCKLE) { Level(100); HP(9999); MaxHP(9999); Moves(MOVE_CELEBRATE); }
        SET_OPPONENT(GetPoolSet(pool, 0));
        SET_OPPONENT(GetPoolSet(pool, 1));
        SET_OPPONENT(GetPoolSet(pool, 2));
        SET_OPPONENT(GetPoolSet(pool, 3));
    } WHEN {
        TURN { MOVE(playerLeft, MOVE_CELEBRATE); MOVE(playerRight, MOVE_CELEBRATE); }
        TURN { MOVE(playerLeft, MOVE_CELEBRATE); MOVE(playerRight, MOVE_CELEBRATE); }
    }
}
