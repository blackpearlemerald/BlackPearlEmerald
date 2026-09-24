# BPE built-in randomizer

Status: built on the `randomizer` branch and covered by `test/randomizer.c`;
waiting for the maintainer's mGBA playtest. The options and rules were agreed
with the maintainer on 2026-09-18. Where the build differs from the original
plan, this document describes what was built; "Assumptions to confirm" lists the
smaller choices made without asking.

## Outcome

Players can randomize a new game from inside BPE, in Standard or Nuzlocke mode,
without an external tool. Birch asks right after the Standard/Nuzlocke question.
The choices are locked for that save, like Nuzlocke mode. A short seed code
reproduces the same game on any save, so Soul Link partners and racers can share
one.

Why: the project Discord has had about 45 randomizer questions and requests
since August 2024. Most players want randomized Nuzlockes. Species and abilities
are what they name first. One group of 8 asked for Soul Link, and one player
asked for "all gens including megas". Universal Pokémon Randomizer does not
support BPE, so there is no workaround today.

Out of scope:

- A website spoiler log or seed viewer. The site keeps documenting the normal
  game.
- Randomizing Battle Frontier teams, marts, berry trees or prize corners.
- Turning the randomizer on, off or changing it on an existing save.
- Any change to the save format (see "Settings storage").

## What other hacks do

| Hack | Built-in randomizer | Chosen | Notable rules |
|---|---|---|---|
| Radical Red | Species (normal or "Scaled" to game progress), abilities, learnsets | Start of game, fixed | Bosses are never randomized |
| Unbound | Species (wild, trainers, gifts, trades), learnsets, abilities | New Game options | Route tables fixed once rolled; bosses keep teams on Expert/Insane |
| Elite Redux | Wild (Off / Normal / Legendary), abilities, innates, moves, types | New Game setup | Wonder Guard, Zen Mode, Huge/Pure Power banned; trainers no longer randomized |
| Emerald Imperium | Species (Normal / Scaled / legendary-aware), abilities | In game | Bosses never randomized |
| Modern Emerald (TheXaman) | Starters, wild, trainers, statics, legendaries, types, moves, abilities, evolutions, type chart, items, Chaos | New Game menu, locked | Key items fixed, TMs only swap with TMs; stateless hash of the trainer ID |
| pokeemerald-expansion PRs #3998 and #10125 (unmerged drafts) | Wild, items, statics, trainers, starters, moves, abilities | Compile time only | Stateless per-query RNG; a 6 KB species table in RAM |

Universal Pokémon Randomizer ZX and Archipelago's Emerald randomizer are
external tools, but they define what players expect a full randomizer to offer.
The safeguards that recur across all of them are:

- bosses can be left alone
- legendaries have their own setting
- key items and HMs never move
- Wonder Guard and form-changing abilities are banned
- every Pokémon gets a damaging move early
- settings lock at New Game
- every result follows from the seed

## Player experience

### Setup flow

1. Birch asks for gender, then Standard or Nuzlocke, as today
   (`Task_NewGameBirchSpeech_ChooseNuzlocke` in `src/main_menu.c`).
2. Birch asks "Would you like to randomize?" (`gText_Birch_Randomizer`). No
   clears the randomizer and moves on to name entry.
3. Yes opens the settings screen (`src/randomizer_menu.c`) with the Randomlocke
   preset and a new random seed. It has six pages: L/R changes the page,
   Up/Down picks a row and Left/Right (or A) changes its value. The first page
   holds the preset (Randomlocke, Full or Chaos; it reads Custom once any option
   differs), the seed and a "Start the game" row. A on Generations picks
   generations one by one. A line of button hints under the panel always shows
   the controls for the current mode, including START to finish. The text uses
   the standard menu palette so the button icons draw correctly, and the
   selected row is filled pale blue.
4. On the seed row, Left/Right rolls a new random seed and A opens code entry,
   where Up/Down cycles each character. An accepted code sets the seed and every
   setting from the code.
5. START on any page, or A on "Start the game", shows a summary with the preset
   name and the seed code: "These settings can't be changed once the game
   begins." A saves them and returns to Birch; B goes back.
   B on the pages backs out, and Birch asks the question again.

### After the game starts

- The trainer card's mode line reads "Standard, randomized" or "Nuzlocke,
  randomized", and the front of the player's own card shows the preset and the
  seed code where a link partner's card shows their profile
  (`src/trainer_card.c`). The seed code carries every setting, so no separate
  Options page was built.
- Nothing can be changed.

### Seed code

The code is 16 characters in four groups, for example `K7QD-2MXF-9PHA-RT4C`.
Its alphabet has 32 characters with no look-alikes (no 0/O or 1/I), so each
character carries 5 bits and the code carries 80:

| Bits | Contents |
|---|---|
| 32 | Seed |
| 36 | Every option (see the bit list under "Settings storage") |
| 4 | Algorithm version |
| 8 | Checksum |

The code is entered on a small dedicated screen, where up and down cycle each
character, not on the naming screen. A code with a bad checksum shows "That code
isn't valid." A code from another algorithm version shows "That code was made
with a different version of BPE." A new random seed comes from the RTC and frame
counter at the moment of choosing.

## The options

**Bold** in the Choices column marks the value Custom starts from. That is the
Randomlocke value. The choices are the labels the settings screen shows; they say
plainly whether something is random, matching the Features page. The rest of this
plan uses the internal names, which the screen spells differently:

