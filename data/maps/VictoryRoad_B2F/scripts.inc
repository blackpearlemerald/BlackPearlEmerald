VictoryRoad_B2F_MapScripts::
	.byte 0

VictoryRoad_B2F_EventScript_Vito::
	trainerbattle_single TRAINER_VITO, VictoryRoad_B2F_Text_VitoIntro, VictoryRoad_B2F_Text_VitoDefeat
	msgbox VictoryRoad_B2F_Text_VitoPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B2F_EventScript_Owen::
	trainerbattle_single TRAINER_OWEN, VictoryRoad_B2F_Text_OwenIntro, VictoryRoad_B2F_Text_OwenDefeat
	msgbox VictoryRoad_B2F_Text_OwenPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B2F_EventScript_Caroline::
	trainerbattle_single TRAINER_CAROLINE, VictoryRoad_B2F_Text_CarolineIntro, VictoryRoad_B2F_Text_CarolineDefeat
	msgbox VictoryRoad_B2F_Text_CarolinePostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B2F_EventScript_Julie::
	trainerbattle_single TRAINER_JULIE, VictoryRoad_B2F_Text_JulieIntro, VictoryRoad_B2F_Text_JulieDefeat
	msgbox VictoryRoad_B2F_Text_JuliePostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B2F_EventScript_Felix::
	trainerbattle_single TRAINER_FELIX, VictoryRoad_B2F_Text_FelixIntro, VictoryRoad_B2F_Text_FelixDefeat
	msgbox VictoryRoad_B2F_Text_FelixPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B2F_EventScript_Dianne::
	trainerbattle_single TRAINER_DIANNE, VictoryRoad_B2F_Text_DianneIntro, VictoryRoad_B2F_Text_DianneDefeat
	msgbox VictoryRoad_B2F_Text_DiannePostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B2F_Text_VitoIntro:
	.string ".......................\n"
	.string ".......................$"

VictoryRoad_B2F_Text_VitoDefeat:
	.string "...!$"

VictoryRoad_B2F_Text_VitoPostBattle:
	.string "...$"

VictoryRoad_B2F_Text_OwenIntro:
	.string "I've been looking forward to\n"
	.string "seeing you, {PLAYER}.\p"
	.string "I've assembled a teams that will\n"
	.string "beat any Pokemon type!\p"
	.string "I am a CHAMPION!\p"
	.string "Or as I prefer to call it...\p"
	.string "One of the most powerful trainers\n"
	.string "in the world!$"

VictoryRoad_B2F_Text_OwenDefeat:
	.string "Why did I lose?$"

VictoryRoad_B2F_Text_OwenPostBattle:
	.string "Although I don't like to admit it,\n"
	.string "you've won.$"

VictoryRoad_B2F_Text_CarolineIntro:
	.string "Oh, wow, {PLAYER}.\n"
	.string "I'm amazed you knoew where to find me\p"
	.string "You should have a very good idea\n"
	.string "about how good I am.\p"
	.string "Okay, {PLAYER}, If you're going to mount\n"
	.string "a serious challenge, expect the worst!$"

VictoryRoad_B2F_Text_CarolineDefeat:
	.string "I had no idea you'd become so strong...$"

VictoryRoad_B2F_Text_CarolinePostBattle:
	.string "I've always thought that you would\n"
	.string "eventually become the CHAMPION$"

VictoryRoad_B2F_Text_JulieIntro:
	.string "You shouldn't get complacent just\n"
	.string "because you have a lot of GYM BADGES.\p"
	.string "There's always going to be someone\n"
	.string "who's better than you!$"

VictoryRoad_B2F_Text_JulieDefeat:
	.string "You're better than me!$"

VictoryRoad_B2F_Text_JuliePostBattle:
	.string "Gaze on your collected BADGES and\n"
	.string "remember the TRAINERS you've faced.$"

VictoryRoad_B2F_Text_FelixIntro:
	.string "I can't wait to see the look on your\n"
	.string "face when you've lost all hope!\p"
	.string "I won't allow anyone to beat me!\n"
	.string "No matter who does what!$"

VictoryRoad_B2F_Text_FelixDefeat:
	.string "My calculations... No!\n"
	.string "I should not have lost!$"

VictoryRoad_B2F_Text_FelixPostBattle:
	.string "I AM PERFECTION!\p"
	.string "Since I couldn't become the hero,\n"
	.string "I have prepared the next Trainer!$"

VictoryRoad_B2F_Text_DianneIntro:
	.string "The elite among the elite gather in\n"
	.string "this cave.\p"
	.string "How are you finding it?$"

VictoryRoad_B2F_Text_DianneDefeat:
	.string "Not rattled in the least bit!$"

VictoryRoad_B2F_Text_DiannePostBattle:
	.string "You do have guts! I like that!\n"
	.string "Keep it going!$"

