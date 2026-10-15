#include "global.h"
#include "test/battle.h"
#include "battle_ai_util.h"

// BPE AI scoring rules restored from 1.0.1. Seismic Toss (damage = level 100) and
// Dragon Rage (40) keep the number of hits the AI expects to take exact.
// Scores are compared with the starting score: Celebrate itself loses 10 for doing nothing.

#define BPE_AI_FLAGS (AI_FLAG_CHECK_BAD_MOVE | AI_FLAG_TRY_TO_FAINT | AI_FLAG_CHECK_VIABILITY | AI_FLAG_OMNISCIENT)

AI_SINGLE_BATTLE_TEST("BPE AI: sets Stealth Rock when the foe cannot set up or KO it quickly")
{
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_STEALTH_ROCK) == EFFECT_STEALTH_ROCK);
        ASSUME(GetMoveEffect(MOVE_DRAGON_RAGE) == EFFECT_FIXED_HP_DAMAGE);
        AI_FLAGS(BPE_AI_FLAGS);
        PLAYER(SPECIES_WOBBUFFET) { Level(100); Moves(MOVE_DRAGON_RAGE, MOVE_CELEBRATE); }
        PLAYER(SPECIES_WYNAUT);
        OPPONENT(SPECIES_WOBBUFFET) { MaxHP(400); HP(400); Moves(MOVE_STEALTH_ROCK, MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); SCORE_GT_VAL(opponent, MOVE_STEALTH_ROCK, AI_SCORE_DEFAULT); }
    }
}

AI_SINGLE_BATTLE_TEST("BPE AI: no hazard bonus against a foe that knows a setup move")
{
    u32 move;
    PARAMETRIZE { move = MOVE_STEALTH_ROCK; }
    PARAMETRIZE { move = MOVE_SPIKES; }
    PARAMETRIZE { move = MOVE_TOXIC_SPIKES; }
    PARAMETRIZE { move = MOVE_STICKY_WEB; }
    GIVEN {
        ASSUME(GetMoveCategory(MOVE_SWORDS_DANCE) == DAMAGE_CATEGORY_STATUS);
        AI_FLAGS(BPE_AI_FLAGS);
        PLAYER(SPECIES_WOBBUFFET) { Level(100); Moves(MOVE_DRAGON_RAGE, MOVE_SWORDS_DANCE, MOVE_CELEBRATE); }
        PLAYER(SPECIES_WYNAUT);
        OPPONENT(SPECIES_WOBBUFFET) { MaxHP(400); HP(400); Moves(move, MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); SCORE_EQ_VAL(opponent, move, AI_SCORE_DEFAULT); }
    }
}

AI_SINGLE_BATTLE_TEST("BPE AI: no hazard bonus when the foe KOs it in two hits")
{
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_SEISMIC_TOSS) == EFFECT_LEVEL_DAMAGE);
        AI_FLAGS(BPE_AI_FLAGS);
        PLAYER(SPECIES_WOBBUFFET) { Level(100); Moves(MOVE_SEISMIC_TOSS, MOVE_CELEBRATE); }
        PLAYER(SPECIES_WYNAUT);
        OPPONENT(SPECIES_WOBBUFFET) { MaxHP(400); HP(200); Moves(MOVE_STEALTH_ROCK, MOVE_CELEBRATE); }
    } WHEN {
        TURN { MOVE(player, MOVE_CELEBRATE); SCORE_EQ_VAL(opponent, MOVE_STEALTH_ROCK, AI_SCORE_DEFAULT); }
    }
}

AI_SINGLE_BATTLE_TEST("BPE AI: no setup bonus, defensive boosts included, when the foe KOs first")
{
    u32 hp;
    PARAMETRIZE { hp = 400; } // 4 hits: safe to set up
    PARAMETRIZE { hp = 100; } // 1 hit while faster: not safe
    GIVEN {
        ASSUME(GetMoveCategory(MOVE_SEISMIC_TOSS) == DAMAGE_CATEGORY_PHYSICAL);
        ASSUME(GetMoveEffect(MOVE_IRON_DEFENSE) == EFFECT_STAT_CHANGE);
        AI_FLAGS(BPE_AI_FLAGS);
        PLAYER(SPECIES_WOBBUFFET) { Level(100); Speed(1); Moves(MOVE_SEISMIC_TOSS, MOVE_CELEBRATE); }
        OPPONENT(SPECIES_WOBBUFFET) { MaxHP(400); HP(hp); Speed(100); Moves(MOVE_IRON_DEFENSE, MOVE_CELEBRATE); }
    } WHEN {
        if (hp == 400)
            TURN { MOVE(player, MOVE_CELEBRATE); SCORE_GT_VAL(opponent, MOVE_IRON_DEFENSE, AI_SCORE_DEFAULT); }
        else
            TURN { MOVE(player, MOVE_CELEBRATE); SCORE_EQ_VAL(opponent, MOVE_IRON_DEFENSE, AI_SCORE_DEFAULT); }
    }
}

AI_SINGLE_BATTLE_TEST("BPE AI: Substitute only when the foe needs five or more hits")
{
    u32 move;
    PARAMETRIZE { move = MOVE_DRAGON_RAGE; }  // 10 hits from full HP
    PARAMETRIZE { move = MOVE_SEISMIC_TOSS; } // 4 hits from full HP
    GIVEN {
        ASSUME(GetMoveEffect(MOVE_SUBSTITUTE) == EFFECT_SUBSTITUTE);
        AI_FLAGS(BPE_AI_FLAGS);
        PLAYER(SPECIES_WOBBUFFET) { Level(100); Moves(move, MOVE_CELEBRATE); }
        OPPONENT(SPECIES_WOBBUFFET) { MaxHP(400); HP(400); Moves(MOVE_SUBSTITUTE, MOVE_CELEBRATE); }
    } WHEN {
        if (move == MOVE_DRAGON_RAGE)
            TURN { MOVE(player, MOVE_CELEBRATE); SCORE_GT_VAL(opponent, MOVE_SUBSTITUTE, AI_SCORE_DEFAULT); }
        else
            TURN { MOVE(player, MOVE_CELEBRATE); SCORE_LT_VAL(opponent, MOVE_SUBSTITUTE, AI_SCORE_DEFAULT); }
    }
}
