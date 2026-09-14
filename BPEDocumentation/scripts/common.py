"""Shared config + read-only parsing helpers for the BPE Emerald map docs.

NOTHING in this package ever writes to the game source tree. SRC_ROOT is opened
read-only; all generated output goes under BPEDocumentation/site/.
"""
import json
import os
import re

# --- Paths -------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DOC_ROOT = os.path.dirname(HERE)                      # BPEDocumentation/
PROJECT_ROOT = os.path.dirname(DOC_ROOT)              # repo root (pokeemerald-expansion)
# BPEDocumentation lives inside the game source repo, so the repo root is the
# source root. Fall back to the old top-level layout if run from there.
SRC_ROOT = os.path.abspath(os.environ.get("BPE_SOURCE_ROOT", PROJECT_ROOT))
if not os.path.isdir(os.path.join(SRC_ROOT, "data", "maps")):
    SRC_ROOT = os.path.join(PROJECT_ROOT, "BPE Emerald V1.0.1", "pokeemerald-expansion")

SITE = os.path.abspath(os.environ.get("BPE_SITE_ROOT", os.path.join(DOC_ROOT, "site")))
SITE_DATA = os.path.join(SITE, "js", "data")
SITE_MAPS_IMG = os.path.join(SITE, "img", "maps")

# --- GBA tileset constants (from include/fieldmap.h) -------------------------
NUM_TILES_IN_PRIMARY = 512
NUM_PALS_IN_PRIMARY = 6
NUM_METATILES_IN_PRIMARY = 512
NUM_PALS_TOTAL = 13

MAPGRID_METATILE_ID_MASK = 0x03FF  # bits 0-9

# Metatile tile entry (u16): tileId 0-9, hflip 10, vflip 11, palette 12-15
TILE_ID_MASK = 0x03FF
TILE_HFLIP = 0x0400
TILE_VFLIP = 0x0800
TILE_PAL_SHIFT = 12


def src(*parts):
    return os.path.join(SRC_ROOT, *parts)


def ensure_dirs():
    for d in (SITE, SITE_DATA, SITE_MAPS_IMG,
              os.path.join(SITE, "js"), os.path.join(SITE, "css"),
              os.path.join(SITE, "img"), os.path.join(SITE, "lib")):
        os.makedirs(d, exist_ok=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


def iter_map_jsons():
    """Yield (map_dir_name, parsed_json) for every data/maps/<X>/map.json."""
    maps_dir = src("data", "maps")
    for name in sorted(os.listdir(maps_dir)):
        mj = os.path.join(maps_dir, name, "map.json")
        if os.path.isfile(mj):
            try:
                yield name, load_json(mj)
            except Exception as e:
                raise ValueError(f"Cannot read map {name}: {e}") from e


def load_jasc_pal(path):
    """Return list of 16 (r,g,b) tuples from a JASC-PAL file."""
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    # lines[0]=JASC-PAL, [1]=0100, [2]=count, then RGB triplets
    colors = []
    for ln in lines[3:]:
        parts = ln.split()
        if len(parts) >= 3:
            colors.append((int(parts[0]), int(parts[1]), int(parts[2])))
    while len(colors) < 16:
        colors.append((0, 0, 0))
    return colors[:16]


def prettify_constant(name):
    """ITEM_SILK_SCARF -> Silk Scarf ; TRAINER_CALVIN_1 -> Calvin 1."""
    if not name:
        return name
    for prefix in ("ITEM_", "TRAINER_", "SPECIES_", "MOVE_", "ABILITY_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return " ".join(w.capitalize() for w in name.split("_"))
