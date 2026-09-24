"""Build site/js/data/world.json: map positions, trainers, items, warp links.

Layout strategy
---------------
* The map connection graph is split into connected components. Within a
  component, maps are positioned by BFS accumulation of connection offsets
  (this reproduces the contiguous Hoenn overworld).
* The component containing Littleroot Town is the "overworld" and is placed at
  the world origin.
* Every other component (interiors, caves, dungeon floors - each usually a
  single map) is placed as a floating "island" anchored near a warp that leads
  into it from an already-placed map, packed to avoid overlap. A warpLink is
  recorded so the frontend can draw a connector line.

Read-only against the game source.
"""
import os
import re
import sys
from collections import defaultdict, deque

import common as C
import parse_trainers
import pokemon_sprites
import sprites

TILE = 16  # px per metatile block
PAD = 24   # px gap between islands when packing

TRAINER_TOK_RE = re.compile(r"\bTRAINER_[A-Z0-9_]+\b")
PURCHASE_RE    = re.compile(r"\b(?:removecoins|removemoney)\b")
GIVEITEM_RE    = re.compile(r"\bgiveitem\s+(ITEM_\w+)(?:\s*,\s*(\d+))?")
ADDITEM_RE     = re.compile(r"\badditem\s+(ITEM_\w+)(?:\s*,\s*(\d+))?")

# Fishing's 10 slots are split across the three rods (pokeemerald convention).
FISHING_RODS = {"old": (0, 2), "good": (2, 5), "super": (5, 10)}


# --------------------------------------------------------------------------- #
# Wild encounters
# --------------------------------------------------------------------------- #
def _aggregate(mons, rates):
    """Sum per-slot rates by species; track level range. rates must align."""
    agg = {}
    order = []
    for i, mon in enumerate(mons):
        if i >= len(rates):
            break
        sp = mon["species"]
        pct = rates[i]
        if sp not in agg:
            agg[sp] = {"species": sp, "pct": 0,
                       "min": mon["min_level"], "max": mon["max_level"]}
            order.append(sp)
        a = agg[sp]
        a["pct"] += pct
        a["min"] = min(a["min"], mon["min_level"])
        a["max"] = max(a["max"], mon["max_level"])
    return [agg[s] for s in order]


def build_encounters():
    """mapId -> {land, water, rock_smash, fishing:{old,good,super}}."""
    data = C.load_json(C.src("src", "data", "wild_encounters.json"))
    out = defaultdict(dict)
    for group in data["wild_encounter_groups"]:
        if not group.get("for_maps"):
            continue
        # field type -> slot rate list
        rates = {f["type"]: f["encounter_rates"] for f in group["fields"]}
        for enc in group["encounters"]:
            mid = enc["map"]
            for field in ("land_mons", "water_mons", "rock_smash_mons"):
                if field in enc and field in rates:
                    key = field.replace("_mons", "")
                    out[mid][key] = {
                        "rate": enc[field].get("encounter_rate"),
                        "mons": _aggregate(enc[field]["mons"], rates[field])}
            if "fishing_mons" in enc and "fishing_mons" in rates:
                fr = rates["fishing_mons"]
                fm = enc["fishing_mons"]["mons"]
                rods = {}
                for rod, (a, b) in FISHING_RODS.items():
                    sub = _aggregate(fm[a:b], fr[a:b])
                    if sub:
                        rods[rod] = sub
                if rods:
                    out[mid]["fishing"] = rods
    return out


# Legendary Lottery Island: Mirage Island (Route 130) hosts a rotating,
# post-Champion legendary encounter. The pool lives in the game source as
# sIslandLegendaryPool[] so the site stays in sync with a single source of
# truth. Level is fixed at ISLAND_LEGENDARY_LEVEL in the same file.
def read_island_legendary_pool():
    """(level, [SPECIES_* ...]) from src/field_specials.c, or (70, [])."""
    txt = open(C.src("src", "field_specials.c"), encoding="utf-8").read()
    lvl_m = re.search(r"#define\s+ISLAND_LEGENDARY_LEVEL\s+(\d+)", txt)
    level = int(lvl_m.group(1)) if lvl_m else 70
    arr = re.search(r"sIslandLegendaryPool\[\]\s*=\s*\{(.*?)\};", txt, re.S)
    species = re.findall(r"SPECIES_[A-Z0-9_]+", arr.group(1)) if arr else []
    return level, species


# --------------------------------------------------------------------------- #
# Source loading
# --------------------------------------------------------------------------- #
def load_layout_dims():
    """LAYOUT_ID -> (width_blocks, height_blocks, layout_name)."""
    data = C.load_json(C.src("data", "layouts", "layouts.json"))["layouts"]
    dims = {}
    for l in data:
        dims[l["id"]] = (l["width"], l["height"], l["name"])
    return dims


def parse_scripts_inc(path):
    """label -> body text (up to next top-level label)."""
    if not os.path.isfile(path):
        return {}
    out = {}
    cur = None
    buf = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^(\w+)::", line)
            if m:
                if cur:
                    out[cur] = "".join(buf)
                cur = m.group(1)
                buf = []
            else:
                buf.append(line)
    if cur:
        out[cur] = "".join(buf)

    # Most executable scripts use global ``::`` labels. A few map files also
    # expose callable script labels with a single ``:`` (while text and
    # movement labels use that form routinely). Index those labels in a
    # second pass without changing the global-script bodies above; this keeps
    # the normal fall-through behavior while allowing goto/call targets such
    # as Dewford's retry reward script to resolve.
    cur = None
    buf = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^(\w+)::?", line)
            if m:
                if cur:
                    out.setdefault(cur, "".join(buf))
                cur = m.group(1) if line.startswith(m.group(1) + ":") \
                    and not line.startswith(m.group(1) + "::") else None
                buf = []
            elif cur:
                buf.append(line)
    if cur:
        out.setdefault(cur, "".join(buf))
    return out


def load_shared_scripts():
    """Load globally included script labels used by multiple maps."""
    out = {}
    root = C.src("data", "scripts")
    for dirpath, _, filenames in os.walk(root):
        for filename in sorted(filenames):
            if filename.endswith(".inc"):
                out.update(parse_scripts_inc(os.path.join(dirpath, filename)))
    return out


def resolve_trainer(script_label, scripts, _seen=None):
    """Resolve an object's script to the TRAINER_* it battles, if any.

    Keys on the `trainerbattle*` macro (and `vsseeker_rematchid`, which names a
    rematchable trainer directly) so it works for both line-of-sight trainers
    and talk-to-battle NPCs (gym leaders, rivals) whose trainer_type is NONE,
    without false-positiving ordinary NPCs. Battle scripts are often reached via
    goto/call or switch/case, so all referenced local labels are followed.
    """
    return find_battle(script_label, scripts, _seen)[0]


def find_battle(script_label, scripts, _seen=None):
    """(TRAINER_*, label of the script holding the battle), or (None, None)."""
    battles = find_battles(script_label, scripts, _seen)
    return battles[0][:2] if battles else (None, None)


def find_battles(script_label, scripts, _seen=None, _path=()):
    """Every battle a script can start, as (TRAINER_*, battle label, path).

    `path` is the list of labels from `script_label` to the battle label. A
    script that battles directly stops there; otherwise every branch is
    followed, so the rival's per-starter variants are all found.
    """
    if not script_label:
        return []
    if _seen is None:
        _seen = set()
    if script_label in _seen or len(_seen) > 64:
        return []
    _seen.add(script_label)
    body = scripts.get(script_label)
    if body is None:
        return []
    path = list(_path) + [script_label]
    m = re.search(r"\btrainerbattle\w*[ \t]+([^\n]*)", body)
    if m:
        tid = opponent_from_args(m.group(1))
        if tid:
            return [(tid, script_label, path)]
    m = re.search(r"\bvsseeker_rematchid\s+(TRAINER_[A-Z0-9_]+)", body)
    if m:
        return [(m.group(1), script_label, path)]
    # follow control flow into other local scripts: goto/call/case and their
    # conditional variants (goto_if_eq, call_if_set, ...). The branch target is
    # the last label argument on the line.
    found = []
    for line in body.splitlines():
        if not re.match(r"\s*(?:goto|call|case)\w*\b", line):
            continue
        toks = re.findall(r"[A-Za-z_]\w*", line)
        if toks and toks[-1] in scripts:
            found += find_battles(toks[-1], scripts, _seen, path)
    return found


