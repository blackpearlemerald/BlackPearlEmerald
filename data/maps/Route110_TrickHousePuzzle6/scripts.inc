Route110_TrickHousePuzzle6_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, Route110_TrickHousePuzzle6_OnTransition
	map_script MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE, Route110_TrickHousePuzzle6_OnWarp
	.byte 0

Route110_TrickHousePuzzle6_OnTransition:
	special RotatingGate_InitPuzzle
	end

Route110_TrickHousePuzzle6_OnWarp:
	map_script_2 VAR_TEMP_0, VAR_TEMP_0, Route110_TrickHousePuzzle6_EventScript_InitPuzzle
	.2byte 0

@ NOTE: This rotating gate puzzle makes use of VAR_TEMP_0 - VAR_TEMP_5
Route110_TrickHousePuzzle6_EventScript_InitPuzzle::
	special RotatingGate_InitPuzzleAndGraphics
	end

Route110_TrickHousePuzzle6_EventScript_Scroll::
	lockall
	goto_if_eq VAR_TRICK_HOUSE_PUZZLE_6_STATE, 0, Route110_TrickHousePuzzle6_EventScript_FoundScroll
	goto Route110_TrickHousePuzzle_EventScript_ReadScrollAgain
	end

Route110_TrickHousePuzzle6_EventScript_FoundScroll::
	setvar VAR_TRICK_HOUSE_PUZZLE_6_STATE, 1
	goto Route110_TrickHousePuzzle_EventScript_FoundScroll
	end

Route110_TrickHousePuzzle6_EventScript_Sophia::
	trainerbattle_single TRAINER_SOPHIA, Route110_TrickHousePuzzle6_Text_SophiaIntro, Route110_TrickHousePuzzle6_Text_SophiaDefeat
	msgbox Route110_TrickHousePuzzle6_Text_SophiaPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle6_EventScript_Benny::
	trainerbattle_single TRAINER_BENNY, Route110_TrickHousePuzzle6_Text_BennyIntro, Route110_TrickHousePuzzle6_Text_BennyDefeat
	msgbox Route110_TrickHousePuzzle6_Text_BennyPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle6_EventScript_Benny2::
	trainerbattle_single TRAINER_BENNY2, Route110_TrickHousePuzzle6_Text_Benny2Intro, Route110_TrickHousePuzzle6_Text_Benny2Defeat
	msgbox Route110_TrickHousePuzzle6_Text_Benny2PostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle6_EventScript_Sebastian::
	trainerbattle_single TRAINER_SEBASTIAN, Route110_TrickHousePuzzle6_Text_SebastianIntro, Route110_TrickHousePuzzle6_Text_SebastianDefeat
	msgbox Route110_TrickHousePuzzle6_Text_SebastianPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle6_Text_WroteSecretCodeLockOpened:
	.string "{PLAYER} wrote down the secret code\n"
	.string "on the door.\p"
	.string "“TRICK MASTER is my life.”\n"
	.string "… … … … … … … …\p"
	.string "The lock clicked open!$"

Route110_TrickHousePuzzle6_Text_SophiaIntro:
	.string "I'm Malva, member of the Kalos Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle6_Text_SophiaDefeat:
	.string "You beat my Fire type Pokemon...$"

Route110_TrickHousePuzzle6_Text_SophiaPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle6_Text_BennyIntro:
	.string "I'm Drasna, member of the Kalos Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle6_Text_BennyDefeat:
	.string "You beat my Dragon type Pokemon...$"

Route110_TrickHousePuzzle6_Text_BennyPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle6_Text_Benny2Intro:
	.string "I'm Siebold, member of the Kalos\n"
	.string "Elite 4. Let's battle!$"

Route110_TrickHousePuzzle6_Text_Benny2Defeat:
	.string "You beat my Water type Pokemon...$"

Route110_TrickHousePuzzle6_Text_Benny2PostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle6_Text_SebastianIntro:
	.string "I'm Wikstrom, member of the Kalos\n"
	.string "Elite 4. Let's battle!$"

Route110_TrickHousePuzzle6_Text_SebastianDefeat:
	.string "You beat my Steel type Pokemon...$"

Route110_TrickHousePuzzle6_Text_SebastianPostBattle:
	.string "Good luck on your journey!$"