| Internal name | On screen |
|---|---|
| Whole game / Per route (wild consistency) | Wild swaps: All catchable / Per route |
| Same roles / Random (starters) | Same type / Any type |
| Unchanged / Among themselves / Mixed (legendaries) | Not random / Legendaries only / Can be anywhere |
| Similar / Fully random (strength) | Close to original / Anything |
| Unchanged / Keep their type / Fully random (bosses) | Not random / Random, same type / Random, any type |
| Troll abilities | Harmful abilities: Not allowed / Allowed |

### Page 1: Setup

| # | Option | Choices |
|---|---|---|
| 1 | Preset | **Randomlocke** / Full / Chaos (Custom once changed) |
| 2 | Seed | **New random seed** / Enter a seed code |
| - | Start the game | Opens the summary (same as START) |

Birch's Yes/No question stands in for "Off". The Preset row's description
changes with the selected preset.

### Page 2: Pokémon

| # | Option | Choices |
|---|---|---|
| 3 | Starters | Not random / **Same type** / Any type / Legendaries |
| 4 | Wild Pokémon | Not random / **Random** |
| 5 | Wild swaps | **All catchable** / Per route |
| 6 | Gift Pokémon, eggs and in-game trades | Not random / **Random** |
| 7 | Static encounters | Not random / **Random** |

### Page 3: Pokémon pool

| # | Option | Choices |
|---|---|---|
| 8 | Legendaries | Not random / **Legendaries only** / Can be anywhere |
| 9 | Strength | **Close to original** / Anything |
| 10 | Generations | Nine toggles, Gen 1–9, **all on**; any combination, at least one on |

### Page 4: Trainers and items

| # | Option | Choices |
|---|---|---|
| 11 | Regular trainers | Not random / **Random** |
| 12 | Boss trainers | **Not random** / Random, same type / Random, any type |
| 18 | Field items | **Not random** / Shuffled |

### Page 5: Battle

| # | Option | Choices |
|---|---|---|
| 13 | Abilities | **Not random** / Random |
| 14 | Harmful abilities (shown only when abilities are Random) | **Not allowed** / Allowed |
| 15 | Level-up moves | **Not random** / Random |
| 16 | TM and tutor compatibility | **Not random** / Random |
| 17 | TM contents | **Not random** / Shuffled |

### Page 6: Chaos

| # | Option | Choices |
|---|---|---|
| 19 | Pokémon types | **Not random** / Random |
| 20 | Evolutions | **Not random** / Random |
| 21 | Base stats | **Not random** / Shuffled |
| 22 | Type chart | **Not random** / Shuffled |
| 23 | Monotype | **Off** / one of the 18 types |

### Presets

| Option | Randomlocke | Full | Chaos |
|---|---|---|---|
| Starters | Same type | Same type | Any type |
| Wild Pokémon | Random | Random | Random |
| Wild swaps | All catchable | All catchable | Per route |
| Gifts, eggs, trades | Random | Random | Random |
| Static encounters | Random | Random | Random |
| Legendaries | Legendaries only | Legendaries only | Can be anywhere |
| Strength | Close to original | Close to original | Anything |
| Generations | All | All | All |
| Regular trainers | Random | Random | Random |
| Boss trainers | Not random | Random, same type | Random, any type |
| Abilities | Not random | Random | Random |
| Harmful abilities | Not allowed | Not allowed | Allowed |
| Level-up moves | Not random | Random | Random |
| TM and tutor compatibility | Not random | Random | Random |
| TM contents | Not random | Shuffled | Shuffled |
| Field items | Not random | Shuffled | Shuffled |
| Types, evolutions, base stats, type chart | Not random | Not random | Random / Shuffled |
| Monotype | Off | Off | Off |

## Rules that apply everywhere

### Species pool

- The pool is every species that can exist outside battle and has its own
  sprites, plus the regional forms.
- The pool excludes:
  - Species flagged `isMegaEvolution`, `isPrimalReversion`, `isUltraBurst`,
    `isGigantamax`, `isTeraForm` or `isTotem`.
  - An explicit list of battle-only forms, such as Zen Mode Darmanitan, Blade
    Aegislash, Busted Mimikyu, Gulping and Gorging Cramorant, Noice Eiscue,
    Hangry Morpeko, Hero Palafin, Minior Core, School Wishiwashi, Complete
    Zygarde, Eternamax and Stellar Terapagos.
  - Cosmetic duplicates: Pikachu caps and costumes, Partner Pikachu, Unown
    letters after A, and Vivillon patterns after the first.
- "Legendaries" means species flagged `isRestrictedLegendary`,
  `isSubLegendary`, `isMythical` or `isUltraBeast`. Paradox Pokémon are regular.
- A species' generation is the generation that introduced it or its form:
  - Alolan forms are Gen 7.
  - Galarian and Hisuian forms are Gen 8.
  - Paldean forms are Gen 9.

  So Alolan Vulpix counts as Gen 7.
- A test checks that every species in the pool has a name and front, back, icon
  and overworld sprites.

### Strength

- **Similar:** the replacement's base stat total (BST) is within ±10% of the
  original's. If no candidate fits, the range widens in 10% steps, as in
  Archipelago.
- **Fully random:** no limit.
- **Filters:** Generations, Monotype and the Legendaries setting narrow the pool
  before strength is applied. When they leave nothing, the rules loosen in this
  order and never break the generation choice:
  1. Widen the strength range.
  2. Drop the type or role match.

### Whole game versus Per route

