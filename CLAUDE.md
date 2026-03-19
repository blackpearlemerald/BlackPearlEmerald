# BPE Emerald - Project Guide

## Project Overview

**BPE Emerald** (Black Pearl Emerald) is a Pokémon ROM hack built on top of [pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion) v1.8.6 by RHH (Rom Hacking Hideout).

- Current version: **1.0.1**
- Base: pokeemerald-expansion 1.8.6 (GBA Pokémon Emerald decompilation)

## Project Structure

```
E:\Projects\PokemonBlackPearlEmerald\
├── CLAUDE.md                               ← This file
├── BPE Emerald V1.0.1\
│   └── pokeemerald-expansion\              ← Source code (git repo)
│       ├── src\                            ← C source files
│       ├── include\                        ← Headers, config files
│       │   └── config\                    ← Feature toggles (battle.h, pokemon.h, etc.)
│       ├── data\                           ← Game data (maps, Pokémon, items, etc.)
│       ├── graphics\                       ← Sprites, tilesets
│       ├── sound\                          ← Music, SFX
│       ├── asm\                            ← Assembly files
│       ├── tools\                          ← Build tools
│       ├── Makefile                        ← Build entry point
│       ├── pokeemerald.gba                 ← Compiled ROM (gitignored)
│       └── porymap.project.cfg             ← Porymap map editor config
└── pokeemerald-expansion_1.0.1_SOURCECODE.zip  ← Source backup
```

## Important Paths

- **Source root**: `BPE Emerald V1.0.1/pokeemerald-expansion/`
- **Config files**: `BPE Emerald V1.0.1/pokeemerald-expansion/include/config/`
- **Pokémon data**: `BPE Emerald V1.0.1/pokeemerald-expansion/src/data/`
- **Map data**: `BPE Emerald V1.0.1/pokeemerald-expansion/data/maps/`

## Building

Building requires a Unix-like build environment. Options (Windows):
1. **WSL1** (recommended, fastest) — needs to be installed first: `wsl --install -d Ubuntu`
2. **msys2** with devkitARM (second fastest)
3. **Cygwin** with devkitARM (slowest)

**WSL is NOT currently installed** on this machine.

### Build commands (run inside `BPE Emerald V1.0.1/pokeemerald-expansion/`):
```bash
make          # Standard build
make -j$(nproc)  # Parallel build (faster)
make clean    # Clean build artifacts
```

### Required tools (Ubuntu/WSL):
```bash
sudo apt install build-essential binutils-arm-none-eabi gcc-arm-none-eabi libnewlib-arm-none-eabi git libpng-dev
```

## Git Info

- Branch: `main` (created from detached HEAD at commit `ed784bef37`)
- Remotes: `origin`, `upstream` → rh-hideout/pokeemerald-expansion

## Key Config Files

Feature toggles live in `include/config/`:
- `battle.h` — Battle engine features
- `pokemon.h` — Pokémon-related features
- `item.h` — Item features
- `overworld.h` — Overworld features
- `debug.h` — Debug features

## Tools

- **porymap** — Map editor (configure via `porymap.project.cfg`)
- **poryscript** — Script language for event scripting
