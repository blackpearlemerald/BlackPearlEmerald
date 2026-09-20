#include "global.h"
#include "data.h"
#include "event_data.h"
#include "item.h"
#include "move.h"
#include "pokemon.h"
#include "randomizer.h"
#include "string_util.h"
#include "ui_birch_case.h"
#include "wild_encounter.h"
#include "test/test.h"
#include "constants/abilities.h"
#include "constants/characters.h"
#include "constants/event_objects.h"
#include "constants/hold_effects.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/species.h"
#include "constants/trainers.h"

// BPE randomizer tests. See BPEDocumentation/RANDOMIZER_PLAN.md.

#define SEED_A 0x1234ABCD
#define SEED_B 0x0BADF00D

// Exposed by src/randomizer.c for these tests only.
u32 Randomizer_Test_GetFieldItemCount(void);
u16 Randomizer_Test_GetFieldItemFlag(u32 index);
u16 Randomizer_Test_GetFieldItem(u32 index);
enum Species Randomizer_Test_GetWallyCatchSpecies(const struct Trainer *wally, enum Species species);

static void UseSettings(const struct RandomizerSettings *settings)
{
    Randomizer_SaveSettings(settings);
}

static void UsePreset(enum RandomizerPreset preset, u32 seed)
{
    struct RandomizerSettings settings;

    Randomizer_ApplyPreset(&settings, preset);
    settings.seed = seed;
    UseSettings(&settings);
}

static u32 GetBST(enum Species species)
{
    const struct SpeciesInfo *info = &gSpeciesInfo[species];
    return info->baseHP + info->baseAttack + info->baseDefense + info->baseSpeed + info->baseSpAttack + info->baseSpDefense;
}

static bool32 OriginallyLearns(enum Species species, enum Move move)
{
    const u16 *learnset = gSpeciesInfo[species].teachableLearnset;
    for (u32 i = 0; learnset != NULL && learnset[i] != MOVE_UNAVAILABLE; i++)
    {
        if (learnset[i] == move)
            return TRUE;
    }
    return FALSE;
}

static void FillTrainer(struct Trainer *trainer, struct TrainerMon *mons, u32 count, u8 trainerClass, const u8 *name)
{
    memset(trainer, 0, sizeof(*trainer));
    trainer->party = mons;
    trainer->partySize = count;
    trainer->trainerClass = trainerClass;
    StringCopy(trainer->trainerName, name);
}

TEST("The randomizer is off in a save that never chose it")
{
    Randomizer_ClearSettings();
    EXPECT(!Randomizer_IsActive());
    EXPECT_EQ(Randomizer_GetWildSpecies(SPECIES_ZIGZAGOON, MAP_ROUTE101, WILD_AREA_LAND), SPECIES_ZIGZAGOON);
    EXPECT_EQ(Randomizer_GetGiftSpecies(SPECIES_BELDUM), SPECIES_BELDUM);
    EXPECT_EQ(GetSpeciesType(SPECIES_TREECKO, 0), TYPE_GRASS);
    EXPECT_EQ(GetSpeciesAbility(SPECIES_TREECKO, 0), gSpeciesInfo[SPECIES_TREECKO].abilities[0]);
    EXPECT_EQ(GetTMHMMoveId(1), gTMHMItemMoveIds[1].moveId);
    EXPECT(Randomizer_IsFullHoennDexPossible());
}

TEST("Seed codes round-trip every setting")
{
    struct RandomizerSettings settings, decoded;
    u8 code[RANDOMIZER_CODE_LENGTH + 1];
    u32 preset;

    PARAMETRIZE { preset = RANDOMIZER_PRESET_RANDOMLOCKE; }
    PARAMETRIZE { preset = RANDOMIZER_PRESET_FULL; }
    PARAMETRIZE { preset = RANDOMIZER_PRESET_CHAOS; }
    PARAMETRIZE { preset = RANDOMIZER_PRESET_CUSTOM; }

    Randomizer_ApplyPreset(&settings, preset);
    settings.seed = SEED_A;
    if (preset == RANDOMIZER_PRESET_CUSTOM)
    {
        for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
            settings.options[i] = Randomizer_GetOptionMax(i);
        settings.options[RANDOMIZER_OPTION_GENERATIONS] = 0x0F5;
        settings.seed = 0xFFFFFFFF;
    }
    Randomizer_EncodeSeedCode(&settings, code);
    EXPECT_EQ(Randomizer_DecodeSeedCode(code, &decoded), RANDOMIZER_CODE_OK);
    EXPECT_EQ(decoded.seed, settings.seed);
    for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
        EXPECT_EQ(decoded.options[i], settings.options[i]);
}

