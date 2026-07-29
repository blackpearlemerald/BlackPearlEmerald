# BPE Emerald - Project Guide

## Project Overview

**BPE Emerald** (Black Pearl Emerald) is a Pokémon GBA ROM hack originally built on [pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion) v1.8.6 by RHH (Rom Hacking Hideout), and has since been upgraded to v1.16.3. It is a decompilation-based hack, not a binary patch — the full source is compiled from C/ASM into a `.gba` ROM.

- **Version**: 1.0.1
- **Original base**: pokeemerald-expansion v1.8.6
- **Current expansion version**: v1.16.3 (tag `expansion/1.16.3`, merged 2026-07-28)
- **Build status**: Clean build confirmed (32 MB ROM, 86.52% ROM / 86.62% EWRAM / 87.15% IWRAM)
- **Branch**: `main` (HEAD `79dd7888cb`)

### Enabled Features
- `B_TERA_MECHANICS GEN_LATEST` — Terastallization enabled
- `OW_FOLLOWERS_ENABLED TRUE` — Follower Pokémon enabled
- `OW_ENABLE_DNS TRUE` — Day/Night System enabled (implemented in `src/day_night.c`)

### Debug builds are the default
`RELEASE ?= 0`, and `-DRELEASE` is only added by the `release`/`tidyrelease` targets. So in a plain `make`, every `DISABLED_ON_RELEASE` toggle in `include/config/debug.h` resolves to **enabled**: debug menus are on, and `assertf`/`fatal_assertf` compile to the resumable crash screen rather than being stripped. An upstream assertion that BPE data violates will show a crash screen in-game.

---

## Project Structure

```
E:\Projects\PokemonBlackPearlEmerald\
├── CLAUDE.md                               ← Root notes (outdated; see source root CLAUDE.md)
├── BPE Emerald V1.0.1\
│   └── pokeemerald-expansion\              ← Source code (git repo) ← WORK HERE
│       ├── src\                            ← C source files
│       ├── include\                        ← Headers
│       │   └── config\                    ← Feature toggles (battle.h, pokemon.h, etc.)
│       ├── data\                           ← Game data (maps, Pokémon, items, scripts)
│       │   ├── maps\                       ← Per-map folders (map.json, scripts.inc, etc.)
│       │   └── text\                       ← Text includes (frontier_brain.inc lives here)
│       ├── graphics\                       ← Sprites, tilesets
│       ├── sound\                          ← Music/SFX (.wav format as of 1.14.x)
│       ├── asm\                            ← Assembly files
│       │   └── macros\battle_script.inc   ← Battle script macros
│       ├── tools\                          ← Build tools
│       ├── Makefile                        ← Build entry point
│       └── pokeemerald.gba                 ← Compiled ROM (gitignored)
└── pokeemerald-expansion_1.0.1_SOURCECODE.zip
```

**The source directory path contains spaces** — always quote paths in shell commands:
```bash
cd "BPE Emerald V1.0.1/pokeemerald-expansion"
```

---

## Building

**WSL (Ubuntu) is installed** on this machine. Build inside WSL.

### Build commands (run inside `BPE Emerald V1.0.1/pokeemerald-expansion/`):
```bash
make              # Standard build
make -j$(nproc)   # Parallel build (faster)
make clean        # Clean build artifacts
```

### Required tools (Ubuntu/WSL):
```bash
sudo apt install build-essential binutils-arm-none-eabi gcc-arm-none-eabi libnewlib-arm-none-eabi git libpng-dev
```

---

## Git Info

- **Branch**: `main` (merged `upgrade-to-1.16.3`). There is **no** `master` branch.
- **Remotes**: `origin` → BlackPearlEmerald/PokemonBlackPearlEmerald (the only push target); `upstream` and `RHH` → rh-hideout/pokeemerald-expansion; `AsaparagusEdu` and `mudskipper13` are read-only forks.

### Upgrading to a new expansion release
Start by computing which files can actually conflict — it turns an unknown-size merge into a scoped one:
```bash
git fetch RHH master --tags
git diff --name-only expansion/<old> expansion/<new> | sort > /tmp/up.txt
git diff --name-only expansion/<old> main            | sort > /tmp/bpe.txt
comm -12 /tmp/up.txt /tmp/bpe.txt    # only these can conflict
```
For each file in the intersection, compare hunk headers on both sides (`git diff <old> <ref> -- <file> | grep '^@@'`); hunks more than ~3 lines apart auto-merge. Then merge the **tag**, not `RHH/master`, and diff a pre/post-merge grep-count audit of every BPE custom symbol to prove nothing was silently dropped.

