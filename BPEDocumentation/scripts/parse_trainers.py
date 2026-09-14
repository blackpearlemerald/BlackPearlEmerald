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


def build():
    out = {}
    if not os.path.isfile(C.src("src", "data", "trainers.party")):
        return build_legacy()
    parse_file(C.src("src", "data", "trainers.party"), out)
    parse_file(C.src("src", "data", "trainers_frlg.party"), out)
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
