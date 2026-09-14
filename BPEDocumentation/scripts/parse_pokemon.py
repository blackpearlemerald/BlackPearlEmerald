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

def parse_species_aliases():
    """Parse `SPECIES_X = SPECIES_Y` aliases from species.h → {X: Y}.

    Used to find each form-family's canonical default form (e.g.
    SPECIES_ALCREMIE = SPECIES_ALCREMIE_STRAWBERRY = …_VANILLA_CREAM)."""
    path = REPO / "include" / "constants" / "species.h"
    content = read_file(path)
    alias = {}
    for m in re.finditer(r"\bSPECIES_(\w+)\s*=\s*SPECIES_(\w+)\b", content):
        alias[m.group(1)] = m.group(2)
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
    Those maps have no `map.json` (or a REGION_KANTO one), so we keep only maps
    whose `map.json` declares `REGION_HOENN`."""
    hoenn = set()
    for mj in (REPO / "data" / "maps").glob("*/map.json"):
        try:
            with open(mj, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if d.get("region") == "REGION_HOENN" and d.get("id"):
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


def parse_encounters():
    path = REPO / "src" / "data" / "wild_encounters.json"
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

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
        })

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
    """Parse CONDITIONS({IF_X, VAL}, ...) → list of condition keys found."""
    return re.findall(r"IF_\w+", cond_str)

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

        # Parse CONDITIONS for richer display labels
        if "CONDITIONS" in rest:
            conds = _parse_conditions(rest)
            if conds:
                evo["conditions"] = conds

        evos.append(evo)
    return evos

def _collect_stat_macros(content):
    """Extract #define NAME (P_UPDATED_STATS ... ? val1 : val2) -> {NAME: val1}."""
    macros = {}
    # BPE uses P_UPDATED_STATS >= GEN_LATEST so always take the first (modern) branch
    for m in re.finditer(r"#define\s+(\w+)\s+\(.*?P_UPDATED_STATS.*?\?\s*(\d+)\s*:", content):
        macros[m.group(1)] = int(m.group(2))
    return macros

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
                        # token-paste first (foo##p, p##bar), then whole-word
                        ebody = ebody.replace("##" + p, a).replace(p + "##", a)
                        ebody = re.sub(r"\b" + re.escape(p) + r"\b", a, ebody)
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

# ── Evolution method label (kept in sync with site/js/pokemon.js) ────────────────

def _evo_label(evo):
    m = evo.get("method", "")
    conds = evo.get("conditions", [])
    has_friend = "IF_MIN_FRIENDSHIP" in conds
    is_night = "IF_TIME" in conds
    is_day = "IF_NOT_TIME" in conds
    is_map = "IF_IN_MAP" in conds
    is_fairy = "IF_KNOWS_MOVE_TYPE" in conds

    if m == "EVO_LEVEL" or m.startswith("EVO_LEVEL_"):
        if evo.get("level"):
            return "Lv. " + str(evo["level"])
        if has_friend and is_night:
            return "Friendship (night)"
        if has_friend and is_day:
            return "Friendship (day)"
        if has_friend and is_fairy:
            return "Friendship + Fairy move"
        if has_friend:
            return "Friendship"
        if is_map:
            return "Level up in area"
        return "Level up"
    if m == "EVO_FRIENDSHIP":
        return "Friendship"
    if m == "EVO_FRIENDSHIP_DAY":
        return "Friendship (day)"
    if m == "EVO_FRIENDSHIP_NIGHT":
        return "Friendship (night)"
    if "ITEM_HOLD" in m or m == "EVO_TRADE_ITEM":
        return ("Trade holding " if m == "EVO_TRADE_ITEM" else "Hold ") + (evo.get("item") or "")
    if "ITEM" in m:
        return evo.get("item") or "Use item"
    if m == "EVO_TRADE":
        return "Trade"
    if m == "EVO_MOVE":
        return "Know " + (evo.get("move") or "")
    if m == "EVO_BEAUTY":
        return "Max Beauty"
    if m == "EVO_SPIN":
        return "Spin w/ Sweet"
    return m.replace("EVO_", "").replace("_", " ").title()

def parse_species_info(dex_numbers, learnsets, egg_moves, teachable, encounters, tms, hms):
    tm_set = set(tms)
    hm_set = set(hms)
    all_species = {}

    info_dir = REPO / "src" / "data" / "pokemon" / "species_info"
    for gen_file in sorted(info_dir.glob("gen_*_families.h")):
        raw_content = read_file(gen_file)
        stat_macros = _collect_stat_macros(raw_content)
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

            # Evolutions (raw — merged/canonicalized in a post-pass below once
            # every target species' national dex number is known)
            entry["_evosRaw"] = _parse_evolutions(block)

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

    for entry in all_species.values():
        groups = {}                    # canonical target -> list of raw evo dicts
        order = []
        for evo in entry.pop("_evosRaw"):
            ck = canonical_target(evo["target"])
            if ck not in groups:
                groups[ck] = []
                order.append(ck)
            groups[ck].append(evo)
        merged = []
        for ck in order:
            methods = []
            for evo in groups[ck]:
                label = _evo_label(evo)
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
