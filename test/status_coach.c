#include "global.h"
#include "event_data.h"
#include "load_save.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "constants/field_specials.h"
#include "constants/party_menu.h"
#include "test/test.h"

// BPE: the Pokémon Center status coach, the friendship checker beside the Name
// Rater, the Name Rater's PC check and the Candy Jar level repair.

u16 ScriptCoachInflictStatus(void);
u16 ScriptGetPartyMonFriendship(void);
enum Species ScriptGetSelectedMonSpecies(void);

static u32 CoachStatus(enum Species species, u32 coachStatus)
{
    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][0], species, 20, 0, OTID_STRUCT_PRESET(0));
    CalculateMonStats(&gParties[B_TRAINER_PLAYER][0]);
    gPartiesCount[B_TRAINER_PLAYER] = 1;
    gSpecialVar_0x8004 = 0;
    gSpecialVar_0x8005 = coachStatus;
    return ScriptCoachInflictStatus();
}

TEST("The status coach burns and poisons a party Pokemon")
{
    EXPECT_EQ(CoachStatus(SPECIES_ZIGZAGOON, COACH_STATUS_BURN), COACH_RESULT_DONE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_STATUS), STATUS1_BURN);

    EXPECT_EQ(CoachStatus(SPECIES_ZIGZAGOON, COACH_STATUS_POISON), COACH_RESULT_DONE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_STATUS), STATUS1_POISON);

    EXPECT_EQ(CoachStatus(SPECIES_ZIGZAGOON, COACH_STATUS_TOXIC), COACH_RESULT_DONE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_STATUS), STATUS1_TOXIC_POISON);
}

TEST("The status coach refuses what a Flame or Toxic Orb couldn't do")
{
    u32 hp = 0;
    bool32 isEgg = TRUE;

    EXPECT_EQ(CoachStatus(SPECIES_TORCHIC, COACH_STATUS_BURN), COACH_RESULT_IMMUNE);
    EXPECT_EQ(CoachStatus(SPECIES_GRIMER, COACH_STATUS_POISON), COACH_RESULT_IMMUNE);
    EXPECT_EQ(CoachStatus(SPECIES_MAGNEMITE, COACH_STATUS_TOXIC), COACH_RESULT_IMMUNE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_STATUS), STATUS1_NONE);

    // already burned
    EXPECT_EQ(CoachStatus(SPECIES_ZIGZAGOON, COACH_STATUS_BURN), COACH_RESULT_DONE);
    EXPECT_EQ(ScriptCoachInflictStatus(), COACH_RESULT_HAS_STATUS);

    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_ZIGZAGOON, 20, 0, OTID_STRUCT_PRESET(0));
    CalculateMonStats(&gParties[B_TRAINER_PLAYER][0]);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP, &hp);
    EXPECT_EQ(ScriptCoachInflictStatus(), COACH_RESULT_FAINTED);

    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_ZIGZAGOON, 20, 0, OTID_STRUCT_PRESET(0));
    CalculateMonStats(&gParties[B_TRAINER_PLAYER][0]);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_EGG, &isEgg);
    EXPECT_EQ(ScriptCoachInflictStatus(), COACH_RESULT_EGG);
    ZeroPlayerPartyMons();
}

TEST("The friendship checker reads out a Pokemon's friendship")
{
    u32 friendship = 183;

    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][1], SPECIES_EEVEE, 20, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_FRIENDSHIP, &friendship);
    gSpecialVar_0x8004 = 1;
    EXPECT_EQ(ScriptGetPartyMonFriendship(), 183);
    ZeroPlayerPartyMons();
}

TEST("Pokemon chosen from the PC are not taken for Eggs")
{
    struct BoxPokemon boxMon;

    ZeroPlayerPartyMons();
    CreateBoxMon(&boxMon, SPECIES_ZIGZAGOON, 20, 0, OTID_STRUCT_PRESET(0));
    SetBoxMonAt(0, 3, &boxMon);
    gSpecialVar_0x8004 = PC_MON_CHOSEN;
    gSpecialVar_MonBoxId = 0;
    gSpecialVar_MonBoxPos = 3;
    EXPECT_EQ(ScriptGetSelectedMonSpecies(), SPECIES_ZIGZAGOON);
    ZeroBoxMonAt(0, 3);
}

TEST("Loading the party repairs a level left below the Pokemon's Exp")
{
    struct Pokemon mon;
    u32 staleLevel = 8;

    CreateMon(&mon, SPECIES_MUDKIP, 15, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&mon, MON_DATA_LEVEL, &staleLevel);
    SavePlayerPartyMon(0, &mon);
    *GetSavedPlayerPartyCount() = 1;

    LoadPlayerParty();
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 15);
    ZeroPlayerPartyMons();
}
