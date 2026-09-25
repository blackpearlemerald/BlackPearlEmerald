"""Parse trainers.party (+ _frlg) into a JSON map keyed by TRAINER_X.

Showdown-style format documented at the top of trainers.party. Read-only.
"""
import os
import re

import common as C

HEADER_RE = re.compile(r"^===\s*(TRAINER_\w+)\s*===\s*$")
# first line of a mon block: "[Nick (]Species[)] [(M|F)] [@ Item]"
SPECIES_LINE_RE = re.compile(
    r"^(?P<lead>.*?)(?:\s*@\s*(?P<item>.+))?$")


def _parse_species_line(line):
    item = None
    if "@" in line:
        line, item = line.split("@", 1)
        item = item.strip()
    line = line.strip()
    gender = None
    m = re.search(r"\((M|F)\)\s*$", line)
    if m:
        gender = m.group(1)
        line = line[:m.start()].strip()
    # Nickname (Species) form -> take the parenthesised species
    m = re.search(r"\(([^)]+)\)\s*$", line)
    if m:
        species = m.group(1).strip()
    else:
        species = line
    return species, item, gender


def _flush_mon(block):
    if not block:
        return None
    species, item, gender = _parse_species_line(block[0])
    mon = {"species": species}
    if item:
        mon["item"] = item
    if gender:
        mon["gender"] = gender
    mon["level"] = 100
    moves = []
    for ln in block[1:]:
        ln = ln.strip()
        if ln.startswith("- "):
            moves.append(ln[2:].strip())
        elif ln.lower().startswith("level:"):
            try:
                mon["level"] = int(ln.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif ln.lower().startswith("standard level:"):
            try:
                mon["standardLevel"] = int(ln.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif ln.lower().startswith("ability:"):
            mon["ability"] = ln.split(":", 1)[1].strip()
        elif ln.lower().startswith("tera type:"):
            mon["tera"] = ln.split(":", 1)[1].strip()
        elif ln.lower().startswith(("evs:", "ivs:")):
            key, values = ln.split(":", 1)
            mon[key.lower()] = {stat.lower(): int(value) for value, stat in re.findall(r"(\d+)\s+(HP|Atk|Def|SpA|SpD|Spe)", values, re.I)}
        elif ln.endswith("Nature"):
            mon["nature"] = ln.rsplit(" ", 1)[0].strip()
    if moves:
        mon["moves"] = moves
    return mon


def parse_file(path, out):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    cur = None           # current trainer id
    meta = {}            # name/class/pic for current trainer
    party = []
    block = []           # current mon block lines
    in_header = False    # within the trainer metadata (before first mon)

    def commit_mon():
        m = _flush_mon(block)
        if m:
            party.append(m)
        block.clear()

    def commit_trainer():
        if cur:
            commit_mon()
            out[cur] = {
                "name": meta.get("Name", ""),
                "class": meta.get("Class", ""),
                "pic": meta.get("Pic", ""),
                "party": list(party),
            }

    for raw in lines:
        hm = HEADER_RE.match(raw)
        if hm:
            commit_trainer()
            cur = hm.group(1)
            meta = {}
            party = []
            block = []
            in_header = True
            continue
        if cur is None:
            continue
        line = raw.rstrip()
        if not line.strip():
            if in_header:
                in_header = False  # blank line ends header, starts mons
            else:
                commit_mon()       # blank line separates mons
            continue
        if in_header:
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
            continue
        block.append(line)
    commit_trainer()


def species_constant(name):
    """Species name as written in trainers.party -> SPECIES_X, like trainerproc's fprint_species."""
    if name.startswith("SPECIES_"):
        return name
    out, underscore = ["SPECIES_"], False
    for c in name:
        if c.isascii() and c.isalnum():
            out.append(("_" if underscore else "") + c.upper())
            underscore = False
        elif c in "'%’":
            pass
        elif c in "♂♀":
            out.append("_M" if c == "♂" else "_F")
            underscore = False
        elif c == "é":
            out.append(("_" if underscore else "") + "E")
            underscore = False
        else:
            underscore = True
    return "".join(out)


def _level_up_learnsets():
    """SPECIES_X -> [(level, MOVE_NAME)] in learnset order, plus MOVE_NAME -> display name."""
    import parse_pokemon as P
    learnsets = P.parse_level_up_learnsets()
    by_species = {}
    for path in sorted((P.REPO / "src" / "data" / "pokemon" / "species_info").glob("gen_*_families.h")):
        raw = P.read_file(path)
        for key, block in P.iter_species_decls(P.strip_c_comments(raw), P.collect_macros(raw)):
            m = re.search(r"\.levelUpLearnset\s*=\s*s(\w+)LevelUpLearnset", block)
            if m and m[1] in learnsets:
                by_species["SPECIES_" + key] = [(e["level"], e["move"]) for e in learnsets[m[1]]]
    species_h = P.read_file(P.REPO / "include" / "constants" / "species.h")
    aliases = dict(re.findall(r"^\s*(SPECIES_\w+)\s*=\s*(SPECIES_\w+)\s*,", species_h, re.M))
    aliases.update(re.findall(r"^#define\s+(SPECIES_\w+)\s+(SPECIES_\w+)\s*$", species_h, re.M))
    for alias, target in aliases.items():
        seen = {alias}
        while target in aliases and target not in seen:
            seen.add(target)
            target = aliases[target]
        if alias not in by_species and target in by_species:
            by_species[alias] = by_species[target]
    move_names = {key: move["name"] for key, move in P.parse_moves().items()}
    return by_species, move_names


def _normalize(name):
    """trainerproc's name match: letters and digits only, lowercased."""
    return re.sub(r"[^A-Za-z0-9]", "", name).lower()


def _name_index(names, aliases):
    """{_normalize(spelling): display name} for one kind of thing.

    `names` is {CONSTANT: display name}; `aliases` is {CONSTANT: CONSTANT}.
    Both the display name and the constant are accepted spellings, so a
    pre-Gen VI alias such as MOVE_FAINT_ATTACK resolves to "Feint Attack".
    """
    index = {}
    for key, name in names.items():
        index.setdefault(_normalize(name), name)
        index.setdefault(_normalize(key), name)
    for alias, target in aliases.items():
        seen = {alias}
        while target in aliases and target not in seen:
            seen.add(target)
            target = aliases[target]
        if target in names:
            index.setdefault(_normalize(alias), names[target])
    return index


def _constant_aliases(text, prefix):
    """{NAME: NAME} for the enum and #define aliases, without the prefix.

    Pre-Gen VI names are an enum member in the current source and a #define in
    the 1.0.1 source, and both spellings reach trainers.party.
    """
    aliases = dict(re.findall(
        r"^\s*%s(\w+)\s*=\s*%s(\w+)\s*,?\s*(?://.*)?$" % (prefix, prefix), text, re.M))
    aliases.update(re.findall(
        r"^#define\s+%s(\w+)\s+%s(\w+)\s*(?://.*)?$" % (prefix, prefix), text, re.M))
    return aliases


def canonical_names():
    """Display names for the moves, abilities and items trainers.party names.

    The party format spells names the way trainerproc accepts them, which drops
    punctuation ("Will O Wisp", "Kings Rock") and allows old constant aliases
    ("Faint Attack"). The site and the damage calculator need the name the game
    itself shows, so every authored name goes through these indexes.
    """
    import parse_pokemon as P
    moves = P.parse_moves()
    move_h = P.read_file(P.REPO / "include" / "constants" / "moves.h")
    abilities = P.parse_abilities()
    items_h = P.strip_c_comments(P.read_file(P.REPO / "src" / "data" / "items.h"))
    items = {key: name for key, name in re.findall(
        r"\[ITEM_(\w+)\]\s*=\s*\{.*?\.name\s*=\s*(?:ITEM_NAME|_)\(\s*\"([^\"]+)\"",
        items_h, re.DOTALL)}
    return {
        "moves": _name_index({k: m["name"] for k, m in moves.items()},
                             _constant_aliases(move_h, "MOVE_")),
        "ability": _name_index({k: a["name"] for k, a in abilities.items()}, {}),
        "item": _name_index(items, {}),
    }


def canonicalize_names(trainers, indexes=None):
    """Rewrite every authored move, ability and item to its in-game name.

    An older source that keeps one of these tables somewhere else parses as an
    empty index; its names are then left exactly as the source spells them.
    """
    indexes = indexes or canonical_names()
    unknown = set()

    def fix(kind, name):
        if not indexes[kind]:
            return name
        known = indexes[kind].get(_normalize(name))
        if known is None:
            unknown.add("%s %r" % (kind, name))
            return name
        return known

    for trainer in trainers.values():
        for mon in trainer["party"]:
            for key in ("moves", "standardMoves"):
                if mon.get(key):
                    mon[key] = [fix("moves", move) for move in mon[key]]
            for key in ("ability", "item"):
                if mon.get(key):
                    mon[key] = fix(key, mon[key])
    if unknown:
        raise ValueError("Trainer party names the game does not define: "
                         + ", ".join(sorted(unknown)))


def initial_moveset(learnset, level):
    """GiveBoxMonInitialMoveset: the last four distinct moves learned by `level`."""
    moves = []
    for learn_level, move in learnset:
        if learn_level > level:
            break
        if learn_level == 0 or move in moves:
            continue
        if len(moves) == 4:
            moves.pop(0)
        moves.append(move)
    return moves


def fill_default_moves(trainers, move_name=None):
    """Give every party Pokémon without moves the moveset the game gives it.

    CustomTrainerPartyAssignMoves() calls GiveMonInitialMoveset() when a trainer
    Pokémon lists no moves, so its moves follow its level. A Standard Level that
    changes the result adds "standardMoves".
    """
    learnsets, move_names = _level_up_learnsets()
    name = move_name or (lambda move: move_names.get(move, move.replace("_", " ").title()))
    missing = set()
    for trainer in trainers.values():
        for mon in trainer["party"]:
            if mon.get("moves"):
                continue
            learnset = learnsets.get(species_constant(mon["species"]))
            if learnset is None:
                missing.add(mon["species"])
                continue
            moves = [name(move) for move in initial_moveset(learnset, mon["level"])]
            mon["moves"] = moves
            standard = mon.get("standardLevel")
            if standard and standard != mon["level"]:
                standard_moves = [name(move) for move in initial_moveset(learnset, standard)]
                if standard_moves != moves:
                    mon["standardMoves"] = standard_moves
    if missing:
        raise ValueError("No level-up learnset for trainer species: " + ", ".join(sorted(missing)))


def build():
    out = {}
    if os.path.isfile(C.src("src", "data", "trainers.party")):
        parse_file(C.src("src", "data", "trainers.party"), out)
        parse_file(C.src("src", "data", "trainers_frlg.party"), out)
        fill_default_moves(out)
    else:
        out = build_legacy()
    canonicalize_names(out)
    return out


def build_legacy():
    """Import the pre-trainerproc C format used by the official 1.0.1 source."""
    with open(C.src("src/data/trainer_parties.h"), encoding="utf-8") as f:
        parties_text = f.read()
    with open(C.src("src/data/trainers.h"), encoding="utf-8") as f:
        trainers_text = f.read()
    pretty = lambda s: s.replace("_", " ").title()
    parties = {}
    for name, body in re.findall(r"(?:static )?const struct TrainerMon\w*\s+(\w+)\[\]\s*=\s*\{(.*?)\n\};", parties_text, re.S):
        party = []
        for mon_block in re.findall(r"\{\s*(\.\w+.*?)\n\s*\}(?:,|\s*$)", body, re.S):
            species = re.search(r"\.species\s*=\s*SPECIES_(\w+)", mon_block)
            level = re.search(r"\.lvl\s*=\s*(\d+)", mon_block)
            if not species or not level:
                raise ValueError(f"Cannot parse legacy trainer party {name}")
            mon = {"species": pretty(species[1]), "level": int(level[1])}
            for source_field, key in (("ev", "evs"), ("iv", "ivs")):
                stats = {}
                macro = re.search(r"\." + source_field + r"\s*=\s*TRAINER_PARTY_\w+\(([^)]+)\)", mon_block)
                if macro:
                    values = [int(value.strip()) for value in macro[1].split(",")]
                    if len(values) != 6:
                        raise ValueError(f"Invalid legacy trainer stats in {name}")
                    stats.update(zip(("hp", "atk", "def", "spe", "spa", "spd"), values))
                for suffix, stat in (("HP", "hp"), ("Attack", "atk"), ("Defense", "def"), ("Speed", "spe"), ("SpAttack", "spa"), ("SpDefense", "spd")):
                    value = re.search(r"\." + source_field + suffix + r"\s*=\s*(\d+)", mon_block)
                    if value:
                        stats[stat] = int(value[1])
                if stats:
                    mon[key] = stats
            for field, prefix, key in (("heldItem", "ITEM_", "item"), ("ability", "ABILITY_", "ability"), ("nature", "NATURE_", "nature")):
                m = re.search(r"\." + field + r"\s*=\s*" + prefix + r"(\w+)", mon_block)
                if m and m[1] != "NONE":
                    mon[key] = pretty(m[1])
            moves = re.search(r"\.moves\s*=\s*\{([^}]+)\}", mon_block)
            mon["moves"] = [pretty(m) for m in re.findall(r"MOVE_(\w+)", moves[1] if moves else "") if m != "NONE"]
            party.append(mon)
        parties[name] = party
    out = {}
    for key, body in re.findall(r"\[(TRAINER_\w+)\]\s*=\s*\{(.*?)\n\s*\},", trainers_text, re.S):
        name = re.search(r'\.trainerName\s*=\s*_\("([^"]*)"\)', body)
        cls = re.search(r"\.trainerClass\s*=\s*(TRAINER_CLASS_\w+)", body)
        pic = re.search(r"\.trainerPic\s*=\s*(TRAINER_PIC_\w+)", body)
        party = re.search(r"\.party\s*=\s*TRAINER_PARTY\((\w+)\)", body)
        if party and party[1] not in parties:
            raise ValueError(f"Missing legacy party {party[1]}")
        out[key] = {"name": name[1] if name else "", "class": pretty(cls[1].removeprefix("TRAINER_CLASS_")) if cls else "",
                    "pic": pretty(pic[1].removeprefix("TRAINER_PIC_")) if pic else "", "party": parties.get(party[1], []) if party else []}
    if not out or not parties:
        raise ValueError("No legacy trainer data could be imported.")
    fill_default_moves(out, pretty)
    return out


def main():
    C.ensure_dirs()
    out = build()
    C.write_json(os.path.join(C.SITE_DATA, "trainers.json"), out)
    total_mons = sum(len(t["party"]) for t in out.values())
    print(f"Parsed {len(out)} trainers, {total_mons} party mons")
    return out


if __name__ == "__main__":
    main()
