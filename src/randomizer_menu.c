// BPE: the randomizer settings screen, opened from Birch's speech.
// Six pages of options, a seed code entry and a final summary. The layout follows
// the Options menu (src/option_menu.c).
#include "global.h"
#include "randomizer_menu.h"
#include "battle_main.h"
#include "bg.h"
#include "gpu_regs.h"
#include "international_string_util.h"
#include "main.h"
#include "malloc.h"
#include "menu.h"
#include "palette.h"
#include "randomizer.h"
#include "scanline_effect.h"
#include "sound.h"
#include "sprite.h"
#include "string_util.h"
#include "strings.h"
#include "task.h"
#include "text.h"
#include "text_window.h"
#include "window.h"
#include "constants/rgb.h"
#include "constants/songs.h"

enum
{
    WIN_HEADER,
    WIN_OPTIONS,
    WIN_DESCRIPTION,
};

enum MenuMode
{
    MODE_BROWSE,
    MODE_GENERATIONS,
    MODE_CODE,
    MODE_SUMMARY,
};

enum MenuRow
{
    ROW_PRESET,
    ROW_SEED,
    ROW_STARTERS,
    ROW_WILD,
    ROW_CONSISTENCY,
    ROW_GIFTS,
    ROW_STATICS,
    ROW_LEGENDARIES,
    ROW_STRENGTH,
    ROW_GENERATIONS,
    ROW_REGULAR_TRAINERS,
    ROW_BOSS_TRAINERS,
    ROW_FIELD_ITEMS,
    ROW_ABILITIES,
    ROW_TROLL_ABILITIES,
    ROW_LEVEL_UP_MOVES,
    ROW_TM_COMPATIBILITY,
    ROW_TM_CONTENTS,
    ROW_TYPES,
    ROW_EVOLUTIONS,
    ROW_BASE_STATS,
    ROW_TYPE_CHART,
    ROW_MONOTYPE,
    ROW_COUNT
};

#define ROWS_PER_PAGE 5
#define PAGE_COUNT 6
#define ROW_HEIGHT 16
#define VALUE_X 108
#define OPTION_NONE 0xFF

struct MenuRowInfo
{
    const u8 *name;
    const u8 *description;
    u8 option;                  // RANDOMIZER_OPTION_*, or OPTION_NONE for the preset and seed rows
    const u8 *const *valueNames;
};

struct MenuPage
{
    const u8 *title;
    u8 rows[ROWS_PER_PAGE];
    u8 count;
};

struct RandomizerMenu
{
    struct RandomizerSettings settings;
    u8 page;
    u8 row;
    u8 mode;
    u8 generationCursor;
    u8 codeCursor;
    bool8 seedFromCode;
    u8 code[RANDOMIZER_CODE_LENGTH]; // alphabet indexes while a code is typed
};

static EWRAM_DATA struct RandomizerMenu *sMenu = NULL;
static EWRAM_DATA bool8 sConfirmed = FALSE;

static const u8 *const sOffOn[] = {COMPOUND_STRING("Off"), COMPOUND_STRING("On")};
static const u8 *const sOffRandom[] = {COMPOUND_STRING("Off"), COMPOUND_STRING("Random")};
static const u8 *const sOffShuffled[] = {COMPOUND_STRING("Off"), COMPOUND_STRING("Shuffled")};
static const u8 *const sNoYes[] = {COMPOUND_STRING("No"), COMPOUND_STRING("Yes")};
static const u8 *const sStarterValues[] = {COMPOUND_STRING("Off"), COMPOUND_STRING("Same roles"), COMPOUND_STRING("Random")};
static const u8 *const sConsistencyValues[] = {COMPOUND_STRING("Whole game"), COMPOUND_STRING("Per route")};
static const u8 *const sLegendaryValues[] = {COMPOUND_STRING("Unchanged"), COMPOUND_STRING("Among themselves"), COMPOUND_STRING("Mixed with all")};
static const u8 *const sStrengthValues[] = {COMPOUND_STRING("Similar"), COMPOUND_STRING("Fully random")};
static const u8 *const sBossValues[] = {COMPOUND_STRING("Unchanged"), COMPOUND_STRING("Keep their type"), COMPOUND_STRING("Fully random")};
static const u8 *const sPresetNames[] = {COMPOUND_STRING("Randomlocke"), COMPOUND_STRING("Full"), COMPOUND_STRING("Chaos"), COMPOUND_STRING("Custom")};

