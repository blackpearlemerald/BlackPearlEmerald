#include "global.h"
#include "ui_stat_editor.h"
#include "pokemon.h"
#include "strings.h"
#include "bg.h"
#include "caps.h"
#include "data.h"
#include "decompress.h"
#include "event_data.h"
#include "field_weather.h"
#include "gpu_regs.h"
#include "graphics.h"
#include "item.h"
#include "item_menu.h"
#include "item_menu_icons.h"
#include "list_menu.h"
#include "item_icon.h"
#include "item_use.h"
#include "international_string_util.h"
#include "main.h"
#include "malloc.h"
#include "menu.h"
#include "menu_helpers.h"
#include "palette.h"
#include "party_menu.h"
#include "scanline_effect.h"
#include "script.h"
#include "sound.h"
#include "string_util.h"
#include "strings.h"
#include "task.h"
#include "text_window.h"
#include "overworld.h"
#include "event_data.h"
#include "constants/items.h"
#include "constants/field_weather.h"
#include "constants/songs.h"
#include "constants/rgb.h"
#include "pokemon_icon.h"
#include "pokedex.h"
#include "trainer_pokemon_sprites.h"
#include "field_screen_effect.h"

// BPE custom strings
const u8 gText_StatEditor[] = _("STAT EDITOR");

/*
 *
 */

//==========DEFINES==========//
struct StatEditorResources
{
    MainCallback savedCallback;     // determines callback to run when we exit. e.g. where do we want to go after closing the menu
    u8 gfxLoadState;
    u8 mode;
    u8 monIconSpriteId;
    u16 speciesID;
    u16 selectedStat;
    u16 selectorSpriteId;
    u16 selector_x;
    u16 selector_y;
    u32 editingStat;
    u16 normalTotal;
    u16 evTotal;
    u16 ivTotal;
    u16 partyid;
    u16 inputMode;
    bool8 canEdit;                  // BPE: Standard mode only; Nuzlocke games just view
    u8 wideSelectorSpriteId;
    u8 infoRow;
};

#define INPUT_SELECT_STAT 0
#define INPUT_EDIT_STAT 1

// BPE: selector_x picks the EV column, the IV column or the Ability/Nature panel on the left.
#define SELECTOR_COLUMN_EV   0
#define SELECTOR_COLUMN_IV   1
#define SELECTOR_COLUMN_INFO 2
#define SELECTOR_COLUMNS     3

#define INFO_ROW_ABILITY 0
#define INFO_ROW_NATURE  1
#define INFO_ROWS        2

#define STAT_ROWS 6

enum WindowIds
{
    WINDOW_1,
    WINDOW_2,
    WINDOW_3,
    WINDOW_4,
};

//==========EWRAM==========//
static EWRAM_DATA struct StatEditorResources *sStatEditorDataPtr = NULL;
static EWRAM_DATA u8 *sBg1TilemapBuffer = NULL;

//==========STATIC=DEFINES==========//
static void StatEditor_RunSetup(void);
static bool8 StatEditor_DoGfxSetup(void);
static bool8 StatEditor_InitBgs(void);
static void StatEditor_FadeAndBail(void);
static bool8 StatEditor_LoadGraphics(void);
static void StatEditor_InitWindows(void);
static void PrintTitleToWindowMainState();
static void Task_StatEditorWaitFadeIn(u8 taskId);
static void Task_StatEditorMain(u8 taskId);
static void Task_MenuEditingStat(u8 taskId);
static void SampleUi_DrawMonIcon(u16 dexNum);
static void PrintMonStats(void);
static void SelectorCallback(struct Sprite *sprite);
static struct Pokemon *ReturnPartyMon();
static u8 CreateSelector();
static void DestroySelector();

//==========CONST=DATA==========//
static const struct BgTemplate sStatEditorBgTemplates[] =
{
    {
        .bg = 0,    // windows, etc
        .charBaseIndex = 0,
        .mapBaseIndex = 30,
        .priority = 1
    }, 
    {
        .bg = 1,    // this bg loads the UI tilemap
        .charBaseIndex = 3,
        .mapBaseIndex = 28,
        .priority = 2
    },
    {
        .bg = 2,    // this bg loads the UI tilemap
        .charBaseIndex = 0,
        .mapBaseIndex = 26,
        .priority = 0
    }
};

static const struct WindowTemplate sMenuWindowTemplates[] = 
{
    [WINDOW_1] = 
    {
        .bg = 0,            // which bg to print text on
        .tilemapLeft = 1,   // position from left (per 8 pixels)
        .tilemapTop = 0,    // position from top (per 8 pixels)
        .width = 30,        // width (per 8 pixels)
        .height = 2,        // height (per 8 pixels)
        .paletteNum = 15,   // palette index to use for text
        .baseBlock = 1,     // tile start in VRAM
    },
    [WINDOW_2] = 
    {
        .bg = 0,            // which bg to print text on
        .tilemapLeft = 11,   // position from left (per 8 pixels)
        .tilemapTop = 2,    // position from top (per 8 pixels)
        .width = 18,        // width (per 8 pixels)
        .height = 17,        // height (per 8 pixels)
        .paletteNum = 15,   // palette index to use for text
        .baseBlock = 1 + 70,     // tile start in VRAM
    },
    [WINDOW_3] =
    {
        .bg = 0,            // which bg to print text on
        .tilemapLeft = 1,   // position from left (per 8 pixels)
        .tilemapTop = 11,    // position from top (per 8 pixels)
        .width = 8,        // width (per 8 pixels)
        .height = 9,        // height (per 8 pixels)
        .paletteNum = 15,   // palette index to use for text
        .baseBlock = 1 + 70 + 306,     // tile start in VRAM
    },
    DUMMY_WIN_TEMPLATE,
};

static const u32 sStatEditorBgTiles[] = INCGFX_U32("graphics/ui_menu/background_tileset.png", ".4bpp.lz");
static const u32 sStatEditorBgTilemap[] = INCGFX_U32("graphics/ui_menu/background_tileset.bin", ".lz");
static const u16 sStatEditorBgPalette[] = INCGFX_U16("graphics/ui_menu/background_pal.pal", ".gbapal");

