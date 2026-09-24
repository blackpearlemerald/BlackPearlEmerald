#include "global.h"
#include "event_data.h"
#include "item.h"
#include "test/test.h"
#include "constants/items.h"

// BPE: SELECT can hold up to MAX_REGISTERED_ITEMS key items. The first slot is
// the vanilla save block field; the rest are variables.

static const enum Item sKeyItems[] =
{
    ITEM_MACH_BIKE,
    ITEM_OLD_ROD,
    ITEM_GOOD_ROD,
    ITEM_SUPER_ROD,
    ITEM_ITEMFINDER,
    ITEM_WAILMER_PAIL,
};

STATIC_ASSERT(ARRAY_COUNT(sKeyItems) > MAX_REGISTERED_ITEMS, notEnoughTestItems);

static void ResetRegisteredItems(void)
{
    u32 i;

    ClearBag();
    for (i = 0; i < ARRAY_COUNT(sKeyItems); i++)
        UnregisterItem(sKeyItems[i]);
    for (i = 0; i < ARRAY_COUNT(sKeyItems); i++)
        AddBagItem(sKeyItems[i], 1);
}

TEST("Registered items fill slots in order and refuse more than the limit")
{
    u32 i;

    ResetRegisteredItems();
    EXPECT_EQ(CountRegisteredItems(), 0);

    for (i = 0; i < MAX_REGISTERED_ITEMS; i++)
        EXPECT(RegisterItem(sKeyItems[i]));
    EXPECT_EQ(CountRegisteredItems(), MAX_REGISTERED_ITEMS);
    EXPECT_EQ(gSaveBlock1Ptr->registeredItem, sKeyItems[0]);
    for (i = 0; i < MAX_REGISTERED_ITEMS; i++)
        EXPECT_EQ(GetRegisteredItem(i), sKeyItems[i]);

    EXPECT(!RegisterItem(sKeyItems[MAX_REGISTERED_ITEMS]));
    EXPECT(!IsItemRegistered(sKeyItems[MAX_REGISTERED_ITEMS]));

    // Registering an item twice takes no slot.
    EXPECT(RegisterItem(sKeyItems[0]));
    EXPECT_EQ(CountRegisteredItems(), MAX_REGISTERED_ITEMS);
}

TEST("Deselecting an item closes the gap and frees a slot")
{
    ResetRegisteredItems();
    RegisterItem(ITEM_MACH_BIKE);
    RegisterItem(ITEM_OLD_ROD);
    RegisterItem(ITEM_GOOD_ROD);

    UnregisterItem(ITEM_MACH_BIKE);
    EXPECT_EQ(CountRegisteredItems(), 2);
    EXPECT_EQ(GetRegisteredItem(0), ITEM_OLD_ROD);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_GOOD_ROD);
    EXPECT_EQ(GetRegisteredItem(2), ITEM_NONE);
    EXPECT(!IsItemRegistered(ITEM_MACH_BIKE));
}

TEST("A save from an older release keeps its one registered item")
{
    ResetRegisteredItems();
    gSaveBlock1Ptr->registeredItem = ITEM_ITEMFINDER;
    EXPECT_EQ(CountRegisteredItems(), 1);
    EXPECT(IsItemRegistered(ITEM_ITEMFINDER));
    EXPECT(RegisterItem(ITEM_OLD_ROD));
    EXPECT_EQ(GetRegisteredItem(1), ITEM_OLD_ROD);
}

TEST("Registered items the player no longer carries are forgotten")
{
    ResetRegisteredItems();
    RegisterItem(ITEM_OLD_ROD);
    RegisterItem(ITEM_GOOD_ROD);
    RegisterItem(ITEM_SUPER_ROD);

    RemoveBagItem(ITEM_GOOD_ROD, 1);
    UnregisterMissingItems();
    EXPECT_EQ(CountRegisteredItems(), 2);
    EXPECT_EQ(GetRegisteredItem(0), ITEM_OLD_ROD);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_SUPER_ROD);
}

TEST("Swapping bikes keeps the bike's place among the registered items")
{
    ResetRegisteredItems();
    RegisterItem(ITEM_OLD_ROD);
    RegisterItem(ITEM_MACH_BIKE);

    SwapRegisteredBike();
    EXPECT_EQ(GetRegisteredItem(0), ITEM_OLD_ROD);
    EXPECT_EQ(GetRegisteredItem(1), ITEM_ACRO_BIKE);
    SwapRegisteredBike();
    EXPECT_EQ(GetRegisteredItem(1), ITEM_MACH_BIKE);
}