static const struct MenuRowInfo sRows[ROW_COUNT] =
{
    [ROW_PRESET] = {COMPOUND_STRING("Preset"),
        COMPOUND_STRING("Randomlocke suits a randomized\nNuzlocke. Full and Chaos go further."), OPTION_NONE, NULL},
    [ROW_SEED] = {COMPOUND_STRING("Seed"),
        COMPOUND_STRING("{DPAD_LEFTRIGHT}: new random seed.\n{A_BUTTON}: enter a friend's seed code."), OPTION_NONE, NULL},
    [ROW_STARTERS] = {COMPOUND_STRING("Starters"),
        COMPOUND_STRING("Same roles keeps each ball's type.\nRandom offers nine different types."), RANDOMIZER_OPTION_STARTERS, sStarterValues},
    [ROW_WILD] = {COMPOUND_STRING("Wild POKéMON"),
        COMPOUND_STRING("The POKéMON in grass, caves, water\nand fishing spots."), RANDOMIZER_OPTION_WILD, sOffOn},
    [ROW_CONSISTENCY] = {COMPOUND_STRING("Wild consistency"),
        COMPOUND_STRING("Whole game swaps each POKéMON for\none other. Per route varies by area."), RANDOMIZER_OPTION_WILD_CONSISTENCY, sConsistencyValues},
    [ROW_GIFTS] = {COMPOUND_STRING("Gifts and trades"),
        COMPOUND_STRING("Gift POKéMON, eggs and the POKéMON\ntraders offer and ask for."), RANDOMIZER_OPTION_GIFTS, sOffOn},
    [ROW_STATICS] = {COMPOUND_STRING("Static POKéMON"),
        COMPOUND_STRING("POKéMON you walk up to and battle,\nlike SNORLAX and SUDOWOODO."), RANDOMIZER_OPTION_STATICS, sOffOn},
    [ROW_LEGENDARIES] = {COMPOUND_STRING("Legendaries"),
        COMPOUND_STRING("What legendary encounters become,\nand whether they appear elsewhere."), RANDOMIZER_OPTION_LEGENDARIES, sLegendaryValues},
    [ROW_STRENGTH] = {COMPOUND_STRING("Strength"),
        COMPOUND_STRING("Similar keeps replacements about as\nstrong as the POKéMON they replace."), RANDOMIZER_OPTION_STRENGTH, sStrengthValues},
    [ROW_GENERATIONS] = {COMPOUND_STRING("Generations"),
        COMPOUND_STRING("{A_BUTTON}: choose which generations of\nPOKéMON can appear."), RANDOMIZER_OPTION_GENERATIONS, NULL},
    [ROW_REGULAR_TRAINERS] = {COMPOUND_STRING("Regular trainers"),
        COMPOUND_STRING("The teams of every trainer who\nisn't a boss."), RANDOMIZER_OPTION_REGULAR_TRAINERS, sOffOn},
    [ROW_BOSS_TRAINERS] = {COMPOUND_STRING("Boss trainers"),
        COMPOUND_STRING("GYM LEADERS, the ELITE FOUR, rivals\nand the team bosses."), RANDOMIZER_OPTION_BOSS_TRAINERS, sBossValues},
    [ROW_FIELD_ITEMS] = {COMPOUND_STRING("Field items"),
        COMPOUND_STRING("Item balls and hidden items trade\nplaces. Key items and HMs stay."), RANDOMIZER_OPTION_FIELD_ITEMS, sOffShuffled},
    [ROW_ABILITIES] = {COMPOUND_STRING("Abilities"),
        COMPOUND_STRING("Each evolution family gets new\nabilities. Broken ones are banned."), RANDOMIZER_OPTION_ABILITIES, sOffRandom},
    [ROW_TROLL_ABILITIES] = {COMPOUND_STRING("Troll abilities"),
        COMPOUND_STRING("Allows abilities like TRUANT and\nSLOW START with random abilities."), RANDOMIZER_OPTION_TROLL_ABILITIES, sNoYes},
    [ROW_LEVEL_UP_MOVES] = {COMPOUND_STRING("Level-up moves"),
        COMPOUND_STRING("New level-up moves that favor the\nPOKéMON's own types."), RANDOMIZER_OPTION_LEVEL_UP_MOVES, sOffRandom},
    [ROW_TM_COMPATIBILITY] = {COMPOUND_STRING("TM compatibility"),
        COMPOUND_STRING("Which POKéMON can learn each TM and\ntutor move. HMs never change."), RANDOMIZER_OPTION_TM_COMPATIBILITY, sOffRandom},
    [ROW_TM_CONTENTS] = {COMPOUND_STRING("TM contents"),
        COMPOUND_STRING("Shuffles the move each TM teaches.\nHMs never change."), RANDOMIZER_OPTION_TM_CONTENTS, sOffShuffled},
    [ROW_TYPES] = {COMPOUND_STRING("POKéMON types"),
        COMPOUND_STRING("Each evolution family gets new\ntypes."), RANDOMIZER_OPTION_TYPES, sOffRandom},
    [ROW_EVOLUTIONS] = {COMPOUND_STRING("Evolutions"),
        COMPOUND_STRING("POKéMON evolve into random POKéMON\nof similar strength."), RANDOMIZER_OPTION_EVOLUTIONS, sOffRandom},
    [ROW_BASE_STATS] = {COMPOUND_STRING("Base stats"),
        COMPOUND_STRING("Shuffles each family's base stats.\nTheir total stays the same."), RANDOMIZER_OPTION_BASE_STATS, sOffShuffled},
    [ROW_TYPE_CHART] = {COMPOUND_STRING("Type chart"),
        COMPOUND_STRING("Shuffles type matchups. The move\nmenu shows what is effective."), RANDOMIZER_OPTION_TYPE_CHART, sOffShuffled},
    [ROW_MONOTYPE] = {COMPOUND_STRING("Monotype"),
        COMPOUND_STRING("Every wild, gift and starter POKéMON\nhas this one type."), RANDOMIZER_OPTION_MONOTYPE, NULL},
};

