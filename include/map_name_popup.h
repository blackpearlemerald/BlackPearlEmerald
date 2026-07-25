#ifndef GUARD_MAP_NAME_POPUP_H
#define GUARD_MAP_NAME_POPUP_H

// Exported type declarations

// Exported RAM declarations

// Exported ROM declarations
void HideMapNamePopUpWindow(void);
void ShowMapNamePopup(void);
u8 *GetPopUpMapName(u8 *dest, const struct MapHeader *mapHeader);

// BPE: rename the popup for a sub-area that has no map header of its own
// (Mirage Island inside Route 130). Pass MAPSEC_NONE / clear to fall back to
// the real map header. See sPopupMapSecOverride in src/map_name_popup.c.
void SetMapNamePopupOverride(mapsec_u16_t mapSec);
void ClearMapNamePopupOverride(void);
mapsec_u16_t GetMapNamePopupOverride(void);

#define MAP_POPUP_STRING_BUFFER_LENGTH 27
#define MAP_POPUP_PREFIX_BUFFER_LENGTH 6

#endif //GUARD_MAP_NAME_POPUP_H
