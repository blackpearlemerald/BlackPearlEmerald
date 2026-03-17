VictoryRoad_1F_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, VictoryRoad_1F_OnTransition
	.byte 0

VictoryRoad_1F_OnTransition:
	call_if_eq VAR_VICTORY_ROAD_1F_STATE, 1, VictoryRoad_1F_EventScript_SetEntranceWallyPos1
	call_if_eq VAR_VICTORY_ROAD_1F_STATE, 2, VictoryRoad_1F_EventScript_SetEntranceWallyPos2
	end

VictoryRoad_1F_EventScript_SetEntranceWallyPos1::
	setobjectxyperm LOCALID_VICTORY_ROAD_ENTRANCE_WALLY, 2, 24
	setobjectmovementtype LOCALID_VICTORY_ROAD_ENTRANCE_WALLY, MOVEMENT_TYPE_FACE_DOWN
	return

VictoryRoad_1F_EventScript_SetEntranceWallyPos2::
	setobjectxyperm LOCALID_VICTORY_ROAD_ENTRANCE_WALLY, 3, 24
	setobjectmovementtype LOCALID_VICTORY_ROAD_ENTRANCE_WALLY, MOVEMENT_TYPE_FACE_DOWN
	return

VictoryRoad_1F_EventScript_WallyBattleTrigger1::
	lockall
	setvar VAR_0x8008, 1
	addobject LOCALID_VICTORY_ROAD_ENTRANCE_WALLY
	applymovement LOCALID_VICTORY_ROAD_ENTRANCE_WALLY, VictoryRoad_1F_Movement_WallyApproachPlayer1
	waitmovement 0
	goto VictoryRoad_1F_EventScript_WallyEntranceBattle
	end

VictoryRoad_1F_EventScript_WallyBattleTrigger2::
	lockall
	setvar VAR_0x8008, 2
	addobject LOCALID_VICTORY_ROAD_ENTRANCE_WALLY
	applymovement LOCALID_VICTORY_ROAD_ENTRANCE_WALLY, VictoryRoad_1F_Movement_WallyApproachPlayer2
	waitmovement 0
	goto VictoryRoad_1F_EventScript_WallyEntranceBattle
	end

VictoryRoad_1F_EventScript_WallyEntranceBattle::
	applymovement LOCALID_PLAYER, Common_Movement_WalkInPlaceFasterDown
	waitmovement 0
	msgbox VictoryRoad_1F_Text_WallyNotGoingToLoseAnymore, MSGBOX_DEFAULT
	trainerbattle_no_intro TRAINER_WALLY_VR_1, VictoryRoad_1F_Text_WallyEntranceDefeat
	msgbox VictoryRoad_1F_Text_WallyPostEntranceBattle, MSGBOX_DEFAULT
	clearflag FLAG_HIDE_VICTORY_ROAD_ENTRANCE_WALLY
	copyobjectxytoperm LOCALID_VICTORY_ROAD_ENTRANCE_WALLY
	setflag FLAG_DEFEATED_WALLY_VICTORY_ROAD
	copyvar VAR_VICTORY_ROAD_1F_STATE, VAR_0x8008
	releaseall
	end

VictoryRoad_1F_Movement_WallyApproachPlayer1:
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_up
	step_end

VictoryRoad_1F_Movement_WallyApproachPlayer2:
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_up
	step_end

@ This Wally appears near the entrance once his battle is triggered and remains there until the Hall of Fame is entered
VictoryRoad_1F_EventScript_EntranceWally::
	msgbox VictoryRoad_1F_Text_WallyPostEntranceBattle, MSGBOX_NPC
	end

@ This Wally appears and remains at the exit after the Hall of Fame is entered
VictoryRoad_1F_EventScript_ExitWally::
	trainerbattle_single TRAINER_WALLY_VR_2, VictoryRoad_1F_Text_WallyIntro, VictoryRoad_1F_Text_WallyDefeat
	specialvar VAR_RESULT, ShouldTryRematchBattle
	goto_if_eq VAR_RESULT, TRUE, VictoryRoad_1F_EventScript_RematchWally
	msgbox VictoryRoad_1F_Text_WallyPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_EventScript_RematchWally::
	trainerbattle_rematch TRAINER_WALLY_VR_2, VictoryRoad_1F_Text_WallyIntro, VictoryRoad_1F_Text_WallyDefeat
	msgbox VictoryRoad_1F_Text_WallyPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_EventScript_Edgar::
	trainerbattle_single TRAINER_EDGAR, VictoryRoad_1F_Text_EdgarIntro, VictoryRoad_1F_Text_EdgarDefeat
	msgbox VictoryRoad_1F_Text_EdgarPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_EventScript_Albert::
	trainerbattle_single TRAINER_ALBERT, VictoryRoad_1F_Text_AlbertIntro, VictoryRoad_1F_Text_AlbertDefeat
	msgbox VictoryRoad_1F_Text_AlbertPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_EventScript_Hope::
	trainerbattle_single TRAINER_HOPE, VictoryRoad_1F_Text_HopeIntro, VictoryRoad_1F_Text_HopeDefeat
	msgbox VictoryRoad_1F_Text_HopePostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_EventScript_Quincy::
	trainerbattle_single TRAINER_QUINCY, VictoryRoad_1F_Text_QuincyIntro, VictoryRoad_1F_Text_QuincyDefeat
	msgbox VictoryRoad_1F_Text_QuincyPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_EventScript_Katelynn::
	trainerbattle_single TRAINER_KATELYNN, VictoryRoad_1F_Text_KatelynnIntro, VictoryRoad_1F_Text_KatelynnDefeat
	msgbox VictoryRoad_1F_Text_KatelynnPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_1F_Text_WallyNotGoingToLoseAnymore:
	.string "CYNTHIA: Hello, {PLAYER}...\p"
	.string "Have you been keeping well?\p"
	.string "I made it all the way here, and it's\n"
	.string "all thanks to you.\p"
	.string "You and your Pokemon have overcame\n"
	.string "many challenges.\p"
	.string "It means that you've triumphed over any\n"
	.string "personal weaknesses too.\p"
	.string "The power you've learned...\n"
	.string "I can feel it emanating from you.\p"
	.string "But that's enough talk.\n"
	.string "Let's get on with why you're here...\p"
	.string "If you really think you have what it\n"
	.string "takes to become the new Champion...\p"
	.string "Accept my final challenge!$"

