# Black Pearl Emerald Save Inspector

This repository-local command-line tool reads a player's Pokémon Emerald `.sav` or `.srm` without launching an emulator. It was adapted from the MIT-licensed [Pokemon Emulator Tracker](https://github.com/paulthemagno/pokemon-emulator-tracker) Gen 3 parser and extended for Black Pearl Emerald's compiled save structures, expanded data, custom Pokémon packing, and `SaveBlock3`.

The inspector is read-only. It never changes the supplied save.

## Quick start

Use the ROM that the player used. A known published ROM automatically selects its exact release profile:

```powershell
tools\bpe-save-inspector\bpe-save-inspector.cmd inspect "C:\path\player.srm" --rom "BlackPearlEmerald_v2.0.1.gba" -o ".save-debug\player-report.json"
```

If no ROM is available, put the release profile before the command:

```powershell
tools\bpe-save-inspector\bpe-save-inspector.cmd --profile 2.0.1 inspect "C:\path\player.sav" -o ".save-debug\player-report.json"
```

The complete report includes sector/checksum health, selected save slot, trainer and location, money, inventory, party, every occupied PC slot, every persistent flag bit, all persistent variables, game statistics, Pokédex bits, and custom `SaveBlock3` fields. Each reconstructed block also has a size and SHA-256 hash.

## Debug a flag or variable against game logic

```powershell
tools\bpe-save-inspector\bpe-save-inspector.cmd --profile 2.0.1 query "C:\path\player.srm" FLAG_BADGE01_GET VAR_STARTER_MON -o ".save-debug\progression-query.json"
```

`query` reports the current saved value and every explicit set, clear, write, read, or gate found in the exact release source commit. It includes file names, line numbers, and nearby source context. The operation labels are deliberately conservative; story meaning must be established from the surrounding script or function.

## Other commands

```powershell
# Compare progression state before and after an event.
tools\bpe-save-inspector\bpe-save-inspector.cmd --profile 2.0.1 diff "before.srm" "after.srm" -o ".save-debug\difference.json"

# Extract all four reconstructed binary blocks and a checksum manifest.
tools\bpe-save-inspector\bpe-save-inspector.cmd --profile 2.0.1 extract "player.srm" ".save-debug\raw-blocks"

# Decode every field in one compiled C structure. PokemonStorage output is large.
tools\bpe-save-inspector\bpe-save-inspector.cmd --profile 2.0.1 dump "player.srm" SaveBlock1 -o ".save-debug\save-block-1.json"

# Embed all reconstructed bytes as base64 in the normal report.
tools\bpe-save-inspector\bpe-save-inspector.cmd --profile 2.0.1 inspect "player.srm" --include-raw -o ".save-debug\complete-report.json"
```

Bundled profiles:

- `2.0.0-beta` — source commit `4f39a49bd4e8cb1adead8b8f2e7999d957c6bcb1`
- `2.0.1` — source commit `6c25a87610754b62145b83095b4290d00c27831e`

The unversioned `bpe_layout.json` and `bpe_symbols.json` describe the current working source. A save does not contain a reliable BPE release identifier, so supply a matching ROM or explicit profile. Structural ROM checks catch offset changes, but only a pinned release profile guarantees the correct flag names and source logic.

An `.srm` is supported when it contains raw GBA flash SRAM—the normal format used by mGBA, RetroArch, and many other emulators. Emulator save states such as `.state` are not SRAM and are rejected. Common files with a small wrapper around the 128 KiB SRAM payload are detected by their aligned sector signatures.

## Verification and layout refresh

Run the focused tests:

```powershell
python -m unittest tools\bpe-save-inspector\tests\test_bpe_inspector.py -v
```

After the project's save structures, flags, variables, species, items, or moves change, regenerate the current profile:

```powershell
python tools\bpe-save-inspector\generate_layout.py
```

Regeneration uses the installed WSL ARM compiler and the vendored `pyelftools` copy. Normal inspection requires only Python 3 and does not need network access, Node.js, an emulator, or a running game.
