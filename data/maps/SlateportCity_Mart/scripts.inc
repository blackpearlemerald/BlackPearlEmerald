SlateportCity_Mart_MapScripts::
	.byte 0

SlateportCity_Mart_EventScript_Clerk::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	goto_if_unset FLAG_DEFEATED_DEWFORD_GYM, SlateportCity_Mart_EventScript_PokemartBasic
	goto_if_set FLAG_DEFEATED_DEWFORD_GYM, SlateportCity_Mart_EventScript_PokemartExpanded
	end

SlateportCity_Mart_EventScript_PokemartBasic::
	pokemart SlateportCity_Mart_Pokemart_Basic
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
SlateportCity_Mart_Pokemart_Basic:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_NONE
	release
	end

SlateportCity_Mart_EventScript_PokemartExpanded::
	pokemart SlateportCity_Mart_Pokemart_Expanded
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
SlateportCity_Mart_Pokemart_Expanded:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_MOON_STONE
	.2byte ITEM_SUN_STONE
	.2byte ITEM_SHINY_STONE
	.2byte ITEM_DUSK_STONE
	.2byte ITEM_DAWN_STONE
	.2byte ITEM_ICE_STONE
	.2byte ITEM_SITRUS_BERRY
	.2byte ITEM_CUSTAP_BERRY
	.2byte ITEM_LUM_BERRY
	.2byte ITEM_PRISM_SCALE
	.2byte ITEM_KINGS_ROCK
	.2byte ITEM_TM26
	.2byte ITEM_TM28
	.2byte ITEM_TM31
	.2byte ITEM_TM30
	.2byte ITEM_TM32
	.2byte ITEM_TM33
	.2byte ITEM_TM34
	.2byte ITEM_TM35
	.2byte ITEM_TM37
	.2byte ITEM_TM38
	.2byte ITEM_TM39
	.2byte ITEM_TM40
	.2byte ITEM_TM42
	.2byte ITEM_TM44
	.2byte ITEM_TM45
	.2byte ITEM_TM46
	.2byte ITEM_TM47
	.2byte ITEM_TM49
	.2byte ITEM_TM50
	.2byte ITEM_TM51
	.2byte ITEM_TM52
	.2byte ITEM_TM55
	.2byte ITEM_TM56
	.2byte ITEM_TM08
	.2byte ITEM_TM09
	.2byte ITEM_TM10
	.2byte ITEM_TM74
	.2byte ITEM_TM75
	.2byte ITEM_TM76
	.2byte ITEM_TM226
	.2byte ITEM_NONE
	release
	end

SlateportCity_Mart_EventScript_BlackBelt::
	msgbox SlateportCity_Mart_Text_SomeItemsOnlyAtMart, MSGBOX_NPC
	end

SlateportCity_Mart_EventScript_Man::
	msgbox SlateportCity_Mart_Text_GreatBallIsBetter, MSGBOX_NPC
	end

SlateportCity_Mart_Text_SomeItemsOnlyAtMart:
	.string "The MARKET does have some interesting\n"
	.string "merchandise.\p"
	.string "But there are some items you can only\n"
	.string "get at a POKéMON MART.$"

SlateportCity_Mart_Text_GreatBallIsBetter:
	.string "A GREAT BALL is better than a POKé BALL\n"
	.string "at catching POKéMON.\p"
	.string "With this, I should be able to get that\n"
	.string "elusive POKéMON…$"

