#include "global.h"
#include "agb_flash.h"
#include "event_data.h"
#include "gba/flash_internal.h"
#include "item.h"
#include "load_save.h"
#include "malloc.h"
#include "packed_box_mon.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "random.h"
#include "save.h"
#include "save_engine.h"
#include "string_util.h"
#include "text.h"
#include "test/test.h"
#include "constants/characters.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokeball.h"

// BPE 2.1 save format tests. The crash-safety rules are also exercised far
// more exhaustively by the host simulator in BPETools/save_sim; these tests
// check the real game structures, the packed Pokémon format and the flash
// glue in src/save.c.

// Update these when a save block changes. The save converter and the save
// inspector must be updated with them.
// The Items and Key Items pockets grew by appending slots to the end of
// SaveBlock1, so this is the only size that moved.
#define T_SAVEBLOCK1_OLD_SIZE 15836
#define T_SAVEBLOCK1_EXTRA_SLOTS (BAG_KEYITEMS_EXTRA_COUNT + BAG_ITEMS_EXTRA_COUNT)
#define T_SAVEBLOCK1_SIZE (T_SAVEBLOCK1_OLD_SIZE + sizeof(struct ItemSlot) * T_SAVEBLOCK1_EXTRA_SLOTS)
#define T_SAVEBLOCK2_SIZE 2852
#define T_SAVEBLOCK3_SIZE 4
#define T_STORAGE_HEADER_SIZE (((1 + TOTAL_BOXES_COUNT * (BOX_NAME_LENGTH + 2) + 3) & ~3) + MAX_FUSION_STORAGE * sizeof(struct Pokemon))

TEST("SaveBlock1 is backwards compatible")
{
    EXPECT_EQ(sizeof(struct SaveBlock1), T_SAVEBLOCK1_SIZE);
}

TEST("The extra bag slots are appended after everything older saves hold")
{
    EXPECT_EQ(offsetof(struct SaveBlock1, keyItemsExtra), T_SAVEBLOCK1_OLD_SIZE);
    EXPECT_EQ(offsetof(struct SaveBlock1, itemsExtra),
              T_SAVEBLOCK1_OLD_SIZE + sizeof(struct ItemSlot) * BAG_KEYITEMS_EXTRA_COUNT);
    EXPECT_EQ((u32)gBagPockets[POCKET_KEY_ITEMS].capacity, BAG_KEYITEMS_TOTAL);
    EXPECT_EQ((u32)gBagPockets[POCKET_ITEMS].capacity, BAG_ITEMS_TOTAL);
    // Anything more needs a new save format: SaveBlock1 gets progress parts 1-4.
    EXPECT_LE(sizeof(struct SaveBlock1), SAVE_SECTOR_PAYLOAD_SIZE * (SAVE_PROGRESS_PARTS - 1));
}

TEST("SaveBlock2 is backwards compatible")
{
    EXPECT_EQ(sizeof(struct SaveBlock2), T_SAVEBLOCK2_SIZE);
}

TEST("SaveBlock3 is backwards compatible")
{
    EXPECT_EQ(sizeof(struct SaveBlock3), T_SAVEBLOCK3_SIZE);
}

TEST("PC box header is backwards compatible")
{
    EXPECT_EQ(POKEMON_STORAGE_HEADER_SIZE, T_STORAGE_HEADER_SIZE);
    EXPECT_EQ(offsetof(struct PokemonStorage, fusions), ((1 + TOTAL_BOXES_COUNT * (BOX_NAME_LENGTH + 2) + 3) & ~3));
    EXPECT_EQ(sizeof(struct PackedBoxMon), 60);
    EXPECT_EQ(sizeof(gPokemonStoragePtr->boxes), TOTAL_BOXES_COUNT * IN_BOX_COUNT * 60);
}

// The damage calculator's save import (BPEDocumentation/site/js/save-converter.js)
// reads these members directly.
TEST("Party, flags, variables and Day Care are where the website reads them")
{
    EXPECT_EQ(offsetof(struct SaveBlock1, playerPartyCount), 564);
    EXPECT_EQ(offsetof(struct SaveBlock1, playerParty), 568);
    EXPECT_EQ(offsetof(struct SaveBlock1, flags), 5864);
    EXPECT_EQ(offsetof(struct SaveBlock1, vars), 6164);
    EXPECT_EQ(offsetof(struct SaveBlock1, daycare), 13480);
    EXPECT_EQ(sizeof(struct Pokemon), 100);
    EXPECT_EQ(offsetof(struct Pokemon, level), 84);
    EXPECT_EQ(sizeof(struct DaycareMon), 140);
    EXPECT_EQ(offsetof(struct DaycareMon, mon), 0);
    EXPECT_EQ(DAYCARE_MON_COUNT, 2);
    EXPECT_EQ(VARS_START, 0x4000);
}

TEST("Save format fits the flash layout")
{
    EXPECT_LE(SAVE_META_SIZE + sizeof(struct SaveBlock2) + POKEMON_STORAGE_HEADER_SIZE + sizeof(struct SaveBlock3), SAVE_SECTOR_PAYLOAD_SIZE);
    EXPECT_LE(sizeof(struct SaveBlock1), SAVE_SECTOR_PAYLOAD_SIZE * (SAVE_PROGRESS_PARTS - 1));
    EXPECT_LE(TOTAL_BOXES_COUNT * IN_BOX_COUNT, SAVE_BOX_MAX_MONS);
    EXPECT_EQ(SAVE_SECTOR_BOX_BACKUP + 1, SAVE_SECTOR_HOF_1);
    EXPECT_EQ(PB_TOTAL_BITS, PACKED_BOX_MON_SIZE * 8);
}

TEST("Save engine CRC-32 matches the standard algorithm")
{
    static const u8 sCheck[] = "123456789";
    EXPECT_EQ(~SaveEngine_Crc32(sCheck, 9, 0xFFFFFFFF), 0xCBF43926);
}

// ---------------------------------------------------------------------------
// Packed Pokémon

static enum Species RandomSpecies(void)
{
    enum Species species;
    do
    {
        species = 1 + Random() % (NUM_SPECIES - 1);
    } while (!IsSpeciesEnabled(species) || gSpeciesInfo[species].baseHP == 0);
    return species;
}

static void SetRandom(struct BoxPokemon *boxMon, s32 field, u32 max)
{
    u32 value = Random32() % (max + 1);
    SetBoxMonData(boxMon, field, &value);
}

