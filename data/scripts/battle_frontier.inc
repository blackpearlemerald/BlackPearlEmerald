BattleFrontier_ShowCaughtBannedSpecies::
	goto_if_eq VAR_0x8005, 0, BattleFrontier_ShowCaughtBannedSpeciesEnd
	msgbox BattleFrontier_DoYouWantToSeeTheListOfCaughtBannedSpecies, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, BattleFrontier_ShowCaughtBannedSpeciesEnd
	callnative ShowBattleFrontierCaughtBannedSpecies
	waitstate
BattleFrontier_ShowCaughtBannedSpeciesEnd:
	return


BattleFrontier_DoYouWantToSeeTheListOfCaughtBannedSpecies:
	.string "Do you want to see the list of\n"
	.string "POKéMON species you can't bring?$"

@ BPE: the rule menus every Tower, Factory and Dome attendant shares. VAR_RESULT comes
@ back as the chosen FRONTIER_RULES_* value, or MULTI_B_PRESSED if the player backed out.
BattleFrontier_EventScript_ChooseRules::
	message BattleFrontier_Text_WhichRules
	waitmessage
	callnative ScriptCheckSmogonRulesAllowed
	dynmultipush BattleFrontier_Text_RulesVanilla, FRONTIER_RULES_VANILLA
	dynmultipush BattleFrontier_Text_RulesFullDex, FRONTIER_RULES_FULL_DEX
	goto_if_eq VAR_RESULT, FALSE, BattleFrontier_EventScript_ShowRules
	dynmultipush BattleFrontier_Text_RulesSmogon, FRONTIER_RULES_SMOGON
BattleFrontier_EventScript_ShowRules:
	dynmultistack 17, 0, FALSE, 3, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	switch VAR_RESULT
	case FRONTIER_RULES_VANILLA, BattleFrontier_EventScript_SetSimpleRule
	case FRONTIER_RULES_FULL_DEX, BattleFrontier_EventScript_SetSimpleRule
	case FRONTIER_RULES_SMOGON, BattleFrontier_EventScript_ChooseGeneration
	return

@ The same for everywhere else, which only has Vanilla and Full Dex.
BattleFrontier_EventScript_ChooseFullDexRules::
	message BattleFrontier_Text_WhichRules
	waitmessage
	dynmultipush BattleFrontier_Text_RulesVanilla, FRONTIER_RULES_VANILLA
	dynmultipush BattleFrontier_Text_RulesFullDex, FRONTIER_RULES_FULL_DEX
	dynmultistack 17, 0, FALSE, 2, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_ne VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_EventScript_SetSimpleRule
	return

BattleFrontier_EventScript_SetSimpleRule:
	copyvar VAR_0x8004, VAR_RESULT
	setvar VAR_0x8005, 0
	setvar VAR_0x8006, 0
	setvar VAR_0x8007, FRONTIER_TEAM_USUAL
	callnative SetFrontierRuleForChallenge
	copyvar VAR_RESULT, VAR_0x8004
	return

BattleFrontier_EventScript_ChooseGeneration:
	message BattleFrontier_Text_WhichGeneration
	waitmessage
	dynmultipush BattleFrontier_Text_NationalDex, FRONTIER_GEN_NATIONAL_DEX
	goto_if_eq VAR_FRONTIER_BATTLE_MODE, FRONTIER_MODE_DOUBLES, BattleFrontier_EventScript_PushLaterGens
	dynmultipush BattleFrontier_Text_Gen1, 1
	dynmultipush BattleFrontier_Text_Gen2, 2
BattleFrontier_EventScript_PushLaterGens:
	dynmultipush BattleFrontier_Text_Gen3, 3
	dynmultipush BattleFrontier_Text_Gen4, 4
	dynmultipush BattleFrontier_Text_Gen5, 5
	dynmultipush BattleFrontier_Text_Gen6, 6
	dynmultipush BattleFrontier_Text_Gen7, 7
	dynmultipush BattleFrontier_Text_Gen8, 8
	dynmultipush BattleFrontier_Text_Gen9, 9
	dynmultistack 17, 0, FALSE, 6, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_eq VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_EventScript_ChooseRules
	copyvar VAR_0x8005, VAR_RESULT
	message BattleFrontier_Text_WhichTier
	waitmessage
	dynmultipush BattleFrontier_Text_TierAnythingGoes, FRONTIER_TIER_ANYTHING_GOES
	dynmultipush BattleFrontier_Text_TierUbers, FRONTIER_TIER_UBERS
	dynmultipush BattleFrontier_Text_TierOU, FRONTIER_TIER_OU
	goto_if_eq VAR_FRONTIER_BATTLE_MODE, FRONTIER_MODE_DOUBLES, BattleFrontier_EventScript_ShowTiers
	dynmultipush BattleFrontier_Text_TierUU, FRONTIER_TIER_UU
	dynmultipush BattleFrontier_Text_TierRU, FRONTIER_TIER_RU
BattleFrontier_EventScript_ShowTiers:
	dynmultistack 17, 0, FALSE, 5, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_eq VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_EventScript_ChooseGeneration
	copyvar VAR_0x8006, VAR_RESULT
	message BattleFrontier_Text_WhichTeamSize
	waitmessage
	goto_if_eq VAR_FRONTIER_FACILITY, FRONTIER_FACILITY_FACTORY, BattleFrontier_EventScript_PushRentThree
	goto_if_eq VAR_FRONTIER_FACILITY, FRONTIER_FACILITY_DOME, BattleFrontier_EventScript_PushDomeUsual
	goto_if_eq VAR_FRONTIER_BATTLE_MODE, FRONTIER_MODE_DOUBLES, BattleFrontier_EventScript_PushFourVsFour
	dynmultipush BattleFrontier_Text_ThreeVsThree, FRONTIER_TEAM_USUAL
	goto BattleFrontier_EventScript_PushSixVsSix
