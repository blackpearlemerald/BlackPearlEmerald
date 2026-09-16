MeteorFalls_B1F_2R_MapScripts::
	.byte 0

Legendary_EventScript_BattleJirachi::
	setwildbattle SPECIES_JIRACHI, 75
	waitse
	playmoncry SPECIES_JIRACHI, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	dowildbattle
	setvar VAR_0x8004, SPECIES_JIRACHI
	special TryRecordPreE4LegendaryCatch
	fadescreenswapbuffers FADE_TO_BLACK
	removeobject(2)
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end