def battle_anchor(path, scripts, objects_by_local_id):
    """The object a trigger-tile battle is fought against: the last object
    its scripts name before branching into the battle (the Route 110 rival
    walking up to the player), or None."""
    for i in range(len(path) - 1, -1, -1):
        body = scripts.get(path[i], "")
        if i + 1 < len(path):
            m = re.search(r"^\s*(?:goto|call|case)\w*\b[^\n]*\b%s\s*$"
                          % re.escape(path[i + 1]), body, re.M)
            body = body[:m.start()] if m else body
        for lid in reversed(LOCALID_RE.findall(body)):
            if lid in objects_by_local_id:
                return objects_by_local_id[lid]
    return None


# Captures the whole argument list after a trainerbattle* macro. The first
# TRAINER_* token can be a battle-TYPE constant (e.g. the raw
# `trainerbattle TRAINER_BATTLE_CONTINUE_SCRIPT, LOCALID_X, TRAINER_X, ...`
# form used by the Lavaridge gym), so the real opponent must be picked by
# skipping TRAINER_BATTLE_* types and the TRAINER_NONE rematch placeholder.
TRAINERBATTLE_RE = re.compile(r"\btrainerbattle\w*[ \t]+([^\n]*)")

def opponent_from_args(args):
    for tok in re.findall(r"\bTRAINER_[A-Z0-9_]+\b", args):
        if tok.startswith("TRAINER_BATTLE_") or tok == "TRAINER_NONE":
            continue
        return tok
    return None
LOCALID_RE = re.compile(r"\bLOCALID_[A-Z0-9_]+")

# direction keyword -> facing; the first one found in the movement_type wins
_DIR_KEYS = [("DOWN", "down"), ("SOUTH", "down"), ("UP", "up"),
             ("NORTH", "up"), ("LEFT", "left"), ("WEST", "left"),
             ("RIGHT", "right"), ("EAST", "right")]


def facing_dir(movement_type):
    """Facing direction implied by an object's movement_type (default down)."""
    s = (movement_type or "").upper()
    best, best_pos = "down", None
    for key, d in _DIR_KEYS:
        p = s.find(key)
        if p != -1 and (best_pos is None or p < best_pos):
            best, best_pos = d, p
    return best


def _name_tokens(symbol):
    drop = {"TRAINER", "LOCALID", "OBJ", "EVENT", "GFX", ""}
    return {t for t in symbol.split("_") if t not in drop and not t.isdigit()}


ADDOBJECT_RE = re.compile(r"\baddobject[ \t]+(LOCALID_[A-Z0-9_]+)")
APPLYMOVEMENT_RE = re.compile(
    r"\bapplymovement[ \t]+(LOCALID_[A-Z0-9_]+)[ \t]*,[ \t]*(\w+)")
_STEP_DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def spawned_objects(body):
    """LOCALIDs a script brings onto the map with `addobject`."""
    return set(ADDOBJECT_RE.findall(body or ""))


def walk_to_battle(ev, lid, body, pos, scripts):
    """Replay the `applymovement` steps a script gives object `lid` before
    text position `pos`. Returns (x, y, facing) where the object stands then.

    Cutscene opponents are spawned hidden on a door or stair tile and walk to
    where they are fought, so their map.json position is not where the player
    meets them.
    """
    x, y = int(ev.get("x", 0)), int(ev.get("y", 0))
    facing = facing_dir(ev.get("movement_type"))
    for m in APPLYMOVEMENT_RE.finditer(body[:pos]):
        if m.group(1) != lid:
            continue
        locked = False
        for step in re.findall(r"^\s*(\w+)", scripts.get(m.group(2), ""),
                               re.M):
            if step == "step_end":
                break
            if step == "lock_facing_direction":
                locked = True
            elif step == "unlock_facing_direction":
                locked = False
            d = step.rsplit("_", 1)[-1]
            if d not in _STEP_DIRS:
                continue
            if step.startswith(("walk_", "slide_", "player_run_",
                                "ride_water_current_", "jump_")) \
                    and "_in_place_" not in step:
                dist = 2 if step.startswith("jump_2_") else 1
                x += _STEP_DIRS[d][0] * dist
                y += _STEP_DIRS[d][1] * dist
            if not locked:
                facing = d
    return x, y, facing


def scripted_battles(object_events, scripts, claimed):
    """Find trainer battles that live in map/coord scripts rather than on an
    object (e.g. the Petalburg Woods Aqua grunt, the Champions Room champion),
    and tie each to the object that represents the trainer.

    Tier 1: the LOCALID textually nearest the battle line in the same script.
    Tier 2 (champion-style, where the battle script has no LOCALID): the
    unclaimed object whose LOCALID shares the most name tokens with the trainer.

    An opponent the same script spawns with `addobject` (the Oceanic Museum
    grunts) is placed where its movements take it before the battle.

    Returns list of {x, y, trainerId, gfx}. `claimed` is the set of trainer ids
    already placed from object scripts (skipped here).
    """
    by_localid = {}
    for ev in object_events:
        lid = ev.get("local_id")
        if lid and lid not in ("0", 0):
            by_localid[lid] = ev

    out = []
    used = set()

    def place(lid, tid, body=None, pos=0):
        ev = by_localid[lid]
        if body is not None and lid in spawned_objects(body):
            x, y, facing = walk_to_battle(ev, lid, body, pos, scripts)
        else:
            x, y = int(ev.get("x", 0)), int(ev.get("y", 0))
            facing = facing_dir(ev.get("movement_type"))
        out.append({"x": x, "y": y, "trainerId": tid,
                    "gfx": ev.get("graphics_id"), "dir": facing})
        used.add(lid)
        claimed.add(tid)

    # Tier 1: nearest LOCALID in the same script body
    unmatched = []  # (tid,) deferred to tier 2
    for body in scripts.values():
        for m in TRAINERBATTLE_RE.finditer(body):
            tid = opponent_from_args(m.group(1))
            if tid is None or tid in claimed:
                continue
            pos = m.start()
            best, best_d = None, None
            for lm in LOCALID_RE.finditer(body):
                lid = lm.group(0)
                if lid in by_localid and lid not in used:
                    d = abs(lm.start() - pos)
                    if best_d is None or d < best_d:
                        best, best_d = lid, d
            if best is not None:
                place(best, tid, body, pos)
            else:
                unmatched.append(tid)

    # Tier 2: token-overlap match for battles whose script had no LOCALID
    for tid in unmatched:
        if tid in claimed:
            continue
        tt = _name_tokens(tid)
        best, best_score = None, 0
        for lid in by_localid:
            if lid in used:
                continue
            score = len(tt & _name_tokens(lid))
            if score > best_score:
                best, best_score = lid, score
        if best is not None:
            place(best, tid)
    return out


# --------------------------------------------------------------------------- #
# Mart item lists
# --------------------------------------------------------------------------- #
def _mart_get_pokemart(body, subscripts):
    """Return the pokemart list label referenced in body, or via one goto."""
    pm = re.search(r"\bpokemart\s+(\w+)", body)
    if pm:
        return pm.group(1)
    for m in re.finditer(r"\bgoto\w*\s+(\w+)", body):
        t = m.group(1)
        if t in subscripts:
            pm2 = re.search(r"\bpokemart\s+(\w+)", subscripts[t])
            if pm2:
                return pm2.group(1)
    return None


# Plain-English trigger text for mart-expansion flags. BPE marts expand on
# story flags, not gym badges, so each known flag is mapped to a readable
# trigger. "set" = the tier reached when the flag IS set; "unset" = when it is
# not. Unknown flags fall back to a generic title-cased phrasing.
MART_FLAG_DESCRIPTIONS = {
    "FLAG_ADVENTURE_STARTED": {
        "set":   "After starting your adventure",
        "unset": "Before starting your adventure",
    },
    "FLAG_MET_DEVON_EMPLOYEE": {
        "set":   "After meeting the Devon researcher (Route 116)",
        "unset": "Before meeting the Devon researcher (Route 116)",
    },
    # This flag is never set anywhere in the game, so the expanded tier is
    # unreachable dead code (as in vanilla Emerald): the basic list is what
    # you always get.
    "FLAG_PETALBURG_MART_EXPANDED_ITEMS": {
        "set":   "Never unlocks (unused in-game)",
        "unset": "Always available",
    },
    # Verdanturf "Beans Shop" evolution-item mart expands with gym progress.
    "FLAG_BADGE03_GET": {
        "set":   "After the 3rd Gym Badge",
        "unset": "Before the 3rd Gym Badge",
    },
    "FLAG_BADGE04_GET": {
        "set":   "After the 4th Gym Badge",
        "unset": "Before the 4th Gym Badge",
    },
    "FLAG_SYS_GAME_CLEAR": {
        "set":   "After becoming Champion",
        "unset": "Before becoming Champion",
    },
}


