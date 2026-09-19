"""Generate the lookup tables behind BPE's built-in randomizer.

Writes src/data/randomizer/generated.h, which only src/randomizer.c includes:

  sRandomizerFamilyRoot       first stage of each species' evolution family
  sRandomizerSpeciesSources   where the normal game hands out each species
                              (wild tables, gifts and trades, static encounters)
  sRandomizerTradeRequests    where each in-game trade's requested species is
                              first found in the wild
  sRandomizerFieldItems       every item ball and hidden item, in a fixed order
  sRandomizerFieldItemsByFlag the same locations sorted by their item flag
  sRandomizerTMTier           the badge count at which each TM can first be
                              obtained outside the field items

The field item order is append-only: existing locations keep their index and new
ones are added at the end, so a game update doesn't reshuffle the items of an
existing randomized save. Badge tiers come from BPETools/randomizer_badge_tiers.json.

Run from the repository root after changing evolutions, wild tables, gift or
static scripts, trades, item balls, hidden items or TM sources:

    python BPETools/generate_randomizer_data.py          # rewrite the header
    python BPETools/generate_randomizer_data.py --check  # fail if it is stale
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "src", "data", "randomizer", "generated.h")
TIERS = os.path.join(ROOT, "BPETools", "randomizer_badge_tiers.json")
TIER_NEVER = 255

sys.path.insert(0, os.path.join(ROOT, "BPEDocumentation", "scripts"))
os.environ.setdefault("BPE_SOURCE_ROOT", ROOT)
import parse_pokemon  # noqa: E402  (the documentation exporter's species parser)


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def read_abs(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Species names ──────────────────────────────────────────────────────────────

def parse_species_ids():
    """Every species name (including aliases) -> its numeric ID, plus ID -> canonical name."""
    text = read("include/constants/species.h")
    ids, canonical = {}, {}
    for name, value in re.findall(r"^\s+(SPECIES_\w+)\s*=\s*([^,]+),", text, re.M):
        value = value.strip()
        if value.isdigit():
            ids[name] = int(value)
            canonical.setdefault(int(value), name)
        elif value in ids:
            ids[name] = ids[value]
    for name, value in re.findall(r"^#define\s+(SPECIES_\w+)\s+(SPECIES_\w+)", text, re.M):
        if value in ids:
            ids[name] = ids[value]
    return ids, canonical


SPECIES_IDS, CANONICAL = parse_species_ids()


def canonical(name):
    """The enum name of a species, or None for SPECIES_NONE and unknown names."""
    if not name.startswith("SPECIES_"):
        name = "SPECIES_" + name
    number = SPECIES_IDS.get(name)
    if not number:
        return None
    return CANONICAL[number]


# ── Evolution families ─────────────────────────────────────────────────────────

def parse_family_roots():
    """Map every species that evolves from another to the first stage of its family."""
    info_dir = os.path.join(ROOT, "src", "data", "pokemon", "species_info")
    parents = collections.defaultdict(set)
    for path in sorted(glob.glob(os.path.join(info_dir, "gen_*_families.h"))):
        raw = parse_pokemon.read_file(path)
        macros = parse_pokemon.collect_macros(raw)
        content = parse_pokemon.strip_c_comments(raw)
        for key, block in parse_pokemon.iter_species_decls(content, macros):
            for evo in parse_pokemon._parse_evolutions(block):
                if evo["target"] != key:
                    parents[evo["target"]].add(key)

    def root_of(species, seen=()):
        if species not in parents or species in seen:
            return species
        # Gholdengo has two parents (both Gimmighoul forms); the lowest name is stable.
        return root_of(min(parents[species]), seen + (species,))

    roots = {}
    for species in parents:
        name, root = canonical(species), canonical(root_of(species))
        if name and root and name != root:
            roots[name] = root
    return roots


# ── Where the normal game hands out species ────────────────────────────────────

SOURCE_WILD, SOURCE_GIFT, SOURCE_STATIC = 1, 2, 4
SOURCE_NAMES = {SOURCE_WILD: "RANDOMIZER_SOURCE_WILD",
                SOURCE_GIFT: "RANDOMIZER_SOURCE_GIFT",
                SOURCE_STATIC: "RANDOMIZER_SOURCE_STATIC"}
WILD_AREAS = {"land_mons": "WILD_AREA_LAND", "water_mons": "WILD_AREA_WATER",
              "rock_smash_mons": "WILD_AREA_ROCKS", "fishing_mons": "WILD_AREA_FISHING",
              "hidden_mons": "WILD_AREA_HIDDEN"}
# Gifts the randomizer handles elsewhere: the Johto starters follow the Starters
# option, and the debug menu's gifts are not part of the game.
STARTER_GIFTS = {"SPECIES_CHIKORITA", "SPECIES_CYNDAQUIL", "SPECIES_TOTODILE"}


def script_files():
    files = sorted(glob.glob(os.path.join(ROOT, "data", "maps", "*", "scripts.inc")))
    files += sorted(f for f in glob.glob(os.path.join(ROOT, "data", "scripts", "*.inc"))
                    if os.path.basename(f) != "debug.inc")
    return files


def wild_tables():
    # wild_encounters.json still lists upstream's FireRed/LeafGreen maps, which BPE doesn't have.
    existing = {data["id"] for _, data in load_maps()}
    data = json.loads(read("src/data/wild_encounters.json"))
    for group in data["wild_encounter_groups"]:
        if group.get("label") != "gWildMonHeaders":
            continue  # the Battle Pyramid and Battle Pike keep their own tables
        for encounter in group["encounters"]:
            if encounter.get("map") not in existing:
                continue
            for field, area in WILD_AREAS.items():
                table = encounter.get(field)
                if table:
                    yield encounter["map"], area, [mon["species"] for mon in table["mons"]]


def parse_sources():
    sources = collections.defaultdict(int)

    def add(species, source):
        name = canonical(species)
        if name:
            sources[name] |= source

    for _, _, species_list in wild_tables():
        for species in species_list:
            add(species, SOURCE_WILD)
    add("SPECIES_FEEBAS", SOURCE_WILD)  # the Route 119 fishing tiles
    for species in re.findall(r"\.species\s*=\s*(SPECIES_\w+)", read("src/tv.c")):
        add(species, SOURCE_WILD)  # TV mass outbreaks

    for path in script_files():
        text = parse_pokemon.strip_c_comments(read_abs(path))
        for species in re.findall(r"^\s*setwildbattle\s+(SPECIES_\w+)", text, re.M):
            add(species, SOURCE_STATIC)
        gifts = re.findall(r"^\s*(?:give(?:mon|egg)|randomgift)\s+(SPECIES_\w+)", text, re.M)
        gifts += re.findall(r"^\s*setvar\s+VAR_RESULT,\s*(SPECIES_\w+)\s*\n\s*special\s+RandomizeEggSpecies", text, re.M)
        for species in gifts:
            if species not in STARTER_GIFTS:
                add(species, SOURCE_GIFT)
    for species in re.findall(r"TryAddRoamer\((SPECIES_\w+)", read("src/roamer.c")):
        add(species, SOURCE_STATIC)
    for species in re.findall(r"^\s*\.species\s*=\s*(SPECIES_\w+)", read("src/data/trade.h"), re.M):
        add(species, SOURCE_GIFT)
    return dict(sources)


def parse_trade_requests():
    """In-game trade -> (map, area) where its requested species first appears in the wild."""
    first_seen = {}
    for map_id, area, species_list in wild_tables():
        for species in species_list:
            if canonical(species):
                first_seen.setdefault(canonical(species), (map_id, area))
    requests = {}
    trade_h = read("src/data/trade.h")
    for trade, body in re.findall(r"\[(INGAME_TRADE_\w+)\]\s*=\s*\{(.*?)\n    \}", trade_h, re.S):
        match = re.search(r"\.requestedSpecies\s*=\s*(SPECIES_\w+)", body)
        if match and canonical(match.group(1)) in first_seen:
            requests[trade] = first_seen[canonical(match.group(1))]
    return requests


# ── Badge tiers and item locations ─────────────────────────────────────────────

def load_maps():
    maps = []
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "maps", "*", "map.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        maps.append((os.path.dirname(path), data))
    return maps


def map_tier(tiers, map_data):
    if map_data["id"] in tiers["maps"]:
        return tiers["maps"][map_data["id"]]
    section = map_data.get("region_map_section")
    if section not in tiers["sections"]:
        raise SystemExit(f"{map_data['id']}: region map section {section} has no tier in {TIERS}")
    return tiers["sections"][section]


def parse_flag_values():
    values = {}
    for name, expr in re.findall(r"^#define\s+(FLAG_\w+)\s+(.+?)\s*(?://.*)?$", read("include/constants/flags.h"), re.M):
        values[name] = expr
    resolved = {}

    def value(name, depth=0):
        if name in resolved:
            return resolved[name]
        expr = re.sub(r"\b(FLAG_\w+)\b", lambda m: str(value(m.group(1), depth + 1)), values[name])
        resolved[name] = int(eval(expr, {"__builtins__": {}}))  # flags.h only uses +, - and literals
        return resolved[name]

    return value


def parse_field_items(maps, tiers):
    items = []
    for _, data in maps:
        tier = map_tier(tiers, data)
        for obj in data.get("object_events", []):
            if obj.get("script") == "Common_EventScript_FindItem" and obj.get("flag", "0") != "0":
                amount = int(obj.get("movement_range_x", 0) or 0) or 1
                items.append((obj["flag"], obj["trainer_sight_or_berry_tree_id"], amount, tier))
        for bg in data.get("bg_events", []):
            if bg.get("type") == "hidden_item":
                amount = int(bg.get("quantity", 1) or 1)
                items.append((bg["flag"], bg["item"], amount, tier))
    overrides = tiers.get("items", {})
    seen, unique = set(), []
    for flag, item, amount, tier in items:
        if flag not in seen:
            seen.add(flag)
            unique.append((flag, item, amount, overrides.get(flag, tier)))
    return unique


def previous_item_order():
    if not os.path.exists(OUTPUT):
        return []
    text = read_abs(OUTPUT)
    block = re.search(r"sRandomizerFieldItems\[\] =\n\{(.*?)\n\};", text, re.S)
    return re.findall(r"\{(FLAG_\w+|0)," , block.group(1)) if block else []


def order_field_items(items):
    """Keep every previous location at its index and append new ones."""
    by_flag = {flag: (flag, item, amount, tier) for flag, item, amount, tier in items}
    ordered = []
    for flag in previous_item_order():
        # A removed location keeps its slot as an empty placeholder.
        ordered.append(by_flag.pop(flag, ("0", "ITEM_NONE", 0, TIER_NEVER)))
    ordered.extend(by_flag[flag] for flag, *_ in items if flag in by_flag)
    return ordered


def parse_tm_tiers(maps, tiers):
    best = {}

    def note(tm, tier):
        best[tm] = min(best.get(tm, TIER_NEVER), tier)

    for folder, data in maps:
        script = os.path.join(folder, "scripts.inc")
        if not os.path.exists(script):
            continue
        tier = tiers["gyms"].get(data["id"], map_tier(tiers, data))
        text = parse_pokemon.strip_c_comments(read_abs(script))
        for tm in set(re.findall(r"\b(ITEM_TM_\w+)", text)):
            note(tm, tier)
    for name, tier in tiers.get("scripts", {}).items():
        text = read_abs(os.path.join(ROOT, "data", "scripts", name))
        for tm in set(re.findall(r"\b(ITEM_TM_\w+)", text)):
            note(tm, tier)
    tm_list = re.search(r"#define FOREACH_TM\(F\)(.*?)\n\n", read("include/constants/tms_hms.h"), re.S).group(1)
    return [(name, best.get("ITEM_TM_" + name, TIER_NEVER)) for name in re.findall(r"F\((\w+)\)", tm_list)]


# ── Output ─────────────────────────────────────────────────────────────────────

def render(roots, sources, requests, field_items, flag_value, tm_tiers):
    out = ["// Generated by BPETools/generate_randomizer_data.py. Do not edit by hand.",
           "// Included only by src/randomizer.c.", ""]

    out += ["static const u16 sRandomizerFamilyRoot[NUM_SPECIES] =", "{"]
    for species, root in sorted(roots.items(), key=lambda item: SPECIES_IDS[item[0]]):
        out.append(f"    [{species}] = {root},")
    out += ["};", ""]

    out += ["static const u8 sRandomizerSpeciesSources[NUM_SPECIES] =", "{"]
    for species, mask in sorted(sources.items(), key=lambda item: SPECIES_IDS[item[0]]):
        names = " | ".join(SOURCE_NAMES[bit] for bit in sorted(SOURCE_NAMES) if mask & bit)
        out.append(f"    [{species}] = {names},")
    out += ["};", ""]

    out += ["static const struct RandomizerTradeRequest sRandomizerTradeRequests[] =", "{"]
    for trade, (map_id, area) in sorted(requests.items()):
        out.append(f"    [{trade}] = {{{map_id}, {area}}},")
    out += ["};", ""]

    out += ["// Append-only: an existing location must keep its index.",
            "static const struct RandomizerFieldItem sRandomizerFieldItems[] =", "{"]
    for flag, item, amount, tier in field_items:
        out.append(f"    {{{flag}, {item}, {amount}, {tier}}},")
    out += ["};", ""]

    by_flag = sorted((flag_value(flag), index) for index, (flag, *_) in enumerate(field_items) if flag != "0")
    out += ["// Indexes into sRandomizerFieldItems, sorted by item flag for binary search.",
            "static const u16 sRandomizerFieldItemsByFlag[] =", "{"]
    for _, index in by_flag:
        out.append(f"    {index}, // {field_items[index][0]}")
    out += ["};", ""]

    out += ["// Lowest badge tier at which each TM is obtainable outside the field items,",
            f"// in TM order; {TIER_NEVER} means only field items (or nothing) provide it.",
            "static const u8 sRandomizerTMTier[NUM_TECHNICAL_MACHINES] =", "{"]
    for name, tier in tm_tiers:
        out.append(f"    {tier}, // TM {name}")
    out += ["};", ""]
    return "\n".join(out)


def main_text():
    """The header this script would write."""
    with open(TIERS, encoding="utf-8") as f:
        tiers = json.load(f)
    maps = load_maps()
    return render(parse_family_roots(), parse_sources(), parse_trade_requests(),
                  order_field_items(parse_field_items(maps, tiers)), parse_flag_values(),
                  parse_tm_tiers(maps, tiers))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit with 1 if the header is out of date")
    args = parser.parse_args()

    text = main_text()

    current = read_abs(OUTPUT) if os.path.exists(OUTPUT) else None
    if args.check:
        if current != text:
            print(f"{os.path.relpath(OUTPUT, ROOT)} is out of date; run python BPETools/generate_randomizer_data.py")
            return 1
        print(f"{os.path.relpath(OUTPUT, ROOT)} is up to date")
        return 0
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"Wrote {os.path.relpath(OUTPUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