// Sets every stored field to a random valid value.
static void CreateRandomBoxMon(struct BoxPokemon *boxMon)
{
    u8 text[POKEMON_NAME_LENGTH + 1];
    u32 i;

    CreateBoxMon(boxMon, RandomSpecies(), 1 + Random() % 100, Random32(), OTID_STRUCT_PRESET(Random32()));

    for (i = 0; i < POKEMON_NAME_LENGTH; i++)
        text[i] = Random() % 0xFF;
    text[POKEMON_NAME_LENGTH] = EOS;
    SetBoxMonData(boxMon, MON_DATA_NICKNAME, text);
    for (i = 0; i < PLAYER_NAME_LENGTH; i++)
        text[i] = Random() % 0xFF;
    SetBoxMonData(boxMon, MON_DATA_OT_NAME, text);

    SetRandom(boxMon, MON_DATA_LANGUAGE, 7);
    SetRandom(boxMon, MON_DATA_HIDDEN_NATURE, NUM_NATURES - 1);
    SetRandom(boxMon, MON_DATA_DEAD, 1);
    SetRandom(boxMon, MON_DATA_DAYS_SINCE_FORM_CHANGE, 7);
    SetRandom(boxMon, MON_DATA_MARKINGS, 15);
    SetRandom(boxMon, MON_DATA_IS_SHINY, 1);
    SetRandom(boxMon, MON_DATA_TERA_TYPE, NUMBER_OF_MON_TYPES - 1);
    SetRandom(boxMon, MON_DATA_HELD_ITEM, ITEMS_COUNT - 1);
    SetRandom(boxMon, MON_DATA_EXP, (1 << 21) - 1);
    SetRandom(boxMon, MON_DATA_PP_BONUSES, 255);
    SetRandom(boxMon, MON_DATA_FRIENDSHIP, 255);
    SetRandom(boxMon, MON_DATA_POKEBALL, POKEBALL_COUNT - 1);
    for (i = 0; i < MAX_MON_MOVES; i++)
        SetRandom(boxMon, MON_DATA_MOVE1 + i, MOVES_COUNT - 1);
    SetRandom(boxMon, MON_DATA_EVOLUTION_TRACKER, 1023);
    for (i = 0; i < NUM_STATS; i++)
    {
        SetRandom(boxMon, MON_DATA_HYPER_TRAINED_HP + i, 1);
        SetRandom(boxMon, MON_DATA_HP_EV + i, 255);
        SetRandom(boxMon, MON_DATA_HP_IV + i, 31);
    }
    SetRandom(boxMon, MON_DATA_POKERUS, 255);
    SetRandom(boxMon, MON_DATA_MET_LOCATION, 255);
    SetRandom(boxMon, MON_DATA_MET_LEVEL, 127);
    SetRandom(boxMon, MON_DATA_MET_GAME, 15);
    SetRandom(boxMon, MON_DATA_DYNAMAX_LEVEL, MAX_DYNAMAX_LEVEL);
    SetRandom(boxMon, MON_DATA_OT_GENDER, 1);
    SetRandom(boxMon, MON_DATA_IS_EGG, 1);
    SetRandom(boxMon, MON_DATA_GIGANTAMAX_FACTOR, 1);
    SetRandom(boxMon, MON_DATA_CHAMPION_RIBBON, 1);
    SetRandom(boxMon, MON_DATA_IS_SHADOW, 1);
    SetRandom(boxMon, MON_DATA_ABILITY_NUM, 2);
    SetRandom(boxMon, MON_DATA_MODERN_FATEFUL_ENCOUNTER, 1);

    // Data the packed format does not keep
    SetRandom(boxMon, MON_DATA_COOL, 255);
    SetRandom(boxMon, MON_DATA_SHEEN, 255);
    SetRandom(boxMon, MON_DATA_TOUGH_RIBBON, 4);
    SetRandom(boxMon, MON_DATA_EARTH_RIBBON, 1);
    SetRandom(boxMon, MON_DATA_HP_LOST, 100);
    SetRandom(boxMon, MON_DATA_PP1, 5);
}

static const s32 sStoredFields[] =
{
    MON_DATA_PERSONALITY, MON_DATA_OT_ID, MON_DATA_LANGUAGE, MON_DATA_SANITY_IS_BAD_EGG,
    MON_DATA_SANITY_HAS_SPECIES, MON_DATA_SANITY_IS_EGG, MON_DATA_MARKINGS, MON_DATA_IS_SHINY,
    MON_DATA_HIDDEN_NATURE, MON_DATA_DAYS_SINCE_FORM_CHANGE, MON_DATA_SPECIES, MON_DATA_HELD_ITEM,
    MON_DATA_MOVE1, MON_DATA_MOVE2, MON_DATA_MOVE3, MON_DATA_MOVE4, MON_DATA_PP_BONUSES, MON_DATA_EXP,
    MON_DATA_HP_EV, MON_DATA_ATK_EV, MON_DATA_DEF_EV, MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV,
    MON_DATA_FRIENDSHIP, MON_DATA_POKERUS, MON_DATA_MET_LOCATION, MON_DATA_MET_LEVEL, MON_DATA_MET_GAME,
    MON_DATA_POKEBALL, MON_DATA_HP_IV, MON_DATA_ATK_IV, MON_DATA_DEF_IV, MON_DATA_SPEED_IV, MON_DATA_SPATK_IV,
    MON_DATA_SPDEF_IV, MON_DATA_IS_EGG, MON_DATA_ABILITY_NUM, MON_DATA_OT_GENDER, MON_DATA_SPECIES_OR_EGG,
    MON_DATA_IVS, MON_DATA_CHAMPION_RIBBON, MON_DATA_MODERN_FATEFUL_ENCOUNTER, MON_DATA_HYPER_TRAINED_HP,
    MON_DATA_HYPER_TRAINED_ATK, MON_DATA_HYPER_TRAINED_DEF, MON_DATA_HYPER_TRAINED_SPEED,
    MON_DATA_HYPER_TRAINED_SPATK, MON_DATA_HYPER_TRAINED_SPDEF, MON_DATA_IS_SHADOW, MON_DATA_DYNAMAX_LEVEL,
    MON_DATA_GIGANTAMAX_FACTOR, MON_DATA_TERA_TYPE, MON_DATA_EVOLUTION_TRACKER, MON_DATA_DEAD,
};

static const s32 sFastFields[] =
{
    MON_DATA_PERSONALITY, MON_DATA_OT_ID, MON_DATA_LANGUAGE, MON_DATA_SANITY_IS_BAD_EGG,
    MON_DATA_SANITY_HAS_SPECIES, MON_DATA_SANITY_IS_EGG, MON_DATA_MARKINGS, MON_DATA_DEAD,
    MON_DATA_SPECIES, MON_DATA_SPECIES_OR_EGG, MON_DATA_IS_EGG, MON_DATA_HELD_ITEM, MON_DATA_EXP,
    MON_DATA_MOVE1, MON_DATA_MOVE2, MON_DATA_MOVE3, MON_DATA_MOVE4,
};

TEST("Empty PC slots pack to zero bytes and back")
{
    struct BoxPokemon boxMon;
    struct PackedBoxMon packed;
    u32 i;

    ZeroBoxMonData(&boxMon);
    memset(&packed, 0xAA, sizeof(packed));
    PackBoxMon(&packed, &boxMon);
    for (i = 0; i < PACKED_BOX_MON_SIZE; i++)
        EXPECT_EQ(packed.data[i], 0);

    memset(&boxMon, 0xAA, sizeof(boxMon));
    EXPECT_EQ(UnpackBoxMon(&boxMon, &packed), UNPACK_EMPTY);
    for (i = 0; i < sizeof(boxMon); i++)
        EXPECT_EQ(((u8 *)&boxMon)[i], 0);
}

