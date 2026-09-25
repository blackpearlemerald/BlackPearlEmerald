#include "global.h"
#include "battle.h"
#include "battle_setup.h"
#include "caps.h"
#include "data.h"
#include "egg_hatch.h"
#include "event_data.h"
#include "new_game.h"
#include "item.h"
#include "party_menu.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "test/overworld_script.h"
#include "test/test.h"
#include "constants/characters.h"
#include "constants/daycare.h"
#include "constants/move_relearner.h"

TEST("Candy Jar raises a Pokemon to each badge-based level cap")
{
    static const u16 sProgressFlags[] = {
        FLAG_BADGE01_GET,
        FLAG_BADGE02_GET,
        FLAG_BADGE03_GET,
        FLAG_BADGE04_GET,
        FLAG_BADGE05_GET,
        FLAG_BADGE06_GET,
        FLAG_BADGE07_GET,
        FLAG_BADGE08_GET,
        FLAG_IS_CHAMPION,
    };
    static const u8 sExpectedCaps[] = {15, 24, 33, 42, 51, 60, 69, 78, 90, 100};
    struct Pokemon mon;

    for (u32 i = 0; i < ARRAY_COUNT(sProgressFlags); i++)
        FlagClear(sProgressFlags[i]);

    CreateMon(&mon, SPECIES_WOBBUFFET, 5, 0, OTID_STRUCT_PRESET(0));

    for (u32 i = 0; i < ARRAY_COUNT(sExpectedCaps); i++)
    {
        enum GrowthRate growthRate = gSpeciesInfo[SPECIES_WOBBUFFET].growthRate;

        EXPECT_EQ(GetProgressLevelCap(), sExpectedCaps[i]);
        EXPECT(!PokemonUseItemEffects(&mon, ITEM_CANDY_JAR, 0, 0, FALSE));
        EXPECT_EQ(GetMonData(&mon, MON_DATA_LEVEL), sExpectedCaps[i]);
        EXPECT_EQ(GetMonData(&mon, MON_DATA_EXP), gExperienceTables[growthRate][sExpectedCaps[i]]);

        if (i < ARRAY_COUNT(sProgressFlags))
            FlagSet(sProgressFlags[i]);
    }
}

// BPE: level caps are enforced in Nuzlocke mode only; Standard mode plays uncapped.
TEST("Level caps apply only in Nuzlocke mode")
{
    static const u16 sProgressFlags[] = {
        FLAG_BADGE01_GET,
        FLAG_BADGE02_GET,
        FLAG_BADGE03_GET,
        FLAG_BADGE04_GET,
        FLAG_BADGE05_GET,
        FLAG_BADGE06_GET,
        FLAG_BADGE07_GET,
        FLAG_BADGE08_GET,
        FLAG_IS_CHAMPION,
    };
    struct Pokemon standardMon, nuzlockeMon;
    u32 exp = gExperienceTables[gSpeciesInfo[SPECIES_WOBBUFFET].growthRate][16];

    for (u32 i = 0; i < ARRAY_COUNT(sProgressFlags); i++)
        FlagClear(sProgressFlags[i]);

    CreateMon(&standardMon, SPECIES_WOBBUFFET, 15, 0, OTID_STRUCT_PRESET(0));
    CreateMon(&nuzlockeMon, SPECIES_WOBBUFFET, 15, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&standardMon, MON_DATA_EXP, &exp);
    SetMonData(&nuzlockeMon, MON_DATA_EXP, &exp);

    // Standard mode: no badge cap is enforced and experience is not withheld.
    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_STANDARD_LEVEL_CAPS);
    EXPECT_EQ(GetProgressLevelCap(), 15);
    EXPECT_EQ(GetCurrentLevelCap(), MAX_LEVEL);
    EXPECT_EQ(GetSoftLevelCapExpValue(20, 1000), 1000);
    EXPECT(TryIncrementMonLevel(&standardMon));
    EXPECT_EQ(GetMonData(&standardMon, MON_DATA_LEVEL), 16);

    // Nuzlocke mode: the badge cap still stops levels and experience.
    FlagSet(FLAG_NUZLOCKE);
    EXPECT_EQ(GetCurrentLevelCap(), 15);
    EXPECT_EQ(GetSoftLevelCapExpValue(20, 1000), 0);
    EXPECT(!TryIncrementMonLevel(&nuzlockeMon));
    EXPECT_EQ(GetMonData(&nuzlockeMon, MON_DATA_LEVEL), 15);

    // Standard mode with the Level Limiter switched on follows the badge cap too.
    FlagClear(FLAG_NUZLOCKE);
    FlagSet(FLAG_STANDARD_LEVEL_CAPS);
    EXPECT_EQ(GetCurrentLevelCap(), 15);
    EXPECT_EQ(GetSoftLevelCapExpValue(20, 1000), 0);
    EXPECT(!TryIncrementMonLevel(&nuzlockeMon));

    FlagClear(FLAG_STANDARD_LEVEL_CAPS);
}

