#include "global.h"
#include "battle_main.h"
#include "battle_setup.h"
#include "battle_transition.h"
#include "dma3.h"
#include "event_data.h"
#include "field_weather.h"
#include "gpu_regs.h"
#include "gba/m4a_internal.h"
#include "link.h"
#include "item.h"
#include "m4a.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "sound.h"
#include "sprite.h"
#include "task.h"
#include "test/test.h"
#include "constants/items.h"
#include "constants/opponents.h"
#include "constants/songs.h"

// BPE: the Speed Boy runs the game logic 2 to 4 times per VBlank. These cover the
// rules around it; the frame loop itself is measured with a headless build.

TEST("The Speed Boy is a key item")
{
    EXPECT_EQ(GetItemPocket(ITEM_SPEED_BOY), POCKET_KEY_ITEMS);
    EXPECT_EQ(GetItemImportance(ITEM_SPEED_BOY), 1);
}

TEST("The Speed Boy cycles through 2x, 3x and 4x")
{
    FlagClear(FLAG_SPEED_BOY_SPEED_LO);
    FlagClear(FLAG_SPEED_BOY_SPEED_HI);
    EXPECT_EQ(GetFastForwardSpeed(), 2);
    CycleFastForwardSpeed();
    EXPECT_EQ(GetFastForwardSpeed(), 3);
    CycleFastForwardSpeed();
    EXPECT_EQ(GetFastForwardSpeed(), 4);
    CycleFastForwardSpeed();
    EXPECT_EQ(GetFastForwardSpeed(), 2);
}

TEST("Fast forward only speeds up sounds on the battle screen")
{
    MainCallback callback2 = gMain.callback2;

    FlagClear(FLAG_SPEED_BOY_SPEED_LO);
    FlagClear(FLAG_SPEED_BOY_SPEED_HI);
    gMain.callback2 = BattleMainCB2;
    FlagClear(FLAG_SPEED_BOY_ON);
    EXPECT_EQ(GetFastForwardBattleSoundSpeed(), 1);

    FlagSet(FLAG_SPEED_BOY_ON);
    EXPECT_EQ(GetFastForwardBattleSoundSpeed(), 2);

    CycleFastForwardSpeed();
    EXPECT_EQ(GetFastForwardBattleSoundSpeed(), 3);

    gMain.callback2 = CB2_Overworld;
    EXPECT_EQ(GetFastForwardBattleSoundSpeed(), 1);

    FlagClear(FLAG_SPEED_BOY_ON);
    gMain.callback2 = callback2;
}

TEST("Fast forward stays off during link play")
{
    MainCallback callback2 = gMain.callback2;

    gMain.callback2 = BattleMainCB2;
    FlagSet(FLAG_SPEED_BOY_ON);
    gReceivedRemoteLinkPlayers = TRUE;
    EXPECT_EQ(GetFastForwardBattleSoundSpeed(), 1);

    gReceivedRemoteLinkPlayers = FALSE;
    FlagClear(FLAG_SPEED_BOY_ON);
    gMain.callback2 = callback2;
}

TEST("The wireless state left by a Pokemon Center does not stop fast forward")
{
    MainCallback callback2 = gMain.callback2;

    gMain.callback2 = BattleMainCB2;
    FlagSet(FLAG_SPEED_BOY_ON);
    gWirelessCommType = 1;
    EXPECT_GT(GetFastForwardBattleSoundSpeed(), 1);

    gWirelessCommType = 0;
    FlagClear(FLAG_SPEED_BOY_ON);
    gMain.callback2 = callback2;
}

