#include "global.h"
#include "item.h"
#include "pokemon.h"
#include "test/test.h"
#include "constants/items.h"

// BPE: Gimmighoul evolves on level up with 999 Gimmighoul Coins in the bag, which it uses up.

TEST("Gimmighoul evolves into Gholdengo with 999 Gimmighoul Coins and uses them up")
{
    u32 i = 0;
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];
    enum Species forms[] = {SPECIES_GIMMIGHOUL_CHEST, SPECIES_GIMMIGHOUL_ROAMING};
    bool32 canStopEvo = TRUE;

    for (u32 j = 0; j < ARRAY_COUNT(forms); j++)
    {
        PARAMETRIZE_LABEL("%S", gSpeciesInfo[forms[j]].speciesName) { i = j; }
    }

    ZeroPlayerPartyMons();
    CreateMon(mon, forms[i], 20, 0, OTID_STRUCT_PRESET(0));

    ASSUME(AddBagItem(ITEM_GIMMIGHOUL_COIN, 998));
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, &canStopEvo, CHECK_EVO), SPECIES_NONE);

    ASSUME(AddBagItem(ITEM_GIMMIGHOUL_COIN, 1));
    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, &canStopEvo, CHECK_EVO), SPECIES_GHOLDENGO);
    EXPECT(CheckBagHasItem(ITEM_GIMMIGHOUL_COIN, 999));

    EXPECT_EQ(GetEvolutionTargetSpecies(mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, &canStopEvo, DO_EVO), SPECIES_GHOLDENGO);
    EXPECT(!CheckBagHasItem(ITEM_GIMMIGHOUL_COIN, 1));
    ZeroPlayerPartyMons();
}