- **Whole game** swaps species one for one across the whole game:
  - The swap covers the species that appear in the categories being randomized:
    wild tables, gifts, eggs, trades and static encounters.
  - Every original species becomes exactly one other, and every species in the
    set is the replacement for exactly one.
  - So the set of catchable species is the same as the normal game; only their
    places change. This keeps BPE's promise that every Pokémon line can be
    caught, and keeps the Hoenn Dex requirements working.
  - With Similar strength, species only swap inside fixed base stat total
    bands about 20% wide (edges at 210, 252, 302, 363, 435, 522 and 627).
  - Species that can learn Surf only swap with each other, so everything the
    normal game offers to Surf with is still offered somewhere.
  - The legendary setting controls legendaries:
    - Unchanged: legendaries stay out of the swap.
    - Among themselves: the game's own legendaries swap among themselves, so
      the Hoenn legendaries stay catchable. Per route rolls from every legendary.
    - Mixed: legendaries are part of one swap with everything else.
  - A Generations limit or Monotype makes a true one-for-one swap impossible.
    In that case each original species still maps to one fixed replacement, but
    several originals can share one.
- **Per route** rolls each encounter table on its own:
  - A table is one map and one encounter method; its day and night tables
    share the roll.
  - Within a table, each original species maps to one replacement, so the
    table's slot rates stay meaningful. Other tables roll differently.
  - Gifts, eggs, trades and static encounters roll per event.

### HM safety

BPE's bag HMs still need a party Pokémon that could learn the HM
(`CanMonUseBagFieldMove` in `src/party_menu.c`). So:

1. **HM compatibility is never randomized.** "TM and tutor compatibility" and
   "TM contents" skip HMs, and HM moves never appear in randomized learnsets.
2. **Water slots stay usable for Surf.** In Per route games and games with a
   Generations limit or Monotype, surfing and fishing slots only roll Pokémon
   that can learn Surf. The whole-game swap keeps Pokémon that can learn Surf
   swapping with each other instead.
3. **HMs with no possible learner work for anyone.** When the settings are
   confirmed, the game checks each of the eight HMs against the species these
   settings can offer the player. If an HM has no possible learner, which only
   Monotype or narrow Generations can cause, that HM works from the Bag for any
   Pokémon in that save. The result is stored as 8 bits (see storage).

### Story safety

- **Route 101 first battle.** The wild Zigzagoon, Lv 2 (`CreateWildMon` in
  `src/battle_controllers.c`), follows the Wild option but always uses Similar
  strength. The overworld Zigzagoon chasing Birch shows the new species.
- **Wally's tutorial Ralts.** The Ralts, Lv 5 (`StartWallyTutorialBattle` in
  `src/battle_setup.c`), is part of Wally's team rather than an encounter the
  player can have, so it follows the **trainer** options, not the Wild one. It is
  the first stage of whatever his own Ralts line becomes, so the Pokémon he
  catches is the one he brings to Mauville. With his fight left unchanged he
  still catches a Ralts, however the wild Pokémon are randomized.
- **Norman's Zigzagoon.** The Zigzagoon Norman lends for the tutorial
  (`PutZigzagoonInPlayerParty`) is not changed.
- **Starters.** A Birch Case starter that knows no damaging move at level 5 is
  given Tackle, because the Route 101 battle comes right after the pick. The
  Johto gift has no such fallback, so those three balls still only hold Pokémon
  that can already attack.
- **Kecleon.** A randomized Kecleon stays invisible until the Devon Scope reveals
  it, like the original.
- **Cutscenes and disguises.** Story cutscene sprites stay. Sky Pillar's
  Rayquaza keeps its sprite and cry because the same map holds the story scene;
  only its post-game battle changes. Statics disguised as statues or item balls
  keep their look.

### Pokédex goals

- `HasAllHoennMons` gates the Johto starters in Birch's lab and the Lilycove
  Diploma. `HasAllMons` gates the National Pokédex diploma.
- In these settings the full Hoenn Dex may be impossible:
  - Per route with any species category on
  - A Generations limit
  - Monotype
  - Random evolutions

  In those games the Johto starters unlock right after the Hall of Fame.
  `LittlerootTown_ProfessorBirchsLab_EventScript_CheckReadyForJohtoStarter`
  calls a new special that accepts either condition. The diplomas keep their
  normal requirements and may be unreachable in those games.

### Everything else

- **Battle Frontier.** Frontier and Trainer Hill teams are not re-rolled;
  `CreateNPCTrainerPartyFromTrainer` already skips them. Species-level changes
  (abilities, types, learnsets, base stats, type chart) apply there too, because
  they define what each species is in that save.
- **Nuzlocke.** The first-encounter rule and the dupes clause look at the
  Pokémon you actually meet, so they need no changes. Level caps, the Candy Jar,
  and Standard and Nuzlocke trainer levels are unchanged; the randomizer never
  changes levels.
- **Link play.** Link battles use the normal abilities, types, base stats and
  type chart on both sides, so players with different settings never disagree.
  Trades still carry whatever Pokémon each save holds.

## Option details

### Starters

BPE has twelve starter balls: the nine-ball Birch Case on Route 101
(`src/ui_birch_case.c`) and the three post-game Johto balls in Birch's lab.

**Same roles:** each ball becomes a Pokémon with the same main type and the same
number of evolution stages as the Pokémon it replaces.

| Ball | Becomes a random… |
|---|---|
| Treecko, Chikorita | Grass type that evolves twice |
| Torchic, Cyndaquil | Fire type that evolves twice |
| Mudkip, Totodile | Water type that evolves twice |
| Ralts | Psychic type that evolves twice |
| Honedge | Steel type that evolves twice |
| Porygon | Normal type that evolves twice |
| Paldean Wooper | Poison type that evolves once |
| Eevee | Normal type that evolves once |
| Alolan Vulpix | Ice type that evolves once |

