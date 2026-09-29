#include "global.h"
#include "item.h"
#include "item_menu.h"
#include "item_use.h"
#include "malloc.h"
#include "party_menu.h"
#include "task.h"
#include "test/test.h"
#include "constants/items.h"

// BPE: using a Ball from the Bag moves a party Pokemon into it. Balls keep the
// type ITEM_USE_BAG_MENU for battle, which has no screen outside battle, so 2.1.1
// to 2.1.9 closed the Bag instead of opening the party menu.

TEST("Using a Ball from the Bag opens the party menu")
{
    u32 taskId;

    gBagMenu = AllocZeroed(sizeof(*gBagMenu));
    taskId = CreateTask(TaskDummy, 0);
    gSpecialVar_ItemId = ITEM_POKE_BALL;

    GetItemFieldFunc(ITEM_POKE_BALL)(taskId);

    EXPECT(gBagMenu->newScreenCallback == CB2_ShowPartyMenuForItemUse);
    EXPECT(gItemUseCB == ItemUseCB_Ball);

    DestroyTask(taskId);
    TRY_FREE_AND_SET_NULL(gBagMenu);
}

TEST("Every Ball can be used from the Bag and thrown in battle")
{
    enum Item item;

    for (item = ITEM_NONE + 1; item < ITEMS_COUNT; item++)
    {
        if (GetItemPocket(item) != POCKET_POKE_BALLS)
            continue;
        EXPECT(GetItemFieldFunc(item) == ItemUseOutOfBattle_Ball);
        EXPECT_EQ(GetItemType(item), ITEM_USE_BAG_MENU);
    }
}
