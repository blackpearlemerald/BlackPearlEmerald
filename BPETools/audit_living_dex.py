"""Check that a full living dex, every storable alternate form included, can be
collected in BPE.

Works from the game source, like generate_randomizer_data.py, whose parsers it
reuses. A form counts as obtainable when a chain of in-game steps reaches it:

  sources     wild tables, gifts, trades, static and roaming encounters, TV
              outbreaks and the Mirage Island legendary pool (a starter pick
              is a one-off choice, so the Birch Case does not count)
  variants    the forms a wild species can appear in, from
              src/data/wild_form_variants.h, and Unown's letters
  evolution   from an obtainable species whose method is possible: any item
              it needs must be obtainable, and region-locked branches only
              fire in Hoenn
  breeding    the egg an obtainable parent produces, following the daycare's
              rules (Everstone keeps a foreign regional form)
  form change out-of-battle changes: item use, held items, learning a move,
              fusions, Burmy's cloak and Minior's core after battle

Forms that exist only in battle (Megas, Gigantamax, Tera forms, Zen Mode,
Castform's weather forms and the like) cannot be kept, so they are not
required. Totem Pokemon are size variants of their species rather than forms;
the script lists them separately and does not require them.

Run from the repository root:

    python BPETools/audit_living_dex.py            # report, exit 1 on gaps
    python BPETools/audit_living_dex.py --verbose  # also say how each form is reached
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "BPETools"))
import generate_randomizer_data as grd  # noqa: E402
import parse_pokemon  # noqa: E402  (imported by grd; the documentation's species parser)

canonical = grd.canonical
strip = parse_pokemon.strip_c_comments


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


# ── Species data ───────────────────────────────────────────────────────────────

FLAG_FIELDS = ("isMegaEvolution", "isPrimalReversion", "isUltraBurst", "isGigantamax",
               "isTeraForm", "isTotem")


def parse_evolution_entries(block):
    """[(method, param, target, [(condition, value), ...]), ...] for one species."""
    m = re.search(r"\.evolutions\s*=\s*EVOLUTION\(", block)
    if not m:
        return []
    content = parse_pokemon._extract_paren_content(block, m.end() - 1)
    out = []
    for entry in parse_pokemon._extract_brace_entries(content):
        em = re.match(r"\{\s*(EVO_\w+)\s*,\s*([^,{]+?)\s*,\s*(SPECIES_\w+)(.*)\}$", entry.strip(), re.S)
        if not em:
            continue
        conds = re.findall(r"\{\s*(IF_\w+)\s*(?:,\s*([^}]*?))?\s*\}", em.group(4))
        out.append((em.group(1), em.group(2).strip(), em.group(3), [(c, v.strip()) for c, v in conds]))
    return out


def load_species():
    info = {}
    info_dir = os.path.join(ROOT, "src", "data", "pokemon", "species_info")
    for path in sorted(glob.glob(os.path.join(info_dir, "gen_*_families.h"))):
        raw = parse_pokemon.read_file(path)
        macros = parse_pokemon.collect_macros(raw)
        for key, block in parse_pokemon.iter_species_decls(strip(raw), macros):
            name = canonical(key)
            if not name or name in info:
                continue
            table = re.search(r"\.formChangeTable\s*=\s*(s\w+)", block)
            eggs = re.search(r"\.eggGroups\s*=\s*MON_EGG_GROUPS\(([^)]+)\)", block)
            gender = re.search(r"\.genderRatio\s*=\s*([^,\n]+)", block)
            info[name] = {
                "flags": {f for f in FLAG_FIELDS if re.search(r"\." + f + r"\s*=\s*TRUE", block)},
                "formTable": table.group(1) if table else None,
                "eggGroups": re.findall(r"EGG_GROUP_(\w+)", eggs.group(1)) if eggs else [],
                "gender": gender.group(1).strip() if gender else "",
                "evolutions": [(meth, par, canonical(t), conds)
                               for meth, par, t, conds in parse_evolution_entries(block)
                               if canonical(t)],
                "heldItems": re.findall(r"\.item(?:Common|Rare)\s*=\s*(ITEM_\w+)", block),
                "learnsets": [m.group(1) for m in re.finditer(
                    r"\.(?:levelUpLearnset|teachableLearnset|eggMoveLearnset)\s*=\s*s(\w+?)(?:LevelUp|Teachable|EggMove)Learnset", block)],
            }
    return info


def load_learnable_moves(species):
    """Species -> the moves it can ever know (level-up, TM/tutor, egg)."""
    pools = (parse_pokemon.parse_level_up_learnsets(),
             parse_pokemon.parse_egg_moves(),
             parse_pokemon.parse_teachable_learnsets())
    out = {}
    for name, info in species.items():
        moves = set()
        for stem in info["learnsets"]:
            for pool in pools:
                for entry in pool.get(stem, ()):
                    moves.add(entry["move"] if isinstance(entry, dict) else entry)
        out[name] = moves
    return out


def load_form_tables():
    """Table name -> [(method, target, [params])], and fusions as (item, a, b, result)."""
    text = strip(read("src/data/pokemon/form_change_tables.h"))
    tables = {}
    for name, body in re.findall(r"struct FormChange (s\w+)\[\]\s*=\s*\{(.*?)\n\};", text, re.S):
        rows = []
        for method, rest in re.findall(r"\{\s*(FORM_CHANGE_\w+)\s*,?\s*([^}]*)\}", body):
            args = [a.strip() for a in rest.split(",") if a.strip()]
            target = canonical(args[0]) if args and args[0].startswith("SPECIES_") else None
            rows.append((method, target, args[1:]))
        tables[name] = rows
    fusions = []
    for body in re.findall(r"struct Fusion s\w+\[\]\s*=\s*\{(.*?)\n\};", text, re.S):
        for a in re.findall(r"\{\s*\d+\s*,\s*(ITEM_\w+)\s*,\s*(SPECIES_\w+)\s*,\s*(SPECIES_\w+)\s*,\s*(SPECIES_\w+)", body):
            fusions.append((a[0], canonical(a[1]), canonical(a[2]), canonical(a[3])))
    return tables, fusions


# ── Items the player can get ───────────────────────────────────────────────────

PRIZE_FILES = ("src/battle_arena.c", "src/battle_palace.c", "src/battle_pyramid.c",
               "src/battle_tent.c", "src/lottery_corner.c", "src/pokemon_jump.c",
               "src/trainer_hill.c", "src/frontier_util.c", "src/battle_pike.c")


def load_items():
    """Item -> set of places it comes from."""
    items = collections.defaultdict(set)
    for path in grd.script_files():
        text = strip(grd.read_abs(path))
        where = os.path.basename(os.path.dirname(path)) if "maps" in path else os.path.basename(path)
        for item in re.findall(r"^\s*(?:finditem|giveitem|giveitem_msg|additem)\s+(ITEM_\w+)", text, re.M):
            items[item].add("script " + where)
        for item in re.findall(r"^\s*\.2byte\s+(ITEM_\w+)", text, re.M):
            items[item].add("mart " + where)
    for path in glob.glob(os.path.join(ROOT, "data", "maps", "*", "map.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for bg in data.get("bg_events", []):
            if bg.get("type") == "hidden_item":
                items[bg["item"]].add("hidden " + data["name"])
        for obj in data.get("object_events", []):
            if obj.get("script") == "Common_EventScript_FindItem":
                items[obj["trainer_sight_or_berry_tree_id"]].add("item ball " + data["name"])
    for path in PRIZE_FILES:
        if os.path.exists(os.path.join(ROOT, path)):
            for item in re.findall(r"\b(ITEM_\w+)\b", strip(read(path))):
                items[item].add("prize " + os.path.basename(path))
    return items


def load_event_mon_statics():
    """Placed legendaries whose scripts build the battle with seteventmon instead
    of setwildbattle: Mew on Faraway Island, Lugia and Ho-Oh on Navel Rock, and
    Deoxys on Birth Island. generate_randomizer_data only looks for setwildbattle,
    because those four are not randomized."""
    names = set()
    for path in grd.script_files():
        text = strip(grd.read_abs(path))
        for species in re.findall(r"^\s*seteventmon\s+(SPECIES_\w+)", text, re.M):
            name = canonical(species)
            if name:
                names.add(name)
    return names


def direct_sources():
    """grd.parse_sources(), without the in-game trades no map offers.

    src/data/trade.h also holds FireRed and LeafGreen's trades (Lickitung, Mr.
    Mime, Jynx, ...), which grd counts as gifts. The randomizer keeps that as it
    is, since changing it would change existing seeds, but for the living dex a
    trade only counts if some script makes it."""
    used = set()
    for path in grd.script_files():
        used.update(re.findall(r"\bINGAME_TRADE_\w+", grd.read_abs(path)))
    trades = re.findall(r"\[(INGAME_TRADE_\w+)\]\s*=\s*\{(.*?)\n    \}", read("src/data/trade.h"), re.S)
    trade_h = "".join(f"[{trade}] = {{{body}\n    }},\n" for trade, body in trades if trade in used)
    original = grd.read
    grd.read = lambda path: trade_h if path == "src/data/trade.h" else original(path)
    try:
        return grd.parse_sources()
    finally:
        grd.read = original


def load_mirage_pool():
    text = strip(read("src/field_specials.c"))
    body = re.search(r"sIslandLegendaryPool\[\]\s*=\s*\{(.*?)\};", text, re.S).group(1)
    return [canonical(s) for s in re.findall(r"SPECIES_\w+", body)]


def load_wild_variants():
    """Species a wild table lists -> the forms an encounter with it can become."""
    text = strip(read("src/data/wild_form_variants.h"))
    arrays = {name: [canonical(s) for s in re.findall(r"SPECIES_\w+", body)]
              for name, body in re.findall(r"u16 (s\w+)\[\]\s*=\s*\{(.*?)\};", text, re.S)}
    return {canonical(species): arrays[forms]
            for species, forms in re.findall(r"VARIANTS\((SPECIES_\w+),\s*\d+,\s*(s\w+)\)", text)}


def scatterbug_breed_form():
    match = re.search(r"#define\s+P_SCATTERBUG_LINE_FORM_BREED\s+(SPECIES_\w+)", read("include/config/pokemon.h"))
    return canonical(match.group(1))


# ── The reachability pass ──────────────────────────────────────────────────────

# Form change methods that happen outside battle and leave the Pokemon in the
# new form. Minior's core (FORM_CHANGE_END_BATTLE) is what a caught Minior keeps.
KEEP_METHODS = {"FORM_CHANGE_ITEM_USE", "FORM_CHANGE_ITEM_USE_MULTICHOICE", "FORM_CHANGE_ITEM_HOLD",
                "FORM_CHANGE_MOVE", "FORM_CHANGE_END_BATTLE_ENVIRONMENT", "FORM_CHANGE_END_BATTLE"}
# Ways into a form that mean it can sit in the PC. Everything else is a battle
# transformation (or Castform's weather, which the PC undoes).
RESTING_METHODS = KEEP_METHODS | {"EVOLUTION", "FUSION", "FORM_CHANGE_FAINT", "FORM_CHANGE_WITHDRAW",
                                  "FORM_CHANGE_DEPOSIT", "FORM_CHANGE_DAYS_PASSED",
                                  "FORM_CHANGE_TIME_OF_DAY", "FORM_CHANGE_STATUS"}
BATTLE_FLAGS = {"isMegaEvolution", "isPrimalReversion", "isUltraBurst", "isGigantamax", "isTeraForm"}
CURRENT_REGION = "REGION_HOENN"
# No BPE script runs tryspecialevo, so script-triggered evolutions never happen.
IMPOSSIBLE_EVOS = {"EVO_NONE", "EVO_SCRIPT_TRIGGER"}
# Battle forms that no form change table leads to: Ash-Greninja comes from
# Battle Bond, Eternamax exists only in its story battle, and Shadow Lugia is
# the Orre battle form.
NOT_FORMS = {"SPECIES_GRENINJA_ASH", "SPECIES_ETERNATUS_ETERNAMAX", "SPECIES_LUGIA_SHADOW"}
EGG_REPLACEMENTS = {"SPECIES_MANAPHY": "SPECIES_PHIONE",
                    "SPECIES_SINISTEA_ANTIQUE": "SPECIES_SINISTEA_PHONY",
                    "SPECIES_POLTCHAGEIST_ARTISAN": "SPECIES_POLTCHAGEIST_COUNTERFEIT",
                    "SPECIES_MIMIKYU_TOTEM_DISGUISED": "SPECIES_MIMIKYU_DISGUISED",
                    "SPECIES_TOGEDEMARU_TOTEM": "SPECIES_TOGEDEMARU"}


class Audit:
    def __init__(self):
        self.species = load_species()
        self.tables, self.fusions = load_form_tables()
        self.items = load_items()
        self.mirage = load_mirage_pool()
        self.event_statics = load_event_mon_statics()
        self.variants = load_wild_variants()
        self.moves = load_learnable_moves(self.species)
        self.scatterbug_egg = scatterbug_breed_form()
        self.order = sorted(self.species, key=lambda n: grd.SPECIES_IDS[n])
        self.how = {}
        self.blocked = collections.defaultdict(list)
        # First parent in species order, as the daycare walks them.
        self.parents = {}
        for name in self.order:
            for _, _, target, _ in self.species[name]["evolutions"]:
                if target != name:
                    self.parents.setdefault(target, name)
        # Mirage Island's Floette brings its Mega Stone.
        for name in self.mirage:
            item = self.mirage_held_item(name)
            if item:
                self.items[item].add("held by Mirage Island " + name[8:])

    def mirage_held_item(self, name):
        # Mirrors GetIslandLegendaryHeldItem in src/field_specials.c.
        return "ITEM_FLOETTITE" if name == "SPECIES_FLOETTE_ETERNAL" else None

    def item_ok(self, item):
        item = item.strip()
        if item in ("ITEM_NONE", "0", ""):
            return True
        if self.items.get(item):
            return True
        # Held by an obtainable wild Pokemon: Thief, Covet or Pickup can take it.
        return any(item in info["heldItems"] and name in self.how for name, info in self.species.items())

    def cond_ok(self, conds):
        for cond, value in conds:
            if cond == "IF_REGION" and value != CURRENT_REGION:
                return False, f"{cond} {value}"
            if cond == "IF_NOT_REGION" and value == CURRENT_REGION:
                return False, f"{cond} {value}"
            if cond in ("IF_HOLD_ITEM", "IF_BAG_ITEM_COUNT") and value:
                item = value.split(",")[0].strip()
                if item.startswith("ITEM_") and not self.item_ok(item):
                    return False, f"{cond} {item} unobtainable"
            if cond == "IF_SPECIES_IN_PARTY":
                target = canonical(value.split(",")[0].strip())
                if target and target not in self.how:
                    return False, f"{cond} {value} not yet obtainable"
        return True, ""

    def egg_species(self, name):
        for _ in range(5):
            if name not in self.parents:
                break
            name = self.parents[name]
        name = EGG_REPLACEMENTS.get(name, name)
        if name.startswith("SPECIES_ROTOM"):
            return "SPECIES_ROTOM"
        if name.startswith("SPECIES_SCATTERBUG"):
            return self.scatterbug_egg
        if name.startswith("SPECIES_FURFROU"):
            return "SPECIES_FURFROU_NATURAL"
        return name

    def add(self, name, how):
        if name and name in self.species and name not in self.how:
            self.how[name] = how
            return True
        return False

    def run(self):
        sources = direct_sources()
        for name in sources:
            self.add(name, "wild/gift/static")
        for name in self.event_statics:
            self.add(name, "wild/gift/static")
        for name in self.mirage:
            self.add(name, "Mirage Island")
        for base, forms in self.variants.items():
            if sources.get(base, 0) & grd.SOURCE_WILD:
                for form in forms:
                    self.add(form, f"wild {base[8:]} variant")
        if "SPECIES_UNOWN" in self.how:
            for name in self.species:
                if name.startswith("SPECIES_UNOWN_"):
                    self.add(name, "Unown personality")

        changed = True
        while changed:
            changed = False
            for name in self.order:
                if name in self.how:
                    changed |= self.expand(name)
            for item, a, b, result in self.fusions:
                if result in self.how or a not in self.how or b not in self.how:
                    continue
                if not self.item_ok(item):
                    self.blocked[result].append(f"fusion {item} unobtainable")
                    continue
                changed |= self.add(result, f"fusion of {a[8:]} and {b[8:]} with {item}")

    def expand(self, name):
        info = self.species[name]
        changed = False
        for method, param, target, conds in info["evolutions"]:
            if target in self.how:
                continue
            if method in IMPOSSIBLE_EVOS:
                self.blocked[target].append(f"{method} from {name[8:]}")
                continue
            if "ITEM" in method and param.startswith("ITEM_") and not self.item_ok(param):
                self.blocked[target].append(f"{method} {param} unobtainable (from {name[8:]})")
                continue
            ok, why = self.cond_ok(conds)
            if not ok:
                self.blocked[target].append(f"{method} from {name[8:]}: {why}")
                continue
            changed |= self.add(target, f"evolves from {name[8:]} ({method} {param})")

        if info["eggGroups"] and "NO_EGGS_DISCOVERED" not in info["eggGroups"]:
            genderless = "MON_GENDERLESS" in info["gender"]
            if not genderless or "SPECIES_DITTO" in self.how:
                egg = self.egg_species(name)
                changed |= self.add(egg, f"bred from {name[8:]}")
                if egg == "SPECIES_NIDORAN_F":
                    changed |= self.add("SPECIES_NIDORAN_M", f"bred from {name[8:]}")
                if egg == "SPECIES_ILLUMISE":
                    changed |= self.add("SPECIES_VOLBEAT", f"bred from {name[8:]}")
                # A regional form is foreign in Hoenn: bred without an Everstone,
                # its Egg hatches the first form in its table (GetRegionalFormByRegion).
                base = re.sub(r"_(ALOLA|GALAR|HISUI|PALDEA)(_\w+)?$", "", egg)
                if base != egg:
                    changed |= self.add(base, f"bred from {name[8:]} without an Everstone")

        for method, target, args in self.tables.get(info["formTable"], []):
            if not target or target in self.how or target == name or method not in KEEP_METHODS:
                continue
            item = next((a for a in args if a.startswith("ITEM_")), None)
            if item and not self.item_ok(item):
                self.blocked[target].append(f"{method} {item} unobtainable (from {name[8:]})")
                continue
            if method == "FORM_CHANGE_MOVE" and "WHEN_LEARNED" in args:
                move = next((a for a in args if a.startswith("MOVE_")), None)
                if move and move[5:] not in self.moves.get(name, ()):
                    self.blocked[target].append(f"{method} {move} not learnable (from {name[8:]})")
                    continue
            changed |= self.add(target, f"form change from {name[8:]} ({method} {item or ''})".strip())
        return changed

    def storable(self, name):
        info = self.species[name]
        if name in NOT_FORMS or info["flags"] & BATTLE_FLAGS:
            return False
        incoming = []
        for other, oinfo in self.species.items():
            if other == name:
                continue
            incoming += [m for m, target, _ in self.tables.get(oinfo["formTable"], []) if target == name]
            incoming += ["EVOLUTION" for _, _, target, _ in oinfo["evolutions"] if target == name]
        incoming += ["FUSION" for _, _, _, result in self.fusions if result == name]
        return not incoming or any(m in RESTING_METHODS for m in incoming)


# Every Mirage Island entry is meant to be a Pokemon the player cannot already
# make from something else, so the lottery never offers what feels like a repeat.
# These are the deliberate exceptions, each with the reason it earns its slot.
POOL_DUPES_ALLOWED = {
    "SPECIES_NECROZMA_DUSK_MANE":  "the one Necrozma can only be fused one way at a time",
    "SPECIES_NECROZMA_DAWN_WINGS": "the one Necrozma can only be fused one way at a time",
    "SPECIES_KYUREM_WHITE":        "both Kyurem fusions share one fusion storage slot",
    "SPECIES_KYUREM_BLACK":        "both Kyurem fusions share one fusion storage slot",
    "SPECIES_CALYREX_ICE":         "both Calyrex fusions share one fusion storage slot",
    "SPECIES_CALYREX_SHADOW":      "both Calyrex fusions share one fusion storage slot",
}


def pool_overlap(audit):
    """Pool entries that another obtainable Pokemon also turns into."""
    pool = set(audit.mirage)
    out = {}
    for name, info in audit.species.items():
        if name not in audit.how:
            continue
        for _, _, target, _ in info["evolutions"]:
            if target in pool and target != name:
                out.setdefault(target, "evolves from " + name[8:])
        if info["eggGroups"] and "NO_EGGS_DISCOVERED" not in info["eggGroups"]:
            egg = audit.egg_species(name)
            if egg in pool and egg != name:
                out.setdefault(egg, "bred from " + name[8:])
    for _, a, b, result in audit.fusions:
        if result in pool and a in audit.how and b in audit.how:
            out.setdefault(result, "fused from " + a[8:] + " and " + b[8:])
    return {k: v for k, v in out.items() if k not in POOL_DUPES_ALLOWED}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--verbose", action="store_true", help="say how each form is reached")
    parser.add_argument("--json", help="also write the report to this file")
    args = parser.parse_args()

    audit = Audit()
    audit.run()

    missing, totems, found = [], [], []
    for name in audit.order:
        if not audit.storable(name):
            continue
        if "isTotem" in audit.species[name]["flags"]:
            totems.append(name)
        elif name in audit.how:
            found.append(name)
        else:
            missing.append(name)

    print(f"{len(found)} storable species and forms are obtainable, {len(missing)} are not.")
    for name in missing:
        reasons = sorted(set(audit.blocked.get(name, []))) or ["no source"]
        print(f"  {name[8:]:34} {'; '.join(reasons)}")
    if totems:
        print(f"\nTotem Pokemon (size variants, not required): {', '.join(n[8:] for n in totems)}")
    if args.verbose:
        print()
        for name in found:
            print(f"  {name[8:]:34} {audit.how[name]}")
    overlap = pool_overlap(audit)
    if overlap:
        print()
        print(str(len(overlap)) + " Mirage Island entries the player can already make:")
        for name, how in sorted(overlap.items()):
            print("  " + name[8:].ljust(34) + " " + how)
        print("  Give each one a home the lottery does not duplicate, or record why it")
        print("  has to stay in POOL_DUPES_ALLOWED.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"missing": missing, "how": audit.how, "poolOverlap": overlap,
                       "blocked": {k: sorted(set(v)) for k, v in audit.blocked.items()}}, f, indent=1)
    return 1 if missing or overlap else 0


if __name__ == "__main__":
    sys.exit(main())