static const struct MenuPage sPages[PAGE_COUNT] =
{
    {COMPOUND_STRING("SETUP"), {ROW_PRESET, ROW_SEED}, 2},
    {COMPOUND_STRING("POKéMON"), {ROW_STARTERS, ROW_WILD, ROW_CONSISTENCY, ROW_GIFTS, ROW_STATICS}, 5},
    {COMPOUND_STRING("POKéMON POOL"), {ROW_LEGENDARIES, ROW_STRENGTH, ROW_GENERATIONS}, 3},
    {COMPOUND_STRING("TRAINERS AND ITEMS"), {ROW_REGULAR_TRAINERS, ROW_BOSS_TRAINERS, ROW_FIELD_ITEMS}, 3},
    {COMPOUND_STRING("BATTLE"), {ROW_ABILITIES, ROW_TROLL_ABILITIES, ROW_LEVEL_UP_MOVES, ROW_TM_COMPATIBILITY, ROW_TM_CONTENTS}, 5},
    {COMPOUND_STRING("CHAOS"), {ROW_TYPES, ROW_EVOLUTIONS, ROW_BASE_STATS, ROW_TYPE_CHART, ROW_MONOTYPE}, 5},
};

static const u8 sColor_Normal[] = {TEXT_COLOR_WHITE, TEXT_COLOR_DARK_GRAY, TEXT_COLOR_LIGHT_GRAY};
static const u8 sColor_Value[] = {TEXT_COLOR_WHITE, TEXT_COLOR_RED, TEXT_COLOR_LIGHT_RED};
static const u8 sColor_Disabled[] = {TEXT_COLOR_WHITE, TEXT_COLOR_LIGHT_GRAY, TEXT_COLOR_WHITE};
static const u8 sColor_Cursor[] = {TEXT_COLOR_WHITE, TEXT_COLOR_BLUE, TEXT_COLOR_LIGHT_BLUE};

static const u16 sMenuText_Pal[] = INCGFX_U16("graphics/interface/option_menu_text.pal", ".gbapal");
static const u16 sMenuBg_Pal[] = {RGB(17, 18, 31)};

static const struct WindowTemplate sWindowTemplates[] =
{
    [WIN_HEADER] = {
        .bg = 1,
        .tilemapLeft = 2,
        .tilemapTop = 1,
        .width = 26,
        .height = 2,
        .paletteNum = 1,
        .baseBlock = 2
    },
    [WIN_OPTIONS] = {
        .bg = 0,
        .tilemapLeft = 2,
        .tilemapTop = 5,
        .width = 26,
        .height = 10,
        .paletteNum = 1,
        .baseBlock = 0x36
    },
    [WIN_DESCRIPTION] = {
        .bg = 1,
        .tilemapLeft = 2,
        .tilemapTop = 16,
        .width = 26,
        .height = 4,
        .paletteNum = 1,
        .baseBlock = 0x36 + 26 * 10
    },
    DUMMY_WIN_TEMPLATE
};

static const struct BgTemplate sBgTemplates[] =
{
    {
        .bg = 1,
        .charBaseIndex = 1,
        .mapBaseIndex = 30,
        .screenSize = 0,
        .paletteMode = 0,
        .priority = 0,
        .baseTile = 0
    },
    {
        .bg = 0,
        .charBaseIndex = 1,
        .mapBaseIndex = 31,
        .screenSize = 0,
        .paletteMode = 0,
        .priority = 1,
        .baseTile = 0
    }
};

static void Task_RandomizerMenuFadeIn(u8 taskId);
static void Task_RandomizerMenuInput(u8 taskId);
static void Task_RandomizerMenuFadeOut(u8 taskId);
static void DrawPage(void);
static void DrawDescription(const u8 *text);

bool32 RandomizerMenu_WasConfirmed(void)
{
    return sConfirmed;
}

static void MainCB2(void)
{
    RunTasks();
    AnimateSprites();
    BuildOamBuffer();
    UpdatePaletteFade();
}

static void VBlankCB(void)
{
    LoadOam();
    ProcessSpriteCopyRequests();
    TransferPlttBuffer();
}