TEST("Seed codes reject a changed character")
{
    struct RandomizerSettings settings, decoded;
    u8 code[RANDOMIZER_CODE_LENGTH + 1];
    u32 rejected = 0;

    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.seed = SEED_A;
    Randomizer_EncodeSeedCode(&settings, code);
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        u8 original = code[i];
        code[i] = (original == Randomizer_GetCodeChar(0)) ? Randomizer_GetCodeChar(1) : Randomizer_GetCodeChar(0);
        if (Randomizer_DecodeSeedCode(code, &decoded) != RANDOMIZER_CODE_OK)
            rejected++;
        code[i] = original;
    }
    // An 8-bit checksum lets a rare change through; nearly every one must fail.
    EXPECT_GE(rejected, RANDOMIZER_CODE_LENGTH - 1);
    code[0] = CHAR_0; // not in the alphabet
    EXPECT_EQ(Randomizer_DecodeSeedCode(code, &decoded), RANDOMIZER_CODE_INVALID);
}

TEST("Presets are recognized, and a changed preset is Custom")
{
    struct RandomizerSettings settings;

    for (u32 preset = 0; preset < RANDOMIZER_PRESET_CUSTOM; preset++)
    {
        Randomizer_ApplyPreset(&settings, preset);
        EXPECT_EQ(Randomizer_GetPreset(&settings), preset);
    }
    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.options[RANDOMIZER_OPTION_TYPE_CHART] = TRUE;
    EXPECT_EQ(Randomizer_GetPreset(&settings), RANDOMIZER_PRESET_CUSTOM);
}

TEST("Settings survive saving to the variables")
{
    struct RandomizerSettings settings, loaded;

    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_CHAOS);
    settings.seed = SEED_B;
    settings.options[RANDOMIZER_OPTION_MONOTYPE] = TYPE_DRAGON;
    settings.options[RANDOMIZER_OPTION_GENERATIONS] = 0x1FE;
    UseSettings(&settings);
    Randomizer_LoadSettings(&loaded);
    EXPECT_EQ(loaded.seed, settings.seed);
    for (u32 i = 0; i < RANDOMIZER_OPTION_COUNT; i++)
        EXPECT_EQ(loaded.options[i], settings.options[i]);
    EXPECT_EQ(Randomizer_GetSavedVersion(), RANDOMIZER_ALGORITHM_VERSION);
    Randomizer_ClearSettings();
}

TEST("The species pool leaves out battle-only and cosmetic forms")
{
    EXPECT(Randomizer_IsSpeciesInPool(SPECIES_BULBASAUR));
    EXPECT(Randomizer_IsSpeciesInPool(SPECIES_VULPIX_ALOLA));
    EXPECT(Randomizer_IsSpeciesInPool(SPECIES_ROTOM_WASH));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_NONE));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_VENUSAUR_MEGA));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_CHARIZARD_GMAX));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_RATICATE_ALOLA_TOTEM));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_UNOWN_B));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_PIKACHU_PARTNER));
    EXPECT(!Randomizer_IsSpeciesInPool(SPECIES_DARMANITAN_GALAR_ZEN));
    for (enum Species species = 1; species < NUM_SPECIES; species++)
    {
        const struct SpeciesInfo *info = &gSpeciesInfo[species];
        if (Randomizer_IsSpeciesInPool(species))
            EXPECT(!info->isMegaEvolution && !info->isGigantamax && !info->isTotem && !info->isPrimalReversion);
    }
}

TEST("Generated evolution families match the species data")
{
    for (enum Species species = 1; species < NUM_SPECIES; species++)
    {
        const struct Evolution *evolutions = gSpeciesInfo[species].evolutions;
        if (!IsSpeciesEnabled(species) || species == SPECIES_GIMMIGHOUL_ROAMING)
            continue;
        for (u32 i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
        {
            enum Species target = evolutions[i].targetSpecies;
            if (target == species || target >= NUM_SPECIES || !IsSpeciesEnabled(target))
                continue;
            EXPECT_EQ(Randomizer_GetFamilyRoot(target), Randomizer_GetFamilyRoot(species));
        }
    }
    EXPECT_EQ(Randomizer_GetFamilyRoot(SPECIES_VENUSAUR), SPECIES_BULBASAUR);
    EXPECT_EQ(Randomizer_GetEvolutionStage(SPECIES_IVYSAUR), 1);
    EXPECT_EQ(Randomizer_GetFamilyLength(SPECIES_CHARMANDER), 3);
    EXPECT_EQ(Randomizer_GetFamilyLength(SPECIES_EEVEE), 2);
}

TEST("The whole-game swap is one for one")
{
    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_A);
    for (enum Species species = 1; species < NUM_SPECIES; species++)
    {
        enum Species swapped = Randomizer_GetWildSpecies(species, MAP_ROUTE101, WILD_AREA_LAND);
        if (swapped == species)
            continue;
        EXPECT_EQ(Randomizer_GetWildSwapOriginal(swapped), species);
        EXPECT_EQ(Randomizer_IsLegendary(swapped), Randomizer_IsLegendary(species));
        EXPECT_EQ(OriginallyLearns(swapped, MOVE_SURF), OriginallyLearns(species, MOVE_SURF));
        EXPECT(Randomizer_IsSpeciesInPool(swapped));
    }
    Randomizer_ClearSettings();
}

