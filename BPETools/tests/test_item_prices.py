"""Exporter tests for item prices: config expressions, #if branches, the
Verdanturf mart's capped prices and sell-back values.

Inputs are small synthetic game-source fragments in temporary directories.
"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
import item_prices as P


CONFIG = """
#define GEN_1 0
#define GEN_2 1
#define GEN_3 2
#define GEN_4 3
#define GEN_5 4
#define GEN_6 5
#define GEN_7 6
#define GEN_8 7
#define GEN_9 8
#define GEN_LATEST GEN_9
"""

ITEM_CONFIG = """
#define I_PRICE               GEN_LATEST
#define I_BERRY_PRICE         GEN_7   // berries stay cheap
#define I_SELL_VALUE_FRACTION GEN_LATEST
#define I_USE_EVO_HELD_ITEMS_FROM_BAG TRUE
"""

ITEMS = """
#if I_USE_EVO_HELD_ITEMS_FROM_BAG == TRUE
    #define EVO_HELD_ITEM_FIELD_FUNC ItemUseOutOfBattle_EvolutionStone
#else
    #define EVO_HELD_ITEM_FIELD_FUNC ItemUseOutOfBattle_CannotUse
#endif
#define TREASURE_FACTOR ((I_SELL_VALUE_FRACTION >= GEN_9) ? 2 : 1)

const struct ItemInfo gItemsInfo[] =
{
    [ITEM_HYPER_POTION] =
    {
        .price = (I_PRICE >= GEN_2 && I_PRICE <= GEN_6) ? 1200 : 1500,
        .pocket = POCKET_ITEMS,
    },
    [ITEM_BURN_HEAL] =
    {
    #if I_PRICE >= GEN_8
        .price = 200,
    #else
        .price = 250,
    #endif
    },
    [ITEM_PEARL] =
    {
        .price = (I_PRICE >= GEN_7) ? 2000 * TREASURE_FACTOR : 1400,
    },
    #if I_PRICE >= GEN_9
        #define GEM_PRICE 15000
    #else
        #define GEM_PRICE 200
    #endif
    [ITEM_FIRE_GEM] =
    {
        .price = GEM_PRICE,
    },
    [ITEM_ORAN_BERRY] =
    {
        .price = (I_BERRY_PRICE >= GEN_8) ? 80 : 20,
        .pocket = POCKET_BERRIES,
    },
    [ITEM_FIRE_STONE] =
    {
        .price = 3000,
        .fieldUseFunc = ItemUseOutOfBattle_EvolutionStone,
    },
    [ITEM_RAZOR_CLAW] =
    {
        .price = 15000,
        .fieldUseFunc = EVO_HELD_ITEM_FIELD_FUNC,
    },
    [ITEM_LOVE_SWEET] =
    {
        .price = 1000,
    },
    [ITEM_GIMMIGHOUL_COIN] =
    {
        .price = 400,
    },
    [ITEM_FLAME_ORB] =
    {
        .price = 15000,
    },
    [ITEM_MACH_BIKE] =
    {
        .price = 1000,
        .importance = 1,
    },
};
"""

ITEM_C = """
static const u16 *const sVerdanturfMartLists[] =
{
    VerdanturfTown_Mart_Pokemart_Basic,
};

static bool32 IsEvolutionItem(enum Item itemId)
{
    switch (itemId)
    {
    case ITEM_LOVE_SWEET:
        return TRUE;
    default:
        return FALSE;
    }
}

u32 GetVerdanturfMartPrice(enum Item itemId)
{
    u32 price = GetItemPrice(itemId);
    u32 cap = 500;

    if (itemId == ITEM_GIMMIGHOUL_COIN)
        cap = 10;
    else if (GetItemPocket(itemId) == POCKET_BERRIES)
        cap = 50;
    else if (IsEvolutionItem(itemId))
        cap = 200;
    return min(price, cap);
}

u32 GetItemSellPrice(enum Item itemId)
{
    u32 price = IsSoldInVerdanturfMart(itemId) ? GetVerdanturfMartPrice(itemId) : GetItemPrice(itemId);
    if (price != 0 && price < ITEM_SELL_FACTOR)
        return 1;
    return price / ITEM_SELL_FACTOR;
}
"""

MART = """
VerdanturfTown_Mart_EventScript_Clerk::
	pokemart VerdanturfTown_Mart_Pokemart_Basic
	end

	.align 2
VerdanturfTown_Mart_Pokemart_Basic:
	.2byte ITEM_FIRE_STONE
	.2byte ITEM_RAZOR_CLAW
	.2byte ITEM_LOVE_SWEET
	.2byte ITEM_ORAN_BERRY
	.2byte ITEM_GIMMIGHOUL_COIN
	.2byte ITEM_FLAME_ORB
	pokemartlistend
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def source(root, item_c=ITEM_C):
    write(root / "include/config/general.h", CONFIG)
    write(root / "include/config/item.h", ITEM_CONFIG)
    write(root / "include/constants/item.h",
          "#define ITEM_SELL_FACTOR ((I_SELL_VALUE_FRACTION >= GEN_9) ? 4 : 2)\n")
    write(root / "src/data/items.h", ITEMS)
    write(root / "src/item.c", item_c)
    write(root / "data/maps/VerdanturfTown_Mart/scripts.inc", MART)


