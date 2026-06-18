"""
BPE Emerald Pokédex data parser.

Reads ROM source files and generates:
  site/data/pokedex_index.json   - Lightweight listing data (all species, basic fields)
  site/data/species/{KEY}.json   - Full data per species (moves, encounters, etc.)
  site/data/moves.json           - Move data (name/type/power/acc/pp/category)
  site/data/abilities.json       - Ability names and descriptions
  site/sprites/pokemon/{key}.png - 64x64 front sprites (first frame cropped)
  site/sprites/icons/{key}.png   - 32x32 icons (first frame cropped)

Usage:  py parse_pokemon.py
"""

import re, json, os, sys, glob, shutil
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent
DOC_ROOT = HERE.parent
REPO = DOC_ROOT.parent
SITE = DOC_ROOT / "site"
DATA_DIR = SITE / "data"
SPECIES_DIR = DATA_DIR / "species"
SPRITES_DIR = SITE / "sprites" / "pokemon"
ICONS_DIR = SITE / "sprites" / "icons"

# ── Helpers ────────────────────────────────────────────────────────────────────

def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def strip_c_comments(text):
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text

def find_blocks(content, start_pattern):
    """Yield (key, block_content) for each [KEY] = { ... } block."""
    pat = re.compile(start_pattern)
    pos = 0
    while pos < len(content):
        m = pat.search(content, pos)
        if not m:
            break
        key = m.group(1)
        i = m.end()
        # Find opening brace
        while i < len(content) and content[i] != '{':
            i += 1
        if i >= len(content):
            break
        i += 1  # skip '{'
        depth = 1
        while i < len(content) and depth > 0:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            i += 1
        yield key, content[m.end():i - 1]
        pos = i