TEST("Similar strength keeps replacements close to the original")
{
    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_B);
    for (enum Species species = SPECIES_BULBASAUR; species < SPECIES_CELEBI; species++)
    {
        enum Species swapped = Randomizer_GetWildSpecies(species, MAP_ROUTE101, WILD_AREA_LAND);
        u32 before = GetBST(species), after = GetBST(swapped);
        // The strength bands are about 20% wide.
        EXPECT_LE(after * 100, before * 125);
        EXPECT_GE(after * 125, before * 100);
    }
    Randomizer_ClearSettings();
}

TEST("The same seed always gives the same game")
{
    enum Species first[20], second[20];
    u32 differences = 0;

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    for (u32 i = 0; i < ARRAY_COUNT(first); i++)
        first[i] = Randomizer_GetWildSpecies(SPECIES_BULBASAUR + i, MAP_ROUTE102, WILD_AREA_LAND);
    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    for (u32 i = 0; i < ARRAY_COUNT(first); i++)
        EXPECT_EQ(Randomizer_GetWildSpecies(SPECIES_BULBASAUR + i, MAP_ROUTE102, WILD_AREA_LAND), first[i]);
    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_B);
    for (u32 i = 0; i < ARRAY_COUNT(second); i++)
    {
        second[i] = Randomizer_GetWildSpecies(SPECIES_BULBASAUR + i, MAP_ROUTE102, WILD_AREA_LAND);
        if (second[i] != first[i])
            differences++;
    }
    EXPECT_GT(differences, 10);
    Randomizer_ClearSettings();
}

TEST("Per-route water slots only hold Pokemon that can learn Surf")
{
    struct RandomizerSettings settings;

    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_CHAOS);
    settings.seed = SEED_B;
    settings.options[RANDOMIZER_OPTION_TYPES] = FALSE;
    UseSettings(&settings);
    for (enum Species species = SPECIES_TENTACOOL; species < SPECIES_TENTACOOL + 40; species++)
    {
        EXPECT(OriginallyLearns(Randomizer_GetWildSpecies(species, MAP_ROUTE103, WILD_AREA_WATER), MOVE_SURF));
        EXPECT(OriginallyLearns(Randomizer_GetWildSpecies(species, MAP_ROUTE110, WILD_AREA_FISHING), MOVE_SURF));
    }
    Randomizer_ClearSettings();
}

TEST("Generations limit which Pokemon appear")
{
    struct RandomizerSettings settings;

    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.seed = SEED_A;
    settings.options[RANDOMIZER_OPTION_GENERATIONS] = 0x1FF & ~(1 << 2); // Gen 3 only
    UseSettings(&settings);
    for (enum Species species = SPECIES_BULBASAUR; species < SPECIES_BULBASAUR + 60; species++)
    {
        enum Species picked = Randomizer_GetWildSpecies(species, MAP_ROUTE101, WILD_AREA_LAND);
        if (picked != species)
            EXPECT_EQ(Randomizer_GetSpeciesGeneration(picked), 3);
    }
    Randomizer_ClearSettings();
}

TEST("Same-role starters keep each ball's type and evolution length")
{
    u16 starters[12];

    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_A);
    Randomizer_FillStarters(starters, ARRAY_COUNT(starters));
    for (u32 i = 0; i < ARRAY_COUNT(starters); i++)
    {
        enum Species original = (i < 9) ? BirchCase_GetOriginalSpecies(i) : (u16[]){SPECIES_CHIKORITA, SPECIES_CYNDAQUIL, SPECIES_TOTODILE}[i - 9];
        EXPECT_EQ(Randomizer_GetFamilyRoot(starters[i]), starters[i]);
        EXPECT(!Randomizer_IsLegendary(starters[i]));
        EXPECT(GetSpeciesType(starters[i], 0) == GetSpeciesType(original, 0) || GetSpeciesType(starters[i], 1) == GetSpeciesType(original, 0));
        EXPECT_EQ(Randomizer_GetFamilyLength(starters[i]), Randomizer_GetFamilyLength(original));
        EXPECT_NE(Randomizer_GetFamilyRoot(starters[i]), Randomizer_GetFamilyRoot(original));
        for (u32 j = 0; j < i; j++)
            EXPECT_NE(Randomizer_GetFamilyRoot(starters[i]), Randomizer_GetFamilyRoot(starters[j]));
    }
    Randomizer_ClearSettings();
}