TEST("Packed bit fields do not overlap and fill 480 bits")
{
    static const u16 sFields[][2] =
    {
        {PB_PERSONALITY}, {PB_OT_ID}, {PB_NICKNAME_CHAR(0)}, {PB_NICKNAME_CHAR(1)}, {PB_NICKNAME_CHAR(2)},
        {PB_NICKNAME_CHAR(3)}, {PB_NICKNAME_CHAR(4)}, {PB_NICKNAME_CHAR(5)}, {PB_NICKNAME_CHAR(6)},
        {PB_NICKNAME_CHAR(7)}, {PB_NICKNAME_CHAR(8)}, {PB_NICKNAME_CHAR(9)}, {PB_NICKNAME_CHAR(10)},
        {PB_NICKNAME_CHAR(11)}, {PB_OT_NAME_CHAR(0)}, {PB_OT_NAME_CHAR(1)}, {PB_OT_NAME_CHAR(2)},
        {PB_OT_NAME_CHAR(3)}, {PB_OT_NAME_CHAR(4)}, {PB_OT_NAME_CHAR(5)}, {PB_OT_NAME_CHAR(6)},
        {PB_LANGUAGE}, {PB_HIDDEN_NATURE_MODIFIER}, {PB_IS_BAD_EGG}, {PB_IS_EGG}, {PB_DEAD},
        {PB_DAYS_SINCE_FORM_CHANGE}, {PB_MARKINGS}, {PB_SHINY_MODIFIER}, {PB_SPECIES}, {PB_TERA_TYPE},
        {PB_HELD_ITEM}, {PB_EXPERIENCE}, {PB_PP_BONUSES}, {PB_FRIENDSHIP}, {PB_POKEBALL},
        {PB_MOVE(0)}, {PB_MOVE(1)}, {PB_MOVE(2)}, {PB_MOVE(3)}, {PB_EVOLUTION_TRACKER_1},
        {PB_EVOLUTION_TRACKER_2}, {PB_HYPER_TRAINED(0)}, {PB_HYPER_TRAINED(1)}, {PB_HYPER_TRAINED(2)},
        {PB_HYPER_TRAINED(3)}, {PB_HYPER_TRAINED(4)}, {PB_HYPER_TRAINED(5)}, {PB_EV(0)}, {PB_EV(1)},
        {PB_EV(2)}, {PB_EV(3)}, {PB_EV(4)}, {PB_EV(5)}, {PB_POKERUS}, {PB_MET_LOCATION}, {PB_MET_LEVEL},
        {PB_MET_GAME}, {PB_DYNAMAX_LEVEL}, {PB_OT_GENDER}, {PB_IV(0)}, {PB_IV(1)}, {PB_IV(2)}, {PB_IV(3)},
        {PB_IV(4)}, {PB_IV(5)}, {PB_GIGANTAMAX_FACTOR}, {PB_CHAMPION_RIBBON}, {PB_IS_SHADOW},
        {PB_ABILITY_NUM}, {PB_MODERN_FATEFUL_ENCOUNTER},
    };
    u8 used[PACKED_BOX_MON_SIZE] = {0};
    u32 i, bit, total = 0;

    for (i = 0; i < ARRAY_COUNT(sFields); i++)
    {
        for (bit = sFields[i][0]; bit < sFields[i][0] + sFields[i][1]; bit++)
        {
            EXPECT_LT(bit, PB_TOTAL_BITS);
            EXPECT_EQ(used[bit / 8] & (1 << (bit % 8)), 0);
            used[bit / 8] |= 1 << (bit % 8);
            total++;
        }
    }
    EXPECT_EQ(total, PB_TOTAL_BITS);
}

TEST("Packed bit helpers read back what they write")
{
    u8 data[PACKED_BOX_MON_SIZE];
    u32 offset, width, value;

    for (offset = 0; offset < 64; offset += 3)
    {
        for (width = 1; width <= 32; width++)
        {
            memset(data, Random() & 1 ? 0xFF : 0x00, sizeof(data));
            value = Random32() & (width == 32 ? 0xFFFFFFFF : ((1u << width) - 1));
            SetPackedBits(data, offset, width, value);
            EXPECT_EQ(GetPackedBits(data, offset, width), value);
        }
    }
}

TEST("PC Pokémon keep every stored field when packed and unpacked")
{
    struct BoxPokemon original, unpacked;
    struct PackedBoxMon packed, repacked;
    u32 i, n;

    for (n = 0; n < 16; n++) PARAMETRIZE {}

    for (n = 0; n < 12; n++)
    {
        CreateRandomBoxMon(&original);
        PackBoxMon(&packed, &original);
        EXPECT_EQ(UnpackBoxMon(&unpacked, &packed), UNPACK_OK);

        for (i = 0; i < ARRAY_COUNT(sStoredFields); i++)
        {
            if (GetBoxMonData(&original, sStoredFields[i]) != GetBoxMonData(&unpacked, sStoredFields[i]))
                Test_MgbaPrintf("field %d: %d != %d", sStoredFields[i], GetBoxMonData(&original, sStoredFields[i]), GetBoxMonData(&unpacked, sStoredFields[i]));
            EXPECT_EQ(GetBoxMonData(&original, sStoredFields[i]), GetBoxMonData(&unpacked, sStoredFields[i]));
        }

        // Raw names, including for Eggs
        {
            u8 a[POKEMON_NAME_LENGTH + 1], b[POKEMON_NAME_LENGTH + 1];
            GetBoxMonData(&original, MON_DATA_OT_NAME, a);
            GetBoxMonData(&unpacked, MON_DATA_OT_NAME, b);
            EXPECT_EQ(memcmp(a, b, PLAYER_NAME_LENGTH), 0);
        }

        // Packing is stable
        PackBoxMon(&repacked, &unpacked);
        EXPECT_EQ(memcmp(&packed, &repacked, sizeof(packed)), 0);
    }
}

TEST("Nicknames survive packing")
{
    struct BoxPokemon original, unpacked;
    struct PackedBoxMon packed;
    u8 name[POKEMON_NAME_LENGTH + 1], result[POKEMON_NAME_LENGTH + 1];
    u32 i, n;

    for (n = 0; n < 20; n++)
    {
        u32 isEgg = FALSE;
        CreateRandomBoxMon(&original);
        SetBoxMonData(&original, MON_DATA_IS_EGG, &isEgg);
        for (i = 0; i < POKEMON_NAME_LENGTH; i++)
            name[i] = 1 + Random() % 0xFE;
        name[POKEMON_NAME_LENGTH] = EOS;
        SetBoxMonData(&original, MON_DATA_NICKNAME, name);
        i = LANGUAGE_ENGLISH;
        SetBoxMonData(&original, MON_DATA_LANGUAGE, &i);

        PackBoxMon(&packed, &original);
        UnpackBoxMon(&unpacked, &packed);
        GetBoxMonData(&unpacked, MON_DATA_NICKNAME, result);
        EXPECT_EQ(memcmp(name, result, POKEMON_NAME_LENGTH), 0);
    }
}

TEST("Packing heals and drops contest data and other ribbons")
{
    struct BoxPokemon original, unpacked;
    struct PackedBoxMon packed;
    u32 i, value, n;

    for (n = 0; n < 20; n++)
    {
        CreateRandomBoxMon(&original);
        value = FALSE;
        SetBoxMonData(&original, MON_DATA_IS_EGG, &value);
        value = 200;
        for (i = MON_DATA_COOL; i <= MON_DATA_SMART; i++)
        {
            if (i == MON_DATA_COOL || i == MON_DATA_BEAUTY || i == MON_DATA_CUTE || i == MON_DATA_SMART)
                SetBoxMonData(&original, i, &value);
        }
        value = 1;
        SetBoxMonData(&original, MON_DATA_WORLD_RIBBON, &value);
        SetBoxMonData(&original, MON_DATA_WINNING_RIBBON, &value);
        value = 3;
        SetBoxMonData(&original, MON_DATA_COOL_RIBBON, &value);
        value = 55;
        SetBoxMonData(&original, MON_DATA_HP_LOST, &value);
        value = STATUS1_BURN;
        SetBoxMonData(&original, MON_DATA_STATUS, &value);

        PackBoxMon(&packed, &original);
        UnpackBoxMon(&unpacked, &packed);

        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_COOL), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_BEAUTY), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_CUTE), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_SMART), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_TOUGH), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_SHEEN), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_RIBBONS), GetBoxMonData(&original, MON_DATA_CHAMPION_RIBBON));
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_HP_LOST), 0);
        EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_STATUS), STATUS1_NONE);
        for (i = 0; i < MAX_MON_MOVES; i++)
        {
            enum Move move = GetBoxMonData(&unpacked, MON_DATA_MOVE1 + i);
            u32 pp = (move == MOVE_NONE) ? 0 : CalculatePPWithBonus(move, GetBoxMonData(&unpacked, MON_DATA_PP_BONUSES), i);
            EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_PP1 + i), pp);
        }
    }
}

