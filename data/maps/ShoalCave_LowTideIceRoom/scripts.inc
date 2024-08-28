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
	setvar VAR_PREE4_LEGENDARY 1
	goto_if_unset FLAG_SYS_GAME_CLEAR, Global_EventScript_HideLegendariesPreE4
	setflag FLAG_HIDE_OVERWORLD_ARTICUNO
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end

Global_EventScript_HideLegendariesPreE4::
	setflag FLAG_HIDE_OVERWORLD_ARTICUNO
	setflag FLAG_HIDE_OVERWORLD_MOLTRES
	setflag FLAG_HIDE_OVERWORLD_ENTEI
	setflag FLAG_HIDE_OVERWORLD_CELEBI
	setflag FLAG_HIDE_OVERWORLD_ZAPDOS
	setflag FLAG_HIDE_OVERWORLD_RAIKOU
	setflag FLAG_HIDE_OVERWORLD_SUICUNE
	setflag FLAG_HIDE_OVERWORLD_JIRACHI
	setflag FLAG_HIDE_OVERWORLD_SPIRITOMB
	setflag FLAG_HIDE_OVERWORLD_LATIOS
	setflag FLAG_HIDE_OVERWORLD_LATIAS
	setflag FLAG_HIDE_OVERWORLD_ROTOM
	setflag FLAG_HIDE_OVERWORLD_NULL
	setflag FLAG_HIDE_MEW

	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end