TEST("Random starters offer nine different main types")
{
    u16 starters[9];
    u32 types = 0;

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_B);
    Randomizer_FillStarters(starters, ARRAY_COUNT(starters));
    for (u32 i = 0; i < ARRAY_COUNT(starters); i++)
    {
        u32 bit = 1u << GetSpeciesType(starters[i], 0);
        EXPECT(!(types & bit));
        types |= bit;
        EXPECT_EQ(Randomizer_GetFamilyRoot(starters[i]), starters[i]);
    }
    Randomizer_ClearSettings();
}

static bool32 CanAttackAtLevel5(enum Species species)
{
    const struct LevelUpMove *learnset = GetSpeciesLevelUpLearnset(species);

    for (u32 j = 0; learnset[j].move != LEVEL_UP_MOVE_END && learnset[j].level <= 5; j++)
    {
        enum Move move = GetLearnsetMove(species, learnset, j);
        if (GetMoveCategory(move) != DAMAGE_CATEGORY_STATUS && GetMovePower(move) > 1)
            return TRUE;
    }
    return FALSE;
}

TEST("The Johto gift starters can attack at level 5")
{
    u16 starters[12];
    u32 seed;

    PARAMETRIZE { seed = SEED_A; }
    PARAMETRIZE { seed = SEED_B; }
    UsePreset(RANDOMIZER_PRESET_FULL, seed);
    Randomizer_FillStarters(starters, ARRAY_COUNT(starters));
    // The Birch Case grants Tackle instead, so only the Johto balls are filtered.
    for (u32 i = 9; i < ARRAY_COUNT(starters); i++)
        EXPECT(CanAttackAtLevel5(starters[i]));
    Randomizer_ClearSettings();
}

TEST("A starter that cannot attack is given Tackle")
{
    struct Pokemon mon;
    enum Species species;
    bool32 needed;

    PARAMETRIZE { species = SPECIES_MAGIKARP; needed = TRUE; }
    PARAMETRIZE { species = SPECIES_ABRA; needed = TRUE; }
    PARAMETRIZE { species = SPECIES_WYNAUT; needed = TRUE; }
    PARAMETRIZE { species = SPECIES_TREECKO; needed = FALSE; }
    Randomizer_ClearSettings(); // Randomized learnsets would change the moves.
    CreateMon(&mon, species, 5, 0, OTID_STRUCT_PRESET(0));
    EXPECT_EQ(CanAttackAtLevel5(species), !needed);
    GiveMonInitialMoveset(&mon);
    Randomizer_EnsureStarterCanAttack(&mon);
    bool32 knowsTackle = FALSE;
    bool32 canAttack = FALSE;
    for (u32 i = 0; i < MAX_MON_MOVES; i++)
    {
        enum Move move = GetMonData(&mon, MON_DATA_MOVE1 + i);
        if (move == MOVE_TACKLE)
            knowsTackle = TRUE;
        if (move != MOVE_NONE && GetMoveCategory(move) != DAMAGE_CATEGORY_STATUS && GetMovePower(move) > 1)
            canAttack = TRUE;
    }
    EXPECT(canAttack);
    EXPECT_EQ(knowsTackle, needed);
}

TEST("Legendary starters are all legendary and keep nine different types")
{
    struct RandomizerSettings settings;
    u16 starters[9];
    u32 types = 0;
    u32 seed;

    PARAMETRIZE { seed = SEED_A; }
    PARAMETRIZE { seed = SEED_B; }
    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_FULL);
    settings.seed = seed;
    settings.options[RANDOMIZER_OPTION_STARTERS] = RANDOMIZER_STARTERS_LEGENDARY;
    UseSettings(&settings);
    Randomizer_FillStarters(starters, ARRAY_COUNT(starters));
    for (u32 i = 0; i < ARRAY_COUNT(starters); i++)
    {
        u32 bit = 1u << GetSpeciesType(starters[i], 0);
        EXPECT(Randomizer_IsLegendary(starters[i]));
        EXPECT_EQ(Randomizer_GetFamilyRoot(starters[i]), starters[i]);
        EXPECT(!(types & bit));
        types |= bit;
    }
    Randomizer_ClearSettings();
}

