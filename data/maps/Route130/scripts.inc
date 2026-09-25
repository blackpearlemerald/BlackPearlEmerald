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
@ Alternate forms share their base form's name, so the battle would call Galarian
@ Articuno "ARTICUNO" - the Pokemon the player already caught in Shoal Cave. Say
@ which one it is first. The special returns FALSE for everything else, so an
@ ordinary pool legendary still goes straight into its cry and battle.
	special BufferIslandLegendaryFormName
	call_if_eq VAR_RESULT, TRUE, Route130_EventScript_IslandLegendaryFormName
	waitse
	playmoncry VAR_ISLAND_LEGENDARY, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	special SetupIslandLegendaryBattle
	special BattleSetup_StartLegendaryBattle
	specialvar VAR_RESULT, GetBattleOutcome
	goto_if_eq VAR_RESULT, B_OUTCOME_CAUGHT, Route130_EventScript_IslandLegendaryCaught
@ KO'd / ran / teleported: it vanishes, but it hasn't been caught, so it stays in
@ the pool. removeobject also sets this object's FLAG_TEMP_12, which is
@ what UpdateMirageIslandNamePopup (src/field_specials.c) reads to know the island's
@ resident has been used up and to roll a fresh one when the player steps back on.
@ (Whiting out skips this script entirely - the warp out and back re-rolls anyway.)
	msgbox Route130_Text_IslandLegendaryFled, MSGBOX_DEFAULT
	removeobject VAR_LAST_TALKED
	release
	end

Route130_EventScript_IslandLegendaryCaught::
	special RecordIslandLegendaryCatch
	removeobject VAR_LAST_TALKED
	release
	end

Route130_EventScript_IslandLegendaryFormName::
	msgbox Route130_Text_IslandLegendaryForm, MSGBOX_DEFAULT
	closemessage
	return

Route130_Text_IslandLegendaryForm:
	.string "The mirage thins around a shape\n"
	.string "you have not seen before…\p"
	.string "It is {STR_VAR_1}!$"

Route130_Text_IslandLegendaryFled:
	.string "The Pokémon slipped back into the\n"
	.string "mirage, awaiting its next return…$"

@ ---------------------------------------------------------------------------
@ The Mirage Altar.
@
@ Cosmoem, Naganadel, the two Urshifu and Silvally are each made by evolving a
@ second Cosmog, Poipole, Kubfu or Type: Null, and the island only ever gives
@ one of anything. The altar hands back a legendary the player has already
@ caught so they can catch another, which is why those five are no longer in
@ the lottery pool. See src/field_specials.c for the full rule.
@
@ Only the four that lead somewhere are listed, and only once the player has
@ caught them, so the menu is short and says what it is for.
@ ---------------------------------------------------------------------------
Route130_EventScript_MirageAltar::
	lock
	goto_if_unset FLAG_SYS_GAME_CLEAR, Route130_EventScript_MirageAltarSilent
	msgbox Route130_Text_MirageAltarIntro, MSGBOX_DEFAULT
	setvar VAR_0x8005, 0
	setvar VAR_0x8004, SPECIES_COSMOG
	special CheckAltarSpeciesCaught
	call_if_eq VAR_RESULT, TRUE, Route130_EventScript_MirageAltarPushCosmog
	setvar VAR_0x8004, SPECIES_POIPOLE
	special CheckAltarSpeciesCaught
	call_if_eq VAR_RESULT, TRUE, Route130_EventScript_MirageAltarPushPoipole
	setvar VAR_0x8004, SPECIES_KUBFU
	special CheckAltarSpeciesCaught
	call_if_eq VAR_RESULT, TRUE, Route130_EventScript_MirageAltarPushKubfu
	setvar VAR_0x8004, SPECIES_TYPE_NULL
	special CheckAltarSpeciesCaught
	call_if_eq VAR_RESULT, TRUE, Route130_EventScript_MirageAltarPushTypeNull
