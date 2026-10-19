#include "global.h"
#include "item.h"
#include "item_use.h"
#include "constants/items.h"
#include "constants/maps.h"
#include "test/test.h"

// BPE: the Verdanturf mart sells everything cheaply (see GetVerdanturfMartPrice).

extern const u16 VerdanturfTown_Mart_Pokemart_Basic[];
extern const u16 VerdanturfTown_Mart_Pokemart_Expanded3[];
extern const u16 VerdanturfTown_Mart_Pokemart_Expanded4[];
extern const u16 VerdanturfTown_Mart_Pokemart_Postgame[];

static const u16 *const sLists[] =
{
    VerdanturfTown_Mart_Pokemart_Basic,
    VerdanturfTown_Mart_Pokemart_Expanded3,
    VerdanturfTown_Mart_Pokemart_Expanded4,
    VerdanturfTown_Mart_Pokemart_Postgame,
};

TEST("Nothing in the Verdanturf mart costs more than 500, and berries and evolution items cost less")
{
    for (u32 i = 0; i < ARRAY_COUNT(sLists); i++)
    {
        for (const u16 *item = sLists[i]; *item != ITEM_NONE; item++)
        {
            u32 price = GetVerdanturfMartPrice(*item);

            EXPECT_LE(price, 500);
            EXPECT_LE(GetItemSellPrice(*item) * 2, max(price, 2));
            if (GetItemPocket(*item) == POCKET_BERRIES)
                EXPECT_LE(price, 50);
            if (GetItemFieldFunc(*item) == ItemUseOutOfBattle_EvolutionStone)
                EXPECT_LE(price, 200);
        }
    }
    EXPECT_EQ(GetVerdanturfMartPrice(ITEM_FLAME_ORB), 500);
    EXPECT_EQ(GetVerdanturfMartPrice(ITEM_FIRE_STONE), 200);
    EXPECT_EQ(GetVerdanturfMartPrice(ITEM_STRAWBERRY_SWEET), 200);
    EXPECT_LE(GetVerdanturfMartPrice(ITEM_SITRUS_BERRY), 50);
    EXPECT_EQ(GetVerdanturfMartPrice(ITEM_GIMMIGHOUL_COIN), 10);
    EXPECT_EQ(GetVerdanturfMartPrice(ITEM_POKE_BALL), GetItemPrice(ITEM_POKE_BALL));
}

TEST("Only the Verdanturf mart charges its own prices")
{
    struct WarpData saved = gSaveBlock1Ptr->location;

    gSaveBlock1Ptr->location.mapGroup = MAP_GROUP(MAP_VERDANTURF_TOWN_MART);
    gSaveBlock1Ptr->location.mapNum = MAP_NUM(MAP_VERDANTURF_TOWN_MART);
    EXPECT_EQ(GetMartItemPrice(ITEM_FLAME_ORB), 500);

    gSaveBlock1Ptr->location.mapGroup = MAP_GROUP(MAP_LILYCOVE_CITY_DEPARTMENT_STORE_2F);
    gSaveBlock1Ptr->location.mapNum = MAP_NUM(MAP_LILYCOVE_CITY_DEPARTMENT_STORE_2F);
    EXPECT_EQ(GetMartItemPrice(ITEM_FLAME_ORB), GetItemPrice(ITEM_FLAME_ORB));

    gSaveBlock1Ptr->location = saved;
}
