# BPE Emerald -- Bug Reports
_Condensed from Discord #bug-reports (620 messages, exported 2026-06-10)_
_Distinct issues after deduplication: **256**_

## Summary

| Severity | Count |
|----------|-------|
| Critical | 7 (1 resolved emulator issue, 1 code fix applied, 1 already fixed/stale) |
| High | 28 |
| Medium | 221 |
| Low | 0 |

---

## Critical

### Starter battle (Zigzagoon) crash/freeze — ✅ RESOLVED (not a code bug)
- **Category:** Pokémon/Species
- **Reports:** 12 similar reports, 3 reactions, 1 confirmations
- **First reported:** 2024-08-31 by ItsJohn 😑
- **Details:** May I asked? It's my first time playing Pokemon BlackPearl Emerald, it got me interested when I was reading the ROM, but when I played and picked my first pokemon the moment I'm going to battle the wild zigzagooon my game freezes I tried every starter
- **Triage (2026-07-01):** Traced full code path (`Route101_EventScript_BirchsBag` → `ui_birch_case.c` → `StartFirstBattleOnly` → `SetUpBattleVarsAndBirchZigzagoon` → `CreateWildMon`) — matches upstream pokeemerald-expansion behavior, starter is correctly given to the party before the battle starts, Zigzagoon's species data is unremarkable (and wild Zigzagoon encounters work fine everywhere else in the game). Pulled the raw Discord export and found all 5 underlying threads: every reporter who disclosed their emulator was on **MyBoy** (or an unspecified "Game Boy emulator" a community member correctly guessed as MyBoy); switching to Pizza Boy or mGBA resolved it every time. Dev (Captain Cole) told reporters "MyBoy is not recommended for Romhacks" three separate times in these threads. No confirmed mGBA report of this freeze exists in the log. **Conclusion: MyBoy-specific emulator incompatibility (likely its imprecise HLE BIOS/DMA timing choking on the back-to-back custom-UI → battle-transition graphics teardown/reload unique to this scene), not a BPE code defect. Action: document as a known MyBoy incompatibility (README/pinned message: use mGBA or Pizza Boy) rather than a code fix.**