def _describe_condition(flag, kind):
    """Human-readable trigger for a mart tier. kind is 'set' or 'unset'."""
    desc = MART_FLAG_DESCRIPTIONS.get(flag)
    if desc:
        return desc[kind]
    friendly = flag.replace("FLAG_", "").replace("_", " ").title()
    return f"After {friendly}" if kind == "set" else f"Before {friendly}"


def parse_mart_scripts(content):
    """Parse a mart scripts.inc; return [{condition, items}]."""
    # 1. Collect .2byte item lists
    item_lists = {}
    for m in re.finditer(
            r"^(\w+):\s*\n((?:[ \t]+\.2byte ITEM_\w+[ \t]*\n)+)",
            content, re.MULTILINE):
        items_in_block = re.findall(r"\.2byte (ITEM_\w+)", m.group(2))
        if items_in_block:
            item_lists[m.group(1)] = items_in_block

    if not item_lists:
        return []

    # 2. Build script labelâ†’body map
    scripts = {}
    for m in re.finditer(r"^(\w+)::(.*?)(?=^\w+::|\Z)",
                          content, re.MULTILINE | re.DOTALL):
        scripts[m.group(1)] = m.group(2)

    # 3. Locate the clerk (or first script with pokemart)
    clerk_label = next((l for l in scripts if "Clerk" in l), None)
    if not clerk_label:
        return [{"condition": "Always available", "items": v, "_rank": 0}
                for v in item_lists.values()]

    clerk_body = scripts[clerk_label]

    # 4. Conditional jumps in the clerk script â†’ derive conditions & ordering.
    # 'unset' tiers are the early/basic state (rank 0). 'set' tiers unlock later;
    # because the clerk checks the most-advanced flag FIRST, the set tiers are
    # reversed so the earliest-unlocking one gets the lowest rank. This keeps
    # multi-tier marts (e.g. the badge-gated Verdanturf "Beans Shop") in true
    # progression order, which the item-location picker relies on to report the
    # earliest tier an item becomes available.
    inventories, processed = [], set()
    first_flag = first_kind = None

    cond_tiers = []
    for m in re.finditer(
            r"\bgoto_if_(set|unset)\s+(FLAG_\w+),\s*(\w+)", clerk_body):
        kind, flag, target = m.group(1), m.group(2), m.group(3)
        list_label = _mart_get_pokemart(scripts.get(target, ""), scripts)
        if list_label and list_label in item_lists and list_label not in processed:
            if first_flag is None:
                first_flag, first_kind = flag, kind
            cond_tiers.append((kind, flag, list_label))
            processed.add(list_label)

    n_set = sum(1 for k, _, _ in cond_tiers if k == "set")
    seen_set = 0
    for kind, flag, list_label in cond_tiers:
        if kind == "set":
            rank = n_set - seen_set   # first-checked (most advanced) â†’ highest
            seen_set += 1
        else:
            rank = 0
        inventories.append({"condition": _describe_condition(flag, kind),
                            "items": item_lists[list_label],
                            "_rank": rank})

    # 5. Direct pokemart in clerk = fallthrough / opposite of the first jump
    direct_pm = re.search(r"\bpokemart\s+(\w+)", clerk_body)
    if direct_pm:
        ll = direct_pm.group(1)
        if ll in item_lists and ll not in processed:
            if first_flag is not None:
                opp = "unset" if first_kind == "set" else "set"
                cond, rank = _describe_condition(first_flag, opp), \
                             (1 if opp == "set" else 0)
            else:
                cond, rank = "Always available", 0
            inventories.append({"condition": cond, "items": item_lists[ll],
                                "_rank": rank})
            processed.add(ll)

    # 6. Catch any lists still unprocessed
    for label, items_in_block in item_lists.items():
        if label not in processed:
            inventories.append({"condition": "Always available",
                                 "items": items_in_block, "_rank": 0})

    inventories.sort(key=lambda inv: inv["_rank"])
    for inv in inventories:
        inv.pop("_rank", None)
    return inventories


def _spaced(ident):
    """`LilycoveCity_DepartmentStore_2F` â†’ `Lilycove City Department Store 2F`.

    The lookbehinds deliberately exclude digits so floor markers stay intact
    ("2F", not "2 F").
    """
    s = ident.replace("_", " ")
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)       # cityMart â†’ city Mart
    s = re.sub(r"(?<=[A-Z])(?=[A-Z](?!s\b)[a-z])", " ", s)  # TMClerk  â†’ TM Clerk, TMs stays
    s = re.sub(r"(?<=[a-z])(?=\d)", " ", s)          # Store2F  â†’ Store 2F
    return re.sub(r"\s+", " ", s).strip()


# `checktrainerflag TRAINER_X` immediately followed by `goto_if TRUE, <shop>` â€”
# the idiom for an NPC whose shop only opens once you have beaten them.
SHOP_TRAINER_GATE_RE = re.compile(
    r"\bchecktrainerflag\s+(TRAINER_[A-Z0-9_]+)\s*\n\s*goto_if\s+TRUE,\s*(\w+)")
SHOP_FLAG_GATE_RE = re.compile(r"\bgoto_if_(set|unset)\s+(FLAG_\w+),\s*(\w+)")


def parse_shop_scripts(content, trainer_names):
    """Parse `pokemart` vendors in a map that is not a dedicated PokÃ© Mart.

    Returns [{vendor, condition, items}] â€” one entry per vendor per tier.

    Unlike parse_mart_scripts this does not assume a single "Clerk": a map can
    hold several independent vendors (the Lilycove department-store floors, the
    Slateport market stalls, the two post-game NPCs outside the PokÃ©mon League).
    """
    item_lists = {}
    for m in re.finditer(
            r"^(\w+):\s*\n((?:[ \t]+\.2byte ITEM_\w+[ \t]*\n)+)",
            content, re.MULTILINE):
        items_in_block = re.findall(r"\.2byte (ITEM_\w+)", m.group(2))
        if items_in_block:
            item_lists[m.group(1)] = items_in_block
    if not item_lists:
        return []

    scripts = {}
    for m in re.finditer(r"^(\w+)::(.*?)(?=^\w+::|\Z)",
                          content, re.MULTILINE | re.DOTALL):
        scripts[m.group(1)] = m.group(2)

    # Which script opens which list.
    opens = {}
    for label, body in scripts.items():
        pm = re.search(r"\bpokemart\s+(\w+)", body)
        if pm and pm.group(1) in item_lists:
            opens[label] = pm.group(1)
    if not opens:
        return []

    # Which script gates which shop script, and under what condition. The
    # gater is the NPC the player actually talks to, so it names the vendor.
    gates = {}      # shop label -> (gater label, condition, vendor, trainer)
    gate_flags = {}  # gater label -> (flag, kind) of its first flag branch
    for label, body in scripts.items():
        for tflag, target in SHOP_TRAINER_GATE_RE.findall(body):
            if target in opens:
                # The trainer's own name beats a de-camel-cased script label
                # ("ChakaJacek", not "Chaka Jacek").
                who = (trainer_names.get(tflag) or {}).get("name")
                gates[target] = (label,
                                 f"After defeating {who}" if who
                                 else "After defeating this trainer", who,
                                 tflag)
        for kind, flag, target in SHOP_FLAG_GATE_RE.findall(body):
            if target in opens:
                gates[target] = (label, _describe_condition(flag, kind),
                                 None, None)
                gate_flags.setdefault(label, (flag, kind))

    vendors = {}     # entry label -> [{condition, items, _rank}]
    vendor_names = {}  # entry label -> preferred display name
    for shop_label, list_label in sorted(opens.items()):
        trainer = None
        if shop_label in gates:
            entry, condition, who, trainer = gates[shop_label]
            rank = 1
            if who:
                vendor_names[entry] = who
        elif shop_label in gate_flags:
            # This script opens a list AND branches to a gated one, so its own
            # list is the other side of that branch (the tiered-clerk shape).
            flag, kind = gate_flags[shop_label]
            opp = "unset" if kind == "set" else "set"
            entry, condition, rank = shop_label, _describe_condition(flag, opp), 0
        else:
            entry, condition, rank = shop_label, "Always available", 0
        inv = {"condition": condition, "items": item_lists[list_label],
               "_rank": rank}
        if trainer:
            # The trainer's map popup says they become this shop.
            inv["trainer"] = trainer
        vendors.setdefault(entry, []).append(inv)

    out = []
    for entry in sorted(vendors):
        # `Map_EventScript_EnergyGuru` â†’ `Energy Guru`
        vendor = vendor_names.get(entry) \
            or _spaced(re.sub(r"^.*?EventScript_", "", entry))
        for inv in sorted(vendors[entry], key=lambda i: i["_rank"]):
            inv.pop("_rank", None)
            inv["vendor"] = vendor
            out.append(inv)
    return out