// BPE: Nuzlocke mode uses each trainer's Level, Standard mode its Standard Level.
TEST("Trainer parties use Standard Level outside Nuzlocke mode")
{
    // The test build replaces the shipped trainer table, so describe one here.
    static const struct TrainerMon sParty[] =
    {
        {
            .species = SPECIES_WOBBUFFET,
            .lvl = 40,
            .standardLvl = 25,
            .iv = TRAINER_PARTY_IVS(0, 0, 0, 0, 0, 0),
        },
    };
    static const struct Trainer sTrainer =
    {
        .party = sParty,
        .partySize = ARRAY_COUNT(sParty),
        .battleType = TRAINER_BATTLE_TYPE_SINGLES,
    };
    struct Pokemon party[PARTY_SIZE];

    FlagClear(FLAG_NUZLOCKE);
    CreateNPCTrainerPartyFromTrainer(party, &sTrainer, FALSE, BATTLE_TYPE_TRAINER);
    EXPECT_EQ(GetMonData(&party[0], MON_DATA_LEVEL), sParty[0].standardLvl);

    FlagSet(FLAG_NUZLOCKE);
    CreateNPCTrainerPartyFromTrainer(party, &sTrainer, FALSE, BATTLE_TYPE_TRAINER);
    EXPECT_EQ(GetMonData(&party[0], MON_DATA_LEVEL), sParty[0].lvl);

    FlagClear(FLAG_NUZLOCKE);
}

// BPE: an HM in the bag lets a Pokemon use its field move only if it could learn it.
TEST("Bag HMs need a party Pokemon that could learn them")
{
    ZeroPlayerPartyMons();
    FlagClear(FLAG_NUZLOCKE);
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_CHARIZARD, 50;
        givemon SPECIES_BLASTOISE, 50;
    );

    // Neither knows these moves; only compatibility counts.
    EXPECT(CanMonUseBagFieldMove(&gParties[B_TRAINER_PLAYER][0], MOVE_FLY));
    EXPECT(!CanMonUseBagFieldMove(&gParties[B_TRAINER_PLAYER][0], MOVE_SURF));
    EXPECT(CanMonUseBagFieldMove(&gParties[B_TRAINER_PLAYER][1], MOVE_SURF));
    EXPECT(!CanMonUseBagFieldMove(&gParties[B_TRAINER_PLAYER][1], MOVE_FLY));

    // The Pokemon used is one that could learn the move, not simply the lead.
    EXPECT_EQ(GetBagFieldMoveUser(MOVE_SURF), 1);
    EXPECT_EQ(GetBagFieldMoveUser(MOVE_CUT), 0);
    EXPECT_EQ(GetBagFieldMoveUser(MOVE_FLASH), PARTY_SIZE);

    // With the HMs in the bag, Surf works through Blastoise and Flash through nobody.
    AddBagItem(ITEM_HM_SURF, 1);
    AddBagItem(ITEM_HM_FLASH, 1);
    EXPECT(PlayerHasMove(MOVE_SURF));
    EXPECT(!PlayerHasMove(MOVE_FLASH));
    RemoveBagItem(ITEM_HM_SURF, 1);
    RemoveBagItem(ITEM_HM_FLASH, 1);
}

TEST("Nature independent from Hidden Nature")
{
    u32 i, j, nature = 0, hiddenNature = 0;
    struct Pokemon mon;
    for (i = 0; i < NUM_NATURES; i++)
    {
        for (j = 0; j < NUM_NATURES; j++)
        {
            PARAMETRIZE { nature = i; hiddenNature = j; }
        }
    }
    u32 species = SPECIES_WOBBUFFET;
    u32 personality = GetMonPersonality(species, MON_GENDER_RANDOM, nature, RANDOM_UNOWN_LETTER);
    CreateMon(&mon, species, 100, personality, OTID_STRUCT_PLAYER_ID);
    SetMonData(&mon, MON_DATA_HIDDEN_NATURE, &hiddenNature);
    EXPECT_EQ(GetNature(&mon), nature);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HIDDEN_NATURE), hiddenNature);
}

TEST("Terastallization type defaults to primary or secondary type")
{
    u32 i;
    enum Type teraType;
    struct Pokemon mon;
    for (i = 0; i < 128; i++) PARAMETRIZE {}
    CreateRandomMonWithIVs(&mon, SPECIES_PIDGEY, 100, 0);
    teraType = GetMonData(&mon, MON_DATA_TERA_TYPE);
    EXPECT(teraType == GetSpeciesType(SPECIES_PIDGEY, 0)
        || teraType == GetSpeciesType(SPECIES_PIDGEY, 1));
}

TEST("Terastallization type can be set to any type except TYPE_NONE")
{
    u32 i;
    enum Type teraType;
    struct Pokemon mon;
    for (i = 1; i < NUMBER_OF_MON_TYPES; i++)
    {
        PARAMETRIZE { teraType = i; }
    }
    CreateRandomMonWithIVs(&mon, SPECIES_WOBBUFFET, 100, 0);
    SetMonData(&mon, MON_DATA_TERA_TYPE, &teraType);
    EXPECT_EQ(teraType, GetMonData(&mon, MON_DATA_TERA_TYPE));
}

TEST("Terastallization type is reset to the default types when setting Tera Type back to TYPE_NONE")
{
    u32 i;
    enum Type teraType, typeNone;
    struct Pokemon mon;
    for (i = 1; i < NUMBER_OF_MON_TYPES; i++)
    {
        PARAMETRIZE { teraType = i; typeNone = TYPE_NONE; }
    }
    CreateRandomMonWithIVs(&mon, SPECIES_PIDGEY, 100, 0);
    SetMonData(&mon, MON_DATA_TERA_TYPE, &teraType);
    EXPECT_EQ(teraType, GetMonData(&mon, MON_DATA_TERA_TYPE));
    if (typeNone == TYPE_NONE)
        typeNone = GetTeraTypeFromPersonality(&mon);
    SetMonData(&mon, MON_DATA_TERA_TYPE, &typeNone);
    typeNone = GetMonData(&mon, MON_DATA_TERA_TYPE);
    EXPECT(typeNone == GetSpeciesType(SPECIES_PIDGEY, 0)
        || typeNone == GetSpeciesType(SPECIES_PIDGEY, 1));
}

