"""Regenerate BPE's per-mode trainer levels and rematch teams.

Two passes, both rewriting src/data/trainers.party in place:

1. Rematch teams. Every rematch tier in gRematchTable gets a copy of that
   trainer's first-battle team, REMATCH_STEP levels higher per tier (the step
   shrinks where the full step would pass level 100). Rematch tiers get no
   Standard Level, so they fight at the same level in both modes.

2. Standard Level. Nuzlocke mode keeps each trainer's authored Level. Standard
   mode plays without level caps, so its trainers ramp smoothly instead of
   sitting on the badge cap: each trainer is assigned to the badge stretch its
   ace level belongs to, ordered within that stretch by walking distance from
   the previous gym's town over the game's own map graph, then interpolated
   from the previous cap up to the new one. Gym leaders and the Elite Four are
   pinned exactly on their cap.

Both passes are idempotent. Run from the repository root:

    python BPETools/generate_trainer_levels.py [--dry-run]

Rebuild afterwards, and re-export the website data with
BPEDocumentation/scripts/parse_trainers.py so the Trainers page matches.
"""
import argparse
import collections
import io
import json
import os
import re

PARTY = "src/data/trainers.party"
BATTLE_SETUP = "src/battle_setup.c"
MAPS = "data/maps"

# (cap, previous cap, the town the stretch starts from)
STRETCHES = [(15, 5, "LittlerootTown"), (24, 15, "RustboroCity"), (33, 24, "DewfordTown"),
             (42, 33, "MauvilleCity"), (51, 42, "LavaridgeTown"), (60, 51, "PetalburgCity"),
             (69, 60, "FortreeCity"), (78, 69, "MossdeepCity"), (90, 78, "SootopolisCity")]
CAPS = [cap for cap, _, _ in STRETCHES]
# Side content that is not part of a gym stretch keeps its authored levels.
SKIP_MAPS = ("TrickHousePuzzle", "BattleFrontier", "BattleTent", "SecretBase", "BattlePyramid")
LEADERS = ("TRAINER_ROXANNE_1", "TRAINER_BRAWLY_1", "TRAINER_WATTSON_1", "TRAINER_FLANNERY_1",
           "TRAINER_NORMAN_1", "TRAINER_WINONA_1", "TRAINER_TATE_AND_LIZA_1", "TRAINER_JUAN_1",
           "TRAINER_SIDNEY", "TRAINER_PHOEBE", "TRAINER_GLACIA", "TRAINER_DRAKE", "TRAINER_WALLACE")
REMATCH_STEP = 5
# Emerald keeps each rival fight as six trainers (the player's gender x their
# starter). BPE's rival fields the same team in all six, so they are one fight
# and share one Standard Level.
RIVAL_COPY = re.compile(r"TRAINER_(?:MAY|BRENDAN)_(.+)_(?:MUDKIP|TORCHIC|TREECKO)$")


def fight(trainer):
    """The fight a trainer id stands for: the rival's copies share one."""
    match = RIVAL_COPY.match(trainer)
    return "RIVAL_" + match.group(1) if match else trainer


def read(path):
    return io.open(path, encoding="utf-8", errors="replace", newline="").read()


def split_party(text):
    """Split trainers.party into [pre, header, body, header, body, ...]."""
    return re.split(r"(?m)^(=== TRAINER_[A-Z0-9_]+ ===)", text)


def rematch_chains():
    """[(first battle id, [tier ids])] taken from gRematchTable.

    The table repeats an id to pad short chains, and the Elite Four repeat their
    own id in every slot, so an id that is also a first battle is never a tier.
    """
    src = read(BATTLE_SETUP)
    entries, firsts = [], set()
    for match in re.finditer(r"REMATCH\(([^)]*)\)", src):
        ids = [x.strip() for x in match.group(1).split(",") if x.strip().startswith("TRAINER_")]
        if ids:
            firsts.add(ids[0])
            entries.append((ids[0], list(dict.fromkeys(i for i in ids[1:5] if i != ids[0]))))
    return [(first, [t for t in tiers if t not in firsts]) for first, tiers in entries]


def placements():
    """TRAINER_ID -> the first map whose scripts reference it."""
    found = {}
    for folder in sorted(os.listdir(MAPS)):
        path = os.path.join(MAPS, folder, "scripts.inc")
        if os.path.isfile(path):
            for trainer in sorted(set(re.findall(r"\b(TRAINER_[A-Z0-9_]+)\b", read(path)))):
                found.setdefault(trainer, folder)
    return found


