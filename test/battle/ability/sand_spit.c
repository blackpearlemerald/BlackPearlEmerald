#include "global.h"
#include "test/battle.h"

SINGLE_BATTLE_TEST("Sand Spit sets up sandstorm for 5 turns when hit")
{
    GIVEN {
        PLAYER(SPECIES_SANDACONDA) { Ability(ABILITY_SAND_SPIT); }
        OPPONENT(SPECIES_LANDORUS);
    } WHEN {
        TURN { MOVE(opponent, MOVE_SCRATCH); }
        TURN {}
        TURN {}
        TURN {}
        TURN {}
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SCRATCH, opponent);
        HP_BAR(player);
        ABILITY_POPUP(player, ABILITY_SAND_SPIT);
        MESSAGE("A sandstorm kicked up!");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm subsided.");
    }
}

SINGLE_BATTLE_TEST("Sand Spit sets up sandstorm for 8 turns when hit with Smooth Rock")
{
    GIVEN {
        ASSUME(gItemsInfo[ITEM_SMOOTH_ROCK].holdEffect == HOLD_EFFECT_SMOOTH_ROCK);
        PLAYER(SPECIES_SANDACONDA) { Ability(ABILITY_SAND_SPIT); Item(ITEM_SMOOTH_ROCK); }
        OPPONENT(SPECIES_LANDORUS);
    } WHEN {
        TURN { MOVE(opponent, MOVE_SCRATCH); }
        TURN {}
        TURN {}
        TURN {}
        TURN {}
        TURN {}
        TURN {}
        TURN {}
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SCRATCH, opponent);
        HP_BAR(player);
        ABILITY_POPUP(player, ABILITY_SAND_SPIT);
        MESSAGE("A sandstorm kicked up!");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm subsided.");
    }
}

SINGLE_BATTLE_TEST("Sand Spit triggers even if the user is knocked out by the hit")
{
    GIVEN {
        PLAYER(SPECIES_SANDACONDA) { Ability(ABILITY_SAND_SPIT); HP(1); }
        PLAYER(SPECIES_LANDORUS);
        OPPONENT(SPECIES_LANDORUS);
    } WHEN {
        TURN { MOVE(opponent, MOVE_SCRATCH); SEND_OUT(player, 1); }
        TURN {}
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SCRATCH, opponent);
        HP_BAR(player);
        ABILITY_POPUP(player, ABILITY_SAND_SPIT);
        MESSAGE("A sandstorm kicked up!");
        MESSAGE("The sandstorm is raging.");
        MESSAGE("The sandstorm is raging.");
    }
}

// BPE: Sand Spit left animArg1 unset, so an earlier stat change's animation id was played
// as a general animation. Reported as a freeze in the first gym (Silicobra).
SINGLE_BATTLE_TEST("Sand Spit plays the sandstorm animation after an earlier stat change")
{
    GIVEN {
        PLAYER(SPECIES_SANDACONDA) { Ability(ABILITY_SAND_SPIT); }
        OPPONENT(SPECIES_LANDORUS);
    } WHEN {
        TURN { MOVE(opponent, MOVE_GROWL); }
        TURN { MOVE(opponent, MOVE_SCRATCH); }
    } SCENE {
        ANIMATION(ANIM_TYPE_MOVE, MOVE_GROWL, opponent);
        ANIMATION(ANIM_TYPE_GENERAL, B_ANIM_STATS_CHANGE, player);
        ANIMATION(ANIM_TYPE_MOVE, MOVE_SCRATCH, opponent);
        ABILITY_POPUP(player, ABILITY_SAND_SPIT);
        MESSAGE("A sandstorm kicked up!");
        ANIMATION(ANIM_TYPE_GENERAL, B_ANIM_SANDSTORM_CONTINUES, player);
        MESSAGE("The sandstorm is raging.");
    }
}
