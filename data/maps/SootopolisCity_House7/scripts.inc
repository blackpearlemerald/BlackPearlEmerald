SootopolisCity_House7_MapScripts::
	.byte 0

SootopolisCity_House7_EventScript_OldMan::
	msgbox SootopolisCity_House7_Text_CityFromEruptedVolcano, MSGBOX_NPC
	end

SootopolisCity_House7_EventScript_PokefanF::
	msgbox SootopolisCity_House7_Text_CaveMadeToKeepSomething, MSGBOX_NPC
	end

SootopolisCity_House7_Text_CityFromEruptedVolcano:
	.string "An underwater volcano erupted and\n"
	.string "forced itself up from the depths.\p"
	.string "Its crater emerged from the sea and\n"
	.string "became filled with rainwater.\p"
	.string "That's how SOOTOPOLIS CITY came into\n"
	.string "being.$"

SootopolisCity_House7_Text_CaveMadeToKeepSomething:
	.string "I've been waiting for a worthy trainer.\p"
	.string "This pokemon beside me has been handed\n"
	.string "down for generations.\p"
	.string "It's always been referred to as, NULL.$"

Legendary_EventScript_BattleNull::
	setwildbattle SPECIES_TYPE_NULL, 30
	waitse
	playmoncry SPECIES_TYPE_NULL, CRY_MODE_ENCOUNTER
	delay 40
	waitmoncry
	dowildbattle
	setvar VAR_0x8004, SPECIES_TYPE_NULL
	special TryRecordPreE4LegendaryCatch
	fadescreenswapbuffers FADE_TO_BLACK
	removeobject(3)
	fadescreenswapbuffers FADE_FROM_BLACK
	release
	end