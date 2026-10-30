#include "global.h"
#include "item.h"
#include "item_use.h"
#include "constants/items.h"
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

TEST("Every Verdanturf list sells every ball except the Master Ball, for 300 at most")
{
    for (u32 i = 0; i < ARRAY_COUNT(sLists); i++)
    {
        for (enum Item ball = ITEM_NONE + 1; ball < ITEMS_COUNT; ball++)
        {
            const u16 *item = sLists[i];

            if (GetItemPocket(ball) != POCKET_POKE_BALLS)
                continue;
            while (*item != ITEM_NONE && *item != ball)
                item++;
            EXPECT_EQ(*item == ball, ball != ITEM_MASTER_BALL);
            if (ball != ITEM_MASTER_BALL)
            {
                EXPECT_NE(GetItemPrice(ball), 0);
                EXPECT_LE(GetItemPrice(ball), 300);
            }
        }
    }
}

TEST("Whatever the Verdanturf mart sells costs its price everywhere")
{
    for (u32 i = 0; i < ARRAY_COUNT(sLists); i++)
    {
        for (const u16 *item = sLists[i]; *item != ITEM_NONE; item++)
            EXPECT_EQ(GetItemPrice(*item), GetVerdanturfMartPrice(*item));
    }
    // Also stocked by other marts, which must not charge more.
    EXPECT_EQ(GetItemPrice(ITEM_GREAT_BALL), 100);
    EXPECT_EQ(GetItemPrice(ITEM_ULTRA_BALL), 200);
    EXPECT_EQ(GetItemSellPrice(ITEM_FLAME_ORB), 500 / ITEM_SELL_FACTOR);
    // Items it doesn't sell keep their own price.
    EXPECT_EQ(GetItemPrice(ITEM_NUGGET), gItemsInfo[ITEM_NUGGET].price);
}