enum Colors
{
    FONT_BLACK,
    FONT_WHITE,
    FONT_RED,
    FONT_BLUE,
};
static const u8 sMenuWindowFontColors[][3] = 
{
    [FONT_BLACK]  = {TEXT_COLOR_TRANSPARENT,  TEXT_COLOR_DARK_GRAY,  TEXT_COLOR_LIGHT_GRAY},
    [FONT_WHITE]  = {TEXT_COLOR_TRANSPARENT,  TEXT_COLOR_WHITE,  TEXT_COLOR_DARK_GRAY},
    [FONT_RED]   = {TEXT_COLOR_TRANSPARENT,  TEXT_COLOR_RED,        TEXT_COLOR_LIGHT_GRAY},
    [FONT_BLUE]  = {TEXT_COLOR_TRANSPARENT,  TEXT_COLOR_BLUE,       TEXT_COLOR_LIGHT_GRAY},
};

#define TAG_SELECTOR 30004
#define TAG_SELECTOR_WIDE 30005

static const u16 sSelector_Pal[] = INCGFX_U16("graphics/ui_menu/selector.png", ".gbapal");
static const u32 sSelector_Gfx[] = INCGFX_U32("graphics/ui_menu/selector.png", ".4bpp.lz");
static const u32 sSelectorWide_Gfx[] = INCGFX_U32("graphics/ui_menu/selector_wide.png", ".4bpp.lz");
static const u8 sA_ButtonGfx[]         = INCGFX_U8("graphics/ui_menu/a_button.png", ".4bpp");
static const u8 sB_ButtonGfx[]         = INCGFX_U8("graphics/ui_menu/b_button.png", ".4bpp");
static const u8 sR_ButtonGfx[]         = INCGFX_U8("graphics/ui_menu/r_button.png", ".4bpp");
static const u8 sDPad_ButtonGfx[]         = INCGFX_U8("graphics/ui_menu/dpad_button.png", ".4bpp");

static const struct OamData sOamData_Selector =
{
    .size = SPRITE_SIZE(32x32),
    .shape = SPRITE_SHAPE(32x32),
    .priority = 0,
};

static const struct CompressedSpriteSheet sSpriteSheet_Selector =
{
    .data = sSelector_Gfx,
    .size = 32*32*4/2,
    .tag = TAG_SELECTOR,
};

static const struct SpritePalette sSpritePal_Selector =
{
    .data = sSelector_Pal,
    .tag = TAG_SELECTOR
};

// BPE: a 64-pixel-wide selector for the Ability and Nature boxes.
static const struct OamData sOamData_SelectorWide =
{
    .size = SPRITE_SIZE(64x32),
    .shape = SPRITE_SHAPE(64x32),
    .priority = 0,
};

static const struct CompressedSpriteSheet sSpriteSheet_SelectorWide =
{
    .data = sSelectorWide_Gfx,
    .size = 64*32*4/2,
    .tag = TAG_SELECTOR_WIDE,
};

