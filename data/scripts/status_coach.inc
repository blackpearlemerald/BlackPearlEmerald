@ BPE: the status coach stands in every Pokémon Center. He burns or poisons a
@ party Pokémon for strategies that want it before a battle.
@ See ScriptCoachInflictStatus in field_specials.c.
Common_EventScript_StatusCoach::
	lock
	faceplayer
	message Common_Text_StatusCoachGreeting
	waitmessage
	dynmultichoice 0, 0, FALSE, 4, 0, DYN_MULTICHOICE_CB_NONE, Common_Text_StatusCoachBurn, Common_Text_StatusCoachPoison, Common_Text_StatusCoachBadPoison, Common_Text_StatusCoachCancel
	switch VAR_RESULT
	case 0, Common_EventScript_StatusCoachBurn
	case 1, Common_EventScript_StatusCoachPoison
	case 2, Common_EventScript_StatusCoachBadPoison
	goto Common_EventScript_StatusCoachGoodbye
	end

Common_EventScript_StatusCoachBurn::
	setvar VAR_0x8005, COACH_STATUS_BURN
	goto Common_EventScript_StatusCoachChooseMon
	end

Common_EventScript_StatusCoachPoison::
	setvar VAR_0x8005, COACH_STATUS_POISON
	goto Common_EventScript_StatusCoachChooseMon
	end

Common_EventScript_StatusCoachBadPoison::
	setvar VAR_0x8005, COACH_STATUS_TOXIC
	goto Common_EventScript_StatusCoachChooseMon
	end

Common_EventScript_StatusCoachChooseMon::
	msgbox Common_Text_StatusCoachWhichMon, MSGBOX_DEFAULT
	special ChoosePartyMon
	lock
	faceplayer
	goto_if_ge VAR_0x8004, PARTY_SIZE, Common_EventScript_StatusCoachGoodbye
	bufferpartymonnick STR_VAR_1, VAR_0x8004
	specialvar VAR_RESULT, ScriptCoachInflictStatus
	switch VAR_RESULT
	case COACH_RESULT_EGG, Common_EventScript_StatusCoachEgg
	case COACH_RESULT_FAINTED, Common_EventScript_StatusCoachFainted
	case COACH_RESULT_HAS_STATUS, Common_EventScript_StatusCoachHasStatus
	case COACH_RESULT_IMMUNE, Common_EventScript_StatusCoachImmune
	playse SE_M_TOXIC
	waitse
	msgbox Common_Text_StatusCoachDone, MSGBOX_DEFAULT
	release
	end

Common_EventScript_StatusCoachEgg::
	msgbox Common_Text_StatusCoachEgg, MSGBOX_DEFAULT
	release
	end

Common_EventScript_StatusCoachFainted::
	msgbox Common_Text_StatusCoachFainted, MSGBOX_DEFAULT
	release
	end

Common_EventScript_StatusCoachHasStatus::
	msgbox Common_Text_StatusCoachHasStatus, MSGBOX_DEFAULT
	release
	end

Common_EventScript_StatusCoachImmune::
	msgbox Common_Text_StatusCoachImmune, MSGBOX_DEFAULT
	release
	end

Common_EventScript_StatusCoachGoodbye::
	msgbox Common_Text_StatusCoachGoodbye, MSGBOX_DEFAULT
	release
	end

Common_Text_StatusCoachGreeting:
	.string "I'm a STATUS COACH! Some strategies\n"
	.string "want a burned or poisoned POKéMON.\p"
	.string "Want me to do that for you?$"

Common_Text_StatusCoachBurn:
	.string "Burn$"

Common_Text_StatusCoachPoison:
	.string "Poison$"

Common_Text_StatusCoachBadPoison:
	.string "Bad poison$"

Common_Text_StatusCoachCancel:
	.string "Cancel$"

Common_Text_StatusCoachWhichMon:
	.string "Which POKéMON?$"

Common_Text_StatusCoachDone:
	.string "There you go! {STR_VAR_1} is ready\n"
	.string "for battle.\p"
	.string "The nurse here can heal it if you\n"
	.string "change your mind.$"

Common_Text_StatusCoachEgg:
	.string "That's an EGG!\n"
	.string "Let it hatch first.$"

Common_Text_StatusCoachFainted:
	.string "{STR_VAR_1} has fainted.\n"
	.string "I can't do anything for it.$"

Common_Text_StatusCoachHasStatus:
	.string "{STR_VAR_1} already has a status\n"
	.string "condition. Heal it first.$"

Common_Text_StatusCoachImmune:
	.string "{STR_VAR_1} can't get that\n"
	.string "condition.$"

Common_Text_StatusCoachGoodbye:
	.string "Come back any time!$"