TEST("Monotype starters all share the chosen type")
{
    struct RandomizerSettings settings;
    u16 starters[12];

    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.seed = SEED_A;
    settings.options[RANDOMIZER_OPTION_MONOTYPE] = TYPE_WATER;
    UseSettings(&settings);
    Randomizer_FillStarters(starters, ARRAY_COUNT(starters));
    for (u32 i = 0; i < ARRAY_COUNT(starters); i++)
        EXPECT(GetSpeciesType(starters[i], 0) == TYPE_WATER || GetSpeciesType(starters[i], 1) == TYPE_WATER);
    Randomizer_ClearSettings();
}

TEST("Wally's catch follows his team, not the wild option")
{
    struct RandomizerSettings settings;
    struct Trainer wally;
    struct TrainerMon party[2] = {0};
    enum Species caught, gardevoir;

    party[0].species = SPECIES_DELCATTY;
    party[1].species = SPECIES_GARDEVOIR;
    FillTrainer(&wally, party, ARRAY_COUNT(party), TRAINER_CLASS_RIVAL, COMPOUND_STRING("WALLY"));

    // Randomlocke randomizes wild Pokemon but leaves bosses, and Wally is a rival.
    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.seed = SEED_A;
    UseSettings(&settings);
    EXPECT_EQ(Randomizer_Test_GetWallyCatchSpecies(&wally, SPECIES_RALTS), SPECIES_RALTS);
    EXPECT_EQ(Randomizer_GetTrainerSpecies(&wally, 1), SPECIES_GARDEVOIR);

    // With his fight randomized, he catches the first stage of his new line.
    settings.options[RANDOMIZER_OPTION_BOSS_TRAINERS] = RANDOMIZER_BOSSES_FULLY_RANDOM;
    UseSettings(&settings);
    caught = Randomizer_Test_GetWallyCatchSpecies(&wally, SPECIES_RALTS);
    gardevoir = Randomizer_GetTrainerSpecies(&wally, 1);
    EXPECT_NE(caught, SPECIES_RALTS);
    EXPECT_EQ(Randomizer_GetFamilyRoot(caught), caught);
    EXPECT_EQ(Randomizer_GetFamilyRoot(gardevoir), caught);
    Randomizer_ClearSettings();
}

TEST("A trainer's family keeps its replacement between fights")
{
    struct Trainer trainer;
    struct TrainerMon mon = {0};
    enum Species species[3];

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    mon.species = SPECIES_GIBLE;
    FillTrainer(&trainer, &mon, 1, TRAINER_CLASS_RIVAL, COMPOUND_STRING("CYNTHIA"));
    species[0] = Randomizer_GetTrainerSpecies(&trainer, 0);
    mon.species = SPECIES_GABITE;
    species[1] = Randomizer_GetTrainerSpecies(&trainer, 0);
    mon.species = SPECIES_GARCHOMP;
    species[2] = Randomizer_GetTrainerSpecies(&trainer, 0);
    EXPECT_NE(species[0], SPECIES_GIBLE);
    EXPECT_EQ(Randomizer_GetFamilyRoot(species[1]), species[0]);
    EXPECT_EQ(Randomizer_GetFamilyRoot(species[2]), species[0]);
    EXPECT_EQ(Randomizer_GetEvolutionStage(species[0]), 0);
    Randomizer_ClearSettings();
}

TEST("Unchanged bosses keep their Pokemon")
{
    struct Trainer trainer;
    struct TrainerMon mon = {0};

    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_A);
    mon.species = SPECIES_GEODUDE;
    FillTrainer(&trainer, &mon, 1, TRAINER_CLASS_LEADER, COMPOUND_STRING("ROXANNE"));
    EXPECT_EQ(Randomizer_GetTrainerSpecies(&trainer, 0), SPECIES_GEODUDE);
    EXPECT(Randomizer_KeepsTrainerAbilities(&trainer));
    FillTrainer(&trainer, &mon, 1, TRAINER_CLASS_YOUNGSTER, COMPOUND_STRING("CALVIN"));
    EXPECT_NE(Randomizer_GetTrainerSpecies(&trainer, 0), SPECIES_GEODUDE);
    Randomizer_ClearSettings();
}

