MauvilleCity_Gym_MapScripts::
	map_script MAP_SCRIPT_ON_LOAD, MauvilleCity_Gym_OnLoad
	.byte 0

MauvilleCity_Gym_OnLoad:
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Gym_EventScript_DeactivatePuzzle
	switch VAR_MAUVILLE_GYM_STATE
	case 0, MauvilleCity_Gym_EventScript_UpdateBarriers
	case 1, MauvilleCity_Gym_EventScript_Switch1Pressed
	case 2, MauvilleCity_Gym_EventScript_Switch2Pressed
	case 3, MauvilleCity_Gym_EventScript_Switch3Pressed
	case 4, MauvilleCity_Gym_EventScript_Switch4Pressed
	end

MauvilleCity_Gym_EventScript_UpdateBarriers::
	goto_if_set FLAG_MAUVILLE_GYM_BARRIERS_STATE, MauvilleCity_Gym_EventScript_SetAltBarriers
	end

MauvilleCity_Gym_EventScript_SetAltBarriers::
	setmetatile 3, 11, METATILE_MauvilleGym_RedBeamV1_On, TRUE
	setmetatile 3, 12, METATILE_MauvilleGym_RedBeamV2_On, TRUE
	setmetatile 3, 13, METATILE_MauvilleGym_PoleTop_On, TRUE
	setmetatile 4, 10, METATILE_MauvilleGym_RedBeamH1_On, FALSE
	setmetatile 5, 10, METATILE_MauvilleGym_RedBeamH2_On, FALSE
	setmetatile 4, 11, METATILE_MauvilleGym_RedBeamH3_On, TRUE
	setmetatile 5, 11, METATILE_MauvilleGym_RedBeamH4_On, TRUE
	setmetatile 7, 10, METATILE_MauvilleGym_RedBeamH1_On, FALSE
	setmetatile 8, 10, METATILE_MauvilleGym_RedBeamH2_On, FALSE
	setmetatile 7, 11, METATILE_MauvilleGym_RedBeamH3_On, TRUE
	setmetatile 8, 11, METATILE_MauvilleGym_RedBeamH4_On, TRUE
	setmetatile 4, 13, METATILE_MauvilleGym_GreenBeamH1_Off, FALSE
	setmetatile 5, 13, METATILE_MauvilleGym_GreenBeamH2_Off, FALSE
	setmetatile 4, 14, METATILE_MauvilleGym_GreenBeamH3_Off, FALSE
	setmetatile 5, 14, METATILE_MauvilleGym_GreenBeamH4_Off, FALSE
	setmetatile 1, 10, METATILE_MauvilleGym_GreenBeamH1_Off, FALSE
	setmetatile 2, 10, METATILE_MauvilleGym_GreenBeamH2_Off, FALSE
	setmetatile 1, 11, METATILE_MauvilleGym_GreenBeamH3_Off, FALSE
	setmetatile 2, 11, METATILE_MauvilleGym_GreenBeamH4_Off, FALSE
	setmetatile 6, 8, METATILE_MauvilleGym_PoleBottom_On, TRUE
	setmetatile 6, 9, METATILE_MauvilleGym_FloorTile, FALSE
	setmetatile 6, 10, METATILE_MauvilleGym_PoleTop_Off, FALSE
	setmetatile 4, 6, METATILE_MauvilleGym_GreenBeamH1_Off, FALSE
	setmetatile 5, 6, METATILE_MauvilleGym_GreenBeamH2_Off, FALSE
	setmetatile 4, 7, METATILE_MauvilleGym_GreenBeamH3_Off, FALSE
	setmetatile 5, 7, METATILE_MauvilleGym_GreenBeamH4_Off, FALSE
	end

MauvilleCity_Gym_EventScript_Switch1Pressed::
	setvar VAR_0x8004, 0
	special MauvilleGymPressSwitch
	goto MauvilleCity_Gym_EventScript_UpdateBarriers
	end

MauvilleCity_Gym_EventScript_Switch2Pressed::
	setvar VAR_0x8004, 1
	special MauvilleGymPressSwitch
	goto MauvilleCity_Gym_EventScript_UpdateBarriers
	end