TEST("Packed fields read without unpacking match unpacked fields")
{
    struct BoxPokemon boxMon;
    struct PackedBoxMon packed;
    u32 i, n, value;
    u16 moves[5];

    for (n = 0; n < 40; n++)
    {
        if (n % 10 == 0)
            ZeroBoxMonData(&boxMon);
        else
            CreateRandomBoxMon(&boxMon);
        PackBoxMon(&packed, &boxMon);
        UnpackBoxMon(&boxMon, &packed);
        for (i = 0; i < ARRAY_COUNT(sFastFields); i++)
        {
            EXPECT(TryGetPackedBoxMonData(&packed, sFastFields[i], NULL, &value));
            EXPECT_EQ(value, GetBoxMonData(&boxMon, sFastFields[i]));
        }
        for (i = 0; i < 4; i++)
            moves[i] = (i == 0) ? GetBoxMonData(&boxMon, MON_DATA_MOVE3) : Random() % MOVES_COUNT;
        moves[4] = MOVES_COUNT;
        EXPECT(TryGetPackedBoxMonData(&packed, MON_DATA_KNOWN_MOVES, (u8 *)moves, &value));
        EXPECT_EQ(value, GetBoxMonData(&boxMon, MON_DATA_KNOWN_MOVES, (u8 *)moves));
    }
}

TEST("Bad Eggs stay Bad Eggs in the PC")
{
    struct BoxPokemon boxMon, unpacked;
    struct PackedBoxMon packed;
    u32 value;

    CreateRandomBoxMon(&boxMon);
    value = GetBoxMonData(&boxMon, MON_DATA_CHECKSUM) + 1;
    SetBoxMonData(&boxMon, MON_DATA_CHECKSUM, &value);

    PackBoxMon(&packed, &boxMon);
    EXPECT_EQ(GetPackedBits(packed.data, PB_IS_BAD_EGG), 1);
    EXPECT_EQ(UnpackBoxMon(&unpacked, &packed), UNPACK_OK);
    EXPECT(GetBoxMonData(&unpacked, MON_DATA_SANITY_IS_BAD_EGG));
    EXPECT(GetBoxMonData(&unpacked, MON_DATA_SANITY_HAS_SPECIES));
    EXPECT_EQ(GetBoxMonData(&unpacked, MON_DATA_SPECIES), SPECIES_EGG);
    EXPECT(GetBoxMonData(&unpacked, MON_DATA_IS_EGG));
}

TEST("Invalid packed records are repaired or rejected")
{
    struct BoxPokemon boxMon;
    struct PackedBoxMon packed;

    CreateRandomBoxMon(&boxMon);
    PackBoxMon(&packed, &boxMon);
    SetPackedBits(packed.data, PB_HELD_ITEM, 1023);
    SetPackedBits(packed.data, PB_MOVE(2), 2047);
    SetPackedBits(packed.data, PB_ABILITY_NUM, 3);
    EXPECT_EQ(UnpackBoxMon(&boxMon, &packed), UNPACK_REPAIRED);
    EXPECT_EQ(GetBoxMonData(&boxMon, MON_DATA_HELD_ITEM), ITEM_NONE);
    EXPECT_EQ(GetBoxMonData(&boxMon, MON_DATA_MOVE3), MOVE_NONE);
    EXPECT_EQ(GetBoxMonData(&boxMon, MON_DATA_ABILITY_NUM), 0);

    SetPackedBits(packed.data, PB_SPECIES, SPECIES_NONE);
    EXPECT_EQ(UnpackBoxMon(&boxMon, &packed), UNPACK_INVALID);
    EXPECT_EQ(GetBoxMonData(&boxMon, MON_DATA_SPECIES), SPECIES_NONE);
    EXPECT_EQ(GetBoxMonData(&boxMon, MON_DATA_SANITY_HAS_SPECIES), FALSE);
}

// ---------------------------------------------------------------------------
// PC storage accessors and the box cache

TEST("PC accessors agree whether or not a box is cached")
{
    struct BoxPokemon mons[4], copy;
    u32 i, value;
    u8 boxes[4] = {0, 1, TOTAL_BOXES_COUNT - 1, TOTAL_BOXES_COUNT / 2};
    u8 slots[4] = {0, IN_BOX_COUNT - 1, 7, 13};

    ResetPokemonStorageSystem();
    for (i = 0; i < 4; i++)
    {
        CreateRandomBoxMon(&mons[i]);
        SetBoxMonAt(boxes[i], slots[i], &mons[i]);
    }
    FlushBoxCache();

    for (i = 0; i < 4; i++)
    {
        struct PackedBoxMon packed;
        struct BoxPokemon expected;
        PackBoxMon(&packed, &mons[i]);
        UnpackBoxMon(&expected, &packed);

        EXPECT_EQ(GetBoxMonDataAt(boxes[i], slots[i], MON_DATA_PERSONALITY), GetBoxMonData(&expected, MON_DATA_PERSONALITY));
        EXPECT_EQ(GetBoxMonDataAt(boxes[i], slots[i], MON_DATA_SPECIES), GetBoxMonData(&expected, MON_DATA_SPECIES));
        EXPECT_EQ(GetBoxMonDataAt(boxes[i], slots[i], MON_DATA_EXP), GetBoxMonData(&expected, MON_DATA_EXP));
        EXPECT_EQ(GetBoxMonDataAt(boxes[i], slots[i], MON_DATA_FRIENDSHIP), GetBoxMonData(&expected, MON_DATA_FRIENDSHIP));

        // Through the cache
        EXPECT_EQ(GetBoxMonData(GetBoxedMonPtr(boxes[i], slots[i]), MON_DATA_PERSONALITY), GetBoxMonData(&expected, MON_DATA_PERSONALITY));
        EXPECT_EQ(GetBoxMonDataAt(boxes[i], slots[i], MON_DATA_FRIENDSHIP), GetBoxMonData(&expected, MON_DATA_FRIENDSHIP));
        CopyBoxMonAt(boxes[i], slots[i], &copy);
        EXPECT_EQ(GetBoxMonData(&copy, MON_DATA_OT_ID), GetBoxMonData(&expected, MON_DATA_OT_ID));
    }

    // A change through a cache pointer persists after another box is used
    value = 77;
    SetBoxMonData(GetBoxedMonPtr(boxes[0], slots[0]), MON_DATA_FRIENDSHIP, &value);
    EXPECT_EQ(GetBoxMonDataAt(boxes[1], slots[1], MON_DATA_SPECIES), GetBoxMonData(&mons[1], MON_DATA_SPECIES));
    GetBoxedMonPtr(boxes[2], 0);
    EXPECT_EQ(GetBoxMonDataAt(boxes[0], slots[0], MON_DATA_FRIENDSHIP), 77);
    FlushBoxCache();
    InvalidateBoxCache();
    EXPECT_EQ(GetBoxMonDataAt(boxes[0], slots[0], MON_DATA_FRIENDSHIP), 77);

    // Changes to uncached boxes
    value = 12;
    SetBoxMonDataAt(boxes[3], slots[3], MON_DATA_FRIENDSHIP, &value);
    EXPECT_EQ(GetBoxMonDataAt(boxes[3], slots[3], MON_DATA_FRIENDSHIP), 12);
    ZeroBoxMonAt(boxes[3], slots[3]);
    EXPECT_EQ(GetBoxMonDataAt(boxes[3], slots[3], MON_DATA_SPECIES), SPECIES_NONE);
    EXPECT_EQ(CountAllStorageMons(), 3);

    ResetPokemonStorageSystem();
    EXPECT_EQ(CountAllStorageMons(), 0);
}

TEST("Every PC slot can hold a Pokémon")
{
    struct BoxPokemon boxMon;
    u32 box, slot;

    ResetPokemonStorageSystem();
    CreateBoxMon(&boxMon, SPECIES_WOBBUFFET, 5, 0, OTID_STRUCT_PRESET(0));
    for (box = 0; box < TOTAL_BOXES_COUNT; box++)
    {
        for (slot = 0; slot < IN_BOX_COUNT; slot++)
        {
            u32 personality = box * IN_BOX_COUNT + slot + 1;
            SetBoxMonData(&boxMon, MON_DATA_PERSONALITY, &personality);
            SetBoxMonAt(box, slot, &boxMon);
        }
    }
    EXPECT_EQ(CountAllStorageMons(), TOTAL_BOXES_COUNT * IN_BOX_COUNT);
    EXPECT_EQ(CheckFreePokemonStorageSpace(), FALSE);
    for (box = 0; box < TOTAL_BOXES_COUNT; box++)
    {
        for (slot = 0; slot < IN_BOX_COUNT; slot++)
            EXPECT_EQ(GetBoxMonDataAt(box, slot, MON_DATA_PERSONALITY), box * IN_BOX_COUNT + slot + 1);
    }
    ResetPokemonStorageSystem();
}

