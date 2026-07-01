Route130_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, Route130_OnTransition
	.byte 0

Route130_OnTransition:
	call_if_ge VAR_SOOTOPOLIS_CITY_STATE, 4, Route130_EventScript_CheckSetAbnormalWeather
	specialvar VAR_RESULT, IsMirageIslandPresent
	goto_if_eq VAR_RESULT, TRUE, Route130_EventScript_SetMirageIslandLayout
@ Mirage Island isn't currently visible, hide any objects on the island. Only the first flag is actually associated with anything.
	setflag FLAG_TEMP_HIDE_MIRAGE_ISLAND_BERRY_TREE
	setflag FLAG_TEMP_12
	setflag FLAG_TEMP_13
	setflag FLAG_TEMP_14
	setflag FLAG_TEMP_15
	setflag FLAG_TEMP_16
	setflag FLAG_TEMP_17
	setflag FLAG_TEMP_18
	setflag FLAG_TEMP_19
	setflag FLAG_TEMP_1A
	setflag FLAG_TEMP_1B
	setflag FLAG_TEMP_1C
	setflag FLAG_TEMP_1D
	setflag FLAG_TEMP_1E
	setflag FLAG_TEMP_1F
	setmaplayoutindex LAYOUT_ROUTE130
	end

Route130_EventScript_SetMirageIslandLayout::
	setmaplayoutindex LAYOUT_ROUTE130_MIRAGE_ISLAND
@ Legendary Lottery Island: roll a random uncaught legendary for the island slot.
@ ChooseIslandLegendary sets VAR_ISLAND_LEGENDARY + VAR_OBJ_GFX_ID_0 and returns
@ the species in VAR_RESULT (SPECIES_NONE when every pool legendary is caught).
	special ChooseIslandLegendary
	goto_if_eq VAR_RESULT, SPECIES_NONE, Route130_EventScript_HideIslandLegendary
	end

@ Every pool legendary has been caught - keep the island's legendary slot hidden.
Route130_EventScript_HideIslandLegendary::
	setflag FLAG_TEMP_12
	end

Route130_EventScript_IslandLegendary::
	lock
	faceplayer
	waitse
	playmoncry VAR_ISLAND_LEGENDARY, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	special SetupIslandLegendaryBattle
	special BattleSetup_StartLegendaryBattle
	specialvar VAR_RESULT, GetBattleOutcome
	goto_if_eq VAR_RESULT, B_OUTCOME_CAUGHT, Route130_EventScript_IslandLegendaryCaught
@ KO'd / ran / teleported: stays in the pool, re-rolled on the next map entry.
	msgbox Route130_Text_IslandLegendaryFled, MSGBOX_DEFAULT
	release
	end

Route130_EventScript_IslandLegendaryCaught::
	removeobject VAR_LAST_TALKED
	release
	end

Route130_Text_IslandLegendaryFled:
	.string "The legendary slipped back\n"
	.string "into the mirage…$"

Route130_EventScript_CheckSetAbnormalWeather::
	call_if_set FLAG_SYS_WEATHER_CTRL, Common_EventScript_SetAbnormalWeather
	return

Route130_EventScript_Rodney::
	trainerbattle_single TRAINER_RODNEY, Route130_Text_RodneyIntro, Route130_Text_RodneyDefeat
	msgbox Route130_Text_RodneyPostBattle, MSGBOX_AUTOCLOSE
	end

Route130_EventScript_Katie::
	trainerbattle_single TRAINER_KATIE, Route130_Text_KatieIntro, Route130_Text_KatieDefeat
	msgbox Route130_Text_KatiePostBattle, MSGBOX_AUTOCLOSE
	end

Route130_EventScript_Santiago::
	trainerbattle_single TRAINER_SANTIAGO, Route130_Text_SantiagoIntro, Route130_Text_SantiagoDefeat
	msgbox Route130_Text_SantiagoPostBattle, MSGBOX_AUTOCLOSE
	end