// Selector frames: white while choosing, red at the maximum, blue at the minimum, gold while editing.
static const union AnimCmd sSpriteAnim_Selector0[] =
{
    ANIMCMD_FRAME(0, 32),
    ANIMCMD_FRAME(0, 32),
    //ANIMCMD_FRAME(48, 10),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd sSpriteAnim_Selector1[] =
{
    ANIMCMD_FRAME(32, 32),
    ANIMCMD_FRAME(32, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd sSpriteAnim_Selector2[] =
{
    ANIMCMD_FRAME(16, 32),
    ANIMCMD_FRAME(16, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd sSpriteAnim_Selector3[] =
{
    ANIMCMD_FRAME(48, 32),
    ANIMCMD_FRAME(48, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd *const sSpriteAnimTable_Selector[] =
{
    sSpriteAnim_Selector0,
    sSpriteAnim_Selector1,
    sSpriteAnim_Selector2,
    sSpriteAnim_Selector3,
};

// The wide frames are 32 tiles each, so the same four frames start at 0, 32, 64 and 96.
static const union AnimCmd sSpriteAnim_SelectorWide0[] =
{
    ANIMCMD_FRAME(0, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd sSpriteAnim_SelectorWide1[] =
{
    ANIMCMD_FRAME(64, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd sSpriteAnim_SelectorWide2[] =
{
    ANIMCMD_FRAME(32, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd sSpriteAnim_SelectorWide3[] =
{
    ANIMCMD_FRAME(96, 32),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd *const sSpriteAnimTable_SelectorWide[] =
{
    sSpriteAnim_SelectorWide0,
    sSpriteAnim_SelectorWide1,
    sSpriteAnim_SelectorWide2,
    sSpriteAnim_SelectorWide3,
};

#define SELECTOR_ANIM_CHOOSING 0
#define SELECTOR_ANIM_AT_MIN   1
#define SELECTOR_ANIM_AT_MAX   2
#define SELECTOR_ANIM_EDITING  3

static const struct SpriteTemplate sSpriteTemplate_Selector =
{
    .tileTag = TAG_SELECTOR,
    .paletteTag = TAG_SELECTOR,
    .oam = &sOamData_Selector,
    .anims = sSpriteAnimTable_Selector,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SelectorCallback
};

static const struct SpriteTemplate sSpriteTemplate_SelectorWide =
{
    .tileTag = TAG_SELECTOR_WIDE,
    .paletteTag = TAG_SELECTOR,
    .oam = &sOamData_SelectorWide,
    .anims = sSpriteAnimTable_SelectorWide,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SelectorCallback
};

// Begin Generic UI Initialization Code
void Task_OpenStatEditorFromStartMenu(u8 taskId)
{
    if (!gPaletteFade.active)
    {
        CleanupOverworldWindowsAndTilemaps();
        StatEditor_Init(CB2_ReturnToFieldWithOpenMenu);
        DestroyTask(taskId);
    }
}

// This is our main initialization function if you want to call the menu from elsewhere
void StatEditor_Init(MainCallback callback)
{
    if ((sStatEditorDataPtr = AllocZeroed(sizeof(struct StatEditorResources))) == NULL)
    {
        SetMainCallback2(callback);
        return;
    }
    
    // initialize stuff
    sStatEditorDataPtr->gfxLoadState = 0;
    sStatEditorDataPtr->savedCallback = callback;
    sStatEditorDataPtr->selectorSpriteId = 0xFF;
    sStatEditorDataPtr->wideSelectorSpriteId = 0xFF;
    sStatEditorDataPtr->partyid = gSpecialVar_0x8004;
    
    SetMainCallback2(StatEditor_RunSetup);
}

static void StatEditor_RunSetup(void)
{
    StatEditor_DoGfxSetup();
}

static void StatEditor_MainCB(void)
{
    RunTasks();
    AnimateSprites();
    BuildOamBuffer();
    DoScheduledBgTilemapCopiesToVram();
    UpdatePaletteFade();
}

static void StatEditor_VBlankCB(void)
{
    LoadOam();
    ProcessSpriteCopyRequests();
    TransferPlttBuffer();
}

static bool8 StatEditor_DoGfxSetup(void)
{
    switch (gMain.state)
    {
    case 0:
        DmaClearLarge16(3, (void *)VRAM, VRAM_SIZE, 0x1000)
        SetVBlankHBlankCallbacksToNull();
        ResetVramOamAndBgCntRegs();
        ClearScheduledBgCopiesToVram();
        gMain.state++;
        break;
    case 1:
        ScanlineEffect_Stop();
        FreeAllSpritePalettes();
        ResetPaletteFade();
        ResetSpriteData();
        ResetTasks();
        gMain.state++;
        break;
    case 2:
        if (StatEditor_InitBgs())
        {
            sStatEditorDataPtr->gfxLoadState = 0;
            gMain.state++;
        }
        else
        {
            StatEditor_FadeAndBail();
            return TRUE;
        }
        break;
    case 3:
        if (StatEditor_LoadGraphics() == TRUE)
            gMain.state++;
        break;
    case 4:
        sStatEditorDataPtr->speciesID = GetMonData(ReturnPartyMon(), MON_DATA_SPECIES);
        sStatEditorDataPtr->canEdit = StatEditor_CanEditMon(ReturnPartyMon());
        FreeMonIconPalettes();
        LoadMonIconPalettes();
        LoadCompressedSpriteSheet(&sSpriteSheet_Selector);
        LoadCompressedSpriteSheet(&sSpriteSheet_SelectorWide);
        LoadSpritePalette(&sSpritePal_Selector);
        SampleUi_DrawMonIcon(sStatEditorDataPtr->speciesID);
        gMain.state++;
        break;
    case 5:
        StatEditor_InitWindows();
        PrintTitleToWindowMainState();
        sStatEditorDataPtr->inputMode = INPUT_SELECT_STAT;
        PrintMonStats();
        CreateSelector();
        gMain.state++;
        break;
    case 6:
        CreateTask(Task_StatEditorWaitFadeIn, 0);
        BlendPalettes(0xFFFFFFFF, 16, RGB_BLACK);
        gMain.state++;
        break;
    case 7:
        BeginNormalPaletteFade(0xFFFFFFFF, 0, 16, 0, RGB_BLACK);
        gMain.state++;
        break;
    default:
        SetVBlankCallback(StatEditor_VBlankCB);
        SetMainCallback2(StatEditor_MainCB);
        return TRUE;
    }
    return FALSE;
}

#define try_free(ptr) ({               \
    void ** ptr__ = (void **)&(ptr);   \
    if (*ptr__ != NULL) {              \
        Free(*ptr__);                  \
        *ptr__ = NULL;                 \
    }                                  \
})

static void StatEditor_FreeResources(void)
{
    DestroySelector();
    FreeAndDestroyMonPicSprite(sStatEditorDataPtr->monIconSpriteId);
    try_free(sStatEditorDataPtr);
    try_free(sBg1TilemapBuffer);
    FreeAllWindowBuffers();
}


static void Task_StatEditorWaitFadeAndBail(u8 taskId)
{
    if (!gPaletteFade.active)
    {
        SetMainCallback2(sStatEditorDataPtr->savedCallback);
        StatEditor_FreeResources();
        DestroyTask(taskId);
    }
}

static void StatEditor_FadeAndBail(void)
{
    BeginNormalPaletteFade(0xFFFFFFFF, 0, 0, 16, RGB_BLACK);
    CreateTask(Task_StatEditorWaitFadeAndBail, 0);
    SetVBlankCallback(StatEditor_VBlankCB);
    SetMainCallback2(StatEditor_MainCB);
}

static bool8 StatEditor_InitBgs(void)
{
    ResetAllBgsCoordinates();
    sBg1TilemapBuffer = Alloc(0x800);
    if (sBg1TilemapBuffer == NULL)
        return FALSE;
    
    memset(sBg1TilemapBuffer, 0, 0x800);
    ResetBgsAndClearDma3BusyFlags(0);
    InitBgsFromTemplates(0, sStatEditorBgTemplates, NELEMS(sStatEditorBgTemplates));
    SetBgTilemapBuffer(1, sBg1TilemapBuffer);
    ScheduleBgCopyTilemapToVram(1);
    SetGpuReg(REG_OFFSET_DISPCNT, DISPCNT_OBJ_ON | DISPCNT_OBJ_1D_MAP);
    ShowBg(0);
    ShowBg(1);
    ShowBg(2);
    return TRUE;
}

static bool8 StatEditor_LoadGraphics(void)
{
    switch (sStatEditorDataPtr->gfxLoadState)
    {
    case 0:
        ResetTempTileDataBuffers();
        DecompressAndCopyTileDataToVram(1, sStatEditorBgTiles, 0, 0, 0);
        sStatEditorDataPtr->gfxLoadState++;
        break;
    case 1:
        if (FreeTempTileDataBuffersIfPossible() != TRUE)
        {
            DecompressDataWithHeaderWram(sStatEditorBgTilemap, sBg1TilemapBuffer);
            sStatEditorDataPtr->gfxLoadState++;
        }
        break;
    case 2:
        LoadPalette(sStatEditorBgPalette, 0, 32);
        sStatEditorDataPtr->gfxLoadState++;
        break;
    default:
        sStatEditorDataPtr->gfxLoadState = 0;
        return TRUE;
    }
    return FALSE;
}

static void StatEditor_InitWindows(void)
{
    InitWindows(sMenuWindowTemplates);
    DeactivateAllTextPrinters();
    ScheduleBgCopyTilemapToVram(0);
    
    FillWindowPixelBuffer(WINDOW_1, 0);
    PutWindowTilemap(WINDOW_1);
    CopyWindowToVram(WINDOW_1, 3);
    
    ScheduleBgCopyTilemapToVram(2);
}

static void Task_StatEditorWaitFadeIn(u8 taskId)
{
    if (!gPaletteFade.active)
        gTasks[taskId].func = Task_StatEditorMain;
}

static void Task_StatEditorTurnOff(u8 taskId)
{
    // s16 *data = gTasks[taskId].data;

    if (!gPaletteFade.active)
    {
        SetMainCallback2(sStatEditorDataPtr->savedCallback);
        StatEditor_FreeResources();
        DestroyTask(taskId);
    }
}

//
//       Stat Editor Code
//  End of UI setup code, beginning of stat editor specific code
//
static struct Pokemon *ReturnPartyMon()
{
    return &gParties[B_TRAINER_PLAYER][sStatEditorDataPtr->partyid];
}

#define MON_ICON_X     32 + 8
#define MON_ICON_Y     32 + 24
static void SampleUi_DrawMonIcon(u16 dexNum)
{
    u16 speciesId = dexNum;
    // BPE: draw the Pokemon itself, not a stock picture of its species, so a shiny
    // shows its own colours here and gender differences match the mon.
    struct Pokemon *mon = ReturnPartyMon();
    bool8 isShiny = IsMonShiny(mon);
    u32 personality = GetMonData(mon, MON_DATA_PERSONALITY);

    sStatEditorDataPtr->monIconSpriteId = CreateMonPicSprite(speciesId, isShiny, personality, TRUE, MON_ICON_X, MON_ICON_Y, 0, TAG_NONE);

    gSprites[sStatEditorDataPtr->monIconSpriteId].oam.priority = 0;
}

static u8 CreateSelector()
{
    if (sStatEditorDataPtr->selectorSpriteId == 0xFF)
        sStatEditorDataPtr->selectorSpriteId = CreateSprite(&sSpriteTemplate_Selector, 188, 30, 0);
    if (sStatEditorDataPtr->wideSelectorSpriteId == 0xFF)
    {
        sStatEditorDataPtr->wideSelectorSpriteId = CreateSprite(&sSpriteTemplate_SelectorWide, 40, 130, 0);
        gSprites[sStatEditorDataPtr->wideSelectorSpriteId].data[1] = TRUE;
    }

    StartSpriteAnim(&gSprites[sStatEditorDataPtr->selectorSpriteId], SELECTOR_ANIM_CHOOSING);
    StartSpriteAnim(&gSprites[sStatEditorDataPtr->wideSelectorSpriteId], SELECTOR_ANIM_CHOOSING);
    DebugPrintf("Sprite ID: %d", sStatEditorDataPtr->selectorSpriteId);
    return sStatEditorDataPtr->selectorSpriteId;
}

static void DestroySelector()
{
    if (sStatEditorDataPtr->selectorSpriteId != 0xFF)
        DestroySprite(&gSprites[sStatEditorDataPtr->selectorSpriteId]);
    sStatEditorDataPtr->selectorSpriteId = 0xFF;
    if (sStatEditorDataPtr->wideSelectorSpriteId != 0xFF)
        DestroySprite(&gSprites[sStatEditorDataPtr->wideSelectorSpriteId]);
    sStatEditorDataPtr->wideSelectorSpriteId = 0xFF;
}

#define DISTANCE_BETWEEN_STATS_Y 16
#define SECOND_COLUMN ((8 * 4))
#define THIRD_COLUMN ((8 * 8))
#define STARTING_X 60
#define STARTING_Y 26

struct MonPrintData {
    u16 x;
    u16 y;
};

static const struct MonPrintData StatPrintData[] =
{
    [MON_DATA_MAX_HP] = {STARTING_X, STARTING_Y},
    [MON_DATA_HP_EV] = {STARTING_X + SECOND_COLUMN, STARTING_Y},
    [MON_DATA_HP_IV] = {STARTING_X + THIRD_COLUMN, STARTING_Y},

    [MON_DATA_ATK] = {STARTING_X, STARTING_Y + DISTANCE_BETWEEN_STATS_Y},
    [MON_DATA_ATK_EV] = {STARTING_X + SECOND_COLUMN, STARTING_Y + DISTANCE_BETWEEN_STATS_Y},
    [MON_DATA_ATK_IV] = {STARTING_X + THIRD_COLUMN, STARTING_Y + DISTANCE_BETWEEN_STATS_Y},

    [MON_DATA_DEF] = {STARTING_X, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 2)},
    [MON_DATA_DEF_EV] = {STARTING_X + SECOND_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 2)},
    [MON_DATA_DEF_IV] = {STARTING_X + THIRD_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 2)},

    [MON_DATA_SPATK] = {STARTING_X, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 3)},
    [MON_DATA_SPATK_EV] = {STARTING_X + SECOND_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 3)},
    [MON_DATA_SPATK_IV] = {STARTING_X + THIRD_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 3)},

    [MON_DATA_SPDEF] = {STARTING_X, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 4)},
    [MON_DATA_SPDEF_EV] = {STARTING_X + SECOND_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 4)},
    [MON_DATA_SPDEF_IV] = {STARTING_X + THIRD_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 4)},

    [MON_DATA_SPEED] = {STARTING_X, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 5)},
    [MON_DATA_SPEED_EV] = {STARTING_X + SECOND_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 5)},
    [MON_DATA_SPEED_IV] = {STARTING_X + THIRD_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 5)},
};

