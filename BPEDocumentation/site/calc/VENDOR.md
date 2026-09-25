# Vendored: Smogon's Pokémon Damage Calculator

Source: https://github.com/smogon/damage-calc (branch `master`)
Engine: `@smogon/calc` 0.12.0, built from that checkout
License: MIT (`calc/LICENSE`, retained)

BPE builds its calculator on Smogon's own, which is the one the damage
mechanics come from: Generations 1-9 including Terastallization, the Paradox
abilities and the Legends Z-A Mega abilities the game uses. Everything Black
Pearl Emerald adds sits in files of its own, so upstream can be taken again
without re-doing the work.

## How it was built

```bash
git clone https://github.com/smogon/damage-calc.git
cd damage-calc/calc && npm install --ignore-scripts && npm run compile   # tsc -> calc/dist
cd .. && node build view                                                 # src + calc/dist -> dist
```

`dist/` is then copied here without `champions.html`, `honkalculate.html`,
`randoms.html`, `oms.html`, `js/data/sets/` (Smogon's competitive sets; BPE
ships the game's trainers instead), `calc/test/`, `*.d.ts` and `*.js.map`.

## What BPE adds

- `js/bpe_data.js` — loads `data/bpe_calc_data.json` over the calculator's Gen 9
  tables: the game's Pokémon, moves, ability and item names, Mega Stones, and
  every trainer's team as this generation's sets. A base power of 1 means the
  game works the power out during the battle (Low Kick, Gyro Ball, Return, ...),
  so the calculator's own handling is left alone. The damage engine keeps its
  own species and move tables, built when the page loads, so `bpe_data.js` also
  answers the engine's generation 9 lookups (`calc.Species.prototype.get`,
  `calc.Moves.prototype.get`) from the game's data. Without that, species the
  calculator never had (the game's `Aegislash`, `Toxtricity-Amped`) had no
  weight or abilities in the engine, and the box match-ups used Smogon's stats
  and move powers.
- `js/bpe_trainers.js` — the opposing trainer's whole team inside Pokémon 2's
  panel, between its HP and its moves, in party order, with the one that is loaded marked. Clicking loads a team
  member.
- `js/bpe_formes.js` — a trainer's Pokémon holding its Mega Stone Mega Evolves,
  which is what happens in battle.
- `js/bpe_box.js` — the player's imported Pokémon inside Pokémon 1's panel,
  under its moves, party first. Sets live in the calculator's own imported-set store
  (`localStorage.customsets`), the party order beside it in
  `localStorage.bpeBoxParty`. Each tile shows its match-up against the
  trainer's Pokémon; sets spell stats `at`/`df`/`sa`/`sd`/`sp`, so they are
  renamed for the engine, which reads a missing stat as 31 IVs and 0 EVs.
- `js/bpe_deeplink.js` — `calc.html#mon=...` from the map and the Trainers page.
- `../js/calc_save_import.js`, `../js/save-converter.js` — Import .sav, shared
  with the rest of the site (`BPETools/tests/test_calc_save_import.py` covers
  the reading half).
- `css/bpe-layout.css` and `js/bpe_layout.js` — the page layout of BPE's
  earlier calculator: Pokémon 1, the field and Pokémon 2 as three columns
  across the page (`.panel-wrapper` in `index.html`), Pokémon 2's results on
  the right, and a sprite on each side (`.poke-sprite`) that follows the set
  and forme. The stylesheet loads last and also undoes Smogon's fixed 60px
  `header` height, which hid the top of the page under the site header.
- `css/bpe.css`, plus the site header, version selector and nav in `index.html`.
- `index.html` also drops Google Analytics, the Pokémon Showdown site header,
  the generation and mode pickers (BPE is one game on one generation),
  Smogon's set files, the light-theme switch (the site is dark only) and
  Smogon's credits footer, whose links pointed players at Smogon's bug
  reports.

## Changes inside the vendored code

Each is a one-liner with a `BPE:` comment (`grep -rn "BPE:" js calc`), and all
are worth sending upstream:

- `js/shared_controls.js` — three guards for a generation whose sets load after
  the page (`getFirstValidSetOption()` can return nothing), and a species or set
  with no listed ability (`altForme.abilities[0]` and `chosenSet.abilities[0]`).
- `js/shared_controls.js` — a set of four moves keeps the order the game gives
  them; only a longer list is a pool to pick from.
- `js/shared_controls.js` — the set search also matches a set's name, so a
  trainer ("REA", "Leader REA") lists their Pokémon, each under its Pokémon's
  heading. Upstream matches the Pokémon's name only.
- `calc/mechanics/gen789.js` — Super Fang and Ruination take half the target's
  HP, as Nature's Madness already did; upstream gives them no damage at all.
  Re-apply after rebuilding `dist/`, since this file is compiled from
  `calc/src/mechanics/gen789.ts`.

## Regenerating data

`py BPEDocumentation/scripts/build_calc_data.py` writes `data/bpe_calc_data.json`
and the `img/newhd/` sprites. It reads the vendored `calc/data/*.js` to spell
each name the way this calculator does, so re-vendoring upstream keeps the
names in step.
