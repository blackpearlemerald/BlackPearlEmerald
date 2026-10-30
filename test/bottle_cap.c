#include "global.h"
#include "event_data.h"
#include "item.h"
#include "item_use.h"
#include "pokemon.h"
#include "script.h"
#include "test/test.h"
#include "constants/flags.h"
#include "constants/item.h"
#include "constants/items.h"

void ScriptBottleCapRaiseIV(void);

TEST("A Bottle Cap maxes out only the chosen IV")
{
    u32 iv = 3, field;

    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PLAYER_ID);
    for (field = MON_DATA_HP_IV; field <= MON_DATA_SPDEF_IV; field++)
        SetMonData(&gParties[B_TRAINER_PLAYER][0], field, &iv);

    gSpecialVar_0x8004 = 0;
    gSpecialVar_Result = MON_DATA_SPEED_IV - MON_DATA_HP_IV;
    ScriptBottleCapRaiseIV();

    EXPECT_EQ(gSpecialVar_Result, TRUE);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPEED_IV), MAX_PER_STAT_IVS);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_IV), 3);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_ATK_IV), 3);
    EXPECT_EQ(GetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_SPDEF_IV), 3);
}

TEST("A Bottle Cap is not used on an IV that is already maxed")
{
    u32 iv = MAX_PER_STAT_IVS;

    ZeroPlayerPartyMons();
    CreateMon(&gParties[B_TRAINER_PLAYER][0], SPECIES_WOBBUFFET, 50, 0, OTID_STRUCT_PLAYER_ID);
    SetMonData(&gParties[B_TRAINER_PLAYER][0], MON_DATA_HP_IV, &iv);

    gSpecialVar_0x8004 = 0;
    gSpecialVar_Result = 0;
    ScriptBottleCapRaiseIV();

    EXPECT_EQ(gSpecialVar_Result, FALSE);
}

TEST("A Bottle Cap cannot be sold for more than it costs")
{
    EXPECT_LE(GetItemSellPrice(ITEM_BOTTLE_CAP), GetItemPrice(ITEM_BOTTLE_CAP));
    EXPECT_EQ(GetItemPrice(ITEM_BOTTLE_CAP), 500);
}

// SetUpItemUseCallback indexes a table that has no ITEM_USE_BAG_MENU entry, and
// such an item drops back to the Start menu instead of running its script.
TEST("A Bottle Cap closes the Bag through the field callback")
{
    EXPECT_EQ(GetItemType(ITEM_BOTTLE_CAP), ITEM_USE_FIELD);
}

TEST("The Running Shoes are a key item")
{
    EXPECT_EQ(GetItemPocket(ITEM_RUNNING_SHOES), POCKET_KEY_ITEMS);
    EXPECT_EQ(GetItemImportance(ITEM_RUNNING_SHOES), 1);
    EXPECT_EQ(ITEM_RUNNING_SHOES, 890);
    EXPECT_EQ(FLAG_CLASSIC_RUNNING, 0x45);
    EXPECT_EQ(FLAG_RECEIVED_SHOES_KEY_ITEM, 0x46);
}
