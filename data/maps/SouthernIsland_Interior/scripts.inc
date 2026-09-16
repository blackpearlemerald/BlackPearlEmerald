SouthernIsland_Interior_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, SouthernIsland_Interior_OnTransition
	.byte 0

SouthernIsland_Interior_OnTransition:
	call SouthernIsland_Interior_EventScript_SetUpPlayerGfx
	end

SouthernIsland_Interior_EventScript_SetUpPlayerGfx::
	checkplayergender
	goto_if_eq VAR_RESULT, MALE, SouthernIsland_Interior_EventScript_SetBrendanGfx
	goto_if_eq VAR_RESULT, FEMALE, SouthernIsland_Interior_EventScript_SetMayGfx
	end

SouthernIsland_Interior_EventScript_SetBrendanGfx::
	setvar VAR_OBJ_GFX_ID_0, OBJ_EVENT_GFX_CYNTHIA
	return

SouthernIsland_Interior_EventScript_SetMayGfx::
	setvar VAR_OBJ_GFX_ID_0, OBJ_EVENT_GFX_CYNTHIA
	return

@ BPE: the sign no longer starts the original level 50 Latios/Latias encounter.
@ Latias and Latios stand in the room as pre-Elite Four legendaries instead.
SouthernIsland_Interior_EventScript_Sign::
	msgbox SouthernIsland_Interior_Text_Sign, MSGBOX_SIGN
	end

Legendary_EventScript_BattleLatias::
	setwildbattle SPECIES_LATIAS, 75
	waitse
	playmoncry SPECIES_LATIAS, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	dowildbattle
	setvar VAR_0x8004, SPECIES_LATIAS
	special TryRecordPreE4LegendaryCatch
	fadescreenswapbuffers FADE_TO_BLACK
	removeobject LOCALID_SOUTHERN_ISLAND_LATIAS
	call_if_set FLAG_HIDE_OVERWORLD_LATIOS, SouthernIsland_Interior_EventScript_RemoveLatios
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end

Legendary_EventScript_BattleLatios::
	setwildbattle SPECIES_LATIOS, 75
	waitse
	playmoncry SPECIES_LATIOS, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	dowildbattle
	setvar VAR_0x8004, SPECIES_LATIOS
	special TryRecordPreE4LegendaryCatch
	fadescreenswapbuffers FADE_TO_BLACK
	removeobject LOCALID_SOUTHERN_ISLAND_LATIOS
	call_if_set FLAG_HIDE_OVERWORLD_LATIAS, SouthernIsland_Interior_EventScript_RemoveLatias
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end

SouthernIsland_Interior_EventScript_RemoveLatias::
	removeobject LOCALID_SOUTHERN_ISLAND_LATIAS
	return

SouthernIsland_Interior_EventScript_RemoveLatios::
	removeobject LOCALID_SOUTHERN_ISLAND_LATIOS
	return