#define TILE_TOP_CORNER_L 0x1A2
#define TILE_TOP_EDGE     0x1A3
#define TILE_TOP_CORNER_R 0x1A4
#define TILE_LEFT_EDGE    0x1A5
#define TILE_RIGHT_EDGE   0x1A7
#define TILE_BOT_CORNER_L 0x1A8
#define TILE_BOT_EDGE     0x1A9
#define TILE_BOT_CORNER_R 0x1AA

static void DrawFrame(u32 top, u32 height)
{
    u32 bottom = top + height + 1;

    FillBgTilemapBufferRect(1, TILE_TOP_CORNER_L,  1, top,    1, 1, 7);
    FillBgTilemapBufferRect(1, TILE_TOP_EDGE,      2, top,   26, 1, 7);
    FillBgTilemapBufferRect(1, TILE_TOP_CORNER_R, 28, top,    1, 1, 7);
    FillBgTilemapBufferRect(1, TILE_LEFT_EDGE,     1, top + 1, 1, height, 7);
    FillBgTilemapBufferRect(1, TILE_RIGHT_EDGE,   28, top + 1, 1, height, 7);
    FillBgTilemapBufferRect(1, TILE_BOT_CORNER_L,  1, bottom, 1, 1, 7);
    FillBgTilemapBufferRect(1, TILE_BOT_EDGE,      2, bottom, 26, 1, 7);
    FillBgTilemapBufferRect(1, TILE_BOT_CORNER_R, 28, bottom, 1, 1, 7);
}

void CB2_InitRandomizerMenu(void)
{
    switch (gMain.state)
    {
    default:
    case 0:
        SetVBlankCallback(NULL);
        sConfirmed = FALSE;
        sMenu = AllocZeroed(sizeof(*sMenu));
        if (sMenu == NULL)
        {
            SetMainCallback2(gMain.savedCallback);
            return;
        }
        Randomizer_ApplyPreset(&sMenu->settings, RANDOMIZER_PRESET_RANDOMLOCKE);
        sMenu->settings.seed = Randomizer_NewSeed();
        gMain.state++;
        break;
    case 1:
        DmaClearLarge16(3, (void *)(VRAM), VRAM_SIZE, 0x1000);
        DmaClear32(3, OAM, OAM_SIZE);
        DmaClear16(3, PLTT, PLTT_SIZE);
        SetGpuReg(REG_OFFSET_DISPCNT, 0);
        ResetBgsAndClearDma3BusyFlags(0);
        InitBgsFromTemplates(0, sBgTemplates, ARRAY_COUNT(sBgTemplates));
        for (u32 bg = 0; bg < 4; bg++)
        {
            ChangeBgX(bg, 0, BG_COORD_SET);
            ChangeBgY(bg, 0, BG_COORD_SET);
        }
        InitWindows(sWindowTemplates);
        DeactivateAllTextPrinters();
        SetGpuReg(REG_OFFSET_WIN0H, 0);
        SetGpuReg(REG_OFFSET_WIN0V, 0);
        SetGpuReg(REG_OFFSET_WININ, WININ_WIN0_BG0);
        SetGpuReg(REG_OFFSET_WINOUT, WINOUT_WIN01_BG0 | WINOUT_WIN01_BG1 | WINOUT_WIN01_CLR);
        SetGpuReg(REG_OFFSET_BLDCNT, BLDCNT_TGT1_BG0 | BLDCNT_EFFECT_DARKEN);
        SetGpuReg(REG_OFFSET_BLDALPHA, 0);
        SetGpuReg(REG_OFFSET_BLDY, 4);
        SetGpuReg(REG_OFFSET_DISPCNT, DISPCNT_WIN0_ON | DISPCNT_OBJ_ON | DISPCNT_OBJ_1D_MAP);
        ShowBg(0);
        ShowBg(1);
        gMain.state++;
        break;
    case 2:
        ResetPaletteFade();
        ScanlineEffect_Stop();
        ResetTasks();
        ResetSpriteData();
        gMain.state++;
        break;
    case 3:
        LoadBgTiles(1, GetWindowFrameTilesPal(gSaveBlock2Ptr->optionsWindowFrameType)->tiles, 0x120, 0x1A2);
        LoadPalette(sMenuBg_Pal, BG_PLTT_ID(0), sizeof(sMenuBg_Pal));
        LoadPalette(GetWindowFrameTilesPal(gSaveBlock2Ptr->optionsWindowFrameType)->pal, BG_PLTT_ID(7), PLTT_SIZE_4BPP);
        LoadPalette(sMenuText_Pal, BG_PLTT_ID(1), sizeof(sMenuText_Pal));
        gMain.state++;
        break;
    case 4:
        PutWindowTilemap(WIN_HEADER);
        PutWindowTilemap(WIN_OPTIONS);
        PutWindowTilemap(WIN_DESCRIPTION);
        DrawFrame(0, 2);
        DrawFrame(4, 10);
        DrawFrame(15, 4);
        CopyBgTilemapBufferToVram(1);
        DrawPage();
        gMain.state++;
        break;
    case 5:
        CreateTask(Task_RandomizerMenuFadeIn, 0);
        BeginNormalPaletteFade(PALETTES_ALL, 0, 16, 0, RGB_BLACK);
        SetVBlankCallback(VBlankCB);
        SetMainCallback2(MainCB2);
        return;
    }
}

