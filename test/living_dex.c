#include "global.h"
#include "event_data.h"
#include "field_specials.h"
#include "pokedex.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "test/test.h"
#include "constants/items.h"

// BPE: the pieces that make a living dex of every form possible. The Mirage
// Island legendaries and the wild form variants offer what the player doesn't
// have; BPETools/audit_living_dex.py checks that every form has a way in.

TEST("Owned species cover the party, the PC and the Day Care, but not eggs")
{
    struct BoxPokemon boxMon;
    u32 owned[OWNED_SPECIES_WORDS];
    bool32 isEgg = TRUE;

    ResetPokemonStorageSystem();
    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_PIKACHU_LIBRE, 5, 0, OTID_STRUCT_PRESET(0));
    CreateBoxMon(&boxMon, SPECIES_ARCEUS_FIRE, 70, 0, OTID_STRUCT_PRESET(0));
    SetBoxMonAt(TOTAL_BOXES_COUNT - 1, IN_BOX_COUNT - 1, &boxMon);
    CreateBoxMon(&gSaveBlock1Ptr->daycare.mons[1].mon, SPECIES_VIVILLON_POLAR, 20, 0, OTID_STRUCT_PRESET(0));
    CreateBoxMon(&boxMon, SPECIES_KYUREM_BLACK, 1, 0, OTID_STRUCT_PRESET(0));
    SetBoxMonData(&boxMon, MON_DATA_IS_EGG, &isEgg);
    SetBoxMonAt(0, 0, &boxMon);

    GetOwnedSpecies(owned);
    EXPECT(IsSpeciesOwned(owned, SPECIES_PIKACHU_LIBRE));
    EXPECT(IsSpeciesOwned(owned, SPECIES_ARCEUS_FIRE));
    EXPECT(IsSpeciesOwned(owned, SPECIES_VIVILLON_POLAR));
    EXPECT(!IsSpeciesOwned(owned, SPECIES_KYUREM_BLACK));
    EXPECT(!IsSpeciesOwned(owned, SPECIES_PIKACHU));
    EXPECT(!IsSpeciesOwned(owned, SPECIES_ARCEUS_NORMAL));
    EXPECT(!IsSpeciesOwned(owned, SPECIES_NONE));

    ZeroBoxMonData(&gSaveBlock1Ptr->daycare.mons[1].mon);
    ZeroPlayerPartyMons();
    ResetPokemonStorageSystem();
}

TEST("A Peat Block evolves Ursaring into both Ursaluna forms")
{
    const struct Evolution *evolutions = GetSpeciesEvolutions(SPECIES_URSARING);
    bool32 ursaluna = FALSE, bloodmoon = FALSE;
    u32 i;

    for (i = 0; evolutions[i].method != EVOLUTIONS_END; i++)
    {
        if (evolutions[i].method != EVO_ITEM || evolutions[i].param != ITEM_PEAT_BLOCK)
            continue;
        if (evolutions[i].targetSpecies == SPECIES_URSALUNA)
            ursaluna = TRUE;
        if (evolutions[i].targetSpecies == SPECIES_URSALUNA_BLOODMOON)
            bloodmoon = TRUE;
    }
    EXPECT(ursaluna);
    EXPECT(bloodmoon);
}

static void AddToPokedex(u16 species)
{
    u32 dexNum = SpeciesToNationalPokedexNum(species);

    GetSetPokedexFlag(dexNum, FLAG_SET_SEEN);
    GetSetPokedexFlag(dexNum, FLAG_SET_CAUGHT);
}

static void CatchOnIsland(u16 species)
{
    AddToPokedex(species);
    VarSet(VAR_ISLAND_LEGENDARY, species);
    RecordIslandLegendaryCatch();
}

static void ClearIslandCatches(void)
{
    u32 flag;

    ResetPokedex();
    for (flag = FLAG_ISLAND_CAUGHT_ARTICUNO_GALAR; flag <= FLAG_ISLAND_CAUGHT_PHIONE; flag++)
        FlagClear(flag);
    VarSet(VAR_ISLAND_LEGENDARY, SPECIES_NONE);
}

TEST("Evolving an island legendary leaves its evolutions on the island")
{
    ClearIslandCatches();
    CatchOnIsland(SPECIES_COSMOG);
    AddToPokedex(SPECIES_COSMOEM);
    AddToPokedex(SPECIES_SOLGALEO);
    CatchOnIsland(SPECIES_POIPOLE);
    AddToPokedex(SPECIES_NAGANADEL);
    CatchOnIsland(SPECIES_KUBFU);
    AddToPokedex(SPECIES_URSHIFU_SINGLE_STRIKE);

    EXPECT(IsIslandLegendaryCaught(SPECIES_COSMOG));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_COSMOEM));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_SOLGALEO));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_LUNALA));
    EXPECT(IsIslandLegendaryCaught(SPECIES_POIPOLE));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_NAGANADEL));
    EXPECT(IsIslandLegendaryCaught(SPECIES_KUBFU));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_URSHIFU_SINGLE_STRIKE));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_URSHIFU_RAPID_STRIKE));

    CatchOnIsland(SPECIES_SOLGALEO);
    CatchOnIsland(SPECIES_URSHIFU_SINGLE_STRIKE);
    EXPECT(IsIslandLegendaryCaught(SPECIES_SOLGALEO));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_LUNALA));
    EXPECT(IsIslandLegendaryCaught(SPECIES_URSHIFU_SINGLE_STRIKE));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_URSHIFU_RAPID_STRIKE));

    ClearIslandCatches();
}

TEST("A Phione hatched from Manaphy leaves Phione on the island")
{
    ClearIslandCatches();
    CatchOnIsland(SPECIES_MANAPHY);
    AddToPokedex(SPECIES_PHIONE);
    EXPECT(IsIslandLegendaryCaught(SPECIES_MANAPHY));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_PHIONE));

    CatchOnIsland(SPECIES_PHIONE);
    EXPECT(IsIslandLegendaryCaught(SPECIES_PHIONE));
    ClearIslandCatches();
}

TEST("Island catches from before the catch flags still count")
{
    ClearIslandCatches();
    AddToPokedex(SPECIES_SOLGALEO);
    AddToPokedex(SPECIES_NAGANADEL);
    AddToPokedex(SPECIES_URSHIFU_SINGLE_STRIKE);
    AddToPokedex(SPECIES_PHIONE);
    AddToPokedex(SPECIES_MEWTWO);

    EXPECT(IsIslandLegendaryCaught(SPECIES_SOLGALEO));
    EXPECT(IsIslandLegendaryCaught(SPECIES_NAGANADEL));
    EXPECT(IsIslandLegendaryCaught(SPECIES_URSHIFU_SINGLE_STRIKE));
    EXPECT(IsIslandLegendaryCaught(SPECIES_PHIONE));
    EXPECT(IsIslandLegendaryCaught(SPECIES_MEWTWO));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_URSHIFU_RAPID_STRIKE));
    EXPECT(!IsIslandLegendaryCaught(SPECIES_LUNALA));
    ClearIslandCatches();
}
