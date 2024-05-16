VictoryRoad_B1F_MapScripts::
	.byte 0

VictoryRoad_B1F_EventScript_Samuel::
	trainerbattle_single TRAINER_SAMUEL, VictoryRoad_B1F_Text_SamuelIntro, VictoryRoad_B1F_Text_SamuelDefeat
	msgbox VictoryRoad_B1F_Text_SamuelPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B1F_EventScript_Shannon::
	trainerbattle_single TRAINER_SHANNON, VictoryRoad_B1F_Text_ShannonIntro, VictoryRoad_B1F_Text_ShannonDefeat
	msgbox VictoryRoad_B1F_Text_ShannonPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B1F_EventScript_Michelle::
	trainerbattle_single TRAINER_MICHELLE, VictoryRoad_B1F_Text_MichelleIntro, VictoryRoad_B1F_Text_MichelleDefeat
	msgbox VictoryRoad_B1F_Text_MichellePostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B1F_EventScript_Mitchell::
	trainerbattle_single TRAINER_MITCHELL, VictoryRoad_B1F_Text_MitchellIntro, VictoryRoad_B1F_Text_MitchellDefeat
	msgbox VictoryRoad_B1F_Text_MitchellPostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B1F_EventScript_Halle::
	trainerbattle_single TRAINER_HALLE, VictoryRoad_B1F_Text_HalleIntro, VictoryRoad_B1F_Text_HalleDefeat
	msgbox VictoryRoad_B1F_Text_HallePostBattle, MSGBOX_AUTOCLOSE
	end

VictoryRoad_B1F_Text_SamuelIntro:
	.string "I will create the future I desire!\p"
	.string "I shall sweep you before me!$"

VictoryRoad_B1F_Text_SamuelDefeat:
	.string "Everything's ruined…$"

VictoryRoad_B1F_Text_SamuelPostBattle:
	.string "Your ideals... Your feelings...\n"
	.string "They were stronger than mine, it seems.$"

VictoryRoad_B1F_Text_ShannonIntro:
	.string "To win your way through the POKéMON\n"
	.string "LEAGUE, you need the trust of your\l"
	.string "POKéMON.$"

VictoryRoad_B1F_Text_ShannonDefeat:
	.string "Your relationship is based on\n"
	.string "solid trust.$"

VictoryRoad_B1F_Text_ShannonPostBattle:
	.string "By being together all the time, trust\n"
	.string "grows between POKéMON and TRAINERS.$"

VictoryRoad_B1F_Text_MichelleIntro:
	.string "This isn't the goal. It's only a place\n"
	.string "on the way to the POKéMON LEAGUE.$"

VictoryRoad_B1F_Text_MichelleDefeat:
	.string "That's the way!$"

VictoryRoad_B1F_Text_MichellePostBattle:
	.string "You'll do fine, for sure!\n"
	.string "Your POKéMON are all eager to go!$"

VictoryRoad_B1F_Text_MitchellIntro:
	.string "I will do what I must to put your\n"
	.string "worries to rest...\p"
	.string "By demonstrating my strength\n"
	.string "in battle!$"

VictoryRoad_B1F_Text_MitchellDefeat:
	.string "You are strong...$"

VictoryRoad_B1F_Text_MitchellPostBattle:
	.string "You should carry on...$"

VictoryRoad_B1F_Text_HalleIntro:
	.string "Why should I run and hide from\n"
	.string "the world and wait quietly?\p"
	.string "By freeing ourselves, our world\n"
	.string "can be made complete.\p"
	.string "That is my justice!\n"
	.string "No one can interfere!$"

VictoryRoad_B1F_Text_HalleDefeat:
	.string "This can't be!$"

VictoryRoad_B1F_Text_HallePostBattle:
	.string "Don't think you have what it\n"
	.string "takes to become Champion,\l"
	.string "just because you beat me...$"