// ── Drawing ──────────────────────────────────────────────────────────────────

static const struct MenuPage *CurrentPage(void)
{
    return &sPages[sMenu->page];
}

static u32 CurrentRow(void)
{
    return CurrentPage()->rows[sMenu->row];
}

static bool32 IsRowDisabled(u32 row)
{
    return row == ROW_TROLL_ABILITIES && !sMenu->settings.options[RANDOMIZER_OPTION_ABILITIES];
}

// Everything in the options window outside WIN0 is dimmed, so the code entry and
// the summary light up the whole window.
#define HIGHLIGHT_ALL 0xFF

static void HighlightRow(u32 index)
{
    if (index == HIGHLIGHT_ALL)
    {
        SetGpuReg(REG_OFFSET_WIN0H, WIN_RANGE(16, DISPLAY_WIDTH - 16));
        SetGpuReg(REG_OFFSET_WIN0V, WIN_RANGE(40, 40 + ROWS_PER_PAGE * ROW_HEIGHT));
        return;
    }
    SetGpuReg(REG_OFFSET_WIN0H, WIN_RANGE(16, DISPLAY_WIDTH - 16));
    SetGpuReg(REG_OFFSET_WIN0V, WIN_RANGE(index * ROW_HEIGHT + 40, index * ROW_HEIGHT + 40 + ROW_HEIGHT));
}

static void DrawHeader(const u8 *title)
{
    u8 text[64];
    u8 *end;

    FillWindowPixelBuffer(WIN_HEADER, PIXEL_FILL(1));
    end = StringCopy(text, COMPOUND_STRING("RANDOMIZER  "));
    StringCopy(end, title);
    AddTextPrinterParameterized3(WIN_HEADER, FONT_NORMAL, 8, 1, sColor_Normal, TEXT_SKIP_DRAW, text);
    if (sMenu->mode == MODE_BROWSE || sMenu->mode == MODE_GENERATIONS)
    {
        end = ConvertIntToDecimalStringN(text, sMenu->page + 1, STR_CONV_MODE_LEFT_ALIGN, 1);
        end = StringCopy(end, COMPOUND_STRING("/"));
        ConvertIntToDecimalStringN(end, PAGE_COUNT, STR_CONV_MODE_LEFT_ALIGN, 1);
        AddTextPrinterParameterized3(WIN_HEADER, FONT_NORMAL, GetStringRightAlignXOffset(FONT_NORMAL, text, 200), 1, sColor_Normal, TEXT_SKIP_DRAW, text);
    }
    CopyWindowToVram(WIN_HEADER, COPYWIN_FULL);
}

static void DrawDescription(const u8 *text)
{
    FillWindowPixelBuffer(WIN_DESCRIPTION, PIXEL_FILL(1));
    AddTextPrinterParameterized3(WIN_DESCRIPTION, FONT_NARROW, 4, 1, sColor_Normal, TEXT_SKIP_DRAW, text);
    CopyWindowToVram(WIN_DESCRIPTION, COPYWIN_FULL);
}

static void DrawGenerations(u32 y)
{
    u8 digit[2];
    u32 excluded = sMenu->settings.options[RANDOMIZER_OPTION_GENERATIONS];

    for (u32 i = 0; i < RANDOMIZER_GENERATION_COUNT; i++)
    {
        const u8 *color = (excluded & (1u << i)) ? sColor_Disabled : sColor_Value;
        if (sMenu->mode == MODE_GENERATIONS && sMenu->generationCursor == i)
            color = sColor_Cursor;
        digit[0] = CHAR_1 + i;
        digit[1] = EOS;
        AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, VALUE_X + i * 10, y, color, TEXT_SKIP_DRAW, digit);
    }
}

static const u8 *GetValueName(u32 row)
{
    const struct MenuRowInfo *info = &sRows[row];

    switch (row)
    {
    case ROW_PRESET:
        return sPresetNames[Randomizer_GetPreset(&sMenu->settings)];
    case ROW_SEED:
        return sMenu->seedFromCode ? COMPOUND_STRING("From a code") : COMPOUND_STRING("Random");
    case ROW_MONOTYPE:
    {
        u32 type = sMenu->settings.options[RANDOMIZER_OPTION_MONOTYPE];
        return type == TYPE_NONE ? COMPOUND_STRING("Off") : gTypesInfo[type].name;
    }
    default:
        return info->valueNames[sMenu->settings.options[info->option]];
    }
}

