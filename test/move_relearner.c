#include "global.h"
#include "pokemon.h"
#include "test/test.h"
#include "constants/move_relearner.h"

// BPE: the Pokémon Center relearner (level-up moves) also teaches moves only a
// pre-evolution learns, and the Egg Move Tutor teaches Volt Tackle to the
// Pikachu line.

u32 MoveRelearner_Test_GetMoves(struct BoxPokemon *mon, enum MoveRelearnerStates state, u16 *moves);

static bool32 ListHasMove(enum Species species, u32 level, enum MoveRelearnerStates state, enum Move move)
{
    u16 moves[MAX_RELEARNER_MOVES];
    u32 i, count;

    CreateMon(&gParties[B_TRAINER_PLAYER][0], species, level, 0, OTID_STRUCT_PRESET(0));
    count = MoveRelearner_Test_GetMoves(&gParties[B_TRAINER_PLAYER][0].box, state, moves);
    for (i = 0; i < count; i++)
    {
        if (moves[i] == move)
            return TRUE;
    }
    return FALSE;
}

TEST("The level-up relearner offers moves only a pre-evolution learns")
{
    // Slakoth learns Slack Off at 9; Vigoroth never does.
    EXPECT(ListHasMove(SPECIES_VIGOROTH, 20, MOVE_RELEARNER_LEVEL_UP_MOVES, MOVE_SLACK_OFF));
    // A pre-evolution's move still waits for its level.
    EXPECT(!ListHasMove(SPECIES_VIGOROTH, 5, MOVE_RELEARNER_LEVEL_UP_MOVES, MOVE_SLACK_OFF));
}

TEST("The Egg Move Tutor teaches Volt Tackle to the Pikachu line")
{
    EXPECT(ListHasMove(SPECIES_PICHU, 5, MOVE_RELEARNER_EGG_MOVES, MOVE_VOLT_TACKLE));
    EXPECT(ListHasMove(SPECIES_PIKACHU, 20, MOVE_RELEARNER_EGG_MOVES, MOVE_VOLT_TACKLE));
    EXPECT(ListHasMove(SPECIES_RAICHU, 40, MOVE_RELEARNER_EGG_MOVES, MOVE_VOLT_TACKLE));
}

TEST("Relearner move lists fit the relearner menu")
{
    u32 species = 0, j;
    u16 moves[MAX_RELEARNER_MOVES];

    for (j = 1; j < NUM_SPECIES; j++)
    {
        if (IsSpeciesEnabled(j))
            PARAMETRIZE { species = j; }
    }
    CreateMon(&gParties[B_TRAINER_PLAYER][0], species, MAX_LEVEL, 0, OTID_STRUCT_PRESET(0));
    EXPECT_LE(MoveRelearner_Test_GetMoves(&gParties[B_TRAINER_PLAYER][0].box, MOVE_RELEARNER_LEVEL_UP_MOVES, moves), MAX_RELEARNER_MOVES - 1);
    EXPECT_LE(MoveRelearner_Test_GetMoves(&gParties[B_TRAINER_PLAYER][0].box, MOVE_RELEARNER_EGG_MOVES, moves), MAX_RELEARNER_MOVES - 1);
}