SET_CONST_RE = re.compile(r"^\s*\.set\s+(\w+)\s*,\s*(\d+)", re.MULTILINE)
REMOVECOINS_RE = re.compile(r"\bremovecoins\s+(\w+)")
ADDDECOR_RE = re.compile(r"\badddecoration\s+(DECOR_\w+)")
ADDCOINS_RE = re.compile(r"\baddcoins\s+(\w+)")
REMOVEMONEY_RE = re.compile(r"\bremovemoney\s+(\w+)")


def parse_prize_scripts(content, object_events):
    """Parse coin-prize counters (the Game Corner) in one map's scripts.

    A prize is a script that takes coins (`removecoins`) and hands over an
    item or a decoration. Each prize is attributed to the NPC whose script
    reaches it, which names the counter. Returns (inventories, coin_sales):
    inventories are mart-style [{vendor, condition, items, prizes}] and
    coin_sales lists the coin bundles sold for money [{coins, price}].
    """
    if "removecoins" not in content and "addcoins" not in content:
        return [], []
    consts = {k: int(v) for k, v in SET_CONST_RE.findall(content)}

    def value(tok):
        return int(tok) if tok.isdigit() else consts.get(tok)

    scripts = {}
    for m in re.finditer(r"^(\w+)::(.*?)(?=^\w+::|\Z)",
                         content, re.MULTILINE | re.DOTALL):
        scripts[m.group(1)] = m.group(2)

    prizes, sales = {}, {}
    for label, body in scripts.items():
        cost = REMOVECOINS_RE.search(body)
        if cost and value(cost.group(1)):
            item = ADDITEM_RE.search(body)
            decor = ADDDECOR_RE.search(body)
            if item:
                prizes[label] = {"item": item.group(1),
                                 "coins": value(cost.group(1))}
            elif decor:
                prizes[label] = {"decoration": decor.group(1),
                                 "name": decor.group(1)[len("DECOR_"):]
                                 .replace("_", " ").title(),
                                 "coins": value(cost.group(1))}
        coins, money = ADDCOINS_RE.search(body), REMOVEMONEY_RE.search(body)
        if coins and money and value(coins.group(1)) and value(money.group(1)):
            sales[label] = {"coins": value(coins.group(1)),
                            "price": value(money.group(1))}
    if not prizes:
        return [], []

    def reachable(start):
        seen, todo = [], [start]
        while todo:
            label = todo.pop()
            if label in seen or label not in scripts:
                continue
            seen.append(label)
            todo.extend(script_refs(scripts[label], scripts))
        return seen

    inventories, claimed = [], set()
    for obj in object_events:
        entry = obj.get("script")
        if entry not in scripts:
            continue
        reach = set(reachable(entry))
        labels = [l for l in scripts
                  if l in prizes and l not in claimed and l in reach]
        if not labels:
            continue
        claimed.update(labels)
        found = sorted((prizes[l] for l in labels), key=lambda p: p["coins"])
        needs_case = "ITEM_COIN_CASE" in scripts[entry]
        inventories.append({
            "vendor": _spaced(re.sub(r"^.*?EventScript_", "", entry)),
            "condition": "Coin Case required" if needs_case
                         else "Always available",
            "items": [p["item"] for p in found if "item" in p],
            "prizes": found,
        })
    coin_sales = sorted(sales.values(), key=lambda s: s["coins"])
    return inventories, coin_sales