static const u16 statsToPrintActual[] = {
        MON_DATA_MAX_HP, MON_DATA_ATK, MON_DATA_DEF, MON_DATA_SPEED, MON_DATA_SPATK, MON_DATA_SPDEF,
};

static const u16 statsToPrintEVs[] = {
        MON_DATA_HP_EV, MON_DATA_ATK_EV, MON_DATA_DEF_EV, MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV,
};

static const u16 statsToPrintIVs[] = {
        MON_DATA_HP_IV, MON_DATA_ATK_IV, MON_DATA_DEF_IV, MON_DATA_SPEED_IV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_IV,
};


static const u8 sGenderColors[2][3] =
{
    {TEXT_COLOR_TRANSPARENT, TEXT_COLOR_LIGHT_BLUE, TEXT_COLOR_BLUE},
    {TEXT_COLOR_TRANSPARENT, TEXT_COLOR_LIGHT_RED, TEXT_COLOR_RED}
};

//static const u8 sText_MenuTitle[] = _("Stat Editor");
static const u8 sText_MenuHP[] = _("HP");
static const u8 sText_MenuAttack[] = _("Attack");
static const u8 sText_MenuSpAttack[] = _("Sp. Atk");
static const u8 sText_MenuDefense[] = _("Defense");
static const u8 sText_MenuSpDefense[] = _("Sp. Def");
static const u8 sText_MenuSpeed[] = _("Speed");
static const u8 sText_MenuTotal[] = _("Total");
static const u8 sText_MenuStat[] = _("Stat");
static const u8 sText_MenuActual[] = _("Actual");
static const u8 sText_MenuEV[] = _("EV");
static const u8 sText_MenuIV[] = _("IV");
static const u8 sText_MonLevel[]         = _("Lv.{CLEAR 1}{STR_VAR_1}");