VictoryRoad_1F_Text_WallyEntranceDefeat:
	.string "{PLAYER}, you are strong,\n"
	.string "just as I expected...$"

VictoryRoad_1F_Text_WallyPostEntranceBattle:
	.string "CYNTHIA: I couldn't beat you this time,\n"
	.string "But one of these days, {PLAYER},\l"
	.string "I will catch up to you…\p"
	.string "Your next steps forward will be\n"
	.string "especially challenging. Good luck!$"

VictoryRoad_1F_Text_WallyIntro:
	.string "CYNTHIA: Hello, {PLAYER}.\p"
	.string "I've gotten stronger since that last\n"
	.string "time. I wanted to show you, {PLAYER}!\p"
	.string "Okay… Here I come!$"

VictoryRoad_1F_Text_WallyDefeat:
	.string "Wow!\n"
	.string "{PLAYER}, you are strong, after all!$"

VictoryRoad_1F_Text_WallyPostBattle:
	.string "CYNTHIA: I couldn't beat you this time,\n"
	.string "But one of these days, {PLAYER},\l"
	.string "I will catch up to you…\p"
	.string "Your next steps forward will be\n"
	.string "especially challenging. Good luck!$"

VictoryRoad_1F_Text_EdgarIntro:
	.string "I've made it this far a couple times,\n"
	.string "but the last stretch is so long…$"

VictoryRoad_1F_Text_EdgarDefeat:
	.string "My dream ends here again…$"

VictoryRoad_1F_Text_EdgarPostBattle:
	.string "You've made it this far. Keep the\n"
	.string "momentum going and become the\l"
	.string "CHAMPION! If anyone can, it's you!$"

VictoryRoad_1F_Text_AlbertIntro:
	.string "I really look forward to having\n"
	.string "serious battles with strong Trainers!\p"
	.string "I mean, come on! The Trainers who\n"
	.string "make it here are Trainers who desire\l"
	.string "victory with every fiber of their being!\p"
	.string "If I battle with people like that,\n"
	.string "not only will I get stronger,\l"
	.string "my Pokemon will too!\p"
	.string "OK! Brace yourself!$"

VictoryRoad_1F_Text_AlbertDefeat:
	.string "I'm upset I couldn't win!$"

VictoryRoad_1F_Text_AlbertPostBattle:
	.string "I'm sad I lost here…\p"
	.string "But you know what?\n"
	.string "More than that, I'm happy for you!$"

VictoryRoad_1F_Text_HopeIntro:
	.string "I don't know why you have come here.\p"
	.string "Anyway, I have to warn you that this\n"
	.string "is not a place for kids like you.\p"
	.string "You have a certain look...\p"
	.string "It reminds me of a kid who stood in\n"
	.string "front of me many years ago...\p"
	.string "...\p"
	.string "I will not repeat failure from\n"
	.string "the past!$"

VictoryRoad_1F_Text_HopeDefeat:
	.string "Truly, impressive…$"

VictoryRoad_1F_Text_HopePostBattle:
	.string "How can a kid like you manage to\n"
	.string "destroy my dream once again?$"

VictoryRoad_1F_Text_QuincyIntro:
	.string "What is the VICTORY ROAD?\n"
	.string "I'll tell you if you win!$"

VictoryRoad_1F_Text_QuincyDefeat:
	.string "Okay!\n"
	.string "Well done!$"

VictoryRoad_1F_Text_QuincyPostBattle:
	.string "Getting through here safely--that's\n"
	.string "the final test for any TRAINER aiming\l"
	.string "to become the POKéMON CHAMPION.\p"
	.string "That's why it's called the VICTORY\n"
	.string "ROAD.$"

VictoryRoad_1F_Text_KatelynnIntro:
	.string "It is up to you now, {PLAYER}\p"
	.string "AI Turo switching to sleep mode...\p"
	.string "Activating offensive protocols...\p"
	.string "Please, defeat me...$"

VictoryRoad_1F_Text_KatelynnDefeat:
	.string "I-impossible!$"

VictoryRoad_1F_Text_KatelynnPostBattle:
	.string "...Proceed$"