class ExpressionTests(unittest.TestCase):
    def test_c_operators_and_macros(self):
        macros = {"GEN_9": "8", "I_PRICE": "GEN_9", "F": "((I_PRICE >= GEN_9) ? 2 : 1)"}
        self.assertEqual(P.evaluate("(I_PRICE <= 2 || I_PRICE >= GEN_9) ? 0 : 300", macros), 0)
        self.assertEqual(P.evaluate("(I_PRICE == 0) ? 1 : 3000", macros), 3000)
        self.assertEqual(P.evaluate("500 * F", macros), 1000)
        self.assertEqual(P.evaluate("defined(I_PRICE) && !defined NOPE", macros), 1)
        with self.assertRaises(P.Unknown):
            P.evaluate("UNKNOWN_CONFIG >= GEN_9", macros)

    def test_unknown_condition_keeps_every_branch(self):
        text = "#if SOMETHING_ELSE\na\n#else\nb\n#endif\nc"
        self.assertEqual(P.preprocess(text, {}).split(), ["a", "b", "c"])


class PriceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_prices_follow_the_game_config(self):
        source(self.root)
        prices = P.Prices(self.root)
        self.assertEqual(prices.price("HYPER_POTION"), 1500)
        self.assertEqual(prices.price("BURN_HEAL"), 200)
        self.assertEqual(prices.price("PEARL"), 4000)      # treasure factor
        self.assertEqual(prices.price("FIRE_GEM"), 15000)  # #if-chosen macro
        self.assertEqual(prices.price("ORAN_BERRY"), 20)   # I_BERRY_PRICE is GEN_7

    def test_verdanturf_caps_and_sell_back(self):
        source(self.root)
        prices = P.Prices(self.root)
        self.assertEqual(prices.verdanturf_price("FIRE_STONE"), 200)
        self.assertEqual(prices.verdanturf_price("RAZOR_CLAW"), 200)  # through the macro
        self.assertEqual(prices.verdanturf_price("LOVE_SWEET"), 200)
        self.assertEqual(prices.verdanturf_price("ORAN_BERRY"), 20)   # already cheaper
        self.assertEqual(prices.verdanturf_price("GIMMIGHOUL_COIN"), 10)
        self.assertEqual(prices.verdanturf_price("FLAME_ORB"), 500)
        # The site gives one price: Verdanturf's, for anything it sells.
        self.assertEqual(prices.price("FLAME_ORB"), 500)
        self.assertEqual(prices.price("PEARL"), 4000)             # not sold there
        self.assertEqual(prices.sell_price("FLAME_ORB"), 125)     # 500 / 4, anywhere
        self.assertEqual(prices.sell_price("GIMMIGHOUL_COIN"), 2)
        self.assertEqual(prices.sell_price("PEARL"), 1000)
        self.assertEqual(prices.sell_price("MACH_BIKE"), 0)       # key item

    def test_other_marts_charge_by_source(self):
        # 2.2.3-2.2.5: only the Verdanturf mart charged its price.
        source(self.root)
        prices = P.Prices(self.root)
        self.assertEqual(prices.mart_price("FLAME_ORB", "MAP_SLATEPORT_CITY_MART"), 15000)
        self.assertEqual(prices.mart_price("FLAME_ORB", "MAP_VERDANTURF_TOWN_MART"), 500)
        # Later: GetItemPrice is the Verdanturf price everywhere.
        source(self.root, item_c=ITEM_C + """
u32 GetItemPrice(enum Item itemId)
{
    if (IsSoldInVerdanturfMart(itemId))
        return GetVerdanturfMartPrice(itemId);
    return gItemsInfo[SanitizeItemId(itemId)].price;
}
""")
        prices = P.Prices(self.root)
        self.assertEqual(prices.mart_price("FLAME_ORB", "MAP_SLATEPORT_CITY_MART"), 500)
        self.assertEqual(prices.mart_price("PEARL", "MAP_SLATEPORT_CITY_MART"), 4000)

    def test_source_without_verdanturf_prices(self):
        source(self.root, item_c="u32 GetItemPrice(u16 itemId) { return 0; }\n")
        prices = P.Prices(self.root)
        self.assertIsNone(prices.verdanturf_price("FLAME_ORB"))
        self.assertEqual(prices.mart_price("FLAME_ORB", "MAP_VERDANTURF_TOWN_MART"), 15000)
        self.assertEqual(prices.sell_price("FLAME_ORB"), 3750)

    def test_changed_verdanturf_rules_are_refused(self):
        source(self.root, item_c=ITEM_C.replace("cap = 10;", "cap = GetCoinCap();"))
        with self.assertRaises(ValueError):
            P.Prices(self.root)


if __name__ == "__main__":
    unittest.main()
