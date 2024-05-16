MauvilleCity_Mart_MapScripts::
	.byte 0

MauvilleCity_Mart_EventScript_Clerk::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	goto_if_unset FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Mart_EventScript_PokemartBasic
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Mart_EventScript_PokemartExpanded
	end

MauvilleCity_Mart_EventScript_PokemartBasic::
	pokemart MauvilleCity_Mart_Pokemart_Basic
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
MauvilleCity_Mart_Pokemart_Basic:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_NONE
	release
	end

MauvilleCity_Mart_EventScript_PokemartExpanded::
	pokemart MauvilleCity_Mart_Pokemart_Expanded
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
MauvilleCity_Mart_Pokemart_Expanded:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_DUBIOUS_DISC
	.2byte ITEM_PROTECTOR
	.2byte ITEM_ELECTIRIZER
	.2byte ITEM_MAGMARIZER
	.2byte ITEM_REAPER_CLOTH
	.2byte ITEM_DRAGON_SCALE
	.2byte ITEM_METAL_COAT
	.2byte ITEM_DEEPSEATOOTH
	.2byte ITEM_DEEPSEASCALE
	.2byte ITEM_SITRUS_BERRY
	.2byte ITEM_CUSTAP_BERRY
	.2byte ITEM_LUM_BERRY
	.2byte ITEM_OCCA_BERRY
	.2byte ITEM_PASSHO_BERRY
	.2byte ITEM_WACAN_BERRY
	.2byte ITEM_RINDO_BERRY
	.2byte ITEM_YACHE_BERRY
	.2byte ITEM_CHOPLE_BERRY
	.2byte ITEM_KEBIA_BERRY
	.2byte ITEM_SHUCA_BERRY
	.2byte ITEM_COBA_BERRY
	.2byte ITEM_PAYAPA_BERRY
	.2byte ITEM_TANGA_BERRY
	.2byte ITEM_CHARTI_BERRY
	.2byte ITEM_KASIB_BERRY
	.2byte ITEM_HABAN_BERRY
	.2byte ITEM_COLBUR_BERRY
	.2byte ITEM_BABIRI_BERRY
	.2byte ITEM_CHILAN_BERRY
	.2byte ITEM_ROSELI_BERRY
	.2byte ITEM_TM29
	.2byte ITEM_TM48
	.2byte ITEM_TM58
	.2byte ITEM_TM59
	.2byte ITEM_TM60
	.2byte ITEM_TM61
	.2byte ITEM_TM62
	.2byte ITEM_TM63
	.2byte ITEM_TM64
	.2byte ITEM_TM65
	.2byte ITEM_TM66
	.2byte ITEM_TM67
	.2byte ITEM_TM68
	.2byte ITEM_TM69
	.2byte ITEM_TM70
	.2byte ITEM_TM71
	.2byte ITEM_TM72
	.2byte ITEM_TM73
	.2byte ITEM_TM77
	.2byte ITEM_TM78
	.2byte ITEM_TM79
	.2byte ITEM_TM80
	.2byte ITEM_TM81
	.2byte ITEM_TM82
	.2byte ITEM_TM83
	.2byte ITEM_TM84
	.2byte ITEM_TM85
	.2byte ITEM_TM86
	.2byte ITEM_TM87
	.2byte ITEM_TM89
	.2byte ITEM_TM92
	.2byte ITEM_NONE
	release
	end

MauvilleCity_Mart_EventScript_ExpertM::
	msgbox MauvilleCity_Mart_Text_ItemsToTemporarilyElevateStats, MSGBOX_NPC
	end

MauvilleCity_Mart_EventScript_Man::
	msgbox MauvilleCity_Mart_Text_DecisionsDetermineBattle, MSGBOX_NPC
	end

MauvilleCity_Mart_Text_ItemsToTemporarilyElevateStats:
	.string "There are items that temporarily\n"
	.string "elevate the stats of POKéMON.\p"
	.string "The ones I know you use in battle\n"
	.string "are X ATTACK and X DEFEND…\p"
	.string "I do believe that there are others\n"
	.string "like them.$"

MauvilleCity_Mart_Text_DecisionsDetermineBattle:
	.string "Use a certain move, or use an item\n"
	.string "instead…\p"
	.string "The TRAINER's decisions determine how\n"
	.string "battles turn out, I think.$"

