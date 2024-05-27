VerdanturfTown_House_MapScripts::
	.byte 0

VerdanturfTown_House_EventScript_Woman1::
	msgbox VerdanturfTown_House_Text_TrainersGatherAtPokemonLeague, MSGBOX_NPC
	end

VerdanturfTown_House_EventScript_Woman2::
	goto_if_unset FLAG_ROTOM_CATALOG, VerdanturfTown_House_EventScript_Woman2_GiveCatalog
	msgbox VerdanturfTown_House_Text_Catalog2, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_House_EventScript_Woman2_GiveCatalog::
	msgbox VerdanturfTown_House_Text_Catalog, MSGBOX_DEFAULT
	giveitem ITEM_ROTOM_CATALOG
	setflag FLAG_ROTOM_CATALOG
	release
	end

VerdanturfTown_House_Text_TrainersGatherAtPokemonLeague:
	.string "Far away, deep in EVER GRANDE CITY,\n"
	.string "is the POKéMON LEAGUE.\p"
	.string "The TRAINERS who gather there are\n"
	.string "all frighteningly well skilled.$"

VerdanturfTown_House_Text_DefeatEliteFourInARow:
	.string "In the POKéMON LEAGUE, I think the\n"
	.string "rules say that you have to battle the\l"
	.string "ELITE FOUR all in a row.\p"
	.string "If you lose to any of them, you have\n"
	.string "to begin your challenge again from the\l"
	.string "first one.$"

VerdanturfTown_House_Text_Catalog:
	.string "I love reading magazines and catalogs!\p"
	.string "I did get a strange one in the mail\n"
	.string "the other day...\p"
	.string "Here! Maybe you would like it!$"

VerdanturfTown_House_Text_Catalog2:
	.string "Have you taken a look at that catalog\n"
	.string "I gave you?\p"
	.string "I ordered it from a guy in Fallarbor,\n"
	.string "but I haven't heard from him in a while…$"