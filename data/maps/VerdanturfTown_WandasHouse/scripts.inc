VerdanturfTown_WandasHouse_MapScripts::
	.byte 0

VerdanturfTown_WandasHouse_EventScript_Wally::
	lock
	faceplayer
	goto_if_set FLAG_WALLY_SPEECH, VerdanturfTown_WandasHouse_EventScript_WallyShortSpeech
	msgbox VerdanturfTown_WandasHouse_Text_StrongerSpeech, MSGBOX_DEFAULT
	setflag FLAG_WALLY_SPEECH
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallyShortSpeech::
	msgbox VerdanturfTown_WandasHouse_Text_StrongerSpeechShort, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysUncle::
	lock
	faceplayer
	goto_if_set FLAG_DEFEATED_WALLY_VICTORY_ROAD, VerdanturfTown_WandasHouse_EventScript_WallysUncleEverGrande
	goto_if_set FLAG_DEFEATED_LAVARIDGE_GYM, VerdanturfTown_WandasHouse_EventScript_WallysUncleSlippedOff
	msgbox VerdanturfTown_WandasHouse_Text_WallysNextDoor, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysUncleSlippedOff::
	msgbox VerdanturfTown_WandasHouse_Text_WallySlippedOff, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysUncleEverGrande::
	msgbox VerdanturfTown_WandasHouse_Text_WallyGoneThatFar, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WandasBoyfriend::
	msgbox VerdanturfTown_WandasHouse_Text_CanSeeGirlfriendEveryDay, MSGBOX_DEFAULT
	goto_if_unset FLAG_ON_THE_HOUSE, VerdanturfTown_WandasHouse_EventScript_OnTheHouse
	release
	end

VerdanturfTown_WandasHouse_EventScript_OnTheHouse::
	msgbox VerdanturfTown_WandasHouse_Text_OnTheHouse, MSGBOX_DEFAULT
	giveitem ITEM_PEARL
	setflag FLAG_ON_THE_HOUSE
	release
	end

VerdanturfTown_WandasHouse_EventScript_Wanda::
	lock
	faceplayer
	goto_if_set FLAG_DEFEATED_LAVARIDGE_GYM, VerdanturfTown_WandasHouse_EventScript_WandaDontWorry
	goto_if_set FLAG_DEFEATED_WALLY_MAUVILLE, VerdanturfTown_WandasHouse_EventScript_MeetWanda
	msgbox VerdanturfTown_WandasHouse_Text_DontWorryAboutWally, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_MeetWanda::
	msgbox VerdanturfTown_WandasHouse_Text_MeetWanda, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WandaDontWorry::
	msgbox VerdanturfTown_WandasHouse_Text_DontWorryAboutWally, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysAunt::
	lock
	faceplayer
	goto_if_set FLAG_DEFEATED_WALLY_VICTORY_ROAD, VerdanturfTown_WandasHouse_EventScript_WallysAuntEverGrande
	goto_if_set FLAG_DEFEATED_LAVARIDGE_GYM, VerdanturfTown_WandasHouse_EventScript_WallysAuntAnythingHappened
	goto_if_set FLAG_RUSTURF_TUNNEL_OPENED, VerdanturfTown_WandasHouse_EventScript_WallysAuntTunnelOpen
	msgbox VerdanturfTown_WandasHouse_Text_DaughtersBoyfriendDriven, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysAuntTunnelOpen::
	msgbox VerdanturfTown_WandasHouse_Text_DaughtersBoyfriendWasDigging, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysAuntAnythingHappened::
	msgbox VerdanturfTown_WandasHouse_Text_IfAnythingHappenedToWally, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_EventScript_WallysAuntEverGrande::
	msgbox VerdanturfTown_WandasHouse_Text_WallyWasInEverGrande, MSGBOX_DEFAULT
	release
	end

