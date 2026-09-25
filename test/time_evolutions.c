#include "global.h"
#include "event_data.h"
#include "overworld.h"
#include "pokemon.h"
#include "rtc.h"
#include "test/test.h"
#include "constants/items.h"

// BPE: the Pocket Watch, and every evolution that depends on the time of day,
// checked at each time the watch can show (Morning, Day, Evening, Night).

struct TimeEvolution
{
    u16 species;
    u8 level;
    u8 friendship;
    u16 heldItem;
    u8 mode;
    u16 param; // item used, or spin for EVO_MODE_OVERWORLD_SPECIAL
    u16 targets[TIMES_OF_DAY_COUNT];
};

#define NIGHT_ONLY(t)     {SPECIES_NONE, SPECIES_NONE, SPECIES_NONE, t}
#define NOT_NIGHT(t)      {t, t, t, SPECIES_NONE}
#define DAY_OR_NIGHT(d, n) {d, d, d, n}

static const struct TimeEvolution sTimeEvolutions[] =
{
    {SPECIES_RATTATA_ALOLA, 20, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_RATICATE_ALOLA)},
    {SPECIES_HAPPINY, 5, 0, ITEM_OVAL_STONE, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_CHANSEY)},
    {SPECIES_HAPPINY, 5, 0, ITEM_NONE, EVO_MODE_ITEM_USE, ITEM_OVAL_STONE, NOT_NIGHT(SPECIES_CHANSEY)},
    {SPECIES_EEVEE, 5, 255, ITEM_NONE, EVO_MODE_NORMAL, 0, DAY_OR_NIGHT(SPECIES_ESPEON, SPECIES_UMBREON)},
    {SPECIES_GLIGAR, 20, 0, ITEM_RAZOR_FANG, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_GLISCOR)},
    {SPECIES_GLIGAR, 20, 0, ITEM_NONE, EVO_MODE_ITEM_USE, ITEM_RAZOR_FANG, NIGHT_ONLY(SPECIES_GLISCOR)},
    {SPECIES_SNEASEL, 20, 0, ITEM_RAZOR_CLAW, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_WEAVILE)},
    {SPECIES_SNEASEL, 20, 0, ITEM_NONE, EVO_MODE_ITEM_USE, ITEM_RAZOR_CLAW, NIGHT_ONLY(SPECIES_WEAVILE)},
    {SPECIES_SNEASEL_HISUI, 20, 0, ITEM_RAZOR_CLAW, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_SNEASLER)},
    {SPECIES_SNEASEL_HISUI, 20, 0, ITEM_NONE, EVO_MODE_ITEM_USE, ITEM_RAZOR_CLAW, NOT_NIGHT(SPECIES_SNEASLER)},
    {SPECIES_URSARING, 40, 0, ITEM_NONE, EVO_MODE_ITEM_USE, ITEM_PEAT_BLOCK, DAY_OR_NIGHT(SPECIES_URSALUNA_BLOODMOON, SPECIES_URSALUNA)},
    {SPECIES_LINOONE_GALAR, 35, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_OBSTAGOON)},
    {SPECIES_BUDEW, 5, 255, ITEM_NONE, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_ROSELIA)},
    {SPECIES_CHINGLING, 5, 255, ITEM_NONE, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_CHIMECHO)},
    {SPECIES_RIOLU, 5, 255, ITEM_NONE, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_LUCARIO)},
    {SPECIES_TYRUNT, 39, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_TYRANTRUM)},
    {SPECIES_AMAURA, 39, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_AURORUS)},
    {SPECIES_YUNGOOS, 20, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_GUMSHOOS)},
    {SPECIES_ROCKRUFF, 25, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, DAY_OR_NIGHT(SPECIES_LYCANROC_MIDDAY, SPECIES_LYCANROC_MIDNIGHT)},
    {SPECIES_ROCKRUFF_OWN_TEMPO, 25, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, {SPECIES_NONE, SPECIES_NONE, SPECIES_LYCANROC_DUSK, SPECIES_NONE}},
    {SPECIES_FOMANTIS, 34, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NOT_NIGHT(SPECIES_LURANTIS)},
    {SPECIES_COSMOEM, 53, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, DAY_OR_NIGHT(SPECIES_SOLGALEO, SPECIES_LUNALA)},
    {SPECIES_SNOM, 5, 255, ITEM_NONE, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_FROSMOTH)},
    {SPECIES_GREAVARD, 30, 0, ITEM_NONE, EVO_MODE_NORMAL, 0, NIGHT_ONLY(SPECIES_HOUNDSTONE)},
    // Alcremie's Day forms need TIME_DAY, which does not include the morning.
    {SPECIES_MILCERY, 5, 0, ITEM_STRAWBERRY_SWEET, EVO_MODE_OVERWORLD_SPECIAL, SPIN_CW_SHORT,
        {SPECIES_NONE, SPECIES_ALCREMIE_STRAWBERRY_VANILLA_CREAM, SPECIES_NONE, SPECIES_ALCREMIE_STRAWBERRY_MATCHA_CREAM}},
    {SPECIES_MILCERY, 5, 0, ITEM_STRAWBERRY_SWEET, EVO_MODE_OVERWORLD_SPECIAL, SPIN_EITHER,
        {SPECIES_NONE, SPECIES_NONE, SPECIES_ALCREMIE_STRAWBERRY_RAINBOW_SWIRL, SPECIES_NONE}},
};