TEST("Shininess independent from PID and OTID")
{
    u32 pid, otId, data;
    bool32 isShiny;
    struct Pokemon mon;
    PARAMETRIZE { pid = 0; otId = 0; }
    CreateMon(&mon, SPECIES_WOBBUFFET, 100, pid, OTID_STRUCT_PRESET(otId));
    isShiny = IsMonShiny(&mon);
    data = !isShiny;
    SetMonData(&mon, MON_DATA_IS_SHINY, &data);
    EXPECT_EQ(pid, GetMonData(&mon, MON_DATA_PERSONALITY));
    EXPECT_EQ(otId, GetMonData(&mon, MON_DATA_OT_ID));
    EXPECT_EQ(!isShiny, GetMonData(&mon, MON_DATA_IS_SHINY));
}

TEST("Shininess set on an Egg persists after hatching")
{
    u32 personality = SHINY_ODDS;
    u32 trainerId = 0;
    bool32 isShiny = TRUE;
    bool8 isEgg = TRUE;

    SetTrainerId(trainerId, gSaveBlock2Ptr->playerTrainerId);
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_TOGEPI, EGG_HATCH_LEVEL, personality, OTID_STRUCT_PLAYER_ID);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_EGG, &isEgg);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_SHINY, &isShiny);

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_SHINY), TRUE);

    gSpecialVar_0x8004 = 0;
    ScriptHatchMon();

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_EGG), FALSE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_SHINY), TRUE);
}

TEST("Hyper Training increases stats without affecting IVs")
{
    u32 data, hp, atk, def, speed, spatk, spdef, friendship = 0;
    struct Pokemon mon;
    CreateMonWithIVs(&mon, SPECIES_WOBBUFFET, 100, 0, OTID_STRUCT_PRESET(0), 3);
    // Consider B_FRIENDSHIP_BOOST.
    SetMonData(&mon, MON_DATA_FRIENDSHIP, &friendship);
    CalculateMonStats(&mon);

    hp = GetMonData(&mon, MON_DATA_HP);
    atk = GetMonData(&mon, MON_DATA_ATK);
    def = GetMonData(&mon, MON_DATA_DEF);
    speed = GetMonData(&mon, MON_DATA_SPEED);
    spatk = GetMonData(&mon, MON_DATA_SPATK);
    spdef = GetMonData(&mon, MON_DATA_SPDEF);

    data = TRUE;
    SetMonData(&mon, MON_DATA_HYPER_TRAINED_HP, &data);
    SetMonData(&mon, MON_DATA_HYPER_TRAINED_ATK, &data);
    SetMonData(&mon, MON_DATA_HYPER_TRAINED_DEF, &data);
    SetMonData(&mon, MON_DATA_HYPER_TRAINED_SPEED, &data);
    SetMonData(&mon, MON_DATA_HYPER_TRAINED_SPATK, &data);
    SetMonData(&mon, MON_DATA_HYPER_TRAINED_SPDEF, &data);
    CalculateMonStats(&mon);

    EXPECT_EQ(GetMonData(&mon, MON_DATA_HP_IV), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_ATK_IV), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_DEF_IV), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPEED_IV), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPATK_IV), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPDEF_IV), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPEED_IV), 3);

    EXPECT_EQ(hp - 3 + MAX_PER_STAT_IVS, GetMonData(&mon, MON_DATA_HP));
    EXPECT_EQ(atk - 3 + MAX_PER_STAT_IVS, GetMonData(&mon, MON_DATA_ATK));
    EXPECT_EQ(def - 3 + MAX_PER_STAT_IVS, GetMonData(&mon, MON_DATA_DEF));
    EXPECT_EQ(speed - 3 + MAX_PER_STAT_IVS, GetMonData(&mon, MON_DATA_SPEED));
    EXPECT_EQ(spatk - 3 + MAX_PER_STAT_IVS, GetMonData(&mon, MON_DATA_SPATK));
    EXPECT_EQ(spdef - 3 + MAX_PER_STAT_IVS, GetMonData(&mon, MON_DATA_SPDEF));
}

TEST("Status1 round-trips through BoxPokemon")
{
    u32 status1;
    struct Pokemon mon1, mon2;
    PARAMETRIZE { status1 = STATUS1_NONE; }
    PARAMETRIZE { status1 = STATUS1_SLEEP_TURN(1); }
    PARAMETRIZE { status1 = STATUS1_SLEEP_TURN(2); }
    PARAMETRIZE { status1 = STATUS1_SLEEP_TURN(3); }
    PARAMETRIZE { status1 = STATUS1_SLEEP_TURN(4); }
    PARAMETRIZE { status1 = STATUS1_SLEEP_TURN(5); }
    PARAMETRIZE { status1 = STATUS1_POISON; }
    PARAMETRIZE { status1 = STATUS1_BURN; }
    PARAMETRIZE { status1 = STATUS1_FREEZE; }
    PARAMETRIZE { status1 = STATUS1_PARALYSIS; }
    PARAMETRIZE { status1 = STATUS1_TOXIC_POISON; }
    PARAMETRIZE { status1 = STATUS1_FROSTBITE; }
    CreateRandomMonWithIVs(&mon1, SPECIES_WOBBUFFET, 100, 0);
    SetMonData(&mon1, MON_DATA_STATUS, &status1);
    BoxMonToMon(&mon1.box, &mon2);
    EXPECT_EQ(GetMonData(&mon2, MON_DATA_STATUS), status1);
}

