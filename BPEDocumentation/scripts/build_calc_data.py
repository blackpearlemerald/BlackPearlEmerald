"""Build the Dynamic-Calc data source for BPE Emerald.

Reads the already-parsed BPE documentation data (species/*.json, moves.json,
abilities.json, trainers.json, world.json) and writes:

  site/calc/data/bpe_calc_data.json   -- the npoint-schema blob the calc loads
  site/calc/img/newhd/<name>.png      -- Pokemon sprites named to the calc's
                                         JS sprite-name convention (copied from
                                         BPE's own img/pokemon sprites)

Schema mirrors the working Dynamic-Calc npoint example (Blaze Black):
  poks[ShowdownName]            = {bs, types, abilities, weightkg, learnset_info}
  moves[Move Name]             = {type, category, basePower}
  formatted_sets[Species][key] = {tr_id, sub_index, level, moves, item, ability,
                                  nature, evs, ivs, sprite, battle_type, mega,
                                  ...}  (mega: the form its held Mega Stone
                                  turns it into, when it has one)
  save_data                    = this source's species/move/item numbering and
                                  the rules js/calc_save_import.js needs to read
                                  a player's .sav into the calculator

Run:  py BPEDocumentation/scripts/build_calc_data.py
"""
import json
import os
import re
import shutil
import sys

import common

SITE = common.SITE
SPECIES_DIR = os.path.join(SITE, "data", "species")
MOVES_JSON = os.path.join(SITE, "data", "moves.json")
ABIL_JSON = os.path.join(SITE, "data", "abilities.json")
ITEMS_JSON = os.path.join(SITE, "data", "items_index.json")
TRAINERS_JSON = os.path.join(SITE, "js", "data", "trainers.json")
WORLD_JSON = os.path.join(SITE, "js", "data", "world.json")

CALC_DIR = os.path.join(SITE, "calc")
OUT_JSON = os.path.join(CALC_DIR, "data", "bpe_calc_data.json")
NEWHD_DIR = os.path.join(CALC_DIR, "img", "newhd")

# ── Name helpers ──────────────────────────────────────────────────────────────

# Internal form suffix -> Showdown form token. Longest suffixes first so that
# e.g. _MEGA_X is matched before _MEGA and _PALDEA_BLAZE before _PALDEAN.
FORM_TOKENS = [
    ("_MEGA_X", "Mega-X"), ("_MEGA_Y", "Mega-Y"), ("_MEGA", "Mega"),
    ("_PRIMAL", "Primal"),
    ("_GIGANTAMAX", "Gmax"), ("_GMAX", "Gmax"),
    ("_ALOLA", "Alola"), ("_GALAR", "Galar"), ("_HISUI", "Hisui"),
    ("_ALOLAN", "Alola"), ("_GALARIAN", "Galar"), ("_HISUIAN", "Hisui"),
    ("_PALDEAN_BLAZE_BREED", "Paldea-Blaze"), ("_PALDEAN_AQUA_BREED", "Paldea-Aqua"),
    ("_PALDEAN_COMBAT_BREED", "Paldea-Combat"),
    ("_PALDEA_BLAZE", "Paldea-Blaze"), ("_PALDEA_AQUA", "Paldea-Aqua"),
    ("_PALDEA_COMBAT", "Paldea-Combat"), ("_PALDEAN", "Paldea"),
    ("_HEAT", "Heat"), ("_WASH", "Wash"), ("_MOW", "Mow"),
    ("_FROST", "Frost"), ("_FAN", "Fan"),
    ("_ORIGIN", "Origin"), ("_THERIAN", "Therian"), ("_INCARNATE", "Incarnate"),
    ("_SKY", "Sky"), ("_SANDY", "Sandy"), ("_TRASH", "Trash"),
    ("_RAINY", "Rainy"), ("_SNOWY", "Snowy"), ("_SUNSHINE", "Sunshine"),
    ("_ATTACK", "Attack"), ("_DEFENSE", "Defense"), ("_SPEED", "Speed"),
    ("_DUSK_MANE", "Dusk-Mane"), ("_DAWN_WINGS", "Dawn-Wings"),
    ("_ULTRA", "Ultra"), ("_CROWNED", "Crowned"),
    ("_PIROUETTE", "Pirouette"), ("_RESOLUTE", "Resolute"),
    ("_LOW_KEY", "Low-Key"), ("_AMPED", "Amped"),
    ("_SUMMER", "Summer"), ("_AUTUMN", "Autumn"), ("_WINTER", "Winter"),
    ("_SPRING", "Spring"), ("_BLOODMOON", "Bloodmoon"), ("_HERO", "Hero"),
]

