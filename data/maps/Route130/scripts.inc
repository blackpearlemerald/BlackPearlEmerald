Route130_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, Route130_OnTransition
	.byte 0

Route130_OnTransition:
	call_if_ge VAR_SOOTOPOLIS_CITY_STATE, 4, Route130_EventScript_CheckSetAbnormalWeather
@ Mirage Island is always present in BPE - it is this map's default layout
@ (LAYOUT_ROUTE130_MIRAGE_ISLAND, set in map.json). The rotating Legendary
@ Lottery resident only appears once the player is Champion; before that, and
@ once every pool legendary is caught, its object slot stays hidden.
	goto_if_set FLAG_SYS_GAME_CLEAR, Route130_EventScript_SetupIslandLegendary
	setflag FLAG_TEMP_12
	end

Route130_EventScript_SetupIslandLegendary::
@ Roll a random uncaught legendary. ChooseIslandLegendary sets VAR_ISLAND_LEGENDARY
@ + VAR_OBJ_GFX_ID_0 and returns the species in VAR_RESULT (SPECIES_NONE when every
@ pool legendary has been caught).
	special ChooseIslandLegendary
	goto_if_eq VAR_RESULT, SPECIES_NONE, Route130_EventScript_HideIslandLegendary
	end

@ Nothing to show (all caught) - keep the island's legendary slot hidden.
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
@ KO'd / ran / teleported: it vanishes, but its Pokedex caught flag is untouched, so
@ it stays in the pool. removeobject also sets this object's FLAG_TEMP_12, which is
@ what UpdateMirageIslandNamePopup (src/field_specials.c) reads to know the island's
@ resident has been used up and to roll a fresh one when the player steps back on.
@ (Whiting out skips this script entirely - the warp out and back re-rolls anyway.)
	msgbox Route130_Text_IslandLegendaryFled, MSGBOX_DEFAULT
	removeobject VAR_LAST_TALKED
	release
	end

Route130_EventScript_IslandLegendaryCaught::
	removeobject VAR_LAST_TALKED
	release
	end

Route130_Text_IslandLegendaryFled:
	.string "The Pokémon slipped back into the\n"
	.string "mirage, awaiting its next return…$"

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