MauvilleCity_Gym_EventScript_Switch3Pressed::
	setvar VAR_0x8004, 2
	special MauvilleGymPressSwitch
	goto MauvilleCity_Gym_EventScript_UpdateBarriers
	end

MauvilleCity_Gym_EventScript_Switch4Pressed::
	setvar VAR_0x8004, 3
	special MauvilleGymPressSwitch
	goto MauvilleCity_Gym_EventScript_UpdateBarriers
	end

MauvilleCity_Gym_EventScript_DeactivatePuzzle::
	special MauvilleGymDeactivatePuzzle
	end

MauvilleCity_Gym_EventScript_Wattson::
	trainerbattle_single TRAINER_WATTSON_1, MauvilleCity_Gym_Text_WattsonIntro, MauvilleCity_Gym_Text_WattsonDefeat, MauvilleCity_Gym_EventScript_WattsonDefeated, NO_MUSIC
	specialvar VAR_RESULT, ShouldTryRematchBattle
	goto_if_eq VAR_RESULT, TRUE, MauvilleCity_Gym_EventScript_WattsonRematch
	goto_if_unset FLAG_RECEIVED_TM_SHOCK_WAVE, MauvilleCity_Gym_EventScript_GiveShockWave2
	goto_if_eq VAR_NEW_MAUVILLE_STATE, 2, MauvilleCity_Gym_EventScript_CompletedNewMauville
	msgbox MauvilleCity_Gym_Text_WattsonPostBattle, MSGBOX_DEFAULT
	release
	end

MauvilleCity_Gym_EventScript_WattsonDefeated::
	message MauvilleCity_Gym_Text_ReceivedDynamoBadge
	waitmessage
	call Common_EventScript_PlayGymBadgeFanfare
	msgbox MauvilleCity_Gym_Text_ExplainDynamoBadgeTakeThis, MSGBOX_DEFAULT
	setvar VAR_SLATEPORT_OUTSIDE_MUSEUM_STATE, 3
	clearflag FLAG_HIDE_VERDANTURF_TOWN_SCOTT
	setflag FLAG_DEFEATED_MAUVILLE_GYM
	setflag FLAG_BADGE03_GET
	addvar VAR_PETALBURG_GYM_STATE, 1
	call_if_eq VAR_PETALBURG_GYM_STATE, 6, Common_EventScript_ReadyPetalburgGymForBattle
	setvar VAR_0x8008, 3
	call Common_EventScript_SetGymTrainers
	special MauvilleGymDeactivatePuzzle
	special DrawWholeMapView
	playse SE_UNLOCK
	call MauvilleCity_Gym_EventScript_GiveShockWave
	closemessage
	delay 30
	playfanfare MUS_REGISTER_MATCH_CALL
	msgbox MauvilleCity_Gym_Text_RegisteredWattson, MSGBOX_DEFAULT
	waitfanfare
	closemessage
	delay 30
	setflag FLAG_ENABLE_WATTSON_MATCH_CALL
	release
	end