static void DrawRow(u32 index)
{
    u32 row = CurrentPage()->rows[index];
    u32 y = index * ROW_HEIGHT + 1;
    bool32 disabled = IsRowDisabled(row);

    FillWindowPixelRect(WIN_OPTIONS, PIXEL_FILL(1), 0, index * ROW_HEIGHT, 26 * 8, ROW_HEIGHT);
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, 8, y, disabled ? sColor_Disabled : sColor_Normal, TEXT_SKIP_DRAW, sRows[row].name);
    if (row == ROW_GENERATIONS)
        DrawGenerations(y);
    else
        AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NARROW, VALUE_X, y, disabled ? sColor_Disabled : sColor_Value, TEXT_SKIP_DRAW, GetValueName(row));
}

static void DrawPage(void)
{
    const struct MenuPage *page = CurrentPage();

    DrawHeader(page->title);
    FillWindowPixelBuffer(WIN_OPTIONS, PIXEL_FILL(1));
    for (u32 i = 0; i < page->count; i++)
        DrawRow(i);
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_FULL);
    HighlightRow(sMenu->row);
    if (sMenu->mode == MODE_GENERATIONS)
        DrawDescription(COMPOUND_STRING("{DPAD_LEFTRIGHT}: choose a generation.\n{A_BUTTON}: switch it on or off. {B_BUTTON}: done."));
    else
        DrawDescription(sRows[CurrentRow()].description);
}

static void RedrawRow(u32 index)
{
    DrawRow(index);
    // The preset name follows every change.
    if (sMenu->page == 0 && index != 0)
        DrawRow(0);
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_GFX);
}

static void DrawCode(void)
{
    u8 text[2];
    u32 x = 20;

    FillWindowPixelBuffer(WIN_OPTIONS, PIXEL_FILL(1));
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, 8, 1, sColor_Normal, TEXT_SKIP_DRAW, COMPOUND_STRING("Enter the seed code:"));
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        if (i != 0 && i % 4 == 0)
        {
            text[0] = CHAR_HYPHEN;
            text[1] = EOS;
            AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, x, 25, sColor_Normal, TEXT_SKIP_DRAW, text);
            x += 8;
        }
        text[0] = Randomizer_GetCodeChar(sMenu->code[i]);
        text[1] = EOS;
        AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, x, 25, i == sMenu->codeCursor ? sColor_Cursor : sColor_Value, TEXT_SKIP_DRAW, text);
        x += 9;
    }
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NARROW, 8, 49, sColor_Normal, TEXT_SKIP_DRAW,
                                 COMPOUND_STRING("Type the code a friend shared to play\nexactly the same game."));
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_FULL);
}

static void DrawSummary(void)
{
    u8 code[RANDOMIZER_CODE_LENGTH + 1];
    u8 grouped[RANDOMIZER_CODE_LENGTH + 4];
    u32 out = 0;

    Randomizer_EncodeSeedCode(&sMenu->settings, code);
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        if (i != 0 && i % 4 == 0)
            grouped[out++] = CHAR_HYPHEN;
        grouped[out++] = code[i];
    }
    grouped[out] = EOS;

    DrawHeader(COMPOUND_STRING("READY?"));
    HighlightRow(HIGHLIGHT_ALL);
    FillWindowPixelBuffer(WIN_OPTIONS, PIXEL_FILL(1));
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, 8, 1, sColor_Normal, TEXT_SKIP_DRAW, COMPOUND_STRING("Preset:"));
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, 64, 1, sColor_Value, TEXT_SKIP_DRAW, sPresetNames[Randomizer_GetPreset(&sMenu->settings)]);
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, 8, 17, sColor_Normal, TEXT_SKIP_DRAW, COMPOUND_STRING("Seed code:"));
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NORMAL, 20, 33, sColor_Value, TEXT_SKIP_DRAW, grouped);
    AddTextPrinterParameterized3(WIN_OPTIONS, FONT_NARROW, 8, 51, sColor_Normal, TEXT_SKIP_DRAW, COMPOUND_STRING("Share the code so friends can play\nexactly the same game."));
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_FULL);
    DrawDescription(COMPOUND_STRING("These settings can't be changed later.\n{A_BUTTON}: begin  {B_BUTTON}: go back"));
}

// ── Input ────────────────────────────────────────────────────────────────────

static void Task_RandomizerMenuFadeIn(u8 taskId)
{
    if (!gPaletteFade.active)
        gTasks[taskId].func = Task_RandomizerMenuInput;
}

static void ChangePage(s32 delta)
{
    sMenu->page = (sMenu->page + PAGE_COUNT + delta) % PAGE_COUNT;
    sMenu->row = 0;
    PlaySE(SE_SELECT);
    DrawPage();
}

