Route110_TrickHousePuzzle8_MapScripts::
	.byte 0

Route110_TrickHousePuzzle8_EventScript_Scroll::
	lockall
	goto_if_eq VAR_TRICK_HOUSE_PUZZLE_8_STATE, 0, Route110_TrickHousePuzzle8_EventScript_FoundScroll
	goto Route110_TrickHousePuzzle_EventScript_ReadScrollAgain
	end

Route110_TrickHousePuzzle8_EventScript_FoundScroll::
	setvar VAR_TRICK_HOUSE_PUZZLE_8_STATE, 1
	goto Route110_TrickHousePuzzle_EventScript_FoundScroll
	end

Route110_TrickHousePuzzle8_EventScript_Vincent::
	trainerbattle_single TRAINER_VINCENT, Route110_TrickHousePuzzle8_Text_VincentIntro, Route110_TrickHousePuzzle8_Text_VincentDefeat
	msgbox Route110_TrickHousePuzzle8_Text_VincentPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle8_EventScript_Keira::
	trainerbattle_single TRAINER_KEIRA, Route110_TrickHousePuzzle8_Text_KeiraIntro, Route110_TrickHousePuzzle8_Text_KeiraDefeat
	msgbox Route110_TrickHousePuzzle8_Text_KeiraPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle8_EventScript_Keira2::
	trainerbattle_single TRAINER_KEIRA2, Route110_TrickHousePuzzle8_Text_Keira2Intro, Route110_TrickHousePuzzle8_Text_Keira2Defeat
	msgbox Route110_TrickHousePuzzle8_Text_Keira2PostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle8_EventScript_Leroy::
	trainerbattle_single TRAINER_LEROY, Route110_TrickHousePuzzle8_Text_LeroyIntro, Route110_TrickHousePuzzle8_Text_LeroyDefeat
	msgbox Route110_TrickHousePuzzle8_Text_LeroyPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle8_Text_WroteSecretCodeLockOpened::
	.string "{PLAYER} wrote down the secret code\n"
	.string "on the door.\p"
	.string "“TRICK MASTER I love.”\n"
	.string "… … … … … … … …\p"
	.string "The lock clicked open!$"

Route110_TrickHousePuzzle8_Text_VincentIntro:
	.string "I'm Poppy, member of the Paldea Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle8_Text_VincentDefeat:
	.string "You beat my Steel type Pokemon...$"

Route110_TrickHousePuzzle8_Text_VincentPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle8_Text_KeiraIntro:
	.string "I'm Rika, member of the Paldea Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle8_Text_KeiraDefeat:
	.string "You beat my Ground type Pokemon...$"

Route110_TrickHousePuzzle8_Text_KeiraPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle8_Text_Keira2Intro:
	.string "I'm Hassel, member of the Paldea Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle8_Text_Keira2Defeat:
	.string "You beat my Dragon type Pokemon...$"

Route110_TrickHousePuzzle8_Text_Keira2PostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle8_Text_LeroyIntro:
	.string "I'm Larry, member of the Paldea Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle8_Text_LeroyDefeat:
	.string "You beat my Normal type Pokemon...$"

Route110_TrickHousePuzzle8_Text_LeroyPostBattle:
	.string "Good luck on your journey!$"