---

## Key Config Files

Feature toggles live in `include/config/`:
- `battle.h` — Battle engine features (Mega Evo, Z-Moves, Tera, exp settings, etc.)
- `pokemon.h` — Pokémon features (egg groups, abilities, etc.)
- `item.h` — Item behavior features
- `overworld.h` — Overworld features (followers, DNS, etc.)
- `debug.h` — Debug mode features

---

## Tools

- **porymap** — Map editor (configured via `porymap.project.cfg`; user config files are gitignored)
- **poryscript** — Script language for event scripting (`use_poryscript=0` — using regular mapscripts)
- **Python**: use `py` (not `python3`) on this machine; always write scripts to a file and run with `py script.py` (shell escaping breaks backslashes in one-liners)

---

## Known Quirks & Upgrade Notes

### Species Naming
BPE uses full suffixes (`_GALARIAN`, `_ALOLAN`, `_HISUIAN`, `_PALDEAN`); upstream uses shorter forms. BPE names are kept; aliases are added in `species.h`.

### Preserved BPE Files
- `data/text/frontier_brain.inc` — deleted upstream but required by BPE; kept manually.

### Script File Encoding
Always use `newline=''` when writing `.s` files via Python to prevent CRLF line endings.

### Event Script Constants
- `ALLOCATE_SCRIPT_CMD_TABLE` must be set to `1` before the `script_cmd_table.inc` include in `event_scripts.s`.
- The `setvar` macro has a `.if` guard requiring constant values — undefined LOCALID symbols become **linker errors**.
- The `map` macro `.ifdef` check was reverted (incompatible with BPE's C-macro map constants).

### map_event_ids.h (and friends) — generated, do not hand-edit
`include/constants/map_event_ids.h` is **auto-generated by mapjson** from the `"local_id"` attributes on `map.json` objects, and is gitignored via `include/constants/.gitignore`. Editing it by hand gets silently overwritten on the next build. To add a LOCALID, add `"local_id": <object_events index + 1>` to the object in its `map.json`.

Same rule for the other generated+gitignored headers in that directory: `map_groups.h`, `layouts.h`, `region_map_sections.h`, `heal_locations.h`.

**Exception:** the working-tree copy of `include/constants/layouts.h` is manually curated — BPE deleted the FRLG `data/layouts/*` folders but `layouts.json` still lists them, so 29 layouts are stubbed to `0xFFFF`. A full regeneration breaks the INCBINs. Never let make regenerate it (it won't unless `layouts.json`'s mtime changes); if new upstream code references an FRLG `LAYOUT_*`, patch the C code instead.

### Item Numbering (1.14.x conflict resolved)
Upstream added 26 new Mega Stone items (CLEFABLITE–FALINKSITE) at indices 829–854, conflicting with BPE's custom HM layout (HM01–HM08 at 824–831).
**Fix**: Upstream Mega Stones renumbered to 976–1001; `ITEMS_COUNT=1002`.

### Audio Format (1.14.x)
All audio changed from `.aif` to `.wav` in upstream 1.14.x — already applied wholesale.

### Battle Script Macro Renames (1.14.x)
In `asm/macros/battle_script.inc`: `attackstring` → `printattackstring` (and other renames).

### Cumulative API Changes by Version

| Version | Change |
|---------|--------|
| 1.12.x | `InBattlePyramid` → `InBattlePyramid_()` |
| 1.12.x | `GetPartyBattlerData` → `GetBattlerMon` |
| 1.12.x | Hold effects consolidated to `HOLD_EFFECT_TYPE_POWER` (aliases added) |
| 1.13.x | `STATUS2` bitfield → `volatiles` struct in battle C files |
| 1.13.x | `setgraphicalstatchangevalues`/`playstatchangeanimation` removed → use `setstatchanger`/`statbuffchange` |
| 1.13.x | `LZDecompressWram` → `DecompressDataWithHeaderWram` |
| 1.13.x | `sFieldMoves[j]` → `FieldMove_GetMoveId(j)` |
| 1.14.x | NPC scripts refactored to use `LOCALID_*` symbols — ~25 new LOCALIDs per upgrade |
| 1.14.x | `LOCALID_VERDANTURF_MART_CLERK` added for `GetMartEmployeeObjectEventId` |