**Random:** the Birch Case offers nine unrelated Pokémon, each with a different
main type. The Johto balls become three more random Pokémon.

**Legendaries:** the same nine different main types, but every ball holds a
legendary, mythical or Ultra Beast. It ignores the Legendaries option, which
still governs the rest of the game.

**Monotype** makes all twelve share the chosen type and overrides both modes.

Rules for every mode:

- Every ball is an unevolved (basic) Pokémon.
- No two balls come from the same evolution family.
- **Strength:** with Similar strength, the replacement's final evolution has a
  BST within ±10% of the original's final evolution.
- **Legendaries:** possible only when Legendaries is Mixed, or in the
  Legendaries starter mode, which makes all nine of them legendary.
- **Usable immediately:** a Birch Case starter with no damaging move at level 5
  is handed Tackle, so any Pokémon can fill a ball. The three Johto balls keep
  the old rule and only hold Pokémon that already attack by then.
- With random types on, the roles use the types Pokémon have in that seed, so
  the Grass ball offers something that is Grass in that game.

How it fits in:

- **Birch Case screen:** it reads `sStarterChoices[].species` in six places.
  One accessor replaces those reads and returns the randomized species, so the
  icon, Dex number, name and category all follow.
- **Johto balls:** the scripts' `showmonpic`, `givemon` and "You'll take
  Totodile?" texts take the species from a variable, and the texts become
  generic.

### Wild Pokémon

- **Every encounter method** goes through one species accessor:
  - grass, including each time-of-day table
  - surfing, all three rods, Rock Smash and hidden encounters
  - Sweet Scent and Honey
  - the Route 119 Feebas tiles
  - TV mass outbreaks
- **Outbreaks:** a mass outbreak is randomized when its TV show is generated, so
  the broadcast names the right Pokémon.
- **Encounter abilities:** Magnet Pull, Static, Flash Fire and similar abilities
  look at the new species' types (`TryGetAbilityInfluencedWildMonIndex`).
- Levels and slot rates are unchanged.
- **Screens that list wild Pokémon:** the Pokédex area screen and Match Call
  show the randomized species.
  - In Whole game mode the area screen runs the swap backwards to find where a
    species lives.
  - In Per route mode it rolls each table forwards.

### Gifts, eggs and trades

- **Gifts:** the `givemon` gifts are randomized: Castform, Beldum, and the
  Lileep and Anorith fossils. The Johto starters belong to Starters instead.
- **Eggs:** the `giveegg` eggs (Togepi, Pichu) are randomized. Day Care eggs are
  simply the parents' species.
- **In-game trades:** both the Pokémon you receive and the one the trader asks
  for are randomized, so the trade stays possible.
  - In Whole game mode the requested Pokémon goes through the swap.
  - In Per route mode the trader asks for whatever replaced the requested
    Pokémon in the first area it originally appeared in. The data generator
    records that area.

### Static encounters

- **Which ones:** the 28 `setwildbattle` encounters and the roaming
  Latios/Latias (`InitRoamer` in `src/roamer.c`).
- **Legendaries** follow the Legendaries setting. The Voltorb, Electrode,
  Snorlax, Sudowoodo, Kecleon, Spiritomb, Rotom and Type: Null encounters follow
  Static encounters.
- **Levels** are unchanged.
- **Overworld sprite:** an object that shows its Pokémon (the Regis,
  Latias/Latios, Sudowoodo, the Kecleon, the post-game Kyogre and Groudon, and
  Petalburg's Snorlax) shows the new Pokémon instead, through
  `OBJ_EVENT_GFX_SPECIES`. `sStaticEncounters` in `src/randomizer.c` lists every
  static encounter's map and object sprite. `TrySpawnObjectEventTemplate`
  swaps the graphics before the sprite is built, so the object gets the new
  Pokémon's follower sprite, palette and walking animations (the Route 101
  chase uses them), and `InitObjectEventStateFromTemplate` swaps them for
  objects set up another way. `playmoncry` plays the new Pokémon's cry on those
  maps.

### Trainers

- **Bosses** are the trainer classes Leader, Elite Four, Champion, Rival (which
  covers Cynthia and Wally), and the Magma and Aqua Leaders and Admins. Everyone
  else is regular.
- **Random, keep their type:** each replacement shares at least one type with
  the Pokémon it replaces. Type-themed gyms stay themed, and mixed teams keep
  their spread.
- **Continuity:** a trainer who appears more than once keeps the same
  replacements between fights. That covers the rival, Wally, the Magma and Aqua
  bosses, gym rematches and every rematch tier.
  - The replacement is picked per evolution family, keyed by trainer name and
    class.
  - Its evolution stage follows the original's, so Gible → Gabite → Garchomp
    becomes X → X2 → X3.
  - One-off regular trainers pick per party slot.
- **Other settings:** Strength, Legendaries and Generations apply. Monotype does
  not.
- **Kept from the trainer's data:**
  - Level: Nuzlocke `Level:` or `Standard Level:`
  - Nature, IVs and EVs (in Standard mode), Poké Ball, nickname, shininess, held
    item and Tera Type
- **Changed:**
  - A Mega Stone holder's replacement is picked from species that can Mega
    Evolve, keeping the type rule, and holds its own Mega Stone.
  - Other items that only work for one species (Light Ball, Thick Club, Leek,
    Soul Dew and similar) become Leftovers.
  - The Gigantamax factor is dropped unless the new species has one.
  - A hand-picked ability no longer applies to the new species. The Pokémon uses
    one of its own ability slots, or the seed's ability when abilities are
    random.