TEST("Bosses that keep their type share a type with the original")
{
    struct Trainer trainer;
    struct TrainerMon mons[3] = {{.species = SPECIES_GEODUDE}, {.species = SPECIES_NOSEPASS}, {.species = SPECIES_ONIX}};

    UsePreset(RANDOMIZER_PRESET_FULL, SEED_B);
    FillTrainer(&trainer, mons, 3, TRAINER_CLASS_LEADER, COMPOUND_STRING("ROXANNE"));
    for (u32 i = 0; i < 3; i++)
    {
        enum Species species = Randomizer_GetTrainerSpecies(&trainer, i);
        EXPECT(GetSpeciesType(species, 0) == TYPE_ROCK || GetSpeciesType(species, 1) == TYPE_ROCK
            || GetSpeciesType(species, 0) == TYPE_GROUND || GetSpeciesType(species, 1) == TYPE_GROUND);
    }
    Randomizer_ClearSettings();
}

TEST("A Mega Stone holder becomes a Pokemon that can Mega Evolve")
{
    struct Trainer trainer;
    struct TrainerMon mon = {.species = SPECIES_ABSOL, .heldItem = ITEM_ABSOLITE};
    enum Species species;

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    FillTrainer(&trainer, &mon, 1, TRAINER_CLASS_CHAMPION, COMPOUND_STRING("WALLACE"));
    species = Randomizer_GetTrainerSpecies(&trainer, 0);
    EXPECT_EQ(GetItemHoldEffect(Randomizer_GetTrainerHeldItem(SPECIES_ABSOL, species, ITEM_ABSOLITE)), HOLD_EFFECT_MEGA_STONE);
    Randomizer_ClearSettings();
}

TEST("Randomized trainer Pokemon get a full, sensible moveset")
{
    struct Pokemon mon;

    UsePreset(RANDOMIZER_PRESET_FULL, SEED_A);
    CreateMon(&mon, SPECIES_GARCHOMP, 60, 0, OTID_STRUCT_PRESET(0));
    Randomizer_GiveTrainerMonMoves(&mon);
    for (u32 i = 0; i < MAX_MON_MOVES; i++)
    {
        enum Move move = GetMonData(&mon, MON_DATA_MOVE1 + i);
        EXPECT_NE(move, MOVE_NONE);
        EXPECT(!IsExplosionMove(move));
        for (u32 j = 0; j < i; j++)
            EXPECT_NE(move, GetMonData(&mon, MON_DATA_MOVE1 + j));
    }
    Randomizer_ClearSettings();
}

TEST("Random abilities are shared by a family and never broken")
{
    UsePreset(RANDOMIZER_PRESET_FULL, SEED_A);
    for (enum Species species = 1; species < NUM_SPECIES; species++)
    {
        if (!Randomizer_IsSpeciesInPool(species))
            continue;
        for (u32 slot = 0; slot < NUM_ABILITY_SLOTS; slot++)
        {
            enum Ability ability = GetSpeciesAbility(species, slot);
            enum Ability rootAbility = GetSpeciesAbility(Randomizer_GetFamilyRoot(species), slot);
            if (gSpeciesInfo[species].abilities[slot] == ABILITY_NONE)
            {
                EXPECT_EQ(ability, ABILITY_NONE);
                continue;
            }
            if (species != SPECIES_SHEDINJA)
                EXPECT_NE(ability, ABILITY_WONDER_GUARD);
            if (ability != gSpeciesInfo[species].abilities[slot])
            {
                EXPECT_NE(ability, ABILITY_HUGE_POWER);
                EXPECT_NE(ability, ABILITY_PURE_POWER);
                EXPECT_GE(gAbilitiesInfo[ability].aiRating, 0);
                if (gSpeciesInfo[Randomizer_GetFamilyRoot(species)].abilities[slot] != ABILITY_NONE)
                    EXPECT_EQ(ability, rootAbility);
            }
        }
    }
    Randomizer_ClearSettings();
}

TEST("Random learnsets start with an attack")
{
    UsePreset(RANDOMIZER_PRESET_FULL, SEED_B);
    for (enum Species species = 1; species < NUM_SPECIES; species++)
    {
        const struct LevelUpMove *learnset;
        enum Move move;

        if (!Randomizer_IsSpeciesInPool(species))
            continue;
        learnset = GetSpeciesLevelUpLearnset(species);
        if (learnset[0].move == LEVEL_UP_MOVE_END)
            continue;
        move = GetLearnsetMove(species, learnset, 0);
        EXPECT_NE(GetMoveCategory(move), DAMAGE_CATEGORY_STATUS);
        EXPECT_NE(move, MOVE_SURF);
        EXPECT_NE(move, MOVE_CUT);
    }
    Randomizer_ClearSettings();
}