TEST("The Pocket Watch shows each time of day until Real Time is chosen")
{
    u32 time;

    for (time = 0; time < TIMES_OF_DAY_COUNT; time++)
    {
        SetPocketWatchTime(time);
        EXPECT_EQ(GetTimeOfDay(), time);
    }

    // A script override still wins, and clearing it (as every warp does)
    // leaves the watch time in place.
    SetPocketWatchTime(TIME_NIGHT);
    SetTimeOfDay(13);
    EXPECT_EQ(GetTimeOfDay(), TIME_DAY);
    SetTimeOfDay(0);
    EXPECT_EQ(GetTimeOfDay(), TIME_NIGHT);
    EXPECT(FlagGet(FLAG_POCKET_WATCH_SET));

    SetPocketWatchTime(TIMES_OF_DAY_COUNT); // Real Time
    EXPECT(!FlagGet(FLAG_POCKET_WATCH_SET));
    EXPECT(!FlagGet(FLAG_POCKET_WATCH_TIME_LO));
    EXPECT(!FlagGet(FLAG_POCKET_WATCH_TIME_HI));
}

TEST("The night runs past midnight")
{
    SetTimeOfDay(3);
    EXPECT_EQ(GetTimeOfDay(), TIME_NIGHT);
    SetTimeOfDay(0);
}

TEST("Every time-of-day evolution happens at the right time")
{
    u32 i = 0, j, time;
    struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][0];

    for (j = 0; j < ARRAY_COUNT(sTimeEvolutions); j++)
    {
        PARAMETRIZE_LABEL("%S", gSpeciesInfo[sTimeEvolutions[j].species].speciesName) { i = j; }
    }

    ZeroPlayerPartyMons();
    CreateMon(mon, sTimeEvolutions[i].species, sTimeEvolutions[i].level, 0, OTID_STRUCT_PRESET(0));
    SetMonData(mon, MON_DATA_FRIENDSHIP, &sTimeEvolutions[i].friendship);
    SetMonData(mon, MON_DATA_HELD_ITEM, &sTimeEvolutions[i].heldItem);

    for (time = 0; time < TIMES_OF_DAY_COUNT; time++)
    {
        bool32 canStopEvo = TRUE;
        u16 param = sTimeEvolutions[i].param;

        SetPocketWatchTime(time);
        if (sTimeEvolutions[i].mode == EVO_MODE_OVERWORLD_SPECIAL)
        {
            gSpecialVar_0x8000 = param;
            param = 0;
        }
        EXPECT_EQ(GetEvolutionTargetSpecies(mon, sTimeEvolutions[i].mode, param, NULL, &canStopEvo, CHECK_EVO),
                  sTimeEvolutions[i].targets[time]);
    }
    SetPocketWatchTime(TIMES_OF_DAY_COUNT);
    ZeroPlayerPartyMons();
}
