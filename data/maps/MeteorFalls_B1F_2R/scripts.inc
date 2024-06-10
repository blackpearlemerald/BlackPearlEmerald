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
    setflag FLAG_HIDE_OVERWORLD_JIRACHI
    fadescreenswapbuffers FADE_FROM_BLACK
    release
    end