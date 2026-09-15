#include "global.h"
#include "event_data.h"
#include "item.h"
#include "script_menu.h"
#include "test/test.h"
#include "constants/flags.h"
#include "constants/items.h"
#include "constants/script_menu.h"

TEST("Owned event tickets unlock all four ferry destinations")
{
    static const u16 sDestinationFlags[] = {
        FLAG_ENABLE_SHIP_SOUTHERN_ISLAND,
        FLAG_ENABLE_SHIP_NAVEL_ROCK,
        FLAG_ENABLE_SHIP_BIRTH_ISLAND,
        FLAG_ENABLE_SHIP_FARAWAY_ISLAND,
    };
    u32 destinations;

    ClearBag();
    for (u32 i = 0; i < ARRAY_COUNT(sDestinationFlags); i++)
        FlagClear(sDestinationFlags[i]);
    FlagClear(FLAG_RECEIVED_MYSTIC_TICKET);
    FlagClear(FLAG_RECEIVED_AURORA_TICKET);
    FlagClear(FLAG_RECEIVED_OLD_SEA_MAP);

    EXPECT(AddBagItem(ITEM_EON_TICKET, 1));
    EXPECT(AddBagItem(ITEM_MYSTIC_TICKET, 1));
    EXPECT(AddBagItem(ITEM_AURORA_TICKET, 1));
    EXPECT(AddBagItem(ITEM_OLD_SEA_MAP, 1));

    destinations = Test_GetAvailableEventTicketDestinations();

    EXPECT(destinations & (1 << SSTIDAL_SELECTION_SOUTHERN_ISLAND));
    EXPECT(destinations & (1 << SSTIDAL_SELECTION_NAVEL_ROCK));
    EXPECT(destinations & (1 << SSTIDAL_SELECTION_BIRTH_ISLAND));
    EXPECT(destinations & (1 << SSTIDAL_SELECTION_FARAWAY_ISLAND));
    for (u32 i = 0; i < ARRAY_COUNT(sDestinationFlags); i++)
        EXPECT(FlagGet(sDestinationFlags[i]));
    EXPECT(FlagGet(FLAG_RECEIVED_MYSTIC_TICKET));
    EXPECT(FlagGet(FLAG_RECEIVED_AURORA_TICKET));
    EXPECT(FlagGet(FLAG_RECEIVED_OLD_SEA_MAP));
}
