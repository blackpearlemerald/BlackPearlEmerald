ShoalCave_LowTideIceRoom_MapScripts::
	.byte 0

ShoalCave_LowTideIceRoom_EventScript_BattleArticuno::
	setwildbattle SPECIES_ARTICUNO, 75
	waitse
	playmoncry SPECIES_ARTICUNO, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	dowildbattle
	fadescreenswapbuffers FADE_TO_BLACK
	removeobject(4)
	setflag FLAG_HIDE_OVERWORLD_ARTICUNO
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end

