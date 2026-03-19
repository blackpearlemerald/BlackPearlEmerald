# BPE Emerald - Project Guide

## Project Overview

**BPE Emerald** (Black Pearl Emerald) is a Pokémon GBA ROM hack originally built on [pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion) v1.8.6 by RHH (Rom Hacking Hideout), and has since been upgraded to v1.15.0. It is a decompilation-based hack, not a binary patch — the full source is compiled from C/ASM into a `.gba` ROM.

- **Version**: 1.0.1
- **Original base**: pokeemerald-expansion v1.8.6
- **Current expansion version**: v1.15.0
- **Build status**: Clean build confirmed (32 MB ROM, no errors)
- **Branch**: `main` (HEAD `58f9e1afea`)

### Enabled Features
- `B_TERA_MECHANICS GEN_LATEST` — Terastallization enabled
- `OW_FOLLOWERS_ENABLED TRUE` — Follower Pokémon enabled
- `OW_ENABLE_DNS FALSE` — Day/Night System disabled

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

- **Branch**: `main` (HEAD `58f9e1afea`, merged upgrade-to-1.14.4)
- **Remotes**: `origin`, `upstream` → rh-hideout/pokeemerald-expansion

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

### map_event_ids.h
BPE-added file (not in upstream). After each upgrade, new NPC LOCALIDs used by map scripts must be **manually added** by cross-referencing `map.json` object positions against `setvar`/`applymovement` calls in `scripts.inc`. Missing LOCALIDs cause linker errors.

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
