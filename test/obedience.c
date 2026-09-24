#include "global.h"
#include "battle_util.h"
#include "caps.h"
#include "event_data.h"
#include "test/test.h"

// BPE: traded Pokémon obey up to the badge-based level cap, so one trained to
// the cap never disobeys. Above the cap the vanilla badge table still applies.

static const u16 sBadgeFlags[] =
{
    FLAG_BADGE01_GET,
    FLAG_BADGE02_GET,
    FLAG_BADGE03_GET,
    FLAG_BADGE04_GET,
    FLAG_BADGE05_GET,
    FLAG_BADGE06_GET,
    FLAG_BADGE07_GET,
    FLAG_BADGE08_GET,
};

static void SetBadgeCount(u32 count)
{
    u32 i;

    FlagClear(FLAG_IS_CHAMPION);
    for (i = 0; i < ARRAY_COUNT(sBadgeFlags); i++)
    {
        if (i < count)
            FlagSet(sBadgeFlags[i]);
        else
            FlagClear(sBadgeFlags[i]);
    }
}

TEST("Obedience level is never below the level cap")
{
    u32 badges = 0;

    for (u32 j = 0; j <= ARRAY_COUNT(sBadgeFlags); j++)
        PARAMETRIZE { badges = j; }

    SetBadgeCount(badges);
    EXPECT_GE(GetObedienceLevel(), GetProgressLevelCap());
    SetBadgeCount(0);
}

TEST("Obedience level follows the level cap, then the badge table")
{
    static const u8 sExpected[] = { 15, 24, 33, 42, 51, 60, 70, 80, MAX_LEVEL };
    u32 badges = 0;

    for (u32 j = 0; j < ARRAY_COUNT(sExpected); j++)
        PARAMETRIZE { badges = j; }

    SetBadgeCount(badges);
    EXPECT_EQ(GetObedienceLevel(), sExpected[badges]);
    SetBadgeCount(0);
}

TEST("Obedience level does not depend on the mode or the Level Limiter")
{
    u32 nuzlocke = 0, limiter = 0;

    PARAMETRIZE { nuzlocke = FALSE; limiter = FALSE; }
    PARAMETRIZE { nuzlocke = FALSE; limiter = TRUE; }
    PARAMETRIZE { nuzlocke = TRUE; limiter = FALSE; }

    SetBadgeCount(2);
    if (nuzlocke)
        FlagSet(FLAG_NUZLOCKE);
    else
        FlagClear(FLAG_NUZLOCKE);
    if (limiter)
        FlagSet(FLAG_STANDARD_LEVEL_CAPS);
    else
        FlagClear(FLAG_STANDARD_LEVEL_CAPS);

    EXPECT_EQ(GetObedienceLevel(), 33);

    FlagClear(FLAG_NUZLOCKE);
    FlagClear(FLAG_STANDARD_LEVEL_CAPS);
    SetBadgeCount(0);
}
