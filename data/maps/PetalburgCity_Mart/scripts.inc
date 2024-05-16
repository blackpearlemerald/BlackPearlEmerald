PetalburgCity_Mart_MapScripts::
	.byte 0

PetalburgCity_Mart_EventScript_Clerk::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	goto_if_unset FLAG_DEFEATED_PETALBURG_GYM, PetalburgCity_Mart_EventScript_PokemartBasic
	goto_if_set FLAG_DEFEATED_PETALBURG_GYM, PetalburgCity_Mart_EventScript_PokemartExpanded
	end

PetalburgCity_Mart_EventScript_PokemartBasic::
	pokemart PetalburgCity_Mart_Pokemart_Basic
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
PetalburgCity_Mart_Pokemart_Basic:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_NONE
	release
	end

PetalburgCity_Mart_EventScript_PokemartExpanded::
	pokemart PetalburgCity_Mart_Pokemart_Expanded
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
PetalburgCity_Mart_Pokemart_Expanded:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_METAL_COAT
	.2byte ITEM_TM88
	.2byte ITEM_TM90
	.2byte ITEM_TM91
	.2byte ITEM_TM100
	.2byte ITEM_TM102
	.2byte ITEM_TM107
	.2byte ITEM_TM113
	.2byte ITEM_TM114
	.2byte ITEM_TM115
	.2byte ITEM_TM116
	.2byte ITEM_TM118
	.2byte ITEM_TM119
	.2byte ITEM_TM120
	.2byte ITEM_TM121
	.2byte ITEM_TM122
	.2byte ITEM_TM123
	.2byte ITEM_TM124
	.2byte ITEM_TM125
	.2byte ITEM_TM126
	.2byte ITEM_TM127
	.2byte ITEM_TM128
	.2byte ITEM_TM129
	.2byte ITEM_TM131
	.2byte ITEM_TM122
	.2byte ITEM_TM134
	.2byte ITEM_TM135
	.2byte ITEM_NONE
	release
	end

PetalburgCity_Mart_EventScript_Woman::
	msgbox PetalburgCity_Mart_Text_WeakWillGrowStronger, MSGBOX_NPC
	end

PetalburgCity_Mart_EventScript_Boy::
	msgbox PetalburgCity_Mart_Text_RepelIsUseful, MSGBOX_NPC
	end

PetalburgCity_Mart_EventScript_Man::
	msgbox PetalburgCity_Mart_Text_TakeSomeAntidotesWithYou, MSGBOX_NPC
	end

PetalburgCity_Mart_Text_WeakWillGrowStronger:
	.string "Even if a POKéMON is weak now,\n"
	.string "it will grow stronger.\p"
	.string "The most important thing is love!\n"
	.string "Love for your POKéMON!$"

PetalburgCity_Mart_Text_RepelIsUseful:
	.string "Do you use REPEL?\n"
	.string "It keeps POKéMON away, so it's\l"
	.string "useful when you're in a hurry.$"

PetalburgCity_Mart_Text_TakeSomeAntidotesWithYou:
	.string "Do you have any ANTIDOTES with\n"
	.string "you?\p"
	.string "If you walk around with a poisoned\n"
	.string "POKéMON, it will lose HP until it faints.\l"
	.string "Take some ANTIDOTES with you.$"

