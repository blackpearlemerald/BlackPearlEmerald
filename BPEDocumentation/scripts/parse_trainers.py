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
    parse_file(C.src("src", "data", "trainers.party"), out)
    parse_file(C.src("src", "data", "trainers_frlg.party"), out)
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
