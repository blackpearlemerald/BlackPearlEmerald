BattleFrontier_RankingHall_MapScripts::
	.byte 0

BattleFrontier_RankingHall_EventScript_TowerSinglesRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_TOWER_SINGLES
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_TowerDoublesRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_TOWER_DOUBLES
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_TowerMultisRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_TOWER_MULTIS
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_TowerLinkRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_TOWER_LINK
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_ArenaRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_ARENA
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_PalaceRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_PALACE
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_FactoryRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_FACTORY
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_DomeRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_DOME
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_PikeRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_PIKE
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_PyramidRecords::
	lockall
	setvar VAR_0x8005, RANKING_HALL_PYRAMID
	goto BattleFrontier_RankingHall_EventScript_ShowRecords
	end

BattleFrontier_RankingHall_EventScript_ShowRecords::
	special ShowRankingHallRecordsWindow
	waitbuttonpress
	special ScrollRankingHallRecordsWindow
	waitbuttonpress
	special RemoveRecordsWindow
	releaseall
	end

BattleFrontier_RankingHall_EventScript_Attendant::
	lock
	faceplayer
	msgbox BattleFrontier_RankingHall_Text_ExplainRankingHall, MSGBOX_DEFAULT
	msgbox BattleFrontier_RankingHall_Text_AskRuleRecords, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, BattleFrontier_RankingHall_EventScript_EndRuleRecords
BattleFrontier_RankingHall_EventScript_ChooseRecordsFacility:
	message BattleFrontier_RankingHall_Text_WhichRecords
	waitmessage
	dynmultipush BattleFrontier_RankingHall_Text_Tower, FRONTIER_FACILITY_TOWER
	dynmultipush BattleFrontier_RankingHall_Text_Dome, FRONTIER_FACILITY_DOME
	dynmultipush BattleFrontier_RankingHall_Text_Palace, FRONTIER_FACILITY_PALACE
	dynmultipush BattleFrontier_RankingHall_Text_Arena, FRONTIER_FACILITY_ARENA
	dynmultipush BattleFrontier_RankingHall_Text_Factory, FRONTIER_FACILITY_FACTORY
	dynmultipush BattleFrontier_RankingHall_Text_Pike, FRONTIER_FACILITY_PIKE
	dynmultipush BattleFrontier_RankingHall_Text_Pyramid, FRONTIER_FACILITY_PYRAMID
	dynmultipush BattleFrontier_RankingHall_Text_TrainerHill, FRONTIER_RECORDS_HILL
	dynmultistack 17, 0, FALSE, 6, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_eq VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_RankingHall_EventScript_EndRuleRecords
	copyvar VAR_0x8004, VAR_RESULT
	setvar VAR_0x8005, FRONTIER_MODE_SINGLES
	setvar VAR_0x8006, FRONTIER_RECORDS_FULL_DEX
	goto_if_eq VAR_0x8004, FRONTIER_RECORDS_HILL, BattleFrontier_RankingHall_EventScript_ShowRuleRecords
	goto_if_eq VAR_0x8004, FRONTIER_FACILITY_ARENA, BattleFrontier_RankingHall_EventScript_ShowRuleRecords
	goto_if_eq VAR_0x8004, FRONTIER_FACILITY_PIKE, BattleFrontier_RankingHall_EventScript_ShowRuleRecords
	goto_if_eq VAR_0x8004, FRONTIER_FACILITY_PYRAMID, BattleFrontier_RankingHall_EventScript_ShowRuleRecords
	message BattleFrontier_RankingHall_Text_WhichBattles
	waitmessage
	dynmultipush BattleFrontier_RankingHall_Text_Singles, FRONTIER_MODE_SINGLES
	dynmultipush BattleFrontier_RankingHall_Text_Doubles, FRONTIER_MODE_DOUBLES
	goto_if_ne VAR_0x8004, FRONTIER_FACILITY_TOWER, BattleFrontier_RankingHall_EventScript_ShowRecordsModes
	dynmultipush BattleFrontier_RankingHall_Text_Multi, FRONTIER_MODE_MULTIS
BattleFrontier_RankingHall_EventScript_ShowRecordsModes:
	dynmultistack 17, 0, FALSE, 3, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_eq VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_RankingHall_EventScript_ChooseRecordsFacility
	copyvar VAR_0x8005, VAR_RESULT
	goto_if_eq VAR_0x8005, FRONTIER_MODE_MULTIS, BattleFrontier_RankingHall_EventScript_ShowRuleRecords
	goto_if_eq VAR_0x8004, FRONTIER_FACILITY_PALACE, BattleFrontier_RankingHall_EventScript_ShowRuleRecords
	message BattleFrontier_RankingHall_Text_WhichRules
	waitmessage
	dynmultipush BattleFrontier_Text_RulesFullDex, FRONTIER_RECORDS_FULL_DEX
	dynmultipush BattleFrontier_Text_NationalDex, FRONTIER_GEN_NATIONAL_DEX
	goto_if_eq VAR_0x8005, FRONTIER_MODE_DOUBLES, BattleFrontier_RankingHall_EventScript_PushLaterGens
	dynmultipush BattleFrontier_Text_Gen1, 1
	dynmultipush BattleFrontier_Text_Gen2, 2