BattleFrontier_EventScript_PushRentThree:
	dynmultipush BattleFrontier_Text_RentThree, FRONTIER_TEAM_USUAL
	dynmultipush BattleFrontier_Text_RentSix, FRONTIER_TEAM_6V6
	goto BattleFrontier_EventScript_ShowTeamSizes
BattleFrontier_EventScript_PushDomeUsual:
	dynmultipush BattleFrontier_Text_DomeUsual, FRONTIER_TEAM_USUAL
	goto BattleFrontier_EventScript_PushSixVsSix
BattleFrontier_EventScript_PushFourVsFour:
	dynmultipush BattleFrontier_Text_FourVsFour, FRONTIER_TEAM_USUAL
BattleFrontier_EventScript_PushSixVsSix:
	dynmultipush BattleFrontier_Text_SixVsSix, FRONTIER_TEAM_6V6
BattleFrontier_EventScript_ShowTeamSizes:
	dynmultistack 17, 0, FALSE, 2, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_eq VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_EventScript_ChooseGeneration
	copyvar VAR_0x8007, VAR_RESULT
	setvar VAR_0x8004, FRONTIER_RULES_SMOGON
	callnative SetFrontierRuleForChallenge
	msgbox BattleFrontier_Text_SmogonRulesNote, MSGBOX_DEFAULT
	call_if_eq VAR_0x8007, FRONTIER_TEAM_6V6, BattleFrontier_EventScript_DoubleBattlePointsNote
	goto_if_eq VAR_FRONTIER_FACILITY, FRONTIER_FACILITY_FACTORY, BattleFrontier_EventScript_SmogonRuleChosen
	setvar VAR_0x8004, 0
BattleFrontier_EventScript_ReportIllegalMons:
	callnative BufferNextIllegalFrontierMon
	goto_if_eq VAR_RESULT, FALSE, BattleFrontier_EventScript_SmogonRuleChosen
	msgbox gStringVar4, MSGBOX_DEFAULT
	goto BattleFrontier_EventScript_ReportIllegalMons

BattleFrontier_EventScript_SmogonRuleChosen:
	setvar VAR_RESULT, FRONTIER_RULES_SMOGON
	return

BattleFrontier_EventScript_DoubleBattlePointsNote:
	msgbox BattleFrontier_Text_DoubleBattlePoints, MSGBOX_DEFAULT
	return

BattleFrontier_EventScript_SelectSixMons::
	msgbox BattleFrontier_Text_SelectSixMons, MSGBOX_DEFAULT
	return

BattleFrontier_Text_WhichTeamSize:
	.string "How many POKéMON on each team?$"

BattleFrontier_Text_ThreeVsThree:
	.string "3 vs 3$"

BattleFrontier_Text_FourVsFour:
	.string "4 vs 4$"

BattleFrontier_Text_DomeUsual:
	.string "Bring 3, use 2$"

BattleFrontier_Text_SixVsSix:
	.string "6 vs 6$"

BattleFrontier_Text_RentThree:
	.string "Rent 3$"

BattleFrontier_Text_RentSix:
	.string "Rent 6$"

BattleFrontier_Text_DoubleBattlePoints:
	.string "6 vs 6 challenges pay double\n"
	.string "the usual Battle Points.$"

BattleFrontier_Text_SelectSixMons:
	.string "Please select the six POKéMON\n"
	.string "you wish to enter.$"

BattleFrontier_Text_WhichRules:
	.string "Which rules would you like?$"

BattleFrontier_Text_RulesVanilla:
	.string "Vanilla$"

BattleFrontier_Text_RulesFullDex:
	.string "Full Dex$"

BattleFrontier_Text_RulesSmogon:
	.string "Smogon$"

BattleFrontier_Text_WhichGeneration:
	.string "Which generation's rules?$"

BattleFrontier_Text_NationalDex:
	.string "National Dex$"

BattleFrontier_Text_Gen1:
	.string "Gen 1$"

BattleFrontier_Text_Gen2:
	.string "Gen 2$"

BattleFrontier_Text_Gen3:
	.string "Gen 3$"

BattleFrontier_Text_Gen4:
	.string "Gen 4$"

BattleFrontier_Text_Gen5:
	.string "Gen 5$"

BattleFrontier_Text_Gen6:
	.string "Gen 6$"

BattleFrontier_Text_Gen7:
	.string "Gen 7$"

BattleFrontier_Text_Gen8:
	.string "Gen 8$"

BattleFrontier_Text_Gen9:
	.string "Gen 9$"

BattleFrontier_Text_WhichTier:
	.string "Which tier?$"

BattleFrontier_Text_TierAnythingGoes:
	.string "Anything Goes$"

BattleFrontier_Text_TierUbers:
	.string "Ubers$"

BattleFrontier_Text_TierOU:
	.string "OU$"

BattleFrontier_Text_TierUU:
	.string "UU$"

BattleFrontier_Text_TierRU:
	.string "RU$"

BattleFrontier_Text_SmogonRulesNote:
	.string "Battles use today's rules, and every\n"
	.string "POKéMON is raised to Level 100 for\l"
	.string "the battle only.$"

BattleFrontier_Text_TeamTooSmall:
	.string "You don't have enough different\n"
	.string "POKéMON allowed under these rules.$"