// ---------------------------------------------------------------------------
// Saving and loading through the flash chip

struct SaveDigest
{
    u32 progress;
    u32 sectors[SAVE_BOX_SECTOR_COUNT];
    u32 parts[4]; // SaveBlock1, SaveBlock2, SaveBlock3, box header (diagnostics)
};

static void TakeDigest(struct SaveDigest *digest)
{
    u32 i;
    const u8 *boxes = (const u8 *)gPokemonStoragePtr->boxes;
    u32 monCount = TOTAL_BOXES_COUNT * IN_BOX_COUNT;

    FlushBoxCache();
    digest->progress = SaveEngine_Crc32((u8 *)gSaveBlock1Ptr, sizeof(struct SaveBlock1), 0xFFFFFFFF);
    digest->progress = SaveEngine_Crc32((u8 *)gSaveBlock2Ptr, sizeof(struct SaveBlock2), digest->progress);
    digest->progress = SaveEngine_Crc32((u8 *)gSaveBlock3Ptr, sizeof(struct SaveBlock3), digest->progress);
    digest->progress = SaveEngine_Crc32((u8 *)gPokemonStoragePtr, POKEMON_STORAGE_HEADER_SIZE, digest->progress);
    digest->parts[0] = SaveEngine_Crc32((u8 *)gSaveBlock1Ptr, sizeof(struct SaveBlock1), 0xFFFFFFFF);
    digest->parts[1] = SaveEngine_Crc32((u8 *)gSaveBlock2Ptr, sizeof(struct SaveBlock2), 0xFFFFFFFF);
    digest->parts[2] = SaveEngine_Crc32((u8 *)gSaveBlock3Ptr, sizeof(struct SaveBlock3), 0xFFFFFFFF);
    digest->parts[3] = SaveEngine_Crc32((u8 *)gPokemonStoragePtr, POKEMON_STORAGE_HEADER_SIZE, 0xFFFFFFFF);
    for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
    {
        u32 first = i * SAVE_BOX_MONS_PER_SECTOR;
        u32 count = first >= monCount ? 0 : min(SAVE_BOX_MONS_PER_SECTOR, monCount - first);
        digest->sectors[i] = SaveEngine_Crc32(boxes + first * SAVE_BOX_MON_SIZE, count * SAVE_BOX_MON_SIZE, 0xFFFFFFFF);
    }
}

// Turns the console off and on again.
static u8 Reboot(void)
{
    gSaveTestPowerCutEnabled = FALSE;
    gSaveTestPowerLost = FALSE;
    memset(gSaveBlock1Ptr, 0x5A, sizeof(struct SaveBlock1));
    memset(gSaveBlock2Ptr, 0x5A, sizeof(struct SaveBlock2));
    memset(gSaveBlock3Ptr, 0x5A, sizeof(struct SaveBlock3));
    memset(gPokemonStoragePtr, 0x5A, sizeof(struct PokemonStorage));
    InvalidateBoxCache();
    ZeroPlayerPartyMons();
    Save_ResetSaveCounters();
    return LoadGameSave(SAVE_NORMAL);
}

static void StartTestGame(void)
{
    ASSUME(gFlashMemoryPresent == TRUE);
    // Earlier tests can leave a follower object behind. Followers are saved
    // inactive and reactivated on load, so a save/load round trip would not
    // be byte-identical with one present.
    memset(gObjectEvents, 0, sizeof(gObjectEvents));
    ClearSaveData();
    ClearSav1();
    ClearSav2();
    ClearSav3();
    ResetPokemonStorageSystem();
    // ZeroMonData keeps an HP-lost value from the slot's previous Pokémon,
    // which LoadPlayerParty then resets; start from truly empty slots so a
    // save/load round trip is byte-identical.
    memset(gParties[B_TRAINER_PLAYER], 0, sizeof(gParties[B_TRAINER_PLAYER]));
    gPartiesCount[B_TRAINER_PLAYER] = 0;
    Save_StartNewGameIdentity();
}

static void PutRandomMon(u8 box, u8 slot)
{
    struct BoxPokemon boxMon;
    CreateRandomBoxMon(&boxMon);
    SetBoxMonAt(box, slot, &boxMon);
}

static void GiveRandomPartyMon(void)
{
    u32 slot = gPartiesCount[B_TRAINER_PLAYER];
    if (slot >= PARTY_SIZE)
        return;
    CreateMon(&gParties[B_TRAINER_PLAYER][slot], RandomSpecies(), 50, Random32(), OTID_STRUCT_PRESET(Random32()));
    gPartiesCount[B_TRAINER_PLAYER]++;
}

static void ChangeProgress(void)
{
    gSaveBlock2Ptr->playTimeSeconds = Random() % 60;
    gSaveBlock2Ptr->playTimeMinutes = Random() % 60;
    gSaveBlock2Ptr->playTimeHours = Random() % 999;
    gSaveBlock1Ptr->money = Random32();
    FlagToggle(FLAG_BADGE05_GET);
    VarSet(VAR_PC_BOX_TO_SEND_MON, Random() % TOTAL_BOXES_COUNT);
}

static bool32 DigestEqual(const struct SaveDigest *a, const struct SaveDigest *b)
{
    return memcmp(a, b, sizeof(*a)) == 0;
}

TEST("A saved game loads back exactly")
{
    struct SaveDigest saved, loaded;
    u32 i;

    StartTestGame();
    for (i = 0; i < 3; i++)
        GiveRandomPartyMon();
    for (i = 0; i < 60; i++)
        PutRandomMon(Random() % TOTAL_BOXES_COUNT, Random() % IN_BOX_COUNT);
    ChangeProgress();

    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    TakeDigest(&saved);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    TakeDigest(&loaded);
    EXPECT(DigestEqual(&saved, &loaded));
    EXPECT_EQ(gPartiesCount[B_TRAINER_PLAYER], 3);

    // Saving again without changes loads the same game
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    TakeDigest(&loaded);
    EXPECT(DigestEqual(&saved, &loaded));

    // Many saves in a row alternate copies and keep working
    for (i = 0; i < 12; i++)
    {
        ChangeProgress();
        PutRandomMon(Random() % TOTAL_BOXES_COUNT, Random() % IN_BOX_COUNT);
        EXPECT_EQ(TrySavingData(i % 3 == 0 ? SAVE_LINK : SAVE_NORMAL), SAVE_STATUS_OK);
        TakeDigest(&saved);
        EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
        TakeDigest(&loaded);
        EXPECT(DigestEqual(&saved, &loaded));
    }
}

TEST("A full PC saves and loads")
{
    struct SaveDigest saved, loaded;
    u32 box, slot;

    StartTestGame();
    GiveRandomPartyMon();
    for (box = 0; box < TOTAL_BOXES_COUNT; box++)
    {
        for (slot = 0; slot < IN_BOX_COUNT; slot++)
            PutRandomMon(box, slot);
    }
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    TakeDigest(&saved);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    TakeDigest(&loaded);
    EXPECT(DigestEqual(&saved, &loaded));
    EXPECT_EQ(CountAllStorageMons(), TOTAL_BOXES_COUNT * IN_BOX_COUNT);
}