MauvilleCity_Gym_EventScript_GiveShockWave2::
	additem ITEM_TM_FOUL_PLAY
	additem ITEM_TM_BULK_UP
	additem ITEM_TM_AIR_SLASH
	additem ITEM_TM_BODY_SLAM
	additem ITEM_TM_FIRE_PUNCH
	additem ITEM_TM_THUNDER_PUNCH
	additem ITEM_TM_ICE_PUNCH
	additem ITEM_TM_SLEEP_TALK
	additem ITEM_TM_SEED_BOMB
	additem ITEM_TM_ELECTRO_BALL
	additem ITEM_TM_DRAIN_PUNCH
	additem ITEM_TM_DRAGON_CLAW
	additem ITEM_TM_DAZZLING_GLEAM
	additem ITEM_TM_METRONOME
	additem ITEM_TM_GRASS_KNOT
	additem ITEM_TM_THUNDER_WAVE
	additem ITEM_TM_POISON_JAB
	additem ITEM_TM_STOMPING_TANTRUM
	additem ITEM_TM_REST
	additem ITEM_TM_ROCK_SLIDE
	additem ITEM_TM_METRONOME
	additem ITEM_TM_GRASS_KNOT
	additem ITEM_TM_THUNDER_WAVE
	additem ITEM_TM_POISON_JAB
	additem ITEM_TM_HIGH_HORSEPOWER
	additem ITEM_TM_REST
	additem ITEM_TM_BODY_PRESS
	additem ITEM_TM_PAIN_SPLIT
	additem ITEM_TM_SCORCHING_SANDS
	additem ITEM_TM_EXPANDING_FORCE
	additem ITEM_TM_HARD_PRESS
	additem ITEM_TM_UPPER_HAND
	giveitem ITEM_LIFE_ORB
	goto_if_eq VAR_RESULT, FALSE, Common_EventScript_ShowBagIsFull
	msgbox MauvilleCity_Gym_Text_ExplainShockWave, MSGBOX_DEFAULT
	setflag FLAG_RECEIVED_TM_SHOCK_WAVE
	release
	end

MauvilleCity_Gym_EventScript_GiveShockWave::
	additem ITEM_TM_FOUL_PLAY
	additem ITEM_TM_BULK_UP
	additem ITEM_TM_AIR_SLASH
	additem ITEM_TM_BODY_SLAM
	additem ITEM_TM_FIRE_PUNCH
	additem ITEM_TM_THUNDER_PUNCH
	additem ITEM_TM_ICE_PUNCH
	additem ITEM_TM_SLEEP_TALK
	additem ITEM_TM_SEED_BOMB
	additem ITEM_TM_ELECTRO_BALL
	additem ITEM_TM_DRAIN_PUNCH
	additem ITEM_TM_DRAGON_CLAW
	additem ITEM_TM_DAZZLING_GLEAM
	additem ITEM_TM_METRONOME
	additem ITEM_TM_GRASS_KNOT
	additem ITEM_TM_THUNDER_WAVE
	additem ITEM_TM_POISON_JAB
	additem ITEM_TM_STOMPING_TANTRUM
	additem ITEM_TM_REST
	additem ITEM_TM_ROCK_SLIDE
	additem ITEM_TM_METRONOME
	additem ITEM_TM_GRASS_KNOT
	additem ITEM_TM_THUNDER_WAVE
	additem ITEM_TM_POISON_JAB
	additem ITEM_TM_HIGH_HORSEPOWER
	additem ITEM_TM_REST
	additem ITEM_TM_BODY_PRESS
	additem ITEM_TM_PAIN_SPLIT
	additem ITEM_TM_SCORCHING_SANDS
	additem ITEM_TM_EXPANDING_FORCE
	additem ITEM_TM_HARD_PRESS
	additem ITEM_TM_UPPER_HAND
	giveitem ITEM_LIFE_ORB
	goto_if_eq VAR_RESULT, FALSE, Common_EventScript_BagIsFull
	msgbox MauvilleCity_Gym_Text_ExplainShockWave, MSGBOX_DEFAULT
	setflag FLAG_RECEIVED_TM_SHOCK_WAVE
	return

MauvilleCity_Gym_EventScript_CompletedNewMauville::
	msgbox MauvilleCity_Gym_Text_WattsonGoForthAndEndeavor, MSGBOX_DEFAULT
	release
	end

MauvilleCity_Gym_EventScript_WattsonRematch::
	trainerbattle_rematch_double TRAINER_WATTSON_1, MauvilleCity_Gym_Text_WattsonPreRematch, MauvilleCity_Gym_Text_WattsonRematchDefeat, MauvilleCity_Gym_Text_WattsonRematchNeedTwoMons
	msgbox MauvilleCity_Gym_Text_WattsonPostRematch, MSGBOX_AUTOCLOSE
	end