static const u8 sText_MenuAButtonTextMain[]    = _("Edit");
static const u8 sText_MenuBButtonTextMain[]    = _("Back");
static const u8 sText_MenuBButtonTextEdit[]    = _("Done");
static const u8 sText_MenuDPadButtonTextMain[] = _("Move");
static const u8 sText_MenuDPadButtonTextEdit[] = _("Change");

#define BUTTON_Y 4
#define HINT_DPAD_X 60
#define HINT_A_X    124
#define HINT_B_X    170

static void PrintButtonHint(const u8 *gfx, u32 x, u32 width, const u8 *text)
{
    BlitBitmapToWindow(WINDOW_1, gfx, x, BUTTON_Y, width, 8);
    AddTextPrinterParameterized4(WINDOW_1, FONT_NARROW, x + width + 4, 0, 0, 0, sMenuWindowFontColors[FONT_WHITE], TEXT_SKIP_DRAW, text);
}

static void PrintTitleToWindowMainState()
{
    FillWindowPixelBuffer(WINDOW_1, PIXEL_FILL(TEXT_COLOR_TRANSPARENT));

    // BPE: Nuzlocke games can only look, so they get just the way out.
    if (sStatEditorDataPtr->canEdit)
    {
        PrintButtonHint(sDPad_ButtonGfx, HINT_DPAD_X, 24, sText_MenuDPadButtonTextMain);
        PrintButtonHint(sA_ButtonGfx, HINT_A_X, 8, sText_MenuAButtonTextMain);
    }
    PrintButtonHint(sB_ButtonGfx, HINT_B_X, 8, sText_MenuBButtonTextMain);

    PutWindowTilemap(WINDOW_1);
    CopyWindowToVram(WINDOW_1, 3);
}

static void PrintTitleToWindowEditState()
{
    FillWindowPixelBuffer(WINDOW_1, PIXEL_FILL(TEXT_COLOR_TRANSPARENT));

    PrintButtonHint(sDPad_ButtonGfx, HINT_DPAD_X, 24, sText_MenuDPadButtonTextEdit);
    PrintButtonHint(sB_ButtonGfx, HINT_B_X, 8, sText_MenuBButtonTextEdit);

    PutWindowTilemap(WINDOW_1);
    CopyWindowToVram(WINDOW_1, 3);
}

static void PrintMonStats()
{
    u8 i;
    u16 currentStat;
    u16 nature;
    u8 text[2];
    u16 level = GetMonData(ReturnPartyMon(), MON_DATA_LEVEL);
    u16 personality = GetMonData(ReturnPartyMon(), MON_DATA_PERSONALITY);
    u16 gender = GetGenderFromSpeciesAndPersonality(sStatEditorDataPtr->speciesID, personality);

    FillWindowPixelBuffer(WINDOW_2, PIXEL_FILL(TEXT_COLOR_TRANSPARENT));
    FillWindowPixelBuffer(WINDOW_3, PIXEL_FILL(TEXT_COLOR_TRANSPARENT));

    sStatEditorDataPtr->normalTotal = 0;
    sStatEditorDataPtr->evTotal = 0;
    sStatEditorDataPtr->ivTotal = 0;

    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 18, 7, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuStat);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, STARTING_X - 6, 7, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuActual);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, STARTING_X + SECOND_COLUMN + 4, 7, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuEV);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, STARTING_X + THIRD_COLUMN + 5, 7, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuIV);

    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 24, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 0), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuHP);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 12, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 1), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuAttack);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 12, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 2), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuDefense);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 10, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 3), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuSpAttack);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 12, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 4), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuSpDefense);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 16, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 5), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuSpeed);
    AddTextPrinterParameterized4(WINDOW_2, FONT_NARROW, 16, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 6), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, sText_MenuTotal);

    // Print Mon Stats
    for(i = 0; i < 6; i++)
    {
        currentStat = GetMonData(ReturnPartyMon(), statsToPrintActual[i]);
        sStatEditorDataPtr->normalTotal += currentStat;
        DebugPrintf("Stat: %d", currentStat);
        ConvertIntToDecimalStringN(gStringVar2, currentStat, STR_CONV_MODE_RIGHT_ALIGN, 3);
        AddTextPrinterParameterized4(WINDOW_2, 1, StatPrintData[statsToPrintActual[i]].x, StatPrintData[statsToPrintActual[i]].y, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);
    }

    for(i = 0; i < 6; i++)
    {
        // BPE: EVs do nothing in Nuzlocke mode, so they read zero there.
        currentStat = FlagGet(FLAG_NUZLOCKE) ? 0 : GetMonData(ReturnPartyMon(), statsToPrintEVs[i]);
        sStatEditorDataPtr->evTotal += currentStat;
        DebugPrintf("Stat: %d", currentStat);
        ConvertIntToDecimalStringN(gStringVar2, currentStat, STR_CONV_MODE_RIGHT_ALIGN, 3);
        AddTextPrinterParameterized4(WINDOW_2, 1, StatPrintData[statsToPrintEVs[i]].x, StatPrintData[statsToPrintEVs[i]].y, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);
    }

    for(i = 0; i < 6; i++)
    {
        currentStat = GetMonData(ReturnPartyMon(), statsToPrintIVs[i]);
        sStatEditorDataPtr->ivTotal += currentStat;
        DebugPrintf("Stat: %d", currentStat);
        ConvertIntToDecimalStringN(gStringVar2, currentStat, STR_CONV_MODE_RIGHT_ALIGN, 3);
        AddTextPrinterParameterized4(WINDOW_2, 1, StatPrintData[statsToPrintIVs[i]].x, StatPrintData[statsToPrintIVs[i]].y, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);
    }

    // Calc Totals
    ConvertIntToDecimalStringN(gStringVar2, sStatEditorDataPtr->normalTotal, STR_CONV_MODE_RIGHT_ALIGN, 4);
    AddTextPrinterParameterized4(WINDOW_2, 1, STARTING_X - 6, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 6), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);

    ConvertIntToDecimalStringN(gStringVar2, sStatEditorDataPtr->evTotal, STR_CONV_MODE_RIGHT_ALIGN, 3);
    AddTextPrinterParameterized4(WINDOW_2, 1, STARTING_X + SECOND_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 6), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);

    ConvertIntToDecimalStringN(gStringVar2, sStatEditorDataPtr->ivTotal, STR_CONV_MODE_RIGHT_ALIGN, 3);
    AddTextPrinterParameterized4(WINDOW_2, 1, STARTING_X + THIRD_COLUMN, STARTING_Y + (DISTANCE_BETWEEN_STATS_Y * 6), 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);


    // Print ability / nature / name / level / gender