### Bad Egg crash (electric arena) — 🔧 FIX APPLIED + superseded by official 1.16.2 upstream fix (2026-07-01, pending in-game playtest)
- **Category:** Battle
- **Reports:** 6 similar reports
- **First reported:** 2024-12-29 by ItsRegger
- **Details:** my friend ran into it at the weather institute with the double battle of the aqua grunts. they both have 4 mons each, so when she went to the double battle, the 6th one got thrown out as a bad egg. i thought its some sort of overflow or underflow error
- **Root cause (confirmed 2026-07-01):** `EFFECT_KNOCK_OFF` and `EFFECT_STEAL_ITEM` in `src/battle_move_resolution.c` gated their item-removal effect on `IsAnyTargetTurnDamaged(battlerAtk, ...)`, which loops over *every other battler on the field* and returns TRUE if *any* of them took damage this turn — not specifically whether the move's actual target did (`src/battle_util.c:10635`). In a double battle, if the target had already fainted earlier in the same turn from a different attacker, this guard still passed (because *someone* on the field was hurt that turn), so the move's item-removal effect fired against an already-vacated/about-to-be-replaced battler slot. The subsequent `BtlController_EmitSetMonData(..., REQUEST_HELDITEM_BATTLE, ...)` write is deferred and resolves the target party slot via `gBattlerPartyIndexes[battler]` read at processing time (`battle_controllers.c:2317`), so once the fainted mon's replacement was sent in, the held-item write landed on the new mon's encrypted party data instead — corrupting it into a checksum-invalid "Bad Egg." Only manifests in doubles (in singles there's only one "other battler," so the check is harmless there), matching every report (Weather Institute Aqua Grunts, a detailed Greninja/Basculegion report, Electric Arena).
- **Verified against upstream:** BPE's `main` was 69 commits behind `RHH/master` (122 behind `upcoming`) at time of investigation. Upstream has already reworked this exact code as part of a large, unrelated 393-line MoveEnd/CalcValue refactor (commit `3e3b79d916`, "Fix Thousand Arrows not grounding both targets #10354") — too entangled to safely backport wholesale. But the corrected predicate upstream now uses (`IsBattlerTurnDamaged(battlerDef, ...)`) is a helper that already existed unchanged in BPE's current code (`include/battle.h:1102`), so the fix was portable as an isolated 2-line change.
- **Fix applied:** swapped `IsAnyTargetTurnDamaged(cv->battlerAtk, EXCLUDING_SUBSTITUTES)` → `IsBattlerTurnDamaged(cv->battlerDef, EXCLUDING_SUBSTITUTES)` in both the `EFFECT_KNOCK_OFF` (line ~3459) and `EFFECT_STEAL_ITEM` (line ~3498) cases in `src/battle_move_resolution.c`. Confirmed clean incremental rebuild (32MB ROM, no new warnings/errors). **Not yet playtested in-game** — recommend a manual double-battle repro test (intentionally KO a Knock-Off/Thief target with one attacker while another attacker's Knock Off/Thief also targets it the same turn) before calling this fully verified.

### Taxi Ticket softlock on Slateport Beach — ✅ ALREADY FIXED (stale report, resolved 2024-08-25)
- **Category:** Overworld
- **Reports:** 2 similar reports
- **First reported:** 2024-08-23 by CD💿
- **Details:** DO NOT USE TAXI TICKET ON SLATEPORT BEACH, PRIOR TO ENTERING SLATEPORT CITY. YOU WILL SOFTLOCK THE GAME, MR BRINEYS BOAT WILL BE ON SLATEPORT BEACH, AND YOU WILL HAVE NO WAY BACK THERE.
- **Investigation (2026-07-01):** Root cause was that Route109 ("Slateport Beach," where Mr. Briney's boat lands you) has no fly spot of its own, and Slateport City itself wasn't yet marked "visited"/flyable until the player physically walked into its map — so using the Taxi Ticket immediately after landing at Route109 left no valid fly destination to reach that area again, stranding the boat. Confirmed via the raw Discord export that the dev (CD) diagnosed and fixed this personally: a teammate ("Danni") found the exploit, and CD's own follow-up two weeks later (2024-09-07) explains the fix as intentional ("before you could softlock if u took the boat to slateport beach, but then used the taxi ticket to fly back... The boat would be stuck at Slateport beach, and not reachable again"). `git blame` on `data/maps/DewfordTown/scripts.inc` confirms: line 33 (`setflag FLAG_VISITED_SLATEPORT_CITY`) was committed by CD on **2024-08-25**, two days after the original report — it fires the moment the player chooses to sail to Slateport, registering Slateport City as flyable before the boat animation even plays. Verified this line is still present and reachable from current `main` HEAD (last touched 2026-03-17, survived every subsequent version upgrade). **No further fix needed; this bug report is stale.**
- **Unrelated bonus finding:** while tracing Mr. Briney's location-tracking (`VAR_BRINEY_LOCATION`), found that every boat-trip script (`DewfordTown_EventScript_SailToSlateport`, `Route109_EventScript_DoSailToDewford`, etc.) ends with `copyvar VAR_BRINEY_LOCATION, VAR_0x8008`, which restores the *pre-trip* location instead of the new destination (nothing ever writes the new value into `VAR_0x8008` first). This only affects `EventScript_ResetMrBriney`, which is exclusively called from the literal Teleport field effect (`fldeff_teleport.c`), not Fly/Taxi Ticket — so it's unrelated to this bug and not confirmed to cause any current player-facing issue (the `Common_EventScript_UpdateBrineyLocation` self-heal on Pokémon Center visits likely papers over it pre-Petalburg-Gym). Not actioned; flagging for awareness only.

### Lycanroc / Rockruff evolution freeze — 🔧 "always Midday" FIXED (2026-07-01); freeze unconfirmed
- **Category:** Pokémon/Species
- **Reports:** 2 similar reports
- **First reported:** 2024-09-07 by jit
- **Details:** no matter what time I evolve my rockruff it becomes midday lycanroc and when it evolves the game freezes
- **Investigation (2026-07-01):** Pulled the full raw Discord thread — the reporter themselves said "freeze was a one time thing thankfully" and never reproduced it again; no other Lycanroc-freeze report exists anywhere else in the 620-message export. Treating the freeze as a non-issue (likely an unrelated one-off) unless it resurfaces. The "always evolves to Midday" part was real and root-caused: Rockruff's evolution is correctly time-gated (`IF_TIME`/`IF_NOT_TIME` against `TIME_NIGHT` in species data), and the underlying `GetTimeOfDay()`/`UpdateTimeOfDay()` machinery is correct — but the **Pocket Watch item** (BPE's intended workaround for unreliable GBA RTC emulation on most emulators) was a literal unfinished stub (`// CODE HERE FOR POCKET WATCH`) that just reopened the vanilla Wall Clock screen, which only offsets the *real hardware RTC* — ineffective on emulators without proper RTC support, which is most of this playerbase (matches the dev's own Discord comment: "Some emulators you can use the pocket watch key item for evolutions, some will reference real life time"). Also confirmed the project's `OW_USE_FAKE_RTC` config is `FALSE`, so even the debug menu's own time-changer (`FakeRtc_ForwardTimeTo`) is a no-op for actual gameplay time in this build.
- **Fix applied:** reimplemented `ItemUseOutOfBattle_PocketWatch` (`src/item_use.c`) to show a Morning/Day/Evening/Night choice menu (new `EventScript_PocketWatch` in `data/event_scripts.s`, new `MULTI_POCKET_WATCH` multichoice list) that calls the pre-existing but previously-unused `SetTimeOfDay()` override (`src/overworld.c`), which `UpdateTimeOfDay()` already prefers unconditionally over the real RTC — making time-of-day fully emulator-independent. Clean build (32MB ROM, no new warnings), pushed to main. **Likely also fixes the broader reported cluster of "time-based evolution doesn't work" (Amaura→Aurorus, Linoone→Obstagoon, Greavard's line) since they share the same root mechanism** — not independently verified per-species, but worth re-testing if those resurface. Not yet playtested in-game.

### Togekiss Calm Mind freeze
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-10-13 by SpookCrab

### This guys are crashing my game
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-28 by dog

### Mi juego se crashea apenas inicio el juego alguna solución?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-18 by Vinny

## High

### MyBoy emulator incompatibility
- **Category:** Emulator Compat
- **Reports:** 7 similar reports, 1 confirmations
- **First reported:** 2024-09-04 by Gustav
- **Details:** Wake me up when this game could run with MyBoy! pls im begging yall 🥺

### Wrong Pokemon in trainer teams
- **Category:** Battle
- **Reports:** 2 similar reports
- **First reported:** 2024-12-06 by AlWar
- **Details:** In Gym3 Split AmyAndLiv3 have wrong pokemon in the docs (I fought Jolteon and Lanturn) Joseph Pokemon are missing moves in the docs

### EXP not gained after level 15
- **Category:** Battle
- **Reports:** 3 reactions
- **First reported:** 2025-03-16 by Dian-Keto
- **Details:** Hello, my pokemon don’t reach exp. After level 15 every battle it takes 0 exp. Why????

### Got the wrong sprite
- **Category:** Graphics
- **Reports:** 2 similar reports
- **First reported:** 2024-08-25 by Silvanor

### I'm able to catch multiple pokemon on the one the same route all over sudden on nuzlock mode...
- **Category:** Overworld
- **Reports:** 1 confirmations
- **First reported:** 2024-08-25 by nexo
- **Details:** I'm able to catch multiple pokemon on the one the same route all over sudden on nuzlock mode (the notice "already catched your encounter on this route" or whatever doesnt appear anymore) tested multiple old routes. It worked properly and stopped working after beating the 5th /petalburg gym). The nuzlock mode in general seems to work fine still. I tested some dead mons from my PC and they are still dead and stay dead even after using the...

### I Just remembered this but this bugged/glitched pokemon Sprite shows up in the credits after you...
- **Category:** Graphics
- **Reports:** 1 confirmations
- **First reported:** 2024-09-12 by furius2
- **Details:** I Just remembered this but this bugged/glitched pokemon Sprite shows up in the credits after you beat the e4

### Obv you're correct, I was just trying to get ahold of someone to say something. I'm avoiding...
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-11-13 by AeternusMactus
- **Details:** Obv you're correct, I was just trying to get ahold of someone to say something. I'm avoiding saying how it works in the group to make sure it doesn't turn into an exploit for people to beat the game

### Tyrantiarite and Mawilite are missing. Need to add in next update. @Captain Cole
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2026-04-09 by CD💿

### Hidden trainer visible in 4th gym
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-18 by sirchuggs0100
- **Details:** Not game breaking but in the fourth gym I can see a little bit of a head where a hidden trainer is

### I don't know if others have mentioned it, but in the current version there's a bug in the first...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Eric ǃ
- **Details:** I don't know if others have mentioned it, but in the current version there's a bug in the first gym. Bulldoze is supposed to auto hit and deal double damage when the opponent is using Dig, but it still misses Onix when I try.

### Unless I’m missing something
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by alvin9456

### Only other thing I bought was an upgrade to evolve my Porygon
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-26 by alvin9456

### it just wouldnt evolve despite the in game clock being set to night
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### its lvl 33 now, still didnt evolve
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### it took 52 points of damage, swapped out so it didnt die and when i lvled it up it didnt evolve...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon
- **Details:** it took 52 points of damage, swapped out so it didnt die and when i lvled it up it didnt evolve either

### Amaura evo isnt working; set both computer and in game time to night; didnt work tyrunt evolved...
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon
- **Details:** Amaura evo isnt working; set both computer and in game time to night; didnt work tyrunt evolved just fine, i think its just the night mecanic itself that isnt working

### i keep having to make new teams for each badge because we cant use otems in battle
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### Which badge are you going for now?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by Mini

### Um, for some reason Synchronize doesn't work on wild battles as much as Vanilla Emerald's...
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-09-03 by RealGpsboy97
- **Details:** Um, for some reason Synchronize doesn't work on wild battles as much as Vanilla Emerald's mechanics were. When I used a Level 42 Synchronize Beheeyem raised from an egg, it still wouldn't let me find the nature I wanted even if it was like 10+ catches...

### I dont think this is a bug per say, but CD idk if you knew this when you included Tera Blast in...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-07 by FDMajora
- **Details:** I dont think this is a bug per say, but CD idk if you knew this when you included Tera Blast in the gym 5 TM bundle?

### Pokemon Linoone can't evolve form 3 at night. Is it a bug? Now I have upgraded to level 42....
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-09-29 by sEaRtHs
- **Details:** Pokemon Linoone can't evolve form 3 at night. Is it a bug? Now I have upgraded to level 42. After adjusting the time, it hasn't changed. Can you help me check

### i think the tyrogue evo might be bugged im tryna get hitmontop and my tyrogue is holding...
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2024-10-11 by CyanChip
- **Details:** i think the tyrogue evo might be bugged im tryna get hitmontop and my tyrogue is holding protective pads and isnt evolving when leveling up

### weird lil bug. When Nuzlocking on Route 104 I can never get my encounter. I sometimes have the...
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-10-15 by Toasty
- **Details:** weird lil bug. When Nuzlocking on Route 104 I can never get my encounter. I sometimes have the bug where it lets you catch a second mon on random routes, but route 104 is always broken for me for some reason

### in Mossdeep, the guy at the entrance of the gym says the gym is a Psychic-type gym still, and...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2025-06-08 by Korremar
- **Details:** in Mossdeep, the guy at the entrance of the gym says the gym is a Psychic-type gym still, and the karate guy just south of the town that teaches DynamicPunch claims he can't beat the gym because he's a Fighting-type trainer, but the gym is a Normal-type gym

### mega doc says you can only catch one of the legendaries pre-e4 but
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2025-06-11 by Korremar

### Seems like a TM for Superpower is missing.  Its not in the bag and not in the doc.
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2025-07-25 by ZachDevelop
- **Details:** Seems like a TM for Superpower is missing. Its not in the bag and not in the doc.

### also i want to comment about Petalburg City encounter. I found out that Snorlax Encounter before...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2026-04-09 by Kuro
- **Details:** also i want to comment about Petalburg City encounter. I found out that Snorlax Encounter before going to the Petalburg City Gym and Petalburg City encounter are separated while Mirage Tower and Route 111 are not separated encounter

### Where is Steven ? He's supposed to be here and help me with the invisible pokemon that blocked...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2026-04-11 by Kuro
- **Details:** Where is Steven ? He's supposed to be here and help me with the invisible pokemon that blocked my way to gym 6

## Medium

### Wrong trainer sprite in Battle Tents
- **Category:** Battle
- **Reports:** 3 similar reports
- **First reported:** 2024-09-26 by DonkeyTeethMcGee
- **Details:** I'm sure this has been brought up before but the wrong character sprite loads up in the battle tents. Cynthia's sprite shows once you enter the arena to battle. Not game breaking by any means, but thought it was interesting the first time it happened.

### is the sprite correct for move tutor at odale town? (V1.0)
- **Category:** Overworld
- **Reports:** 3 reactions, 1 confirmations
- **First reported:** 2024-08-25 by A Start Gaming

### Pokedex owned count wrong
- **Category:** Pokémon/Species
- **Reports:** 2 similar reports
- **First reported:** 2025-07-26 by ZachDevelop
- **Details:** Possibly its just earlier evolutions don't count. So, if I caught a Gyarados, Magikarp isn't in the pokedex as caught, and when I encounter it in a new route it does not count as a dupe.

### Magnitude move issues
- **Category:** Misc
- **Reports:** 2 similar reports
- **First reported:** 2024-08-25 by Eric ǃ

### Trick House quiz typos
- **Category:** Scripts/Text
- **Reports:** 2 similar reports
- **First reported:** 2025-06-04 by Korremar
- **Details:** found a typo in the Trick House quiz - when the question asker asks which mon didn't get a Paradox form, one of the answers is Jigglybuff

### (Fight wasMagma Hideout Grunt 1, idk if it's circumstantial)
- **Category:** Battle
- **Reports:** 2 similar reports
- **First reported:** 2025-05-10 by Deleted User
- **Details:** (Fight wasMagma Hideout Grunt #1, idk if it's circumstantial)

### I've tried on my phone first then that didn't work
- **Category:** Misc
- **Reports:** 2 similar reports
- **First reported:** 2024-09-13 by JackPrino

### Hey so on Route 107, the opposing trainers' priority moves don't seem to be working on my...
- **Category:** Battle
- **Reports:** 1 reactions, 1 confirmations
- **First reported:** 2024-12-30 by MagicalGirlLaurie
- **Details:** Hey so on Route 107, the opposing trainers' priority moves don't seem to be working on my Kilowattrel. Queenly Majesty pops up, and while I do have a Tsareena in my party, she's not in battle rn, so Idk why that would pop up.

### Gallade can't relearn Psychocut from the Move Tutor
- **Category:** Battle
- **Reports:** 2 similar reports
- **First reported:** 2025-06-25 by nerdygamer7057

### Gengarite, Tyranitarite, Garchompite, Audinite, Mawile, Choice Band, Choice Specs, Choice Scarf...
- **Category:** Misc
- **Reports:** 2 similar reports
- **First reported:** 2026-04-09 by Kuro
- **Details:** Gengarite, Tyranitarite, Garchompite, Audinite, Mawile, Choice Band, Choice Specs, Choice Scarf are TrickHouse's Rewards after finishing 8 Rooms

### Black Glasses NPC dialogue loop
- **Category:** Overworld
- **Reports:** 2 reactions
- **First reported:** 2024-08-26 by Silvanor
- **Details:** After showing the guy "Black Glasses" because we know we can never find his glasses any where. He starts walking and he walks through the tree that can be cut.

### After you beat the game, or lose the nuzlocke mode, it will heal everything and disable nuzlocke...
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-08-25 by CD💿
- **Details:** After you beat the game, or lose the nuzlocke mode, it will heal everything and disable nuzlocke mode

### Appreciate the bug dumping Gobou. There was only so much we could find with the 3 devs... lol
- **Category:** Battle
- **Reports:** 1 confirmations
- **First reported:** 2024-08-28 by CD💿

### Stats menu shows the nature that the mon had before using a Mint on it (I used a Jolly Mint on...
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-08-28 by GobouLePoissonBoue
- **Details:** Stats menu shows the nature that the mon had before using a Mint on it (I used a Jolly Mint on that one)

### I've seen a weird bug where the game has no text at all for me. is there a fix?
- **Category:** Scripts/Text
- **Reports:** 1 confirmations
- **First reported:** 2024-08-29 by Jae

### Game froze as soon as I released my stater
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-08-31 by DIEZEL-BUG

### I thought maybe it would be like just a special attack version of return, or it could be used...
- **Category:** Battle
- **Reports:** 2 reactions
- **First reported:** 2024-09-07 by FDMajora
- **Details:** I thought maybe it would be like just a special attack version of return, or it could be used sort of like judgement, but looks like not

### cuz my game froze lol
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-09-13 by JackPrino

### It seems there's an Alakazam on route 119 with thunderbolt.
- **Category:** Overworld
- **Reports:** 1 confirmations
- **First reported:** 2024-09-13 by Danni
- **Details:** It seems there's an Alakazam on route 119 with thunderbolt. Uh. That's illegal.

### That electrode looking at the swampert/whiscash/quagsire you send out to fight it “I’m about to...
- **Category:** Battle
- **Reports:** 1 confirmations
- **First reported:** 2024-09-13 by FDMajora
- **Details:** That electrode looking at the swampert/whiscash/quagsire you send out to fight it “I’m about to end this mon’s whole career”

### greavard is not evolving even when time is set to a night hour
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-09-13 by duskhakaishin

### actually i think its just this trainer
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2024-10-13 by SpookCrab

### Hello, my nuzlocke mode broke, after completing this event and defeating my enemy in route 110,...
- **Category:** Overworld
- **Reports:** 2 reactions
- **First reported:** 2024-10-15 by LuisPgtz
- **Details:** Hello, my nuzlocke mode broke, after completing this event and defeating my enemy in route 110, I notice was allowed to heal faint Pokemons and capture more than once per route, is there a way to turn it on again?

### Hey guys, I am playing on normal version and have received the rare candy jar. I thought this...
- **Category:** Misc
- **Reports:** 2 reactions
- **First reported:** 2025-03-19 by Matt.exe
- **Details:** Hey guys, I am playing on normal version and have received the rare candy jar. I thought this jar is only received when playing nuzlock. Is this a bug?

### During a battle in the abandoned ship the game freaked out and froze here
- **Category:** Battle
- **Reports:** 1 confirmations
- **First reported:** 2025-03-25 by Matt.exe

### alr
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2025-03-30 by Balu  | バルテキャット
- **Details:** alr i was a bit worried about that

### yeah...if people use this..the game would be too easy😅
- **Category:** Misc
- **Reports:** 1 confirmations
- **First reported:** 2025-03-30 by Balu  | バルテキャット
- **Details:** yeah...if people use this..the game would be too easy😅 btw you can delete the image if you want

### I'm surfing on 134, I fished with a Super Rod, and for some reason it displays the "Oh! A bite!"...
- **Category:** Overworld
- **Reports:** 1 confirmations
- **First reported:** 2025-06-08 by Korremar
- **Details:** I'm surfing on 134, I fished with a Super Rod, and for some reason it displays the "Oh! A bite!" text multiple times before it actually sends me into a battle

### Portable PC is known to spawn random tiles in places (For example, using it on Mt. Chiminey...
- **Category:** Battle
- **Reports:** 2 reactions
- **First reported:** 2025-08-10 by Deleted User
- **Details:** Portable PC is known to spawn random tiles in places (For example, using it on Mt. Chiminey spawns a flower tile on the edge of the volcano) but in Weather Institute you can just spawn PCs on almost any tile, interacting with any of them will spawn a PC on the tile above. Very funny way to soflock yourself if you box yourself in on the right

### Idk what this is but i cant progress in trick house or the game past this one battle
- **Category:** Overworld
- **Reports:** 1 confirmations
- **First reported:** 2025-09-28 by Demon Days

### This trainer has a shedinja as 4th mon
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2024-08-25 by Vale

### Any help with uploading the patch file to the rom?  Every time I upload the base emerald...
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2024-08-25 by TheTutmeister27
- **Details:** Any help with uploading the patch file to the rom? Every time I upload the base emerald edition, the patch file is dithered when trying to select it.

### Note to self
- **Category:** Battle
- **Reports:** 1 reactions
- **First reported:** 2024-08-29 by furius2
- **Details:** Note to self Don't use volt switch into a golisopod that switched out due to its ability

### Ah I forgot that's how that worked okay thanks
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2024-08-30 by bluarcticwolf

### interesting corv set
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2024-08-30 by Flare

### I messed it up to where CD had to implement that. XD
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2024-09-07 by Danni

### i got it working now
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2024-09-13 by JackPrino

### It says its unseeable but its not
- **Category:** Scripts/Text
- **Reports:** 1 reactions
- **First reported:** 2024-09-27 by knives

### So it said it was hurt by poison twice in the same turn and died on its own??
- **Category:** Misc
- **Reports:** 1 reactions
- **First reported:** 2026-04-14 by olive

### Freeze-Dry accuracy issue (Sand Veil?)
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-03 by GobouLePoissonBoue
- **Details:** And, dunno if I'm just terribly unlucky but... I missed 4/4 Freeze-Drys on a Dugtrio under sandstorm, maybe a bug related to Sand Veil?

### Lusamine portrait/art issue
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2026-05-10 by Kuro

### So does Bulbapedia. That's on me. Sorry for wasting your time, guys.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Eric ǃ
- **Details:** So does Bulbapedia. That's on me. Sorry for wasting your time, guys.

### I used my serious mint on my jolly roselia
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### I deposited it in pc, it's back to being jolly again
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### Iirc it said serious, lemme recheck
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### suggestition we make a jira for ticketing
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Dr Huntersteel 🛠

### another one ;
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Dr Huntersteel 🛠
- **Details:** another one ; whenever i catch a new pokemon number is 000

### I'm fighting the nidoqueen trainer and
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### There's a rogue vespiquen
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### The turtonator trainer has a cincinno too
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### God it's a technician cincinno
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### All the trainers have 3 mons each but only two are documented
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### ( correct me please if i am wrong )
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Dr Huntersteel 🛠
- **Details:** ( correct me please if i am wrong ) wattrel got k.o by a dig ? ( isn't his supposed to be elec-fly )

### You probably landed? Certain things will cause you to “land” and get hit by ground moves. Its a...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by CD💿
- **Details:** You probably landed? Certain things will cause you to “land” and get hit by ground moves. Its a newer gen mechanic

### ye that's probs what happened
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### is the candy jar only suppose to be on nuzlock mode? cause I got it on standard mode
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Boots

### It's supposed to be on both now
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Vale

### So uh. Aaron's Heracross has flamethrower. Why?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Danni

### No prob. If it helps.That it's moveset in the official guide.
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Danni
- **Details:** No prob. If it helps.That it's moveset in the official guide.

### I don’t think that’s right… heracross can’t learn dragon breath or flamethrower lol
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Captain Cole

### Oh, do you recommend another one?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by dog

### Not sure if this is intentional based on the way the mega doc is laid out- but each floor of...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Arom25
- **Details:** Not sure if this is intentional based on the way the mega doc is laid out- but each floor of Granite cave counts towards the same encounter but Stevens room is a separate encounter?

### Pizza controller low key weird
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Silvanor

### It works but it feels weird
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Silvanor

### I played as a male character but it doesn't seem to match
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Silvanor

### Found a bug in route 114
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Silvanor

### Able to jump on top of an item which makes the player overlaps with item on the ground
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Silvanor

### Near the house of the lady who created the PC system
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-25 by Silvanor

### Idk if it’s a bug but nuzlocke mode is supposed to be inf money. I ran out after buying Vitamins.
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-25 by alvin9456
- **Details:** Idk if it’s a bug but nuzlocke mode is supposed to be inf money. I ran out after buying Vitamins.

### But I’m not sure if that’s when I didn’t have inf money
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-26 by alvin9456

### EVs are not in the game?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Danni
- **Details:** *EVs are not in the game?* Sorry Eevee. Another time.

### It’s a joke based on the spelling of EV and Eevee.
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Danni
- **Details:** It’s a joke based on the spelling of EV and Eevee.

### Damnnn. Oh well lol thx
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-26 by alvin9456

### Found a small error in route 116
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Silvanor

### I honestly have no clue how that works... lol... gonna have to dig deep into fixing that one
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-26 by CD💿

### area catching considers that you've already caught a mon in an area when you use save states in...
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-26 by eunuc
- **Details:** area catching considers that you've already caught a mon in an area when you use save states in emulator. (nuzlocke mode)

### Suggestion, please put a "reset" on The editor option (select on battle scene)
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-26 by dog
- **Details:** Suggestion, please put a "reset" on The editor option (select on battle scene) I Just reset my pokemon moveset and I cant remember The moveset

### Not sure if a bug or just regular emerald but I used max repel in mirage tower and it didn’t work
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Gilly

### Yes definitely and it even says the effect of a repel lingers from earlier
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Gilly

### I’ll try leaving and reentering
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Gilly

### Ah maybe my mons are lower level than the towers average level
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-26 by Gilly

### i don't know how true this is but when i fought amy and liv they only had a jolteon and lantrun...
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-27 by Astrosoul
- **Details:** i don't know how true this is but when i fought amy and liv they only had a jolteon and lantrun but on the docs it shows a completely different team.

### @CD💿  so that’s why I couldn’t get the shiny honedge
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-27 by Mini
- **Details:** @CD💿 so that’s why I couldn’t get the shiny honedge

### ( i have no idea why it shows up, something to do with bringing up the menu on that tile)
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-27 by Read the FAQ and use google

### as its normal electrode it should not have chloroblast, unless that was a change made in this rom
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by furius2

### Don't use game boy emulator..
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-08-28 by Rehan
- **Details:** Don't use game boy emulator..

### after you do the grunt fight in rusturf tunnel the trainer by the fighter that's meant to be a...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-28 by Astrosoul
- **Details:** after you do the grunt fight in rusturf tunnel the trainer by the fighter that's meant to be a double by the item moves

### This was encounter 65
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-28 by furius2
- **Details:** This was encounter 65 So don't think its working like its supposed to

### on the same trainer, swampert does not get aqua jet but again that would be a fun buff for it
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by furius2

### took almost 3 hours, but this should be (hopefully) all the mons that have an illegal move...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-28 by furius2
- **Details:** took almost 3 hours, but this should be (hopefully) all the mons that have an illegal move listed on the doc in order for each split. For each split i first name the mon and after it which move they normaly can't get( i hope i did this correctly)

### Delta works great too
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by Reks117

### Eh,who cares,im gonna go play superstar saga
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by stevevets

### Pearl description is a bit too long aha
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2024-08-28 by GobouLePoissonBoue

### (Notice how the "for" goes outside the box?)
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by GobouLePoissonBoue

### (Its single eye didn't even notice I'm a girl 🥴)
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by GobouLePoissonBoue

### Dusclops does not cater to our concept of gender everyone is bröther to him
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by Awakeon 2.0

### Now do it with one dev
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-28 by Awakeon 2.0

### ...is that NPC supposed to teleport here after I beat the Aqua Grunt in the cave?
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-29 by GobouLePoissonBoue
- **Details:** ...is that NPC supposed to teleport here after I beat the Aqua Grunt in the cave? The girl is supposed to be in the circled spot in that screenshot, and the Black Belt is supposed to move instead, to allow player to go inside the house

### "These" nah it was just one Ability Capsule
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-29 by GobouLePoissonBoue

### what's bro doing here (route 110/103)
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-29 by GobouLePoissonBoue

### All of these NPCs don't turn around when talked to
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-29 by GobouLePoissonBoue

### Normal shop in trainer tower, on route 111
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-29 by GobouLePoissonBoue

### G yamasks evo seems to be bugged, it took 49 points of damage, switched and killed the mon and...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-29 by luludracon
- **Details:** G yamasks evo seems to be bugged, it took 49 points of damage, switched and killed the mon and lvled it up but no evo

### I tried to reinstall but it still occurs.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-29 by Jae
- **Details:** I tried to reinstall but it still occurs.

### My gyarados getting hit with thunderpunch activated the dragonite's enigma berry
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2024-08-29 by furius2

### It is just a little seeable
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-29 by yakir22

### I just started my playthrough on a nuzlocke run and the first 3 routes all say ove already...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-30 by bluarcticwolf
- **Details:** I just started my playthrough on a nuzlocke run and the first 3 routes all say ove already caught a pokemon on that route even though I only have my starter. Is there a fix for this or do I need to restart?

### thats nuzlocke rule. One encounter per route. If you killed or run away it considered that. So...
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-08-30 by _-Eth@n-_
- **Details:** thats nuzlocke rule. One encounter per route. If you killed or run away it considered that. So you need to catch the first poke you encounter.

### You can always move to another route if you don't like the pokemon that you've enocuntered.
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-30 by _-Eth@n-_
- **Details:** You can always move to another route if you don't like the pokemon that you've enocuntered.

### THEY BUFFED CORVIKNIGHT
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-30 by Awakeon 2.0

### i almost lost a mon to a fucking corv eq
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-30 by Flare

### I should attack the first with shadow sneak right ?
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-31 by Anis

### Oh you are right my bad
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by Anis

### so did any1 ever test if A rattata is bugged like it seems to be?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### yea ive got a tab in the guide im working for bugged evos i find
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### G yamask isnt working either
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### Just got Eon Ticket and Old Sea Map buttt neither ferry gives me the option to go to those...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-08-31 by Vhale92
- **Details:** Just got Eon Ticket and Old Sea Map buttt neither ferry gives me the option to go to those places, does that only work post champ

### Damn. Can you recommend a android emulator
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-08-31 by DIEZEL-BUG

### Could you send like an image of it?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by DIEZEL-BUG

### I looked but I'm not sure if it's right
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by DIEZEL-BUG

### ill put it in general as its not supposed to be conversed here
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### whats wrong with this image?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### exactly, does tell me i can skip a trainer tho
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by luludracon

### So we gotta fix it so players don’t see it and have an easier time suffering
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-08-31 by Mini

### Ngl… recoding that whole script was very annoying and overly difficult for no go reason. Im not...
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2024-08-31 by CD💿
- **Details:** Ngl… recoding that whole script was very annoying and overly difficult for no go reason. Im not surprised I messed up.

### I'm using Visual boy advance
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2024-09-01 by AbsorbedFire#8970

### Retro arch and pizza boy works maybe you can try it dunno about vba
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-01 by Mohit

### Why can't I use flash to open the cave to catch registeel
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2024-09-02 by Zapdoszablai

### Where can I find Rotom?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-02 by Zapdoszablai

### You can jump on that ledge in route 112 to go inside a guy
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-09-03 by GobouLePoissonBoue

### That ninja boy on route 113 has a lv 20 team for some reason
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-09-03 by GobouLePoissonBoue

### Lanette goes through the move relearner in Fallarbor's Pkmn Center
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-09-03 by GobouLePoissonBoue

### It got me feels like i cant really enjoy the game tho 😭
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-04 by Gustav

### I just started  using it like  1 week ago
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2024-09-04 by Kingslayer19
- **Details:** I just started using it like 1 week ago

### When I was younger I used JOHN GBA
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-04 by Awakeon 2.0
- **Details:** When I was younger I used **JOHN GBA**

### Android I dont know, because I dont have an Android device. But ig Pizzaboy or Retroarch?
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-04 by CD💿

### Best DS emu is GBArunner (it can’t run anything with 32 MB)
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-04 by Awakeon 2.0

### And  pizzaboy ,:peepopog: retroarch
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-04 by Kingslayer19
- **Details:** And pizzaboy ,:peepo_pog: retroarch

### …What the hell did you do Ash
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-06 by Danni

### Bro what am I looking at?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-06 by Mini

### also, trick used by npc when you don't have an item and they do makes you permanently steal...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-09-06 by Ash
- **Details:** also, trick used by npc when you don't have an item and they do makes you permanently steal their item

### probably can use this as the player too
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-06 by Ash

### Idk if this is known already, but Hisuian Arcanine appears as “not able” at the egg move tutor,...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-07 by FDMajora
- **Details:** Idk if this is known already, but Hisuian Arcanine appears as “not able” at the egg move tutor, despite having the following moves listed as possible egg moves on bulbapedia/similar sites: Covet, double Kick, double edge, head smash, morning sun, thrash

### The dusclops seems to work fine like normal
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-07 by FDMajora

### I didnt check before evolving it, but other stone evos work fine so idk. Maybe the “egg moves”...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-07 by FDMajora
- **Details:** I didnt check before evolving it, but other stone evos work fine so idk. Maybe the “egg moves” list just didnt populate right/is blank?

### and the pocket watch seems to work for me because the overworld changes from day to night...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-09-07 by jit
- **Details:** and the pocket watch seems to work for me because the overworld changes from day to night whenever I use it

### whatever i’ll thug it out
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-07 by jit

### I would know. I’m the one that did that glitch.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-07 by Danni
- **Details:** I would know. I’m the one that did that glitch.

### Can I claim that name? ^^
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-07 by Danni

### Super minor thing but there's one random patch of grass and flowers on Mt. Chimney. It only...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-12 by tessatrix
- **Details:** Super minor thing but there's one random patch of grass and flowers on Mt. Chimney. It only showed up when I saved before I did the fight.

### First time playing this game why does it bug for me
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by JackPrino

### I tired many emulator
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-13 by JackPrino

### Does the game just hate me or something 😭
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by JackPrino

### Does anyone have sound problems when they go into battle or when they load the game
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-13 by Dipz

### Version 1.0.1 correct?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by JackPrino

### That’s the sound problem I am having
- **Category:** Audio
- **Reports:** 1 report
- **First reported:** 2024-09-13 by Dipz

### Am I just outta luck here?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by JackPrino

### It also works on My Retro Gameboy
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by ⁴ᴷ⁀➷Mood

### But I wouldn't suggest using that, it is one of the best mobile gba emulators but if ya don't...
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2024-09-13 by ⁴ᴷ⁀➷Mood
- **Details:** But I wouldn't suggest using that, it is one of the best mobile gba emulators but if ya don't wanna pay a subscription it's $30 to use it

### It works beautifully on pizzaboy
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-13 by Rika

### I’m trying play the game on my emulator rg35xxx and it won’t get pass the first battle
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-13 by kendallkendrickshan

### Doing its best starmie impression
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by FDMajora

### That is legit funny.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-13 by Danni
- **Details:** That is legit funny.

### Dunno if this belongs here but docs says smoliv has harvest but on the calcs it Doesnt have it
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2024-09-14 by Rika

### I looked into items blindly convincing myself its abilities
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2024-09-14 by Rika

### wtf, i was breeding for my poc what happened here?
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-15 by luludracon

### it charged me 25600 to pull him out
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-15 by luludracon

### Growth did not give +2 in Sun
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-15 by Last Light

### Is this can be play on android?
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-15 by Nag

### Not able to get sablenite from the granite cave.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-17 by dharani.r
- **Details:** Not able to get sablenite from the granite cave.

### yea ive pointed that one out
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-18 by luludracon

### not a bug just like
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-19 by duskhakaishin

### this pokemon is not weak to ice
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-19 by duskhakaishin

### thus this berry does nothing
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2024-09-19 by duskhakaishin

### i didnt know where else to put this
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-19 by duskhakaishin

### Infiniti respawn zapdos
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-23 by trupergum

### First room of Trick House, I opened my pc, which led to one pc next to the trainer, I clicked on...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-09-23 by .bracemino
- **Details:** First room of Trick House, I opened my pc, which led to one pc next to the trainer, I clicked on it, another one appeared, then another and so on

### That’s freaking impressive.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-23 by Danni
- **Details:** That’s freaking impressive.

### “So this is my gaming setup”
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-23 by .bracemino

### It didn’t affect the game in any other way tho, just a visual bug
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2024-09-23 by .bracemino

### And I can access the pcs too, dunno how it happened
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-23 by .bracemino

### i have the patched version but right at the beginning whichever starter i pick on standard mode...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-09-29 by Shadow
- **Details:** i have the patched version but right at the beginning whichever starter i pick on standard mode the game glitches out as soon as the pokemon are both on the field, there is no text and nothing happens afterward

### does anyone else have this issue?
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-29 by Shadow

### frequently-asked-questions
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-09-29 by Mohit
- **Details:** #frequently-asked-questions

### yes, ok i have the pizzaboy on my phone so ill try it there, are there any emulators for android...
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-29 by Shadow
- **Details:** yes, ok i have the pizzaboy on my phone so ill try it there, are there any emulators for android phone that are reccomended for this one?

### pizzaboy worked for now thank you DouglasQuilava
- **Category:** Emulator Compat
- **Reports:** 1 report
- **First reported:** 2024-09-29 by Shadow

### i fought a guy on route 109 (in the house) and he used dig w ursarang and brick break went...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-10-01 by CyanChip
- **Details:** i fought a guy on route 109 (in the house) and he used dig w ursarang and brick break went through the dig

### Not sure if it's a bug but have 'Flinched' a few Pokemon only for them to then attack straight...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-10-01 by ZacF97
- **Details:** Not sure if it's a bug but have 'Flinched' a few Pokemon only for them to then attack straight away and not miss that next move, typically happens against Megas or after an area affect

### Hey @CD💿 could you dm me. I think I found something that kinda breaks the nuzlock mode.
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-05 by Suppmain
- **Details:** Hey @CD💿 could you dm me. I think I found something that kinda breaks the nuzlock mode.

### the black augurite doesnt have a location. If it does its not posted in the mega doc
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-10-06 by rust

### kept getting the message from dad saying “u cant use that rn”
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-11 by CyanChip

### and when his alakazam used calm mind 😭
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-13 by SpookCrab

### anyone know how to fix this? i want to continue my run but i cant get past this traienr
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-14 by SpookCrab

### Ah es verdad aquí solo entienden ingles y tengo que traducirlo :Facepalm:
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-18 by Vinny

### my game just start and I choose the starter gets buggy, I dont know if there is any solution for...
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2024-10-18 by Vinny
- **Details:** my game just start and I choose the starter gets buggy, I dont know if there is any solution for that

### aaaand we back to dealing with this
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-10-18 by 𝓡𝓲𝓵𝓮𝔂 𝓴𝓾𝓴𝓸

### Hi, is galarian yamask evo bugged? I had it take 49 dmg in a single hit, got out of battle,...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2024-11-05 by Ryan
- **Details:** Hi, is galarian yamask evo bugged? I had it take 49 dmg in a single hit, got out of battle, didnt heal, then used a rare candy on it and no effect.

### I've found a backdoor. It makes battles dead simple, and ruins the gameplay :/
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-11-12 by AeternusMactus

### When I beat leader Jordan, the guy from the winged house is supposed to give me surf and he...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-12-02 by Richipm
- **Details:** When I beat leader Jordan, the guy from the winged house is supposed to give me surf and he doesn't give me anything

### My pokemons are bugged at level 15, I can't lvl up them
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2024-12-12 by BRFernandes011

### In the nuzlocke mode I found that when you have a fainted party member in the first slot you can...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2024-12-14 by AlphaBryce
- **Details:** In the nuzlocke mode I found that when you have a fainted party member in the first slot you can catch an infinite amount of pokemon anywhere no matter if you have caught one in that route

### Does anyone know if the day/night system for evolutions works, or has been fixed? I'm wanting to...
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2025-01-24 by Keebleron
- **Details:** Does anyone know if the day/night system for evolutions works, or has been fixed? I'm wanting to get an Aurorus, and nothing I try has worked so far.

### Some emulators you can use the pocket watch key item for evoluions, some will reference real...
- **Category:** Items
- **Reports:** 1 report
- **First reported:** 2025-01-24 by CD💿
- **Details:** Some emulators you can use the pocket watch key item for evoluions, some will reference real life time

### My screen keeps inverting colours whenever I'm outside a building and it's only the colours of...
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2025-03-01 by Lord_Zeref
- **Details:** My screen keeps inverting colours whenever I'm outside a building and it's only the colours of the outside ground that does this, might be a hardware issue idk

### Not really the place for asking questions but this rom uses lvl caps
- **Category:** Scripts/Text
- **Reports:** 1 report
- **First reported:** 2025-03-16 by furius2
- **Details:** Not really the place for asking questions but this rom uses lvl caps #questions-or-help

### also this was in the weather inst
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2025-03-29 by Deleted User

### It's actually kinda funny how many people mention it here tbh
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2025-03-30 by 𝓡𝓲𝓵𝓮𝔂 𝓴𝓾𝓴𝓸

### Its whatever honestly. Not gonna punish ppl for talking about it. It was unintenional to leave...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2025-03-30 by CD💿
- **Details:** Its whatever honestly. Not gonna punish ppl for talking about it. It was unintenional to leave it in. Ppl can hold themselves accountable and not cheat stuff in.

### Fair but that's not why I say it's surprising lol
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2025-03-31 by 𝓡𝓲𝓵𝓮𝔂 𝓴𝓾𝓴𝓸

### Covert cloak is bugged (I think), salt cure still activated on my Orthworm while holding
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2025-05-10 by Deleted User

### I caught latios, and was then able to catch mew
- **Category:** Pokémon/Species
- **Reports:** 1 report
- **First reported:** 2025-06-11 by Korremar

### Skarmory can't learn Roost from the egg move tutor
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2025-06-11 by Korremar

### Blaziken don’t get no fighting moves. Never gotten sky upper cut. Had to use brick break
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2025-06-14 by Zaylurk

### Ferroseed doesn't seem to dupe out properly if you encounter it again.  I've had this happen...
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2025-07-26 by ZachDevelop
- **Details:** Ferroseed doesn't seem to dupe out properly if you encounter it again. I've had this happen twice on different routes.

### The mega doc doesn't have the right sheet fr Amy and liv on route 110
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2025-09-29 by Goomba on a Roomba

### was just coming here to comment this lol^
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2025-11-06 by James

### they actually have a jolteon and a whiscash
- **Category:** Misc
- **Reports:** 1 report
- **First reported:** 2025-11-06 by James

### How can i interact with this one ? Or is it just a bug ? Spoiler Alert: || It's on route 105 ||
- **Category:** Overworld
- **Reports:** 1 report
- **First reported:** 2026-04-09 by Kuro

### Today i found a bug about Scale Shot. It seems like in some conditions, Scale Shot didn't...
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2026-04-11 by Kuro
- **Details:** Today i found a bug about Scale Shot. It seems like in some conditions, Scale Shot didn't activate it's secondary effect. Example: i used Sword Dance and then Scale Shot with my Haxorus, the defense didn't drop and the speed didn't increase

### So uh I had one Pokemon left on a double battle.. And yeah.
- **Category:** Battle
- **Reports:** 1 report
- **First reported:** 2026-04-14 by olive
- **Details:** So uh I had one Pokemon left on a double battle.. And yeah.

### Celebrity Giovanni didn't change his art
- **Category:** Graphics
- **Reports:** 1 report
- **First reported:** 2026-05-10 by Kuro