MauvilleCity_Gym_EventScript_Switch1::
	lockall
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Gym_EventScript_SwitchDoNothing
	goto_if_eq VAR_MAUVILLE_GYM_STATE, 1, MauvilleCity_Gym_EventScript_SwitchDoNothing
	setvar VAR_MAUVILLE_GYM_STATE, 1
	setvar VAR_0x8004, 0
	goto MauvilleCity_Gym_EventScript_PressFloorSwitch
	end

MauvilleCity_Gym_EventScript_Switch2::
	lockall
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Gym_EventScript_SwitchDoNothing
	goto_if_eq VAR_MAUVILLE_GYM_STATE, 2, MauvilleCity_Gym_EventScript_SwitchDoNothing
	setvar VAR_MAUVILLE_GYM_STATE, 2
	setvar VAR_0x8004, 1
	goto MauvilleCity_Gym_EventScript_PressFloorSwitch
	end

MauvilleCity_Gym_EventScript_Switch3::
	lockall
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Gym_EventScript_SwitchDoNothing
	goto_if_eq VAR_MAUVILLE_GYM_STATE, 3, MauvilleCity_Gym_EventScript_SwitchDoNothing
	setvar VAR_MAUVILLE_GYM_STATE, 3
	setvar VAR_0x8004, 2
	goto MauvilleCity_Gym_EventScript_PressFloorSwitch
	end

MauvilleCity_Gym_EventScript_Switch4::
	lockall
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Gym_EventScript_SwitchDoNothing
	goto_if_eq VAR_MAUVILLE_GYM_STATE, 4, MauvilleCity_Gym_EventScript_SwitchDoNothing
	setvar VAR_MAUVILLE_GYM_STATE, 4
	setvar VAR_0x8004, 3
	goto MauvilleCity_Gym_EventScript_PressFloorSwitch
	end

MauvilleCity_Gym_EventScript_PressFloorSwitch::
	special MauvilleGymSetDefaultBarriers
	special MauvilleGymPressSwitch
	special DrawWholeMapView
	playse SE_UNLOCK
	goto_if_set FLAG_MAUVILLE_GYM_BARRIERS_STATE, MauvilleCity_Gym_EventScript_ClearBarriersAltState
	goto_if_unset FLAG_MAUVILLE_GYM_BARRIERS_STATE, MauvilleCity_Gym_EventScript_SetBarriersAltState
	releaseall
	end

MauvilleCity_Gym_EventScript_SwitchDoNothing::
	releaseall
	end

MauvilleCity_Gym_EventScript_SetBarriersAltState::
	setflag FLAG_MAUVILLE_GYM_BARRIERS_STATE
	releaseall
	end

MauvilleCity_Gym_EventScript_ClearBarriersAltState::
	clearflag FLAG_MAUVILLE_GYM_BARRIERS_STATE
	releaseall
	end

MauvilleCity_Gym_EventScript_Kirk::
	trainerbattle_single TRAINER_KIRK, MauvilleCity_Gym_Text_KirkIntro, MauvilleCity_Gym_Text_KirkDefeat
	msgbox MauvilleCity_Gym_Text_KirkPostBattle, MSGBOX_AUTOCLOSE
	end

MauvilleCity_Gym_EventScript_Shawn::
	trainerbattle_single TRAINER_SHAWN, MauvilleCity_Gym_Text_ShawnIntro, MauvilleCity_Gym_Text_ShawnDefeat
	msgbox MauvilleCity_Gym_Text_ShawnPostBattle, MSGBOX_AUTOCLOSE
	end

MauvilleCity_Gym_EventScript_Ben::
	trainerbattle_single TRAINER_BEN, MauvilleCity_Gym_Text_BenIntro, MauvilleCity_Gym_Text_BenDefeat
	msgbox MauvilleCity_Gym_Text_BenPostBattle, MSGBOX_AUTOCLOSE
	end

MauvilleCity_Gym_EventScript_Vivian::
	trainerbattle_single TRAINER_VIVIAN, MauvilleCity_Gym_Text_VivianIntro, MauvilleCity_Gym_Text_VivianDefeat
	msgbox MauvilleCity_Gym_Text_VivianPostBattle, MSGBOX_AUTOCLOSE
	end

