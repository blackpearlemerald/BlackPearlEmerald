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
import common as C

# ── Paths ──────────────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent
DOC_ROOT = HERE.parent
REPO = Path(C.SRC_ROOT)
SITE = Path(C.SITE)
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

_GEN_CONFIG_CACHE = {}

def gen_config():
    """Resolve GEN_* and every `#define NAME GEN_x` config to its integer value.

    moves_info.h writes gen-gated fields as `FIELD = B_UPDATED_MOVE_DATA >= GEN_9 ? a : b`,
    so evaluating those needs the numeric value of both sides of the comparison.
    """
    if _GEN_CONFIG_CACHE:
        return _GEN_CONFIG_CACHE
    config_path = REPO / "include/config/general.h"
    if not config_path.exists():
        config_path = REPO / "include/config.h"
    general = strip_c_comments(read_file(config_path))
    for m in re.finditer(r"#define\s+(GEN_\w+)\s+(\d+)\s*$", general, re.M):
        _GEN_CONFIG_CACHE[m.group(1)] = int(m.group(2))
    # GEN_LATEST is defined in terms of another GEN_ constant.
    m = re.search(r"#define\s+GEN_LATEST\s+(GEN_\w+)", general)
    if m:
        _GEN_CONFIG_CACHE["GEN_LATEST"] = _GEN_CONFIG_CACHE.get(m.group(1), 8)
    # Config toggles that gate move data, e.g. B_UPDATED_MOVE_DATA, B_HIDDEN_POWER_DMG.
    for cfg in ("battle.h", "pokemon.h"):
        text = strip_c_comments(read_file(REPO / "include" / "config" / cfg))
        for m in re.finditer(r"#define\s+([A-Z]\w+)\s+(GEN_\w+)\s*$", text, re.M):
            if m.group(2) in _GEN_CONFIG_CACHE:
                _GEN_CONFIG_CACHE[m.group(1)] = _GEN_CONFIG_CACHE[m.group(2)]
    return _GEN_CONFIG_CACHE

def read_num_field(block, field, default=0):
    """Read `.field = N` or `.field = CONFIG >= GEN_x ? a : b` from a struct block."""
    m = re.search(r"\.%s\s*=\s*([^,;}]+)" % field, block)
    if not m:
        return default
    expr = m.group(1).strip()
    if expr.isdigit():
        return int(expr)
    t = re.match(r"\(?\s*(\w+)\s*(>=|>|<=|<|==|!=)\s*(GEN_\w+)\s*\)?\s*\?\s*(\d+)\s*:\s*(\d+)", expr)
    if t:
        cfg = gen_config()
        lhs, op, rhs = cfg.get(t.group(1)), t.group(2), cfg.get(t.group(3))
        if lhs is None or rhs is None:
            return int(t.group(4))  # unknown config: assume the modern branch
        ok = {">=": lhs >= rhs, ">": lhs > rhs, "<=": lhs <= rhs,
              "<": lhs < rhs, "==": lhs == rhs, "!=": lhs != rhs}[op]
        return int(t.group(4) if ok else t.group(5))
    m = re.search(r"\d+", expr)
    return int(m.group(0)) if m else default

def prettify_map(map_id):
    """MAP_ROUTE101 -> 'Route 101',  MAP_RUSTBORO_CITY -> 'Rustboro City'."""
    name = map_id.replace("MAP_", "").replace("_", " ").title()
    # Fix common abbreviations
    name = re.sub(r'\bB(\d+)F\b', r'B\1F', name)
    name = re.sub(r'\bRoute(\d)', r'Route \1', name)
    return name

# ── 1. National Dex Numbers ────────────────────────────────────────────────────

def parse_dex_numbers():
    path = REPO / "include" / "constants" / "pokedex.h"
    content = read_file(path)
    m = re.search(r"enum(?:\s+NationalDexOrder)?\s*\{(.*?)\}", content, re.DOTALL)
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

def parse_species_aliases(defines=False):
    """Parse `SPECIES_X = SPECIES_Y` aliases from species.h → {X: Y}.

    Used to find each form-family's canonical default form (e.g.
    SPECIES_ALCREMIE = SPECIES_ALCREMIE_STRAWBERRY = …_VANILLA_CREAM).
    With `defines`, BPE's `#define SPECIES_MEOWTH_ALOLAN SPECIES_MEOWTH_ALOLA`
    names are included too, for resolving what scripts and wild tables use."""
    path = REPO / "include" / "constants" / "species.h"
    content = read_file(path)
    alias = {}
    for m in re.finditer(r"\bSPECIES_(\w+)\s*=\s*SPECIES_(\w+)\b", content):
        alias[m.group(1)] = m.group(2)
    if defines:
        for m in re.finditer(r"^\s*#define\s+SPECIES_(\w+)\s+SPECIES_(\w+)\s*$", content, re.M):
            alias.setdefault(m.group(1), m.group(2))
    return alias

# ── 2. Moves ───────────────────────────────────────────────────────────────────