TEST("The link trade save commits only when its last byte is written")
{
    struct SaveDigest before, after, loaded;

    StartTestGame();
    GiveRandomPartyMon();
    PutRandomMon(0, 0);
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    TakeDigest(&before);

    PutRandomMon(3, 4);
    ChangeProgress();
    LinkFullSave_Init();
    while (!LinkFullSave_WriteSector())
        ;
    LinkFullSave_ReplaceLastSector();
    TakeDigest(&after);

    // Partner disconnected before the commit: the old game loads
    EXPECT_EQ(Reboot(), SAVE_STATUS_ERROR); // One copy is incomplete
    TakeDigest(&loaded);
    EXPECT(DigestEqual(&before, &loaded));

    // Redo the trade and commit it
    PutRandomMon(3, 4);
    ChangeProgress();
    LinkFullSave_Init();
    while (!LinkFullSave_WriteSector())
        ;
    LinkFullSave_ReplaceLastSector();
    LinkFullSave_SetLastSectorSignature();
    TakeDigest(&after);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    TakeDigest(&loaded);
    EXPECT(DigestEqual(&after, &loaded));
}

TEST("Incremental link saves write the whole game")
{
    struct SaveDigest after, loaded;
    u32 frames = 0;

    StartTestGame();
    GiveRandomPartyMon();
    PutRandomMon(5, 5);
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);

    PutRandomMon(12, 1);
    ChangeProgress();
    WriteSaveBlock2();
    while (!WriteSaveBlock1Sector())
        frames++;
    EXPECT_GT(frames, 0);
    TakeDigest(&after);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    TakeDigest(&loaded);
    EXPECT(DigestEqual(&after, &loaded));
}

// Power cuts ------------------------------------------------------------------
//
// Each case builds an old game, saves it, changes it, and cuts the power after
// a chosen number of flash operations while saving the change (one erase or
// one byte counts as an operation; a sector write is 4097). After turning the
// console back on, the loaded game must be the old game or the new game (the
// PC may mix old and new sectors), and saving it again must work.

#define FLASH_OPS_PER_SECTOR (SAVE_SECTOR_SIZE + 1)
#define CUTS_PER_SECTOR 5
#define MAX_CUT_SECTORS 14

static const u16 sCutOffsets[CUTS_PER_SECTOR] = {0, 1, 1900, SAVE_SECTOR_PAYLOAD_SIZE + 1, SAVE_SECTOR_SIZE};

enum
{
    SAVE_KIND_NORMAL,
    SAVE_KIND_LINK_TRADE,
    SAVE_KIND_NEW_GAME,
};

#define MAX_TRACKED_MONS (TOTAL_BOXES_COUNT * IN_BOX_COUNT + PARTY_SIZE)

static u32 CollectPersonalities(u32 *out)
{
    u32 count = 0, i, box, slot;
    for (i = 0; i < gPartiesCount[B_TRAINER_PLAYER]; i++)
    {
        if (GetMonData(&gParties[B_TRAINER_PLAYER][i], MON_DATA_SPECIES) != SPECIES_NONE)
            out[count++] = GetMonData(&gParties[B_TRAINER_PLAYER][i], MON_DATA_PERSONALITY);
    }
    for (box = 0; box < TOTAL_BOXES_COUNT; box++)
    {
        for (slot = 0; slot < IN_BOX_COUNT; slot++)
        {
            if (GetBoxMonDataAt(box, slot, MON_DATA_SANITY_HAS_SPECIES))
                out[count++] = GetBoxMonDataAt(box, slot, MON_DATA_PERSONALITY);
        }
    }
    return count;
}

static bool32 ContainsValue(const u32 *list, u32 count, u32 value)
{
    u32 i;
    for (i = 0; i < count; i++)
    {
        if (list[i] == value)
            return TRUE;
    }
    return FALSE;
}

static void DepositPartyMon(u8 partySlot, u8 box, u8 boxSlot)
{
    SetBoxMonAt(box, boxSlot, &gParties[B_TRAINER_PLAYER][partySlot].box);
    memset(&gParties[B_TRAINER_PLAYER][partySlot], 0, sizeof(struct Pokemon));
    CompactPartySlots();
    gPartiesCount[B_TRAINER_PLAYER]--;
}

static void WithdrawMon(u8 box, u8 boxSlot)
{
    u32 slot = gPartiesCount[B_TRAINER_PLAYER];
    BoxMonAtToMon(box, boxSlot, &gParties[B_TRAINER_PLAYER][slot]);
    ZeroBoxMonAt(box, boxSlot);
    gPartiesCount[B_TRAINER_PLAYER]++;
}

static void MoveBoxMon(u8 fromBox, u8 fromSlot, u8 toBox, u8 toSlot)
{
    struct BoxPokemon boxMon;
    CopyBoxMonAt(fromBox, fromSlot, &boxMon);
    ZeroBoxMonAt(fromBox, fromSlot);
    SetBoxMonAt(toBox, toSlot, &boxMon);
}

// A game with Pokémon spread over the first, middle and last box sectors.
static void BuildOldGame(void)
{
    u32 i;
    StartTestGame();
    for (i = 0; i < 4; i++)
        GiveRandomPartyMon();
    for (i = 0; i < 10; i++)
    {
        PutRandomMon(0, i);
        PutRandomMon(TOTAL_BOXES_COUNT / 2, i);
        PutRandomMon(TOTAL_BOXES_COUNT - 1, i);
    }
    ChangeProgress();
}

static void Change_Deposit(void)
{
    DepositPartyMon(1, TOTAL_BOXES_COUNT - 1, 20);
    ChangeProgress();
}

static void Change_Withdraw(void)
{
    WithdrawMon(TOTAL_BOXES_COUNT / 2, 3);
    ChangeProgress();
}

static void Change_MoveAcrossSectors(void)
{
    MoveBoxMon(0, 2, TOTAL_BOXES_COUNT - 1, 25);
    MoveBoxMon(TOTAL_BOXES_COUNT / 2, 4, 0, 28);
}

static void Change_SwapAndGiveItem(void)
{
    struct BoxPokemon a, b;
    u32 item = ITEM_LEFTOVERS;
    CopyBoxMonAt(0, 1, &a);
    CopyBoxMonAt(0, 6, &b);
    SetBoxMonAt(0, 1, &b);
    SetBoxMonAt(0, 6, &a);
    SetBoxMonDataAt(0, 7, MON_DATA_HELD_ITEM, &item);
    ChangeProgress();
}

static void Change_ReleaseAndTakeItems(void)
{
    u32 item = ITEM_NONE;
    ZeroBoxMonAt(0, 5);
    ZeroBoxMonAt(TOTAL_BOXES_COUNT - 1, 9);
    SetBoxMonDataAt(TOTAL_BOXES_COUNT / 2, 0, MON_DATA_HELD_ITEM, &item);
    ChangeProgress();
}

// The storage menu's shift: a party Pokémon takes a PC Pokémon's slot.
static void Change_ExchangePartyAndPc(void)
{
    struct Pokemon fromBox;
    BoxMonAtToMon(TOTAL_BOXES_COUNT / 2, 8, &fromBox);
    SetBoxMonAt(TOTAL_BOXES_COUNT / 2, 8, &gParties[B_TRAINER_PLAYER][0].box);
    gParties[B_TRAINER_PLAYER][0] = fromBox;
    WithdrawMon(0, 9);
    ChangeProgress();
}

static void Change_BoxNamesAndWallpapers(void)
{
    StringCopy(GetBoxNamePtr(3), COMPOUND_STRING("SAVED"));
    gPokemonStoragePtr->boxWallpapers[TOTAL_BOXES_COUNT - 1] = 2;
    gPokemonStoragePtr->currentBox = TOTAL_BOXES_COUNT - 1;
}

static void Change_FillWholeSectors(void)
{
    u32 slot;
    for (slot = 10; slot < IN_BOX_COUNT; slot++)
    {
        PutRandomMon(1, slot);
        PutRandomMon(TOTAL_BOXES_COUNT - 2, slot);
    }
    DepositPartyMon(0, 2, 0);
    ChangeProgress();
}

