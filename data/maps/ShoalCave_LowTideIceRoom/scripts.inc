ShoalCave_LowTideIceRoom_MapScripts::
	.byte 0

ShoalCave_LowTideIceRoom_EventScript_BattleArticuno::
	setwildbattle SPECIES_ARTICUNO, 75
	waitse
	playmoncry SPECIES_ARTICUNO, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	dowildbattle
	setvar VAR_0x8004, SPECIES_ARTICUNO
	special TryRecordPreE4LegendaryCatch
	fadescreenswapbuffers FADE_TO_BLACK
	removeobject(4)
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end