- **Unchanged bosses keep their hand-picked abilities** even when abilities are
  random.
  - The Pokémon they don't give an ability use the normal species' ability for
    that slot.
  - A per-battle override in the battle struct holds these. It exists only
    during battle.

**Moves for randomized trainer Pokémon: the strongest sensible set.**

- **Candidates:**
  - Level-up moves at or below the Pokémon's level, from the randomized learnset
    when that option is on.
  - TMs it can learn, from randomized compatibility when that option is on, that
    the player could have obtained by then.
- **"By then"** means the player's badge count when the battle starts. Eight
  badges plus the Champion flag counts as post-game.
  - A TM counts once any of its sources is available at that badge count: its
    field location (after the Field items and TM contents shuffles), an NPC
    gift, a mart or a prize corner.
  - A generated table gives every source its badge tier, and the game takes the
    lowest.
- **Scoring:**
  - Base score: power × accuracy.
  - ×1.5 for attacks of the Pokémon's own type.
  - Uses whichever attacking stat is higher.
  - Penalties for recharge, charge turns and self-KO.
- **Banned:** Explosion, Self-Destruct, Memento, Final Gambit, Healing Wish,
  Lunar Dance, Dream Eater, Snore, Focus Punch, Last Resort, Belch, Synchronoise
  and the one-hit KO moves.
- **Picking the four moves:**
  1. The best attack of each of its own types.
  2. The best attacks of new types, for coverage.
  3. The last slot may take a status move from a short approved list (setup,
     recovery, entry hazards, status conditions) if it can learn one.
  4. Next-best attacks fill anything left.
- Pokémon whose species didn't change keep their hand-made moves.

### Abilities

- **One pick per evolution family and slot:** the family and slot choose the
  ability, so evolutions keep it. Species keep their number of ability slots,
  including the hidden ability.
- **Always banned:**
  - Huge Power and Pure Power.
  - Wonder Guard, except that Shedinja keeps its own Wonder Guard.
  - Every species-locked or form-changing ability:
    - Starting set: the abilities flagged `cantBeCopied` or `cantBeSwapped` in
      `gAbilitiesInfo`.
    - Explicit list: Multitype, RKS System, Zen Mode, Stance Change, Schooling,
      Disguise, Battle Bond, Power Construct, Shields Down, Comatose, Ice Face,
      Gulp Missile, Hunger Switch, As One, Zero to Hero, Commander, Tera Shift,
      Forecast and Flower Gift.
- **Troll abilities** are the ones the battle AI rates as harmful (a negative
  `aiRating`), such as Truant, Slow Start, Defeatist, Klutz and Stall. They are
  only allowed when the option is Yes.
- **Scope:** abilities apply to the player's, wild and trainer Pokémon, except
  Unchanged bosses, and to the Frontier.

### Level-up moves

- **Shape:** each species keeps its learnset's levels and length; only the moves
  change.
- **Move choice:** new moves favour the Pokémon's own types. Each entry rolls a
  move of one of its types about 40% of the time, Normal about 20%, and any
  type otherwise.
- **Guarantees:**
  - Every species gets at least one damaging move by level 5.
  - HM moves and the trainer ban list never appear.
- **Move Relearner** shows the randomized moves, because it reads the same
  accessor.

### TM and tutor compatibility, TM contents

- **Compatibility:**
  - Each species keeps about as many TMs and tutor moves as before, re-rolled
    with a lean towards its own types.
  - HMs are untouched.
- **TM contents:**
  - TM contents shuffles which move each TM teaches, among the TM moves only.
  - TM names and descriptions in the Bag follow the shuffle.
  - HMs are untouched.

### Field items

- **Shuffled:** field items, meaning item balls (about 230) and hidden items,
  trade places. Quantities move with their items.
  - TMs only swap with other TMs.
  - Key items and HMs never move.
  - Everything else shuffles among the remaining spots, including Mega Stones,
    evolution items and Rare Candies. So every item still exists somewhere.
- **Not shuffled:** NPC gifts, marts, berry trees and prize corners.

### Chaos

- **Types:**
  - Each evolution family's base form gets random types.
  - Evolutions keep them. Where the original evolution gained a type, the new
    one gains a random extra type.
  - Every type-based rule uses the seed's types: starter roles, bosses keeping
    their type, Monotype and the encounter abilities.
- **Evolutions:**
  - Each evolution leads to a random species of similar strength to the
    original target.
  - The method, level and item stay the same, and nothing evolves into itself.
- **Base stats:**
  - The six base stats are shuffled with one pattern shared by the whole family.
  - BST is unchanged, so the strength rules still hold.
- **Type chart:**
  - A random relabelling of the 18 types: a move of type A against type D uses
    the original matchup of relabelled(A) against relabelled(D). Every type
    keeps as many strengths and weaknesses as before.
  - The Stellar and typeless types are untouched.
  - The move menu's effectiveness hint (`B_SHOW_EFFECTIVENESS` is set to
    always) shows the shuffled results, so players can learn the new chart.
- **Monotype:**
  - Wild, gift, egg, trade, static and starter Pokémon all have the chosen type.
  - Legendaries follow the Legendaries setting, restricted to the chosen type
    where possible.
  - Trainers are unaffected.
  - The HM safety rules above keep the game completable.

## Technical design

### Settings storage

The settings fit in six save variables that have never been used. All six are
still `VAR_UNUSED_*` in the 1.0.1 source (`bpe/source/1.0.1`), `bpe/v2.0.0-beta`,
`bpe/v2.0.4`, `bpe/v2.0.6-beta` and `main`. No save format change is needed, and
converted pre-2.1 saves read as "randomizer off".

