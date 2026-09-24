#include "global.h"
#include "caps.h"
#include "dexnav.h"
#include "event_data.h"
#include "pokemon.h"
#include "randomizer.h"
#include "wild_encounter.h"
#include "test/test.h"
#include "constants/maps.h"
#include "constants/moves.h"

// BPE: DexNav is a Standard mode tool. It uses the randomizer's wild Pokémon, the
// forms the wild form variants pick, and the chain as its search level.

// Exposed by src/dexnav.c for these tests only.
u8 DexNav_Test_GetSearchLevel(enum Species species);
u16 DexNav_Test_GenerateHeldItem(enum Species species, u8 searchLevel);
void DexNav_Test_GenerateMoveset(enum Species species, u8 searchLevel, u8 level, u16 *moves);
u8 DexNav_Test_GenerateMonLevel(enum Species species, enum EncounterType environment);
u32 DexNav_Test_GetListedLandSpecies(enum Species *dst);

static void GoToRoute101(void)
{
    gSaveBlock1Ptr->location.mapGroup = MAP_GROUP(MAP_ROUTE101);
    gSaveBlock1Ptr->location.mapNum = MAP_NUM(MAP_ROUTE101);
}

static const struct WildPokemonInfo *GetRoute101LandMons(void)
{
    u32 headerId = GetCurrentMapWildMonHeaderId();
    return gWildMonHeaders[headerId].encounterTypes[GetTimeOfDayForEncounters(headerId, WILD_AREA_LAND)].landMonsInfo;
}

static void TurnRandomizerOff(void)
{
    VarSet(VAR_RANDOMIZER_SEED_LO, 0);
    VarSet(VAR_RANDOMIZER_SEED_HI, 0);
    VarSet(VAR_RANDOMIZER_OPTIONS_0, 0);
    VarSet(VAR_RANDOMIZER_OPTIONS_1, 0);
    VarSet(VAR_RANDOMIZER_OPTIONS_2, 0);
}

TEST("DexNav comes with the Pokedex in Standard mode only")
{
    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_SYS_POKEDEX_GET);
    EXPECT(!IsDexNavUnlocked());

    FlagSet(FLAG_SYS_POKEDEX_GET);
    EXPECT(IsDexNavUnlocked());

    FlagSet(FLAG_NUZLOCKE);
    EXPECT(!IsDexNavUnlocked());

    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_SYS_POKEDEX_GET);
}

TEST("DexNav can't be used in the Safari Zone")
{
    FlagClear(FLAG_SYS_SAFARI_MODE);
    EXPECT(IsDexNavUsableHere());
    FlagSet(FLAG_SYS_SAFARI_MODE);
    EXPECT(!IsDexNavUsableHere());
    FlagClear(FLAG_SYS_SAFARI_MODE);
}

TEST("A running search is RAM-only state and ending it clears it")
{
    EXPECT_GE(DN_FLAG_SEARCHING, SPECIAL_FLAGS_START);
    FlagSet(DN_FLAG_SEARCHING);
    EndDexNavSearch();
    EXPECT(!FlagGet(DN_FLAG_SEARCHING));
}

TEST("The chain is the search level")
{
    gSaveBlock3Ptr->dexNavChain = 0;
    EXPECT_EQ(DexNav_Test_GetSearchLevel(SPECIES_ZIGZAGOON), 0);
    gSaveBlock3Ptr->dexNavChain = 37;
    EXPECT_EQ(DexNav_Test_GetSearchLevel(SPECIES_ZIGZAGOON), 37);
    gSaveBlock3Ptr->dexNavChain = 0;
}

TEST("DexNav held items never favour the rare item")
{
    enum Species species;
    u32 i, level, common, rare, none;

    for (species = 1; species < NUM_SPECIES; species++)
    {
        if (gSpeciesInfo[species].itemCommon != ITEM_NONE && gSpeciesInfo[species].itemRare != ITEM_NONE
         && gSpeciesInfo[species].itemCommon != gSpeciesInfo[species].itemRare)
            break;
    }
    ASSUME(species < NUM_SPECIES);

    for (level = 0; level <= 100; level += 50)
    {
        common = rare = none = 0;
        for (i = 0; i < 2000; i++)
        {
            u16 item = DexNav_Test_GenerateHeldItem(species, level);
            if (item == gSpeciesInfo[species].itemCommon)
                common++;
            else if (item == gSpeciesInfo[species].itemRare)
                rare++;
            else
                none++;
        }
        EXPECT_LT(rare, common);
        if (level == 0)
        {
            EXPECT_LT(rare, 200);           // about 5%
            EXPECT_GT(none, 700);           // about 45%
        }
        if (level == 100)
            EXPECT_EQ(none, 0);
    }
}