# Explicit overrides keyed by internal species id (irregular Showdown spellings).
NAME_OVERRIDES = {
    "NIDORAN_F": "Nidoran-F",
    "NIDORAN_M": "Nidoran-M",
    "KOMMO_O": "Kommo-o",
    "FARFETCHD": "Farfetch'd",
    "SIRFETCHD": "Sirfetch'd",
    "TYPE_NULL": "Type: Null",
    "MR_MIME": "Mr. Mime",
    "MR_MIME_GALAR": "Mr. Mime-Galar",
    "MR_RIME": "Mr. Rime",
    "MIME_JR": "Mime Jr.",
    "HO_OH": "Ho-Oh",
    "PORYGON_Z": "Porygon-Z",
}


def normalize(s):
    """Showdown-style id: strip every non-alphanumeric, lowercase."""
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()


def canon_name(internal_id, display_name):
    """Compute the Showdown species name from internal id + base display name."""
    if internal_id in NAME_OVERRIDES:
        return NAME_OVERRIDES[internal_id]
    base = display_name
    for suffix, token in FORM_TOKENS:
        if internal_id.endswith(suffix):
            return "%s-%s" % (base, token)
    return base


def js_sprite_name(showdown_name):
    """Replicate the calc's JS transform used to build sprite filenames:
    name.toLowerCase().replace(" ","-").replace(".","").replace("’","").replace(":","-")
    NOTE: JS String.replace(str, str) only replaces the FIRST occurrence."""
    s = showdown_name.lower()
    s = s.replace(" ", "-", 1)
    s = s.replace(".", "", 1)
    s = s.replace("’", "", 1)
    s = s.replace(":", "-", 1)
    return s


def title_word(w):
    return w[:1].upper() + w[1:].lower() if w else w


# ── Stat / field mapping ──────────────────────────────────────────────────────

BS_MAP = [("hp", "hp"), ("atk", "at"), ("def", "df"),
          ("spa", "sa"), ("spd", "sd"), ("spe", "sp")]


def map_base_stats(bs):
    return {short: bs[long] for long, short in BS_MAP}


# ── Mega Evolution ────────────────────────────────────────────────────────────

def mega_evolutions():
    """(source species id, item id) -> Mega species id, from the game's
    form-change tables. A trainer mon holding its Mega Stone Mega Evolves in
    battle, so the calc shows that set in its Mega form."""
    import parse_pokemon  # imported here: it derives its paths at import time
    with open(common.src("src/data/pokemon/form_change_tables.h"), encoding="utf-8") as f:
        forms = parse_pokemon.strip_c_comments(f.read())
    tables = dict(re.findall(
        r"static const struct FormChange s(\w+FormChangeTable)\[\]\s*=\s*\{(.*?)\n\};",
        forms, re.DOTALL))
    megas = {}
    for table, species_list in parse_pokemon._form_change_sources().items():
        rows = re.findall(
            r"\{\s*FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM\s*,\s*SPECIES_(\w+)\s*,\s*ITEM_(\w+)\s*\}",
            tables.get(table, ""))
        for target, item in rows:
            for species in species_list:
                if species != target:
                    megas[(species, item)] = target
    return megas


# ── Save numbering ────────────────────────────────────────────────────────────