def extract_compound_string(text):
    """Return plain text from COMPOUND_STRING content (strips quotes, collapses \\n)."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    joined = " ".join(parts)
    joined = joined.replace(r"\n", " ").replace("  ", " ").strip()
    return joined

def prettify_map(map_id):
    """MAP_ROUTE101 -> 'Route 101',  MAP_RUSTBORO_CITY -> 'Rustboro City'."""
    name = map_id.replace("MAP_", "").replace("_", " ").title()
    # Fix common abbreviations
    name = re.sub(r'\bB(\d+)F\b', r'B\1F', name)
    return name

# ── 1. National Dex Numbers ────────────────────────────────────────────────────

def parse_dex_numbers():
    path = REPO / "include" / "constants" / "pokedex.h"
    content = read_file(path)
    m = re.search(r"enum NationalDexOrder\s*\{(.*?)\}", content, re.DOTALL)
    if not m:
        return {}
    dex_map = {}
    current = 0
    for entry in re.finditer(r"NATIONAL_DEX_(\w+)(?:\s*=\s*(\d+))?", m.group(1)):
        name, val = entry.group(1), entry.group(2)
        if val:
            current = int(val)
        dex_map[name] = current
        current += 1
    return dex_map  # {"BULBASAUR": 1, "IVYSAUR": 2, ...}

# ── 2. Moves ───────────────────────────────────────────────────────────────────

def parse_moves():
    path = REPO / "src" / "data" / "moves_info.h"
    content = strip_c_comments(read_file(path))
    moves = {}
    for key, block in find_blocks(content, r"\[MOVE_(\w+)\]\s*="):
        name_m = re.search(r'\.name\s*=\s*COMPOUND_STRING\("([^"]+)"\)', block)
        if not name_m:
            continue
        # Type: may be a conditional; grab the first TYPE_X token after '.type ='
        type_m = re.search(r'\.type\s*=\s*(?:[^;]*?)\bTYPE_(\w+)', block)
        power_m = re.search(r'\.power\s*=\s*(\d+)', block)
        acc_m = re.search(r'\.accuracy\s*=\s*(\d+)', block)
        pp_m = re.search(r'\.pp\s*=\s*(\d+)', block)
        cat_m = re.search(r'\.category\s*=\s*DAMAGE_CATEGORY_(\w+)', block)
        moves[key] = {
            "name": name_m.group(1),
            "type": type_m.group(1) if type_m else "NORMAL",
            "power": int(power_m.group(1)) if power_m else 0,
            "accuracy": int(acc_m.group(1)) if acc_m else 0,
            "pp": int(pp_m.group(1)) if pp_m else 0,
            "category": cat_m.group(1) if cat_m else "STATUS",
        }
    return moves

# ── 3. Abilities ───────────────────────────────────────────────────────────────

def parse_abilities():
    path = REPO / "src" / "data" / "abilities.h"
    content = strip_c_comments(read_file(path))
    abilities = {}
    for key, block in find_blocks(content, r"\[ABILITY_(\w+)\]\s*="):
        name_m = re.search(r'\.name\s*=\s*_\("([^"]+)"\)', block)
        if not name_m:
            continue
        desc_m = re.search(r'\.description\s*=\s*COMPOUND_STRING\((.*?)\)(?=\s*[,}])', block, re.DOTALL)
        desc = extract_compound_string(desc_m.group(1)) if desc_m else ""
        abilities[key] = {"name": name_m.group(1), "description": desc}
    return abilities

# ── 4. TM / HM list ────────────────────────────────────────────────────────────

def parse_tms():
    path = REPO / "include" / "constants" / "tms_hms.h"
    content = read_file(path)
    tm_m = re.search(r"#define FOREACH_TM\(F\)\s*(.*?)(?=#define|\Z)", content, re.DOTALL)
    hm_m = re.search(r"#define FOREACH_HM\(F\)\s*(.*?)(?=#define|\Z)", content, re.DOTALL)
    tms = re.findall(r"F\((\w+)\)", tm_m.group(1)) if tm_m else []
    hms = re.findall(r"F\((\w+)\)", hm_m.group(1)) if hm_m else []
    return tms, hms  # both are MOVE_NAME without the MOVE_ prefix? No, they include just the name

# ── 5. Level-up learnsets ──────────────────────────────────────────────────────

def parse_level_up_learnsets():
    learnsets = {}
    learnset_dir = REPO / "src" / "data" / "pokemon" / "level_up_learnsets"
    pat = re.compile(
        r"static const struct LevelUpMove s(\w+)LevelUpLearnset\[\]\s*=\s*\{(.*?)\};",
        re.DOTALL,
    )
    for f in sorted(learnset_dir.glob("gen_*.h")):
        for name, body in pat.findall(read_file(f)):
            moves = [
                {"level": int(lv), "move": mv}
                for lv, mv in re.findall(r"LEVEL_UP_MOVE\(\s*(\d+)\s*,\s*MOVE_(\w+)\)", body)
            ]
            learnsets[name] = moves
    return learnsets

# ── 6. Egg moves ───────────────────────────────────────────────────────────────

def parse_egg_moves():
    path = REPO / "src" / "data" / "pokemon" / "egg_moves.h"
    content = read_file(path)
    egg_moves = {}
    pat = re.compile(r"static const u16 s(\w+)EggMoveLearnset\[\]\s*=\s*\{(.*?)\};", re.DOTALL)
    for name, body in pat.findall(content):
        moves = [mv for mv in re.findall(r"MOVE_(\w+)", body) if mv != "UNAVAILABLE"]
        egg_moves[name] = moves
    return egg_moves

# ── 7. Teachable learnsets (TM + tutor) ───────────────────────────────────────

def parse_teachable_learnsets():
    path = REPO / "src" / "data" / "pokemon" / "teachable_learnsets.h"
    content = read_file(path)
    teachable = {}
    pat = re.compile(r"static const u16 s(\w+)TeachableLearnset\[\]\s*=\s*\{(.*?)\};", re.DOTALL)
    for name, body in pat.findall(content):
        moves = [mv for mv in re.findall(r"MOVE_(\w+)", body) if mv != "UNAVAILABLE"]
        teachable[name] = moves
    return teachable

# ── 8. Wild encounters ─────────────────────────────────────────────────────────

def parse_encounters():
    path = REPO / "src" / "data" / "wild_encounters.json"
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    enc_types = ["land_mons", "water_mons", "rock_smash_mons", "fishing_mons"]
    species_enc = {}  # SPECIES_KEY -> list of encounter dicts

    for group in raw.get("wild_encounter_groups", []):
        for entry in group.get("encounters", []):
            map_id = entry.get("map", "")
            map_name = prettify_map(map_id)
            for enc_type in enc_types:
                if enc_type not in entry:
                    continue
                for mon in entry[enc_type].get("mons", []):
                    sp = mon["species"].replace("SPECIES_", "")
                    if sp not in species_enc:
                        species_enc[sp] = []
                    # Merge same map+type rows
                    existing = next(
                        (e for e in species_enc[sp] if e["map"] == map_id and e["type"] == enc_type),
                        None,
                    )
                    if existing:
                        existing["minLevel"] = min(existing["minLevel"], mon["min_level"])
                        existing["maxLevel"] = max(existing["maxLevel"], mon["max_level"])
                    else:
                        species_enc[sp].append({
                            "map": map_id,
                            "mapName": map_name,
                            "minLevel": mon["min_level"],
                            "maxLevel": mon["max_level"],
                            "type": enc_type,
                        })
    return species_enc

# ── 9. Species info ────────────────────────────────────────────────────────────

SKIP_SPECIES = {"NONE", "EGG", "OLD_UNOWN_B", "OLD_UNOWN_C", "OLD_UNOWN_D", "OLD_UNOWN_E"}

def _parse_evolutions(block):
    m = re.search(r"\.evolutions\s*=\s*EVOLUTION\((.*?)\)(?=\s*[,}])", block, re.DOTALL)
    if not m:
        return []
    evos = []
    for evo_m in re.finditer(r"\{(\w+),\s*(.*?),\s*SPECIES_(\w+)\}", m.group(1)):
        method, param, target = evo_m.group(1), evo_m.group(2).strip(), evo_m.group(3)
        evo = {"method": method, "target": target}
        if method in ("EVO_LEVEL", "EVO_LEVEL_ATK_GT_DEF", "EVO_LEVEL_ATK_LT_DEF",
                      "EVO_LEVEL_ATK_EQ_DEF", "EVO_LEVEL_RAIN", "EVO_LEVEL_NIGHT",
                      "EVO_LEVEL_DAY", "EVO_LEVEL_FEMALE", "EVO_LEVEL_MALE"):
            try:
                evo["level"] = int(param)
            except ValueError:
                evo["param"] = param
        elif "ITEM" in method:
            evo["item"] = param.replace("ITEM_", "").replace("_", " ").title()
        elif "MOVE" in method:
            evo["move"] = param.replace("MOVE_", "").replace("_", " ").title()
        else:
            evo["param"] = param
        evos.append(evo)
    return evos

def parse_species_info(dex_numbers, learnsets, egg_moves, teachable, encounters, tms, hms):
    tm_set = set(tms)
    hm_set = set(hms)
    all_species = {}

    info_dir = REPO / "src" / "data" / "pokemon" / "species_info"
    for gen_file in sorted(info_dir.glob("gen_*_families.h")):
        content = strip_c_comments(read_file(gen_file))
        for species_key, block in find_blocks(content, r"\[SPECIES_(\w+)\]\s*="):
            if species_key in SKIP_SPECIES:
                continue

            entry = {"id": species_key}

            # Name
            m = re.search(r'\.speciesName\s*=\s*_\("([^"]+)"\)', block)
            entry["name"] = m.group(1) if m else species_key.replace("_", " ").title()

            # Nat dex num
            m = re.search(r"\.natDexNum\s*=\s*NATIONAL_DEX_(\w+)", block)
            if m:
                nat = m.group(1)
                entry["natDexNum"] = dex_numbers.get(nat, 0)
            else:
                entry["natDexNum"] = 0
            # Fallback for forms defined via macros: strip trailing _SUFFIX parts
            if entry["natDexNum"] == 0:
                base = species_key
                while "_" in base:
                    base = base.rsplit("_", 1)[0]
                    if base in dex_numbers:
                        entry["natDexNum"] = dex_numbers[base]
                        break

            # Base stats
            stats = {}
            for src_key, dst_key in [
                ("baseHP", "hp"), ("baseAttack", "atk"), ("baseDefense", "def"),
                ("baseSpAttack", "spa"), ("baseSpDefense", "spd"), ("baseSpeed", "spe"),
            ]:
                sm = re.search(rf"\.{src_key}\s*=\s*(\d+)", block)
                stats[dst_key] = int(sm.group(1)) if sm else 0
            entry["baseStats"] = stats

            # Types
            m = re.search(r"\.types\s*=\s*MON_TYPES\(TYPE_(\w+)(?:,\s*TYPE_(\w+))?\)", block)
            entry["types"] = [m.group(1)] + ([m.group(2)] if m and m.group(2) else []) if m else ["NORMAL"]

            # Abilities
            m = re.search(
                r"\.abilities\s*=\s*\{\s*ABILITY_(\w+),\s*ABILITY_(\w+),\s*ABILITY_(\w+)\s*\}", block
            )
            if m:
                entry["abilities"] = [
                    ab if ab != "NONE" else None for ab in [m.group(1), m.group(2), m.group(3)]
                ]
            else:
                entry["abilities"] = [None, None, None]

            # Egg groups
            m = re.search(r"\.eggGroups\s*=\s*MON_EGG_GROUPS\(([^)]+)\)", block)
            entry["eggGroups"] = re.findall(r"EGG_GROUP_(\w+)", m.group(1)) if m else []

            # Gender ratio
            m = re.search(r"\.genderRatio\s*=\s*PERCENT_FEMALE\(([\d.]+)\)", block)
            if m:
                entry["genderRatio"] = float(m.group(1))
            elif "MON_GENDERLESS" in block:
                entry["genderRatio"] = -1
            elif re.search(r"\bMON_MALE\b", block):
                entry["genderRatio"] = 0.0
            elif re.search(r"\bMON_FEMALE\b", block):
                entry["genderRatio"] = 100.0
            else:
                entry["genderRatio"] = 50.0

            # Misc
            for field, dst, default in [
                ("catchRate", "catchRate", 255),
                ("expYield", "expYield", 0),
                ("height", "height", 0),
                ("weight", "weight", 0),
            ]:
                m = re.search(rf"\.{field}\s*=\s*(\d+)", block)
                entry[dst] = int(m.group(1)) if m else default

            m = re.search(r"\.growthRate\s*=\s*GROWTH_(\w+)", block)
            entry["growthRate"] = m.group(1).replace("_", " ").title() if m else "Medium Fast"

            m = re.search(r'\.categoryName\s*=\s*_\("([^"]+)"\)', block)
            entry["category"] = m.group(1) if m else ""

            # Description
            m = re.search(
                r"\.description\s*=\s*COMPOUND_STRING\((.*?)\)(?=\s*[,}])", block, re.DOTALL
            )
            entry["description"] = extract_compound_string(m.group(1)) if m else ""

            # Evolutions
            entry["evolutions"] = _parse_evolutions(block)

            # Learnsets (resolve by array name embedded in block)
            def get_array_name(field):
                am = re.search(rf"\.{field}\s*=\s*s(\w+)", block)
                return am.group(1) if am else None

            lvl_name = get_array_name("levelUpLearnset")
            egg_name = get_array_name("eggMoveLearnset")
            teach_name = get_array_name("teachableLearnset")

            entry["levelUpMoves"] = learnsets.get(lvl_name.replace("LevelUpLearnset",""), []) if lvl_name else []
            entry["eggMoves"] = egg_moves.get(egg_name.replace("EggMoveLearnset",""), []) if egg_name else []

            all_teach = teachable.get(teach_name.replace("TeachableLearnset",""), []) if teach_name else []
            entry["tmMoves"] = [mv for mv in all_teach if mv in tm_set]
            entry["hmMoves"] = [mv for mv in all_teach if mv in hm_set]
            entry["tutorMoves"] = [mv for mv in all_teach if mv not in tm_set and mv not in hm_set]

            # Wild encounters
            entry["encounters"] = encounters.get(species_key, [])

            # Sprite/icon paths filled in by copy_sprites()
            entry["sprite"] = None
            entry["icon"] = None

            all_species[species_key] = entry

    # Back-fill preEvolution pointers
    for key, entry in all_species.items():
        for evo in entry["evolutions"]:
            t = evo["target"]
            if t in all_species and "preEvolution" not in all_species[t]:
                all_species[t]["preEvolution"] = key

    return all_species

# ── 10. Sprites ────────────────────────────────────────────────────────────────

FORM_SUFFIXES = [
    ("_MEGA_X", "mega_x"), ("_MEGA_Y", "mega_y"), ("_MEGA_Z", "mega_z"),
    ("_MEGA", "mega"), ("_GMAX", "gmax"), ("_GIGANTAMAX", "gigantamax"),
    ("_ALOLAN", "alolan"), ("_GALARIAN", "galarian"), ("_HISUIAN", "hisuian"),
    ("_PALDEAN", "paldean"), ("_PRIMAL", "primal"), ("_ORIGIN", "origin"),
    ("_SKY", "sky"), ("_ATTACK", "attack"), ("_DEFENSE", "defense"),
    ("_SPEED", "speed"), ("_HEAT", "heat"), ("_WASH", "wash"),
    ("_FROST", "frost"), ("_FAN", "fan"), ("_MOW", "mow"),
    ("_SANDY", "sandy"), ("_TRASH", "trash"), ("_RAINY", "rainy"),
    ("_SNOWY", "snowy"), ("_SUNSHINE", "sunshine"), ("_PIROUETTE", "pirouette"),
    ("_SENSU", "sensu"), ("_PAU", "pau"), ("_POMPOM", "pompom"), ("_BAILE", "baile"),
    ("_MIDNIGHT", "midnight"), ("_DUSK", "dusk"), ("_DUSK_MANE", "dusk_mane"),
    ("_DAWN_WINGS", "dawn_wings"), ("_ULTRA", "ultra"),
    ("_INCARNATE", "incarnate"), ("_THERIAN", "therian"),
    ("_BLACK", "black"), ("_WHITE", "white"),
    ("_RESOLUTE", "resolute"), ("_ORDINARY", "ordinary"),
    ("_ARIA", "aria"), ("_COMPLETE", "complete"),
    ("_TEN_PERCENT", "ten_percent"), ("_FIFTY_PERCENT", "fifty_percent"),
    ("_FULL_BELLY", "full_belly"), ("_HANGRY", "hangry"),
    ("_CROWNED", "crowned"), ("_ETERNAMAX", "eternamax"),
    ("_ICE", "ice"), ("_SHADOW", "shadow"),
]

def _sprite_candidates(species_key, filename):
    name = species_key
    subfolder = None
    for suffix, folder in sorted(FORM_SUFFIXES, key=lambda x: -len(x[0])):
        if name.endswith(suffix):
            subfolder = folder
            name = name[: -len(suffix)]
            break
    base = name.lower()
    poke_dir = REPO / "graphics" / "pokemon" / base
    candidates = []
    if subfolder:
        candidates += [poke_dir / subfolder / filename, poke_dir / subfolder / filename.replace("anim_", "")]
    candidates.append(poke_dir / filename)
    return candidates

def find_sprite(species_key):
    for path in _sprite_candidates(species_key, "anim_front.png"):
        if path.exists():
            return path
    return None

def find_icon(species_key):
    for path in _sprite_candidates(species_key, "icon.png"):
        if path.exists():
            return path
    return None

def crop_and_save(src_path, dst_path, w, h):
    from PIL import Image
    img = Image.open(src_path)
    frame = img.crop((0, 0, w, h))
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    frame.save(dst_path, "PNG")

def copy_sprites(all_species):
    try:
        from PIL import Image
        has_pil = True
    except ImportError:
        has_pil = False
        print("  WARNING: Pillow not available — sprites won't be cropped")

    SPRITES_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    new_sprites = new_icons = missing = 0

    for key, entry in all_species.items():
        sp_name = key.lower() + ".png"

        src = find_sprite(key)
        dst = SPRITES_DIR / sp_name
        if src:
            entry["sprite"] = f"sprites/pokemon/{sp_name}"
            if not dst.exists():
                try:
                    crop_and_save(src, dst, 64, 64) if has_pil else shutil.copy2(src, dst)
                    new_sprites += 1
                except Exception as e:
                    print(f"  ! sprite {key}: {e}")
        else:
            missing += 1

        src = find_icon(key)
        dst = ICONS_DIR / sp_name
        if src:
            entry["icon"] = f"sprites/icons/{sp_name}"
            if not dst.exists():
                try:
                    crop_and_save(src, dst, 32, 32) if has_pil else shutil.copy2(src, dst)
                    new_icons += 1
                except Exception as e:
                    print(f"  ! icon {key}: {e}")

    print(f"  sprites: {new_sprites} new, {missing} not found")
    print(f"  icons:   {new_icons} new")

# ── 11. Output ─────────────────────────────────────────────────────────────────

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)

INDEX_FIELDS = ("id", "name", "natDexNum", "types", "baseStats", "abilities",
                "eggGroups", "catchRate", "expYield", "growthRate", "genderRatio",
                "category", "height", "weight", "sprite", "icon",
                "evolutions", "preEvolution")

def main():
    print("BPE Pokédex parser")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SPECIES_DIR.mkdir(parents=True, exist_ok=True)

    print("  [1] National dex numbers …")
    dex = parse_dex_numbers()
    print(f"       -> {len(dex)} entries")

    print("  [2] Moves ...")
    moves = parse_moves()
    print(f"       -> {len(moves)} moves")

    print("  [3] Abilities ...")
    abilities = parse_abilities()
    print(f"       -> {len(abilities)} abilities")

    print("  [4] TM/HM list ...")
    tms, hms = parse_tms()
    print(f"       -> {len(tms)} TMs, {len(hms)} HMs")

    print("  [5] Level-up learnsets ...")
    learnsets = parse_level_up_learnsets()
    print(f"       -> {len(learnsets)} learnsets")

    print("  [6] Egg moves ...")
    egg_moves = parse_egg_moves()
    print(f"       -> {len(egg_moves)} lists")

    print("  [7] Teachable learnsets ...")
    teachable = parse_teachable_learnsets()
    print(f"       -> {len(teachable)} lists")

    print("  [8] Wild encounters ...")
    encounters = parse_encounters()
    print(f"       -> {len(encounters)} species have encounters")

    print("  [9] Species info ...")
    all_species = parse_species_info(dex, learnsets, egg_moves, teachable, encounters, tms, hms)
    print(f"       -> {len(all_species)} species")

    print("  [10] Copying sprites ...")
    copy_sprites(all_species)

    print("  [11] Writing JSON ...")

    write_json(DATA_DIR / "moves.json", moves)
    write_json(DATA_DIR / "abilities.json", abilities)

    # Lightweight index for listing page
    index = {k: {f: v[f] for f in INDEX_FIELDS if f in v} for k, v in all_species.items()}
    write_json(DATA_DIR / "pokedex_index.json", index)

    # Full per-species files for detail pages
    for key, entry in all_species.items():
        write_json(SPECIES_DIR / f"{key}.json", entry)

    idx_kb = os.path.getsize(DATA_DIR / "pokedex_index.json") // 1024
    print(f"       -> pokedex_index.json: {idx_kb} KB")
    print(f"       -> {len(all_species)} species JSON files")
    print(f"       -> moves.json + abilities.json")

    with_sprite = sum(1 for e in all_species.values() if e["sprite"])
    with_enc = sum(1 for e in all_species.values() if e["encounters"])
    print(f"\nDone!  {with_sprite}/{len(all_species)} sprites  |  {with_enc} with encounters")


if __name__ == "__main__":
    main()
