Route110_TrickHousePuzzle4_MapScripts::
	.byte 0

Route110_TrickHousePuzzle4_EventScript_Scroll::
	lockall
	goto_if_eq VAR_TRICK_HOUSE_PUZZLE_4_STATE, 0, Route110_TrickHousePuzzle4_EventScript_FoundScroll
	goto Route110_TrickHousePuzzle_EventScript_ReadScrollAgain
	end

Route110_TrickHousePuzzle4_EventScript_FoundScroll::
	setvar VAR_TRICK_HOUSE_PUZZLE_4_STATE, 1
	goto Route110_TrickHousePuzzle_EventScript_FoundScroll
	end

Route110_TrickHousePuzzle4_EventScript_Cora::
	trainerbattle_single TRAINER_CORA, Route110_TrickHousePuzzle4_Text_CoraIntro, Route110_TrickHousePuzzle4_Text_CoraDefeat
	msgbox Route110_TrickHousePuzzle4_Text_CoraPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle4_EventScript_Yuji::
	trainerbattle_single TRAINER_YUJI, Route110_TrickHousePuzzle4_Text_YujiIntro, Route110_TrickHousePuzzle4_Text_YujiDefeat
	msgbox Route110_TrickHousePuzzle4_Text_YujiPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle4_EventScript_Yuji2::
	trainerbattle_single TRAINER_YUJI2, Route110_TrickHousePuzzle4_Text_Yuji2Intro, Route110_TrickHousePuzzle4_Text_Yuji2Defeat
	msgbox Route110_TrickHousePuzzle4_Text_Yuji2PostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle4_EventScript_Paula::
	trainerbattle_single TRAINER_PAULA, Route110_TrickHousePuzzle4_Text_PaulaIntro, Route110_TrickHousePuzzle4_Text_PaulaDefeat
	msgbox Route110_TrickHousePuzzle4_Text_PaulaPostBattle, MSGBOX_AUTOCLOSE
	end

Route110_TrickHousePuzzle4_Text_WroteSecretCodeLockOpened:
	.string "{PLAYER} wrote down the secret code\n"
	.string "on the door.\p"
	.string "“TRICK MASTER is cool.”\n"
	.string "… … … … … … … …\p"
	.string "The lock clicked open!$"

Route110_TrickHousePuzzle4_Text_CoraIntro:
	.string "I'm Bertha, member of the Sinnoh Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle4_Text_CoraDefeat:
	.string "You beat my Ground type Pokemon...$"

Route110_TrickHousePuzzle4_Text_CoraPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle4_Text_YujiIntro:
	.string "I'm Lucian, member of the Sinnoh Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle4_Text_YujiDefeat:
	.string "You beat my Psychic type Pokemon...$"

Route110_TrickHousePuzzle4_Text_YujiPostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle4_Text_Yuji2Intro:
	.string "I'm Aaron, member of the Sinnoh Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle4_Text_Yuji2Defeat:
	.string "You beat my Bug type Pokemon...$"

Route110_TrickHousePuzzle4_Text_Yuji2PostBattle:
	.string "Good luck on your journey!$"

Route110_TrickHousePuzzle4_Text_PaulaIntro:
	.string "I'm Flint, member of the Sinnoh Elite\n"
	.string "4. Let's battle!$"

Route110_TrickHousePuzzle4_Text_PaulaDefeat:
	.string "You beat my Fire type Pokemon...$"

Route110_TrickHousePuzzle4_Text_PaulaPostBattle:
	.string "Good luck on your journey!$"