MauvilleCity_Gym_EventScript_Angelo::
	trainerbattle_single TRAINER_ANGELO, MauvilleCity_Gym_Text_AngeloIntro, MauvilleCity_Gym_Text_AngeloDefeat
	msgbox MauvilleCity_Gym_Text_AngeloPostBattle, MSGBOX_AUTOCLOSE
	end

MauvilleCity_Gym_EventScript_GymGuide::
	lock
	faceplayer
	goto_if_set FLAG_DEFEATED_MAUVILLE_GYM, MauvilleCity_Gym_EventScript_GymGuidePostVictory
	msgbox MauvilleCity_Gym_Text_GymGuideAdvice, MSGBOX_DEFAULT
	release
	end

MauvilleCity_Gym_EventScript_GymGuidePostVictory::
	msgbox MauvilleCity_Gym_Text_GymGuidePostVictory, MSGBOX_DEFAULT
	release
	end

MauvilleCity_Gym_EventScript_LeftGymStatue::
	lockall
	goto_if_set FLAG_BADGE03_GET, MauvilleCity_Gym_EventScript_GymStatueCertified
	goto MauvilleCity_Gym_EventScript_GymStatue
	end

MauvilleCity_Gym_EventScript_RightGymStatue::
	lockall
	goto_if_set FLAG_BADGE03_GET, MauvilleCity_Gym_EventScript_GymStatueCertified
	goto MauvilleCity_Gym_EventScript_GymStatue
	end

MauvilleCity_Gym_EventScript_GymStatueCertified::
	msgbox MauvilleCity_Gym_Text_GymStatueCertified, MSGBOX_DEFAULT
	releaseall
	end

MauvilleCity_Gym_EventScript_GymStatue::
	msgbox MauvilleCity_Gym_Text_GymStatue, MSGBOX_DEFAULT
	releaseall
	end

MauvilleCity_Gym_Text_GymGuideAdvice:
	.string "Hey, how's it going, CHAMPION-\n"
	.string "bound {PLAYER}?\p"
	.string "DHill, is the LEADER of MAUVILLE!$"

MauvilleCity_Gym_Text_GymGuidePostVictory:
	.string "Whoa, you're electrifying!\n"
	.string "You've powered the door open!$"

MauvilleCity_Gym_Text_KirkIntro:
	.string "My electric soul, it'll shatter your\n"
	.string "dreams whole, whoa-yeahah!$"

MauvilleCity_Gym_Text_KirkDefeat:
	.string "That was plugged in, amped up,\n"
	.string "over-driven electric, man!$"

MauvilleCity_Gym_Text_KirkPostBattle:
	.string "POKéMON and rock, it's all about heart,\n"
	.string "whoa-yeah!$"

MauvilleCity_Gym_Text_ShawnIntro:
	.string "I trained under DHill!\n"
	.string "There ain't no way I'll lose easily!$"

MauvilleCity_Gym_Text_ShawnDefeat:
	.string "Unplugged and turned off…$"

MauvilleCity_Gym_Text_ShawnPostBattle:
	.string "DHill, our GYM LEADER, has been\n"
	.string "around for a long, long time.\p"
	.string "He was battling even before your\n"
	.string "daddy was born, that tough coot.$"

MauvilleCity_Gym_Text_BenIntro:
	.string "This GYM's got puzzles!\n"
	.string "Isn't it fun?$"

MauvilleCity_Gym_Text_BenDefeat:
	.string "It's no fun to lose…$"

MauvilleCity_Gym_Text_BenPostBattle:
	.string "DHill says he likes setting up\n"
	.string "little traps with switches.$"

MauvilleCity_Gym_Text_VivianIntro:
	.string "With my charm and my POKéMON's moves,\n"
	.string "you'll be shocked!$"

MauvilleCity_Gym_Text_VivianDefeat:
	.string "I'm shocked by your power!$"

MauvilleCity_Gym_Text_VivianPostBattle:
	.string "I've heard that MAUVILLE was founded\n"
	.string "by DHill.\p"
	.string "He was a TRAINER long before we\n"
	.string "became TRAINERS.\l"
	.string "He must know all sorts of things!$"

