"""Build the data behind the Battle Facilities page.

data/facilities.json holds the page's text. data/frontier_sets.json holds the
set tables: one table of sets, and the pools and Frontier Brain teams as lists
of ids into it, in the game's own order.

The tables are read from src/data/battle_frontier/frontier_sets.h at the
selected game source. That header is what the game compiles, so the page can't
disagree with it, and it is tracked: BPETools/generate_frontier_sets.py itself
can't run in a hosted export, because it reads teachable_learnsets.h, which only
a game build writes. The generator of the same source still supplies the pool
and tier names, and test_facilities_export.py checks both give the same pools.

The page's text is handwritten and belongs to the release, like features.json. A
release whose source has no BPETools/frontier_sets/ gets no sets, and the page
says so. Run after parse_pokemon and parse_items.
"""
import importlib.util
import json
import os
import re

import build_features
import common as C

CONTENT_PATH = C.src("BPEDocumentation", "content", "facilities.json")
SETS_FOLDER = C.src("BPETools", "frontier_sets")
HEADER_PATH = C.src("src", "data", "battle_frontier", "frontier_sets.h")
GENERATOR_PATH = C.src("BPETools", "generate_frontier_sets.py")
LICENSE_NAME = "LICENSE-pokemon-showdown.txt"
SCHEMA_VERSION = 1

SET_ROW = re.compile(r"^\s*SET\((\w+), (\w+), (\w+), (\w+), (\d+), (\w+), (\w+), (\w+), (\w+), (\w+)\),$", re.M)