#ifdef POKEMON_EXPANSION
    StringCopy(gStringVar2, GetSpeciesName(sStatEditorDataPtr->speciesID));
#else
    StringCopy(gStringVar2, gSpeciesNames[sStatEditorDataPtr->speciesID]);
#endif

    AddTextPrinterParameterized4(WINDOW_3, FONT_NARROW, 4, 2, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);

    ConvertIntToDecimalStringN(gStringVar1, level, STR_CONV_MODE_RIGHT_ALIGN, 3);
    StringExpandPlaceholders(gStringVar2, sText_MonLevel);
    AddTextPrinterParameterized4(WINDOW_3, FONT_SMALL_NARROW, 4, 18, 0, 0, sMenuWindowFontColors[FONT_WHITE], TEXT_SKIP_DRAW, gStringVar2);

    StringCopy(text, gText_MaleSymbol);
    if (gender != MON_GENDERLESS)
    {
        if (gender == MON_FEMALE)
            StringCopy(text, gText_FemaleSymbol);
        else
            StringCopy(text, gText_MaleSymbol);
        AddTextPrinterParameterized4(WINDOW_3, FONT_NORMAL, 41 + 8, 19, 0, 0, sGenderColors[(gender == MON_FEMALE)], TEXT_SKIP_DRAW, text);
    }

    // BPE: the nature the stats use, which a Mint (or this editor) may have changed.
    nature = GetMonData(ReturnPartyMon(), MON_DATA_HIDDEN_NATURE);
    StringCopy(gStringVar2, gNaturesInfo[nature].name);
    AddTextPrinterParameterized4(WINDOW_3, FONT_SMALL_NARROW, 4, 50, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);

    StringCopy(gStringVar2, gAbilitiesInfo[GetMonAbility(ReturnPartyMon())].name);
    AddTextPrinterParameterized4(WINDOW_3, FONT_SMALL_NARROW, 4, 34, 0, 0, sMenuWindowFontColors[FONT_WHITE], 0xFF, gStringVar2);

    PutWindowTilemap(WINDOW_3);
    CopyWindowToVram(WINDOW_3, 3);

    PutWindowTilemap(WINDOW_2);
    CopyWindowToVram(WINDOW_2, 3);
}

struct SpriteCordsStruct {
    u8 x;
    u8 y;
};

// BPE: where the selectors sit. The EV and IV cells are two columns of six; the
// Ability and Nature boxes are under the Pokemon's picture.
static const struct SpriteCordsStruct sStatSelectorCoords[STAT_ROWS][2] = {
    {{188, 30 + 20}, {220, 30 + 20}},
    {{188, 46 + 20}, {220, 46 + 20}},
    {{188, 62 + 20}, {220, 62 + 20}},
    {{188, 78 + 20}, {220, 78 + 20}},
    {{188, 94 + 20}, {220, 94 + 20}},
    {{188, 110 + 20}, {220, 110 + 20}}, // Thanks Jaizu
};

static const struct SpriteCordsStruct sInfoSelectorCoords[INFO_ROWS] = {
    [INFO_ROW_ABILITY] = {40, 130},
    [INFO_ROW_NATURE]  = {40, 146},
};

// Left to right on screen: the Ability/Nature panel, then EVs, then IVs.
static const u8 sColumnOrder[SELECTOR_COLUMNS] = {
    SELECTOR_COLUMN_INFO, SELECTOR_COLUMN_EV, SELECTOR_COLUMN_IV,
};

static void SelectorCallback(struct Sprite *sprite)
{
    bool32 isWide = sprite->data[1];
    bool32 onInfo = (sStatEditorDataPtr->selector_x == SELECTOR_COLUMN_INFO);

    // Only the selector for the current box shows, and none at all when the Pokemon can't be edited.
    if (!sStatEditorDataPtr->canEdit || isWide != onInfo)
    {
        sprite->invisible = TRUE;
        sprite->data[0] = 0;
        return;
    }

    if(sStatEditorDataPtr->inputMode == INPUT_EDIT_STAT)
    {
        if(sprite->data[0] == 32)
        {
            sprite->invisible = TRUE;
        }
        if(sprite->data[0] >= 48)
        {
            sprite->invisible = FALSE;
            sprite->data[0] = 0;
        }
        sprite->data[0]++;
    }
    else
    {
        sprite->invisible = FALSE;
        sprite->data[0] = 0;
    }

    if (isWide)
    {
        sprite->x = sInfoSelectorCoords[sStatEditorDataPtr->infoRow].x;
        sprite->y = sInfoSelectorCoords[sStatEditorDataPtr->infoRow].y;
    }
    else
    {
        sStatEditorDataPtr->selectedStat = sStatEditorDataPtr->selector_x + (sStatEditorDataPtr->selector_y * 2);
        sprite->x = sStatSelectorCoords[sStatEditorDataPtr->selector_y][sStatEditorDataPtr->selector_x].x;
        sprite->y = sStatSelectorCoords[sStatEditorDataPtr->selector_y][sStatEditorDataPtr->selector_x].y;
    }
}

