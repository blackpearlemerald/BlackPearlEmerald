#ifndef GUARD_RANDOMIZER_MENU_H
#define GUARD_RANDOMIZER_MENU_H

// Opens the randomizer settings screen. It returns to gMain.savedCallback, and
// RandomizerMenu_WasConfirmed() then tells whether the player confirmed settings
// (they are saved to the randomizer variables) or backed out.
void CB2_InitRandomizerMenu(void);
bool32 RandomizerMenu_WasConfirmed(void);

#endif // GUARD_RANDOMIZER_MENU_H