def c_constants(path, prefix):
    """Numeric values of the #defines and enum members named <prefix>* in a C
    header, in declaration order. Handles both the #define lists of older
    sources (1.0.1) and the enums of current ones, including implicit enum
    values and members defined in terms of other constants."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = text.replace("\\\n", " ")
    exprs, order = {}, []
    for name, expr in re.findall(r"^[ \t]*#[ \t]*define[ \t]+(\w+)[ \t]+([^\n]+)", text, flags=re.M):
        exprs[name] = expr.strip()
        order.append(name)
    for body in re.findall(r"\benum\b[^{;]*\{(.*?)\}", text, flags=re.S):
        # Skip preprocessor lines and macro calls (items.h generates its
        # ITEM_TM_<move> aliases with RECURSIVELY(...) inside the enum).
        lines = [line for line in body.split("\n")
                 if not line.strip().startswith("#") and not re.match(r"\s*\w+\s*\(", line)]
        previous = None
        for entry in " ".join(lines).split(","):
            entry = entry.strip()
            if not entry:
                continue
            m = re.fullmatch(r"(\w+)\s*(?:=\s*(.+))?", entry, flags=re.S)
            if not m:
                raise ValueError("Cannot read enum member %r in %s" % (entry, path))
            name, expr = m.group(1), m.group(2)
            if expr is None:
                expr = "0" if previous is None else "(%s) + 1" % previous
            exprs[name] = expr.strip()
            order.append(name)
            previous = name

    values = {}

    def value(name, depth=0):
        if name not in values:
            if depth > 64 or name not in exprs:
                raise KeyError(name)
            expr = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: str(value(m.group(0), depth + 1)), exprs[name])
            expr = re.sub(r"\b(0x[0-9A-Fa-f]+|\d+)[uUlL]*\b", lambda m: str(int(m.group(1), 0)), expr)
            if not re.fullmatch(r"[\d\s+\-*()<>|&]*", expr):
                raise KeyError(name)
            values[name] = int(eval(expr, {"__builtins__": {}}))  # digits and operators only
        return values[name]

    result = {}
    for name in order:
        if name.startswith(prefix) and name not in result:
            try:
                result[name] = value(name)
            except (KeyError, SyntaxError):
                pass  # not a number (e.g. a function-like macro)
    return result


def numbered(constants, prefix, known, limit):
    """{number: id} for the first declared <prefix><id> of each number whose id
    has exported data, so aliases never shadow the name the data uses."""
    result = {}
    for name, number in constants.items():
        key = name[len(prefix):]
        if 0 < number < limit and number not in result and key in known:
            result[number] = key
    return result


def dense(table):
    """{number: value} -> a list indexed by number, None for gaps."""
    out = [None] * (max(table) + 1 if table else 0)
    for number, value in table.items():
        out[number] = value
    return out


def build_save_data(species_info, poks, move_name, item_name):
    """Tables that turn the numbers in a save file into calculator names.

    species_info: {species id: (calc name, growth rate, [ability names])}
    A species entry is [calc name, growth rate index], plus its three ability
    slots when they differ from the calculator entry it shares (alternate forms).
    """
    growth_rates = sorted({growth for _, growth, _ in species_info.values()})
    entries = {}
    for sid, (name, growth, abilities) in species_info.items():
        slots = (list(abilities) + [None] * 3)[:3]
        shared = poks[name].get("abilities", {})
        entry = [name, growth_rates.index(growth)]
        if slots != [shared.get("0"), shared.get("1"), shared.get("H")]:
            entry.append(slots)
        entries[sid] = entry

    def header(name):
        return common.src("include", "constants", name)

    species = c_constants(header("species.h"), "SPECIES_")
    egg = species.get("SPECIES_EGG", 1 << 11)
    moves = c_constants(header("moves.h"), "MOVE_")
    items = c_constants(header("items.h"), "ITEM_")
    flags = c_constants(header("flags.h"), "FLAG_NUZLOCKE")
    variables = c_constants(header("vars.h"), "VAR_RANDOMIZER_")

    # The box format stores species and moves in 11 bits, held items in 10.
    by_species = numbered(species, "SPECIES_", entries, min(egg, 1 << 11))
    by_move = numbered(moves, "MOVE_", move_name, 1 << 11)
    by_item = numbered(items, "ITEM_", item_name, 1 << 10)
    for table, constants, prefix, known in ((by_species, species, "SPECIES_", "BULBASAUR"),
                                            (by_move, moves, "MOVE_", "POUND"),
                                            (by_item, items, "ITEM_", "POKE_BALL")):
        if table.get(constants.get(prefix + known)) != known:
            raise ValueError("Could not number %s%s for the save importer." % (prefix, known))

    # CalculateMonStats ignores EVs in Nuzlocke mode from 2.1 on; older
    # sources count them.
    with open(common.src("src", "pokemon.c"), encoding="utf-8") as f:
        nuzlocke_ignores_evs = bool(re.search(
            r"evsDisabled\s*=\s*FlagGet\(\s*FLAG_NUZLOCKE\s*\)", f.read()))

    return {
        "growthRates": growth_rates,
        "species": dense({n: entries[k] for n, k in by_species.items()}),
        "moves": dense({n: move_name[k] for n, k in by_move.items()}),
        "items": dense({n: item_name[k] for n, k in by_item.items()}),
        "nuzlockeFlag": flags.get("FLAG_NUZLOCKE"),
        "nuzlockeIgnoresEvs": nuzlocke_ignores_evs,
        "randomizerVars": [variables[name] for name in sorted(variables)],
    }


def main():
    species_files = sorted(
        f for f in os.listdir(SPECIES_DIR) if f.endswith(".json"))
    moves_data = common.load_json(MOVES_JSON)
    abil_data = common.load_json(ABIL_JSON)
    trainers = common.load_json(TRAINERS_JSON)

    # move id -> Showdown display name
    move_name = {mid: m.get("name", mid) for mid, m in moves_data.items()}

    # ── poks ─────────────────────────────────────────────────────────────────
    poks = {}
    norm_index = {}   # normalize(name) -> ShowdownName (for trainer matching)
    sprite_src_for = {}  # ShowdownName -> site-relative sprite path
    save_species = {}  # species id -> (ShowdownName, growth rate, abilities)

    for fn in species_files:
        sid = fn[:-5]
        d = common.load_json(os.path.join(SPECIES_DIR, fn))
        name = canon_name(sid, d["name"])
        save_species[sid] = (
            name, d.get("growthRate", "Medium Fast"),
            [abil_data.get(ab, {}).get("name") if ab else None for ab in d.get("abilities", [])])
        if name in poks:
            # keep first; alt/totem dupes fall through to the base entry
            norm_index.setdefault(normalize(sid), name)
            continue

        abilities = {}
        slot_keys = ["0", "1", "H"]
        for i, ab in enumerate(d.get("abilities", [])):
            if ab:
                an = abil_data.get(ab, {}).get("name")
                if an:
                    abilities[slot_keys[i] if i < 3 else str(i)] = an

        tms = []
        special_moves = [entry.get("move") for entry in d.get("specialMoves", [])]
        for mid in (d.get("tmMoves", []) + d.get("tutorMoves", [])
                    + d.get("hmMoves", []) + special_moves):
            mn = move_name.get(mid)
            if mn and mn not in tms:
                tms.append(mn)
        learnset = []
        for lm in d.get("levelUpMoves", []):
            mn = move_name.get(lm["move"])
            if mn:
                learnset.append([lm["level"], mn])

        entry = {
            "bs": map_base_stats(d["baseStats"]),
            "types": [title_word(t) for t in d.get("types", [])],
            "learnset_info": {"tms": tms, "learnset": learnset},
        }
        if abilities:
            entry["abilities"] = abilities
        if d.get("weight") is not None:
            entry["weightkg"] = round(d["weight"] / 10.0, 1)
        poks[name] = entry
        norm_index[normalize(name)] = name
        norm_index.setdefault(normalize(sid), name)
        if d.get("sprite"):
            sprite_src_for[name] = d["sprite"].replace("/", os.sep)

    # Resolve source aliases (including older #define syntax) before matching
    # trainer display names. A missing game species must never use another dex.
    with open(common.src("include/constants/species.h"), encoding="utf-8") as source:
        constants = source.read()
    aliases = re.findall(r"SPECIES_(\w+)\s*(?:=\s*|\s+)SPECIES_(\w+)", constants)
    for _ in range(len(aliases) + 1):
        changed = False
        for alias, target in aliases:
            if normalize(alias) not in norm_index and normalize(target) in norm_index:
                norm_index[normalize(alias)] = norm_index[normalize(target)]
                changed = True
        if not changed:
            break

    # ── moves ────────────────────────────────────────────────────────────────
    # NOTE: power=0 in moves.json now means a genuinely non-damaging move
    # (parse_pokemon.read_num_field resolves the B_UPDATED_MOVE_DATA ternaries
    # that used to zero out ~100 damaging moves). The calc copies basePower
    # unconditionally, so emitting a 0 would zero out a move's damage — keep
    # skipping those and let the calc's built-in Gen 9 data fill them in.
    out_moves = {}
    for mid, m in moves_data.items():
        nm = m.get("name")
        if not nm or nm == "-":
            continue
        power = m.get("power", 0) or 0
        if power <= 0:
            continue
        out_moves[nm] = {
            "type": title_word(m["type"]),
            "category": title_word(m["category"]),
            "basePower": power,
        }

    # ── formatted_sets (trainer teams, grouped by tr_id) ──────────────────────
    # Each trainer needs a UNIQUE label: the calc isolates a trainer's team by
    # the label in the set name, and BPE has hundreds of duplicate names
    # ("GRUNT"). Non-unique labels would both break team grouping and collide
    # in formatted_sets[species] (overwriting sets). We disambiguate repeats by
    # appending an incrementing number, mirroring upstream ("Grunt6").
    items_data = common.load_json(ITEMS_JSON)
    mega_for = {}  # (ShowdownName, item display name) -> Mega ShowdownName
    for (species, item), target in mega_evolutions().items():
        source_name = norm_index.get(normalize(species))
        target_name = norm_index.get(normalize(target))
        item_name = items_data.get(item, {}).get("name")
        if source_name and target_name and item_name:
            mega_for[(source_name, item_name)] = target_name

    formatted_sets = {}
    unmatched = set()
    tr_id = 0
    label_counts = {}
    EV_KEYS = [("hp", "hp"), ("atk", "at"), ("def", "df"),
               ("spa", "sa"), ("spd", "sd"), ("spe", "sp")]

    for internal_tid in sorted(trainers.keys()):
        t = trainers[internal_tid]
        party = t.get("party") or []
        if not party or internal_tid == "TRAINER_NONE":
            continue
        tr_id += 1
        base_label = ("%s %s" % (t.get("class", ""), t.get("name", ""))).strip() \
            or "Trainer"
        label_counts[base_label] = label_counts.get(base_label, 0) + 1
        label = base_label if label_counts[base_label] == 1 \
            else "%s %d" % (base_label, label_counts[base_label])
        trainer_sprite = ("../img/sprites/%s" % t["pic"].replace(" ", "_")) \
            if t.get("pic") else None

        for sub_index, mon in enumerate(party):
            sp = mon.get("species")
            if not sp:
                continue
            # resolve to a poks key; fall back to the raw string (built-in dex)
            key = norm_index.get(normalize(sp), sp)
            if normalize(sp) not in norm_index:
                unmatched.add(sp)

            evs = {}
            for long, short in EV_KEYS:
                if mon.get("evs", {}).get(long):
                    evs[short] = mon["evs"][long]
            set_data = {
                "tr_id": tr_id,
                "sub_index": sub_index,
                "level": mon.get("level", 50),
                "moves": [m for m in (mon.get("moves") or []) if m] or ["-"],
                "nature": mon.get("nature", "Hardy"),
                "evs": evs,
                "ivs": {short: mon["ivs"][long] for long, short in EV_KEYS if long in mon.get("ivs", {})},
                "form": 0,
                "noCh": False,
                "battle_type": "Singles",
                "reward_item": "None",
            }
            if mon.get("ability"):
                set_data["ability"] = mon["ability"]
            if mon.get("item"):
                set_data["item"] = mon["item"]
                if (key, mon["item"]) in mega_for:
                    set_data["mega"] = mega_for[(key, mon["item"])]
            if trainer_sprite:
                set_data["sprite"] = trainer_sprite

            sets = formatted_sets.setdefault(key, {})
            set_name = "Lvl %d %s " % (set_data["level"], label)
            # ensure uniqueness within this species (same name/level trainers,
            # or a trainer carrying two of the same species)
            uniq = set_name
            n = 2
            while uniq in sets:
                uniq = "Lvl %d %s (%d) " % (set_data["level"], label, n)
                n += 1
            sets[uniq] = set_data

    save_data = build_save_data(save_species, poks, move_name,
                                {iid: item["name"] for iid, item in items_data.items()})

    blob = {
        "title": "BPE Emerald",
        "poks": poks,
        "moves": out_moves,
        "formatted_sets": formatted_sets,
        "save_data": save_data,
    }
    if unmatched:
        raise ValueError("Trainer species missing from this release's calculator data: " + ", ".join(sorted(unmatched)))
    common.write_json(OUT_JSON, blob)

    # ── sprites: copy BPE pokemon sprites into calc/img/newhd named per JS ─────
    if os.path.isdir(NEWHD_DIR):
        shutil.rmtree(NEWHD_DIR)
    os.makedirs(NEWHD_DIR, exist_ok=True)
    copied = missing = 0
    missing_names = []
    for name in poks:
        rel = sprite_src_for.get(name)
        src = os.path.join(SITE, rel) if rel else None
        if src and os.path.exists(src):
            dst = os.path.join(NEWHD_DIR, js_sprite_name(name) + ".png")
            shutil.copyfile(src, dst)
            copied += 1
        else:
            missing += 1
            if len(missing_names) < 20:
                missing_names.append((name, rel or "(no sprite field)"))

    # ── report ────────────────────────────────────────────────────────────────
    print("Wrote %s" % OUT_JSON)
    print("  poks:           %d" % len(poks))
    print("  moves:          %d" % len(out_moves))
    print("  trainers:       %d" % tr_id)
    print("  set species:    %d" % len(formatted_sets))
    print("  save numbering: %d species, %d moves, %d items" % tuple(
        sum(1 for entry in save_data[key] if entry) for key in ("species", "moves", "items")))
    print("Sprites -> %s" % NEWHD_DIR)
    print("  copied:  %d   missing: %d" % (copied, missing))
    if missing_names:
        print("  missing sprite sources (first 20):")
        for nm, sf in missing_names:
            print("    %-24s expected img/pokemon/%s" % (nm, sf))
    if unmatched:
        print("WARNING: %d trainer species not found in poks (using built-in "
              "dex fallback):" % len(unmatched))
        for s in sorted(unmatched):
            print("    %s" % s)


if __name__ == "__main__":
    main()
