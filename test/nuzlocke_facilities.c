#include "global.h"
#include "test/test.h"
#include "battle.h"
#include "constants/battle.h"
#include "event_data.h"
#include "party_menu.h"
#include "pokemon.h"
#include "script_pokemon_util.h"
#include "load_save.h"

// BPE Nuzlocke: the Frontier, Tents and Trainer Hill never affect the run.

static void SetUpNuzlocke(void)
{
    FlagSet(FLAG_NUZLOCKE);
    FlagSet(FLAG_SYS_POKEDEX_GET);
    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));
    CalculateMonStats(&gParties[B_TRAINER_PLAYER][0]);
    gPartiesCount[B_TRAINER_PLAYER] = 1;
}

static void TearDownNuzlocke(void)
{
    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_SYS_POKEDEX_GET);
    FlagClear(FLAG_NUZLOCKE_DEAD_REPAIRED);
    gBattleTypeFlags = 0;
    ZeroPlayerPartyMons();
}

TEST("Nuzlocke: facility and Trainer Hill battles are exempt, others are not")
{
    gBattleTypeFlags = BATTLE_TYPE_TRAINER;
    EXPECT(!IsNuzlockeExemptBattle());
    gBattleTypeFlags = BATTLE_TYPE_TRAINER | BATTLE_TYPE_BATTLE_TOWER;
    EXPECT(IsNuzlockeExemptBattle());
    gBattleTypeFlags = BATTLE_TYPE_PYRAMID;
    EXPECT(IsNuzlockeExemptBattle());
    gBattleTypeFlags = BATTLE_TYPE_PIKE;
    EXPECT(IsNuzlockeExemptBattle());
    gBattleTypeFlags = BATTLE_TYPE_TRAINER | BATTLE_TYPE_TRAINER_HILL;
    EXPECT(IsNuzlockeExemptBattle());
    gBattleTypeFlags = 0;
}

TEST("Nuzlocke: a Pokémon that fainted in a facility heals, a dead one does not")
{
    u32 hp = 0;
    bool32 dead = TRUE;
    SetUpNuzlocke();

    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP, &hp);
    HealPlayerParty();
    EXPECT_NE(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP), 0);

    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP, &hp);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEAD, &dead);
    HealPlayerParty();
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP), 0);

    TearDownNuzlocke();
}

TEST("Nuzlocke: dead Pokémon can't be chosen for a facility")
{
    u32 hp = 0;
    bool32 dead = TRUE;
    SetUpNuzlocke();
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP, &hp);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEAD, &dead);
    EXPECT(IsMonDeadInNuzlocke(&gParties[B_TRAINER_PLAYER][0]));
    TearDownNuzlocke();
}
