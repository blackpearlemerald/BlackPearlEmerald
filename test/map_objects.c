#include "global.h"
#include "event_object_movement.h"
#include "overworld.h"
#include "test/test.h"
#include "constants/event_object_movement.h"
#include "constants/event_objects.h"
#include "constants/maps.h"
#include "constants/trainer_types.h"
#include "../src/data/map_group_count.h"

// BPE: the Victory Road freeze. Giovanni (1F) and Blue (B2F) use FRLG overworld
// graphics, which the Emerald build left out, so their graphics entry was NULL.
// The trainer's sprite got a garbage size and was placed far off screen, and
// once it spotted the player its approach never finished.

extern const struct ObjectEventGraphicsInfo *const gObjectEventGraphicsInfoPointers[NUM_OBJ_EVENT_GFX];

static bool32 HasOwnGraphics(u16 graphicsId)
{
    // Variable and Pokemon graphics are resolved while the game runs.
    if (graphicsId >= OBJ_EVENT_GFX_VARS && graphicsId <= OBJ_EVENT_GFX_VAR_F)
        return TRUE;
    if (graphicsId & OBJ_EVENT_MON)
        return TRUE;
    return graphicsId < NUM_OBJ_EVENT_GFX && gObjectEventGraphicsInfoPointers[graphicsId] != NULL;
}

TEST("Every object placed on a map has overworld graphics in this build")
{
    u32 group, num, i, missing = 0;

    for (group = 0; group < MAP_GROUPS_COUNT; group++)
    {
        for (num = 0; num < MAP_GROUP_COUNT[group]; num++)
        {
            const struct MapEvents *events = Overworld_GetMapHeaderByGroupAndId(group, num)->events;

            for (i = 0; i < events->objectEventCount; i++)
            {
                u16 graphicsId = events->objectEvents[i].graphicsId;

                if (!HasOwnGraphics(graphicsId))
                {
                    Test_MgbaPrintf("map %d.%d object %d: graphics %d are not built", group, num, i + 1, graphicsId);
                    missing++;
                }
            }
        }
    }
    EXPECT_EQ(missing, 0);
}

TEST("The Victory Road trainers have their own graphics")
{
    EXPECT(HasOwnGraphics(OBJ_EVENT_GFX_GIOVANNI));
    EXPECT(HasOwnGraphics(OBJ_EVENT_GFX_BLUE));
    EXPECT_EQ(GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_GIOVANNI)->height, 32);
    EXPECT_EQ(GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_BLUE)->height, 32);
}

TEST("Graphics missing from the build fall back to a real sprite")
{
    u32 id;

    for (id = 0; id < NUM_OBJ_EVENT_GFX; id++)
    {
        if (gObjectEventGraphicsInfoPointers[id] == NULL)
            break;
    }
    ASSUME(id < NUM_OBJ_EVENT_GFX); // Emerald builds leave the FRLG-only graphics out
    EXPECT(GetObjectEventGraphicsInfo(id) == GetObjectEventGraphicsInfo(OBJ_EVENT_GFX_NINJA_BOY));
}

// Victory Road B2F and Route 118: moving trainers back to their vanilla spots put
// Red (Vito) and Rose on tiles BPE had since filled with rock, where nobody could
// reach or battle them.
TEST("Every trainer stands on open ground")
{
    u32 group, num, i, stuck = 0;

    for (group = 0; group < MAP_GROUPS_COUNT; group++)
    {
        for (num = 0; num < MAP_GROUP_COUNT[group]; num++)
        {
            const struct MapHeader *header = Overworld_GetMapHeaderByGroupAndId(group, num);
            const struct MapLayout *layout = header->mapLayout;

            for (i = 0; i < header->events->objectEventCount; i++)
            {
                const struct ObjectEventTemplate *template = &header->events->objectEvents[i];

                if (template->kind != OBJ_KIND_NORMAL || template->trainerType == TRAINER_TYPE_NONE)
                    continue;
                // Hidden trainers sit in trees, rocks and sand on purpose.
                if (template->movementType == MOVEMENT_TYPE_INVISIBLE
                 || template->movementType == MOVEMENT_TYPE_TREE_DISGUISE
                 || template->movementType == MOVEMENT_TYPE_MOUNTAIN_DISGUISE
                 || template->movementType == MOVEMENT_TYPE_BURIED)
                    continue;
                if (layout == NULL)
                    continue;
                if (template->x < 0 || template->y < 0 || template->x >= layout->width || template->y >= layout->height
                 || UNPACK_COLLISION(layout->map[template->y * layout->width + template->x]) != 0)
                {
                    Test_MgbaPrintf("map %d.%d object %d: trainer at (%d,%d) is inside a wall", group, num, i + 1, template->x, template->y);
                    stuck++;
                }
            }
        }
    }
    EXPECT_EQ(stuck, 0);
}
