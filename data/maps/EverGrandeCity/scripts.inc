EverGrandeCity_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, EverGrandeCity_OnTransition
	.byte 0

EverGrandeCity_OnTransition:
	call_if_set FLAG_SYS_WEATHER_CTRL, Common_EventScript_SetAbnormalWeather
	end

EverGrandeCity_EventScript_VictoryRoadSign::
	msgbox EverGrandeCity_Text_EnteringVictoryRoad, MSGBOX_SIGN
	end

EverGrandeCity_EventScript_CitySign::
	msgbox EverGrandeCity_Text_CitySign, MSGBOX_SIGN
	end

EverGrandeCity_EventScript_PokemonLeagueSign::
	msgbox EverGrandeCity_Text_EnteringPokemonLeague, MSGBOX_SIGN
	end

EverGrandeCity_EventScript_SetVisitedEverGrande::
	setflag FLAG_VISITED_EVER_GRANDE_CITY
	setvar VAR_TEMP_1, 1
	end

@ Two post-game challengers standing beside the hedges on the approach to the
@ Pokemon League. Each asks Yes/No before battling; beat one and he opens a
@ permanent, unlimited shop.

EverGrandeCity_EventScript_ChakaJacek::
	lock
	faceplayer
	checktrainerflag TRAINER_CHAKAJACEK
	goto_if TRUE, EverGrandeCity_EventScript_ChakaJacekShop
	msgbox EverGrandeCity_Text_ChakaJacekIntro, MSGBOX_DEFAULT
	msgbox EverGrandeCity_Text_ChakaJacekChallenge, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, EverGrandeCity_EventScript_ChakaJacekDeclined
	trainerbattle_no_intro TRAINER_CHAKAJACEK, EverGrandeCity_Text_ChakaJacekDefeat
	msgbox EverGrandeCity_Text_ChakaJacekPostBattle, MSGBOX_DEFAULT
	goto EverGrandeCity_EventScript_ChakaJacekShop
	end

EverGrandeCity_EventScript_ChakaJacekDeclined::
	msgbox EverGrandeCity_Text_ChakaJacekDeclined, MSGBOX_DEFAULT
	release
	end

EverGrandeCity_EventScript_ChakaJacekShop::
	message EverGrandeCity_Text_ChakaJacekShopGreeting
	waitmessage
	pokemart EverGrandeCity_Pokemart_AbilityCapsule
	msgbox EverGrandeCity_Text_ChakaJacekShopFarewell, MSGBOX_DEFAULT
	release
	end

	.align 2
EverGrandeCity_Pokemart_AbilityCapsule:
	.2byte ITEM_ABILITY_CAPSULE
	pokemartlistend

EverGrandeCity_EventScript_Furius2::
	lock
	faceplayer
	checktrainerflag TRAINER_FURIUS2
	goto_if TRUE, EverGrandeCity_EventScript_Furius2Shop
	msgbox EverGrandeCity_Text_Furius2Intro, MSGBOX_DEFAULT
	msgbox EverGrandeCity_Text_Furius2Challenge, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, EverGrandeCity_EventScript_Furius2Declined
	trainerbattle_no_intro TRAINER_FURIUS2, EverGrandeCity_Text_Furius2Defeat
	msgbox EverGrandeCity_Text_Furius2PostBattle, MSGBOX_DEFAULT
	goto EverGrandeCity_EventScript_Furius2Shop
	end

EverGrandeCity_EventScript_Furius2Declined::
	msgbox EverGrandeCity_Text_Furius2Declined, MSGBOX_DEFAULT
	release
	end

EverGrandeCity_EventScript_Furius2Shop::
	message EverGrandeCity_Text_Furius2ShopGreeting
	waitmessage
	pokemart EverGrandeCity_Pokemart_AbilityPatch
	msgbox EverGrandeCity_Text_Furius2ShopFarewell, MSGBOX_DEFAULT
	release
	end

	.align 2
EverGrandeCity_Pokemart_AbilityPatch:
	.2byte ITEM_ABILITY_PATCH
	pokemartlistend

EverGrandeCity_Text_EnteringVictoryRoad:
	.string "ENTERING VICTORY ROAD$"

EverGrandeCity_Text_EnteringPokemonLeague:
	.string "ENTERING POKéMON LEAGUE\n"
	.string "CENTER GATE$"

EverGrandeCity_Text_CitySign:
	.string "EVER GRANDE CITY\p"
	.string "“The paradise of flowers, the sea,\n"
	.string "and POKéMON.”$"

EverGrandeCity_Text_ChakaJacekIntro:
	.string "I'm CHAKAJACEK.\p"
	.string "I was the very first person to beat\n"
	.string "the CHAMPION in STANDARD MODE.\p"
	.string "Nobody had finished this game\n"
	.string "before I did. Not one soul.$"

EverGrandeCity_Text_ChakaJacekChallenge:
	.string "So how about it? Want to battle\n"
	.string "the team I won with?\p"
	.string "Beat it, and I'll be your source of\n"
	.string "unlimited ABILITY CAPSULES.\p"
	.string "Ready?$"

EverGrandeCity_Text_ChakaJacekDeclined:
	.string "Heh. The offer stands whenever\n"
	.string "you're ready.$"

EverGrandeCity_Text_ChakaJacekDefeat:
	.string "My winning team… beaten?$"

EverGrandeCity_Text_ChakaJacekPostBattle:
	.string "Ha! A deal's a deal.\p"
	.string "From here on, ABILITY CAPSULES are\n"
	.string "yours. As many as you want.\p"
	.string "¥1000 each. Go build something\n"
	.string "unstoppable.$"

EverGrandeCity_Text_ChakaJacekShopGreeting:
	.string "ABILITY CAPSULES, ¥1000 apiece.\n"
	.string "How many do you need?$"

EverGrandeCity_Text_ChakaJacekShopFarewell:
	.string "Come back any time.$"

EverGrandeCity_Text_Furius2Intro:
	.string "The name's FURIUS2.\p"
	.string "I was the very first person to beat\n"
	.string "the CHAMPION in NUZLOCKE MODE.\p"
	.string "One life per POKéMON. No second\n"
	.string "chances. All the way to the top.$"

EverGrandeCity_Text_Furius2Challenge:
	.string "So how about it? Want to battle\n"
	.string "the team I won with?\p"
	.string "Beat it, and I'll be your source of\n"
	.string "unlimited ABILITY PATCHES.\p"
	.string "Ready?$"

EverGrandeCity_Text_Furius2Declined:
	.string "Take your time. Come back when\n"
	.string "your team's ready.$"

EverGrandeCity_Text_Furius2Defeat:
	.string "Heh… no second chances for me,\n"
	.string "either.$"

EverGrandeCity_Text_Furius2PostBattle:
	.string "I lost them all fair and square.\n"
	.string "A deal's a deal.\p"
	.string "ABILITY PATCHES, as many as you\n"
	.string "want. ¥2000 each.\p"
	.string "Drag those hidden abilities out\n"
	.string "into the light.$"

EverGrandeCity_Text_Furius2ShopGreeting:
	.string "ABILITY PATCHES, ¥2000 apiece.\n"
	.string "How many do you need?$"

EverGrandeCity_Text_Furius2ShopFarewell:
	.string "Play carefully out there.$"