TEST("canhypertrain/hypertrain affect MON_DATA_HYPER_TRAINED_* and recalculate stats")
{
    u32 atk, friendship = 0;
    CreateRandomMonWithIVs(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 100, 0);

    // Consider B_FRIENDSHIP_BOOST.
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_FRIENDSHIP, &friendship);
    CalculateMonStats(&gParties[B_TRAINER_PLAYER][0]);

    atk = GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK);

    RUN_OVERWORLD_SCRIPT(
        canhypertrain STAT_ATK, 0;
    );
    EXPECT(VarGet(VAR_RESULT));

    RUN_OVERWORLD_SCRIPT(
        hypertrain STAT_ATK, 0;
        canhypertrain STAT_ATK, 0;
    );
    EXPECT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HYPER_TRAINED_ATK));
    EXPECT_EQ(atk + 31, GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK));
    EXPECT(!VarGet(VAR_RESULT));
}

TEST("hasgigantamaxfactor/togglegigantamaxfactor affect MON_DATA_GIGANTAMAX_FACTOR")
{
    CreateRandomMonWithIVs(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 100, 0);

    RUN_OVERWORLD_SCRIPT(
        hasgigantamaxfactor 0;
    );
    EXPECT(!VarGet(VAR_RESULT));

    RUN_OVERWORLD_SCRIPT(
        togglegigantamaxfactor 0;
        hasgigantamaxfactor 0;
    );
    EXPECT(VarGet(VAR_RESULT));
    EXPECT(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_GIGANTAMAX_FACTOR));

    RUN_OVERWORLD_SCRIPT(
        togglegigantamaxfactor 0;
        hasgigantamaxfactor 0;
    );
    EXPECT(!VarGet(VAR_RESULT));
    EXPECT(!GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_GIGANTAMAX_FACTOR));
}

TEST("togglegigantamaxfactor fails for Melmetal")
{
    CreateRandomMonWithIVs(&gParties[B_TRAINER_PLAYER][0], SPECIES_MELMETAL, 100, 0);

    RUN_OVERWORLD_SCRIPT(
        hasgigantamaxfactor 0;
    );
    EXPECT(!VarGet(VAR_RESULT));

    RUN_OVERWORLD_SCRIPT(
        togglegigantamaxfactor 0;
    );
    EXPECT(!VarGet(VAR_RESULT));
    EXPECT(!GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_GIGANTAMAX_FACTOR));
}

TEST("givemon [simple]")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 100);
}

TEST("givemon respects perfectIVCount")
{
    ZeroPlayerPartyMons();
    u32 perfectIVs[6] = {0};

    ASSUME(gSpeciesInfo[SPECIES_MEW].perfectIVCount == 3);
    ASSUME(gSpeciesInfo[SPECIES_CELEBI].perfectIVCount == 3);
    ASSUME(gSpeciesInfo[SPECIES_JIRACHI].perfectIVCount == 3);
    ASSUME(gSpeciesInfo[SPECIES_MANAPHY].perfectIVCount == 3);
    ASSUME(gSpeciesInfo[SPECIES_VICTINI].perfectIVCount == 3);
    ASSUME(gSpeciesInfo[SPECIES_DIANCIE].perfectIVCount == 3);

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_MEW, 100;
        givemon SPECIES_CELEBI, 100;
        givemon SPECIES_JIRACHI, 100;
        givemon SPECIES_MANAPHY, 100;
        givemon SPECIES_VICTINI, 100;
        givemon SPECIES_DIANCIE, 100;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_MEW);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_SPECIES), SPECIES_CELEBI);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_SPECIES), SPECIES_JIRACHI);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][3], MON_DATA_SPECIES), SPECIES_MANAPHY);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][4], MON_DATA_SPECIES), SPECIES_VICTINI);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][5], MON_DATA_SPECIES), SPECIES_DIANCIE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][3], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][4], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][5], MON_DATA_LEVEL), 100);
    for (u32 j = 0; j < 6; j++)
    {
        for (u32 k = 0; k < NUM_STATS; k++)
        {
            if (GetMonData(&gParties[B_TRAINER_PLAYER][j], MON_DATA_HP_IV + k) == MAX_PER_STAT_IVS)
                perfectIVs[j]++;
        }
        EXPECT_GE(perfectIVs[j], 3);
    }
}

TEST("givemon respects perfectIVCount but does overwrite fixed IVs (1)")
{
    ZeroPlayerPartyMons();

    ASSUME(gSpeciesInfo[SPECIES_MEW].perfectIVCount == 3);
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_MEW, 100, hpIv=7, atkIv=8, defIv=9, speedIv=10, spAtkIv=11, spDefIv=12
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_IV), 7);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_IV), 8);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF_IV), 9);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_IV), 10);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK_IV), 11);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_IV), 12);
}

TEST("givemon respects perfectIVCount but does overwrite fixed IVs (2)")
{
    ZeroPlayerPartyMons();

    ASSUME(gSpeciesInfo[SPECIES_MEW].perfectIVCount == 3);
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_MEW, 100, hpIv=7, atkIv=8, defIv=9
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_IV), 7);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_IV), 8);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF_IV), 9);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_IV), MAX_PER_STAT_IVS);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK_IV), MAX_PER_STAT_IVS);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_IV), MAX_PER_STAT_IVS);
}