def parse_marts(trainer_names=None):
    """Return {map_id: {name, inventories}} for every map that sells items.

    Dedicated `*_Mart` maps keep the clerk-based tier parsing; every other map
    is scanned for NPC vendors (department stores, the Herb Shop, the Slateport
    stalls, post-game shop NPCs), which the mart-only scan used to miss.
    """
    trainer_names = trainer_names or {}
    result = {}
    maps_dir = C.src("data", "maps")
    for dirname in sorted(os.listdir(maps_dir)):
        scripts_path = os.path.join(maps_dir, dirname, "scripts.inc")
        map_json_path = os.path.join(maps_dir, dirname, "map.json")
        if not os.path.isfile(scripts_path):
            continue
        try:
            mj = C.load_json(map_json_path)
            map_id = mj.get("id")
        except Exception:
            continue
        if not map_id:
            continue
        with open(scripts_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if "mart" in dirname.lower():
            inventories = parse_mart_scripts(content)
            if inventories:
                # "OldaleTown_Mart" â†’ "Oldale Town"
                raw = dirname.replace("_Mart", "").replace("_UnusedMart", "").replace("_", " ")
                name = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
                result[map_id] = {"name": name, "inventories": inventories}
            continue

        prizes, coin_sales = parse_prize_scripts(
            content, mj.get("object_events", []))
        if prizes:
            result[map_id] = {"name": _spaced(dirname),
                              "title": f"{_spaced(dirname)} Prizes",
                              "kind": "prizes", "inventories": prizes}
            if coin_sales:
                result[map_id]["coinSales"] = coin_sales
            continue

        inventories = parse_shop_scripts(content, trainer_names)
        if inventories:
            name = _spaced(dirname)
            title = name if re.search(r"\b(Shop|Store|Mart|Market)\b", name) \
                else f"{name} Shops"
            result[map_id] = {"name": name, "title": title,
                               "inventories": inventories}
    return result


# --------------------------------------------------------------------------- #
# NPC care-package (gift) detection
# --------------------------------------------------------------------------- #
def script_refs(body, scripts):
    """Yield local/global script labels referenced by executable commands."""
    for line in body.splitlines():
        if not re.match(
                r"\s*(?:(?:goto|call|case)\w*|map_script(?:_2)?)\b", line):
            continue
        toks = re.findall(r"[A-Za-z_]\w*", line)
        if toks and toks[-1] in scripts:
            yield toks[-1]


def collect_gift_packages(script_label, scripts, _seen=None, _depth=0):
    """Return item reward groups reachable from an object's script.

    Each group is one script block and the items it grants directly. A block
    that grants at least two distinct items is a care package. A block that
    grants one item is an ordinary gift (HMs, TMs, key items); several such
    blocks behind one NPC can be mutually exclusive choices (bikes, fossils),
    so they are never merged into a care package. Callers are followed so
    story-event and Gym reward helper scripts are still found.
    """
    if not script_label:
        return []
    if _seen is None:
        _seen = set()
    if script_label in _seen or _depth > 24:
        return []
    _seen.add(script_label)
    body = scripts.get(script_label)
    if body is None:
        return []
    direct = []
    for m in GIVEITEM_RE.finditer(body):
        direct.append((m.group(1), int(m.group(2)) if m.group(2) else 1))
    for m in ADDITEM_RE.finditer(body):
        direct.append((m.group(1), int(m.group(2)) if m.group(2) else 1))
    if len({item for item, _ in direct}) == 1 and PURCHASE_RE.search(body):
        direct = []  # a coin/money purchase (Game Corner prizes), not a gift
    packages = [(script_label, direct)] if direct else []
    for target in script_refs(body, scripts):
        packages.extend(collect_gift_packages(
            target, scripts, _seen, _depth + 1))
    return packages


def merge_gift_packages(packages):
    """Merge reward groups for one NPC into (items, isCarePackage).

    Care-package items (from blocks granting 2+ distinct items) keep their
    previous merged quantities. Single-item gifts are added afterwards as
    ordinary gifts. Each item records whether it came from a care package.
    """
    care, single = {}, {}
    for _, package in packages:
        group = {}
        for item_id, qty in package:
            group[item_id] = group.get(item_id, 0) + qty
        target = care if len(group) >= 2 else single
        for item_id, qty in group.items():
            # Retry/alternate paths can reach the same reward; do not count
            # those as extra physical copies.
            target[item_id] = max(target.get(item_id, 0), qty)
    items = [{"item": it, "qty": qty, "carePackage": True}
             for it, qty in care.items()]
    items += [{"item": it, "qty": qty, "carePackage": False}
              for it, qty in single.items() if it not in care]
    return items, bool(care)


# --------------------------------------------------------------------------- #
# Static (scripted) wild encounters: legendaries, Snorlax, Kecleon, ...
# --------------------------------------------------------------------------- #
WILD_BATTLE_RE = re.compile(
    r"\b(?:setwildbattle|seteventmon)\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(\w+)")
# Every encounter under BPE's "pre-Elite Four legendary" rule reports its
# battle to TryRecordPreE4LegendaryCatch. Older releases set this variable
# instead, so both mark the group.
PREE4_RE = re.compile(r"\bsetvar\s+VAR_PREE4_LEGENDARY\b|\bspecial\s+TryRecordPreE4LegendaryCatch\b")
LEGENDARY_FLAG_RE = re.compile(
    r"\.is(?:Legendary|SubLegendary|RestrictedLegendary|Mythical)\s*=\s*TRUE"
    r"|SPECIES_FLAG_(?:LEGENDARY|MYTHICAL)")


def collect_static_encounters(script_label, scripts, _seen=None, _depth=0):
    """Return ({(species, level)}, sets_pre_e4, [visited labels]) reachable
    from a script through goto/call/case branches."""
    if _seen is None:
        _seen = []
    if not script_label or script_label in _seen or _depth > 24:
        return set(), False, _seen
    body = scripts.get(script_label)
    if body is None:
        return set(), False, _seen
    _seen.append(script_label)
    found = {(m.group(1), m.group(2)) for m in WILD_BATTLE_RE.finditer(body)}
    pre_e4 = bool(PREE4_RE.search(body))
    for target in script_refs(body, scripts):
        sub, sub_pre, _ = collect_static_encounters(
            target, scripts, _seen, _depth + 1)
        found |= sub
        pre_e4 = pre_e4 or sub_pre
    return found, pre_e4, _seen


def static_encounter(script, scripts, objects_by_local_id=None):
    """Describe the single static encounter an event starts, or None.

    Scripts that can start encounters with different species (for example
    the vanilla Southern Island sign, which picks Latios or Latias from a
    variable) are ambiguous and skipped rather than guessed.
    """
    found, pre_e4, visited = collect_static_encounters(script, scripts)
    if len(found) != 1:
        return None
    species, level = next(iter(found))
    entry = {"species": species,
             "level": int(level) if level.isdigit() else level,
             "preE4": pre_e4}
    # A trigger tile often starts the battle with a separate Pokemon object
    # (Groudon, Kyogre, Ho-Oh); anchor the marker on that object.
    token = species[len("SPECIES_"):].split("_")[0]
    for label in visited:
        for local_id in LOCALID_RE.findall(scripts.get(label, "")):
            ev = (objects_by_local_id or {}).get(local_id)
            if ev and token in local_id:
                entry["anchor"] = (int(ev.get("x", 0)), int(ev.get("y", 0)))
                return entry
    return entry


def load_legendary_species():
    """SPECIES_* flagged legendary/mythical in the species info headers."""
    root = C.src("src", "data", "pokemon", "species_info")
    out = set()
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.endswith(".h"):
            continue
        with open(os.path.join(root, name), encoding="utf-8",
                  errors="replace") as f:
            text = f.read()
        starts = list(re.finditer(r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=", text,
                                  re.MULTILINE))
        for i, m in enumerate(starts):
            end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
            if LEGENDARY_FLAG_RE.search(text, m.end(), end):
                out.add(m.group(1))
    return out


def find_script_path(start, target, scripts, _seen=None, _depth=0):
    """Return one call/goto/map-script path from start to target."""
    if not start or _depth > 24:
        return None
    if start == target:
        return [start]
    if _seen is None:
        _seen = set()
    if start in _seen:
        return None
    seen = _seen | {start}
    for child in script_refs(scripts.get(start, ""), scripts):
        path = find_script_path(child, target, scripts, seen, _depth + 1)
        if path:
            return [start] + path
    return None


VAR_GFX_RE = re.compile(
    r"\bsetvar\s+VAR_OBJ_GFX_ID_(\w)\s*,\s*(OBJ_EVENT_GFX_\w+)")


def variable_gfx(local_scripts, scripts):
    """OBJ_EVENT_GFX_VAR_N -> the one sprite this map's scripts set it to."""
    values = defaultdict(set)
    seen = set()
    todo = list(local_scripts)
    while todo:
        label = todo.pop()
        if label in seen:
            continue
        seen.add(label)
        body = scripts.get(label, "")
        for n, gfx in VAR_GFX_RE.findall(body):
            values["OBJ_EVENT_GFX_VAR_" + n].add(gfx)
        todo.extend(script_refs(body, scripts))
    return {var: gfx.pop() for var, gfx in values.items() if len(gfx) == 1}


def load_maps(dims):
    """Return dict name -> map record with objects/items resolved."""
    maps = {}
    shared_scripts = load_shared_scripts()
    for dirname, mj in C.iter_map_jsons():
        layout_id = mj.get("layout")
        if layout_id not in dims:
            continue  # layout has no renderable blockdata (deleted FRLG etc.)
        w, h, layout_name = dims[layout_id]
        img = layout_name + ".png"
        if not os.path.isfile(os.path.join(C.SITE_MAPS_IMG, img)):
            continue
        local_scripts = parse_scripts_inc(
            C.src("data", "maps", dirname, "scripts.inc"))
        scripts = local_scripts
        gift_scripts = dict(shared_scripts)
        gift_scripts.update(local_scripts)

        trainers, items, gifts, statics = [], [], [], []
        claimed_package_scripts = set()
        objects_by_local_id = {
            ev.get("local_id"): ev for ev in mj.get("object_events", [])
            if ev.get("local_id")
        }

        def add_care_package(script, x, y, gfx=None, direction="down"):
            packages = collect_gift_packages(script, gift_scripts)
            packages = [(source, items) for source, items in packages
                        if source not in claimed_package_scripts]
            # A single item granted by a globally shared script is usually
            # an event distribution (the Mystery Gift man offers the Eon
            # Ticket in every Pokemon Center), not this map's own gift.
            packages = [(source, items) for source, items in packages
                        if len({item for item, _ in items}) >= 2
                        or source in local_scripts]
            if not packages:
                return
            for source, _ in packages:
                claimed_package_scripts.add(source)
            items, care_package = merge_gift_packages(packages)
            if items:
                gifts.append({"x": x, "y": y, "gfx": gfx,
                              "dir": direction, "script": script,
                              "carePackage": care_package,
                              "items": items})

        for ev in mj.get("object_events", []):
            x, y = int(ev.get("x", 0)), int(ev.get("y", 0))
            # resolve any object whose script starts a battle (covers gym
            # leaders / rivals with trainer_type NONE, not just sight trainers)
            if ev.get("script"):
                placed_here = set()
                for tid, battle_label, _ in find_battles(ev.get("script"),
                                                         scripts):
                    # A cutscene NPC (Capt. Stern) can start a battle against
                    # objects its script spawns; those belong to the spawned
                    # opponents, which scripted_battles() places below.
                    if spawned_objects(scripts.get(battle_label)) \
                            - {ev.get("local_id")} or tid in placed_here:
                        continue
                    placed_here.add(tid)
                    trainers.append({"x": x, "y": y, "trainerId": tid,
                                     "gfx": ev.get("graphics_id"),
                                     "dir": facing_dir(ev.get("movement_type"))})
                # Gifts: an NPC/event script that recursively gives items (2+
                # in one block is a care package). Trainer objects can also
                # award them (notably Gym Leaders), so this must be
                # independent of trainer detection.
                if ev.get("graphics_id") != "OBJ_EVENT_GFX_ITEM_BALL":
                    add_care_package(
                        ev.get("script"), x, y, ev.get("graphics_id"),
                        facing_dir(ev.get("movement_type")))
            if ev.get("graphics_id") == "OBJ_EVENT_GFX_ITEM_BALL":
                items.append({"x": x, "y": y,
                              "item": ev.get("trainer_sight_or_berry_tree_id"),
                              "hidden": False})
        # scripted/cutscene battles not attached to an object's own script
        claimed = {t["trainerId"] for t in trainers}
        trainers.extend(
            scripted_battles(mj.get("object_events", []), scripts, claimed))
        # Trigger tiles that start a battle whose scripts name no object
        # near it (the rival scenes on Routes 110 and 119).
        for ce in mj.get("coord_events", []):
            for tid, _, path in find_battles(ce.get("script"), scripts):
                ev = battle_anchor(path, scripts, objects_by_local_id)
                if tid in claimed or ev is None:
                    continue
                claimed.add(tid)
                trainers.append({"x": int(ev.get("x", 0)),
                                 "y": int(ev.get("y", 0)), "trainerId": tid,
                                 "gfx": ev.get("graphics_id"),
                                 "dir": facing_dir(ev.get("movement_type"))})
        # OBJ_EVENT_GFX_VAR_N objects take the sprite the map's scripts set
        # (the Route 119 rival).
        var_gfx = variable_gfx(local_scripts, gift_scripts)
        for t in trainers:
            t["gfx"] = var_gfx.get(t["gfx"], t["gfx"])

        for ev in mj.get("bg_events", []):
            if ev.get("type") == "hidden_item":
                items.append({"x": int(ev.get("x", 0)),
                              "y": int(ev.get("y", 0)),
                              "item": ev.get("item"), "hidden": True})
            elif ev.get("script"):
                add_care_package(ev.get("script"), int(ev.get("x", 0)),
                                 int(ev.get("y", 0)))

        # Triggered events can be the actual handoff point for a package.
        for ev in mj.get("coord_events", []):
            if ev.get("script"):
                add_care_package(ev.get("script"), int(ev.get("x", 0)),
                                 int(ev.get("y", 0)))

        # Finally include packages awarded by map-script cutscenes. Prefer a
        # referenced character's exact tile; otherwise use the map center.
        for root in (label for label in local_scripts
                     if label.endswith("_MapScripts")):
            packages = collect_gift_packages(root, gift_scripts)
            unseen_sources = [source for source, _ in packages
                              if source not in claimed_package_scripts]
            if not unseen_sources:
                continue
            anchor = None
            for source in unseen_sources:
                path = find_script_path(root, source, gift_scripts) or []
                for label in reversed(path):
                    local_ids = re.findall(
                        r"\bLOCALID_[A-Z0-9_]+\b",
                        gift_scripts.get(label, ""))
                    for local_id in reversed(local_ids):
                        if local_id in objects_by_local_id:
                            anchor = objects_by_local_id[local_id]
                            break
                    if anchor:
                        break
                if anchor:
                    break
            add_care_package(
                root,
                int(anchor.get("x")) if anchor else max(0, int(w) // 2),
                int(anchor.get("y")) if anchor else max(0, int(h) // 2),
                anchor.get("graphics_id") if anchor else None,
                facing_dir(anchor.get("movement_type")) if anchor else "down")

        # Static encounters. Objects come first so a Pokemon's own object
        # wins over a trigger tile that starts the same battle.
        seen_species = set()
        # Several objects may share a species (Kecleon on one route); a
        # trigger tile for an already-placed species is the same battle.
        events = ([(ev, True) for ev in mj.get("object_events", [])]
                  + [(ev, False) for ev in mj.get("bg_events", [])
                     + mj.get("coord_events", [])])
        for ev, is_object in events:
            if not ev.get("script") or ev.get("script") == "0x0":
                continue
            enc = static_encounter(ev["script"], gift_scripts,
                                   objects_by_local_id)
            if not enc or (not is_object and enc["species"] in seen_species):
                continue
            seen_species.add(enc["species"])
            x, y = enc.pop("anchor", (int(ev.get("x", 0)), int(ev.get("y", 0))))
            enc.update(x=x, y=y, place=_spaced(dirname))
            statics.append(enc)

        warps = [{"x": int(w0.get("x", 0)), "y": int(w0.get("y", 0)),
                  "dest": w0.get("dest_map")}
                 for w0 in mj.get("warp_events", [])]

        maps[mj["id"]] = {
            "id": mj["id"], "name": dirname, "img": img,
            "w": w, "h": h, "wPx": w * TILE, "hPx": h * TILE,
            "type": mj.get("map_type"),
            "connections": mj.get("connections") or [],
            "warps": warps, "trainers": trainers, "items": items,
            "gifts": gifts, "statics": statics,
        }
    return maps


# --------------------------------------------------------------------------- #
# Connection components + intra-component layout
# --------------------------------------------------------------------------- #
def component_layout(maps):
    """Return list of components; each is {mapId: (localX, localY)} in px."""
    seen = set()
    comps = []
    for root in maps:
        if root in seen:
            continue
        coords = {root: (0, 0)}
        seen.add(root)
        q = deque([root])
        while q:
            cur = q.popleft()
            cx, cy = coords[cur]
            m = maps[cur]
            for conn in m["connections"]:
                nb = conn.get("map")
                if nb not in maps:
                    continue
                off = int(conn.get("offset", 0)) * TILE
                d = conn.get("direction")
                nm = maps[nb]
                if d == "up":
                    pos = (cx + off, cy - nm["hPx"])
                elif d == "down":
                    pos = (cx + off, cy + m["hPx"])
                elif d == "left":
                    pos = (cx - nm["wPx"], cy + off)
                elif d == "right":
                    pos = (cx + m["wPx"], cy + off)
                else:
                    continue
                if nb not in coords:
                    coords[nb] = pos
                    seen.add(nb)
                    q.append(nb)
        # normalise to local (0,0) min corner & record bbox
        minx = min(x for x, _ in coords.values())
        miny = min(y for _, y in coords.values())
        coords = {k: (x - minx, y - miny) for k, (x, y) in coords.items()}
        comps.append(coords)
    return comps


# --------------------------------------------------------------------------- #
# Packing islands without overlap
# --------------------------------------------------------------------------- #
class Packer:
    def __init__(self):
        self.rects = []  # (x0, y0, x1, y1)

    def add(self, x0, y0, w, h):
        self.rects.append((x0, y0, x0 + w, y0 + h))

    def overlaps(self, x0, y0, w, h):
        x1, y1 = x0 + w, y0 + h
        for rx0, ry0, rx1, ry1 in self.rects:
            if x0 < rx1 + PAD and x1 + PAD > rx0 and \
               y0 < ry1 + PAD and y1 + PAD > ry0:
                return True
        return False

    def find_spot(self, ax, ay, w, h):
        """Spiral search outward from (ax, ay) for a non-overlapping slot."""
        if not self.overlaps(ax, ay, w, h):
            return ax, ay
        step = max(64, (w + h) // 4)
        for ring in range(1, 60):
            r = ring * step
            for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r),
                           (r, r), (-r, r), (r, -r), (-r, -r)):
                x, y = ax + dx, ay + dy
                if not self.overlaps(x, y, w, h):
                    return x, y
        return ax, ay  # give up, allow overlap


# --------------------------------------------------------------------------- #
# Main assembly
# --------------------------------------------------------------------------- #
def assemble(maps):
    comps = component_layout(maps)
    # find the overworld component (contains Littleroot)
    main_idx = 0
    for i, c in enumerate(comps):
        if "MAP_LITTLEROOT_TOWN" in c:
            main_idx = i
            break

    placed = {}        # mapId -> (originX, originY)
    packer = Packer()
    warp_links = []

    def place_component(coords, base_x, base_y):
        for mid, (lx, ly) in coords.items():
            ox, oy = base_x + lx, base_y + ly
            placed[mid] = (ox, oy)
            packer.add(ox, oy, maps[mid]["wPx"], maps[mid]["hPx"])

    # 1. overworld at origin
    place_component(comps[main_idx], 0, 0)

    # warp lookup: destMap -> list of (srcMap, srcXY)
    warp_into = defaultdict(list)
    for mid, m in maps.items():
        for wp in m["warps"]:
            if wp["dest"]:
                warp_into[wp["dest"]].append((mid, wp["x"], wp["y"]))

    # Sootopolis City is reached by diving, not a warp, so nothing anchors it
    # and it (with every building inside) would fall to the overflow grid.
    # Treat the crater on Route 126's island as its entrance instead, so the
    # city floats next to the island with a link drawn from the crater.
    warp_into["MAP_SOOTOPOLIS_CITY"].insert(0, ("MAP_ROUTE126", 43, 45))

    # 1b. Cluster all Trick House maps into one tidy block. They are otherwise
    #     scattered: only Puzzle 1 has a static warp path from the overworld, so
    #     the entrance/corridor/end land near Route 110 while puzzle rooms 2-8
    #     (warp-orphans) fall to the overflow grid far away. Group them here so
    #     the whole Trick House reads as a single area on the map.
    TH_ORDER = ["ENTRANCE", "CORRIDOR", "PUZZLE1", "PUZZLE2", "PUZZLE3",
                "PUZZLE4", "PUZZLE5", "PUZZLE6", "PUZZLE7", "PUZZLE8", "END"]
    def _th_rank(mid):
        for i, k in enumerate(TH_ORDER):
            if mid.endswith(k):
                return i
        return len(TH_ORDER)
    th_mids = sorted((mid for mid in maps if "TRICK_HOUSE" in mid), key=_th_rank)
    th_set = set(th_mids)
    if th_mids:
        # reserve a clear block to the right of the overworld component
        base_x = max(placed[m][0] + maps[m]["wPx"] for m in placed) + 600
        col_w = max(maps[m]["wPx"] for m in th_mids) + PAD
        row_h = max(maps[m]["hPx"] for m in th_mids) + PAD + 24
        COLS = 4
        for i, mid in enumerate(th_mids):
            ox = base_x + (i % COLS) * col_w
            oy = (i // COLS) * row_h
            placed[mid] = (ox, oy)
            packer.add(ox, oy, maps[mid]["wPx"], maps[mid]["hPx"])

    # 2. iteratively place remaining components anchored to placed maps
    #    (skip Trick House maps; they were clustered above in step 1b)
    remaining = [c for i, c in enumerate(comps)
                 if i != main_idx and not (set(c) & th_set)]
    progressed = True
    while remaining and progressed:
        progressed = False
        still = []
        for coords in remaining:
            anchor = None  # (ax, ay, link_from_xy, link_from_map, target_mid)
            for mid in coords:
                for src_map, sx, sy in warp_into.get(mid, []):
                    if src_map in placed:
                        sox, soy = placed[src_map]
                        ax = sox + sx * TILE
                        ay = soy + sy * TILE
                        anchor = (ax, ay, (ax, ay), src_map, mid)
                        break
                if anchor:
                    break
            if not anchor:
                still.append(coords)
                continue
            ax, ay, link_xy, src_map, target_mid = anchor
            # bbox of the component
            cw = max(coords[m][0] + maps[m]["wPx"] for m in coords)
            ch = max(coords[m][1] + maps[m]["hPx"] for m in coords)
            tlx, tly = coords[target_mid]
            # desired: put target map a bit below-right of the warp tile
            want_x = ax + 48 - tlx
            want_y = ay + 48 - tly
            spot_x, spot_y = packer.find_spot(want_x, want_y, cw, ch)
            place_component(coords, spot_x, spot_y)
            tox, toy = placed[target_mid]
            warp_links.append({
                "from": [link_xy[0], link_xy[1]],
                "to": [tox + maps[target_mid]["wPx"] / 2,
                       toy + maps[target_mid]["hPx"] / 2]})
            progressed = True
        remaining = still

    # 3. anything still unplaced (no warp path) -> overflow grid at bottom
    if remaining:
        oy = max((placed[m][1] + maps[m]["hPx"] for m in placed), default=0) \
            + 400
        ox = 0
        rowh = 0
        for coords in remaining:
            cw = max(coords[m][0] + maps[m]["wPx"] for m in coords)
            ch = max(coords[m][1] + maps[m]["hPx"] for m in coords)
            if ox > 6000:
                ox = 0
                oy += rowh + PAD
                rowh = 0
            place_component(coords, ox, oy)
            ox += cw + PAD
            rowh = max(rowh, ch)

    # 4. Trick House progression links: outside (Route 110) -> entrance ->
    #    corridor -> each puzzle room in order. The Trick House warps are
    #    dynamic (one entrance door cycles through rooms via a variable), so
    #    these are drawn explicitly to show the intended play sequence.
    def _center(mid):
        ox, oy = placed[mid]
        return (ox + maps[mid]["wPx"] / 2, oy + maps[mid]["hPx"] / 2)

    def _edge_toward(mid, toward):
        # point on mid's rectangle border in the direction of `toward`, so a
        # room's incoming and outgoing endpoints sit on different edges and
        # don't overlap (overlapping endpoints make clicks resolve the wrong
        # direction).
        cx, cy = _center(mid)
        dx, dy = toward[0] - cx, toward[1] - cy
        if dx == 0 and dy == 0:
            return [cx, cy]
        hw, hh = maps[mid]["wPx"] / 2, maps[mid]["hPx"] / 2
        sx = hw / abs(dx) if dx else float("inf")
        sy = hh / abs(dy) if dy else float("inf")
        s = min(sx, sy)
        return [cx + dx * s, cy + dy * s]

    TH = "MAP_ROUTE110_TRICK_HOUSE_"
    chain = ([TH + "ENTRANCE", TH + "CORRIDOR"]
             + [TH + f"PUZZLE{i}" for i in range(1, 9)])
    if all(mid in placed for mid in chain):
        # outside door on Route 110 -> entrance
        if "MAP_ROUTE110" in placed:
            rox, roy = placed["MAP_ROUTE110"]
            for wp in maps["MAP_ROUTE110"]["warps"]:
                if wp["dest"] == TH + "ENTRANCE":
                    door = [rox + wp["x"] * TILE, roy + wp["y"] * TILE]
                    warp_links.append({
                        "from": door,
                        "to": _edge_toward(TH + "ENTRANCE", door)})
                    break
        # entrance -> corridor -> puzzle 1 -> ... -> puzzle 8, endpoints on the
        # facing edges of each room
        for a, b in zip(chain, chain[1:]):
            warp_links.append({"from": _edge_toward(a, _center(b)),
                               "to": _edge_toward(b, _center(a))})

    return placed, warp_links


# --------------------------------------------------------------------------- #
# Curated route notes
# --------------------------------------------------------------------------- #
# Hand-written signposts for the places where BPE deliberately diverges from
# vanilla Emerald and a player working from old knowledge would get stuck.
# Nothing in the game data says "this moved", so these are authored here and
# pinned to a tile; `goto` chains a note to the map that now holds what the
# player is after. Coordinates are map-local tiles, same as an object event.
# Guides belong to the selected game source, including historical exports.
_guides_path = C.src("BPEDocumentation", "content", "guides.json")
GUIDE_NOTES = C.load_json(_guides_path) if os.path.isfile(_guides_path) else []

# What a player must do to receive each gift, keyed by the marker's script.
# Shown in the gift popup and on the item page. The script scan cannot tell a
# debug-only or legacy-save branch from a real one, nor see single items given
# by shared scripts, so an entry may also correct the detected items:
# "exclude" drops items the player can't get there, "add" adds missed items or
# sets a quantity. A gift left with no items is not shown.
_gift_notes_path = C.src("BPEDocumentation", "content", "gift_notes.json")
GIFT_NOTES = ({n["script"]: n for n in C.load_json(_gift_notes_path)}
              if os.path.isfile(_gift_notes_path) else {})


# Curated lines about a trainer, keyed by TRAINER_ constant and shown at the
# top of the trainer's map popup (who the post-game challengers are).
_trainer_notes_path = C.src("BPEDocumentation", "content", "trainer_notes.json")
TRAINER_NOTES = ({n["trainer"]: n["note"] for n in C.load_json(_trainer_notes_path)}
                 if os.path.isfile(_trainer_notes_path) else {})


def annotate_trainer_shops(trainers, marts):
    """Give each trainer who opens a shop once beaten that shop's items.

    `trainers` is the shipped trainerData; entries are copied before they are
    changed so the parsed trainer database stays as it was.
    """
    for mart in marts.values():
        for inv in mart.get("inventories", []):
            tid = inv.get("trainer")
            if tid in trainers:
                t = trainers[tid] = dict(trainers[tid])
                t["shop"] = t.get("shop", []) + list(inv["items"])


def apply_trainer_notes(trainers, notes):
    """Attach curated notes; return the note keys that match no shown trainer."""
    for tid, note in notes.items():
        if tid in trainers:
            trainers[tid] = {**trainers[tid], "note": note}
    return sorted(set(notes) - set(trainers))


def apply_gift_note(gift, entry):
    """Attach a curated note to a gift and apply its item corrections."""
    if entry.get("note"):
        gift["note"] = entry["note"]
    excluded = set(entry.get("exclude", []))
    items = [dict(i) for i in gift["items"] if i["item"] not in excluded]
    for extra in entry.get("add", []):
        found = next((i for i in items if i["item"] == extra["item"]), None)
        if found:
            found["qty"] = extra.get("qty", 1)
        else:
            items.append({"item": extra["item"], "qty": extra.get("qty", 1),
                          "carePackage": False})
    gift["items"] = items
    gift["carePackage"] = any(i["carePackage"] for i in items)
    return gift


def build_guides(placed):
    """Pin each curated note to world pixel coordinates."""
    out = []
    known = {n["id"] for n in GUIDE_NOTES}
    for note in GUIDE_NOTES:
        mid = note["mapId"]
        if mid not in placed:
            print(f"  ! guide '{note['id']}': {mid} is not placed - skipped")
            continue
        dest = note.get("goto") or {}
        if dest.get("mapId") and dest["mapId"] not in placed:
            print(f"  ! guide '{note['id']}': target {dest['mapId']} "
                  f"is not placed - link dropped")
            dest = {}
        if dest.get("guide") and dest["guide"] not in known:
            print(f"  ! guide '{note['id']}': target note "
                  f"'{dest['guide']}' does not exist - link dropped")
            dest = {}
        ox, oy = placed[mid]
        entry = {"id": note["id"], "mapId": mid,
                 "gx": ox + note["x"] * TILE + TILE // 2,
                 "gy": oy + note["y"] * TILE + TILE // 2,
                 "title": note["title"], "body": note["body"]}
        if note.get("gfx"):
            entry["gfx"] = note["gfx"]
            entry["dir"] = note.get("dir", "down")
        if dest:
            entry["goto"] = dest
        out.append(entry)
    return out


def build():
    dims = load_layout_dims()
    maps = load_maps(dims)
    placed, warp_links = assemble(maps)
    trainers_db = parse_trainers.build()
    encounters = build_encounters()

    out_maps, out_trainers, out_items, out_gifts = [], [], [], []
    out_statics = []
    legendary_species = load_legendary_species()
    used_trainers = set()
    unresolved = 0
    enc_count = 0
    for mid, (ox, oy) in placed.items():
        m = maps[mid]
        entry = {"id": mid, "name": m["name"], "img": m["img"],
                 "type": m.get("type"),
                 "x": ox, "y": oy, "w": m["wPx"], "h": m["hPx"]}
        if mid in encounters:
            entry["enc"] = encounters[mid]
            enc_count += 1
        out_maps.append(entry)
        for t in m["trainers"]:
            tid = t["trainerId"]
            used_trainers.add(tid)
            out_trainers.append({"mapId": mid,
                                 "gx": ox + t["x"] * TILE + TILE // 2,
                                 "gy": oy + t["y"] * TILE + TILE // 2,
                                 "trainerId": tid, "gfx": t.get("gfx"),
                                 "dir": t.get("dir", "down")})
        for it in m["items"]:
            out_items.append({"mapId": mid,
                              "gx": ox + it["x"] * TILE + TILE // 2,
                              "gy": oy + it["y"] * TILE + TILE // 2,
                              "item": it["item"], "hidden": it["hidden"]})
        for g in m.get("gifts", []):
            gift = {"mapId": mid,
                    "gx": ox + g["x"] * TILE + TILE // 2,
                    "gy": oy + g["y"] * TILE + TILE // 2,
                    "gfx": g.get("gfx"),
                    "dir": g.get("dir", "down"),
                    "script": g.get("script", ""),
                    "carePackage": g.get("carePackage", False),
                    "items": g["items"]}
            if gift["script"] in GIFT_NOTES:
                apply_gift_note(gift, GIFT_NOTES[gift["script"]])
            if gift["items"]:
                out_gifts.append(gift)

        for st in m.get("statics", []):
            entry = {"mapId": mid, "place": st["place"],
                     "gx": ox + st["x"] * TILE + TILE // 2,
                     "gy": oy + st["y"] * TILE + TILE // 2,
                     "species": st["species"], "level": st["level"]}
            if st["preE4"]:
                entry["preE4"] = True
            if st["species"] in legendary_species:
                entry["legendary"] = True
            out_statics.append(entry)

    # only ship trainer data actually referenced on the map
    trainers_ship = {tid: trainers_db[tid]
                     for tid in used_trainers if tid in trainers_db}
    unresolved = len([t for t in used_trainers if t not in trainers_db])

    # Legendary Lottery Island: Route 130 is drawn with the Mirage Island layout
    # (always present in BPE), so attach the rotating legendary pool to its
    # encounter popup as a "Mirage Island Legendary" category.
    mirage_level, mirage_pool = read_island_legendary_pool()
    if mirage_pool:
        r130 = next((e for e in out_maps if e["id"] == "MAP_ROUTE130"), None)
        if r130 is not None:
            r130.setdefault("enc", {})["mirage"] = {
                "level": mirage_level,
                "mons": [{"species": sp} for sp in mirage_pool],
            }

    # annotate each party mon with its menu-icon filename (img/pokemon/*.png)
    pokemon_sprites.annotate(trainers_ship)

    # annotate each wild-encounter mon with its menu-icon filename
    enc_new, enc_missing = pokemon_sprites.annotate_encounters(out_maps)

    # Static encounter markers reuse the wild-encounter menu icons.
    pokemon_sprites.annotate_encounters(
        [{"enc": {"land": {"mons": out_statics}}}])

    guides = build_guides(placed)
    all_gift_scripts = {g.get("script", "") for m in maps.values()
                        for g in m.get("gifts", [])}
    for script in set(GIFT_NOTES) - all_gift_scripts:
        print(f"  ! gift note '{script}' matches no gift NPC - skipped")
    for g in out_gifts:
        if not g.get("note"):
            print(f"  ! gift '{g['script']}' on {g['mapId']} has no note")

    # render overworld sprites for trainers + gift NPCs + guides + item ball
    gfx_ids = {t["gfx"] for t in out_trainers if t.get("gfx")}
    gfx_ids |= {g["gfx"] for g in out_gifts if g.get("gfx")}
    gfx_ids |= {g["gfx"] for g in guides if g.get("gfx")}
    gfx_ids.add("OBJ_EVENT_GFX_ITEM_BALL")  # for item pickups
    sprite_map = sprites.extract_sprites(
        gfx_ids, os.path.join(C.SITE, "img", "sprites"))

    marts = parse_marts(trainers_db)
    annotate_trainer_shops(trainers_ship, marts)
    for tid in apply_trainer_notes(trainers_ship, TRAINER_NOTES):
        print(f"  ! trainer note '{tid}' matches no trainer on the map - skipped")

    world = {
        "tile": TILE,
        "maps": out_maps,
        "trainers": out_trainers,
        "items": out_items,
        "gifts": out_gifts,
        "statics": out_statics,
        "marts": marts,
        "guides": guides,
        "warpLinks": warp_links,
        "trainerData": trainers_ship,
        "sprites": sprite_map,
    }
    import map_overview
    map_overview.build(world, C.SITE)
    C.write_json(os.path.join(C.SITE_DATA, "world.json"), world)

    print(f"Maps placed:    {len(out_maps)}")
    print(f"Trainers shown: {len(out_trainers)} "
          f"({len(trainers_ship)} unique teams, {unresolved} unresolved)")
    print(f"Items shown:    {len(out_items)} "
          f"({sum(1 for i in out_items if i['hidden'])} hidden)")
    print(f"Gifts:          {len(out_gifts)} "
          f"({sum(1 for g in out_gifts if g['carePackage'])} care packages)")
    print(f"Static Pokemon: {len(out_statics)} "
          f"({sum(1 for s in out_statics if s.get('preE4'))} pre-Elite Four)")
    print(f"Marts parsed:   {len(marts)}")
    print(f"Guide notes:    {len(guides)}")
    print(f"Warp links:     {len(warp_links)}")
    print(f"Maps w/ encs:   {enc_count}")
    print(f"Enc icons:      {enc_new} new"
          + (f", {len(enc_missing)} without an icon" if enc_missing else ""))
    if enc_missing:
        print("  " + ", ".join(sorted(enc_missing)))
    print(f"Trainer sprites:{len(sprite_map)} unique gfx")
    return world


if __name__ == "__main__":
    C.ensure_dirs()
    build()
