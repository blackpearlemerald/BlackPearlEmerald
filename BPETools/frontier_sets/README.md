# Battle facility sets and rules

The enemy Pokémon for the Smogon and Full Dex rule sets, and the rules each generation and
tier allows. `python BPETools/generate_frontier_sets.py` turns these files into
`src/data/battle_frontier/frontier_sets.h`.

- `sets.json`: every tested set, and each pool's sets, strongest first, with win rate per
  1000 and games played. Rows are `[species, form, item, ability, nature, EVs, moves, grade, source]`.
- `rules.json`: for each generation (National Dex, then 1 to 9), which species, moves and
  items exist, what each tier bans, and which Showdown format each tier's rules came from.
- `LICENSE-pokemon-showdown.txt`: Pokémon Showdown's MIT notice.

## Credit

Sets and rules come from [Pokémon Showdown](https://github.com/smogon/pokemon-showdown)
(commit `5b01be8`): its Factory and Battle Stadium sets, its Random Battle generator, its
team validator and its battle engine. Usage numbers come from Smogon's public monthly
statistics. Smogon's own written set analyses are copyrighted and are not used.

## Grades

- **A**: a Showdown Factory or Battle Stadium set, or a set made from recent high-ladder
  usage where every part is common on that Pokémon.
- **B**: a usage set from an older generation or with less common parts.
- **C**: built from Showdown's Random Battle move lists, with a role-based item and spread.

## Remaking the sets

Only do this to change which sets exist. It needs Node, about 700 MB of disk and hours of
CPU time. The scripts use their own folder as the work folder, so copy `pipeline/` into
`.release-work/frontier-sets/` (gitignored) and run them there. Keep long jobs to about
40% of the cores: `sim.cjs` and `gen_candidates.cjs` already stop at 9 workers.

1. `git clone https://github.com/smogon/pokemon-showdown showdown`, check out `5b01be8`, then
   `node build` inside it.
2. `python -I find_stats2.py` downloads the usage stats into `stats/`.
3. `python -I dump_bpe.py` reads BPE's species, moves and items into `bpe_data.json`.
4. `node gen_candidates.cjs` writes `cand/`, every candidate Showdown's validator accepts.
5. `node prune_candidates.cjs` writes `cand2/`, without sets that break set-building sense.
6. `node sim.cjs 60 . cand2 sim1`, then `node select_sets.cjs cand2 sim1 cand3 0`.
7. `node sim.cjs 150 . cand3 sim2`, then `node select_sets.cjs cand3 sim2 final 1`.
8. `node ag_sim_prepare.cjs`, `node sim.cjs 60 ^nd-AGmix ag_in ag_sim`, `node ag_sim_keep.cjs`.
   Pokémon in the AG tier itself are tested separately, against Ubers.
9. From `BPETools/frontier_sets/pipeline`, `node export_for_game.cjs` writes `sets.json` and
   `rules.json`.

The tests played 1.2 million battles on Showdown's engine with a simple damage-minded AI.
They catch weak sets but don't measure expert play, and they don't cover BPE-only changes.

## What the generator does

It drops a set that the game can't make: a move no list teaches that species, or an ability
the species doesn't have. It then drops a set from any pool whose rules it breaks. A tier
with fewer than 30 species fills up from the tiers below, because a Factory or Dome field
needs that many, and Anything Goes holds every tier. `make check TESTS=test/frontier_sets.c`
checks the same things against the game's real data.