TEST("givemon respects FORM_CHANGE_ITEM_HOLD")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_ARCEUS_NORMAL, 100, item=ITEM_ZAP_PLATE;
        givemon SPECIES_ARCEUS_GRASS, 100, item=ITEM_ZAP_PLATE;
        givemon SPECIES_ARCEUS_ELECTRIC, 100, item=ITEM_ZAP_PLATE;
        givemon SPECIES_GIRATINA_ORIGIN, 100, item=ITEM_POTION;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_ARCEUS_ELECTRIC);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][1], MON_DATA_SPECIES), SPECIES_ARCEUS_ELECTRIC);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][2], MON_DATA_SPECIES), SPECIES_ARCEUS_ELECTRIC);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][3], MON_DATA_SPECIES), SPECIES_GIRATINA_ALTERED);
}

TEST("givemon [moves]")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100, move1=MOVE_SCRATCH, move2=MOVE_SPLASH, move3=MOVE_NONE, move4=MOVE_NONE;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE1), MOVE_SCRATCH);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE2), MOVE_SPLASH);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE3), MOVE_NONE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE4), MOVE_NONE);
}

TEST("givemon [moves (default)]")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_PYUKUMUKU, 100, move1=MOVE_DEFAULT, move2=MOVE_DEFAULT, move3=MOVE_DEFAULT;
    );

    const struct LevelUpMove *learnset = GetSpeciesLevelUpLearnset(SPECIES_PYUKUMUKU);
    u32 learnsetLength;
    for (learnsetLength = 0; learnset[learnsetLength].move != LEVEL_UP_MOVE_END; learnsetLength++)
    {
        ; // we just want to get length of the learnset array
    }
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_PYUKUMUKU);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE1), learnset[learnsetLength - 4].move);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE2), learnset[learnsetLength - 3].move);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE3), learnset[learnsetLength - 2].move);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE4), learnset[learnsetLength - 1].move);
}

TEST("givemon [all]")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100, item=ITEM_LEFTOVERS, ball=BALL_MASTER, nature=NATURE_BOLD, abilityNum=2, gender=MON_MALE, hpEv=1, atkEv=2, defEv=3, speedEv=4, spAtkEv=5, spDefEv=6, hpIv=7, atkIv=8, defIv=9, speedIv=10, spAtkIv=11, spDefIv=12, move1=MOVE_SCRATCH, move2=MOVE_SPLASH, move3=MOVE_CELEBRATE, move4=MOVE_EXPLOSION, shinyMode=SHINY_MODE_ALWAYS, gmaxFactor=TRUE, teraType=TYPE_FIRE, dmaxLevel=7;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HELD_ITEM), ITEM_LEFTOVERS);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_POKEBALL), BALL_MASTER);
    EXPECT_EQ(GetNature(&gParties[B_TRAINER_PLAYER][0]), NATURE_BOLD);
    EXPECT_EQ(GetMonAbility(&gParties[B_TRAINER_PLAYER][0]), GetSpeciesAbility(SPECIES_WOBBUFFET, 2));
    EXPECT_EQ(GetMonGender(&gParties[B_TRAINER_PLAYER][0]), MON_MALE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_EV), 1);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_EV), 2);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF_EV), 3);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_EV), 4);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK_EV), 5);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_EV), 6);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_IV), 7);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_IV), 8);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF_IV), 9);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_IV), 10);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK_IV), 11);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_IV), 12);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE1), MOVE_SCRATCH);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE2), MOVE_SPLASH);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE3), MOVE_CELEBRATE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE4), MOVE_EXPLOSION);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_SHINY), TRUE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_GIGANTAMAX_FACTOR), TRUE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_TERA_TYPE), TYPE_FIRE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DYNAMAX_LEVEL), 7);
}

