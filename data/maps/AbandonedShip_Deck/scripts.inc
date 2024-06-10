AbandonedShip_Deck_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, AbandonedShip_Deck_OnTransition
	.byte 0

AbandonedShip_Deck_OnTransition:
	setflag FLAG_LANDMARK_ABANDONED_SHIP
	end

Legendary_EventScript_BattleSpiritomb::
    setwildbattle SPECIES_SPIRITOMB, 75
    waitse
    playmoncry SPECIES_SPIRITOMB, CRY_MODE_ENCOUNTER
    delay 40
    waitmoncry
    dowildbattle
    fadescreenswapbuffers FADE_TO_BLACK
    removeobject(1)
    setflag FLAG_HIDE_OVERWORLD_SPIRITOMB
    fadescreenswapbuffers FADE_FROM_BLACK
    release
    end
