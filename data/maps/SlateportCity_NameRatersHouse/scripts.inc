SlateportCity_NameRatersHouse_MapScripts::
	.byte 0

SlateportCity_NameRatersHouse_EventScript_NameRater::
	lock
	faceplayer
	msgbox SlateportCity_NameRatersHouse_Text_PleasedToRateMonNickname, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, YES, SlateportCity_NameRatersHouse_EventScript_ChooseMonToRate
	goto_if_eq VAR_RESULT, NO, SlateportCity_NameRatersHouse_EventScript_DeclineNameRate
	end

SlateportCity_NameRatersHouse_EventScript_ChooseMonToRate::
	msgbox SlateportCity_NameRatersHouse_Text_CritiqueWhichMonNickname, MSGBOX_DEFAULT
	chooseboxmon
	waitstate
	goto_if_ne VAR_0x8004, PARTY_NOTHING_CHOSEN, SlateportCity_NameRatersHouse_EventScript_RateMonNickname
	goto_if_eq VAR_0x8004, PARTY_NOTHING_CHOSEN, SlateportCity_NameRatersHouse_EventScript_DeclineNameRate
	end

SlateportCity_NameRatersHouse_EventScript_DeclineNameRate::
	msgbox SlateportCity_NameRatersHouse_Text_DoVisitAgain, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_EventScript_RateMonNickname::
	specialvar VAR_RESULT, ScriptGetSelectedMonSpecies
	goto_if_eq VAR_RESULT, SPECIES_EGG, SlateportCity_NameRatersHouse_EventScript_CantRateEgg
	special BufferMonNickname
	special IsMonOTIDNotPlayers
	goto_if_eq VAR_RESULT, TRUE, SlateportCity_NameRatersHouse_EventScript_PlayerNotMonsOT
	specialvar VAR_RESULT, MonOTNameNotPlayer
	special BufferMonNickname
	goto_if_eq VAR_RESULT, TRUE, SlateportCity_NameRatersHouse_EventScript_PlayerNotMonsOT
	msgbox SlateportCity_NameRatersHouse_Text_FineNameSuggestBetterOne, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, YES, SlateportCity_NameRatersHouse_EventScript_ChangeNickname
	goto_if_eq VAR_RESULT, NO, SlateportCity_NameRatersHouse_EventScript_DeclineNameRate
	end

SlateportCity_NameRatersHouse_EventScript_CantRateEgg::
	msgbox SlateportCity_NameRatersHouse_Text_ThatIsMerelyAnEgg, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_EventScript_PlayerNotMonsOT::
	msgbox SlateportCity_NameRatersHouse_Text_MagnificentName, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_EventScript_ChangeNickname::
	msgbox SlateportCity_NameRatersHouse_Text_WhatShallNewNameBe, MSGBOX_DEFAULT
	call Common_EventScript_NameReceivedPartyMon
	specialvar VAR_RESULT, TryPutNameRaterShowOnTheAir
	special BufferMonNickname
	goto_if_eq VAR_RESULT, TRUE, SlateportCity_NameRatersHouse_EventScript_NewNameDifferent
	msgbox SlateportCity_NameRatersHouse_Text_NameNoDifferentYetSuperior, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_EventScript_NewNameDifferent::
	msgbox SlateportCity_NameRatersHouse_Text_MonShallBeKnownAsName, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_Text_PleasedToRateMonNickname:
	.string "Hi, hi! I'm the NAME RATER!\n"
	.string "I'm the fortune-teller of names!\p"
	.string "I shall be pleased to rate your\n"
	.string "POKéMON's nickname.$"

SlateportCity_NameRatersHouse_Text_CritiqueWhichMonNickname:
	.string "Which POKéMON's nickname should\n"
	.string "I critique?$"

SlateportCity_NameRatersHouse_Text_FineNameSuggestBetterOne:
	.string "Hmmm… {STR_VAR_1}, is it? That is\n"
	.string "quite a fine name you bestowed.\p"
	.string "But! What say you, if I were to\n"
	.string "suggest a slightly better name?$"

SlateportCity_NameRatersHouse_Text_WhatShallNewNameBe:
	.string "Ah, good. Then, what shall the new\n"
	.string "nickname be?$"

SlateportCity_NameRatersHouse_Text_MonShallBeKnownAsName:
	.string "Done! From now on, this POKéMON\n"
	.string "shall be known as {STR_VAR_1}!\p"
	.string "It is a better name than before!\n"
	.string "How fortunate for you!$"

SlateportCity_NameRatersHouse_Text_DoVisitAgain:
	.string "I see.\n"
	.string "Do come visit again.$"

SlateportCity_NameRatersHouse_Text_NameNoDifferentYetSuperior:
	.string "Done! From now on, this POKéMON\n"
	.string "shall be known as {STR_VAR_1}!\p"
	.string "It looks no different from before,\n"
	.string "and yet, this is vastly superior!\p"
	.string "How fortunate for you!$"

SlateportCity_NameRatersHouse_Text_MagnificentName:
	.string "Hmmm… {STR_VAR_1} it is!\p"
	.string "This is a magnificent nickname!\n"
	.string "It is impeccably beyond reproach!\p"
	.string "You'll do well to cherish your\n"
	.string "{STR_VAR_1} now and beyond.$"

SlateportCity_NameRatersHouse_Text_ThatIsMerelyAnEgg:
	.string "Now, now.\n"
	.string "That is merely an EGG!$"

@ BPE: the Name Rater's friend reads out a party Pokémon's exact friendship.
SlateportCity_NameRatersHouse_EventScript_FriendshipChecker::
	lock
	faceplayer
	msgbox SlateportCity_NameRatersHouse_Text_FriendshipCheckerIntro, MSGBOX_DEFAULT
	special ChoosePartyMon
	lock
	faceplayer
	goto_if_ge VAR_0x8004, PARTY_SIZE, SlateportCity_NameRatersHouse_EventScript_FriendshipCheckerDecline
	specialvar VAR_RESULT, ScriptGetPartyMonSpecies
	goto_if_eq VAR_RESULT, SPECIES_EGG, SlateportCity_NameRatersHouse_EventScript_FriendshipCheckerEgg
	bufferpartymonnick STR_VAR_1, VAR_0x8004
	specialvar VAR_RESULT, ScriptGetPartyMonFriendship
	buffernumberstring STR_VAR_2, VAR_RESULT
	msgbox SlateportCity_NameRatersHouse_Text_FriendshipValue, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_EventScript_FriendshipCheckerEgg::
	msgbox SlateportCity_NameRatersHouse_Text_FriendshipCheckerEgg, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_EventScript_FriendshipCheckerDecline::
	msgbox SlateportCity_NameRatersHouse_Text_FriendshipCheckerDecline, MSGBOX_DEFAULT
	release
	end

SlateportCity_NameRatersHouse_Text_FriendshipCheckerIntro:
	.string "My friend rates names, but I can\n"
	.string "tell how much a POKéMON loves you!\p"
	.string "Which one should I look at?$"

SlateportCity_NameRatersHouse_Text_FriendshipValue:
	.string "{STR_VAR_1}'s friendship is\n"
	.string "{STR_VAR_2} out of 255.\p"
	.string "POKéMON that evolve through\n"
	.string "friendship need at least 160.$"

SlateportCity_NameRatersHouse_Text_FriendshipCheckerEgg:
	.string "That's an EGG! It hasn't met\n"
	.string "you yet.$"

SlateportCity_NameRatersHouse_Text_FriendshipCheckerDecline:
	.string "Come back any time!$"
