#include "global.h"
#include "event_object_movement.h"
#include "field_effect.h"
#include "field_effect_helpers.h"
#include "sprite.h"
#include "trainer_see.h"
#include "test/test.h"
#include "constants/event_objects.h"
#include "constants/field_effects.h"
#include "constants/event_object_movement.h"
#include "constants/trainer_types.h"

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

// Victory Road freeze: a trainer whose sprite id pointed at another sprite was
// invisible, put its "!" over that other sprite when it spotted the player and
// never walked over.
static struct ObjectEvent *SetUpTrainer(u32 spriteId)
{
    struct ObjectEvent *trainer = &gObjectEvents[1];

    memset(trainer, 0, sizeof(*trainer));
    trainer->active = TRUE;
    trainer->localId = 1;
    trainer->graphicsId = OBJ_EVENT_GFX_GIOVANNI;
    trainer->movementType = MOVEMENT_TYPE_FACE_LEFT;
    trainer->trainerType = TRAINER_TYPE_NORMAL;
    trainer->trainerRange_berryTreeId = 4;
    trainer->spriteId = spriteId;
    return trainer;
}

TEST("An object whose sprite can't be made again after a battle is dropped, not left with a stale sprite")
{
    struct ObjectEvent *trainer;

    FillSpriteTable();
    trainer = SetUpTrainer(0);

    SpawnObjectEventsOnReturnToField(0, 0);
    EXPECT(!trainer->active);

    memset(trainer, 0, sizeof(*trainer));
    ResetSpriteData();
}

TEST("Removing an object never destroys a sprite that belongs to something else")
{
    struct ObjectEvent *trainer;
    u32 otherSprite;

    ResetSpriteData();
    otherSprite = CreateSpriteUnchecked(&gDummySpriteTemplate, 0, 0, 0);
    gSprites[otherSprite].data[0] = 5;
    trainer = SetUpTrainer(otherSprite);

    EXPECT(!ObjectEventHasOwnSprite(trainer));
    RemoveObjectEvent(trainer);
    EXPECT(gSprites[otherSprite].inUse);
    EXPECT(!trainer->active);

    memset(trainer, 0, sizeof(*trainer));
    ResetSpriteData();
}

TEST("A trainer without a sprite of its own is dropped instead of spotting the player")
{
    struct ObjectEvent *trainer;
    u32 otherSprite;

    ResetSpriteData();
    otherSprite = CreateSpriteUnchecked(&gDummySpriteTemplate, 0, 0, 0);
    gSprites[otherSprite].data[0] = 5;
    trainer = SetUpTrainer(otherSprite);

    EXPECT(!CheckForTrainersWantingBattle());
    EXPECT(!trainer->active);
    EXPECT(gSprites[otherSprite].inUse);

    memset(trainer, 0, sizeof(*trainer));
    ResetSpriteData();
}