MauvilleCity_Gym_Text_AngeloIntro:
	.string "I love shiny things!$"

MauvilleCity_Gym_Text_AngeloDefeat:
	.string "Oh…\n"
	.string "My eyes are frazzled…$"

MauvilleCity_Gym_Text_AngeloPostBattle:
	.string "MAUVILLE GYM's DHill makes great\n"
	.string "music. It makes me happy!$"

MauvilleCity_Gym_Text_WattsonIntro:
	.string "Yo. Lots of people know me for my\n"
	.string "music. But I've since converted...\p"
	.string "I've decided to settle down a bit,\n"
	.string "since I will soon be a father.\p"
	.string "However, I know the real fans will\n"
	.string "never forget the prime of DHill.\p"
	.string "YOU'RE MY WONDERRRRWAAAAAAAAAAAALL!$"

MauvilleCity_Gym_Text_WattsonDefeat:
	.string "Fair enough!\n"
	.string "I lost!\p"
	.string "You ended up giving me a thrill!\n"
	.string "Take this BADGE!$"

MauvilleCity_Gym_Text_ReceivedDynamoBadge:
	.string "{PLAYER} received the DYNAMO BADGE\n"
	.string "from DHill.$"

MauvilleCity_Gym_Text_ExplainDynamoBadgeTakeThis:
	.string "With the DYNAMO BADGE, POKéMON can\n"
	.string "use ROCK SMASH out of battle.\p"
	.string "And, it will make your POKéMON a little\n"
	.string "bit faster, too.\p"
	.string "Hmm…\n"
	.string "Also, please accept this reward!$"

MauvilleCity_Gym_Text_ExplainShockWave:
	.string "I would also like to give you this…\p"
	.string "{PLAYER} recieved TM Package 3!\p"
	.string "Those rewards will help you greatly\n"
	.string "on your journey!\p" 
	.string "One last thing...\p"  
	.string "Please check the Mauville Mart for\n" 
	.string "new items!$"

MauvilleCity_Gym_Text_RegisteredWattson:
	.string "Registered GYM LEADER DHill\n"
	.string "in the POKéNAV.$"

MauvilleCity_Gym_Text_WattsonPostBattle:
	.string "Please check the Mauville Mart for\n" 
	.string "new items!$"

MauvilleCity_Gym_Text_WattsonGoForthAndEndeavor:
	.string "Wahahahah!\n"
	.string "Go forth and endeavor, youngster!$"

MauvilleCity_Gym_Text_GymStatue:
	.string "MAUVILLE CITY POKéMON GYM$"

MauvilleCity_Gym_Text_GymStatueCertified:
	.string "MAUVILLE CITY POKéMON GYM\p"
	.string "DHill'S CERTIFIED TRAINERS:\n"
	.string "{PLAYER}$"

MauvilleCity_Gym_Text_WattsonPreRematch:
	.string "DHill: Ah-ha! Here at last!\n"
	.string "I know what you want.\l"
	.string "You want to battle my POKéMON!\p"
	.string "Wahahahaha!\p"
	.string "I'll make sparks fly from you!\n"
	.string "Don't say I didn't warn you!$"

MauvilleCity_Gym_Text_WattsonRematchDefeat:
	.string "Oof…\n"
	.string "Our batteries ran dry…$"

MauvilleCity_Gym_Text_WattsonPostRematch:
	.string "DHill: We'll have to recharge our\n"
	.string "batteries again.\p"
	.string "When we're fully charged up, we'll\n"
	.string "gladly accept your challenge.\p"
	.string "So, come back again sometime,\n"
	.string "won't you?$"

MauvilleCity_Gym_Text_WattsonRematchNeedTwoMons:
	.string "DHill: Ah-ha! Here at last!\n"
	.string "I know what you want.\l"
	.string "You want to battle my POKéMON!\p"
	.string "Wahahahaha!\p"
	.string "Oops! Wait!\n"
	.string "You've only one POKéMON with you!\p"
	.string "Come see me with two or more\n"
	.string "POKéMON, all right?$"