def parse_moves():
    path = REPO / "src" / "data" / "moves_info.h"
    content = strip_c_comments(read_file(path))
    moves = {}
    for key, block in find_blocks(content, r"\[MOVE_(\w+)\]\s*="):
        name_m = re.search(r'\.name\s*=\s*(?:COMPOUND_STRING|HANDLE_EXPANDED_MOVE_NAME)\("([^"]+)"', block)
        if not name_m:
            continue
        # Type: may be a conditional; grab the first TYPE_X token after '.type ='
        type_m = re.search(r'\.type\s*=\s*(?:[^;]*?)\bTYPE_(\w+)', block)
        cat_m = re.search(r'\.category\s*=\s*DAMAGE_CATEGORY_(\w+)', block)
        moves[key] = {
            "name": name_m.group(1),
            "type": type_m.group(1) if type_m else "NORMAL",
            "power": read_num_field(block, "power"),
            "accuracy": read_num_field(block, "accuracy"),
            "pp": read_num_field(block, "pp"),
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
    if (REPO / "src/data/pokemon/all_learnables.json").exists():
        from teachable_data import build
        return build(REPO)
    content = read_file(path)
    teachable = {}
    pat = re.compile(r"static const u16 s(\w+)TeachableLearnset\[\]\s*=\s*\{(.*?)\};", re.DOTALL)
    for name, body in pat.findall(content):
        moves = [mv for mv in re.findall(r"MOVE_(\w+)", body) if mv != "UNAVAILABLE"]
        teachable[name] = moves
    return teachable

# ── 8. Wild encounters ─────────────────────────────────────────────────────────

def parse_hoenn_map_ids():
    """Set of map IDs that actually exist in this game as Hoenn-region maps.

    BPE removed the FRLG (Kanto / Sevii Islands) maps, but
    `wild_encounters.json` still carries stale encounter entries for them.
    Those maps have no `map.json` (or a REGION_KANTO one). Historical Emerald
    sources omit `region` entirely because every included map is in Hoenn."""
    hoenn = set()
    for mj in (REPO / "data" / "maps").glob("*/map.json"):
        try:
            with open(mj, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if d.get("region", "REGION_HOENN") == "REGION_HOENN" and d.get("id"):
            hoenn.add(d["id"])
    return hoenn

def read_island_legendary_pool():
    """(level, [BARE_SPECIES ...]) for the Mirage Island legendary lottery,
    parsed from sIslandLegendaryPool[] in src/field_specials.c so the site
    stays in sync with the game's actual pool."""
    txt = (REPO / "src" / "field_specials.c").read_text(encoding="utf-8")
    lvl_m = re.search(r"#define\s+ISLAND_LEGENDARY_LEVEL\s+(\d+)", txt)
    level = int(lvl_m.group(1)) if lvl_m else 70
    arr = re.search(r"sIslandLegendaryPool\[\]\s*=\s*\{(.*?)\};", txt, re.S)
    species = re.findall(r"SPECIES_([A-Z0-9_]+)", arr.group(1)) if arr else []
    return level, species


def read_pre_e4_legendaries():
    """{BARE_SPECIES: needs the 8th badge} for sPreE4Legendaries[] in
    src/field_specials.c, the legendaries of which only one can be caught
    before the Champion. Empty for releases without the list."""
    txt = strip_c_comments((REPO / "src" / "field_specials.c").read_text(encoding="utf-8"))
    arr = re.search(r"sPreE4Legendaries\[\]\s*=\s*\{(.*?)\};", txt, re.S)
    if not arr:
        return {}
    return {sp: badge == "TRUE" for sp, badge in
            re.findall(r"\{\s*SPECIES_(\w+)\s*,\s*\w+\s*,\s*\w+\s*,\s*(TRUE|FALSE)\s*\}", arr.group(1))}


def read_mirage_altar_species():
    """[BARE_SPECIES ...] the Mirage Altar on Route 130 can call back, from the
    VAR_0x8004 values its script checks. Empty for releases without the altar."""
    path = REPO / "data" / "maps" / "Route130" / "scripts.inc"
    if not path.is_file():
        return []
    txt = path.read_text(encoding="utf-8")
    start = txt.find("Route130_EventScript_MirageAltar::")
    if start < 0:
        return []
    # Up to the next label: the script body, not its menu helpers.
    after = start + len("Route130_EventScript_MirageAltar::")
    end = re.search(r"^\w+::", txt[after:], re.M)
    body = txt[start:after + end.start() if end else len(txt)]
    return re.findall(r"setvar VAR_0x8004, SPECIES_(\w+)\s*\n\s*special CheckAltarSpeciesCaught", body)


# Notes on the Pokédex's location rows for the legendaries, so a player knows
# when each one is there as well as where.
PRE_E4_NOTE = ("Before you become Champion, only one of the pre-Champion legendaries can be caught; "
               "the others hide until the Hall of Fame. Comes back until caught.")
STORY_LEGENDARY_NOTE = "Comes back until caught."
MIRAGE_NOTE = "After the Hall of Fame. Each visit, the island offers one legendary you haven't caught."
ALTAR_NOTE = "After the Hall of Fame, once you've caught one. The altar calls back as many as you like."


def load_static_encounters():
    """Scripted overworld encounters (legendaries, Snorlax, Kecleon...) that
    extract_world.py already wrote to world.json for this release."""
    path = Path(C.SITE_DATA) / "world.json"
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("statics") or []


def read_wild_form_variants():
    """[(BASE, chance, [FORM ...]), ...] from src/data/wild_form_variants.h: the
    forms a wild species can appear in. Releases before the table existed have
    no file, and no variants."""
    path = REPO / "src" / "data" / "wild_form_variants.h"
    if not path.is_file():
        return []
    txt = strip_c_comments(path.read_text(encoding="utf-8"))
    arrays = {name: re.findall(r"SPECIES_(\w+)", body)
              for name, body in re.findall(r"u16 (s\w+)\[\]\s*=\s*\{(.*?)\};", txt, re.S)}
    return [(base, int(chance), arrays.get(forms, []))
            for base, chance, forms in re.findall(r"VARIANTS\(SPECIES_(\w+),\s*(\d+),\s*(s\w+)\)", txt)]


def read_wild_held_item_rules():
    """(normal, boosted, [ABILITY ...]) for wild held items, read from
    SetWildMonHeldItem() and CanFirstMonBoostHeldItemRarity() in src/pokemon.c.

    `normal` and `boosted` are (common %, rare %). The abilities are the ones
    that raise the odds when leading the party in this release: 1.0.1 set
    OW_COMPOUND_EYES and OW_SUPER_LUCK so that neither did."""
    txt = strip_c_comments(read_file(REPO / "src" / "pokemon.c"))

    def odds(var, boosted, default):
        m = re.search(rf"{var}\s*=\s*itemHeldBoost\s*\?\s*(\d+)\s*:\s*(\d+)", txt)
        return int(m.group(1 if boosted else 2)) if m else default

    def split(boosted):
        no_item = odds("chanceNoItem", boosted, 20 if boosted else 45)
        not_rare = odds("chanceNotRare", boosted, 80 if boosted else 95)
        return not_rare - no_item, 100 - not_rare

    config = dict(gen_config())
    overworld = strip_c_comments(read_file(REPO / "include" / "config" / "overworld.h"))
    for m in re.finditer(r"#define\s+(OW_\w+)\s+(GEN_\w+)\s*$", overworld, re.M):
        if m.group(2) in config:
            config[m.group(1)] = config[m.group(2)]

    abilities = []
    body = re.search(r"CanFirstMonBoostHeldItemRarity\(void\)\s*\{(.*?)\n\}", txt, re.S)
    for cond in re.findall(r"if\s*\((.*)\)\s*$", body.group(1) if body else "", re.M):
        ability = re.search(r"ability\s*==\s*ABILITY_(\w+)", cond)
        if not ability:
            continue
        rest = re.sub(r"&&\s*ability\s*==\s*ABILITY_\w+|ability\s*==\s*ABILITY_\w+\s*(&&)?", "", cond).strip()
        # An unknown config means the ability can't be shown to boost.
        if not rest or _eval_config_condition(rest, config):
            abilities.append(ability.group(1))
    return split(False), split(True), abilities


def wild_held_items(common, rare, rules):
    """[{"item", "pct", "boostPct"}, ...] for a species' itemCommon/itemRare,
    following SetWildMonHeldItem(): the same item in both slots is always held."""
    (norm_c, norm_r), (boost_c, boost_r), boosters = rules
    if not boosters:
        boost_c, boost_r = norm_c, norm_r
    if common and common == rare:
        return [{"item": common, "pct": 100, "boostPct": 100}]
    out = []
    if common:
        out.append({"item": common, "pct": norm_c, "boostPct": boost_c})
    if rare:
        out.append({"item": rare, "pct": norm_r, "boostPct": boost_r})
    return out


def parse_encounters(statics=()):
    path = REPO / "src" / "data" / "wild_encounters.json"
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Wild tables may name a form family by its alias (SPECIES_FLORGES is
    # SPECIES_FLORGES_RED); species pages use the form's own name.
    species_h = REPO / "include" / "constants" / "species.h"
    aliases = parse_species_aliases(defines=True) if species_h.is_file() else {}

    def resolve(name):
        seen = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return name

    hoenn_maps = parse_hoenn_map_ids()
    enc_types = ["land_mons", "water_mons", "rock_smash_mons", "fishing_mons"]
    species_enc = {}  # SPECIES_KEY -> list of encounter dicts

    for group in raw.get("wild_encounter_groups", []):
        for entry in group.get("encounters", []):
            map_id = entry.get("map", "")
            # Skip FRLG / non-Hoenn maps that aren't in this game.
            if map_id not in hoenn_maps:
                continue
            map_name = prettify_map(map_id)
            for enc_type in enc_types:
                if enc_type not in entry:
                    continue
                for mon in entry[enc_type].get("mons", []):
                    sp = resolve(mon["species"].replace("SPECIES_", ""))
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

    # Static encounters: one row per species and map, linked to that map.
    pre_e4 = read_pre_e4_legendaries()
    for st in statics:
        sp = resolve(st["species"].replace("SPECIES_", ""))
        rows = species_enc.setdefault(sp, [])
        if any(e["map"] == st["mapId"] and e["type"] == "static" for e in rows):
            continue
        row = {
            "map": st["mapId"],
            "mapName": st.get("place") or prettify_map(st["mapId"]),
            "minLevel": st["level"],
            "maxLevel": st["level"],
            "type": "static",
        }
        if st.get("preE4") and sp in pre_e4:
            row["note"] = ("Appears after the 8th Gym. " if pre_e4[sp] else "") + PRE_E4_NOTE
        elif st.get("legendary") and pre_e4:
            row["note"] = STORY_LEGENDARY_NOTE
        rows.append(row)

    # Legendary Lottery Island: every pool legendary gets a "Mirage Island"
    # location (Route 130) whose link snaps to the island on the map.
    mirage_level, mirage_pool = read_island_legendary_pool()
    for sp in mirage_pool:
        species_enc.setdefault(sp, []).append({
            "map": "MAP_ROUTE130",  # Route 130 is drawn with the island layout
            "mapName": "Mirage Island",
            "minLevel": mirage_level,
            "maxLevel": mirage_level,
            "type": "mirage",
            "note": MIRAGE_NOTE,
        })

    # The Mirage Altar calls back another of a legendary already caught, which
    # is what its evolutions and forms need.
    for sp in read_mirage_altar_species():
        species_enc.setdefault(resolve(sp), []).append({
            "map": "MAP_ROUTE130",
            "mapName": "Mirage Altar",
            "minLevel": mirage_level,
            "maxLevel": mirage_level,
            "type": "altar",
            "note": ALTAR_NOTE,
        })

    # Wild form variants: each form is found wherever its species is, with a
    # note saying how often.
    wild_types = set(enc_types)
    for base, chance, forms in read_wild_form_variants():
        base = resolve(base)
        rows = [e for e in species_enc.get(base, []) if e["type"] in wild_types]
        name = base.split("_")[0].title()
        forms = [resolve(f) for f in forms]
        if chance >= 100:
            note = f"Random form, 1 of {len(forms)}"
        elif len(forms) > 1:
            note = f"{chance}% of {name}, 1 of {len(forms)} forms"
        else:
            note = f"{chance}% of {name}"
        for form in forms:
            for row in rows:
                if form == base:
                    row["note"] = note
                else:
                    species_enc.setdefault(form, []).append(dict(row, note=note))

    return species_enc

# ── 9. Species info ────────────────────────────────────────────────────────────

SKIP_SPECIES = {"NONE", "EGG", "OLD_UNOWN_B", "OLD_UNOWN_C", "OLD_UNOWN_D", "OLD_UNOWN_E"}

def _extract_paren_content(text, start):
    """Return text inside matching parens starting at `start` (which must be '(')."""
    depth = 1
    i = start + 1
    while i < len(text) and depth > 0:
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
        i += 1
    return text[start + 1 : i - 1]

def _extract_brace_entries(text):
    """Yield each top-level {...} string from `text` (handles nested braces)."""
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 1
            j = i + 1
            while j < len(text) and depth > 0:
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                j += 1
            yield text[i:j]
            i = j
        else:
            i += 1

def _parse_conditions(cond_str):
    """Parse CONDITIONS({IF_X, A, B}, ...) → [["IF_X", "A", "B"], ...]."""
    conds = []
    for m in re.finditer(r"\{\s*(IF_\w+)\s*(?:,([^{}]*))?\}", cond_str):
        args = [a.strip() for a in (m.group(2) or "").split(",") if a.strip()]
        conds.append([m.group(1)] + args)
    return conds

def _parse_evolutions(block):
    m = re.search(r"\.evolutions\s*=\s*EVOLUTION\(", block)
    if not m:
        return []

    # Use paren-counting to extract the full EVOLUTION(...) content,
    # avoiding truncation at the first ')' inside nested CONDITIONS(...) calls.
    evo_content = _extract_paren_content(block, m.end() - 1)

    evos = []
    for entry in _extract_brace_entries(evo_content):
        # Each entry is like:
        #   {EVO_ITEM, ITEM_THUNDER_STONE, SPECIES_JOLTEON}
        #   {EVO_LEVEL, 0, SPECIES_UMBREON, CONDITIONS({IF_MIN_FRIENDSHIP,...},{IF_TIME,...})}
        em = re.match(r"\{\s*(\w+),\s*([^,{]+),\s*SPECIES_(\w+)(.*)\}$", entry.strip(), re.DOTALL)
        if not em:
            continue
        method = em.group(1)
        param  = em.group(2).strip()
        target = em.group(3)
        rest   = em.group(4).strip()   # e.g. ", CONDITIONS(...)" or ""

        # Skip non-evolution entries (e.g. inner condition braces that leaked through)
        if not method.startswith("EVO_"):
            continue

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

        evo["rawParam"] = param
        if "CONDITIONS" in rest:
            conds = _parse_conditions(rest)
            if conds:
                evo["conditions"] = conds

        evos.append(evo)

    # Shedinja appears when its sibling evolves, so it shares that level.
    for evo in evos:
        if evo["method"] == "EVO_SPLIT_FROM_EVO":
            evo["splitFrom"] = evo["rawParam"].replace("SPECIES_", "")
            for other in evos:
                if other["target"] == evo["splitFrom"] and other.get("level"):
                    evo["level"] = other["level"]
    return evos

def _collect_stat_macros(content):
    """Extract #define NAME (P_UPDATED_STATS ... ? val1 : val2) -> {NAME: val1}."""
    macros = {}
    # BPE uses P_UPDATED_STATS >= GEN_LATEST so always take the first (modern) branch
    for m in re.finditer(r"#define\s+(\w+)\s+\(.*?P_UPDATED_STATS.*?\?\s*(\d+)\s*:", content):
        macros[m.group(1)] = int(m.group(2))
    # Newer source also places numeric stat macros in #if/#elif branches.
    def select_branch(match):
        branches = re.split(r"^\s*#(?:if|elif)\s+(P_UPDATED_STATS[^\n]+)\n|^\s*#(else)\s*\n", match[0], flags=re.M)
        for i in range(1, len(branches), 3):
            condition, otherwise, body = branches[i:i + 3]
            if otherwise or read_num_field(".choice = " + condition + " ? 1 : 0,", "choice"):
                return body
        return ""
    selected = re.sub(r"^\s*#if\s+P_UPDATED_STATS[^\n]+\n.*?^\s*#endif[^\n]*", select_branch, content, flags=re.M | re.S)
    for m in re.finditer(r"^\s*#define\s+(\w+)\s+(\d+)\s*$", selected, re.M):
        macros.setdefault(m[1], int(m[2]))
    return macros

def _eval_config_condition(expression, config=None):
    """Evaluate a simple C config comparison, or return None if it is unknown."""
    m = re.fullmatch(r"\s*\(?\s*(\w+)\s*(>=|>|<=|<|==|!=)\s*(\w+|\d+)\s*\)?\s*", expression)
    if not m:
        return None
    config = config or gen_config()

    def value(token):
        return int(token) if token.isdigit() else config.get(token)

    lhs, rhs = value(m.group(1)), value(m.group(3))
    if lhs is None or rhs is None:
        return None
    return {
        ">=": lhs >= rhs,
        ">": lhs > rhs,
        "<=": lhs <= rhs,
        "<": lhs < rhs,
        "==": lhs == rhs,
        "!=": lhs != rhs,
    }[m.group(2)]

def _collect_object_macros(raw_content):
    """Collect active object-like macros while honoring known config branches.

    Unknown feature guards are intentionally treated as active so that this
    source parser can still inspect family-local definitions. Known generation
    comparisons, including P_UPDATED_TYPES, select the same branch as the game.
    """
    text = strip_c_comments(_join_line_continuations(raw_content))
    macros = {}
    frames = []
    active = True

    for line in text.splitlines():
        directive = re.match(r"\s*#\s*(if|elif|else|endif)\b\s*(.*)", line)
        if directive:
            kind, expression = directive.groups()
            if kind == "if":
                result = _eval_config_condition(expression)
                frames.append({
                    "parent": active,
                    "known": result is not None,
                    "taken": bool(result),
                })
                active = active and (bool(result) if result is not None else True)
            elif kind == "elif" and frames:
                frame = frames[-1]
                if frame["known"]:
                    result = _eval_config_condition(expression)
                    active = frame["parent"] and not frame["taken"] and bool(result)
                    frame["taken"] = frame["taken"] or bool(result)
                else:
                    active = frame["parent"]
            elif kind == "else" and frames:
                frame = frames[-1]
                active = frame["parent"] and (not frame["taken"] if frame["known"] else True)
                frame["taken"] = True
            elif kind == "endif" and frames:
                active = frames.pop()["parent"]
            continue

        if not active:
            continue
        define = re.match(r"\s*#\s*define\s+(\w+)[ \t]+(.+?)\s*$", line)
        if define:
            macros[define.group(1)] = define.group(2)

    return macros

def _expand_object_macros(expression, macros):
    """Recursively expand object-like macros in a field initializer."""
    for _ in range(25):
        expanded = re.sub(
            r"\b[A-Za-z_]\w*\b",
            lambda match: f"({macros[match.group(0)]})" if match.group(0) in macros else match.group(0),
            expression,
        )
        if expanded == expression:
            return expanded
        expression = expanded
    return expression

def _resolve_type_conditionals(expression):
    """Resolve generation-gated TYPE_X ternaries inside a type initializer."""
    conditional = re.compile(
        r"\(\s*(\w+)\s*(>=|>|<=|<|==|!=)\s*(\w+|\d+)\s*"
        r"\?\s*(TYPE_\w+)\s*:\s*(TYPE_\w+)\s*\)"
    )
    for _ in range(25):
        match = conditional.search(expression)
        if not match:
            break
        result = _eval_config_condition(" ".join(match.group(i) for i in (1, 2, 3)))
        if result is None:
            break
        expression = expression[:match.start()] + match.group(4 if result else 5) + expression[match.end():]
    return expression

def _read_field_initializer(block, field):
    """Read a C field initializer through its top-level trailing comma."""
    match = re.search(rf"\.{re.escape(field)}\s*=\s*", block)
    if not match:
        return None
    start = match.end()
    depth = 0
    for i in range(start, len(block)):
        if block[i] in "({[":
            depth += 1
        elif block[i] in ")}]":
            depth -= 1
        elif block[i] == "," and depth == 0:
            return block[start:i].strip()
    return block[start:].strip()

def _parse_species_types(block, type_macros):
    """Resolve literal or macro-defined species types for the active config."""
    expression = _read_field_initializer(block, "types")
    if expression is None:
        return ["NORMAL"]
    expression = _resolve_type_conditionals(_expand_object_macros(expression, type_macros))
    resolved = []
    for type_name in re.findall(r"\bTYPE_(\w+)\b", expression):
        if type_name not in resolved:
            resolved.append(type_name)
    if not resolved:
        raise ValueError(f"Unable to resolve species type initializer: {expression}")
    return resolved

# ── Macro-defined species expansion ─────────────────────────────────────────────
#
# Many cosmetic / regional forms (Vivillon, Alcremie, Mothim, Scatterbug, Unown …)
# are NOT written as `[SPECIES_X] = { ... }` brace blocks.  Instead they are macro
# instantiations like:
#
#     [SPECIES_SCATTERBUG_ICY_SNOW] = SCATTERBUG_SPECIES_INFO(ICY_SNOW),
#
# where the macro body uses `##` token-pasting to build the per-form evolution
# target (e.g. SPECIES_SPEWPA_##evolution -> SPECIES_SPEWPA_ICY_SNOW).
#
# The naïve brace scanner cannot handle these — it skips forward to the next `{`,
# stealing an unrelated species' body (corrupting data) and silently eating the
# species declarations in between.  We fix that by collecting the `#define`
# macros and expanding the invocation into a real brace block before parsing.

def _join_line_continuations(raw):
    """Join C backslash-newline line continuations into single logical lines."""
    return re.sub(r"\\\s*\n", " ", raw)

def _read_paren(text, i):
    """text[i] must be '('. Return (inner_text, index_after_close)."""
    assert text[i] == "("
    depth = 0
    start = i
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return text[start + 1:], len(text)

def _split_top_args(s):
    """Split macro arg list on top-level commas (ignoring nested parens/braces)."""
    args, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1; cur += ch
        elif ch in ")]}":
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            args.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip() or args:
        args.append(cur)
    return [a.strip() for a in args]

def collect_macros(raw_content):
    """Collect #define macros (function-like and object-like) whose body is a
    species-info fragment.  Returns {name: (params_or_None, body_text)}."""
    text = strip_c_comments(_join_line_continuations(raw_content))
    macros = {}
    # Function-like:  NAME(...)  — '(' must immediately follow the name (C rule).
    # Object-like:    NAME       — at least one space before the body.
    for m in re.finditer(r"#define\s+(\w+)(\([^()]*\))?[ \t]+(.*)", text):
        name = m.group(1)
        params = None
        if m.group(2):
            params = [p.strip() for p in m.group(2)[1:-1].split(",") if p.strip()]
        body = m.group(3).strip()
        # Only keep macros that actually carry species-info fields, to avoid
        # clobbering value macros / unrelated defines.
        if ".base" in body or "_MISC_INFO" in body or ".speciesName" in body \
           or ".natDexNum" in body or ".evolutions" in body or ".types" in body:
            macros[name] = (params, body)
    return macros

def expand_macros(text, macros, _seen=(), _depth=0):
    """Recursively expand any macro invocations found in `text`."""
    if _depth > 25:
        return text
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "_" or ch.isalpha():
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            if word in macros and word not in _seen:
                params, body = macros[word]
                k = j
                args = None
                if params is not None:
                    while k < n and text[k] in " \t\n":
                        k += 1
                    if k < n and text[k] == "(":
                        inner, k = _read_paren(text, k)
                        args = _split_top_args(inner)
                ebody = body
                if params:
                    # The ## paste operator concatenates tokens and absorbs any
                    # surrounding whitespace (e.g. `SPECIES_FLOETTE_ ##FORM` →
                    # `SPECIES_FLOETTE_FORM`). Normalise that before substituting.
                    ebody = re.sub(r"\s*##\s*", "##", ebody)
                    for p, a in zip(params, args or []):
                        # token-paste first (foo##p, p##bar), then whole-word.
                        # Only whole tokens: in `sMinior##Form##FormChangeTable`
                        # the parameter Form must not eat into FormChangeTable.
                        ident = re.escape(p)
                        ebody = re.sub(r"##" + ident + r"(?!\w)", lambda _: a, ebody)
                        ebody = re.sub(r"(?<!\w)" + ident + r"##", lambda _: a, ebody)
                        ebody = re.sub(r"\b" + ident + r"\b", lambda _: a, ebody)
                ebody = ebody.replace("##", "")  # drop any stray paste operators
                out.append(expand_macros(ebody, macros, _seen + (word,), _depth + 1))
                i = k if params is not None else j
                continue
            out.append(word)
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)

def iter_species_decls(content, macros):
    """Yield (species_key, block_text) for every `[SPECIES_X] = ...` declaration,
    handling both brace blocks and macro instantiations."""
    for m in re.finditer(r"\[SPECIES_(\w+)\]\s*=\s*", content):
        key = m.group(1)
        j = m.end()
        if j >= len(content):
            continue
        if content[j] == "{":
            # Plain brace block — extract with brace matching.
            depth, i = 0, j
            while i < len(content):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            # Brace blocks may still embed field-list macros such as
            # FLABEBE_MISC_INFO(Red, RED, 1) — expand those so stats/types/
            # evolutions inside them are parsed.
            yield key, expand_macros(content[j + 1:i], macros)
        else:
            # Macro instantiation: NAME or NAME(args)
            mm = re.match(r"(\w+)\s*", content[j:])
            if not mm:
                continue
            mname = mm.group(1)
            if mname not in macros:
                continue  # unknown / non-species macro — skip (no corruption)
            # Isolate just this invocation (NAME or NAME(...)) before expanding,
            # so we don't recursively expand the rest of the file.
            after = j + mm.end()
            inv_end = after
            if macros[mname][0] is not None and after < len(content) and content[after] == "(":
                _, inv_end = _read_paren(content, after)
            expanded = expand_macros(content[j:inv_end], macros).lstrip()
            # Extract the first balanced brace block from the expansion.
            bi = expanded.find("{")
            if bi < 0:
                continue
            depth, i = 0, bi
            while i < len(expanded):
                if expanded[i] == "{":
                    depth += 1
                elif expanded[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            yield key, expanded[bi + 1:i]

# ── Evolution method labels ──────────────────────────────────────────────────────
#
# Every condition the game checks (GetEvolutionTargetSpecies in src/pokemon.c)
# is written out, so a label never says "Level up" when more is needed. Older
# sources name one rule per method (EVO_LEVEL_FEMALE, EVO_ITEM_HOLD_NIGHT, ...)
# instead of listing CONDITIONS; _normalize_evo translates them first.

# The player never leaves Hoenn (include/regions.h), as in
# BPETools/audit_living_dex.py, so other regions' evolutions cannot happen.
CURRENT_REGION = "REGION_HOENN"

# Old method → (current method, whether the old param is the level, conditions).
# "P" stands for the old param and "SELF" for the evolving species.
_LEGACY_EVOS = {
    "EVO_FRIENDSHIP": ("EVO_LEVEL", False, [["IF_MIN_FRIENDSHIP"]]),
    "EVO_FRIENDSHIP_DAY": ("EVO_LEVEL", False, [["IF_MIN_FRIENDSHIP"], ["IF_NOT_TIME", "TIME_NIGHT"]]),
    "EVO_FRIENDSHIP_NIGHT": ("EVO_LEVEL", False, [["IF_MIN_FRIENDSHIP"], ["IF_TIME", "TIME_NIGHT"]]),
    "EVO_TRADE_ITEM": ("EVO_TRADE", False, [["IF_HOLD_ITEM", "P"]]),
    "EVO_TRADE_SPECIFIC_MON": ("EVO_TRADE", False, [["IF_TRADE_PARTNER_SPECIES", "P"]]),
    "EVO_LEVEL_ATK_GT_DEF": ("EVO_LEVEL", True, [["IF_ATK_GT_DEF"]]),
    "EVO_LEVEL_ATK_EQ_DEF": ("EVO_LEVEL", True, [["IF_ATK_EQ_DEF"]]),
    "EVO_LEVEL_ATK_LT_DEF": ("EVO_LEVEL", True, [["IF_ATK_LT_DEF"]]),
    "EVO_LEVEL_SILCOON": ("EVO_LEVEL", True, [["IF_PID_UPPER_MODULO_10_GT", "4"]]),
    "EVO_LEVEL_CASCOON": ("EVO_LEVEL", True, [["IF_PID_UPPER_MODULO_10_LT", "5"]]),
    "EVO_LEVEL_NINJASK": ("EVO_LEVEL", True, []),
    "EVO_LEVEL_SHEDINJA": ("EVO_SPLIT_FROM_EVO", True, []),
    "EVO_BEAUTY": ("EVO_LEVEL", False, [["IF_MIN_BEAUTY", "P"]]),
    "EVO_LEVEL_FEMALE": ("EVO_LEVEL", True, [["IF_GENDER", "MON_FEMALE"]]),
    "EVO_LEVEL_MALE": ("EVO_LEVEL", True, [["IF_GENDER", "MON_MALE"]]),
    "EVO_LEVEL_NIGHT": ("EVO_LEVEL", True, [["IF_TIME", "TIME_NIGHT"]]),
    "EVO_LEVEL_DAY": ("EVO_LEVEL", True, [["IF_NOT_TIME", "TIME_NIGHT"]]),
    "EVO_LEVEL_DUSK": ("EVO_LEVEL", True, [["IF_TIME", "TIME_EVENING"]]),
    "EVO_LEVEL_RAIN": ("EVO_LEVEL", True, [["IF_WEATHER", "WEATHER_RAIN"]]),
    "EVO_LEVEL_FOG": ("EVO_LEVEL", True, [["IF_WEATHER", "WEATHER_FOG"]]),
    "EVO_LEVEL_DARK_TYPE_MON_IN_PARTY": ("EVO_LEVEL", True, [["IF_TYPE_IN_PARTY", "TYPE_DARK"]]),
    "EVO_LEVEL_NATURE_AMPED": ("EVO_LEVEL", True, [["IF_AMPED_NATURE"]]),
    "EVO_LEVEL_NATURE_LOW_KEY": ("EVO_LEVEL", True, [["IF_LOW_KEY_NATURE"]]),
    "EVO_LEVEL_FAMILY_OF_FOUR": ("EVO_LEVEL", True, [["IF_PID_MODULO_100_GT", "0"]]),
    "EVO_LEVEL_FAMILY_OF_THREE": ("EVO_LEVEL", True, [["IF_PID_MODULO_100_EQ", "0"]]),
    "EVO_ITEM_HOLD": ("EVO_LEVEL", False, [["IF_HOLD_ITEM", "P"]]),
    "EVO_ITEM_HOLD_DAY": ("EVO_LEVEL", False, [["IF_HOLD_ITEM", "P"], ["IF_NOT_TIME", "TIME_NIGHT"]]),
    "EVO_ITEM_HOLD_NIGHT": ("EVO_LEVEL", False, [["IF_HOLD_ITEM", "P"], ["IF_TIME", "TIME_NIGHT"]]),
    "EVO_ITEM_MALE": ("EVO_ITEM", False, [["IF_GENDER", "MON_MALE"]]),
    "EVO_ITEM_FEMALE": ("EVO_ITEM", False, [["IF_GENDER", "MON_FEMALE"]]),
    "EVO_ITEM_DAY": ("EVO_ITEM", False, [["IF_NOT_TIME", "TIME_NIGHT"]]),
    "EVO_ITEM_NIGHT": ("EVO_ITEM", False, [["IF_TIME", "TIME_NIGHT"]]),
    "EVO_DARK_SCROLL": ("EVO_SCRIPT_TRIGGER", False, []),
    "EVO_WATER_SCROLL": ("EVO_SCRIPT_TRIGGER", False, []),
    "EVO_MOVE": ("EVO_LEVEL", False, [["IF_KNOWS_MOVE", "P"]]),
    "EVO_MOVE_TWO_SEGMENT": ("EVO_LEVEL", False, [["IF_KNOWS_MOVE", "P"], ["IF_PID_MODULO_100_GT", "0"]]),
    "EVO_MOVE_THREE_SEGMENT": ("EVO_LEVEL", False, [["IF_KNOWS_MOVE", "P"], ["IF_PID_MODULO_100_EQ", "0"]]),
    "EVO_FRIENDSHIP_MOVE_TYPE": ("EVO_LEVEL", False, [["IF_MIN_FRIENDSHIP"], ["IF_KNOWS_MOVE_TYPE", "P"]]),
    "EVO_MAPSEC": ("EVO_LEVEL", False, [["IF_IN_MAPSEC", "P"]]),
    "EVO_SPECIFIC_MAP": ("EVO_LEVEL", False, [["IF_IN_MAP", "P"]]),
    "EVO_SPECIFIC_MON_IN_PARTY": ("EVO_LEVEL", False, [["IF_SPECIES_IN_PARTY", "P"]]),
    "EVO_CRITICAL_HITS": ("EVO_BATTLE_END", False, [["IF_CRITICAL_HITS_GE", "P"]]),
    "EVO_SCRIPT_TRIGGER_DMG": ("EVO_SCRIPT_TRIGGER", False, [["IF_CURRENT_DAMAGE_GE", "P"]]),
    "EVO_LEVEL_MOVE_TWENTY_TIMES": ("EVO_LEVEL", False, [["IF_USED_MOVE_X_TIMES", "P", "20"]]),
    "EVO_USE_MOVE_TWENTY_TIMES": ("EVO_LEVEL", False, [["IF_USED_MOVE_X_TIMES", "P", "20"]]),
    "EVO_LEVEL_RECOIL_DAMAGE_MALE": ("EVO_LEVEL", False, [["IF_RECOIL_DAMAGE_GE", "P"], ["IF_GENDER", "MON_MALE"]]),
    "EVO_LEVEL_RECOIL_DAMAGE_FEMALE": ("EVO_LEVEL", False, [["IF_RECOIL_DAMAGE_GE", "P"], ["IF_GENDER", "MON_FEMALE"]]),
    "EVO_RECOIL_DAMAGE_MALE": ("EVO_LEVEL", False, [["IF_RECOIL_DAMAGE_GE", "P"], ["IF_GENDER", "MON_MALE"]]),
    "EVO_RECOIL_DAMAGE_FEMALE": ("EVO_LEVEL", False, [["IF_RECOIL_DAMAGE_GE", "P"], ["IF_GENDER", "MON_FEMALE"]]),
    "EVO_ITEM_COUNT_999": ("EVO_LEVEL", False, [["IF_BAG_ITEM_COUNT", "P", "999"]]),
    "EVO_DEFEAT_THREE_WITH_ITEM": ("EVO_LEVEL", False, [["IF_DEFEAT_X_WITH_ITEMS", "SELF", "P", "3"]]),
    "EVO_OVERWORLD_STEPS": ("EVO_LEVEL", False, [["IF_MIN_OVERWORLD_STEPS", "P"]]),
}

# 1.0.1 gives Charmander EVO_LEVEL_AND_EVO_CHARM, which no game code handles.
_IMPOSSIBLE_METHODS = {"EVO_NONE", "EVO_LEVEL_AND_EVO_CHARM"}

_TIMES = {"TIME_NIGHT": "night", "TIME_EVENING": "evening", "TIME_MORNING": "morning", "TIME_DAY": "day"}
# Qualifiers that only decide which of several forms appears.
_FORM_PICKERS = ("gender", "nature", "chance")


def _normalize_evo(evo, source):
    """Return (method, level, conditions) in the current CONDITIONS vocabulary."""
    method = evo["method"]
    param = evo.get("rawParam", "")
    level = evo.get("level") or 0
    conds = [list(c) for c in evo.get("conditions", [])]
    if method in _LEGACY_EVOS:
        method, keeps_level, extra = _LEGACY_EVOS[method]
        level = int(param) if keeps_level and param.isdigit() else level
        subst = {"P": param, "SELF": "SPECIES_" + source}
        conds = [[subst.get(a, a) for a in c] for c in extra] + conds
    elif method == "EVO_LEVEL_BATTLE_ONLY" and param.isdigit():
        level = int(param)
    return method, level, conds


def _evo_possible(evo, source, names):
    """False for evolutions nothing in the game can trigger."""
    method, _, conds = _normalize_evo(evo, source)
    if evo["method"] in _IMPOSSIBLE_METHODS:
        return False
    # Script evolutions only happen where a map script runs tryspecialevo.
    if evo["method"] == "EVO_SCRIPT_TRIGGER" and evo.get("rawParam") not in names.script_triggers:
        return False
    if method == "EVO_SCRIPT_TRIGGER" and not names.script_triggers:
        return False
    for cond, *args in conds:
        if cond == "IF_REGION" and args and args[0] != CURRENT_REGION:
            return False
        if cond == "IF_NOT_REGION" and args and args[0] == CURRENT_REGION:
            return False
    return True


def _chance(cond, arg):
    a = int(arg)
    return {"IF_PID_MODULO_100_GT": 99 - a, "IF_PID_MODULO_100_EQ": 1, "IF_PID_MODULO_100_LT": a,
            "IF_PID_UPPER_MODULO_10_GT": (9 - a) * 10, "IF_PID_UPPER_MODULO_10_EQ": 10,
            "IF_PID_UPPER_MODULO_10_LT": a * 10}[cond]


def _evo_label(evo, source, names, form_pickers=True):
    """One readable line for an evolution. Without form_pickers, the qualifiers
    that only choose between forms shown as one Pokémon are summarised."""
    method, level, conds = _normalize_evo(evo, source)
    if method == "EVO_SPIN":
        return "Spin holding a Sweet"

    base = None
    words, notes, pickers = [], [], []
    friendship = any(c[0] == "IF_MIN_FRIENDSHIP" for c in conds)
    for cond, *args in conds:
        a = args + [""] * 3
        if cond == "IF_HOLD_ITEM":
            words.append("holding " + names.item(a[0]))
        elif cond == "IF_KNOWS_MOVE":
            words.append("knowing " + names.move(a[0]))
        elif cond == "IF_KNOWS_MOVE_TYPE":
            words.append("knowing a " + names.type(a[0]) + "-type move")
        elif cond == "IF_USED_MOVE_X_TIMES":
            words.append(f"after using {names.move(a[0])} {a[1]} times")
        elif cond == "IF_RECOIL_DAMAGE_GE":
            amount = "" if a[0] == "1" else a[0] + " "
            words.append(f"after taking {amount}recoil damage without fainting")
        elif cond == "IF_DEFEAT_X_WITH_ITEMS":
            words.append(f"after defeating {a[2]} {names.species(a[0])} holding {names.item(a[1])}")
        elif cond == "IF_MIN_OVERWORLD_STEPS":
            words.append(f"after walking {int(a[0]):,} steps as the party leader")
        elif cond == "IF_CURRENT_DAMAGE_GE":
            words.append(f"while missing at least {a[0]} HP")
        elif cond == "IF_SPECIES_IN_PARTY":
            words.append(f"with {names.species(a[0])} in the party")
        elif cond == "IF_TYPE_IN_PARTY":
            words.append(f"with a {names.type(a[0])}-type Pokémon in the party")
        elif cond == "IF_BAG_ITEM_COUNT":
            count, item = int(a[1] or 1), names.item(a[0])
            words.append(f"with a {item} in the bag" if count == 1
                         else f"with {count:,} {item}{'' if item.endswith('s') else 's'} in the bag")
        elif cond == "IF_TRADE_PARTNER_SPECIES":
            words.append("for " + names.species(a[0]))
        elif cond in ("IF_IN_MAP", "IF_IN_MAPSEC"):
            words.append("in " + names.place(a[0]))
        elif cond == "IF_WEATHER":
            words.append("in " + a[0].replace("WEATHER_", "").replace("_", " ").lower())
        elif cond == "IF_MIN_BEAUTY":
            words.append(f"with {a[0]}+ Beauty")
        elif cond in ("IF_ATK_GT_DEF", "IF_ATK_EQ_DEF", "IF_ATK_LT_DEF"):
            words.append("with Attack " + {"GT": ">", "EQ": "=", "LT": "<"}[cond[7:9]] + " Defense")
        elif cond in ("IF_TIME", "IF_NOT_TIME"):
            when = _TIMES.get(a[0], a[0].replace("TIME_", "").lower())
            notes.append(("not at " if cond == "IF_NOT_TIME" else "") + when)
        elif cond == "IF_GENDER":
            pickers.append(("gender", "male" if a[0] == "MON_MALE" else "female"))
        elif cond in ("IF_AMPED_NATURE", "IF_LOW_KEY_NATURE"):
            pickers.append(("nature", ("Amped" if cond == "IF_AMPED_NATURE" else "Low Key") + " nature"))
        elif cond.startswith("IF_PID_"):
            pickers.append(("chance", f"{_chance(cond, a[0])}% chance"))
        elif cond == "IF_CRITICAL_HITS_GE":
            base = f"Land {a[0]} critical hit{'' if a[0] == '1' else 's'} in one battle"
        elif cond not in ("IF_MIN_FRIENDSHIP", "IF_REGION", "IF_NOT_REGION"):
            words.append(cond.replace("IF_", "").replace("_", " ").lower())

    if base is None:
        if method in ("EVO_LEVEL", "EVO_LEVEL_BATTLE_ONLY"):
            base = f"Lv. {level}" if level else ("Friendship" if friendship else "Level up")
            if method == "EVO_LEVEL_BATTLE_ONLY":
                base += " in battle"
        elif method == "EVO_ITEM":
            base = names.item(evo.get("rawParam", ""))
        elif method == "EVO_TRADE":
            base = "Trade"
        elif method == "EVO_BATTLE_END":
            base = "After a battle"
        elif method == "EVO_SPLIT_FROM_EVO":
            base = (f"Lv. {level}" if level else "Level up") + " with a free party slot"
        elif method == "EVO_SCRIPT_TRIGGER":
            base = "Special event"
        else:
            base = method.replace("EVO_", "").replace("_", " ").title()
    if words and method == "EVO_SPLIT_FROM_EVO" and words[0].startswith("with "):
        words[0] = "and " + words[0][5:]
    elif words and (base == "Friendship" or method == "EVO_ITEM"):
        base += ","

    if form_pickers:
        notes += [text for _, text in pickers]
    else:
        notes += ["form by " + kind for kind in _FORM_PICKERS if any(k == kind for k, _ in pickers)]
    label = " ".join([base] + words)
    return label + (f" ({', '.join(notes)})" if notes else "")


class EvoNames:
    """Display names for the constants an evolution label mentions."""

    def __init__(self, moves=None, species=None):
        self.moves = moves or {}
        self.species_names = species or {}
        self.items = _read_item_names()
        self.mapsecs = _read_mapsec_names()
        self.script_triggers = _read_script_evo_triggers()

    @staticmethod
    def _readable(name, key):
        # Older sources squeeze names into 12 characters ("ScrllOfDrknss").
        if not name or (" " not in name and re.search(r"[a-z][A-Z]", name)):
            return key.replace("_", " ").title()
        return name

    def move(self, const):
        key = const.replace("MOVE_", "")
        return self._readable(self.moves.get(key, {}).get("name"), key)

    def item(self, const):
        key = const.replace("ITEM_", "")
        return self._readable(self.items.get(key), key)

    def species(self, const):
        key = const.replace("SPECIES_", "")
        return self.species_names.get(key) or key.replace("_", " ").title()

    def type(self, const):
        return const.replace("TYPE_", "").title()

    def place(self, const):
        if const.startswith("MAPSEC_"):
            return self.mapsecs.get(const) or const[7:].replace("_", " ").title()
        return prettify_map(const)


def _read_item_names():
    path = REPO / "src" / "data" / "items.h"
    if not path.exists():
        return {}
    names = {}
    for key, block in find_blocks(strip_c_comments(read_file(path)), r"\[ITEM_(\w+)\]\s*="):
        m = re.search(r'\.name\s*=\s*(?:ITEM_NAME|_)\("([^"]+)"\)', block)
        if m:
            names[key] = m.group(1)
    return names


def _read_mapsec_names():
    path = REPO / "src" / "data" / "region_map" / "region_map_sections.json"
    if not path.exists():
        return {}
    sections = json.loads(read_file(path)).get("map_sections", [])
    return {s["id"]: s["name"].title() for s in sections if s.get("id") and s.get("name")}


def _read_script_evo_triggers():
    triggers = set()
    for path in (REPO / "data").rglob("*.inc"):
        triggers.update(re.findall(r"^\s*tryspecialevo\s+(\w+)", read_file(path), re.M))
    return triggers

def parse_species_info(dex_numbers, learnsets, egg_moves, teachable, encounters, tms, hms,
                       held_rules=None, moves=None):
    tm_set = set(tms)
    hm_set = set(hms)
    all_species = {}
    species_h = REPO / "include" / "constants" / "species.h"
    enc_alias = parse_species_aliases(defines=True) if species_h.is_file() else {}

    info_dir = REPO / "src" / "data" / "pokemon" / "species_info"
    for gen_file in sorted(info_dir.glob("gen_*_families.h")):
        raw_content = read_file(gen_file)
        stat_macros = _collect_stat_macros(raw_content)
        type_macros = _collect_object_macros(raw_content)
        macros = collect_macros(raw_content)
        content = strip_c_comments(raw_content)
        for species_key, block in iter_species_decls(content, macros):
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
                if sm:
                    stats[dst_key] = int(sm.group(1))
                else:
                    # Try named macro reference (e.g. CHARIZARD_SP_ATK → stat_macros dict)
                    mm = re.search(rf"\.{src_key}\s*=\s*(\w+)", block)
                    macro_name = mm.group(1) if mm else None
                    if macro_name and macro_name in stat_macros:
                        stats[dst_key] = stat_macros[macro_name]
                    else:
                        # Try inline P_UPDATED_STATS ternary (BPE always uses modern gen values)
                        tm = re.search(rf"\.{src_key}\s*=.*?P_UPDATED_STATS.*?\?\s*(\d+)", block)
                        stats[dst_key] = int(tm.group(1)) if tm else 0
            entry["baseStats"] = stats

            # Types
            entry["types"] = _parse_species_types(block, type_macros)

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

            # Evolutions (raw — merged/canonicalized in a post-pass below once
            # every target species' national dex number is known)
            entry["_evosRaw"] = _parse_evolutions(block)

            # Read by apply_forms(), which removes them again.
            m = re.search(r"\.formChangeTable\s*=\s*s(\w+FormChangeTable)", block)
            entry["_formTable"] = m.group(1) if m else None
            entry["_battleOnly"] = bool(re.search(
                r"\.is(?:MegaEvolution|PrimalReversion|UltraBurst|Gigantamax|TeraForm)\s*=\s*TRUE", block))
            entry["_totem"] = bool(re.search(r"\.isTotem\s*=\s*TRUE", block))
            entry["_evolvesFrom"] = []

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
            # The wild tables resolve names to the enum's own (GRENINJA_BOND)
            # while species_info may declare its alias (GRENINJA_BATTLE_BOND).
            entry["encounters"] = (encounters.get(species_key)
                                   or encounters.get(_final_species(species_key, enc_alias), []))

            # Items a wild one can hold, with their odds
            if held_rules:
                slots = [re.search(rf"\.{f}\s*=\s*ITEM_(\w+)", block) for f in ("itemCommon", "itemRare")]
                common, rare = [m.group(1) if m and m.group(1) != "NONE" else None for m in slots]
                held = wild_held_items(common, rare, held_rules)
                if held:
                    entry["wildHeldItems"] = held
                    entry["heldItemBoostAbilities"] = held_rules[2]

            # Sprite/icon paths filled in by copy_sprites()
            entry["sprite"] = None
            entry["icon"] = None

            all_species[species_key] = entry

    # ── Post-pass: canonicalize + merge evolution targets ───────────────────────
    #
    # Two problems are fixed here:
    #   (1) Multiple evolution methods to the SAME species (e.g. Eevee → Leafeon by
    #       Leaf Stone *or* by levelling in Petalburg Woods) were rendered as two
    #       separate nodes — the "weird duplicates".
    #   (2) Pokémon that evolve into many cosmetic forms of one species (Milcery →
    #       63 Alcremie creams) exploded the tree.  These forms share a national
    #       dex number and identical types/stats, so they collapse to one node.

    # Cosmetic-form dex numbers: every species with that dex number has identical
    # types + base stats (Vivillon patterns, Alcremie creams, Mothim, …).  These
    # are safe to collapse.  Functionally distinct forms (e.g. Wormadam Plant/
    # Sandy/Trash, which differ in typing) are NOT collapsed.
    # Special (non-cosmetic) form markers — Gigantamax/Mega/etc. share their base
    # dex number but differ in stats, and must not disturb cosmetic detection.
    SPECIAL_FORM = ("_GMAX", "_GIGANTAMAX", "_MEGA", "_PRIMAL", "_ETERNAMAX")

    def _is_special(e):
        return any(s in e["id"] for s in SPECIAL_FORM) \
            or sum(e["baseStats"].values()) == 0   # unparsed / placeholder

    by_dex = {}
    for e in all_species.values():
        by_dex.setdefault(e["natDexNum"], []).append(e)

    def _sig(e):
        return (tuple(e["types"]), tuple(sorted(e["baseStats"].items())))

    cosmetic_dex = set()
    for dn, members in by_dex.items():
        normal = [m for m in members if not _is_special(m)]
        if dn and len(normal) > 1 and all(_sig(m) == _sig(normal[0]) for m in normal):
            cosmetic_dex.add(dn)

    # Canonical representative species per dex number, taken from species.h
    # aliases (e.g. SPECIES_ALCREMIE = SPECIES_ALCREMIE_STRAWBERRY = …).
    alias = parse_species_aliases()

    def resolve_alias(k):
        seen = set()
        while k in alias and k not in seen:
            seen.add(k)
            k = alias[k]
        return k

    dex_rep, dex_rep_score = {}, {}
    for base in alias:
        concrete = resolve_alias(base)
        if concrete in all_species:
            dn = all_species[concrete]["natDexNum"]
            score = base.count("_")          # fewer underscores ⇒ more canonical
            if dn not in dex_rep_score or score < dex_rep_score[dn]:
                dex_rep_score[dn] = score
                dex_rep[dn] = concrete

    def canonical_target(tkey):
        sp = all_species.get(tkey)
        if sp is None:
            r = resolve_alias(tkey)
            sp = all_species.get(r)
            if sp is None:
                return tkey            # unknown target — keep as-is
            tkey = r
        dn = sp["natDexNum"]
        if dn in cosmetic_dex and dn in dex_rep:
            return dex_rep[dn]
        return tkey

    names = EvoNames(moves, {k: v["name"] for k, v in all_species.items()})
    for key, entry in all_species.items():
        groups = {}                    # canonical target -> list of raw evo dicts
        order = []
        for evo in entry.pop("_evosRaw"):
            if not _evo_possible(evo, key, names):
                target = all_species.get(resolve_alias(evo["target"]))
                if target is not None:
                    target["_hasParent"] = True
                continue
            # The exact form reached, which the Forms section lists even when
            # the chain collapses it into one node.
            exact = all_species.get(resolve_alias(evo["target"]))
            if exact is not None:
                exact["_hasParent"] = True
            if exact is not None:
                exact["_evolvesFrom"].append({"from": key, "method": _evo_label(evo, key, names)})
            ck = canonical_target(evo["target"])
            if ck not in groups:
                groups[ck] = []
                order.append(ck)
            groups[ck].append(evo)
        merged = []
        for ck in order:
            # Forms shown as one Pokémon (Meowstic, Maushold, ...) name what
            # picks the form instead of listing each form's rule.
            one_form = len({evo["target"] for evo in groups[ck]}) == 1
            methods = []
            for evo in groups[ck]:
                label = _evo_label(evo, key, names, form_pickers=one_form)
                if label not in methods:
                    methods.append(label)
            merged.append({"target": ck, "methods": methods})
        entry["evolutions"] = merged

    # Back-fill preEvolution pointers (on the merged/canonical targets)
    for key, entry in all_species.items():
        for evo in entry["evolutions"]:
            t = evo["target"]
            if t in all_species and "preEvolution" not in all_species[t]:
                all_species[t]["preEvolution"] = key

    return all_species

# ── 10. Special move sources ──────────────────────────────────────────────────

_SPECIAL_DISPLAY_NAMES = {
    "N_SOLARIZER": "N-Solarizer",
    "N_LUNARIZER": "N-Lunarizer",
}


def _special_display_name(name):
    return _SPECIAL_DISPLAY_NAMES.get(name, C.prettify_constant(name))


def _append_special_move(special, species, move, method):
    if move == "NONE":
        return
    entry = {"move": move, "method": method}
    entries = special.setdefault(species, [])
    if entry not in entries:
        entries.append(entry)


def _form_change_sources():
    """Map each form-change table name to the species that references it."""
    sources = {}
    info_dir = REPO / "src" / "data" / "pokemon" / "species_info"
    for gen_file in sorted(info_dir.glob("gen_*_families.h")):
        raw_content = read_file(gen_file)
        macros = collect_macros(raw_content)
        content = strip_c_comments(raw_content)
        for species, block in iter_species_decls(content, macros):
            match = re.search(r"\.formChangeTable\s*=\s*s(\w+FormChangeTable)", block)
            if match:
                sources.setdefault(match.group(1), []).append(species)
    return sources


def apply_special_moves(all_species):
    """Add obtainable moves that live outside normal learnset arrays.

    Rules come from the selected game source so documentation corrections stay
    pinned to the release being rebuilt. Moves already shown under Level Up,
    Egg, TM, HM, or Tutor are not duplicated in Special.
    """
    special = {}

    # Light Ball Volt Tackle and any future item-dependent breeding moves.
    daycare_path = REPO / "src" / "daycare.c"
    if daycare_path.exists():
        daycare = strip_c_comments(read_file(daycare_path))
        table = re.search(
            r"sBreedingSpecialMoveItemTable\[\]\s*=\s*\{(.*?)\n\};",
            daycare,
            re.DOTALL,
        )
        if table:
            for species, item, move in re.findall(
                r"\{\s*SPECIES_(\w+)\s*,\s*ITEM_(\w+)\s*,\s*MOVE_(\w+)\s*\}",
                table.group(1),
            ):
                _append_special_move(
                    special,
                    species,
                    move,
                    f"Hatch {_special_display_name(species)} from an Egg while either parent holds "
                    f"a {_special_display_name(item)}.",
                )

    # Catchable TV mass outbreaks can override a wild Pokémon's normal moveset.
    tv_path = REPO / "src" / "tv.c"
    if tv_path.exists():
        tv = strip_c_comments(read_file(tv_path))
        table = re.search(r"sPokeOutbreakSpeciesList\[\]\s*=\s*\{(.*?)\n\};", tv, re.DOTALL)
        if table:
            entries = re.finditer(
                r"\{\s*\.species\s*=\s*SPECIES_(\w+)\s*,(.*?)\n\s*\}",
                table.group(1),
                re.DOTALL,
            )
            for match in entries:
                species, body = match.group(1), match.group(2)
                level_match = re.search(r"\.level\s*=\s*(\d+)", body)
                map_match = re.search(r"\.location\s*=\s*MAP_NUM\(MAP_(\w+)\)", body)
                if not level_match or not map_match:
                    continue
                map_name = prettify_map("MAP_" + map_match.group(1))
                map_name = re.sub(r"^(Route)(\d+)$", r"\1 \2", map_name)
                method = (
                    f"Catch a Lv. {level_match.group(1)} {_special_display_name(species)} during "
                    f"the {map_name} mass outbreak."
                )
                for move in re.findall(r"MOVE_(\w+)", body):
                    _append_special_move(special, species, move, method)

    form_path = REPO / "src" / "data" / "pokemon" / "form_change_tables.h"
    if form_path.exists():
        forms = strip_c_comments(read_file(form_path))

        # Fusion moves are actively offered to the resulting Pokémon.
        for _, body in re.findall(
            r"static const struct Fusion s(\w+FusionTable)\[\]\s*=\s*\{(.*?)\n\};",
            forms,
            re.DOTALL,
        ):
            rows = re.finditer(
                r"\{\s*[^,{}]+\s*,\s*ITEM_(\w+)\s*,\s*SPECIES_(\w+)\s*,\s*"
                r"SPECIES_(\w+)\s*,\s*SPECIES_(\w+)\s*,\s*MOVE_(\w+)\s*,",
                body,
            )
            for row in rows:
                item, first, second, target, move = row.groups()
                _append_special_move(
                    special,
                    target,
                    move,
                    f"Fuse {_special_display_name(first)} with {_special_display_name(second)} "
                    f"using the {_special_display_name(item)}.",
                )

        form_tables = dict(re.findall(
            r"static const struct FormChange s(\w+FormChangeTable)\[\]\s*=\s*\{(.*?)\n\};",
            forms,
            re.DOTALL,
        ))

        # Zacian and Zamazenta replace Iron Head only while in battle.
        for body in form_tables.values():
            for target, item, original, move in re.findall(
                r"\{\s*FORM_CHANGE_BEGIN_BATTLE\s*,\s*SPECIES_(\w+)\s*,\s*ITEM_(\w+)\s*,\s*"
                r"MOVE_(\w+)\s*,\s*MOVE_(\w+)\s*\}",
                body,
            ):
                _append_special_move(
                    special,
                    target,
                    move,
                    f"{_special_display_name(original)} changes into this on entering battle while "
                    f"holding the {_special_display_name(item)}.",
                )

        # Ultra Necrozma retains the fusion move of the form that Ultra Bursts.
        sources = _form_change_sources()
        for table_name, body in form_tables.items():
            targets = re.findall(
                r"\{\s*FORM_CHANGE_BATTLE_ULTRA_BURST\s*,\s*SPECIES_(\w+)", body
            )
            for target in targets:
                for source in sources.get(table_name, []):
                    for inherited in special.get(source, []):
                        _append_special_move(
                            special,
                            target,
                            inherited["move"],
                            f"Retained when {_special_display_name(source)} Ultra Bursts.",
                        )

    added = 0
    for species, moves in special.items():
        entry = all_species.get(species)
        if not entry:
            continue
        standard = set(entry.get("eggMoves", []))
        standard.update(entry.get("tmMoves", []))
        standard.update(entry.get("hmMoves", []))
        standard.update(entry.get("tutorMoves", []))
        standard.update(move["move"] for move in entry.get("levelUpMoves", []))
        filtered = [move for move in moves if move["move"] not in standard]
        if filtered:
            entry["specialMoves"] = filtered
            added += len(filtered)
    return added


# ── 11. Alternate forms ────────────────────────────────────────────────────────
#
# Every species that shares a national dex number is a form of the same
# Pokémon: Megas, regional forms, Rotom's appliances, Vivillon's patterns...
# Each species page lists them all with every way to get each one.

# Older releases name the forms SPECIES_MEOWTH_ALOLAN instead of _ALOLA.
_REGION_WORDS = {"ALOLA": "Alolan", "GALAR": "Galarian", "HISUI": "Hisuian", "PALDEA": "Paldean",
                 "ALOLAN": "Alolan", "GALARIAN": "Galarian", "HISUIAN": "Hisuian", "PALDEAN": "Paldean"}
_FORM_WORDS = {"F": "Female", "M": "Male"}

# Form changes that only undo another one. They are listed when they lead
# somewhere other than the Pokémon's usual form (Minior's core after battle).
_REVERT_METHODS = {"FORM_CHANGE_END_BATTLE", "FORM_CHANGE_FAINT", "FORM_CHANGE_BATTLE_SWITCH_OUT",
                   "FORM_CHANGE_DEPOSIT", "FORM_CHANGE_WITHDRAW", "FORM_CHANGE_DAYS_PASSED",
                   "FORM_CHANGE_STATUS", "FORM_CHANGE_TIME_OF_DAY", "FORM_CHANGE_BEGIN_BATTLE"}

# Older names of form change methods.
_LEGACY_FORM_METHODS = {"FORM_CHANGE_END_BATTLE_TERRAIN": "FORM_CHANGE_END_BATTLE_ENVIRONMENT",
                        "FORM_CHANGE_BATTLE_SWITCH": "FORM_CHANGE_BATTLE_SWITCH_OUT",
                        "FORM_CHANGE_HIT_BY_MOVE": "FORM_CHANGE_BATTLE_HIT_BY_MOVE_CATEGORY",
                        "FORM_CHANGE_TERASTALLIZATION": "FORM_CHANGE_BATTLE_TERASTALLIZATION"}

_GIMMICK_NAMES = {"MEGA": "Mega Evolution", "ULTRA_BURST": "Ultra Burst",
                  "TERA": "Terastallization", "DYNAMAX": "Dynamax"}

# The key item each battle gimmick needs, when the battle code asks for it.
_GIMMICK_KEY_ITEMS = {"MEGA": "MEGA_RING", "ULTRA_BURST": "Z_POWER_RING",
                      "TERA": "TERA_ORB", "DYNAMAX": "DYNAMAX_BAND"}

_BATTLE_WEATHER = {"B_WEATHER_SUN": "harsh sunlight", "B_WEATHER_RAIN": "rain",
                   "B_WEATHER_ICY_ANY": "snow or hail", "B_WEATHER_HAIL": "hail",
                   "B_WEATHER_SNOW": "snow", "B_WEATHER_SANDSTORM": "a sandstorm"}
_OVERWORLD_WEATHER = {"WEATHER_SUNNY_CLOUDS": "sunshine", "WEATHER_DROUGHT": "a drought",
                      "WEATHER_RAIN": "rain", "WEATHER_RAIN_THUNDERSTORM": "thunderstorms",
                      "WEATHER_DOWNPOUR": "downpours", "WEATHER_SNOW": "snow"}
_ENVIRONMENTS = {"GRASS": "grass", "LONG_GRASS": "tall grass", "POND": "water", "MOUNTAIN": "mountains",
                 "PLAIN": "plains", "CAVE": "caves", "SAND": "sand", "BUILDING": "buildings"}


def _final_species(key, alias):
    """Follow species.h aliases to the name the enum itself defines."""
    seen = set()
    while key in alias and key not in seen:
        seen.add(key)
        key = alias[key]
    return key


def _form_label(name, parts, genders=True):
    """"Mega Charizard X", "Galarian Meowth", "Rotom (Wash)" from the species
    name and what its constant adds to the family's. Without `genders`, F and
    M are letters (Unown) rather than Female and Male."""
    parts = list(parts)
    lead, tail, letter = [], [], ""
    while parts and parts[0] in _REGION_WORDS:
        lead.append(_REGION_WORDS[parts.pop(0)])
    if parts and parts[-1] in ("GMAX", "GIGANTAMAX"):
        parts.pop()
        lead.insert(0, "Gigantamax")
    if parts and parts[0] in ("MEGA", "PRIMAL"):
        lead.insert(0, parts.pop(0).title())
        if len(parts) == 1 and len(parts[0]) == 1:
            letter = " " + parts.pop()
    elif "MEGA" in parts:
        parts.remove("MEGA")
        lead.insert(0, "Mega")
    for word, text in (("TOTEM", "Totem"), ("TERA", "Terastal")):
        if parts and parts[-1] == word:
            parts.pop()
            tail.insert(0, text)
    words = _FORM_WORDS if genders else {}
    inside = [" ".join(words.get(p, p.title()) for p in parts)] if parts else []
    inside += tail
    return " ".join(lead + [name]) + letter + (f" ({', '.join(inside)})" if inside else "")


def _read_form_changes():
    """({table: [(method, target, [args])]}, [(item, first, second, result)])"""
    path = REPO / "src" / "data" / "pokemon" / "form_change_tables.h"
    if not path.exists():
        return {}, []
    text = strip_c_comments(read_file(path))
    tables = {}
    for name, body in re.findall(r"struct FormChange s(\w+FormChangeTable)\[\]\s*=\s*\{(.*?)\n\};", text, re.S):
        rows = []
        for method, rest in re.findall(r"\{\s*(FORM_CHANGE_\w+)\s*,?\s*([^}]*)\}", body):
            args = [a.strip() for a in rest.split(",") if a.strip()]
            if args and args[0].startswith("SPECIES_"):
                rows.append((_LEGACY_FORM_METHODS.get(method, method), args[0][8:], args[1:]))
        tables[name] = rows
    fusions = []
    for body in re.findall(r"struct Fusion s\w+\[\]\s*=\s*\{(.*?)\n\};", text, re.S):
        fusions += re.findall(r"\{\s*\w+\s*,\s*ITEM_(\w+)\s*,\s*SPECIES_(\w+)\s*,\s*SPECIES_(\w+)\s*,\s*SPECIES_(\w+)", body)
    return tables, fusions


def _gimmick_key_items():
    """{gimmick: key item} for the gimmicks whose battle code checks the bag."""
    code = "".join(read_file(p) for p in (REPO / "src").glob("battle_*.c"))
    return {g: item for g, item in _GIMMICK_KEY_ITEMS.items()
            if re.search(rf"CheckBagHasItem\(ITEM_{item}\b", code)}


def _dynamax_enabled():
    config = REPO / "include" / "config" / "battle.h"
    m = re.search(r"#define\s+B_FLAG_DYNAMAX_BATTLE\s+(\w+)", read_file(config)) if config.exists() else None
    return bool(m) and m.group(1) != "0"


def _mirage_held_items():
    """{ITEM: SPECIES} for island legendaries that come holding an item."""
    txt = strip_c_comments(read_file(REPO / "src" / "field_specials.c"))
    body = re.search(r"GetIslandLegendaryHeldItem\([^)]*\)\s*\{(.*?)\n\}", txt, re.S)
    if not body:
        return {}
    return {item: species for species, item in
            re.findall(r"SPECIES_(\w+)\s*\)\s*return\s+ITEM_(\w+)", body.group(1))}


def _item_sources(item_ids, all_species, labels):
    """{ITEM: [{"text", "map"?}, ...]}: where the player gets each item, from
    the same world data as the item pages. An empty list means nowhere."""
    import parse_items
    locations = parse_items.build_locations({i: None for i in item_ids})
    wild_types = {"land_mons", "water_mons", "rock_smash_mons", "fishing_mons"}
    mirage = _mirage_held_items()
    script_items = {}
    hoenn = parse_hoenn_map_ids()
    for mj in sorted((REPO / "data" / "maps").glob("*/map.json")):
        script = mj.parent / "scripts.inc"
        if not script.exists():
            continue
        with open(mj, "r", encoding="utf-8") as f:
            map_id = json.load(f).get("id")
        if map_id not in hoenn:
            continue
        for item in re.findall(r"^\s*(?:giveitem|giveitem_msg|finditem|additem)\s+ITEM_(\w+)",
                               read_file(script), re.M):
            if map_id not in script_items.setdefault(item, []):
                script_items[item].append(map_id)
    out = {}
    for item in item_ids:
        loc = locations.get(item) or {}
        where = []
        for g in loc.get("gifts", []):
            where.append({"text": "Gift in " + g["mapName"], "map": g["mapId"]})
        for o in loc.get("overworld", []):
            place = "Mirage Island" if o["mapId"] == "MAP_ROUTE130" else o["mapName"]
            where.append({"text": ("Hidden in " if o.get("hidden") else "") + place, "map": o["mapId"]})
        for m in loc.get("marts", []):
            cond = m.get("condition") or ""
            cond = "" if cond in ("", "Always available") else f" ({cond})"
            where.append({"text": f"{m['martName']} shop{cond}", "map": m["mapId"]})
        if item in mirage:
            where.append({"text": f"Held by Mirage Island's {labels.get(mirage[item], mirage[item])}",
                          "map": "MAP_ROUTE130"})
        for key, sp in all_species.items():
            if any(h["item"] == item for h in sp.get("wildHeldItems", [])) \
                    and any(e["type"] in wild_types for e in sp.get("encounters", [])):
                where.append({"text": f"Held by wild {labels[key]}", "species": key})
        # The world data misses some handouts (a trainer's reward), so no
        # item is called unobtainable while a map script still gives it.
        if not where:
            for map_id in script_items.get(item, []):
                where.append({"text": "Event in " + prettify_map(map_id), "map": map_id})
        out[item] = where
    return out


def _script_gifts_and_trades():
    """[(SPECIES, kind, MAP, requested SPECIES or None)] for the Pokémon map
    scripts hand over: gifts, Eggs and in-game trades."""
    trades = {}
    trade_h = REPO / "src" / "data" / "trade.h"
    if trade_h.exists():
        text = strip_c_comments(read_file(trade_h))
        for name, body in re.findall(r"\[INGAME_TRADE_(\w+)\]\s*=\s*\{(.*?)\n\s*\},", text, re.S):
            species = re.findall(r"\.species\s*=\s*SPECIES_(\w+)", body)
            wanted = re.findall(r"\.requestedSpecies\s*=\s*SPECIES_(\w+)", body)
            if species:
                trades[name] = (species[-1], wanted[-1] if wanted else None)
    hoenn = parse_hoenn_map_ids()
    out = []
    for mj in sorted((REPO / "data" / "maps").glob("*/map.json")):
        script = mj.parent / "scripts.inc"
        if not script.exists():
            continue
        with open(mj, "r", encoding="utf-8") as f:
            map_id = json.load(f).get("id")
        if map_id not in hoenn:
            continue
        text = read_file(script)
        for op, species in re.findall(r"^\s*(givemon|giveegg|randomgift)\s+SPECIES_(\w+)", text, re.M):
            out.append((species, "egg" if op == "giveegg" else "gift", map_id, None))
        for species in re.findall(r"^\s*setvar\s+VAR_RESULT,\s*SPECIES_(\w+)\s*\n\s*special\s+RandomizeEggSpecies",
                                  text, re.M):
            out.append((species, "egg", map_id, None))
        for trade in dict.fromkeys(re.findall(r"\bINGAME_TRADE_(\w+)", text)):
            if trade in trades:
                out.append((trades[trade][0], "trade", map_id, trades[trade][1]))
    return out


def _can_breed(entry):
    return bool(entry.get("eggGroups")) and "NO_EGGS_DISCOVERED" not in entry["eggGroups"]


def _daycare_egg_overrides():
    """[(PARENT, CHILD), ...]: Eggs from PARENT that hatch as CHILD, from the
    exact-species checks in the Day Care's egg code (src/daycare.c)."""
    path = REPO / "src" / "daycare.c"
    if not path.is_file():
        return []
    return re.findall(r"if \(eggSpecies == SPECIES_(\w+)\)\s*eggSpecies = SPECIES_(\w+);", read_file(path))


def apply_forms(all_species, moves=None, abilities=None):
    """Give every species with alternate forms a `forms` list: each form, with
    every way to get it, and `formItems`, where to find the items those ways
    need. Removes the private fields parse_species_info() left for it."""
    names = EvoNames(moves, {k: v["name"] for k, v in all_species.items()})
    alias = parse_species_aliases(defines=True)

    # Species constants -> the name its page uses, through aliases either way.
    page_key = {_final_species(k, alias): k for k in all_species}

    def resolve(key):
        return key if key in all_species else page_key.get(_final_species(key, alias), key)

    by_dex = {}
    for key, e in all_species.items():
        by_dex.setdefault(e["natDexNum"], []).append(key)

    labels, default_form = {}, {}
    for dn, keys in by_dex.items():
        if not dn or len(keys) == 1:
            for k in keys:
                labels[k] = all_species[k]["name"]
                default_form[k] = k
            continue
        split = [k.split("_") for k in keys]
        common = 0
        while all(len(s) > common and s[common] == split[0][common] for s in split):
            common += 1
        prefix = "_".join(split[0][:common])
        default = resolve(prefix) if resolve(prefix) in keys else keys[0]
        letters = {s[common] for s in split if len(s) == common + 1 and len(s[common]) == 1}
        genders = letters <= set(_FORM_WORDS)
        for k, parts in zip(keys, split):
            labels[k] = _form_label(all_species[k]["name"], parts[common:], genders)
            default_form[k] = default

    tables, fusions = _read_form_changes()
    table_users = {}
    for key, e in all_species.items():
        if e.get("_formTable"):
            table_users.setdefault(e["_formTable"], []).append(key)
    key_items = _gimmick_key_items()
    dynamax = _dynamax_enabled()
    daycare = REPO / "src" / "daycare.c"
    everstone_keeps_form = daycare.exists() and "IsSpeciesForeignRegionalForm" in read_file(daycare)

    how = {key: [] for key in all_species}

    def add(target, entry):
        if target in how and entry not in how[target]:
            how[target].append(entry)

    # Wild, scripted and Mirage Island encounters.
    kinds = {"land_mons": "wild", "water_mons": "wild", "rock_smash_mons": "wild",
             "fishing_mons": "wild", "static": "static", "mirage": "mirage", "altar": "altar"}
    texts = {"wild": "Catch one in the wild.",
             "static": "Battle the one waiting in the overworld.",
             "mirage": "Win it in Mirage Island's legendary lottery.",
             "altar": "Call another one at the Mirage Altar on top of Mirage Island."}
    for key, e in all_species.items():
        for kind in ("wild", "static", "mirage", "altar"):
            places = [{"map": enc["map"], "mapName": enc["mapName"], "type": enc["type"],
                       "levels": (str(enc["minLevel"]) if enc["minLevel"] == enc["maxLevel"]
                                  else f"{enc['minLevel']}–{enc['maxLevel']}"),
                       **({"note": enc["note"]} if enc.get("note") else {})}
                      for enc in e.get("encounters", []) if kinds.get(enc["type"]) == kind]
            if places:
                add(key, {"kind": kind, "text": texts[kind], "places": places})

    # Gifts, Eggs and in-game trades.
    for species, kind, map_id, wanted in _script_gifts_and_trades():
        species = resolve(species)
        if species not in how:
            continue
        place = {"map": map_id, "mapName": prettify_map(map_id), "type": kind}
        if kind == "trade" and wanted:
            wanted = resolve(wanted)
            entry = {"kind": "trade", "text": f"Trade a {labels.get(wanted, wanted)} for one.",
                     "species": [wanted], "places": [place]}
        else:
            entry = {"kind": "gift", "text": "Receive an Egg that hatches into one." if kind == "egg"
                     else "Receive one as a gift.", "places": [place]}
        existing = next((e for e in how[species] if e["text"] == entry["text"]), None)
        if existing:
            if place not in existing["places"]:
                existing["places"].append(place)
        else:
            add(species, entry)

    # Evolution, exactly as the chain shows it; several ways from the same
    # Pokémon (Trade or Linking Cord) share one line.
    for key, e in all_species.items():
        by_source = {}
        for src in e.get("_evolvesFrom", []):
            by_source.setdefault(src["from"], []).append(src["method"])
        for source, methods in by_source.items():
            add(key, {"kind": "evolve", "text": f"Evolve {labels[source]}: {' or '.join(methods)}",
                      "species": [source]})

    # Fusions.
    for item, first, second, result in fusions:
        first, second, result = resolve(first), resolve(second), resolve(result)
        if result in how:
            add(result, {"kind": "fusion", "items": [item], "species": [first, second],
                         "text": f"Fuse {labels.get(first, first)} with {labels.get(second, second)} "
                                 f"using the {names.item(item)}."})

    # Form change tables. Rows that differ only in the item (Arceus holding a
    # Plate or a Z-Crystal) or the weather are one way with alternatives.
    merged, reverts, item_steps = {}, [], {}
    for table, rows in tables.items():
        users = [u for u in table_users.get(table, []) if u in all_species]
        if not users:
            continue
        for method, target, args in rows:
            target = resolve(target)
            if target not in how or any("~" in a or a.endswith("WEATHER_NONE") for a in args):
                continue
            sources = [u for u in users if u != target]
            if not sources:
                continue
            # Within one Pokémon the forms are one name: "Use the Zygarde Cube
            # on Zygarde" rather than a line for each form it can start from.
            same_family = all_species[sources[0]]["natDexNum"] == all_species[target]["natDexNum"]
            src = all_species[sources[0]]["name"] if same_family else labels[sources[0]]
            if method in _REVERT_METHODS and not (method == "FORM_CHANGE_BEGIN_BATTLE" and args):
                text = {"FORM_CHANGE_END_BATTLE": f"{src} takes this form after a battle.",
                        "FORM_CHANGE_BEGIN_BATTLE": f"{src} takes this form when a battle starts.",
                        "FORM_CHANGE_BATTLE_SWITCH_OUT": f"In battle, {src} takes this form when it switches out.",
                        }.get(method)
                if text:
                    reverts.append((target, {"kind": "change" if method == "FORM_CHANGE_END_BATTLE"
                                             else "battle", "text": text}))
                continue
            item = next((a[5:] for a in args if a.startswith("ITEM_")), None)
            move = next((names.move(a) for a in args if a.startswith("MOVE_")), None)
            ability = next(((abilities or {}).get(a[8:], {}).get("name") or C.prettify_constant(a[8:])
                            for a in args if a.startswith("ABILITY_")), None)
            via = f" ({ability})" if ability else ""
            entry = None
            if method == "FORM_CHANGE_ITEM_USE":
                when = " during the day" if "DAY" in args else " at night" if "NIGHT" in args else ""
                entry = {"kind": "change", "text": f"Use the {names.item(item)} on {src}{when}.", "items": [item]}
                for u in sources:
                    item_steps.setdefault(item, {})[u] = target
            elif method == "FORM_CHANGE_ITEM_USE_MULTICHOICE":
                entry = {"kind": "change", "items": [item],
                         "text": f"Use the {names.item(item)} on {src} and choose this form."}
            elif method == "FORM_CHANGE_ITEM_HOLD":
                if item in (None, "NONE"):
                    entry = {"kind": "change", "text": f"Take {src}'s held item away."}
                else:
                    merged.setdefault((target, "hold", src), []).append(item)
            elif method == "FORM_CHANGE_MOVE":
                if "WHEN_FORGOTTEN" in args:
                    entry = {"kind": "change", "text": f"Make {src} forget {move}."}
                else:
                    entry = {"kind": "change", "text": f"Teach {src} {move}."}
            elif method == "FORM_CHANGE_BEGIN_BATTLE":
                entry = {"kind": "battle", "items": [item],
                         "text": f"{src} takes this form when a battle starts while it holds the {names.item(item)}."}
            elif method == "FORM_CHANGE_END_BATTLE_ENVIRONMENT":
                env = re.sub(r"^BATTLE_(ENVIRONMENT|TERRAIN)_", "", args[0]) if args else ""
                merged.setdefault((target, "environment", src), []).append(_ENVIRONMENTS.get(env, env.lower()))
            elif method == "FORM_CHANGE_OVERWORLD_WEATHER":
                merged.setdefault((target, "overworld weather", src), []).append(
                    _OVERWORLD_WEATHER.get(args[0], args[0].lower()))
            elif method == "FORM_CHANGE_BATTLE_WEATHER":
                merged.setdefault((target, "battle weather", src), []).append(
                    _BATTLE_WEATHER.get(args[0], args[0].lower()))
            elif method == "FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM":
                entry = {"kind": "battle", "gimmick": "MEGA", "items": [item],
                         "text": f"Mega Evolve {src} in battle while it holds the {names.item(item)}."}
            elif method == "FORM_CHANGE_BATTLE_MEGA_EVOLUTION_MOVE":
                entry = {"kind": "battle", "gimmick": "MEGA",
                         "text": f"Mega Evolve {src} in battle while it knows {move}."}
            elif method == "FORM_CHANGE_BATTLE_PRIMAL_REVERSION":
                entry = {"kind": "battle", "items": [item],
                         "text": f"{src} undergoes Primal Reversion when it enters battle "
                                 f"holding the {names.item(item)}."}
            elif method == "FORM_CHANGE_BATTLE_ULTRA_BURST":
                merged.setdefault((target, "ultra burst", item), []).extend(labels[u] for u in sources)
            elif method == "FORM_CHANGE_BATTLE_GIGANTAMAX":
                entry = {"kind": "battle", "gimmick": "DYNAMAX", "text": f"Gigantamax {src} in battle."}
            elif method == "FORM_CHANGE_BATTLE_TERASTALLIZATION":
                entry = {"kind": "battle", "gimmick": "TERA", "text": f"Terastallize {src} in battle."}
            elif method.startswith("FORM_CHANGE_BATTLE_HP_PERCENT"):
                cmp = next((a for a in args if a.startswith("HP_")), "")
                pct = next((a for a in args if a.isdigit()), "")
                side = "above" if cmp == "HP_HIGHER_THAN" else "at or below"
                merged.setdefault((target, f"hp|{side}|{pct}|{via}", src), []).append(move)
            elif method in ("FORM_CHANGE_BATTLE_BEFORE_MOVE", "FORM_CHANGE_BATTLE_BEFORE_MOVE_CATEGORY"):
                what = move or "a damaging move"
                entry = {"kind": "battle", "text": f"In battle, {src} takes this form when it uses {what}{via}."}
            elif method == "FORM_CHANGE_BATTLE_AFTER_MOVE":
                entry = {"kind": "battle", "text": f"In battle, {src} changes form after it uses {move}."}
            elif method.startswith("FORM_CHANGE_BATTLE_HIT_BY"):
                entry = {"kind": "battle", "text": f"In battle, {src} takes this form when an attack breaks its {ability}."}
            elif method == "FORM_CHANGE_BATTLE_SWITCH_IN":
                entry = {"kind": "battle", "text": f"{src} takes this form when it enters battle{via}."}
            elif method == "FORM_CHANGE_BATTLE_TURN_END":
                entry = {"kind": "battle", "text": f"In battle, {src} switches to this form at the end of a turn{via}."}
            elif method == "FORM_CHANGE_BEGIN_WILD_ENCOUNTER":
                entry = {"kind": "battle", "text": f"Wild {src} appear in this form in battle."}
            if entry:
                entry["items"] = [i for i in entry.get("items", []) if i]
                add(target, entry)

    def join(words):
        words = list(dict.fromkeys(w for w in words if w))
        return " or ".join(words) if len(words) < 3 else ", ".join(words[:-1]) + " or " + words[-1]

    for (target, kind, src), values in merged.items():
        if kind == "hold":
            add(target, {"kind": "change", "items": list(dict.fromkeys(values)),
                         "text": f"Give {src} the {join(names.item(i) for i in values)} to hold."})
        elif kind == "environment":
            add(target, {"kind": "change", "text": f"Battle with {src} in {join(values)}."})
        elif kind == "overworld weather":
            add(target, {"kind": "change", "text": f"{src} takes this form in the overworld during {join(values)}."})
        elif kind == "battle weather":
            add(target, {"kind": "battle", "text": f"In battle, {src} takes this form in {join(values)}."})
        elif kind == "ultra burst":
            add(target, {"kind": "battle", "gimmick": "ULTRA_BURST", "items": [src],
                         "text": f"Ultra Burst {join(values)} in battle while it holds the {names.item(src)}."})
        else:
            _, side, pct, via = kind.split("|")
            during = f" while using {join(values)}" if any(values) else ""
            add(target, {"kind": "battle",
                         "text": f"In battle, {src} takes this form when its HP is {side} {pct}%{during}{via}."})

    # An item that moves a Pokémon on to its next form, round and round
    # (Deoxys and the Meteorite), says so on every form of the cycle.
    for item, steps in item_steps.items():
        start = next(iter(steps))
        start = default_form.get(start, start) if default_form.get(start, start) in steps else start
        order, cur = [], start
        while cur in steps and cur not in order:
            order.append(cur)
            cur = steps[cur]
        if len(order) > 2 and cur == start:
            name = all_species[start]["name"]
            forms = ", ".join(labels[k].split("(")[-1].rstrip(")") for k in order)
            for key in order:
                how[key] = [e for e in how[key] if e.get("items") != [item]]
                add(key, {"kind": "change", "items": [item],
                          "text": f"Use the {names.item(item)} on {name}. Each use changes it to "
                                  f"the next form, in this order: {forms}."})

    # Battle Bond turns Greninja into Ash-Greninja in the rules before Gen 9.
    ash, bond = resolve("GRENINJA_ASH"), resolve("GRENINJA_BATTLE_BOND")
    if ash in how and bond in all_species:
        config = REPO / "include" / "config" / "battle.h"
        gen = re.search(r"#define\s+B_BATTLE_BOND\s+(\w+)", read_file(config)) if config.exists() else None
        transforms = (gen.group(1) in ("GEN_7", "GEN_8") if gen
                      else "SPECIES_GRENINJA_ASH" in read_file(REPO / "src" / "battle_util.c"))
        entry = {"kind": "battle", "species": [bond],
                 "text": f"In battle, {labels[bond]} becomes this form after it knocks out a Pokémon."}
        if not transforms:
            entry["unavailable"] = "Battle Bond raises Greninja's stats instead in this game."
        add(ash, entry)
        all_species[ash]["_battleOnly"] = True

    # A form the Pokémon keeps is reached the lasting way; its battle changes
    # and the undoing of other forms only matter for forms with no other way
    # (Minior's core after a battle, Xerneas in battle).
    lasting = ("wild", "static", "mirage", "gift", "trade", "evolve", "fusion", "altar")
    reverted = set()
    for key, entries in how.items():
        if key == default_form.get(key) or any(e["kind"] in lasting for e in entries):
            how[key] = [e for e in entries if e["kind"] != "battle"]
    # Minior's core: "after a battle" says it all, without the switch-out and
    # battle-start lines that lead to the same form.
    for target, entry in sorted(reverts, key=lambda r: r[1]["kind"] != "change"):
        if (target != default_form.get(target) and not all_species[target].get("_totem")
                and all(e["kind"] == "battle" for e in how[target])
                and not (entry["kind"] == "battle" and target in reverted)):
            add(target, entry)
            if entry["kind"] == "change":
                reverted.add(target)

    # Breeding keeps a regional form when the parent holds an Everstone.
    if everstone_keeps_form:
        for key, e in all_species.items():
            if (set(key.split("_")) & set(_REGION_WORDS) and not e.get("_hasParent")
                    and _can_breed(e) and not e.get("_battleOnly") and not e.get("_totem")
                    and not any(entry["kind"] in ("change", "battle", "fusion") for entry in how[key])):
                article = "an" if labels[key][0] in "AEIOU" else "a"
                add(key, {"kind": "breed", "items": ["EVERSTONE"],
                          "text": f"Breed {article} {labels[key]} holding an Everstone to hatch more."})

    # Forms with no way of their own that hatch from an Egg: a baby from its
    # evolved form (Pichu, Flabébé's colours), and a regular form from a
    # regional one bred without an Everstone (Farfetch'd).
    children = {}
    for key, entries in how.items():
        for entry in entries:
            if entry["kind"] == "evolve":
                children.setdefault(entry["species"][0], []).append(key)

    def breedable_descendant(key, depth=0):
        for child in children.get(key, []):
            if _can_breed(all_species[child]) and any(e["kind"] in lasting[:5] for e in how[child]):
                return child
            found = depth < 3 and breedable_descendant(child, depth + 1)
            if found:
                return found
        return None

    for key, e in all_species.items():
        if how[key] or e.get("_battleOnly") or e.get("_totem") or e.get("_evolvesFrom") is None:
            continue
        if e["_evolvesFrom"]:
            continue
        parent = breedable_descendant(key)
        if parent:
            article = "an" if labels[parent][0] in "AEIOU" else "a"
            add(key, {"kind": "breed", "species": [parent],
                      "text": f"Breed {article} {labels[parent]} to hatch one."})
            continue
        regional = [k for k in by_dex.get(e["natDexNum"], [])
                    if set(k.split("_")) & set(_REGION_WORDS) and _can_breed(all_species[k])
                    and any(x["kind"] in lasting for x in how[k])]
        if everstone_keeps_form and regional and not set(key.split("_")) & set(_REGION_WORDS):
            article = "an" if labels[regional[0]][0] in "AEIOU" else "a"
            add(key, {"kind": "breed", "species": [regional[0]],
                      "text": f"Breed {article} {labels[regional[0]]} that isn't holding an Everstone."})

    # Eggs the Day Care turns into another Pokémon (Manaphy's hatch as Phione).
    for parent, child in _daycare_egg_overrides():
        parent, child = resolve(parent), resolve(child)
        if child in how and parent in how and not how[child]:
            article = "an" if labels[parent][0] in "AEIOU" else "a"
            add(child, {"kind": "breed", "species": [parent],
                        "text": f"Breed {article} {labels[parent]} to hatch one."})

    # Unown's letter is chosen by its personality when it is caught.
    for key in how:
        if key.startswith("UNOWN_") and not how[key] and "UNOWN" in how and how["UNOWN"]:
            add(key, {"kind": "wild", "text": "Wild Unown come in a random letter.",
                      "species": ["UNOWN"]})

    def species_link(key):
        return {"id": key, "label": labels.get(key, key),
                "icon": all_species[key].get("icon") if key in all_species else None}

    # Where each needed item comes from, and whether the way is open at all.
    for entries in how.values():
        for entry in entries:
            if entry.get("gimmick") in key_items:
                entry["items"] = entry.get("items", []) + [key_items[entry["gimmick"]]]
    needed = sorted({i for entries in how.values() for entry in entries for i in entry.get("items", [])})
    sources = _item_sources(needed, all_species, labels) if needed else {}
    for entries in how.values():
        for entry in entries:
            items = entry.get("items", [])
            if entry["kind"] == "change" and len(items) > 1:
                # Alternatives: keep the ones the player can get.
                kept = [i for i in items if sources.get(i)]
                if kept and len(kept) < len(items):
                    src = entry["text"][len("Give "):entry["text"].index(" the ")]
                    entry["items"] = kept
                    entry["text"] = f"Give {src} the {join(names.item(i) for i in kept)} to hold."
                missing = [] if kept else items[:1]
            else:
                missing = [i for i in items if not sources.get(i)]
            gimmick = entry.get("gimmick")
            if gimmick == "DYNAMAX" and not dynamax:
                entry["unavailable"] = "Dynamax isn't part of this game."
            elif gimmick in _GIMMICK_NAMES and key_items.get(gimmick) in missing:
                entry["unavailable"] = f"{_GIMMICK_NAMES[gimmick]} isn't part of this game."
            elif missing:
                entry["unavailable"] = f"The {names.item(missing[0])} can't be obtained in this release."
            entry.pop("gimmick", None)
            if not entry.get("items"):
                entry.pop("items", None)
            if entry.get("species"):
                entry["species"] = [species_link(s) for s in entry["species"]]

    for dn, keys in by_dex.items():
        if not dn or len(keys) < 2:
            continue
        group = []
        item_ids = set()
        for k in keys:
            e = all_species[k]
            entries = how[k]
            item_ids.update(i for entry in entries for i in entry.get("items", []))
            form = {"id": k, "label": labels[k], "types": e["types"], "icon": e.get("icon"),
                    "how": entries}
            if e.get("_battleOnly"):
                form["battleOnly"] = True
            if e.get("_totem"):
                form["totem"] = True
            if e.get("evolutions"):
                form["evolvesInto"] = [species_link(ev["target"]) for ev in e["evolutions"]]
            group.append(form)
        items = {i: {"name": names.item("ITEM_" + i), "icon": f"sprites/items/{i.lower()}.png",
                     "where": sources.get(i, [])} for i in sorted(item_ids)}
        for k in keys:
            all_species[k]["forms"] = group
            if items:
                all_species[k]["formItems"] = items

    # A Pokémon found nowhere says how to get it instead (Solgaleo, Phione).
    for key, e in all_species.items():
        if not e.get("forms") and not e.get("encounters") and how[key]:
            e["obtain"] = how[key]
            item_ids = sorted({i for entry in how[key] for i in entry.get("items", [])})
            if item_ids:
                e["obtainItems"] = {i: {"name": names.item("ITEM_" + i), "icon": f"sprites/items/{i.lower()}.png",
                                        "where": sources.get(i, [])} for i in item_ids}

    for e in all_species.values():
        for field in ("_formTable", "_battleOnly", "_totem", "_evolvesFrom", "_hasParent"):
            e.pop(field, None)
    return sum(1 for keys in by_dex.values() if len(keys) > 1)


# ── 12. Sprites ────────────────────────────────────────────────────────────────

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

POKE_GFX_ROOT = REPO / "graphics" / "pokemon"

def _split_base_form(name_lower):
    """Split a lowercased species name into (base_dir_name, form_subpath).

    The base is the longest underscore-delimited prefix that is an actual
    `graphics/pokemon/<base>/` directory; the remainder is the per-form
    subfolder.  E.g. 'floette_blue' -> ('floette', 'blue'),
    'vivillon_high_plains' -> ('vivillon', 'high_plains'),
    'mr_mime' -> ('mr_mime', '')  (multi-word base that is itself a dir)."""
    parts = name_lower.split("_")
    for i in range(len(parts), 0, -1):
        base = "_".join(parts[:i])
        if (POKE_GFX_ROOT / base).is_dir():
            return base, "_".join(parts[i:])
    return name_lower, ""

def _sprite_candidates(species_key, filename):
    name = species_key
    subfolder = None
    for suffix, folder in sorted(FORM_SUFFIXES, key=lambda x: -len(x[0])):
        if name.endswith(suffix):
            subfolder = folder
            name = name[: -len(suffix)]
            break

    base, form = _split_base_form(name.lower())
    poke_dir = POKE_GFX_ROOT / base
    alt = filename.replace("anim_", "")  # 'anim_front.png' -> 'front.png'
    candidates = []
    # 1. Known form suffix (e.g. _ALOLAN -> alolan/)
    if subfolder:
        candidates += [poke_dir / subfolder / filename, poke_dir / subfolder / alt]
    # 2. Generic per-form subfolder (e.g. FLOETTE_BLUE -> floette/blue/).
    #    Some forms only override the icon, so a missing front here correctly
    #    falls through to the base/default-form art below.
    if form:
        candidates += [poke_dir / form / filename, poke_dir / form / alt]
    # 3. Default / base-folder art.
    candidates += [poke_dir / filename, poke_dir / alt]
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
    encounters = parse_encounters(load_static_encounters())
    print(f"       -> {len(encounters)} species have encounters")

    print("  [9] Species info ...")
    held_rules = read_wild_held_item_rules()
    all_species = parse_species_info(dex, learnsets, egg_moves, teachable, encounters, tms, hms,
                                     held_rules, moves)
    print(f"       -> {len(all_species)} species")

    print("  [10] Special move sources ...")
    special_count = apply_special_moves(all_species)
    print(f"       -> {special_count} undocumented species/move methods")

    print("  [11] Copying sprites ...")
    copy_sprites(all_species)

    print("  [12] Alternate forms ...")
    families = apply_forms(all_species, moves, abilities)
    print(f"       -> {families} Pokémon with more than one form")

    print("  [13] Writing JSON ...")

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
