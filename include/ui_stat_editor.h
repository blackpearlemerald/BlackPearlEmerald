#ifndef GUARD_UI_STAT_EDITOR_H
#define GUARD_UI_STAT_EDITOR_H

#include "main.h"

void Task_OpenStatEditorFromStartMenu(u8 taskId);
void StatEditor_Init(MainCallback callback);

struct Pokemon;
bool32 StatEditor_CanEditMon(struct Pokemon *mon);
u32 StatEditor_GetStatMax(struct Pokemon *mon, u32 field);
u32 StatEditor_GetNextAbilityNum(struct Pokemon *mon, s32 direction);

extern const u8 gAbilityNames[][ABILITY_NAME_LENGTH + 1];
extern const struct SpeciesInfo gSpeciesInfo[];


#endif // GUARD_UI_STAT_EDITOR_H