def map_distances():
    """Walking distance in map hops (connections and warps) from each stretch anchor."""
    folders, graph = {}, collections.defaultdict(set)
    for folder in sorted(os.listdir(MAPS)):
        path = os.path.join(MAPS, folder, "map.json")
        if os.path.isfile(path):
            folders[folder] = json.loads(read(path))
    ids = {data["id"]: folder for folder, data in folders.items()}
    for folder, data in folders.items():
        neighbours = [c.get("map") for c in data.get("connections") or []]
        neighbours += [w.get("dest_map") for w in data.get("warp_events") or []]
        for neighbour in neighbours:
            target = ids.get(neighbour)
            if target:
                graph[folder].add(target)
                graph[target].add(folder)

    result = {}
    for _, _, anchor in STRETCHES:
        distance, queue = {anchor: 0}, collections.deque([anchor])
        while queue:
            current = queue.popleft()
            for nxt in graph[current]:
                if nxt not in distance:
                    distance[nxt] = distance[current] + 1
                    queue.append(nxt)
        result[anchor] = distance
    return result


def apply_rematch_teams(parts):
    index = {parts[i][4:-4]: i for i in range(1, len(parts), 2)}
    written = 0
    for first, tiers in rematch_chains():
        tiers = [t for t in tiers if t in index]
        if first not in index or not tiers:
            continue
        source = re.sub(r"(?m)^Standard Level: \d+\n", "", parts[index[first] + 1])
        blocks = [b.strip() for b in re.split(r"\n\s*\n", source)
                  if re.search(r"(?m)^Level: \d+", b)]
        if not blocks:
            continue
        ace = max(int(x) for x in re.findall(r"(?m)^Level: (\d+)", "\n\n".join(blocks)))
        step = REMATCH_STEP
        if ace + step * len(tiers) > 100:
            step = max(1, (100 - ace) // len(tiers))
        for tier_number, tier in enumerate(tiers, start=1):
            shift = step * tier_number
            raised = [re.sub(r"(?m)^Level: (\d+)$",
                             lambda m: "Level: %d" % min(100, int(m.group(1)) + shift), block)
                      for block in blocks]
            body = parts[index[tier] + 1]
            head = body[:body.index("\n", body.index("AI:")) + 1]
            parts[index[tier] + 1] = head + "\n" + "\n\n".join(raised) + "\n\n"
            written += 1
    return written


def apply_standard_levels(parts):
    rematch = {tier for _, tiers in rematch_chains() for tier in tiers}
    placed = placements()
    distances = map_distances()

    levels = {}
    for i in range(1, len(parts), 2):
        parts[i + 1] = re.sub(r"(?m)^Standard Level: \d+\n", "", parts[i + 1])
        found = [int(x) for x in re.findall(r"(?m)^Level: (\d+)", parts[i + 1])]
        if found:
            levels[parts[i][4:-4]] = found

    buckets = collections.defaultdict(list)
    copies = collections.defaultdict(list)
    for trainer, folder in sorted(placed.items()):
        if trainer in rematch or trainer not in levels or any(s in folder for s in SKIP_MAPS):
            continue
        copies[fight(trainer)].append(trainer)
        if len(copies[fight(trainer)]) > 1:
            continue
        ace = max(levels[trainer])
        cap = next((c for c in CAPS if ace <= c), None)
        if cap:
            buckets[cap].append((trainer, folder, ace))

    plan = {}
    for cap, previous, anchor in STRETCHES:
        distance = distances[anchor]
        rows = buckets[cap]
        others = sorted((r for r in rows if r[0] not in LEADERS),
                        key=lambda r: (1 if "_Gym" in r[1] else 0,
                                       distance.get(r[1], 99), r[2], r[0]))
        for position, (trainer, _, _) in enumerate(others):
            span = cap - 1 - previous
            plan[trainer] = previous + round(span * position / max(len(others) - 1, 1))
        for trainer, _, _ in rows:
            if trainer in LEADERS:
                plan[trainer] = cap
    for trainer in list(plan):
        for copy in copies[fight(trainer)]:
            plan[copy] = plan[trainer]

    for i in range(1, len(parts), 2):
        trainer = parts[i][4:-4]
        if trainer not in plan:
            continue
        ace, target = max(levels[trainer]), plan[trainer]

        def shift(match, ace=ace, target=target):
            level = int(match.group(1))
            return "Level: %d\nStandard Level: %d\n" % (
                level, max(2, min(100, target - (ace - level))))

        parts[i + 1] = re.sub(r"(?m)^Level: (\d+)\n", shift, parts[i + 1])
    return len(plan)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    original = read(PARTY)
    parts = split_party(original)
    rematches = apply_rematch_teams(parts)
    standard = apply_standard_levels(parts)
    updated = "".join(parts)

    print("rematch teams rewritten: %d" % rematches)
    print("trainers given a Standard Level: %d" % standard)
    if args.dry_run:
        print("dry run: %s" % ("unchanged" if updated == original else "would change"))
    else:
        io.open(PARTY, "w", encoding="utf-8", newline="").write(updated)
        print("wrote %s%s" % (PARTY, "" if updated != original else " (unchanged)"))


if __name__ == "__main__":
    main()
