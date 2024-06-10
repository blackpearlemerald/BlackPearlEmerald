MeteorFalls_B1F_2R_MapScripts::
	.byte 0

Legendary_EventScript_BattleJirachi::
    setwildbattle SPECIES_JIRACHI, 75
    waitse
    playmoncry SPECIES_JIRACHI, CRY_MODE_ENCOUNTER
    delay 40
    waitmoncry
    dowildbattle
    fadescreenswapbuffers FADE_TO_BLACK
    removeobject(2)
	setvar VAR_PREE4_LEGENDARY 8
	goto_if_unset FLAG_SYS_GAME_CLEAR, Global_EventScript_HideLegendariesPreE4
    setflag FLAG_HIDE_OVERWORLD_JIRACHI
    fadescreenswapbuffers FADE_FROM_BLACK
    release
    end