| Variable | New name | Holds |
|---|---|---|
| `0x404E` | `VAR_RANDOMIZER_SEED_LO` | Seed, low 16 bits |
| `0x4083` | `VAR_RANDOMIZER_SEED_HI` | Seed, high 16 bits |
| `0x4091` | `VAR_RANDOMIZER_OPTIONS_0` | Option bits 0–15 |
| `0x409B` | `VAR_RANDOMIZER_OPTIONS_1` | Option bits 16–31 |
| `0x409D` | `VAR_RANDOMIZER_OPTIONS_2` | Option bits 32–35, algorithm version (4 bits), HM fallback (8 bits) |
| `0x40A1` | `VAR_STARTER_SPECIES` | The species picked from the Birch Case, in every game |

The 36 option bits:

| Option | Bits |
|---|---|
| Starters | 2 |
| Wild | 1 |
| Wild consistency | 1 |
| Gifts, eggs, trades | 1 |
| Statics | 1 |
| Legendaries | 2 |
| Strength | 1 |
| Generations | 9 |
| Regular trainers | 1 |
| Boss trainers | 2 |
| Abilities | 1 |
| Troll abilities | 1 |
| Level-up moves | 1 |
| TM and tutor compatibility | 1 |
| TM contents | 1 |
| Field items | 1 |
| Types | 1 |
| Evolutions | 1 |
| Base stats | 1 |
| Type chart | 1 |
| Monotype | 5 |

- **On or off:** the randomizer is on when any option bit is set. The seed alone
  says nothing, because 0 is a valid seed. The algorithm version starts at 1.
- **New-game reset:** new-game setup clears variables, so `src/new_game.c` must
  save and restore these the same way it already does for `FLAG_NUZLOCKE`.
- **Before building,** confirm that no script writes these variables. Also check
  local player saves with the save inspector to confirm they are zero.

### Determinism

- **The hash.** `Hash(stream, a, b)` in `src/randomizer.c` is a 32-bit integer
  mix of the seed and its inputs. It keeps no RNG state, so the same inputs always give
  the same result, and saving or reloading never changes anything.
- **Separate categories.** Each option hashes in its own category, so turning
  one option on never changes another option's results.
- **One-for-one mappings.** The Whole game swap, the field item and TM contents
  shuffles, and the type chart relabelling use a keyed Feistel network over the
  index range, with cycle-walking. That is a true one-for-one mapping and it can
  also run backwards. Running it backwards answers questions like "where did
  this species go?" and "where is this TM now?".
- **Keeping old seeds stable across updates.**
  - Species IDs are stable in pokeemerald-expansion, and the species pool is
    worked out from `gSpeciesInfo` at run time. `RANDOMIZER_V1_SPECIES_LIMIT`
    keeps species added after version 1 out of version 1 games.
  - The field item table is append-only: an existing location keeps its index.
  - Changes to a species' own data, such as its base stats, learnset or
    abilities, can still change randomized results. The release notes must say
    so when it happens.
- **When to bump the version.** Any other change that alters an existing seed's
  results bumps the algorithm version. Fixed expected outputs checked by tests
  catch such changes.

### Generated data

- **The generator.** `BPETools/generate_randomizer_data.py` writes
  `src/data/randomizer/generated.h`. The output is committed, as the generated
  trainer levels are; `--check` fails when it is stale.
- **Its inputs:**
  - Evolution data, through the documentation exporter's species parser
    (`BPEDocumentation/scripts/parse_pokemon.py`).
  - Wild tables (`src/data/wild_encounters.json`), skipping upstream's
    FireRed/LeafGreen maps that BPE doesn't have.
  - Gift (`randomgift`, `givemon`, eggs), static (`setwildbattle`, roamers) and
    trade lists from the scripts.
  - Item balls and hidden items from the map JSON files.
  - A hand-checked `BPETools/randomizer_badge_tiers.json`: the badge count needed
    to reach each region map section, the badge each gym's TM reward follows,
    and per-map and per-item overrides.
- **Its tables:** each species' evolution family root, where the normal game
  hands out each species, where each trade's requested species is first found,
  the field item locations (flag, item, quantity, badge tier) with a flag index,
  and the lowest badge tier of each TM's non-field sources.
- **Worked out at run time instead:** the species pool, generations, legendary
  groups, strength bands, evolution stages and family lengths, all from
  `gSpeciesInfo`, so they can't go stale.
- **Checks:** `test/randomizer.c` checks the family table against the evolution
  data.

### RAM and speed

- **RAM:** the randomizer keeps two EWRAM variables for the settings screen (a
  heap pointer and a flag; 12 bytes of EWRAM in total with alignment) and saves
  nothing beyond the six variables. The per-battle ability override lives in
  the battle struct, which is on the heap and only exists during battle.
  `BPETools/tests/test_ram_budget.py` must stay green.
- **Speed:**
  - Each pick tries a few hashed candidates, then counts every candidate when the
    filter is narrow. The whole-game swap walks a Feistel permutation. The
    upstream draft PR #3998 keeps a 6 KB species table in RAM instead, which BPE
    can't spare.
  - The randomizer settings are read straight from the save variables, so a game
    with the randomizer off pays almost nothing.
  - The costliest screen is the Pokédex area map in Per route mode, which rolls
    each different species in every table once. Whole game mode runs the swap
    backwards instead.
  - The Birch Case rolls all nine balls when it opens.
  - Check the area screen, trainer battles and the Birch Case for delays in
    mGBA.