TEST("TM compatibility never changes what can learn an HM")
{
    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    for (enum Species species = 1; species < NUM_SPECIES; species++)
    {
        if (!Randomizer_IsSpeciesInPool(species))
            continue;
        EXPECT_EQ(CanLearnTeachableMove(species, MOVE_SURF), OriginallyLearns(species, MOVE_SURF));
        EXPECT_EQ(CanLearnTeachableMove(species, MOVE_CUT), OriginallyLearns(species, MOVE_CUT));
        EXPECT_EQ(CanLearnTeachableMove(species, MOVE_ROCK_SMASH), OriginallyLearns(species, MOVE_ROCK_SMASH));
    }
    Randomizer_ClearSettings();
}

TEST("TM contents are a shuffle of the TM moves, and HMs stay")
{
    u32 seen[(NUM_TECHNICAL_MACHINES + 31) / 32] = {0};

    UsePreset(RANDOMIZER_PRESET_FULL, SEED_A);
    for (u32 tm = 1; tm <= NUM_TECHNICAL_MACHINES; tm++)
    {
        u32 contents = Randomizer_GetTMIndexContents(tm);
        EXPECT_GE(contents, 1);
        EXPECT_LE(contents, NUM_TECHNICAL_MACHINES);
        EXPECT(!(seen[(contents - 1) / 32] & (1u << ((contents - 1) % 32))));
        seen[(contents - 1) / 32] |= 1u << ((contents - 1) % 32);
        EXPECT_EQ(Randomizer_GetTMIndexTeaching(contents), tm);
        EXPECT_EQ(GetTMHMItemIdFromMoveId(GetTMHMMoveId(tm)), GetTMHMItemId(tm));
    }
    EXPECT_EQ(GetItemTMHMMoveId(ITEM_HM_SURF), MOVE_SURF);
    Randomizer_ClearSettings();
}

TEST("Field items trade places without losing any, and key items stay")
{
    u32 count = Randomizer_Test_GetFieldItemCount();
    u32 usedTms = 0, originalTms = 0;

    UsePreset(RANDOMIZER_PRESET_FULL, SEED_B);
    for (u32 i = 0; i < count; i++)
    {
        u16 flag = Randomizer_Test_GetFieldItemFlag(i);
        u16 original = Randomizer_Test_GetFieldItem(i);
        u16 item = original, amount = 0;

        if (flag == 0)
            continue;
        Randomizer_GetFieldItem(flag, &item, &amount);
        if (GetItemPocket(original) == POCKET_KEY_ITEMS)
            EXPECT_EQ(item, original);
        if (GetItemPocket(original) == POCKET_TM_HM)
        {
            EXPECT_EQ(GetItemPocket(item), POCKET_TM_HM);
            originalTms++;
        }
        if (GetItemPocket(item) == POCKET_TM_HM)
            usedTms++;
    }
    EXPECT_EQ(usedTms, originalTms);
    Randomizer_ClearSettings();
}

TEST("The shuffled type chart is a relabelling of the 18 types")
{
    u32 seen = 0;

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    for (u32 type = TYPE_NORMAL; type <= TYPE_FAIRY; type++)
    {
        u32 relabelled;
        if (type == TYPE_MYSTERY)
            continue;
        relabelled = Randomizer_GetTypeChartType(type);
        EXPECT_NE(relabelled, TYPE_MYSTERY);
        EXPECT(!(seen & (1u << relabelled)));
        seen |= 1u << relabelled;
    }
    EXPECT_EQ(Randomizer_GetTypeChartType(TYPE_MYSTERY), TYPE_MYSTERY);
    EXPECT_EQ(Randomizer_GetTypeChartType(TYPE_STELLAR), TYPE_STELLAR);
    Randomizer_ClearSettings();
}

TEST("An HM works for anyone only when nothing on offer can learn it")
{
    static const u16 hms[] = {MOVE_CUT, MOVE_FLY, MOVE_SURF, MOVE_STRENGTH, MOVE_FLASH, MOVE_ROCK_SMASH, MOVE_WATERFALL, MOVE_DIVE};
    struct RandomizerSettings settings;

    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_A);
    for (u32 i = 0; i < ARRAY_COUNT(hms); i++)
        EXPECT(!Randomizer_HasHMFallback(hms[i]));

    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.seed = SEED_A;
    settings.options[RANDOMIZER_OPTION_MONOTYPE] = TYPE_FIRE;
    settings.options[RANDOMIZER_OPTION_GENERATIONS] = 0x1FF & ~(1 << 0); // Gen 1 only
    UseSettings(&settings);
    for (u32 i = 0; i < ARRAY_COUNT(hms); i++)
    {
        bool32 learnable = FALSE;
        for (enum Species species = 1; species < NUM_SPECIES && !learnable; species++)
        {
            if (Randomizer_IsSpeciesInPool(species) && Randomizer_GetSpeciesGeneration(species) == 1
             && (GetSpeciesType(species, 0) == TYPE_FIRE || GetSpeciesType(species, 1) == TYPE_FIRE)
             && OriginallyLearns(species, hms[i]))
                learnable = TRUE;
        }
        EXPECT_EQ(Randomizer_HasHMFallback(hms[i]), !learnable);
    }
    Randomizer_ClearSettings();
}