static const u16 selectedStatToStatEnum[] = {
        MON_DATA_HP_EV, MON_DATA_HP_IV, MON_DATA_ATK_EV, MON_DATA_ATK_IV, MON_DATA_DEF_EV, MON_DATA_DEF_IV,
        MON_DATA_SPATK_EV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_EV, MON_DATA_SPDEF_IV, MON_DATA_SPEED_EV, MON_DATA_SPEED_IV,
};

// BPE: Standard games may change a Pokemon's EVs, IVs, nature and ability here.
// Nuzlocke games only look, and so does anyone looking at an Egg.
bool32 StatEditor_CanEditMon(struct Pokemon *mon)
{
    return !FlagGet(FLAG_NUZLOCKE) && !GetMonData(mon, MON_DATA_IS_EGG);
}

// The highest value this EV or IV may take, given the Pokemon's other EVs.
u32 StatEditor_GetStatMax(struct Pokemon *mon, u32 field)
{
    u32 i, evCap, otherEVs = 0;

    if (field < MON_DATA_HP_EV || field >= MON_DATA_HP_EV + NUM_STATS)
        return MAX_PER_STAT_IVS;

    for (i = 0; i < NUM_STATS; i++)
    {
        if (MON_DATA_HP_EV + i != field)
            otherEVs += GetMonData(mon, MON_DATA_HP_EV + i);
    }

    evCap = GetCurrentEVCap();
    if (otherEVs >= evCap)
        return 0;
    return min((u32)MAX_PER_STAT_EVS, evCap - otherEVs);
}

// The next ability slot in the given direction that gives a different ability. Empty
// slots and slots repeating an earlier one are skipped. Returns the current slot if
// the species has only one ability.
u32 StatEditor_GetNextAbilityNum(struct Pokemon *mon, s32 direction)
{
    enum Species species = GetMonData(mon, MON_DATA_SPECIES);
    u32 current = GetMonData(mon, MON_DATA_ABILITY_NUM);
    enum Ability currentAbility = GetMonAbility(mon);
    u32 i, j, slot = current;

    for (i = 0; i < NUM_ABILITY_SLOTS; i++)
    {
        enum Ability ability;
        bool32 repeated = FALSE;

        slot = (slot + NUM_ABILITY_SLOTS + direction) % NUM_ABILITY_SLOTS;
        ability = GetSpeciesAbility(species, slot);
        if (ability == ABILITY_NONE || ability == currentAbility)
            continue;
        for (j = 0; j < slot; j++)
        {
            if (GetSpeciesAbility(species, j) == ability)
                repeated = TRUE;
        }
        if (!repeated)
            return slot;
    }
    return current;
}

static void Task_DelayedSpriteLoad(u8 taskId) // wait 4 frames after changing the mon you're editing so there are no palette problems
{
    if (gTasks[taskId].data[11] >= 4)
    {
        SampleUi_DrawMonIcon(sStatEditorDataPtr->speciesID);
        PrintMonStats();
        gTasks[taskId].func = Task_StatEditorMain;
        return;
    }
    else
    {
        gTasks[taskId].data[11]++;
    }
}

static void UNUSED ReloadNewPokemon(u8 taskId)
{
    gSprites[sStatEditorDataPtr->monIconSpriteId].invisible = TRUE;
    FreeAndDestroyMonPicSprite(sStatEditorDataPtr->monIconSpriteId);
    sStatEditorDataPtr->speciesID = GetMonData(ReturnPartyMon(), MON_DATA_SPECIES);
    gTasks[taskId].func = Task_DelayedSpriteLoad;
    gTasks[taskId].data[11] = 0;
}

static u32 GetSelectedStatField(void)
{
    return selectedStatToStatEnum[sStatEditorDataPtr->selector_x + (sStatEditorDataPtr->selector_y * 2)];
}

static struct Sprite *GetActiveSelector(void)
{
    if (sStatEditorDataPtr->selector_x == SELECTOR_COLUMN_INFO)
        return &gSprites[sStatEditorDataPtr->wideSelectorSpriteId];
    return &gSprites[sStatEditorDataPtr->selectorSpriteId];
}

// White while choosing; while editing, red at the maximum, blue at the minimum and gold otherwise.
static void UpdateSelectorAnim(void)
{
    u32 anim = SELECTOR_ANIM_CHOOSING;

    if (sStatEditorDataPtr->inputMode == INPUT_EDIT_STAT)
    {
        anim = SELECTOR_ANIM_EDITING;
        if (sStatEditorDataPtr->selector_x != SELECTOR_COLUMN_INFO)
        {
            u32 field = GetSelectedStatField();
            u32 value = GetMonData(ReturnPartyMon(), field);

            if (value >= StatEditor_GetStatMax(ReturnPartyMon(), field))
                anim = SELECTOR_ANIM_AT_MAX;
            else if (value == 0)
                anim = SELECTOR_ANIM_AT_MIN;
        }
    }

    if (GetActiveSelector()->animNum != anim)
        StartSpriteAnim(GetActiveSelector(), anim);
}

