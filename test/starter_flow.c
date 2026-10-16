#include "global.h"
#include "event_data.h"
#include "main.h"
#include "pokemon.h"
#include "sprite.h"
#include "ui_birch_case.h"
#include "test/test.h"

// BPE: picking a starter in the Birch Case opens the Stat Editor and then returns
// to the field script. These run the real screens frame by frame.

static void CB2_StarterFlowDone(void)
{
}

static void RunFrame(u16 keys)
{
    gMain.newKeys = keys;
    gMain.newAndRepeatedKeys = keys;
    gMain.heldKeys = keys;
    if (gMain.callback1 != NULL)
        gMain.callback1();
    gMain.callback2();
    if (gMain.vblankCallback != NULL)
        gMain.vblankCallback();
}

static void RunFrames(u32 frames, u16 keys)
{
    for (u32 i = 0; i < frames; i++)
        RunFrame(i == 0 ? keys : 0);
}

static u32 CountSpritesInUse(void)
{
    u32 count = 0;
    for (u32 i = 0; i < MAX_SPRITES; i++)
    {
        if (gSprites[i].inUse)
            count++;
    }
    return count;
}

// 2.2.1 froze on a black screen here: the case destroyed its ball sprites twice, the
// second time through ids already set to SPRITE_NONE, which reached far past gSprites.
TEST("Choosing a starter in the Birch Case frees its sprites and opens the Stat Editor")
{
    MainCallback testRunner = gMain.callback2;
    MainCallback caseCallback;
    u32 frames;

    FlagClear(FLAG_NUZLOCKE);
    ZeroPlayerPartyMons();
    gPartiesCount[B_TRAINER_PLAYER] = 0;

    BirchCase_Init(CB2_StarterFlowDone);
    RunFrames(120, 0);          // fade in
    RunFrames(10, A_BUTTON);    // pick the ball under the hand
    RunFrames(10, A_BUTTON);    // confirm it
    RunFrames(10, A_BUTTON);    // keep the nature, receive the starter
    EXPECT_EQ(gPartiesCount[B_TRAINER_PLAYER], 1);
    RunFrames(20, 0);           // the starter's sprite is redrawn

    // Fade out until the case closes and hands over to the Stat Editor.
    caseCallback = gMain.callback2;
    RunFrame(A_BUTTON);
    for (frames = 0; frames < 120 && gMain.callback2 == caseCallback; frames++)
        RunFrame(0);
    EXPECT(gMain.callback2 != caseCallback);
    EXPECT_EQ(CountSpritesInUse(), 0);

    // Leave the Stat Editor once it has faded in and takes input.
    for (frames = 0; frames < 600 && gMain.callback2 != CB2_StarterFlowDone; frames++)
        RunFrame(frames % 10 == 0 ? B_BUTTON : 0);
    EXPECT(gMain.callback2 == CB2_StarterFlowDone);

    SetMainCallback2(testRunner);
    SetVBlankCallback(NULL);
}