BattleFrontier_RankingHall_EventScript_PushLaterGens:
	dynmultipush BattleFrontier_Text_Gen3, 3
	dynmultipush BattleFrontier_Text_Gen4, 4
	dynmultipush BattleFrontier_Text_Gen5, 5
	dynmultipush BattleFrontier_Text_Gen6, 6
	dynmultipush BattleFrontier_Text_Gen7, 7
	dynmultipush BattleFrontier_Text_Gen8, 8
	dynmultipush BattleFrontier_Text_Gen9, 9
	dynmultistack 17, 0, FALSE, 6, FALSE, 0, DYN_MULTICHOICE_CB_NONE
	goto_if_eq VAR_RESULT, MULTI_B_PRESSED, BattleFrontier_RankingHall_EventScript_ChooseRecordsFacility
	copyvar VAR_0x8006, VAR_RESULT
BattleFrontier_RankingHall_EventScript_ShowRuleRecords:
	closemessage
	callnative ShowFrontierRuleRecords
	waitbuttonpress
	special RemoveRecordsWindow
	goto BattleFrontier_RankingHall_EventScript_ChooseRecordsFacility

BattleFrontier_RankingHall_EventScript_EndRuleRecords:
	closemessage
	release
	end

BattleFrontier_RankingHall_Text_AskRuleRecords:
	.string "Would you like to see your own\n"
	.string "Full Dex and Smogon records?$"

BattleFrontier_RankingHall_Text_WhichRecords:
	.string "Which facility's records?$"

BattleFrontier_RankingHall_Text_WhichBattles:
	.string "Which kind of battle?$"

BattleFrontier_RankingHall_Text_WhichRules:
	.string "Which rules?$"

BattleFrontier_RankingHall_Text_Tower:
	.string "Battle Tower$"

BattleFrontier_RankingHall_Text_Dome:
	.string "Battle Dome$"

BattleFrontier_RankingHall_Text_Palace:
	.string "Battle Palace$"

BattleFrontier_RankingHall_Text_Arena:
	.string "Battle Arena$"

BattleFrontier_RankingHall_Text_Factory:
	.string "Battle Factory$"

BattleFrontier_RankingHall_Text_Pike:
	.string "Battle Pike$"

BattleFrontier_RankingHall_Text_Pyramid:
	.string "Battle Pyramid$"

BattleFrontier_RankingHall_Text_TrainerHill:
	.string "Trainer Hill$"

BattleFrontier_RankingHall_Text_Singles:
	.string "Singles$"

BattleFrontier_RankingHall_Text_Doubles:
	.string "Doubles$"

BattleFrontier_RankingHall_Text_Multi:
	.string "Multi$"

BattleFrontier_RankingHall_EventScript_DomePikeFactoryRecordsSign::
	msgbox BattleFrontier_RankingHall_Text_DomePikeFactoryRecords, MSGBOX_SIGN
	end

BattleFrontier_RankingHall_EventScript_PalaceArenaPyramidRecordsSIgn::
	msgbox BattleFrontier_RankingHall_Text_PalaceArenaPyramidRecords, MSGBOX_SIGN
	end

BattleFrontier_RankingHall_EventScript_NinjaBoy::
	lock
	faceplayer
	msgbox BattleFrontier_RankingHall_Text_IsYourNameOnThisList, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, YES, BattleFrontier_RankingHall_EventScript_NinjaBoyNameOnList
	msgbox BattleFrontier_RankingHall_Text_WorkHarderIfYouSawFriendsName, MSGBOX_DEFAULT
	release
	end

BattleFrontier_RankingHall_EventScript_NinjaBoyNameOnList::
	msgbox BattleFrontier_RankingHall_Text_WowThatsSuper, MSGBOX_DEFAULT
	release
	end

BattleFrontier_RankingHall_EventScript_Boy::
	msgbox BattleFrontier_RankingHall_Text_MyNamesNotUpThere, MSGBOX_NPC
	end

BattleFrontier_RankingHall_Text_ExplainRankingHall:
	.string "This is the RANKING HALL.\p"
	.string "This is where we recognize the immortal\n"
	.string "TRAINERS who left great records in\l"
	.string "BATTLE FRONTIER events.$"

BattleFrontier_RankingHall_Text_DomePikeFactoryRecords:
	.string "BATTLE DOME, BATTLE PIKE,\n"
	.string "and BATTLE FACTORY Records$"

BattleFrontier_RankingHall_Text_PalaceArenaPyramidRecords:
	.string "BATTLE PALACE, BATTLE ARENA,\n"
	.string "and BATTLE PYRAMID Records$"

BattleFrontier_RankingHall_Text_IsYourNameOnThisList:
	.string "Hi, is your name on this list?$"

BattleFrontier_RankingHall_Text_WowThatsSuper:
	.string "Wow, that's super!\n"
	.string "I'll have to try harder, too!$"

BattleFrontier_RankingHall_Text_WorkHarderIfYouSawFriendsName:
	.string "Oh, is that right?\p"
	.string "If you saw your friend's name up here,\n"
	.string "I bet it would make you work harder!$"

BattleFrontier_RankingHall_Text_MyNamesNotUpThere:
	.string "Hmm…\n"
	.string "My name's not up there…\p"
	.string "Well, it's only natural since I haven't\n"
	.string "taken any challenges yet.$"

