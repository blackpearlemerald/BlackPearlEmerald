#include "global.h"
#include "battle_setup.h"
#include "event_data.h"
#include "pokedex.h"
#include "pokemon.h"
#include "task.h"
#include "wild_encounter.h"
#include "test/test.h"
#include "constants/region_map_sections.h"

// BPE Nuzlocke dupes clause: a Pokémon whose evolutionary line is already caught can't be
// caught again, and meeting one does not use up the area's encounter.

static void SetUpNuzlocke(void)
{
    FlagSet(FLAG_NUZLOCKE);
    FlagSet(FLAG_SYS_POKEDEX_GET);
    VarSet(VAR_WILD_PKMN_ROUTE_SEEN_0, 0);
    VarSet(VAR_WILD_PKMN_ROUTE_SEEN_1, 0);
    VarSet(VAR_WILD_PKMN_ROUTE_SEEN_2, 0);
    VarSet(VAR_WILD_PKMN_ROUTE_SEEN_3, 0);
    VarSet(VAR_WILD_PKMN_ROUTE_SEEN_4, 0);
    VarSet(VAR_WILD_PKMN_ROUTE_SEEN_5, 0);
}

static void TearDownNuzlocke(void)
{
    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_SYS_POKEDEX_GET);
}

TEST("Nuzlocke: a species already caught is a duplicate and leaves the route's encounter alone")
{
    SetUpNuzlocke();
    GetSetPokedexFlag(SpeciesToNationalPokedexNum(SPECIES_RALTS), FLAG_SET_CAUGHT);

    CreateWildMonForm(SPECIES_RALTS, 5);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_102, TRUE), NUZLOCKE_ENCOUNTER_DUPLICATE);
    EXPECT_EQ(VarGet(VAR_WILD_PKMN_ROUTE_SEEN_0), 0);
    EXPECT_EQ(VarGet(VAR_WILD_PKMN_ROUTE_SEEN_1), 0);

    // the route is still open for a Pokémon that is not a duplicate
    CreateWildMonForm(SPECIES_POOCHYENA, 5);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_102, TRUE), NUZLOCKE_ENCOUNTER_OPEN);
    CreateWildMonForm(SPECIES_POOCHYENA, 5);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_102, TRUE), NUZLOCKE_ENCOUNTER_AREA_USED);

    TearDownNuzlocke();
}

TEST("Nuzlocke: a wild evolution of a caught species is a duplicate too")
{
    SetUpNuzlocke();
    GetSetPokedexFlag(SpeciesToNationalPokedexNum(SPECIES_RALTS), FLAG_SET_CAUGHT);

    CreateWildMonForm(SPECIES_KIRLIA, 20);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_102, FALSE), NUZLOCKE_ENCOUNTER_DUPLICATE);

    TearDownNuzlocke();
}

TEST("Nuzlocke: the dupes clause does not apply outside Nuzlocke mode")
{
    SetUpNuzlocke();
    FlagClear(FLAG_NUZLOCKE);
    GetSetPokedexFlag(SpeciesToNationalPokedexNum(SPECIES_RALTS), FLAG_SET_CAUGHT);

    CreateWildMonForm(SPECIES_RALTS, 5);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_102, TRUE), NUZLOCKE_ENCOUNTER_OPEN);

    TearDownNuzlocke();
}

// A static encounter (legendaries, the Regis, scripted wild battles) never uses the area's
// encounter, so the clause left over from the last wild or trainer battle must not block it.
// Reported on Discord: Zapdos couldn't be caught after a catch in the same area.
TEST("Nuzlocke: static encounters can be caught even after the area's encounter is used")
{
    void (*const starters[])(void) = {
        BattleSetup_StartScriptedWildBattle,
        BattleSetup_StartLegendaryBattle,
        BattleSetup_StartLatiBattle,
        StartRegiBattle,
        StartGroudonKyogreBattle,
    };
    u32 i;

    SetUpNuzlocke();
    CreateWildMonForm(SPECIES_POOCHYENA, 5);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_102, TRUE), NUZLOCKE_ENCOUNTER_OPEN);
    u16 seen = VarGet(VAR_WILD_PKMN_ROUTE_SEEN_0);

    for (i = 0; i < ARRAY_COUNT(starters); i++)
    {
        CreateWildMonForm(SPECIES_REGIROCK, 40);
        gNuzlockeCannotCatch = NUZLOCKE_ENCOUNTER_AREA_USED;
        starters[i]();
        EXPECT_EQ(gNuzlockeCannotCatch, NUZLOCKE_ENCOUNTER_OPEN);
        EXPECT_EQ(VarGet(VAR_WILD_PKMN_ROUTE_SEEN_0), seen);
        ResetTasks();
    }

    TearDownNuzlocke();
}