TEST("A fade from black that ends early still restores the shadow blend")
{
    u32 eva = gWeatherPtr->currBlendEVA, evb = gWeatherPtr->currBlendEVB;

    gWeatherPtr->currBlendEVA = 8;
    gWeatherPtr->currBlendEVB = 12;
    SetGpuReg(REG_OFFSET_BLDALPHA, BLDALPHA_BLEND(0, 0));
    BeginHardwarePaletteFade(BLDCNT_TGT2_ALL | BLDCNT_EFFECT_DARKEN, 0, 1, 0, FALSE);
    for (u32 i = 0; i < 8 && gPaletteFade.active; i++)
    {
        UpdatePaletteFade();
        TransferPlttBuffer();
    }
    EXPECT(!gPaletteFade.active);
    EXPECT_EQ(GetGpuReg(REG_OFFSET_BLDALPHA), BLDALPHA_BLEND(8, 12));

    gWeatherPtr->currBlendEVA = eva;
    gWeatherPtr->currBlendEVB = evb;
    ResetPaletteFade();
}

TEST("Panned battle sounds play at the fast forward tempo")
{
    MainCallback callback2 = gMain.callback2;
    struct MusicPlayerInfo *player = gMPlayTable[gSongTable[SE_M_HARDEN].ms].info;
    struct MusicPlayerInfo *other = player == &gMPlayInfo_SE1 ? &gMPlayInfo_SE2 : &gMPlayInfo_SE1;

    FlagClear(FLAG_SPEED_BOY_SPEED_LO);
    FlagSet(FLAG_SPEED_BOY_SPEED_HI);
    gMain.callback2 = BattleMainCB2;
    FlagSet(FLAG_SPEED_BOY_ON);
    other->tempoU = 1 << 8;
    PlaySE12WithPanning(SE_M_HARDEN, 0);
    EXPECT_EQ(player->tempoU, 4 << 8);
    EXPECT_EQ(other->tempoU, 1 << 8);
    EXPECT_EQ(player->tracks[0].keyShiftX, 0);
    EXPECT_EQ(player->tracks[0].pitX, 0);

    FlagClear(FLAG_SPEED_BOY_ON);
    PlaySE12WithPanning(SE_M_HARDEN, 0);
    EXPECT_EQ(player->tempoU, 1 << 8);

    m4aMPlayStop(&gMPlayInfo_SE1);
    m4aMPlayStop(&gMPlayInfo_SE2);
    gMain.callback2 = callback2;
}

TEST("Battle cries are shorter under fast forward but keep their pitch")
{
    MainCallback callback2 = gMain.callback2;
    u32 key, tune, length;

    FlagClear(FLAG_SPEED_BOY_SPEED_LO);
    FlagSet(FLAG_SPEED_BOY_SPEED_HI);
    gMain.callback2 = BattleMainCB2;
    FlagClear(FLAG_SPEED_BOY_ON);
    PlayCry_ByMode(SPECIES_PIKACHU, 0, CRY_MODE_NORMAL);
    key = gPokemonCrySong.tieKeyValue;
    tune = gPokemonCrySong.tuneValue;
    length = gPokemonCrySong.length;
    StopCryAndClearCrySongs();

    FlagSet(FLAG_SPEED_BOY_ON);
    PlayCry_ByMode(SPECIES_PIKACHU, 0, CRY_MODE_NORMAL);
    EXPECT_EQ(gPokemonCrySong.tieKeyValue, key);
    EXPECT_EQ(gPokemonCrySong.tuneValue, tune);
    EXPECT_EQ(gPokemonCrySong.length, length / 4);
    StopCryAndClearCrySongs();
    DestroyTask(FindTaskIdByFunc(Task_DuckBGMForPokemonCry));

    FlagClear(FLAG_SPEED_BOY_ON);
    gMain.callback2 = callback2;
}

TEST("A sound counts as playing before the sound engine first reads it")
{
    struct MusicPlayerInfo *player = gMPlayTable[gSongTable[SE_M_HARDEN].ms].info;
    u32 ime = REG_IME;
    bool32 playing;

    // No VBlank here, as between two fast forward passes. A cry that reads as
    // stopped now has its song data cleared, and the sound engine hangs on it.
    REG_IME = 0;
    m4aSongNumStart(SE_M_HARDEN);
    playing = IsPokemonCryPlaying(player);
    REG_IME = ime;

    EXPECT(playing);
    m4aMPlayStop(player);
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
