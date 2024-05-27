TerraCave_Entrance_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, TerraCave_Entrance_OnTransition
	.byte 0

TerraCave_Entrance_OnTransition:
	setflag FLAG_ARRIVED_AT_TERRA_CAVE_ENTRANCE
	end

TerraCave_Entrance_EventScript_Guard::
	msgbox Guard_Text_Legendary, MSGBOX_NPC
	release
	end

Guard_Text_Legendary:
	.string "Sorry, I can only allow extremely\n"
	.string "powerful trainers past this point.$"
