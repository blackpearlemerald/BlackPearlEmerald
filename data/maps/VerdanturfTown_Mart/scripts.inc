VerdanturfTown_Mart_MapScripts::
	.byte 0

VerdanturfTown_Mart_EventScript_Clerk::
	lock
	faceplayer
	message gText_Beans_HowMayIServeYou
	waitmessage
	goto_if_set FLAG_BADGE04_GET, VerdanturfTown_Mart_EventScript_PokemartExpanded4
	goto_if_set FLAG_BADGE03_GET, VerdanturfTown_Mart_EventScript_PokemartExpanded3
	goto VerdanturfTown_Mart_EventScript_PokemartBasic
	end

VerdanturfTown_Mart_EventScript_PokemartBasic::
	pokemart VerdanturfTown_Mart_Pokemart_Basic
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
VerdanturfTown_Mart_Pokemart_Basic:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_MAX_POTION
	.2byte ITEM_FIRE_STONE
	.2byte ITEM_WATER_STONE
	.2byte ITEM_THUNDER_STONE
	.2byte ITEM_LEAF_STONE
	.2byte ITEM_MOON_STONE
	.2byte ITEM_SUN_STONE
	.2byte ITEM_SHINY_STONE
	.2byte ITEM_DUSK_STONE
	.2byte ITEM_DAWN_STONE
	.2byte ITEM_ICE_STONE
	.2byte ITEM_LINKING_CORD
	.2byte ITEM_SWEET_APPLE
	.2byte ITEM_TART_APPLE
	.2byte ITEM_SYRUPY_APPLE
	.2byte ITEM_UPGRADE
	.2byte ITEM_CRACKED_POT
	.2byte ITEM_CHIPPED_POT
	.2byte ITEM_UNREMARKABLE_TEACUP
	.2byte ITEM_MASTERPIECE_TEACUP
	.2byte ITEM_PRISM_SCALE
	.2byte ITEM_KINGS_ROCK
	.2byte ITEM_NONE
	release
	end

VerdanturfTown_Mart_EventScript_PokemartExpanded3::
	pokemart VerdanturfTown_Mart_Pokemart_Expanded3
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
VerdanturfTown_Mart_Pokemart_Expanded3:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_MAX_POTION
	.2byte ITEM_FIRE_STONE
	.2byte ITEM_WATER_STONE
	.2byte ITEM_THUNDER_STONE
	.2byte ITEM_LEAF_STONE
	.2byte ITEM_MOON_STONE
	.2byte ITEM_SUN_STONE
	.2byte ITEM_SHINY_STONE
	.2byte ITEM_DUSK_STONE
	.2byte ITEM_DAWN_STONE
	.2byte ITEM_ICE_STONE
	.2byte ITEM_LINKING_CORD
	.2byte ITEM_SWEET_APPLE
	.2byte ITEM_TART_APPLE
	.2byte ITEM_SYRUPY_APPLE
	.2byte ITEM_UPGRADE
	.2byte ITEM_CRACKED_POT
	.2byte ITEM_CHIPPED_POT
	.2byte ITEM_UNREMARKABLE_TEACUP
	.2byte ITEM_MASTERPIECE_TEACUP
	.2byte ITEM_DUBIOUS_DISC
	.2byte ITEM_PROTECTOR
	.2byte ITEM_ELECTIRIZER
	.2byte ITEM_MAGMARIZER
	.2byte ITEM_REAPER_CLOTH
	.2byte ITEM_DRAGON_SCALE
	.2byte ITEM_METAL_COAT
	.2byte ITEM_DEEPSEATOOTH
	.2byte ITEM_DEEPSEASCALE
	.2byte ITEM_PRISM_SCALE
	.2byte ITEM_KINGS_ROCK
	.2byte ITEM_NONE
	release
	end

VerdanturfTown_Mart_EventScript_PokemartExpanded4::
	pokemart VerdanturfTown_Mart_Pokemart_Expanded4
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
VerdanturfTown_Mart_Pokemart_Expanded4:
	.2byte ITEM_POKE_BALL
	.2byte ITEM_GREAT_BALL
	.2byte ITEM_ULTRA_BALL
	.2byte ITEM_RARE_CANDY
	.2byte ITEM_POMEG_BERRY
	.2byte ITEM_MAX_REPEL
	.2byte ITEM_MAX_POTION
	.2byte ITEM_FIRE_STONE
	.2byte ITEM_WATER_STONE
	.2byte ITEM_THUNDER_STONE
	.2byte ITEM_LEAF_STONE
	.2byte ITEM_MOON_STONE
	.2byte ITEM_SUN_STONE
	.2byte ITEM_SHINY_STONE
	.2byte ITEM_DUSK_STONE
	.2byte ITEM_DAWN_STONE
	.2byte ITEM_ICE_STONE
	.2byte ITEM_LINKING_CORD
	.2byte ITEM_SWEET_APPLE
	.2byte ITEM_TART_APPLE
	.2byte ITEM_SYRUPY_APPLE
	.2byte ITEM_UPGRADE
	.2byte ITEM_CRACKED_POT
	.2byte ITEM_CHIPPED_POT
	.2byte ITEM_UNREMARKABLE_TEACUP
	.2byte ITEM_MASTERPIECE_TEACUP
	.2byte ITEM_DUBIOUS_DISC
	.2byte ITEM_PROTECTOR
	.2byte ITEM_ELECTIRIZER
	.2byte ITEM_MAGMARIZER
	.2byte ITEM_REAPER_CLOTH
	.2byte ITEM_DRAGON_SCALE
	.2byte ITEM_METAL_COAT
	.2byte ITEM_DEEPSEATOOTH
	.2byte ITEM_DEEPSEASCALE
	.2byte ITEM_PRISM_SCALE
	.2byte ITEM_KINGS_ROCK
	.2byte ITEM_AUSPICIOUS_ARMOR
	.2byte ITEM_MALICIOUS_ARMOR
	.2byte ITEM_PEAT_BLOCK
	.2byte ITEM_METAL_ALLOY
	.2byte ITEM_NONE
	release
	end

VerdanturfTown_Mart_EventScript_Boy::
	msgbox VerdanturfTown_Mart_Text_XSpecialIsCrucial, MSGBOX_NPC
	end

VerdanturfTown_Mart_EventScript_ExpertF::
	msgbox VerdanturfTown_Mart_Text_NoStrategyGuidesForBattleTent, MSGBOX_NPC
	end

VerdanturfTown_Mart_EventScript_Lass::
	msgbox VerdanturfTown_Mart_Text_NestBallOnWeakenedPokemon, MSGBOX_NPC
	end

VerdanturfTown_Mart_Text_XSpecialIsCrucial:
	.string "For any POKéMON match, X SPECIAL\n"
	.string "is crucial.\p"
	.string "It jacks up the power of some moves\n"
	.string "even though it's only for one battle.$"

VerdanturfTown_Mart_Text_NoStrategyGuidesForBattleTent:
	.string "They don't seem to sell any winning\n"
	.string "strategy guides for the BATTLE TENT…\p"
	.string "It seems one must rely on one's\n"
	.string "own wits after all…$"

VerdanturfTown_Mart_Text_NestBallOnWeakenedPokemon:
	.string "The NEST BALL works better on\n"
	.string "weakened POKéMON.\p"
	.string "VERDANTURF is the only place you can\n"
	.string "buy it.$"