TEST("givemon [vars]")
{
    ZeroPlayerPartyMons();

    VarSet(VAR_TEMP_C, SPECIES_WOBBUFFET);
    VarSet(VAR_TEMP_D, 100);
    VarSet(VAR_0x8000, ITEM_LEFTOVERS);
    VarSet(VAR_0x8001, BALL_MASTER);
    VarSet(VAR_0x8002, NATURE_BOLD);
    VarSet(VAR_0x8003, 2);
    VarSet(VAR_0x8004, MON_MALE);
    VarSet(VAR_0x8005, 1);
    VarSet(VAR_0x8006, 2);
    VarSet(VAR_0x8007, 3);
    VarSet(VAR_0x8008, 4);
    VarSet(VAR_0x8009, 5);
    VarSet(VAR_0x800A, 6);
    VarSet(VAR_0x800B, 7);
    VarSet(VAR_TEMP_0, 8);
    VarSet(VAR_TEMP_1, 9);
    VarSet(VAR_TEMP_2, 10);
    VarSet(VAR_TEMP_3, 11);
    VarSet(VAR_TEMP_4, 12);
    VarSet(VAR_TEMP_5, MOVE_SCRATCH);
    VarSet(VAR_TEMP_6, MOVE_SPLASH);
    VarSet(VAR_TEMP_7, MOVE_CELEBRATE);
    VarSet(VAR_TEMP_8, MOVE_EXPLOSION);
    VarSet(VAR_TEMP_9, SHINY_MODE_ALWAYS);
    VarSet(VAR_TEMP_A, TRUE);
    VarSet(VAR_TEMP_B, TYPE_FIRE);
    VarSet(VAR_TEMP_E, 7);

    RUN_OVERWORLD_SCRIPT(
        givemon VAR_TEMP_C, VAR_TEMP_D, item=VAR_0x8000, ball=VAR_0x8001, nature=VAR_0x8002, abilityNum=VAR_0x8003, gender=VAR_0x8004, hpEv=VAR_0x8005, atkEv=VAR_0x8006, defEv=VAR_0x8007, speedEv=VAR_0x8008, spAtkEv=VAR_0x8009, spDefEv=VAR_0x800A, hpIv=VAR_0x800B, atkIv=VAR_TEMP_0, defIv=VAR_TEMP_1, speedIv=VAR_TEMP_2, spAtkIv=VAR_TEMP_3, spDefIv=VAR_TEMP_4, move1=VAR_TEMP_5, move2=VAR_TEMP_6, move3=VAR_TEMP_7, move4=VAR_TEMP_8, shinyMode=VAR_TEMP_9, gmaxFactor=VAR_TEMP_A, teraType=VAR_TEMP_B, dmaxLevel=VAR_TEMP_E;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPECIES), SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HELD_ITEM), ITEM_LEFTOVERS);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_POKEBALL), BALL_MASTER);
    EXPECT_EQ(GetNature(&gParties[B_TRAINER_PLAYER][0]), NATURE_BOLD);
    EXPECT_EQ(GetMonAbility(&gParties[B_TRAINER_PLAYER][0]), GetSpeciesAbility(SPECIES_WOBBUFFET, 2));
    EXPECT_EQ(GetMonGender(&gParties[B_TRAINER_PLAYER][0]), MON_MALE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_EV), 1);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_EV), 2);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF_EV), 3);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_EV), 4);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK_EV), 5);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_EV), 6);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_IV), 7);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_IV), 8);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF_IV), 9);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_IV), 10);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK_IV), 11);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_IV), 12);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE1), MOVE_SCRATCH);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE2), MOVE_SPLASH);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE3), MOVE_CELEBRATE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MOVE4), MOVE_EXPLOSION);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_IS_SHINY), TRUE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_GIGANTAMAX_FACTOR), TRUE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_TERA_TYPE), TYPE_FIRE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DYNAMAX_LEVEL), 7);
}

TEST("checkteratype/setteratype work")
{
    CreateRandomMonWithIVs(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 100, 0);

    RUN_OVERWORLD_SCRIPT(
        checkteratype 0;
    );
    EXPECT(VarGet(VAR_RESULT) == TYPE_PSYCHIC);

    RUN_OVERWORLD_SCRIPT(
        setteratype TYPE_FIRE, 0;
        checkteratype 0;
    );
    EXPECT(VarGet(VAR_RESULT) == TYPE_FIRE);
}

TEST("createmon [simple]")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        createmon 1, 0, SPECIES_WOBBUFFET, 100;
        createmon 1, 1, SPECIES_WYNAUT, 10;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][0], MON_DATA_SPECIES), SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][0], MON_DATA_LEVEL), 100);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][1], MON_DATA_SPECIES), SPECIES_WYNAUT);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_OPPONENT_A][1], MON_DATA_LEVEL), 10);
}

TEST("Pokémon level up learnsets fit within MAX_LEVEL_UP_MOVES and MAX_RELEARNER_MOVES")
{
    KNOWN_FAILING;

    u32 j, count, species = 0;
    const struct LevelUpMove *learnset;

    for(j = 0; j < SPECIES_EGG; j++)
    {
        PARAMETRIZE { species = j; }
    }

    learnset = GetSpeciesLevelUpLearnset(species);
    count = 0;
    for (j = 0; learnset[j].move != LEVEL_UP_MOVE_END; j++)
        count++;
    EXPECT_LT(count, MAX_LEVEL_UP_MOVES);
    EXPECT_LT(count, MAX_RELEARNER_MOVES - 1); // - 1 because at least one move is already known
}

TEST("Optimised GetMonData")
{
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 5, Random32(), OTID_STRUCT_PRESET(0x12345678));
    u32 exp = 0x123456;
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP, &exp);
    struct Benchmark optimised,
        vanilla = (struct Benchmark) { .ticks = 137 }; // From prior testing
    u32 expGet = 0;
    BENCHMARK(&optimised) { expGet = GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP); }
    EXPECT_EQ(exp, expGet);
    EXPECT_FASTER(optimised, vanilla);
}

TEST("Optimised SetMonData")
{
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 5, Random32(), OTID_STRUCT_PRESET(0x12345678));
    u32 exp = 0x123456;
    struct Benchmark optimised,
        vanilla = (struct Benchmark) { .ticks = 205 }; // From prior testing
    BENCHMARK(&optimised) { SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP, &exp); }
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SANITY_IS_BAD_EGG), FALSE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_EXP), exp);
    EXPECT_FASTER(optimised, vanilla);
}

//Sanity check for a CalculateMonStats refactor (could be deleted or improved)
TEST("CalculateMonStats")
{
    ZeroPlayerPartyMons();

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100, item=ITEM_LEFTOVERS, ball=BALL_MASTER, nature=NATURE_BOLD, abilityNum=2, gender=MON_MALE, hpEv=1, atkEv=2, defEv=3, speedEv=4, spAtkEv=5, spDefEv=6, hpIv=7, atkIv=8, defIv=9, speedIv=10, spAtkIv=11, spDefIv=12, move1=MOVE_SCRATCH, move2=MOVE_SPLASH, move3=MOVE_CELEBRATE, move4=MOVE_EXPLOSION, shinyMode=SHINY_MODE_ALWAYS, gmaxFactor=TRUE, teraType=TYPE_FIRE, dmaxLevel=7;
    );

    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MAX_HP), 497);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK), 71);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF), 143);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED), 82);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK), 83);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF), 134);

}