static void Change_NewGame(void)
{
    u32 i;
    ClearSav1();
    ClearSav2();
    ClearSav3();
    ResetPokemonStorageSystem();
    memset(gParties[B_TRAINER_PLAYER], 0, sizeof(gParties[B_TRAINER_PLAYER]));
    gPartiesCount[B_TRAINER_PLAYER] = 0;
    Save_StartNewGameIdentity();
    GiveRandomPartyMon();
    for (i = 0; i < 3; i++)
        PutRandomMon(i * 5, i);
    ChangeProgress();
}

static void PowerCutTrial(u32 cut, void (*change)(void), u32 kind)
{
    struct SaveDigest old, new, loaded, reloaded;
    u32 *oldMons = Alloc(sizeof(u32) * MAX_TRACKED_MONS);
    u32 *newMons = Alloc(sizeof(u32) * MAX_TRACKED_MONS);
    u32 *loadedMons = Alloc(sizeof(u32) * MAX_TRACKED_MONS);
    u32 oldCount, newCount, loadedCount, i;
    u8 beforeCommit, afterCommit, status;
    bool32 progressOld, progressNew;
    u8 *loadedSb1;

    BuildOldGame();
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    TakeDigest(&old);
    oldCount = CollectPersonalities(oldMons);

    change();
    Save_TestCountSectorWrites();
    SaveEngine_GetPlanCounts(&beforeCommit, &afterCommit);
    TakeDigest(&new);
    newCount = CollectPersonalities(newMons);

    gSaveTestFlashBudget = (cut / CUTS_PER_SECTOR) * FLASH_OPS_PER_SECTOR + sCutOffsets[cut % CUTS_PER_SECTOR];
    gSaveTestPowerCutEnabled = TRUE;
    gSaveTestPowerLost = FALSE;
    switch (kind)
    {
    case SAVE_KIND_NORMAL:
        HandleSavingData(SAVE_NORMAL);
        break;
    case SAVE_KIND_NEW_GAME:
        HandleSavingData(SAVE_OVERWRITE_DIFFERENT_FILE);
        break;
    case SAVE_KIND_LINK_TRADE:
        LinkFullSave_Init();
        while (!LinkFullSave_WriteSector())
            ;
        LinkFullSave_ReplaceLastSector();
        LinkFullSave_SetLastSectorSignature();
        break;
    }
    EXPECT_EQ(gDamagedSaveSectors, 0);

    status = Reboot();
    EXPECT(status == SAVE_STATUS_OK || status == SAVE_STATUS_ERROR);
    TakeDigest(&loaded);
    loadedSb1 = Alloc(sizeof(struct SaveBlock1));
    memcpy(loadedSb1, gSaveBlock1Ptr, sizeof(struct SaveBlock1));
    loadedCount = CollectPersonalities(loadedMons);

    progressOld = loaded.progress == old.progress;
    progressNew = loaded.progress == new.progress;
    EXPECT(progressOld || progressNew);

    if (afterCommit == 0)
    {
        for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
            EXPECT(loaded.sectors[i] == old.sectors[i] || loaded.sectors[i] == new.sectors[i]);
    }
    if (progressOld && !progressNew && beforeCommit <= 1)
    {
        for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
            EXPECT_EQ(loaded.sectors[i], old.sectors[i]);
    }
    if (progressNew && !progressOld && afterCommit == 0)
    {
        for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
            EXPECT_EQ(loaded.sectors[i], new.sectors[i]);
    }

    // No Pokémon appears from nowhere
    for (i = 0; i < loadedCount; i++)
        EXPECT(ContainsValue(oldMons, oldCount, loadedMons[i]) || ContainsValue(newMons, newCount, loadedMons[i]));
    if (kind == SAVE_KIND_NEW_GAME)
    {
        // Either game, never a mix of the two
        bool32 anyOld = FALSE, anyNew = FALSE;
        for (i = 0; i < loadedCount; i++)
        {
            if (ContainsValue(oldMons, oldCount, loadedMons[i]))
                anyOld = TRUE;
            if (ContainsValue(newMons, newCount, loadedMons[i]))
                anyNew = TRUE;
        }
        EXPECT(!(anyOld && anyNew));
        if (progressOld)
            EXPECT(!anyNew);
        else
            EXPECT(!anyOld);
    }
    else
    {
        // No Pokémon in both games is lost. None of these cases makes a
        // Pokémon take the slot of a Pokémon that leaves a full sector, which
        // is the one situation where an interrupted multi-sector save can lose
        // one (see BPETools/save_sim).
        for (i = 0; i < oldCount; i++)
        {
            if (ContainsValue(newMons, newCount, oldMons[i]))
                EXPECT(ContainsValue(loadedMons, loadedCount, oldMons[i]));
        }
    }

    // Playing on and saving again stores exactly what was loaded
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    TakeDigest(&reloaded);
    if (!DigestEqual(&loaded, &reloaded))
    {
        Test_MgbaPrintf("cut %d: progressOld=%d progressNew=%d before=%d after=%d status=%d flags=%d",
                        cut, progressOld, progressNew, beforeCommit, afterCommit, status, SaveEngine_GetLoadFlags());
        for (i = 0; i < 4; i++)
        {
            if (loaded.parts[i] != reloaded.parts[i])
                Test_MgbaPrintf("block %d differs", i);
        }
        for (i = 0; i < SAVE_BOX_SECTOR_COUNT; i++)
        {
            if (loaded.sectors[i] != reloaded.sectors[i])
                Test_MgbaPrintf("box sector %d differs", i);
        }
        for (i = 0, oldCount = 0; i < sizeof(struct SaveBlock1) && oldCount < 24; i++)
        {
            if (loadedSb1[i] != ((u8 *)gSaveBlock1Ptr)[i])
            {
                Test_MgbaPrintf("SaveBlock1[%d] %d -> %d", i, loadedSb1[i], ((u8 *)gSaveBlock1Ptr)[i]);
                oldCount++;
            }
        }
    }
    EXPECT(DigestEqual(&loaded, &reloaded));

    Free(loadedSb1);
    Free(oldMons);
    Free(newMons);
    Free(loadedMons);
}

#define POWER_CUT_TEST(_name, _change, _kind)                         \
TEST("Power cut while saving: " _name)                               \
{                                                                    \
    u32 cut = 0, i;                                                  \
    for (i = 0; i < MAX_CUT_SECTORS * CUTS_PER_SECTOR; i++)           \
        PARAMETRIZE { cut = i; }                                     \
    PowerCutTrial(cut, _change, _kind);                              \
}

POWER_CUT_TEST("deposit", Change_Deposit, SAVE_KIND_NORMAL)
POWER_CUT_TEST("withdraw", Change_Withdraw, SAVE_KIND_NORMAL)
POWER_CUT_TEST("move across sectors", Change_MoveAcrossSectors, SAVE_KIND_NORMAL)
POWER_CUT_TEST("swap and give item", Change_SwapAndGiveItem, SAVE_KIND_NORMAL)
POWER_CUT_TEST("release and take items", Change_ReleaseAndTakeItems, SAVE_KIND_NORMAL)
POWER_CUT_TEST("exchange party and PC Pokemon", Change_ExchangePartyAndPc, SAVE_KIND_NORMAL)
POWER_CUT_TEST("box names and wallpapers", Change_BoxNamesAndWallpapers, SAVE_KIND_NORMAL)
POWER_CUT_TEST("fill sectors", Change_FillWholeSectors, SAVE_KIND_NORMAL)
POWER_CUT_TEST("link trade", Change_Deposit, SAVE_KIND_LINK_TRADE)
POWER_CUT_TEST("new game over an old save", Change_NewGame, SAVE_KIND_NEW_GAME)

