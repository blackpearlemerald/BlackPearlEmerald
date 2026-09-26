#include "global.h"
#include "event_data.h"
#include "field_specials.h"
#include "pokedex.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "string_util.h"
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

// Its own trigger needs the Dusty Bowl arch, which BPE has no map for.
TEST("Galarian Yamask evolves into Runerigus on level-up after losing 49 HP")
{
    struct Pokemon mon;
    bool32 canStopEvo = TRUE;
    u32 hp;

    CreateMon(&mon, SPECIES_YAMASK_GALAR, 34, 0, OTID_STRUCT_PRESET(0));
    EXPECT_EQ(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, &canStopEvo, CHECK_EVO), SPECIES_NONE);

    hp = GetMonData(&mon, MON_DATA_MAX_HP) - 49;
    SetMonData(&mon, MON_DATA_HP, &hp);
    EXPECT_EQ(GetEvolutionTargetSpecies(&mon, EVO_MODE_NORMAL, ITEM_NONE, NULL, &canStopEvo, CHECK_EVO), SPECIES_RUNERIGUS);
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

void ChooseIslandLegendary(void);

// The Altar's unlimited Cosmog evolves into both, so neither is a pool entry.
// Kept in the pool, they turned up again and again for players whose Pokedex
// could not show whether theirs came from the island or from Cosmoem.
TEST("Mirage Island never offers Solgaleo or Lunala")
{
    u32 dexNum, flag;

    ClearIslandCatches();
    for (dexNum = 1; dexNum <= NATIONAL_DEX_COUNT; dexNum++)
    {
        if (dexNum == SpeciesToNationalPokedexNum(SPECIES_SOLGALEO) || dexNum == SpeciesToNationalPokedexNum(SPECIES_LUNALA))
            continue;
        GetSetPokedexFlag(dexNum, FLAG_SET_SEEN);
        GetSetPokedexFlag(dexNum, FLAG_SET_CAUGHT);
    }
    for (flag = FLAG_ISLAND_CAUGHT_ARTICUNO_GALAR; flag <= FLAG_ISLAND_CAUGHT_PHIONE; flag++)
    {
        if (flag != FLAG_ISLAND_CAUGHT_SOLGALEO && flag != FLAG_ISLAND_CAUGHT_LUNALA)
            FlagSet(flag);
    }
    ASSUME(!IsIslandLegendaryCaught(SPECIES_SOLGALEO));
    ASSUME(!IsIslandLegendaryCaught(SPECIES_LUNALA));

    ChooseIslandLegendary();
    EXPECT_EQ(gSpecialVar_Result, SPECIES_NONE);
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

// BPE: the Mirage Altar hands back a legendary the player has already caught,
// so Cosmoem, Naganadel, the two Urshifu and Silvally do not need pool entries
// of their own. See src/field_specials.c.
TEST("The Mirage Altar only offers a legendary the player has caught")
{
    ClearIslandCatches();
    gSpecialVar_0x8004 = SPECIES_KUBFU;
    CheckAltarSpeciesCaught();
    EXPECT(!gSpecialVar_Result);

    AddToPokedex(SPECIES_KUBFU);
    CheckAltarSpeciesCaught();
    EXPECT(gSpecialVar_Result);

    // Its evolutions are not what the altar hands back - Kubfu is.
    gSpecialVar_0x8004 = SPECIES_URSHIFU_SINGLE_STRIKE;
    CheckAltarSpeciesCaught();
    EXPECT(!gSpecialVar_Result);
    ClearIslandCatches();
}

TEST("The Mirage Altar summons the species it was asked for")
{
    struct Pokemon *mon = &gParties[B_TRAINER_OPPONENT_A][0];

    gSpecialVar_0x8004 = SPECIES_COSMOG;
    SetupMirageAltarBattle();
    EXPECT_EQ(GetMonData(mon, MON_DATA_SPECIES), SPECIES_COSMOG);
    EXPECT_EQ(GetMonData(mon, MON_DATA_LEVEL), 70);

    gSpecialVar_0x8004 = SPECIES_TYPE_NULL;
    SetupMirageAltarBattle();
    EXPECT_EQ(GetMonData(mon, MON_DATA_SPECIES), SPECIES_TYPE_NULL);
    ZeroEnemyPartyMons();
}

TEST("The island names an alternate form, which shares its base form's name")
{
    VarSet(VAR_ISLAND_LEGENDARY, SPECIES_ARTICUNO_GALAR);
    BufferIslandLegendaryFormName();
    EXPECT(gSpecialVar_Result);
    EXPECT(StringCompare(gStringVar1, COMPOUND_STRING("Galarian ARTICUNO")) == 0);

    VarSet(VAR_ISLAND_LEGENDARY, SPECIES_CALYREX_SHADOW);
    BufferIslandLegendaryFormName();
    EXPECT(gSpecialVar_Result);

    // A pool member that is the only thing wearing its name says nothing extra.
    VarSet(VAR_ISLAND_LEGENDARY, SPECIES_MEWTWO);
    BufferIslandLegendaryFormName();
    EXPECT(!gSpecialVar_Result);
    VarSet(VAR_ISLAND_LEGENDARY, SPECIES_NONE);
}
