#include "global.h"
#include "battle_main.h"
#include "battle_setup.h"
#include "battle_transition.h"
#include "dma3.h"
#include "link.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "sound.h"
#include "sprite.h"
#include "task.h"
#include "test/test.h"
#include "constants/opponents.h"
#include "constants/songs.h"

// BPE: fast forward runs the game logic 2 or 4 times per VBlank. These cover the
// rules around it; the frame loop itself is measured with a headless build.

TEST("The fast forward option uses padding, so older saves read it as off")
{
    EXPECT_EQ(offsetof(struct SaveBlock2, pokedex), 0x18);
    EXPECT_EQ(OPTIONS_FAST_FORWARD_OFF, 0);
}

TEST("Fast forward only mutes battle sounds on the battle screen")
{
    MainCallback callback2 = gMain.callback2;
    u32 option = gSaveBlock2Ptr->optionsFastForward;

    gMain.callback2 = BattleMainCB2;
    gSaveBlock2Ptr->optionsFastForward = OPTIONS_FAST_FORWARD_OFF;
    EXPECT(!IsFastForwardMutingBattleSfx());

    gSaveBlock2Ptr->optionsFastForward = OPTIONS_FAST_FORWARD_2X;
    EXPECT(IsFastForwardMutingBattleSfx());

    gMain.callback2 = CB2_Overworld;
    EXPECT(!IsFastForwardMutingBattleSfx());

    gMain.callback2 = callback2;
    gSaveBlock2Ptr->optionsFastForward = option;
}

TEST("Fast forward stays off during link play")
{
    MainCallback callback2 = gMain.callback2;
    u32 option = gSaveBlock2Ptr->optionsFastForward;

    gMain.callback2 = BattleMainCB2;
    gSaveBlock2Ptr->optionsFastForward = OPTIONS_FAST_FORWARD_4X;
    gReceivedRemoteLinkPlayers = TRUE;
    EXPECT(!IsFastForwardMutingBattleSfx());

    gReceivedRemoteLinkPlayers = FALSE;
    gMain.callback2 = callback2;
    gSaveBlock2Ptr->optionsFastForward = option;
}

TEST("Muted battle cries do not make the battle wait")
{
    MainCallback callback2 = gMain.callback2;
    u32 option = gSaveBlock2Ptr->optionsFastForward;

    gMain.callback2 = BattleMainCB2;
    gSaveBlock2Ptr->optionsFastForward = OPTIONS_FAST_FORWARD_4X;
    PlayCry_ByMode(SPECIES_WOBBUFFET, 0, CRY_MODE_NORMAL);
    EXPECT(IsCryFinished());

    gMain.callback2 = callback2;
    gSaveBlock2Ptr->optionsFastForward = option;
}

TEST("The DMA queue reports half full before it can drop requests")
{
    static const u32 sData = 0;
    u32 i, ime = REG_IME;
    bool32 halfFullEarly = FALSE, halfFull;

    // VBlank would empty the queue partway through
    REG_IME = 0;
    ClearDma3Requests();
    for (i = 0; i < 65; i++)
    {
        halfFullEarly |= IsDma3QueueHalfFull();
        RequestDma3Copy(&sData, (void *)VRAM, sizeof(sData), 1);
    }
    halfFull = IsDma3QueueHalfFull();
    ClearDma3Requests();
    REG_IME = ime;

    EXPECT(!halfFullEarly);
    EXPECT(halfFull);
}

TEST("The sprite copy queue reports half full before it can drop requests")
{
    static const u8 sData[4] = {0};
    u32 i;

    ClearSpriteCopyRequests();
    for (i = 0; i < 32; i++)
    {
        EXPECT(!IsSpriteCopyQueueHalfFull());
        RequestSpriteCopy(sData, (u8 *)OBJ_VRAM0, sizeof(sData));
    }
    EXPECT(IsSpriteCopyQueueHalfFull());
    ClearSpriteCopyRequests();
}

TEST("Every battle transition finishes at 4 logic passes per VBlank")
{
    u32 transition = 0, frame, pass;
    bool32 done = FALSE;

    for (u32 i = 0; i < B_TRANSITION_COUNT; i++)
    {
        PARAMETRIZE { transition = i; }
    }

    TRAINER_BATTLE_PARAM.opponentA = TRAINER_SIDNEY; // the mugshots read these
    TRAINER_BATTLE_PARAM.opponentB = TRAINER_NONE;
    // The field's VBlank callback does this for the transitions without their own
    SetVBlankCallback(TransferPlttBuffer);
    BattleTransition_Start(transition);
    for (frame = 0; frame < 1000 && !done; frame++)
    {
        for (pass = 0; pass < 4 && !done; pass++)
        {
            RunTasks();
            AnimateSprites();
            BuildOamBuffer();
            UpdatePaletteFade();
            done = IsBattleTransitionDone();
        }
        VBlankIntrWait();
    }
    SetVBlankCallback(NULL);
    SetHBlankCallback(NULL);
    EXPECT(done);
}