TEST("The full Hoenn Dex stays possible only with the whole-game swap")
{
    struct RandomizerSettings settings;

    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_A);
    EXPECT(Randomizer_IsFullHoennDexPossible());
    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_A);
    EXPECT(!Randomizer_IsFullHoennDexPossible());
    Randomizer_ApplyPreset(&settings, RANDOMIZER_PRESET_RANDOMLOCKE);
    settings.seed = SEED_A;
    settings.options[RANDOMIZER_OPTION_MONOTYPE] = TYPE_GRASS;
    UseSettings(&settings);
    EXPECT(!Randomizer_IsFullHoennDexPossible());
    Randomizer_ClearSettings();
}

TEST("Story battles stay easy and static objects show their new Pokemon")
{
    enum Species species;

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_B);
    species = Randomizer_GetStoryWildSpecies(SPECIES_ZIGZAGOON, MAP_ROUTE101);
    EXPECT(!Randomizer_IsLegendary(species));
    EXPECT_LE(GetBST(species) * 100, GetBST(SPECIES_ZIGZAGOON) * 150);
    species = Randomizer_GetStaticSpeciesOnMap(SPECIES_KECLEON, MAP_ROUTE120);
    EXPECT_EQ(Randomizer_GetStaticObjectGraphics(MAP_ROUTE120, OBJ_EVENT_GFX_KECLEON),
              species == SPECIES_KECLEON ? OBJ_EVENT_GFX_KECLEON : species + OBJ_EVENT_MON);
    EXPECT_EQ(Randomizer_GetStaticObjectGraphics(MAP_ROUTE120, OBJ_EVENT_GFX_ITEM_BALL), OBJ_EVENT_GFX_ITEM_BALL);
    Randomizer_ClearSettings();
}

// Pinned results for fixed seeds. If one of these changes, an existing seed now
// gives a different game: raise RANDOMIZER_ALGORITHM_VERSION instead of updating
// the numbers, unless the change is intended and no randomized game was released.
TEST("Fixed seeds keep giving the same results")
{
    static const u16 sExpectedStarters[] = {574, 624, 590, 293, 653, 501, 650, 190, 1363};
    u16 starters[ARRAY_COUNT(sExpectedStarters)];

    UsePreset(RANDOMIZER_PRESET_RANDOMLOCKE, SEED_A);
    EXPECT_EQ(Randomizer_GetWildSpecies(SPECIES_ZIGZAGOON, MAP_ROUTE101, WILD_AREA_LAND), 659);
    EXPECT_EQ(Randomizer_GetWildSpecies(SPECIES_TENTACOOL, MAP_ROUTE105, WILD_AREA_WATER), 79);
    Randomizer_FillStarters(starters, ARRAY_COUNT(starters));
    for (u32 i = 0; i < ARRAY_COUNT(starters); i++)
        EXPECT_EQ(starters[i], sExpectedStarters[i]);

    UsePreset(RANDOMIZER_PRESET_CHAOS, SEED_B);
    EXPECT_EQ(Randomizer_GetWildSpecies(SPECIES_ZIGZAGOON, MAP_ROUTE101, WILD_AREA_LAND), 903);
    EXPECT_EQ(GetSpeciesAbility(SPECIES_TREECKO, 0), 198);
    EXPECT_EQ(GetSpeciesType(SPECIES_TREECKO, 0), 2);
    EXPECT_EQ(GetSpeciesBaseAttack(SPECIES_TREECKO), 65);
    EXPECT_EQ(Randomizer_GetTypeChartType(TYPE_FIRE), 3);
    EXPECT_EQ(Randomizer_GetTMIndexContents(1), 181);
    EXPECT_EQ(Randomizer_GetEvolutionTarget(SPECIES_TREECKO, SPECIES_GROVYLE), 726);
    Randomizer_ClearSettings();
}