static u32 NextMonotype(u32 type, s32 delta)
{
    do
    {
        type = (type + NUMBER_OF_MON_TYPES + delta) % NUMBER_OF_MON_TYPES;
    } while (type == TYPE_MYSTERY || type == TYPE_STELLAR);
    return type;
}

static bool32 ChangeValue(s32 delta)
{
    u32 row = CurrentRow();
    struct RandomizerSettings *settings = &sMenu->settings;

    if (IsRowDisabled(row))
        return FALSE;
    switch (row)
    {
    case ROW_PRESET:
    {
        u32 preset = Randomizer_GetPreset(settings);
        if (preset == RANDOMIZER_PRESET_CUSTOM)
            preset = (delta > 0) ? RANDOMIZER_PRESET_RANDOMLOCKE : RANDOMIZER_PRESET_CHAOS;
        else
            preset = (preset + RANDOMIZER_PRESET_CUSTOM + delta) % RANDOMIZER_PRESET_CUSTOM;
        Randomizer_ApplyPreset(settings, preset);
        return TRUE;
    }
    case ROW_SEED:
        settings->seed = Randomizer_NewSeed();
        sMenu->seedFromCode = FALSE;
        return TRUE;
    case ROW_GENERATIONS:
        return FALSE;
    case ROW_MONOTYPE:
        settings->options[RANDOMIZER_OPTION_MONOTYPE] = NextMonotype(settings->options[RANDOMIZER_OPTION_MONOTYPE], delta);
        return TRUE;
    default:
    {
        u32 option = sRows[row].option;
        u32 count = Randomizer_GetOptionMax(option) + 1;
        settings->options[option] = (settings->options[option] + count + delta) % count;
        return TRUE;
    }
    }
}

static void StartCodeEntry(void)
{
    u8 code[RANDOMIZER_CODE_LENGTH + 1];

    Randomizer_EncodeSeedCode(&sMenu->settings, code);
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        for (u32 j = 0; j < Randomizer_GetCodeAlphabetSize(); j++)
        {
            if (Randomizer_GetCodeChar(j) == code[i])
            {
                sMenu->code[i] = j;
                break;
            }
        }
    }
    sMenu->codeCursor = 0;
    sMenu->mode = MODE_CODE;
    DrawHeader(COMPOUND_STRING("SEED CODE"));
    HighlightRow(HIGHLIGHT_ALL);
    DrawCode();
    DrawDescription(COMPOUND_STRING("{DPAD_UPDOWN}: change  {DPAD_LEFTRIGHT}: move\n{A_BUTTON}: done  {B_BUTTON}: cancel"));
}

static void FinishCodeEntry(void)
{
    u8 code[RANDOMIZER_CODE_LENGTH + 1];
    struct RandomizerSettings decoded;

    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
        code[i] = Randomizer_GetCodeChar(sMenu->code[i]);
    code[RANDOMIZER_CODE_LENGTH] = EOS;
    switch (Randomizer_DecodeSeedCode(code, &decoded))
    {
    case RANDOMIZER_CODE_OK:
        PlaySE(SE_SELECT);
        sMenu->settings = decoded;
        sMenu->seedFromCode = TRUE;
        sMenu->mode = MODE_BROWSE;
        DrawPage();
        DrawDescription(COMPOUND_STRING("Code accepted. Every setting now\nmatches your friend's game."));
        break;
    case RANDOMIZER_CODE_OTHER_VERSION:
        PlaySE(SE_FAILURE);
        DrawDescription(COMPOUND_STRING("That code was made with a different\nversion of BLACK PEARL EMERALD."));
        break;
    default:
        PlaySE(SE_FAILURE);
        DrawDescription(COMPOUND_STRING("That code isn't valid. Check each\ncharacter and try again."));
        break;
    }
}

static void HandleCodeInput(void)
{
    u32 size = Randomizer_GetCodeAlphabetSize();

    if (JOY_NEW(A_BUTTON))
    {
        FinishCodeEntry();
    }
    else if (JOY_NEW(B_BUTTON))
    {
        PlaySE(SE_SELECT);
        sMenu->mode = MODE_BROWSE;
        DrawPage();
    }
    else if (JOY_REPEAT(DPAD_UP) || JOY_REPEAT(DPAD_DOWN))
    {
        s32 delta = JOY_REPEAT(DPAD_UP) ? 1 : -1;
        sMenu->code[sMenu->codeCursor] = (sMenu->code[sMenu->codeCursor] + size + delta) % size;
        PlaySE(SE_SELECT);
        DrawCode();
    }
    else if (JOY_REPEAT(DPAD_LEFT) || JOY_REPEAT(DPAD_RIGHT))
    {
        s32 delta = JOY_REPEAT(DPAD_RIGHT) ? 1 : -1;
        sMenu->codeCursor = (sMenu->codeCursor + RANDOMIZER_CODE_LENGTH + delta) % RANDOMIZER_CODE_LENGTH;
        PlaySE(SE_SELECT);
        DrawCode();
    }
}