TEST("A DexNav Egg Move is new, and the level-up moves stay")
{
    u16 moves[MAX_MON_MOVES], base[MAX_MON_MOVES];
    const u16 *eggMoves = GetSpeciesEggMoves(SPECIES_BULBASAUR);
    u32 i, j, tries;
    bool32 isEggMove = FALSE;

    CreateWildMonForm(SPECIES_BULBASAUR, 1);
    for (i = 0; i < MAX_MON_MOVES; i++)
        base[i] = GetMonData(&gParties[B_TRAINER_OPPONENT_A][0], MON_DATA_MOVE1 + i);
    ASSUME(base[MAX_MON_MOVES - 1] == MOVE_NONE);

    for (tries = 0; tries < 50 && !isEggMove; tries++)
    {
        DexNav_Test_GenerateMoveset(SPECIES_BULBASAUR, 100, 1, moves);
        for (i = 0; eggMoves[i] != MOVE_UNAVAILABLE; i++)
        {
            if (moves[0] == eggMoves[i])
                isEggMove = TRUE;
        }
    }
    EXPECT(isEggMove);

    // no move twice, and every level-up move still known
    for (i = 0; i < MAX_MON_MOVES; i++)
    {
        for (j = i + 1; j < MAX_MON_MOVES; j++)
        {
            if (moves[i] != MOVE_NONE)
                EXPECT_NE(moves[i], moves[j]);
        }
    }
    for (i = 0; i < MAX_MON_MOVES && base[i] != MOVE_NONE; i++)
    {
        for (j = 0; j < MAX_MON_MOVES && moves[j] != base[i]; j++)
            ;
        EXPECT_LT(j, MAX_MON_MOVES);
    }
}

TEST("DexNav levels grow with the chain but stop at the Level Limiter's cap")
{
    const struct WildPokemonInfo *land;
    enum Species species;
    u32 i, minLevel = MAX_LEVEL, maxLevel = 0;

    GoToRoute101();
    TurnRandomizerOff();
    land = GetRoute101LandMons();
    ASSUME(land != NULL);
    species = land->wildPokemon[0].species;
    for (i = 0; i < LAND_WILD_COUNT; i++)
    {
        if (land->wildPokemon[i].species != species)
            continue;
        minLevel = min(minLevel, land->wildPokemon[i].minLevel);
        maxLevel = max(maxLevel, land->wildPokemon[i].maxLevel);
    }

    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_STANDARD_LEVEL_CAPS);
    gSaveBlock3Ptr->dexNavChain = 100;
    EXPECT_GE(DexNav_Test_GenerateMonLevel(species, ENCOUNTER_TYPE_LAND), minLevel + 20);

    FlagSet(FLAG_STANDARD_LEVEL_CAPS);
    ASSUME(GetCurrentLevelCap() > maxLevel);
    for (i = 0; i < 20; i++)
        EXPECT_LE(DexNav_Test_GenerateMonLevel(species, ENCOUNTER_TYPE_LAND), GetCurrentLevelCap());

    EXPECT_EQ(DexNav_Test_GenerateMonLevel(SPECIES_MEWTWO, ENCOUNTER_TYPE_LAND), MON_LEVEL_NONEXISTENT);

    FlagClear(FLAG_STANDARD_LEVEL_CAPS);
    gSaveBlock3Ptr->dexNavChain = 0;
}

TEST("DexNav lists and finds the randomizer's wild Pokemon")
{
    struct RandomizerSettings settings;
    const struct WildPokemonInfo *land;
    enum Species listed[LAND_WILD_COUNT];
    u32 i, j, count;
    bool32 changed = FALSE;

    GoToRoute101();
    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_FULL);
    settings.seed = 0x1234ABCD;
    Randomizer_SaveSettings(&settings);
    land = GetRoute101LandMons();
    ASSUME(land != NULL);

    count = DexNav_Test_GetListedLandSpecies(listed);
    EXPECT_GT(count, 0);
    for (i = 0; i < LAND_WILD_COUNT; i++)
    {
        enum Species species = GetWildEncounterSpecies(land->wildPokemon[i].species, WILD_AREA_LAND);
        if (species != land->wildPokemon[i].species)
            changed = TRUE;
        // every slot's Pokémon in this game is listed (forms share one entry)
        for (j = 0; j < count && SpeciesToNationalPokedexNum(listed[j]) != SpeciesToNationalPokedexNum(species); j++)
            ;
        EXPECT_LT(j, count);
    }
    EXPECT(changed);

    for (i = 0; i < count; i++)
        EXPECT_NE(DexNav_Test_GenerateMonLevel(listed[i], ENCOUNTER_TYPE_LAND), MON_LEVEL_NONEXISTENT);

    TurnRandomizerOff();
}

TEST("A DexNav Pokemon keeps the form its search showed")
{
    CreateWildMonForm(SPECIES_VIVILLON_POLAR, 10);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][0], MON_DATA_SPECIES), SPECIES_VIVILLON_POLAR);
}