### Where it hooks in

New code is in `src/randomizer.c`, `src/randomizer_menu.c`,
`include/randomizer.h`, `include/randomizer_menu.h` and
`include/constants/randomizer.h`. Most hooks are one-line calls, so expansion
upgrades touch little.

| Area | Where |
|---|---|
| New-game choice | `src/main_menu.c`, after `Task_NewGameBirchSpeech_ChooseNuzlocke`; `src/new_game.c` preserves the variables |
| Birch Case | `src/ui_birch_case.c`: the nine balls are rolled once into the menu's heap struct; record `VAR_STARTER_SPECIES` |
| Johto balls | `data/maps/LittlerootTown_ProfessorBirchsLab/scripts.inc` |
| Starter lookups | `GetStarterPokemon` (`src/starter_choose.c`), used by the credits and `IsStarterInParty` (`src/field_specials.c`) |
| Wild | `src/wild_encounter.c`: `TryGenerateWildMon`, `GenerateFishingWildMon`, `GetLocalWildMon`, `GetLocalWaterMon`, `TryGetAbilityInfluencedWildMonIndex`, Feebas; outbreaks in `src/tv.c` |
| Area screen, Match Call | `src/pokedex_area_screen.c`, `src/match_call.c` |
| First battle, Wally | `src/battle_controllers.c` (Zigzagoon Lv 2), `StartWallyTutorialBattle` in `src/battle_setup.c` |
| Gifts, eggs, statics | the `randomgift` macro and `RandomizeGiftSpecies`/`RandomizeEggSpecies` specials in the gift scripts; `ScrCmd_setwildbattle` and `ScrCmd_playmoncry` (`src/scrcmd.c`); `InitRoamer` (`src/roamer.c`); `InitObjectEventStateFromTemplate` (`src/event_object_movement.c`) for static sprites |
| Trades | `CreateInGameTradePokemonInternal` and `GetInGameTradeSpeciesInfo` (`src/trade.c`), data in `src/data/trade.h` |
| Trainers | `CreateNPCTrainerPartyFromTrainer` (`src/battle_main.c`), after `DoTrainerPartyPool`; `CustomTrainerPartyAssignMoves` |
| Abilities | `GetSpeciesAbility` (`src/pokemon.c`) and the stat editor; `ApplyRandomizerKeptAbility` (`src/battle_util.c`) for Unchanged bosses |
| Types | `GetSpeciesType`, plus the Tera type and `IsSpeciesOfType` reads in `src/pokemon.c` |
| Learnsets | `GetLearnsetMove` (`include/pokemon.h`) in the level-up, move relearner and Pokédex readers |
| TM compatibility | `CanLearnTeachableMove` (12 calls) |
| TM contents | `GetTMHMMoveId`, `GetItemTMHMMoveId` and `GetTMHMItemIdFromMoveId` (`include/item.h`) |
| Evolutions | `GetEvolutionTargetSpecies` (`src/pokemon.c`) and the Pokédex evolution screen |
| Base stats | `GetSpeciesBaseHP` and the other five base stat accessors (`src/pokemon.c`) |
| Type chart | `GetTypeModifier` (`src/battle_util.c`), plus the one direct table read in `src/battle_script_commands.c` |
| Field items | `GetItemBallIdAndAmountFromTemplate` (`src/item_ball.c`); the `BG_EVENT_HIDDEN_ITEM` handler in `src/field_control_avatar.c` |
| HM fallback | `CanMonUseBagFieldMove` (`src/party_menu.c`) |
| Dex gate | `LittlerootTown_ProfessorBirchsLab_EventScript_CheckReadyForJohtoStarter` |
| Display | `src/trainer_card.c` |

## Existing bug fixed along the way

- **The bug.** The Birch Case replaced the old three-ball selector but never sets
  `VAR_STARTER_MON`. The variable is always 0, so the game treats every starter
  as Treecko:
  - The credits skip Treecko instead of your real starter.
  - The Petalburg Pokémon Center NPC only talks about your starter if you have a
    Treecko.
  - The Mauville Game Corner always gives the Treecko doll.
- **The fix, in every game, randomized or not:**
  - Record the real species in `VAR_STARTER_SPECIES` and have
    `GetStarterPokemon` return it. Older saves have 0 there and keep today's
    behaviour.
  - The Petalburg NPC names the real starter's type.
  - The Game Corner doll becomes a choice of the three Hoenn dolls.
- **Leave `VAR_STARTER_MON` itself alone.** The rival scripts only handle 0–2,
  and another value would skip the rival battle. Nothing depends on it anyway:
  Cynthia's team is identical in all three variants.

## Testing

A new `test/randomizer.c` runs under `make check`:

- **Determinism:** the same seed and settings always give the same results.
  Fixed seeds must produce fixed expected outputs, which pins results across
  releases.
- **Swaps:** every one-for-one swap really is one-for-one within its group and
  band. The Whole game catchable set equals the normal game's.
- **Species pool:** no excluded forms, legendaries only where the setting allows
  them, and the Generations and Monotype filters hold.
- **Starters:** basic forms, distinct families, a damaging move at level 5, the
  right roles in Same roles, and nine distinct main types in Random.
- **Trainers:**
  - Continuity across rematch tiers and story fights.
  - The keep-their-type rule and the Mega Stone rule.
  - Move sets use only legal moves and TMs available at the badge count.
  - Unchanged bosses keep their abilities.
- **Abilities:** never a banned ability, and troll abilities only when allowed.
- **Learnsets:** a damaging move by level 5, and no HM moves.
- **HM safety:** HM compatibility is untouched. Water slots only offer Surf
  learners. The fallback bits are set exactly when an HM has no possible learner.
