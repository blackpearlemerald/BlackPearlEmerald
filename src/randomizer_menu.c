// BPE: the randomizer settings screen, opened from Birch's speech.
// Six pages of options, a seed code entry and a final summary. The screen is a
// title line, one framed panel (the options above a description) and a line of
// button hints, so the controls, including how to start, are always shown.
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
    WIN_CONTROLS,
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
    ROW_START,
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

enum TextStyle
{
    STYLE_NAME,
    STYLE_VALUE,
    STYLE_DISABLED,
    STYLE_CURSOR,
    STYLE_ON_BACKGROUND, // the title and button hints, on the blue background
};

#define ROWS_PER_PAGE 5
#define PAGE_COUNT 6
#define ROW_HEIGHT 16
#define PANEL_WIDTH (26 * 8)
#define BAR_WIDTH (28 * 8)
#define VALUE_X 108
#define OPTION_NONE 0xFF

// The text palette is the standard menu palette, so button icons draw correctly,
// with one extra color for the selected row.
#define MENU_COLOR_HIGHLIGHT 10

// The window frame's nine tiles go after every window's tiles.
#define FRAME_BASE_TILE 0x1E0
#define FRAME_TILE(n) (FRAME_BASE_TILE + (n))

struct MenuRowInfo
{
    const u8 *name;
    const u8 *description;
    u8 option;                  // RANDOMIZER_OPTION_*, or OPTION_NONE for the setup rows
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

// Values say plainly whether something is random, matching the Features page.
static const u8 *const sOffRandom[] = {COMPOUND_STRING("Not random"), COMPOUND_STRING("Random")};
static const u8 *const sOffShuffled[] = {COMPOUND_STRING("Not random"), COMPOUND_STRING("Shuffled")};
static const u8 *const sNotAllowedAllowed[] = {COMPOUND_STRING("Not allowed"), COMPOUND_STRING("Allowed")};
static const u8 *const sStarterValues[] = {COMPOUND_STRING("Not random"), COMPOUND_STRING("Same type"), COMPOUND_STRING("Any type"), COMPOUND_STRING("Legendaries")};
static const u8 *const sConsistencyValues[] = {COMPOUND_STRING("All catchable"), COMPOUND_STRING("Per route")};
static const u8 *const sLegendaryValues[] = {COMPOUND_STRING("Not random"), COMPOUND_STRING("Legendaries only"), COMPOUND_STRING("Can be anywhere")};
static const u8 *const sStrengthValues[] = {COMPOUND_STRING("Close to original"), COMPOUND_STRING("Anything")};
static const u8 *const sBossValues[] = {COMPOUND_STRING("Not random"), COMPOUND_STRING("Random, same type"), COMPOUND_STRING("Random, any type")};
static const u8 *const sPresetNames[] = {COMPOUND_STRING("Randomlocke"), COMPOUND_STRING("Full"), COMPOUND_STRING("Chaos"), COMPOUND_STRING("Custom")};

// The Preset row describes whichever preset is selected.
static const u8 *const sPresetDescriptions[] =
{
    [RANDOMIZER_PRESET_RANDOMLOCKE] = COMPOUND_STRING("Random POKéMON, all still catchable.\nBosses and battle data aren't random."),
    [RANDOMIZER_PRESET_FULL]        = COMPOUND_STRING("Also random: bosses, abilities,\nmoves, TMs and items."),
    [RANDOMIZER_PRESET_CHAOS]       = COMPOUND_STRING("Everything is random, even types.\nSome POKéMON may not appear at all."),
    [RANDOMIZER_PRESET_CUSTOM]      = COMPOUND_STRING("Your own mix of options. Press left\nor right to go back to a preset."),
};

static const struct MenuRowInfo sRows[ROW_COUNT] =
{
    [ROW_PRESET] = {COMPOUND_STRING("Preset"), NULL, OPTION_NONE, NULL},
    [ROW_SEED] = {COMPOUND_STRING("Seed"),
        COMPOUND_STRING("Press left or right for a new seed.\nPress A to enter a friend's seed code."), OPTION_NONE, NULL},
    [ROW_START] = {COMPOUND_STRING("Start the game"),
        COMPOUND_STRING("Check your settings, then begin.\nSTART does the same on any page."), OPTION_NONE, NULL},
    [ROW_STARTERS] = {COMPOUND_STRING("Starters"),
        COMPOUND_STRING("Same type keeps each ball's type.\nLegendaries fills the case with them."), RANDOMIZER_OPTION_STARTERS, sStarterValues},
    [ROW_WILD] = {COMPOUND_STRING("Wild POKéMON"),
        COMPOUND_STRING("The POKéMON in grass, caves, water\nand fishing spots."), RANDOMIZER_OPTION_WILD, sOffRandom},
    [ROW_CONSISTENCY] = {COMPOUND_STRING("Wild swaps"),
        COMPOUND_STRING("All catchable keeps every POKéMON\nsomewhere. Per route may leave some out."), RANDOMIZER_OPTION_WILD_CONSISTENCY, sConsistencyValues},
    [ROW_GIFTS] = {COMPOUND_STRING("Gifts and trades"),
        COMPOUND_STRING("Gift POKéMON, eggs and the POKéMON\ntraders offer and ask for."), RANDOMIZER_OPTION_GIFTS, sOffRandom},
    [ROW_STATICS] = {COMPOUND_STRING("Static POKéMON"),
        COMPOUND_STRING("POKéMON you walk up to and battle,\nlike SNORLAX and SUDOWOODO."), RANDOMIZER_OPTION_STATICS, sOffRandom},
    [ROW_LEGENDARIES] = {COMPOUND_STRING("Legendaries"),
        COMPOUND_STRING("Legendaries only swaps them with each\nother. Can be anywhere mixes them in."), RANDOMIZER_OPTION_LEGENDARIES, sLegendaryValues},
    [ROW_STRENGTH] = {COMPOUND_STRING("Strength"),
        COMPOUND_STRING("How strong the random POKéMON are\ncompared with the ones they replace."), RANDOMIZER_OPTION_STRENGTH, sStrengthValues},
    [ROW_GENERATIONS] = {COMPOUND_STRING("Generations"),
        COMPOUND_STRING("Press A to choose which generations\nof POKéMON can appear."), RANDOMIZER_OPTION_GENERATIONS, NULL},
    [ROW_REGULAR_TRAINERS] = {COMPOUND_STRING("Regular trainers"),
        COMPOUND_STRING("The teams of every trainer who\nisn't a boss."), RANDOMIZER_OPTION_REGULAR_TRAINERS, sOffRandom},
    [ROW_BOSS_TRAINERS] = {COMPOUND_STRING("Boss trainers"),
        COMPOUND_STRING("GYM LEADERS, the ELITE FOUR, rivals\nand the team bosses."), RANDOMIZER_OPTION_BOSS_TRAINERS, sBossValues},
    [ROW_FIELD_ITEMS] = {COMPOUND_STRING("Field items"),
        COMPOUND_STRING("Item balls and hidden items trade\nplaces. Key items and HMs stay."), RANDOMIZER_OPTION_FIELD_ITEMS, sOffShuffled},
    [ROW_ABILITIES] = {COMPOUND_STRING("Abilities"),
        COMPOUND_STRING("Each evolution family gets new\nabilities. Broken ones are banned."), RANDOMIZER_OPTION_ABILITIES, sOffRandom},
    [ROW_TROLL_ABILITIES] = {COMPOUND_STRING("Harmful abilities"),
        COMPOUND_STRING("Allows abilities like TRUANT and\nSLOW START with random abilities."), RANDOMIZER_OPTION_TROLL_ABILITIES, sNotAllowedAllowed},
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
    {COMPOUND_STRING("SETUP"), {ROW_PRESET, ROW_SEED, ROW_START}, 3},
    {COMPOUND_STRING("POKéMON"), {ROW_STARTERS, ROW_WILD, ROW_CONSISTENCY, ROW_GIFTS, ROW_STATICS}, 5},
    {COMPOUND_STRING("POKéMON POOL"), {ROW_LEGENDARIES, ROW_STRENGTH, ROW_GENERATIONS}, 3},
    {COMPOUND_STRING("TRAINERS AND ITEMS"), {ROW_REGULAR_TRAINERS, ROW_BOSS_TRAINERS, ROW_FIELD_ITEMS}, 3},
    {COMPOUND_STRING("BATTLE"), {ROW_ABILITIES, ROW_TROLL_ABILITIES, ROW_LEVEL_UP_MOVES, ROW_TM_COMPATIBILITY, ROW_TM_CONTENTS}, 5},
    {COMPOUND_STRING("CHAOS"), {ROW_TYPES, ROW_EVOLUTIONS, ROW_BASE_STATS, ROW_TYPE_CHART, ROW_MONOTYPE}, 5},
};

static const u8 sText_ControlsBrowse[] = _("{DPAD_LEFTRIGHT} Change  {L_BUTTON}{R_BUTTON} Page  {START_BUTTON} Start  {B_BUTTON} Back");
static const u8 sText_ControlsGenerations[] = _("{DPAD_LEFTRIGHT} Choose  {A_BUTTON} Switch on or off  {B_BUTTON} Done");
static const u8 sText_ControlsCode[] = _("{DPAD_UPDOWN} Change  {DPAD_LEFTRIGHT} Move  {A_BUTTON} Done  {B_BUTTON} Cancel");
static const u8 sText_ControlsSummary[] = _("{A_BUTTON} Begin the game  {B_BUTTON} Go back");

// {foreground, shadow}; the background is the row's.
static const u8 sTextStyles[][2] =
{
    [STYLE_NAME]          = {TEXT_COLOR_DARK_GRAY, TEXT_COLOR_LIGHT_GRAY},
    [STYLE_VALUE]         = {TEXT_COLOR_BLUE, TEXT_COLOR_LIGHT_BLUE},
    [STYLE_DISABLED]      = {TEXT_COLOR_LIGHT_GRAY, TEXT_COLOR_WHITE},
    [STYLE_CURSOR]        = {TEXT_COLOR_RED, TEXT_COLOR_LIGHT_RED},
    [STYLE_ON_BACKGROUND] = {TEXT_COLOR_WHITE, TEXT_COLOR_DARK_GRAY},
};

static const u16 sMenuBg_Pal[] = {RGB(17, 18, 31)};
static const u16 sHighlight_Pal[] = {RGB(25, 27, 31)};

static const struct WindowTemplate sWindowTemplates[] =
{
    [WIN_HEADER] = {
        .bg = 1,
        .tilemapLeft = 1,
        .tilemapTop = 0,
        .width = 28,
        .height = 2,
        .paletteNum = 1,
        .baseBlock = 2
    },
    [WIN_OPTIONS] = {
        .bg = 0,
        .tilemapLeft = 2,
        .tilemapTop = 3,
        .width = 26,
        .height = 10,
        .paletteNum = 1,
        .baseBlock = 2 + 28 * 2
    },
    [WIN_DESCRIPTION] = {
        .bg = 1,
        .tilemapLeft = 2,
        .tilemapTop = 13,
        .width = 26,
        .height = 4,
        .paletteNum = 1,
        .baseBlock = 2 + 28 * 2 + 26 * 10
    },
    [WIN_CONTROLS] = {
        .bg = 1,
        .tilemapLeft = 1,
        .tilemapTop = 18,
        .width = 28,
        .height = 2,
        .paletteNum = 1,
        .baseBlock = 2 + 28 * 2 + 26 * 10 + 26 * 4
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

// The panel around the options and the description, rows 2 to 17.
static void DrawFrame(void)
{
    const u32 top = 2, height = 14, bottom = top + height + 1;

    FillBgTilemapBufferRect(1, FRAME_TILE(0),  1, top,     1, 1, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(1),  2, top,    26, 1, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(2), 28, top,     1, 1, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(3),  1, top + 1, 1, height, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(5), 28, top + 1, 1, height, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(6),  1, bottom,  1, 1, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(7),  2, bottom, 26, 1, 7);
    FillBgTilemapBufferRect(1, FRAME_TILE(8), 28, bottom,  1, 1, 7);
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
        SetGpuReg(REG_OFFSET_WININ, 0);
        SetGpuReg(REG_OFFSET_WINOUT, 0);
        SetGpuReg(REG_OFFSET_BLDCNT, 0);
        SetGpuReg(REG_OFFSET_BLDALPHA, 0);
        SetGpuReg(REG_OFFSET_BLDY, 0);
        SetGpuReg(REG_OFFSET_DISPCNT, DISPCNT_OBJ_ON | DISPCNT_OBJ_1D_MAP);
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
        LoadBgTiles(1, GetWindowFrameTilesPal(gSaveBlock2Ptr->optionsWindowFrameType)->tiles, 0x120, FRAME_BASE_TILE);
        LoadPalette(sMenuBg_Pal, BG_PLTT_ID(0), sizeof(sMenuBg_Pal));
        LoadPalette(GetWindowFrameTilesPal(gSaveBlock2Ptr->optionsWindowFrameType)->pal, BG_PLTT_ID(7), PLTT_SIZE_4BPP);
        LoadPalette(gStandardMenuPalette, BG_PLTT_ID(1), PLTT_SIZE_4BPP);
        LoadPalette(sHighlight_Pal, BG_PLTT_ID(1) + MENU_COLOR_HIGHLIGHT, sizeof(sHighlight_Pal));
        gMain.state++;
        break;
    case 4:
        PutWindowTilemap(WIN_HEADER);
        PutWindowTilemap(WIN_OPTIONS);
        PutWindowTilemap(WIN_DESCRIPTION);
        PutWindowTilemap(WIN_CONTROLS);
        DrawFrame();
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

static void Print(u32 windowId, u32 fontId, u32 x, u32 y, u32 background, enum TextStyle style, const u8 *text)
{
    const u8 colors[3] = {background, sTextStyles[style][0], sTextStyles[style][1]};

    AddTextPrinterParameterized3(windowId, fontId, x, y, colors, TEXT_SKIP_DRAW, text);
}

static void DrawHeader(const u8 *title, bool32 showPage)
{
    u8 text[64];
    u8 *end;

    FillWindowPixelBuffer(WIN_HEADER, PIXEL_FILL(TEXT_COLOR_TRANSPARENT));
    end = StringCopy(text, COMPOUND_STRING("RANDOMIZER  "));
    StringCopy(end, title);
    Print(WIN_HEADER, FONT_NORMAL, 4, 1, TEXT_COLOR_TRANSPARENT, STYLE_ON_BACKGROUND, text);
    if (showPage)
    {
        end = ConvertIntToDecimalStringN(text, sMenu->page + 1, STR_CONV_MODE_LEFT_ALIGN, 1);
        end = StringCopy(end, COMPOUND_STRING("/"));
        ConvertIntToDecimalStringN(end, PAGE_COUNT, STR_CONV_MODE_LEFT_ALIGN, 1);
        Print(WIN_HEADER, FONT_NORMAL, GetStringRightAlignXOffset(FONT_NORMAL, text, BAR_WIDTH - 4), 1, TEXT_COLOR_TRANSPARENT, STYLE_ON_BACKGROUND, text);
    }
    CopyWindowToVram(WIN_HEADER, COPYWIN_FULL);
}

static void DrawDescription(const u8 *text)
{
    FillWindowPixelBuffer(WIN_DESCRIPTION, PIXEL_FILL(TEXT_COLOR_WHITE));
    FillWindowPixelRect(WIN_DESCRIPTION, PIXEL_FILL(TEXT_COLOR_LIGHT_GRAY), 0, 0, PANEL_WIDTH, 1);
    Print(WIN_DESCRIPTION, FONT_NARROW, 4, 1, TEXT_COLOR_WHITE, STYLE_NAME, text);
    CopyWindowToVram(WIN_DESCRIPTION, COPYWIN_FULL);
}

static void DrawControls(const u8 *text)
{
    FillWindowPixelBuffer(WIN_CONTROLS, PIXEL_FILL(TEXT_COLOR_TRANSPARENT));
    Print(WIN_CONTROLS, FONT_NARROW, 4, 1, TEXT_COLOR_TRANSPARENT, STYLE_ON_BACKGROUND, text);
    CopyWindowToVram(WIN_CONTROLS, COPYWIN_FULL);
}

static void DrawGenerationDescription(void)
{
    u8 *end;
    u32 generation = sMenu->generationCursor;
    bool32 excluded = (sMenu->settings.options[RANDOMIZER_OPTION_GENERATIONS] >> generation) & 1;

    end = StringCopy(gStringVar4, COMPOUND_STRING("Generation "));
    end = ConvertIntToDecimalStringN(end, generation + 1, STR_CONV_MODE_LEFT_ALIGN, 1);
    if (excluded)
        StringCopy(end, COMPOUND_STRING(" is left out: its\nPOKéMON won't appear."));
    else
        StringCopy(end, COMPOUND_STRING(" is in. Gray numbers\nare generations that are left out."));
    DrawDescription(gStringVar4);
}

// Every row is drawn inside its own 16 pixels, so one row can be redrawn alone.
static void DrawGenerations(u32 top, u32 background)
{
    u8 digit[2];
    u32 excluded = sMenu->settings.options[RANDOMIZER_OPTION_GENERATIONS];

    for (u32 i = 0; i < RANDOMIZER_GENERATION_COUNT; i++)
    {
        u32 x = VALUE_X + i * 10;

        digit[0] = CHAR_1 + i;
        digit[1] = EOS;
        Print(WIN_OPTIONS, FONT_NORMAL, x, top, background, (excluded & (1u << i)) ? STYLE_DISABLED : STYLE_VALUE, digit);
        if (sMenu->mode == MODE_GENERATIONS && sMenu->generationCursor == i)
            FillWindowPixelRect(WIN_OPTIONS, PIXEL_FILL(TEXT_COLOR_RED), x, top + 14, 6, 2);
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
    case ROW_START:
        return NULL;
    case ROW_MONOTYPE:
    {
        u32 type = sMenu->settings.options[RANDOMIZER_OPTION_MONOTYPE];
        return type == TYPE_NONE ? COMPOUND_STRING("Off") : gTypesInfo[type].name;
    }
    default:
        return info->valueNames[sMenu->settings.options[info->option]];
    }
}

static const u8 *GetDescription(u32 row)
{
    if (row == ROW_PRESET)
        return sPresetDescriptions[Randomizer_GetPreset(&sMenu->settings)];
    return sRows[row].description;
}

static void DrawRow(u32 index)
{
    u32 row = CurrentPage()->rows[index];
    u32 top = index * ROW_HEIGHT;
    bool32 selected = (index == sMenu->row && (sMenu->mode == MODE_BROWSE || sMenu->mode == MODE_GENERATIONS));
    u32 background = selected ? MENU_COLOR_HIGHLIGHT : TEXT_COLOR_WHITE;
    bool32 disabled = IsRowDisabled(row);
    const u8 *value;

    FillWindowPixelRect(WIN_OPTIONS, PIXEL_FILL(background), 0, top, PANEL_WIDTH, ROW_HEIGHT);
    Print(WIN_OPTIONS, FONT_NORMAL, 8, top, background, disabled ? STYLE_DISABLED : STYLE_NAME, sRows[row].name);
    if (row == ROW_GENERATIONS)
    {
        DrawGenerations(top, background);
        return;
    }
    value = GetValueName(row);
    if (value != NULL)
        Print(WIN_OPTIONS, FONT_NARROW, VALUE_X, top, background, disabled ? STYLE_DISABLED : STYLE_VALUE, value);
}

static void DrawPage(void)
{
    const struct MenuPage *page = CurrentPage();

    DrawHeader(page->title, TRUE);
    FillWindowPixelBuffer(WIN_OPTIONS, PIXEL_FILL(TEXT_COLOR_WHITE));
    for (u32 i = 0; i < page->count; i++)
        DrawRow(i);
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_FULL);
    if (sMenu->mode == MODE_GENERATIONS)
    {
        DrawGenerationDescription();
        DrawControls(sText_ControlsGenerations);
    }
    else
    {
        DrawDescription(GetDescription(CurrentRow()));
        DrawControls(sText_ControlsBrowse);
    }
}

static void RedrawRow(u32 index)
{
    DrawRow(index);
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_GFX);
}

static void DrawCode(void)
{
    u8 text[2];
    u32 x = 20;

    FillWindowPixelBuffer(WIN_OPTIONS, PIXEL_FILL(TEXT_COLOR_WHITE));
    Print(WIN_OPTIONS, FONT_NORMAL, 8, 0, TEXT_COLOR_WHITE, STYLE_NAME, COMPOUND_STRING("Enter the seed code:"));
    for (u32 i = 0; i < RANDOMIZER_CODE_LENGTH; i++)
    {
        if (i != 0 && i % 4 == 0)
        {
            text[0] = CHAR_HYPHEN;
            text[1] = EOS;
            Print(WIN_OPTIONS, FONT_NORMAL, x, 24, TEXT_COLOR_WHITE, STYLE_NAME, text);
            x += 8;
        }
        text[0] = Randomizer_GetCodeChar(sMenu->code[i]);
        text[1] = EOS;
        if (i == sMenu->codeCursor)
        {
            Print(WIN_OPTIONS, FONT_NORMAL, x, 24, TEXT_COLOR_WHITE, STYLE_CURSOR, text);
            FillWindowPixelRect(WIN_OPTIONS, PIXEL_FILL(TEXT_COLOR_RED), x, 24 + 14, 7, 2);
        }
        else
        {
            Print(WIN_OPTIONS, FONT_NORMAL, x, 24, TEXT_COLOR_WHITE, STYLE_VALUE, text);
        }
        x += 9;
    }
    Print(WIN_OPTIONS, FONT_NARROW, 8, 48, TEXT_COLOR_WHITE, STYLE_NAME,
          COMPOUND_STRING("Codes never use O, I, 0 or 1, so\nthey can't be mixed up."));
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_GFX);
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

    DrawHeader(COMPOUND_STRING("READY?"), FALSE);
    FillWindowPixelBuffer(WIN_OPTIONS, PIXEL_FILL(TEXT_COLOR_WHITE));
    Print(WIN_OPTIONS, FONT_NORMAL, 8, 0, TEXT_COLOR_WHITE, STYLE_NAME, COMPOUND_STRING("Preset"));
    Print(WIN_OPTIONS, FONT_NARROW, VALUE_X, 0, TEXT_COLOR_WHITE, STYLE_VALUE, sPresetNames[Randomizer_GetPreset(&sMenu->settings)]);
    Print(WIN_OPTIONS, FONT_NORMAL, 8, 16, TEXT_COLOR_WHITE, STYLE_NAME, COMPOUND_STRING("Seed code"));
    Print(WIN_OPTIONS, FONT_NORMAL, 20, 32, TEXT_COLOR_WHITE, STYLE_VALUE, grouped);
    Print(WIN_OPTIONS, FONT_NARROW, 8, 48, TEXT_COLOR_WHITE, STYLE_NAME,
          COMPOUND_STRING("Share the code so friends can play\nexactly the same game."));
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_GFX);
    DrawDescription(COMPOUND_STRING("These settings can't be changed\nonce the game begins."));
    DrawControls(sText_ControlsSummary);
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

static void MoveCursor(s32 delta)
{
    u32 count = CurrentPage()->count;
    u32 previous = sMenu->row;

    sMenu->row = (sMenu->row + count + delta) % count;
    PlaySE(SE_SELECT);
    DrawRow(previous);
    DrawRow(sMenu->row);
    CopyWindowToVram(WIN_OPTIONS, COPYWIN_GFX);
    DrawDescription(GetDescription(CurrentRow()));
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
    case ROW_START:
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

static void OpenSummary(void)
{
    PlaySE(SE_SELECT);
    sMenu->mode = MODE_SUMMARY;
    DrawSummary();
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
    DrawHeader(COMPOUND_STRING("SEED CODE"), FALSE);
    DrawCode();
    DrawDescription(COMPOUND_STRING("Type the code a friend shared to\nplay exactly the same game."));
    DrawControls(sText_ControlsCode);
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
        DrawGenerationDescription();
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
        DrawGenerationDescription();
    }
}

static void HandleBrowseInput(u8 taskId)
{
    if (JOY_NEW(START_BUTTON))
    {
        OpenSummary();
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
        case ROW_START:
            OpenSummary();
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
        MoveCursor(JOY_REPEAT(DPAD_DOWN) ? 1 : -1);
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