def load_generator():
    """Import the generator of this game source, never the exporter's own copy."""
    spec = importlib.util.spec_from_file_location("frontier_sets_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _block(text, start):
    """The body of the array whose declaration begins with `start`."""
    begin = text.index(start)
    end = text.index("\n};", begin)
    return text[text.index("{", begin) + 1:end]


def _numbers(text):
    return [int(n) for n in re.findall(r"\d+", text)]


def parse_header(text):
    """Return the header's sets, EV spreads, pools by name and Brain team ids."""
    sets = [{"species": r[0], "item": r[1], "ability": r[2], "nature": r[3], "ev": int(r[4]),
             "moves": [m for m in r[5:9] if m != "NONE"],
             "hp": r[9][len("IVS_"):] if r[9].startswith("IVS_") else None}
            for r in SET_ROW.findall(_block(text, "const struct TrainerMon gFrontierSetMons[]"))]
    spreads = [_numbers(s) for s in re.findall(r"\{([\d, ]+)\}", _block(text, "static const u8 sFrontierSetEvs"))]
    pools = {name: _numbers(body) for name, body in re.findall(r"static const u16 sPool_(\w+)\[\] =\n\{(.*?)\n\};", text, re.S)}
    declared = re.findall(r"\{sPool_(\w+), (\d+)\}", text)
    if not declared or {name: int(n) for name, n in declared} != {name: len(ids) for name, ids in pools.items()}:
        raise ValueError("frontier_sets.h: pool sizes disagree with their tables.")
    full_dex = {}
    for facility, body in re.findall(r"\[FRONTIER_FACILITY_(\w+)\] = \{(.*?)\n    \},", _block(text, "const u16 gFrontierBrainFullDexTeams"), re.S):
        ids = _numbers(body)
        full_dex[facility.lower()] = [ids[:6], ids[6:12]]
    tier_ids = _numbers(_block(text, "const u16 gFrontierBrainTierTeams"))
    return {"sets": sets, "spreads": spreads, "pools": pools, "fullDexBrains": full_dex, "tierBrainIds": tier_ids}


def strongest_team(pool, sets, symbol):
    """The team a Brain uses in Gens 1-9, as GetStrongestBrainSetId in src/frontier_sets.c
    picks it: Gold's six are the pool's first six species, and Silver's the next six."""
    team, species = [], []
    wanted = range(6, 12) if symbol == 0 else range(6)
    for set_id in pool:
        name = sets[set_id]["species"]
        if name in species:
            continue
        if len(species) in wanted:
            team.append(set_id)
        species.append(name)
        if len(team) == 6:
            return team
    return team + [pool[0]] * (6 - len(team))


def build_pools(header, gen):
    """The game's rule sets as lists of set ids: {fullDex, smogon: {gen: {style: {tier}}}}."""
    pools = header["pools"]
    smogon = {}
    double_tiers = dict(zip(gen.DOUBLES, gen.TIERS))
    for g in gen.GENS:
        singles = {tier: pools[f"{g}_{tier}"] for tier in gen.TIERS if f"{g}_{tier}" in pools}
        doubles = {double_tiers[pool]: pools[f"{g}_{pool}"] for pool in gen.DOUBLES if f"{g}_{pool}" in pools}
        smogon[g] = {"singles": singles}
        if doubles:
            smogon[g]["doubles"] = doubles
    return {"fullDex": {"singles": pools["FullDex"], "doubles": pools["FullDexDoubles"]}, "smogon": smogon}


def build_brains(header, gen):
    """Full Dex teams by facility, then National Dex teams and each other generation's."""
    ids = header["tierBrainIds"]
    expected = len(gen.BRAIN_TIER_FACILITIES) * len(gen.TIERS) * 2 * 6
    if len(ids) != expected:
        raise ValueError("frontier_sets.h: the Brain tier teams have an unexpected size.")
    national, position = {}, 0
    for facility in gen.BRAIN_TIER_FACILITIES:
        national[facility] = {}
        for tier in gen.TIERS:
            national[facility][tier] = [ids[position:position + 6], ids[position + 6:position + 12]]
            position += 12
    sets, pools = header["sets"], header["pools"]
    gens = {g: {tier: [strongest_team(pools[f"{g}_{tier}"], sets, symbol) for symbol in (0, 1)]
                for tier in gen.TIERS if f"{g}_{tier}" in pools}
            for g in gen.GENS if g != gen.GENS[0]}
    return {"fullDex": header["fullDexBrains"], "nationalDex": national, "gens": gens}


class Table:
    """Strings shared by many sets, numbered in the order they first appear."""

    def __init__(self):
        self.rows, self.ids = [], {}

    def add(self, key, row):
        if key not in self.ids:
            self.ids[key] = len(self.rows)
            self.rows.append(row)
        return self.ids[key]


def _species_label(species, entry, site):
    """The name the Pokédex gives this form, since every form shares its species' name."""
    path = os.path.join(site, "data", "species", species + ".json")
    forms = C.load_json(path).get("forms") if os.path.isfile(path) else None
    return next((form["label"] for form in forms or [] if form["id"] == species), entry.get("name"))


def build_tables(header, gen, site=C.SITE):
    index = C.load_json(os.path.join(site, "data", "pokedex_index.json"))
    item_index = C.load_json(os.path.join(site, "data", "items_index.json"))
    move_names = C.load_json(os.path.join(site, "data", "moves.json"))
    ability_names = C.load_json(os.path.join(site, "data", "abilities.json"))
    species, items, abilities, natures, moves = Table(), Table(), Table(), Table(), Table()

    def named(table, key, source, prefix):
        return table.add(key, (source.get(key) or {}).get("name") or C.prettify_constant(prefix + key))

    def move_id(move, hidden_power):
        if move == "HIDDEN_POWER" and hidden_power:
            return moves.add(move + hidden_power, "Hidden Power " + hidden_power.title())
        return named(moves, move, move_names, "MOVE_")

    rows = []
    for s in header["sets"]:
        if s["species"] not in index:
            raise ValueError(f"frontier_sets.h: {s['species']} has no Pokédex entry.")
        entry = index[s["species"]]
        rows.append([
            species.add(s["species"], [s["species"], _species_label(s["species"], entry, site), entry.get("icon")]),
            -1 if s["item"] == "NONE" else items.add(s["item"], [s["item"], (item_index.get(s["item"]) or {}).get("name") or C.prettify_constant("ITEM_" + s["item"])]),
            -1 if s["ability"] == "NONE" else named(abilities, s["ability"], ability_names, "ABILITY_"),
            natures.add(s["nature"], s["nature"].title()),
            s["ev"],
        ] + [move_id(move, s["hp"]) for move in s["moves"]])
    return {"schemaVersion": SCHEMA_VERSION, "species": species.rows, "items": items.rows,
            "abilities": abilities.rows, "natures": natures.rows, "moves": moves.rows,
            "spreads": header["spreads"], "sets": rows,
            "pools": build_pools(header, gen), "brains": build_brains(header, gen)}


def build(content_path=CONTENT_PATH, site=C.SITE, header_path=HEADER_PATH, sets_folder=SETS_FOLDER):
    page_path = os.path.join(site, "data", "facilities.json")
    tables_path = os.path.join(site, "data", "frontier_sets.json")
    if not os.path.isdir(sets_folder) or not os.path.isfile(header_path):
        # Stale tables from another source must not be left for the page to find.
        if os.path.isfile(tables_path):
            os.remove(tables_path)
        C.write_json(page_path, {"schemaVersion": SCHEMA_VERSION, "available": False})
        print("Battle Facilities: this source has no set data")
        return None
    with open(header_path, encoding="utf-8") as f:
        header = parse_header(f.read())
    tables = build_tables(header, load_generator(), site)
    with open(tables_path, "w", encoding="utf-8") as f:
        json.dump(tables, f, ensure_ascii=False, separators=(",", ":"))
    page = {"schemaVersion": SCHEMA_VERSION, "available": True, "curated": False}
    if os.path.isfile(content_path):
        content = build_features.validate_content(C.load_json(content_path))
        page.update(curated=True, intro=content["intro"], sections=content["sections"])
    license_path = os.path.join(sets_folder, LICENSE_NAME)
    if os.path.isfile(license_path):
        with open(license_path, encoding="utf-8") as f:
            page["showdownLicense"] = f.read().strip()
    C.write_json(page_path, page)
    print(f"Battle Facilities: {len(tables['sets'])} sets, {len(tables['species'])} species, "
          f"{os.path.getsize(tables_path) // 1024} KB")
    return tables


def main():
    C.ensure_dirs()
    return build()


if __name__ == "__main__":
    main()
