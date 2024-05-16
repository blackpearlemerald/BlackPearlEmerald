LavaridgeTown_Mart_MapScripts::
	.byte 0

LavaridgeTown_Mart_EventScript_Clerk::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	goto_if_unset FLAG_DEFEATED_LAVARIDGE_GYM, LavaridgeCity_Mart_EventScript_PokemartBasic
	goto_if_set FLAG_DEFEATED_LAVARIDGE_GYM, LavaridgeCity_Mart_EventScript_PokemartExpanded
	end

LavaridgeCity_Mart_EventScript_PokemartBasic::
	pokemart MauvilleCity_Mart_Pokemart_Basic
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
LavaridgeCity_Mart_Pokemart_Basic:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_NONE
	release
	end

LavaridgeCity_Mart_EventScript_PokemartExpanded::
	pokemart LavaridgeCity_Mart_Pokemart_Expanded
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
LavaridgeCity_Mart_Pokemart_Expanded:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_AUSPICIOUS_ARMOR
	.2byte ITEM_MALICIOUS_ARMOR
	.2byte ITEM_PEAT_BLOCK
	.2byte ITEM_METAL_ALLOY
	.2byte ITEM_SITRUS_BERRY
	.2byte ITEM_CUSTAP_BERRY
	.2byte ITEM_LUM_BERRY
	.2byte ITEM_TM93
	.2byte ITEM_TM94
	.2byte ITEM_TM95
	.2byte ITEM_TM96
	.2byte ITEM_TM98
	.2byte ITEM_TM99
	.2byte ITEM_TM101
	.2byte ITEM_TM104
	.2byte ITEM_TM105
	.2byte ITEM_TM106
	.2byte ITEM_TM108
	.2byte ITEM_TM109
	.2byte ITEM_TM111
	.2byte ITEM_TM112
	.2byte ITEM_NONE
	release
	end

LavaridgeTown_Mart_EventScript_ExpertM::
	msgbox LavaridgeTown_Mart_Text_XSpeedFirstStrike, MSGBOX_NPC
	end

LavaridgeTown_Mart_EventScript_OldWoman::
	msgbox LavaridgeTown_Mart_Text_LocalSpecialtyOnMtChimney, MSGBOX_NPC
	end

LavaridgeTown_Mart_Text_XSpeedFirstStrike:
	.string "Use X SPEED to add to a POKéMON's\n"
	.string "SPEED in battle.\p"
	.string "That will help it get in the first\n"
	.string "strike--a decided advantage!$"

LavaridgeTown_Mart_Text_LocalSpecialtyOnMtChimney:
	.string "On MT. CHIMNEY's peak, there's a local\n"
	.string "specialty that you can buy only there.\p"
	.string "Give it to a POKéMON--it will be elated.$"