- **Field items:** the shuffle is one-for-one, TMs only swap with TMs, and key
  items and HMs never move.
- **Dex gate:** the Johto starter fallback turns on in exactly the listed cases.
- **Seed codes:** round-trip every option, and reject bad checksums and other
  versions.

Also run:

- `python -m unittest discover -s BPETools/tests -v`: generator tests and the RAM
  budget test.
- **Timing:** measure the Pokédex area screen in Per route mode and a six-Pokémon
  trainer party.
- **Maintainer mGBA playtest** (the maintainer runs it):
  - A new game with each preset.
  - Enter one code on two saves and confirm the games match.
  - The Route 101 battle, the Wally tutorial and the rival fights.
  - A gym with "Random, keep their type".
  - HM gates in a Monotype Fire game.
  - Item pickups.
  - The Johto starter fallback, reached through the debug menu.

## Build order

The whole feature ships in one release, including the Chaos page. All seven
steps are built on the `randomizer` branch; the maintainer's mGBA playtest and
the release remain. The build order was:

1. **Core:** the variables and new-game preservation, the hash and swaps, the
   generator and tables, the settings screen, seed codes, the trainer card, and
   the test scaffolding.
2. **Pokémon:**
   - Starters: the Birch Case and the Johto balls.
   - Wild Pokémon by every method.
   - Gifts, eggs, trades, static encounters with their sprites, roamers and
     outbreaks.
   - The Dex gate fallback and the starter-species fix.
3. **Trainers:** species and continuity, Mega Stones and held items, move sets
   with TM availability, and the ability override for Unchanged bosses.
4. **Battle data:** abilities, level-up moves, TM compatibility and TM contents.
5. **Items:** the field item shuffle.
6. **Chaos:** types, evolutions, base stats, the type chart, Monotype and the HM
   fallback.
7. **Documentation and release:** the Features page entry and the `AGENTS.md`
   section. Then set the version and publish through the normal release
   procedure in [RELEASING.md](RELEASING.md), after the maintainer's playtest.

## Documentation

- A Features page entry in `BPEDocumentation/content/features.json` (done). It
  goes live with the release package and says that the site's route and trainer
  pages show the normal game.
- A Randomizer section in the "Known quirks" part of `AGENTS.md` (done):
  - The six variables and the new-game preservation.
  - The algorithm-version rule.
  - "Species, abilities, types, learnsets, evolutions, base stats and the type
    chart must be read through their accessors."
- No website spoiler log or seed viewer.

## Decisions (2026-09-18)

- **Where and when.** The settings are chosen during Birch's speech, right after
  Standard/Nuzlocke, and locked for the save.
- **Boss trainers** get their own option: Unchanged / Random, keep their type /
  Fully random.
- **Abilities** are in the first release.
- **Legendaries** are Unchanged, randomized among themselves, or mixed with all
  Pokémon.
- **No website spoiler log.**
- **Starters:** twelve balls (the Birch Case and the Johto balls), with the
  choices Off / Same roles / Random.
- **Wild consistency** defaults to Whole game. When the settings can make the
  full Hoenn Dex impossible, the Johto starters unlock after the Hall of Fame.
- **Randomized trainer Pokémon** get the strongest sensible set from level-up
  moves and TMs, keep their held items, and only use TMs the player could have
  by then.
- **Generations** is a toggle for each of Gen 1–9, in any combination.
- **Static encounters** show the randomized Pokémon in the overworld.
- **Field items** are shuffled between locations, not drawn at random.
- **Unchanged bosses** keep their hand-picked abilities when abilities are
  random.
- **The Chaos page** ships in the same release as everything else.

## Assumptions to confirm

These were decided while writing the plan; each is easy to change.

- **HM fallback:** an HM with no possible learner, which only Monotype or narrow
  Generations can cause, works for any Pokémon in that save.
- **Wally:** his Ralts line follows his tutorial catch even when bosses are
  Unchanged.
- **Species-only held items:** Light Ball, Thick Club, Leek and similar become
  Leftovers on randomized trainer Pokémon.
- **Trainers roll their own picks.** Trainers don't use the Whole game swap,
  which only covers Pokémon the player can obtain.
- **Chaos wild consistency:** the Chaos preset uses Per route.
- **Regional forms** count as the generation that introduced the form.
- **Paradox Pokémon** are regular, not legendary.
- **Shedinja** keeps Wonder Guard.
- **Game Corner doll:** it becomes a choice of the three Hoenn dolls.
- **Seed codes** are 16 characters, entered on a dedicated screen.

## Sources

- [Unbound wiki: Randomizer](https://pokemonunbound.miraheze.org/wiki/Randomizer)
- [Radical Red changelog](https://www.poke100.com/pokemon-radical-red-changelog/)
- [Elite Redux changelog](https://www.pokeporto.com/pokemon-elite-redux-changelog/)
- [Emerald Imperium features](https://pokemonemeraldimperium.com/features/)
- [TheXaman randomizer and challenges](https://github.com/TheXaman/pokeemerald/blob/tx_randomizer_and_challenges/TX_RAC_FEATURES.md)
- [pokeemerald-expansion PR #3998](https://github.com/rh-hideout/pokeemerald-expansion/pull/3998)
- [Universal Pokémon Randomizer ZX](https://github.com/Ajarmar/universal-pokemon-randomizer-zx)
- [Archipelago Pokémon Emerald](https://github.com/ArchipelagoMW/Archipelago/tree/main/worlds/pokemon_emerald)