static void HandleGenerationInput(void)
{
    u16 *excluded = &sMenu->settings.options[RANDOMIZER_OPTION_GENERATIONS];

    if (JOY_NEW(A_BUTTON))
    {
        u32 toggled = *excluded ^ (1u << sMenu->generationCursor);
        if (toggled == (1u << RANDOMIZER_GENERATION_COUNT) - 1)
        {
            PlaySE(SE_FAILURE); // at least one generation stays on
            return;
        }
        *excluded = toggled;
        PlaySE(SE_SELECT);
        RedrawRow(sMenu->row);
    }
    else if (JOY_NEW(B_BUTTON) || JOY_NEW(START_BUTTON))
    {
        PlaySE(SE_SELECT);
        sMenu->mode = MODE_BROWSE;
        DrawPage();
    }
    else if (JOY_REPEAT(DPAD_LEFT) || JOY_REPEAT(DPAD_RIGHT))
    {
        s32 delta = JOY_REPEAT(DPAD_RIGHT) ? 1 : -1;
        sMenu->generationCursor = (sMenu->generationCursor + RANDOMIZER_GENERATION_COUNT + delta) % RANDOMIZER_GENERATION_COUNT;
        PlaySE(SE_SELECT);
        RedrawRow(sMenu->row);
    }
}

static void HandleBrowseInput(u8 taskId)
{
    const struct MenuPage *page = CurrentPage();

    if (JOY_NEW(START_BUTTON))
    {
        PlaySE(SE_SELECT);
        sMenu->mode = MODE_SUMMARY;
        DrawSummary();
    }
    else if (JOY_NEW(B_BUTTON))
    {
        PlaySE(SE_SELECT);
        sConfirmed = FALSE;
        BeginNormalPaletteFade(PALETTES_ALL, 0, 0, 16, RGB_BLACK);
        gTasks[taskId].func = Task_RandomizerMenuFadeOut;
    }
    else if (JOY_NEW(A_BUTTON))
    {
        switch (CurrentRow())
        {
        case ROW_SEED:
            PlaySE(SE_SELECT);
            StartCodeEntry();
            break;
        case ROW_GENERATIONS:
            PlaySE(SE_SELECT);
            sMenu->mode = MODE_GENERATIONS;
            DrawPage();
            break;
        default:
            if (ChangeValue(1))
            {
                PlaySE(SE_SELECT);
                DrawPage();
            }
            break;
        }
    }
    else if (JOY_NEW(L_BUTTON))
    {
        ChangePage(-1);
    }
    else if (JOY_NEW(R_BUTTON))
    {
        ChangePage(1);
    }
    else if (JOY_REPEAT(DPAD_UP) || JOY_REPEAT(DPAD_DOWN))
    {
        s32 delta = JOY_REPEAT(DPAD_DOWN) ? 1 : -1;
        sMenu->row = (sMenu->row + page->count + delta) % page->count;
        PlaySE(SE_SELECT);
        HighlightRow(sMenu->row);
        DrawDescription(sRows[CurrentRow()].description);
    }
    else if (JOY_REPEAT(DPAD_LEFT) || JOY_REPEAT(DPAD_RIGHT))
    {
        if (ChangeValue(JOY_REPEAT(DPAD_RIGHT) ? 1 : -1))
        {
            PlaySE(SE_SELECT);
            // Some rows depend on others (the preset name, troll abilities).
            DrawPage();
        }
    }
}

static void Task_RandomizerMenuInput(u8 taskId)
{
    switch (sMenu->mode)
    {
    case MODE_BROWSE:
        HandleBrowseInput(taskId);
        break;
    case MODE_GENERATIONS:
        HandleGenerationInput();
        break;
    case MODE_CODE:
        HandleCodeInput();
        break;
    case MODE_SUMMARY:
        if (JOY_NEW(A_BUTTON))
        {
            PlaySE(SE_SELECT);
            Randomizer_SaveSettings(&sMenu->settings);
            sConfirmed = TRUE;
            BeginNormalPaletteFade(PALETTES_ALL, 0, 0, 16, RGB_BLACK);
            gTasks[taskId].func = Task_RandomizerMenuFadeOut;
        }
        else if (JOY_NEW(B_BUTTON))
        {
            PlaySE(SE_SELECT);
            sMenu->mode = MODE_BROWSE;
            DrawPage();
        }
        break;
    }
}

static void Task_RandomizerMenuFadeOut(u8 taskId)
{
    if (!gPaletteFade.active)
    {
        DestroyTask(taskId);
        FreeAllWindowBuffers();
        TRY_FREE_AND_SET_NULL(sMenu);
        SetMainCallback2(gMain.savedCallback);
    }
}
