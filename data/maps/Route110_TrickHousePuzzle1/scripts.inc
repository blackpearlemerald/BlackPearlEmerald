Route110_TrickHousePuzzle1_MapScripts::
	map_script MAP_SCRIPT_ON_LOAD, Route110_TrickHousePuzzle1_OnLoad
	.byte 0

Route110_TrickHousePuzzle1_OnLoad:
	goto_if_eq VAR_TRICK_HOUSE_PUZZLE_1_STATE, 2, Route110_TrickHousePuzzle1_EventScript_OpenDoor
	end

Route110_TrickHousePuzzle1_EventScript_OpenDoor::
	setmetatile 13, 1, METATILE_TrickHousePuzzle_Stairs_Down, FALSE
	end

Route110_TrickHousePuzzle1_EventScript_Scroll::
	lockall
	goto_if_eq VAR_TRICK_HOUSE_PUZZLE_1_STATE, 0, Route110_TrickHousePuzzle1_EventScript_FoundScroll
	goto Route110_TrickHousePuzzle_EventScript_ReadScrollAgain
	end

Route110_TrickHousePuzzle1_EventScript_FoundScroll::
	setvar VAR_TRICK_HOUSE_PUZZLE_1_STATE, 1
	goto Route110_TrickHousePuzzle_EventScript_FoundScroll
	end

Route110_TrickHousePuzzle1_EventScript_Sally::
	trainerbattle_single TRAINER_SALLY, Route110_TrickHousePuzzle1_Text_SallyIntro, Route110_TrickHousePuzzle1_Text_SallyDefeat
	msgbox Route110_TrickHousePuzzle1_Text_SallyPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle1_EventScript_Eddie::
	trainerbattle_single TRAINER_EDDIE, Route110_TrickHousePuzzle1_Text_EddieIntro, Route110_TrickHousePuzzle1_Text_EddieDefeat
	msgbox Route110_TrickHousePuzzle1_Text_EddiePostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle1_EventScript_Eddie2::
	trainerbattle_single TRAINER_EDDIE2, Route110_TrickHousePuzzle1_Text_Eddie2Intro, Route110_TrickHousePuzzle1_Text_Eddie2Defeat
	msgbox Route110_TrickHousePuzzle1_Text_Eddie2PostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle1_EventScript_Robin::
	trainerbattle_single TRAINER_ROBIN, Route110_TrickHousePuzzle1_Text_RobinIntro, Route110_TrickHousePuzzle1_Text_RobinDefeat
	msgbox Route110_TrickHousePuzzle1_Text_RobinPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle1_Text_WroteSecretCodeLockOpened::
	.string "{PLAYER} wrote down the secret code\n"
	.string "on the door.\p"
	.string "“TRICK MASTER is fabulous.”\n"
	.string "… … … … … … … …\p"
	.string "The lock clicked open!$"

Route110_TrickHousePuzzle1_Text_SallyIntro:
	.string "I'm Lorelei, member of the Kanto\n"
	.string "Elite 4. Let's battle!$"

Route110_TrickHousePuzzle1_Text_SallyDefeat:
	.string "You beat my Ice type Pokemon...$"

Route110_TrickHousePuzzle1_Text_SallyPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle1_Text_EddieIntro:
	.string "I'm Agatha, member of the Kanto\n"
	.string "Elite 4. Let's battle!$"

Route110_TrickHousePuzzle1_Text_EddieDefeat:
	.string "You beat my Ghost type Pokemon...$"

Route110_TrickHousePuzzle1_Text_EddiePostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle1_Text_Eddie2Intro:
	.string "I'm Lance, member of the Kanto\n"
	.string "Elite 4. Let's battle!$"

Route110_TrickHousePuzzle1_Text_Eddie2Defeat:
	.string "You beat my Dragon type Pokemon...$"

Route110_TrickHousePuzzle1_Text_Eddie2PostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle1_Text_RobinIntro:
	.string "I'm Bruno, member of the Kanto\n"
	.string "Elite 4. Let's battle!$"

Route110_TrickHousePuzzle1_Text_RobinDefeat:
	.string "You beat my Fighting type Pokemon...$"

Route110_TrickHousePuzzle1_Text_RobinPostBattle:
	.string "Good luck on your journey!$"