// BPE Nuzlocke: EVs are switched off in Nuzlocke mode, for the player and for enemy trainers.
TEST("Nuzlocke mode disables EVs")
{
    struct Pokemon mon;

    ZeroPlayerPartyMons();
    FlagSet(FLAG_NUZLOCKE);

    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 100, item=ITEM_LEFTOVERS, ball=BALL_MASTER, nature=NATURE_BOLD, abilityNum=2, gender=MON_MALE, hpEv=1, atkEv=2, defEv=3, speedEv=4, spAtkEv=5, spDefEv=6, hpIv=7, atkIv=8, defIv=9, speedIv=10, spAtkIv=11, spDefIv=12, move1=MOVE_SCRATCH, move2=MOVE_SPLASH, move3=MOVE_CELEBRATE, move4=MOVE_EXPLOSION, shinyMode=SHINY_MODE_ALWAYS, gmaxFactor=TRUE, teraType=TYPE_FIRE, dmaxLevel=7;
    );

    // The Pokemon from the CalculateMonStats test above, whose stored EVs must not count.
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_MAX_HP), 497);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK), 71);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_DEF), 143);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED), 81);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPATK), 82);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF), 133);

    // Nothing can add EVs while the cap is zero: not battles, not vitamins.
    CreateMon(&mon, SPECIES_WOBBUFFET, 5, 0, OTID_STRUCT_PRESET(0));
    EXPECT_EQ(GetCurrentEVCap(), 0);
    MonGainEVs(&mon, SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonEVCount(&mon), 0);
    EXPECT(PokemonUseItemEffects(&mon, ITEM_HP_UP, 0, 0, FALSE));
    EXPECT_EQ(GetMonEVCount(&mon), 0);

    // Standard mode keeps EVs exactly as they were.
    FlagClear(FLAG_NUZLOCKE);
    EXPECT_EQ(GetCurrentEVCap(), MAX_TOTAL_EVS);
    MonGainEVs(&mon, SPECIES_WOBBUFFET);
    EXPECT_EQ(GetMonEVCount(&mon), gSpeciesInfo[SPECIES_WOBBUFFET].evYield_HP);
}

// BPE Nuzlocke: the dead flag must stick. It used to be numbered among the encrypted
// fields, where Get/SetMonData silently ignored it.
TEST("Nuzlocke dead flag is stored and survives the packed PC record")
{
    struct Pokemon mon;
    bool8 dead = TRUE;

    CreateMon(&mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));
    EXPECT(!GetMonData(&mon, MON_DATA_DEAD));
    SetMonData(&mon, MON_DATA_DEAD, &dead);
    EXPECT(GetMonData(&mon, MON_DATA_DEAD));
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SANITY_IS_BAD_EGG), 0);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPECIES), SPECIES_WOBBUFFET);

    SetBoxMonAt(TOTAL_BOXES_COUNT - 1, 0, &mon.box); // an uncached box: packed
    EXPECT(GetBoxMonDataAt(TOTAL_BOXES_COUNT - 1, 0, MON_DATA_DEAD));
    SetBoxMonAt(0, 0, &mon.box);
    EXPECT(GetBoxMonDataAt(0, 0, MON_DATA_DEAD));

    ZeroBoxMonAt(TOTAL_BOXES_COUNT - 1, 0);
    ZeroBoxMonAt(0, 0);
}

// BPE Nuzlocke: the PC heals what it stores, but a dead Pokémon comes back out fainted.
TEST("Nuzlocke mode keeps dead Pokemon fainted through the PC")
{
    struct Pokemon mon, withdrawn;
    bool8 dead = TRUE;
    u32 hp = 0;

    CreateMon(&mon, SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PRESET(0));
    SetMonData(&mon, MON_DATA_HP, &hp);
    SetMonData(&mon, MON_DATA_DEAD, &dead);

    FlagSet(FLAG_NUZLOCKE);
    SetBoxMonAt(0, 0, &mon.box);
    BoxMonAtToMon(0, 0, &withdrawn);
    EXPECT(GetMonData(&withdrawn, MON_DATA_DEAD));
    EXPECT_EQ(GetMonData(&withdrawn, MON_DATA_HP), 0);

    // Placing it anywhere in the PC heals it (OW_PC_HEAL), which must not revive it.
    HealPokemon(&withdrawn);
    EXPECT_EQ(GetMonData(&withdrawn, MON_DATA_HP), 0);

    // Nor can a Revive.
    EXPECT(PokemonUseItemEffects(&withdrawn, ITEM_MAX_REVIVE, 0, 0, FALSE));
    EXPECT_EQ(GetMonData(&withdrawn, MON_DATA_HP), 0);

    // A living Pokémon is still healed on the way out.
    dead = FALSE;
    SetMonData(&mon, MON_DATA_DEAD, &dead);
    SetBoxMonAt(0, 0, &mon.box);
    BoxMonAtToMon(0, 0, &withdrawn);
    EXPECT_EQ(GetMonData(&withdrawn, MON_DATA_HP), GetMonData(&withdrawn, MON_DATA_MAX_HP));

    // Outside Nuzlocke mode the flag means nothing.
    dead = TRUE;
    SetMonData(&mon, MON_DATA_DEAD, &dead);
    FlagClear(FLAG_NUZLOCKE);
    SetBoxMonAt(0, 0, &mon.box);
    BoxMonAtToMon(0, 0, &withdrawn);
    EXPECT_EQ(GetMonData(&withdrawn, MON_DATA_HP), GetMonData(&withdrawn, MON_DATA_MAX_HP));

    ZeroBoxMonAt(0, 0);
}

