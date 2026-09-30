#include "global.h"
#include "pokemon.h"
#include "wild_encounter.h"
#include "test/test.h"

// BPE: as in Radical Red, each costumed Pikachu has a second type to match its
// costume and always knows its costume's move from Omega Ruby/Alpha Sapphire.

#if P_COSPLAY_PIKACHU_FORMS
static const struct {
    enum Species species;
    enum Type type;
    enum Move move;
} sCostumes[] = {
    {SPECIES_PIKACHU_ROCK_STAR, TYPE_STEEL,    MOVE_METEOR_MASH},
    {SPECIES_PIKACHU_BELLE,     TYPE_ICE,      MOVE_ICICLE_CRASH},
    {SPECIES_PIKACHU_POP_STAR,  TYPE_FAIRY,    MOVE_DRAINING_KISS},
    {SPECIES_PIKACHU_PHD,       TYPE_PSYCHIC,  MOVE_ELECTRIC_TERRAIN},
    {SPECIES_PIKACHU_LIBRE,     TYPE_FIGHTING, MOVE_FLYING_PRESS},
};

static bool32 KnowsMove(struct Pokemon *mon, enum Move move)
{
    u32 i;

    for (i = 0; i < MAX_MON_MOVES; i++)
    {
        if (GetMonData(mon, MON_DATA_MOVE1 + i) == move)
            return TRUE;
    }
    return FALSE;
}

TEST("Each costumed Pikachu is Electric plus its costume's type")
{
    u32 i;

    for (i = 0; i < ARRAY_COUNT(sCostumes); i++)
    {
        EXPECT_EQ(GetSpeciesType(sCostumes[i].species, 0), TYPE_ELECTRIC);
        EXPECT_EQ(GetSpeciesType(sCostumes[i].species, 1), sCostumes[i].type);
    }
    EXPECT_EQ(GetSpeciesType(SPECIES_PIKACHU_COSPLAY, 0), TYPE_ELECTRIC);
    EXPECT_EQ(GetSpeciesType(SPECIES_PIKACHU_COSPLAY, 1), TYPE_ELECTRIC);
}

TEST("Each costumed Pikachu learns its costume's move at level 1")
{
    u32 i;

    for (i = 0; i < ARRAY_COUNT(sCostumes); i++)
    {
        const struct LevelUpMove *learnset = GetSpeciesLevelUpLearnset(sCostumes[i].species);
        EXPECT_EQ(learnset[0].level, 1);
        EXPECT_EQ(learnset[0].move, sCostumes[i].move);
    }
}

TEST("A wild costumed Pikachu always knows its costume's move")
{
    u32 i, level;
    static const u8 sLevels[] = {5, 30, 60};

    for (i = 0; i < ARRAY_COUNT(sCostumes); i++)
    {
        for (level = 0; level < ARRAY_COUNT(sLevels); level++)
        {
            CreateWildMonForm(sCostumes[i].species, sLevels[level]);
            EXPECT(KnowsMove(&gParties[B_TRAINER_OPPONENT_A][0], sCostumes[i].move));
        }
    }
}

TEST("A wild Pikachu without a costume learns no costume move")
{
    u32 i;

    CreateWildMonForm(SPECIES_PIKACHU, 60);
    for (i = 0; i < ARRAY_COUNT(sCostumes); i++)
        EXPECT(!KnowsMove(&gParties[B_TRAINER_OPPONENT_A][0], sCostumes[i].move));
}
#endif