@ dynmultistack on an empty stack would build a menu with no rows.
	goto_if_eq VAR_0x8005, 0, Route130_EventScript_MirageAltarNothingYet
	dynmultipush Route130_Text_MirageAltarCancel, 4
	dynmultistack 0, 0, FALSE, 5, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	switch VAR_RESULT
	case 0, Route130_EventScript_MirageAltarCallCosmog
	case 1, Route130_EventScript_MirageAltarCallPoipole
	case 2, Route130_EventScript_MirageAltarCallKubfu
	case 3, Route130_EventScript_MirageAltarCallTypeNull
	goto Route130_EventScript_MirageAltarLeave
	end

Route130_EventScript_MirageAltarPushCosmog::
	dynmultipush Route130_Text_MirageAltarCosmog, 0
	addvar VAR_0x8005, 1
	return

Route130_EventScript_MirageAltarPushPoipole::
	dynmultipush Route130_Text_MirageAltarPoipole, 1
	addvar VAR_0x8005, 1
	return

Route130_EventScript_MirageAltarPushKubfu::
	dynmultipush Route130_Text_MirageAltarKubfu, 2
	addvar VAR_0x8005, 1
	return

Route130_EventScript_MirageAltarPushTypeNull::
	dynmultipush Route130_Text_MirageAltarTypeNull, 3
	addvar VAR_0x8005, 1
	return

Route130_EventScript_MirageAltarCallCosmog::
	setvar VAR_0x8004, SPECIES_COSMOG
	goto Route130_EventScript_MirageAltarCall
	end

Route130_EventScript_MirageAltarCallPoipole::
	setvar VAR_0x8004, SPECIES_POIPOLE
	goto Route130_EventScript_MirageAltarCall
	end

Route130_EventScript_MirageAltarCallKubfu::
	setvar VAR_0x8004, SPECIES_KUBFU
	goto Route130_EventScript_MirageAltarCall
	end

Route130_EventScript_MirageAltarCallTypeNull::
	setvar VAR_0x8004, SPECIES_TYPE_NULL
	goto Route130_EventScript_MirageAltarCall
	end

@ VAR_0x8004 holds the chosen species; SetupMirageAltarBattle reads it.
Route130_EventScript_MirageAltarCall::
	bufferspeciesname STR_VAR_1, VAR_0x8004
	msgbox Route130_Text_MirageAltarCall, MSGBOX_DEFAULT
	closemessage
	waitse
	playmoncry VAR_0x8004, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	special SetupMirageAltarBattle
	special BattleSetup_StartLegendaryBattle
	release
	end

Route130_EventScript_MirageAltarSilent::
	msgbox Route130_Text_MirageAltarSilent, MSGBOX_DEFAULT
	release
	end

Route130_EventScript_MirageAltarNothingYet::
	msgbox Route130_Text_MirageAltarNothingYet, MSGBOX_DEFAULT
	release
	end

Route130_EventScript_MirageAltarLeave::
	msgbox Route130_Text_MirageAltarLeave, MSGBOX_DEFAULT
	release
	end

Route130_Text_MirageAltarSilent:
	.string "A worn stone altar.\p"
	.string "Whatever it once held, it is silent\n"
	.string "now.$"

Route130_Text_MirageAltarIntro:
	.string "The altar remembers every POKéMON\n"
	.string "the mirage has given up.\p"
	.string "Some of them were only ever half of\n"
	.string "what they could become…$"

Route130_Text_MirageAltarNothingYet:
	.string "The altar remembers nothing yet.\p"
	.string "Catch what the mirage offers, and it\n"
	.string "will learn.$"

Route130_Text_MirageAltarCall:
	.string "The altar glows, and the mirage\n"
	.string "gives up another {STR_VAR_1}!$"

Route130_Text_MirageAltarLeave:
	.string "The glow fades.$"

Route130_Text_MirageAltarCosmog:
	.string "Cosmog$"

Route130_Text_MirageAltarPoipole:
	.string "Poipole$"

Route130_Text_MirageAltarKubfu:
	.string "Kubfu$"

Route130_Text_MirageAltarTypeNull:
	.string "Type: Null$"

Route130_Text_MirageAltarCancel:
	.string "Nothing$"

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

