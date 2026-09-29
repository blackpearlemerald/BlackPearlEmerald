#include "global.h"
#include "event_data.h"
#include "pokemon.h"
#include "ui_stat_editor.h"
#include "test/test.h"

// BPE: the Stat Editor lets Standard games change EVs, IVs, nature and ability.
// Nuzlocke games can only look.

static void SetEVs(struct Pokemon *mon, u32 hp, u32 atk, u32 def, u32 speed, u32 spAtk, u32 spDef)
{
    SetMonData(mon, MON_DATA_HP_EV, &hp);
    SetMonData(mon, MON_DATA_ATK_EV, &atk);
    SetMonData(mon, MON_DATA_DEF_EV, &def);
    SetMonData(mon, MON_DATA_SPEED_EV, &speed);
    SetMonData(mon, MON_DATA_SPATK_EV, &spAtk);
    SetMonData(mon, MON_DATA_SPDEF_EV, &spDef);
}

TEST("The Stat Editor can edit in Standard games but not in Nuzlocke games or on Eggs")
{
    struct Pokemon mon;
    bool32 isEgg = TRUE;

    CreateMon(&mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));

    FlagClear(FLAG_NUZLOCKE);
    EXPECT(StatEditor_CanEditMon(&mon));

    FlagSet(FLAG_NUZLOCKE);
    EXPECT(!StatEditor_CanEditMon(&mon));
    FlagClear(FLAG_NUZLOCKE);

    SetMonData(&mon, MON_DATA_IS_EGG, &isEgg);
    EXPECT(!StatEditor_CanEditMon(&mon));
}

TEST("The Stat Editor keeps EVs within 252 per stat and 510 in total")
{
    struct Pokemon mon;

    FlagClear(FLAG_NUZLOCKE);
    CreateMon(&mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));

    SetEVs(&mon, 0, 0, 0, 0, 0, 0);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_HP_EV), MAX_PER_STAT_EVS);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_SPDEF_EV), MAX_PER_STAT_EVS);

    SetEVs(&mon, 252, 200, 0, 0, 0, 0);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_DEF_EV), MAX_TOTAL_EVS - 452);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_ATK_EV), MAX_PER_STAT_EVS);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_HP_EV), MAX_PER_STAT_EVS);

    SetEVs(&mon, 252, 252, 6, 0, 0, 0);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_SPEED_EV), 0);
}

TEST("The Stat Editor keeps IVs within 31")
{
    struct Pokemon mon;

    CreateMon(&mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_HP_IV), MAX_PER_STAT_IVS);
    EXPECT_EQ(StatEditor_GetStatMax(&mon, MON_DATA_SPDEF_IV), MAX_PER_STAT_IVS);
}

TEST("The Stat Editor cycles through each different ability, Hidden Ability included")
{
    struct Pokemon mon;
    u32 abilityNum = 0;

    CreateMon(&mon, SPECIES_RATTATA, 50, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&mon, MON_DATA_ABILITY_NUM, &abilityNum);
    EXPECT_EQ(StatEditor_GetNextAbilityNum(&mon, 1), 1);
    EXPECT_EQ(StatEditor_GetNextAbilityNum(&mon, -1), 2);

    abilityNum = 2;
    SetMonData(&mon, MON_DATA_ABILITY_NUM, &abilityNum);
    EXPECT_EQ(StatEditor_GetNextAbilityNum(&mon, 1), 0);
}

TEST("The Stat Editor skips empty ability slots")
{
    struct Pokemon mon;
    u32 abilityNum = 0;

    // Overgrow, no second ability, Chlorophyll.
    CreateMon(&mon, SPECIES_BULBASAUR, 50, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&mon, MON_DATA_ABILITY_NUM, &abilityNum);
    EXPECT_EQ(StatEditor_GetNextAbilityNum(&mon, 1), 2);
    EXPECT_EQ(StatEditor_GetNextAbilityNum(&mon, -1), 2);

    abilityNum = 2;
    SetMonData(&mon, MON_DATA_ABILITY_NUM, &abilityNum);
    EXPECT_EQ(StatEditor_GetNextAbilityNum(&mon, 1), 0);
}

TEST("The Stat Editor changes the nature the stats use, as a Mint does")
{
    struct Pokemon mon;
    u32 nature = NATURE_ADAMANT;
    u32 attackBefore;

    CreateMon(&mon, SPECIES_WOBBUFFET, 50, NATURE_MODEST, OTID_STRUCT_PRESET(0));
    CalculateMonStats(&mon);
    attackBefore = GetMonData(&mon, MON_DATA_ATK);

    SetMonData(&mon, MON_DATA_HIDDEN_NATURE, &nature);
    CalculateMonStats(&mon);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HIDDEN_NATURE), NATURE_ADAMANT);
    EXPECT_EQ(GetNature(&mon), NATURE_MODEST);
    EXPECT_GT(GetMonData(&mon, MON_DATA_ATK), attackBefore);
}