static u8 BoxSectorOf(u8 box, u8 slot)
{
    return (box * IN_BOX_COUNT + slot) / SAVE_BOX_MONS_PER_SECTOR;
}

TEST("A damaged box sector is restored from the backup")
{
    struct SaveDigest saved, loaded;

    BuildOldGame();
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    PutRandomMon(TOTAL_BOXES_COUNT - 1, 29);
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    TakeDigest(&saved);

    // The last box write went to this sector, so the backup holds its image
    // from before that save. Damage the sector.
    ProgramFlashByte(SAVE_SECTOR_BOX_FIRST + BoxSectorOf(TOTAL_BOXES_COUNT - 1, 29), SAVE_SECTOR_SIGNATURE_OFFSET2, 0x00);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    EXPECT(SaveEngine_GetLoadFlags() & SAVE_LOAD_FLAG_BOX_RESTORED);
    TakeDigest(&loaded);
    EXPECT_EQ(loaded.progress, saved.progress);
    EXPECT_EQ(GetBoxMonDataAt(TOTAL_BOXES_COUNT - 1, 29, MON_DATA_SPECIES), SPECIES_NONE);
    EXPECT_EQ(GetBoxMonDataAt(TOTAL_BOXES_COUNT - 1, 0, MON_DATA_SANITY_HAS_SPECIES), TRUE);

    // The next save repairs the sector
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
    EXPECT_EQ(SaveEngine_GetLoadFlags(), 0);
}

TEST("A damaged progress copy falls back to the previous save")
{
    struct SaveDigest first, loaded;

    BuildOldGame();
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    TakeDigest(&first);
    ChangeProgress();
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK); // Written to copy B

    ProgramFlashByte(SAVE_SECTOR_PROGRESS_B + 2, SAVE_SECTOR_SIGNATURE_OFFSET2, 0x00);
    EXPECT_EQ(Reboot(), SAVE_STATUS_ERROR);
    TakeDigest(&loaded);
    EXPECT_EQ(loaded.progress, first.progress);
}

TEST("The stored-Pokemon warning fits the PC message window")
{
    // src/pokemon_storage_system.c prints this in WIN_MESSAGE, which is
    // 18 tiles wide and 2 tiles tall, so it gets two lines and no more.
    static const u8 sMessage[] = _("Ribbons and Condition\nwill be lost. Continue?");
    u8 line[64];
    u32 start = 0, i, lines = 0;

    for (i = 0; i <= sizeof(sMessage) - 1; i++)
    {
        if (sMessage[i] != CHAR_NEWLINE && sMessage[i] != EOS)
            continue;
        EXPECT_LT(i - start, sizeof(line));
        memcpy(line, &sMessage[start], i - start);
        line[i - start] = EOS;
        EXPECT_LE(GetStringWidth(FONT_NORMAL, line, 0), 18 * 8);
        lines++;
        start = i + 1;
        if (sMessage[i] == EOS)
            break;
    }
    EXPECT_EQ(lines, 2);
}

TEST("The outdated save message fits its window")
{
    // src/main_menu.c prints this in a 26-tile-wide window with a 1-pixel
    // left inset, so every line must be narrower than that.
    static const u8 sMessage[] = _("This save is from an older\nversion of BPE. To prevent save\ncorruption, the game will not\nallow you to save. Please use the\nSave Converter on the BPE website\nto continue your journey.");
    u8 line[64];
    u32 start = 0, i, lines = 0;

    for (i = 0; i <= sizeof(sMessage) - 1; i++)
    {
        if (sMessage[i] != CHAR_NEWLINE && sMessage[i] != EOS)
            continue;
        EXPECT_LT(i - start, sizeof(line));
        memcpy(line, &sMessage[start], i - start);
        line[i - start] = EOS;
        EXPECT_LE(GetStringWidth(FONT_NORMAL, line, 0), 26 * 8 - 2);
        lines++;
        start = i + 1;
        if (sMessage[i] == EOS)
            break;
    }
    // Six lines of 16 pixels fit the 12-tile-tall window exactly
    EXPECT_EQ(lines, 6);
}

TEST("Saves from before the 2.1 format are recognized")
{
    struct SaveSector *sector = (struct SaveSector *)gSaveEngineBuffer;
    u32 i;

    StartTestGame();
    for (i = 0; i < 14; i++)
    {
        memset(sector, 0, SAVE_SECTOR_SIZE);
        sector->id = i;
        sector->signature = SAVE_SIGNATURE_LEGACY;
        sector->counter = 7;
        EXPECT_EQ(ProgramFlashSectorAndVerify(i, (u8 *)sector), 0);
    }
    EXPECT_EQ(Reboot(), SAVE_STATUS_OUTDATED);

    // Nothing may be written over the old save
    GiveRandomPartyMon();
    EXPECT(Save_IsBlockedByOutdatedSave());
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_ERROR);
    EXPECT_EQ(TrySavingData(SAVE_OVERWRITE_DIFFERENT_FILE), SAVE_STATUS_ERROR);
    EXPECT_EQ(TrySavingData(SAVE_HALL_OF_FAME), SAVE_STATUS_ERROR);
    EXPECT_EQ(gDamagedSaveSectors, 0);
    EXPECT_EQ(LinkFullSave_Init(), TRUE);
    EXPECT_EQ(WriteSaveBlock2(), TRUE);
    for (i = 0; i < SECTORS_COUNT; i++)
    {
        ReadFlash(i, 0, gSaveEngineBuffer, SAVE_SECTOR_SIZE);
        sector = (struct SaveSector *)gSaveEngineBuffer;
        if (i < 14)
            EXPECT_EQ(sector->signature, SAVE_SIGNATURE_LEGACY);
        else
            EXPECT_NE(sector->signature, SAVE_SIGNATURE_V2);
    }
    EXPECT_EQ(Reboot(), SAVE_STATUS_OUTDATED);

    // Clearing the save data unlocks saving
    ClearSaveData();
    EXPECT(!Save_IsBlockedByOutdatedSave());
    EXPECT_EQ(Reboot(), SAVE_STATUS_EMPTY);
    EXPECT_EQ(TrySavingData(SAVE_NORMAL), SAVE_STATUS_OK);
    EXPECT_EQ(Reboot(), SAVE_STATUS_OK);
}

// Prints byte vectors for BPETools/tests/test_bpe_save_format.py and the
// website Save Converter tests. Refresh them with
// python BPETools/save_format_vectors.py after changing the packed format.
TEST("Packed format vectors")
{
    struct BoxPokemon boxMon;
    struct PackedBoxMon packed;
    u8 bytes[sizeof(boxMon) + sizeof(packed)];
    char line[2 * 20 + 1];
    u32 n, i, j;

    for (n = 0; n < 48; n++)
    {
        if (n == 0)
        {
            ZeroBoxMonData(&boxMon);
        }
        else
        {
            CreateRandomBoxMon(&boxMon);
            if (n % 12 == 0)
            {
                u32 value = GetBoxMonData(&boxMon, MON_DATA_CHECKSUM) ^ 0x5A5A;
                SetBoxMonData(&boxMon, MON_DATA_CHECKSUM, &value); // Bad Egg
            }
        }
        PackBoxMon(&packed, &boxMon);
        memcpy(bytes, &boxMon, sizeof(boxMon));
        memcpy(bytes + sizeof(boxMon), &packed, sizeof(packed));
        // The emulator log wraps long lines, so print 20 bytes at a time.
        for (i = 0; i < sizeof(bytes); i += 20)
        {
            for (j = 0; j < 20; j++)
            {
                line[2 * j] = "0123456789ABCDEF"[bytes[i + j] >> 4];
                line[2 * j + 1] = "0123456789ABCDEF"[bytes[i + j] & 15];
            }
            line[40] = '\0';
            Test_MgbaPrintf("VECTOR %d %d %s", n, i / 20, line);
        }
    }
}
