LilycoveCity_House1_MapScripts::
	.byte 0

LilycoveCity_House1_EventScript_ExpertM::
	msgbox LilycoveCity_House1_Text_PokemonPartnersNotTools, MSGBOX_NPC
	end

LilycoveCity_House1_EventScript_Kecleon::
	lock
	faceplayer
	waitse
	playmoncry SPECIES_KECLEON, CRY_MODE_NORMAL
	msgbox LilycoveCity_House1_Text_Kecleon, MSGBOX_DEFAULT
	waitmoncry
	release
	end

@ BPE: Lickitung (and so Lickilicky) had no source in BPE. This offers the
@ INGAME_TRADE_LICKITUNG entry from src/data/trade.h, which the randomizer
@ already counted, so adding it here changes no existing seed.
LilycoveCity_House1_EventScript_Trader::
	lock
	faceplayer
	goto_if_set FLAG_LILYCOVE_NPC_TRADE_COMPLETED, LilycoveCity_House1_EventScript_TradeCompleted
	ingame_trade INGAME_TRADE_LICKITUNG, LilycoveCity_House1_Text_WantToTrade, LilycoveCity_House1_EventScript_DeclineTrade, LilycoveCity_House1_EventScript_NotRequestedMon, LilycoveCity_House1_Text_TakeGoodCare
	setflag FLAG_LILYCOVE_NPC_TRADE_COMPLETED
	release
	end

LilycoveCity_House1_EventScript_DeclineTrade::
	msgbox LilycoveCity_House1_Text_ThatsTooBad, MSGBOX_DEFAULT
	release
	end

LilycoveCity_House1_EventScript_NotRequestedMon::
	bufferspeciesname STR_VAR_1, VAR_0x8009
	msgbox LilycoveCity_House1_Text_ThatsNotMon, MSGBOX_DEFAULT
	release
	end

LilycoveCity_House1_EventScript_TradeCompleted::
	msgbox LilycoveCity_House1_Text_TradeCompleted, MSGBOX_DEFAULT
	release
	end

LilycoveCity_House1_Text_WantToTrade:
	.string "My {STR_VAR_2} licks everything in\n"
	.string "sight. I'd like something calmer.\p"
	.string "Will you trade me a {STR_VAR_1}\n"
	.string "for my {STR_VAR_2}?$"

LilycoveCity_House1_Text_TakeGoodCare:
	.string "It likes to lick. You'll get used\n"
	.string "to it. Take good care of it!$"

LilycoveCity_House1_Text_ThatsTooBad:
	.string "Oh… That's too bad.$"

LilycoveCity_House1_Text_ThatsNotMon:
	.string "Hm? That isn't a {STR_VAR_1}.$"

LilycoveCity_House1_Text_TradeCompleted:
	.string "The POKéMON you gave me just\n"
	.string "naps all day. It's perfect!$"

LilycoveCity_House1_Text_PokemonPartnersNotTools:
	.string "POKéMON are partners to people.\n"
	.string "They aren't our tools.\p"
	.string "Unfortunately, there are some people\n"
	.string "who fail to understand that…$"

LilycoveCity_House1_Text_Kecleon:
	.string "KECLEON: Ruroro?$"

