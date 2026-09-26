#include "global.h"
#include "event_data.h"
#include "item.h"
#include "pokemon.h"
#include "wild_encounter.h"
#include "test/overworld_script.h"
#include "test/test.h"
#include "constants/items.h"

// BPE: the Infinite Repel is a key item that switches a Max Repel on that never
// wears off. It is a flag, so it does not touch the Repel step counter.

static void SetUpLeadAtLevel30(void)
{
    ZeroPlayerPartyMons();
    RUN_OVERWORLD_SCRIPT(
        givemon SPECIES_WOBBUFFET, 30;
    );
    VarSet(VAR_REPEL_STEP_COUNT, 0);
    FlagClear(FLAG_SYS_SAFARI_MODE);
}

TEST("The Infinite Repel keeps weaker wild Pokemon away while it is on")
{
    SetUpLeadAtLevel30();

    FlagClear(FLAG_INFINITE_REPEL_ON);
    EXPECT(!IsRepelActive());
    EXPECT(IsWildLevelAllowedByRepel(10));

    FlagSet(FLAG_INFINITE_REPEL_ON);
    EXPECT(IsRepelActive());
    EXPECT(!IsWildLevelAllowedByRepel(10));
    EXPECT(!IsWildLevelAllowedByRepel(29));
    EXPECT(IsWildLevelAllowedByRepel(30));
    EXPECT(IsWildLevelAllowedByRepel(45));

    FlagClear(FLAG_INFINITE_REPEL_ON);
    EXPECT(IsWildLevelAllowedByRepel(10));
}

TEST("The Infinite Repel never runs out")
{
    u32 i;

    SetUpLeadAtLevel30();
    FlagSet(FLAG_INFINITE_REPEL_ON);

    for (i = 0; i < 300; i++)
        EXPECT(!UpdateRepelCounter());
    EXPECT_EQ(VarGet(VAR_REPEL_STEP_COUNT), 0);
    EXPECT(!IsWildLevelAllowedByRepel(10));

    FlagClear(FLAG_INFINITE_REPEL_ON);
}

TEST("The Infinite Repel does nothing in the Safari Zone")
{
    SetUpLeadAtLevel30();
    FlagSet(FLAG_INFINITE_REPEL_ON);
    FlagSet(FLAG_SYS_SAFARI_MODE);

    EXPECT(!IsInfiniteRepelActive());
    EXPECT(IsWildLevelAllowedByRepel(10));

    FlagClear(FLAG_SYS_SAFARI_MODE);
    FlagClear(FLAG_INFINITE_REPEL_ON);
}

TEST("The Infinite Repel is a key item")
{
    EXPECT_EQ(GetItemPocket(ITEM_INFINITE_REPEL), POCKET_KEY_ITEMS);
    EXPECT_EQ(GetItemImportance(ITEM_INFINITE_REPEL), 1);
}