VerdanturfTown_WandasHouse_Text_StrongerSpeech:
	.string "WALLY: I lost to you, {PLAYER}, but I'm\n"
	.string "not feeling down anymore.\p"
	.string "Because I have a new purpose in life.\n"
	.string "Together with my RALTS, I'm going\l"
	.string "to challenge POKéMON GYMS and become\l"
	.string "a great TRAINER.\p"
	.string "Please watch me, {PLAYER}.\n"
	.string "I'm going to be stronger than you.\p"
	.string "When I do, I'm going to challenge you\n"
	.string "to another battle.$"

VerdanturfTown_WandasHouse_Text_StrongerSpeechShort:
	.string "WALLY: Please watch me, {PLAYER}.\n"
	.string "I'm going to get stronger than you.\p"
	.string "When I do, I'm going to challenge you\n"
	.string "to another battle.$"

VerdanturfTown_WandasHouse_Text_WallysNextDoor:
	.string "UNCLE: Oh! {PLAYER}{KUN}!\n"
	.string "WALLY's next door.\p"
	.string "But, boy, there's something I have to\n"
	.string "tell you.\p"
	.string "This natural environment is doing\n"
	.string "wonders for WALLY's health.\p"
	.string "Maybe it's not just the environment.\n"
	.string "It could be POKéMON that are giving\l"
	.string "the boy hope.$"

VerdanturfTown_WandasHouse_Text_WallySlippedOff:
	.string "WALLY's gone away…\n"
	.string "He slipped off on his own…$"

VerdanturfTown_WandasHouse_Text_WallyGoneThatFar:
	.string "UNCLE: Is that right?\n"
	.string "WALLY's gone away that far all by\l"
	.string "himself…\p"
	.string "Well, I have to give him credit--he is\n"
	.string "my little brother's son.$"

VerdanturfTown_WandasHouse_Text_MeetWanda:
	.string "WANDA: You are?\n"
	.string "Oh, right, I get it!\p"
	.string "You're the {PLAYER} who WALLY was\n"
	.string "telling me about.\p"
	.string "I'm WALLY's cousin.\n"
	.string "Glad to meet you!\p"
	.string "I think WALLY's become a lot more lively\n"
	.string "and healthy since he came here.$"

VerdanturfTown_WandasHouse_Text_DontWorryAboutWally:
	.string "WANDA: Don't worry about WALLY.\n"
	.string "He'll be just fine.\p"
	.string "I know my little cousin, and he has\n"
	.string "POKéMON with him, too.$"

VerdanturfTown_WandasHouse_Text_CanSeeGirlfriendEveryDay:
	.string "Due to my sucessful experiements,\n"
	.string "these Pokemon can talk like humans!\p"
	.string "They can even teach your Pokemon\n"
	.string "special moves!$"

VerdanturfTown_WandasHouse_Text_OnTheHouse:
	.string "Dusclops works for free, but Ditto\n"
	.string "demands payment...\p"
	.string "Here… this Pearl is on the house!$"

VerdanturfTown_WandasHouse_Text_DaughtersBoyfriendDriven:
	.string "My daughter's boyfriend is a very\n"
	.string "driven and passionate sort of person.\p"
	.string "He's been digging a tunnel nonstop\n"
	.string "just so he can see my daughter.\p"
	.string "My daughter's a little concerned,\n"
	.string "so she goes out to the tunnel a lot.$"

VerdanturfTown_WandasHouse_Text_DaughtersBoyfriendWasDigging:
	.string "It's amazing. My daughter's boyfriend\n"
	.string "was digging the tunnel by hand!\p"
	.string "It's so incredible!$"

VerdanturfTown_WandasHouse_Text_IfAnythingHappenedToWally:
	.string "If anything were to happen to WALLY,\n"
	.string "I would never be able to look his\l"
	.string "parents in PETALBURG in the eye…$"

VerdanturfTown_WandasHouse_Text_WallyWasInEverGrande:
	.string "WALLY was in EVER GRANDE?\p"
	.string "His parents in PETALBURG would be\n"
	.string "astonished to hear that!$"