// BPE Nuzlocke: Mirage Tower has its own encounter. It used to share Route 111's.
TEST("Nuzlocke mode gives Mirage Tower its own encounter")
{
    u32 dexIndex = SpeciesToNationalPokedexNum(SPECIES_WOBBUFFET) - 1;

    FlagSet(FLAG_NUZLOCKE);
    FlagSet(FLAG_SYS_POKEDEX_GET);
    for (u32 var = VAR_WILD_PKMN_ROUTE_SEEN_0; var <= VAR_WILD_PKMN_ROUTE_SEEN_5; var++)
        VarSet(var, 0);
    gSaveBlock1Ptr->dexCaught[dexIndex / 8] &= ~(1 << (dexIndex % 8));
    CreateMon(&gParties[B_TRAINER_OPPONENT_A][0], SPECIES_WOBBUFFET, 30, 0, OTID_STRUCT_PRESET(0));

    // Route 111 and the Desert Ruins still share one encounter.
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_ROUTE_111, TRUE), 0);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_DESERT_RUINS, FALSE), 1);

    // Mirage Tower's is still free, and is used up by its own first battle.
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_MIRAGE_TOWER, TRUE), 0);
    EXPECT_EQ(HasWildPokmnOnThisRouteBeenSeen(MAPSEC_MIRAGE_TOWER, FALSE), 1);

    FlagClear(FLAG_NUZLOCKE);
    for (u32 var = VAR_WILD_PKMN_ROUTE_SEEN_0; var <= VAR_WILD_PKMN_ROUTE_SEEN_5; var++)
        VarSet(var, 0);
}

TEST("BoxPokemon encryption works")
{
    // This test exists to ensure that expansion has not broken anything with regards to how BoxPokemon encryption works.
    // If users make changes to the definitions of BoxPokemon, Pokemon, or any of their members, it is expected that this test will fail. To avoid the failing test from blocking CI, users can uncomment the KNOWN_FAILING declaration.
    // KNOWN_FAILING;
    u32 raw[20] =
    {
        990384375,
        2948624514,
        3907508686,
        14410461,
        35316705,
        3907508686,
        64742109,
        718729,
        3102307966,
        2160206402,
        49956971,
        2495766612,
        1424318580,
        273408756,
        2371630199,
        2708871082,
        3059937332,
        2529190026,
        2290634828,
        2870614922
    };

    struct Pokemon mon;
    BoxMonToMon((struct BoxPokemon *)&raw, &mon);

    EXPECT_EQ(GetMonData(&mon, MON_DATA_SANITY_IS_BAD_EGG), 0);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPECIES), SPECIES_TORCHIC);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_MARKINGS), 3);
    const u8 *actualNickname = COMPOUND_STRING("Testing mon");
    u8 nickname[12];
    GetMonData(&mon, MON_DATA_NICKNAME, nickname);
    u32 charIndex = 0;
    while (actualNickname[charIndex] != EOS)
    {
        EXPECT_EQ(actualNickname[charIndex], nickname[charIndex]);
        charIndex++;
    }
    EXPECT_EQ(GetNature(&mon), NATURE_HARDY);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HIDDEN_NATURE), NATURE_ADAMANT);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HP_LOST), 10);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HELD_ITEM), ITEM_ORAN_BERRY);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_MOVE1), MOVE_TACKLE);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_MOVE2), MOVE_SCRATCH);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_MOVE3), MOVE_POUND);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_MOVE4), MOVE_GROWL);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_PP1), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_PP2), 2);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_PP3), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_PP4), 4);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_PP_BONUSES), 255);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_COOL), 10);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_BEAUTY), 20);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_CUTE), 30);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SMART), 40);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_TOUGH), 50);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SHEEN), 150);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_EXP), 12345);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_MET_LEVEL), 20);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HP_EV), 11);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_ATK_EV), 22);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_DEF_EV), 33);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPEED_EV), 44);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPATK_EV), 55);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPDEF_EV), 66);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_FRIENDSHIP), 123);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_POKERUS), 2);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_POKEBALL), BALL_FRIEND);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HP_IV), 31);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_ATK_IV), 30);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_DEF_IV), 29);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPEED_IV), 28);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPATK_IV), 27);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SPDEF_IV), 26);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_CUTE_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_BEAUTY_RIBBON), 0);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_TOUGH_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_SMART_RIBBON), 0);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_CHAMPION_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_VICTORY_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_EFFORT_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_LAND_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_COUNTRY_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_EARTH_RIBBON), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HYPER_TRAINED_HP), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HYPER_TRAINED_ATK), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HYPER_TRAINED_DEF), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HYPER_TRAINED_SPEED), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HYPER_TRAINED_SPATK), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_HYPER_TRAINED_SPDEF), 1);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_DYNAMAX_LEVEL), 3);
    EXPECT_EQ(GetMonData(&mon, MON_DATA_OT_GENDER), 0);
}
