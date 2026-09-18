#include "global.h"
#include "event_object_movement.h"
#include "field_effect.h"
#include "field_effect_helpers.h"
#include "sprite.h"
#include "test/test.h"
#include "constants/event_objects.h"
#include "constants/field_effects.h"

// BPE: a busy route in the rain (Route 120: rain, tall grass, shadows and 44
// objects) can fill all 64 sprite slots. Cosmetic field sprites must then be
// skipped, as in vanilla, instead of stopping the game with "Out of sprite slots".

static void FillSpriteTable(void)
{
    ResetSpriteData();
    while (CreateSpriteUnchecked(&gDummySpriteTemplate, 0, 0, 0) != MAX_SPRITES)
        ;
}

static u32 CountSpritesInUse(void)
{
    u32 i, count = 0;

    for (i = 0; i < MAX_SPRITES; i++)
    {
        if (gSprites[i].inUse)
            count++;
    }
    return count;
}

TEST("A full sprite table skips a trainer's tree disguise instead of crashing")
{
    FillSpriteTable();

    // A tree-disguised trainer coming into view, as on Route 120.
    gObjectEvents[0].active = TRUE;
    gObjectEvents[0].localId = 1;
    gObjectEvents[0].mapNum = 0;
    gObjectEvents[0].mapGroup = 0;
    gFieldEffectArguments[0] = 1;
    gFieldEffectArguments[1] = 0;
    gFieldEffectArguments[2] = 0;

    FieldEffectStart(FLDEFF_TREE_DISGUISE);
    EXPECT_EQ(CountSpritesInUse(), MAX_SPRITES);

    gObjectEvents[0].active = FALSE;
}

TEST("A full sprite table skips object and warp arrow sprites instead of crashing")
{
    FillSpriteTable();

    EXPECT_EQ(CreateWarpArrowSprite(), MAX_SPRITES);
    EXPECT_EQ(CreateObjectGraphicsSpriteWithTag(OBJ_EVENT_GFX_BOY_1, SpriteCallbackDummy, 0, 0, 0, TAG_NONE), MAX_SPRITES);
    EXPECT_EQ(CountSpritesInUse(), MAX_SPRITES);
}