General_EggTutor_EventScript::
	lockall
	setflag FLAG_EGG_MOVE_TUTOR
	applymovement LOCALID_MOVE_RELEARNER, Common_Movement_FacePlayer
	waitmovement 0
	msgbox General_EggTutor_Text_ImTheEggTutor, MSGBOX_DEFAULT
	goto General_EggTutor_EventScript_AskTeachMove
	clearflag FLAG_EGG_MOVE_TUTOR
	end


General_EggTutor_EventScript_AskTeachMove::
	msgbox General_EggTutor_Text_WantMeToTeachMove, MSGBOX_YESNO
	switch VAR_RESULT
	case NO, General_EggTutor_EventScript_ComeBackWithHeartScale
	checkitem ITEM_PEARL
	goto_if_eq VAR_RESULT, FALSE, General_EggTutor_EventScript_ComeBackWithHeartScale
	goto General_EggTutor_EventScript_ChooseMon
	clearflag FLAG_EGG_MOVE_TUTOR
	end

General_EggTutor_EventScript_ChooseMon::
	msgbox General_EggTutor_Text_TutorWhichMon, MSGBOX_DEFAULT
	special ChooseMonForMoveRelearner
	goto_if_eq VAR_0x8004, PARTY_NOTHING_CHOSEN, General_EggTutor_EventScript_ComeBackWithHeartScale
	special IsSelectedMonEgg
	goto_if_eq VAR_RESULT, TRUE, General_EggTutor_EventScript_CantTeachEgg
	goto_if_eq VAR_0x8005, 0, General_EggTutor_EventScript_NoMoveToTeachMon
	goto General_EggTutor_EventScript_ChooseMove
	end

General_EggTutor_EventScript_ChooseMove::
	msgbox General_EggTutor_Text_TeachWhichMove, MSGBOX_DEFAULT
	special TeachMoveRelearnerMove
	goto_if_eq VAR_0x8004, 0, General_EggTutor_EventScript_ChooseMon
	removeitem ITEM_PEARL
	msgbox General_EggTutor_Text_ThereYouGo, MSGBOX_DEFAULT
	goto General_EggTutor_EventScript_ComeBackWithHeartScale
	end

General_EggTutor_EventScript_NoMoveToTeachMon::
	msgbox General_EggTutor_Text_DontHaveMoveToTeachPokemon, MSGBOX_DEFAULT
	goto General_EggTutor_EventScript_ChooseMon
	end

General_EggTutor_EventScript_CantTeachEgg::
	msgbox General_EggTutor_Text_CantTeachEgg, MSGBOX_DEFAULT
	goto General_EggTutor_EventScript_ChooseMon
	end

General_EggTutor_EventScript_ComeBackWithHeartScale::
	msgbox General_EggTutor_Text_ComeBack, MSGBOX_DEFAULT
	clearflag FLAG_EGG_MOVE_TUTOR
	releaseall
	end

General_EggTutor_Text_ImTheEggTutor:
	.string "Hi! I'm the EGG MOVE TUTOR!\p"
	.string "I can teach your Pokémon any Egg Moves\n"
	.string "they could possibly learn!\p"
	.string "...For a price!$"

General_EggTutor_Text_WantMeToTeachMove:
	.string "Would you like me to teach one of your\n"
	.string "Pokémon an Egg Move, for one PEARL?$"

General_EggTutor_Text_TutorWhichMon:
	.string "Which Pokémon?$"

General_EggTutor_Text_TeachWhichMove:
	.string "Which move should I teach?$"

General_EggTutor_Text_DontHaveMoveToTeachPokemon:
	.string "That Pokémon doesn't have any Egg\n"
	.string "Moves.$"

General_EggTutor_Text_ThereYouGo:
	.string "{PLAYER} handed over one PEARL\n"
	.string "in exchange.\p"
	.string "There you go!$"

General_EggTutor_Text_ComeBack:
	.string "Come back with a Pearl if you want\n"
	.string "your Pokemon to learn an Egg Move.$"

General_EggTutor_Text_CantTeachEgg:
	.string "Just because I'm an Egg Move tutor\n"
	.string "doesn't mean I can teach moves to an\l"
	.string "Egg!$"