static void Task_StatEditorMain(u8 taskId) // input control when first loaded into menu
{
    u32 i;

    if (JOY_NEW(B_BUTTON))
    {
        PlaySE(SE_PC_OFF);
        BeginNormalPaletteFade(0xFFFFFFFF, 0, 0, 16, RGB_BLACK);
        gTasks[taskId].func = Task_StatEditorTurnOff;
        return;
    }

    if (!sStatEditorDataPtr->canEdit)
        return;

    if (JOY_NEW(A_BUTTON))
    {
        PlaySE(SE_SELECT);
        sStatEditorDataPtr->inputMode = INPUT_EDIT_STAT;
        PrintTitleToWindowEditState();
        UpdateSelectorAnim();
        gTasks[taskId].func = Task_MenuEditingStat;
        return;
    }

    if (JOY_NEW(DPAD_LEFT) || JOY_NEW(DPAD_RIGHT))
    {
        for (i = 0; i < SELECTOR_COLUMNS; i++)
        {
            if (sColumnOrder[i] == sStatEditorDataPtr->selector_x)
                break;
        }
        if (JOY_NEW(DPAD_LEFT))
            i = (i + SELECTOR_COLUMNS - 1) % SELECTOR_COLUMNS;
        else
            i = (i + 1) % SELECTOR_COLUMNS;
        sStatEditorDataPtr->selector_x = sColumnOrder[i];
    }
    else if (sStatEditorDataPtr->selector_x == SELECTOR_COLUMN_INFO)
    {
        if (JOY_NEW(DPAD_UP) || JOY_NEW(DPAD_DOWN))
            sStatEditorDataPtr->infoRow = (sStatEditorDataPtr->infoRow + 1) % INFO_ROWS;
    }
    else if (JOY_NEW(DPAD_UP))
    {
        if (sStatEditorDataPtr->selector_y == 0)
            sStatEditorDataPtr->selector_y = STAT_ROWS - 1;
        else
            sStatEditorDataPtr->selector_y--;
    }
    else if (JOY_NEW(DPAD_DOWN))
    {
        if (sStatEditorDataPtr->selector_y == STAT_ROWS - 1)
            sStatEditorDataPtr->selector_y = 0;
        else
            sStatEditorDataPtr->selector_y++;
    }
}

// Recalculates the stats after an edit, keeping the damage the Pokemon has taken
// the same, and redraws them.
static void RecalculateStats(void)
{
    struct Pokemon *mon = ReturnPartyMon();
    u32 currentHP = GetMonData(mon, MON_DATA_HP);
    u32 amountHPLost = GetMonData(mon, MON_DATA_MAX_HP) - currentHP;
    u32 newHP;

    CalculateMonStats(mon);

    if (currentHP != 0)
    {
        newHP = GetMonData(mon, MON_DATA_MAX_HP);
        newHP = (newHP > amountHPLost) ? newHP - amountHPLost : 1;
        SetMonData(mon, MON_DATA_HP, &newHP);
    }

    PrintMonStats();
}

#define STAT_STEP_SMALL 1
#define STAT_STEP_LARGE 10
#define STAT_STEP_ALL   0xFFFF

static void ChangeSelectedStat(s32 delta)
{
    struct Pokemon *mon = ReturnPartyMon();
    u32 field = GetSelectedStatField();
    u32 value = GetMonData(mon, field);
    u32 max = StatEditor_GetStatMax(mon, field);
    u32 newValue;

    if (delta < 0)
        newValue = (value > (u32)-delta) ? value + delta : 0;
    else if (value >= max) // An older save may hold more than the limit; it can only go down.
        newValue = value;
    else
        newValue = min(value + delta, max);

    if (newValue != value)
    {
        SetMonData(mon, field, &newValue);
        RecalculateStats();
    }
    UpdateSelectorAnim();
}

static void ChangeNature(s32 direction)
{
    u32 nature = GetMonData(ReturnPartyMon(), MON_DATA_HIDDEN_NATURE);

    // Changes the nature the stats use, as a Mint does; the Pokemon's personality is untouched.
    nature = (nature + NUM_NATURES + direction) % NUM_NATURES;
    SetMonData(ReturnPartyMon(), MON_DATA_HIDDEN_NATURE, &nature);
    RecalculateStats();
}

static void ChangeAbility(s32 direction)
{
    u32 abilityNum = StatEditor_GetNextAbilityNum(ReturnPartyMon(), direction);

    if (abilityNum == GetMonData(ReturnPartyMon(), MON_DATA_ABILITY_NUM))
        return;
    SetMonData(ReturnPartyMon(), MON_DATA_ABILITY_NUM, &abilityNum);
    PrintMonStats();
}

// EVs and IVs: Left/Right change by 1, Up/Down by 10, R and L jump to the maximum and zero.
// Ability and nature: any direction steps through the choices.
static void Task_MenuEditingStat(u8 taskId)
{
    if (JOY_NEW(A_BUTTON) || JOY_NEW(B_BUTTON))
    {
        gTasks[taskId].func = Task_StatEditorMain;
        PlaySE(SE_SELECT);
        sStatEditorDataPtr->inputMode = INPUT_SELECT_STAT;
        UpdateSelectorAnim();
        PrintTitleToWindowMainState();
        return;
    }

    if (sStatEditorDataPtr->selector_x == SELECTOR_COLUMN_INFO)
    {
        s32 direction = 0;

        if (JOY_REPEAT(DPAD_RIGHT) || JOY_REPEAT(DPAD_UP))
            direction = 1;
        else if (JOY_REPEAT(DPAD_LEFT) || JOY_REPEAT(DPAD_DOWN))
            direction = -1;

        if (direction != 0)
        {
            if (sStatEditorDataPtr->infoRow == INFO_ROW_ABILITY)
                ChangeAbility(direction);
            else
                ChangeNature(direction);
        }
        return;
    }

    if (JOY_REPEAT(DPAD_RIGHT))
        ChangeSelectedStat(STAT_STEP_SMALL);
    else if (JOY_REPEAT(DPAD_LEFT))
        ChangeSelectedStat(-STAT_STEP_SMALL);
    else if (JOY_REPEAT(DPAD_UP))
        ChangeSelectedStat(STAT_STEP_LARGE);
    else if (JOY_REPEAT(DPAD_DOWN))
        ChangeSelectedStat(-STAT_STEP_LARGE);
    else if (JOY_NEW(R_BUTTON))
        ChangeSelectedStat(STAT_STEP_ALL);
    else if (JOY_NEW(L_BUTTON))
        ChangeSelectedStat(-STAT_STEP_ALL);
}
