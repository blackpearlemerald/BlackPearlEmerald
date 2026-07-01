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
    return out


def resolve_trainer(script_label, scripts, _seen=None):
    """Resolve an object's script to the TRAINER_* it battles, if any.

    Keys on the `trainerbattle*` macro (and `vsseeker_rematchid`, which names a
    rematchable trainer directly) so it works for both line-of-sight trainers
    and talk-to-battle NPCs (gym leaders, rivals) whose trainer_type is NONE,
    without false-positiving ordinary NPCs. Battle scripts are often reached via
    goto/call or switch/case, so all referenced local labels are followed.
    """
    if not script_label:
        return None
    if _seen is None:
        _seen = set()
    if script_label in _seen or len(_seen) > 64:
        return None
    _seen.add(script_label)
    body = scripts.get(script_label)
    if body is None:
        return None
    m = re.search(r"\btrainerbattle\w*[ \t]+([^\n]*)", body)
    if m:
        tid = opponent_from_args(m.group(1))
        if tid:
            return tid
    m = re.search(r"\bvsseeker_rematchid\s+(TRAINER_[A-Z0-9_]+)", body)
    if m:
        return m.group(1)
    # follow control flow into other local scripts: goto/call/case and their
    # conditional variants (goto_if_eq, call_if_set, ...). The branch target is
    # the last label argument on the line.
    for line in body.splitlines():
        if not re.match(r"\s*(?:goto|call|case)\w*\b", line):
            continue
        toks = re.findall(r"[A-Za-z_]\w*", line)
        if toks and toks[-1] in scripts:
            tid = resolve_trainer(toks[-1], scripts, _seen)
            if tid:
                return tid
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


def scripted_battles(object_events, scripts, claimed):
    """Find trainer battles that live in map/coord scripts rather than on an
    object (e.g. the Petalburg Woods Aqua grunt, the Champions Room champion),
    and tie each to the object that represents the trainer.

    Tier 1: the LOCALID textually nearest the battle line in the same script.
    Tier 2 (champion-style, where the battle script has no LOCALID): the
    unclaimed object whose LOCALID shares the most name tokens with the trainer.

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

    def place(lid, tid):
        ev = by_localid[lid]
        out.append({"x": int(ev.get("x", 0)), "y": int(ev.get("y", 0)),
                    "trainerId": tid, "gfx": ev.get("graphics_id"),
                    "dir": facing_dir(ev.get("movement_type"))})
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
                place(best, tid)
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

    # 2. Build script label→body map
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

    # 4. Conditional jumps in the clerk script → derive conditions & ordering.
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
            rank = n_set - seen_set   # first-checked (most advanced) → highest
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


def parse_marts():
    """Return {map_id: {name, inventories}} for every mart map."""
    result = {}
    maps_dir = C.src("data", "maps")
    for dirname in sorted(os.listdir(maps_dir)):
        if "mart" not in dirname.lower():
            continue
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
        inventories = parse_mart_scripts(content)
        if inventories:
            # "OldaleTown_Mart" → "Oldale Town"
            raw = dirname.replace("_Mart", "").replace("_UnusedMart", "").replace("_", " ")
            name = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
            result[map_id] = {"name": name, "inventories": inventories}
    return result


# --------------------------------------------------------------------------- #
# NPC care-package (gift) detection
# --------------------------------------------------------------------------- #
def collect_gifts(script_label, scripts, _seen=None):
    """Recursively follow calls/gotos; return list of (ITEM_*, qty) tuples."""
    if not script_label:
        return []
    if _seen is None:
        _seen = set()
    if script_label in _seen or len(_seen) > 24:
        return []
    _seen.add(script_label)
    body = scripts.get(script_label)
    if body is None:
        return []
    gifts = []
    for m in GIVEITEM_RE.finditer(body):
        gifts.append((m.group(1), int(m.group(2)) if m.group(2) else 1))
    for m in ADDITEM_RE.finditer(body):
        gifts.append((m.group(1), int(m.group(2)) if m.group(2) else 1))
    for line in body.splitlines():
        if not re.match(r"\s*(?:goto|call|case)\w*\b", line):
            continue
        toks = re.findall(r"[A-Za-z_]\w*", line)
        if toks and toks[-1] in scripts:
            gifts.extend(collect_gifts(toks[-1], scripts, _seen))
    return gifts


def load_maps(dims):
    """Return dict name -> map record with objects/items resolved."""
    maps = {}
    for dirname, mj in C.iter_map_jsons():
        layout_id = mj.get("layout")
        if layout_id not in dims:
            continue  # layout has no renderable blockdata (deleted FRLG etc.)
        w, h, layout_name = dims[layout_id]
        img = layout_name + ".png"
        if not os.path.isfile(os.path.join(C.SITE_MAPS_IMG, img)):
            continue
        scripts = parse_scripts_inc(
            C.src("data", "maps", dirname, "scripts.inc"))

        trainers, items, gifts = [], [], []
        for ev in mj.get("object_events", []):
            x, y = int(ev.get("x", 0)), int(ev.get("y", 0))
            # resolve any object whose script starts a battle (covers gym
            # leaders / rivals with trainer_type NONE, not just sight trainers)
            if ev.get("script"):
                tid = resolve_trainer(ev.get("script"), scripts)
                if tid:
                    trainers.append({"x": x, "y": y, "trainerId": tid,
                                     "gfx": ev.get("graphics_id"),
                                     "dir": facing_dir(ev.get("movement_type"))})
                # Gift NPC: script that recursively gives 2+ items
                elif ev.get("graphics_id") != "OBJ_EVENT_GFX_ITEM_BALL":
                    gift_items = collect_gifts(ev.get("script"), scripts)
                    if len(gift_items) >= 2:
                        gifts.append({"x": x, "y": y,
                                      "gfx": ev.get("graphics_id"),
                                      "dir": facing_dir(ev.get("movement_type")),
                                      "script": ev.get("script"),
                                      "items": [{"item": it, "qty": qty}
                                                 for it, qty in gift_items]})
            if ev.get("graphics_id") == "OBJ_EVENT_GFX_ITEM_BALL":
                items.append({"x": x, "y": y,
                              "item": ev.get("trainer_sight_or_berry_tree_id"),
                              "hidden": False})
        # scripted/cutscene battles not attached to an object's own script
        claimed = {t["trainerId"] for t in trainers}
        trainers.extend(
            scripted_battles(mj.get("object_events", []), scripts, claimed))

        for ev in mj.get("bg_events", []):
            if ev.get("type") == "hidden_item":
                items.append({"x": int(ev.get("x", 0)),
                              "y": int(ev.get("y", 0)),
                              "item": ev.get("item"), "hidden": True})

        warps = [{"x": int(w0.get("x", 0)), "y": int(w0.get("y", 0)),
                  "dest": w0.get("dest_map")}
                 for w0 in mj.get("warp_events", [])]

        maps[mj["id"]] = {
            "id": mj["id"], "name": dirname, "img": img,
            "w": w, "h": h, "wPx": w * TILE, "hPx": h * TILE,
            "type": mj.get("map_type"),
            "connections": mj.get("connections") or [],
            "warps": warps, "trainers": trainers, "items": items,
            "gifts": gifts,
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


def build():
    dims = load_layout_dims()
    maps = load_maps(dims)
    placed, warp_links = assemble(maps)
    trainers_db = parse_trainers.build()
    encounters = build_encounters()

    out_maps, out_trainers, out_items, out_gifts = [], [], [], []
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
            out_gifts.append({"mapId": mid,
                              "gx": ox + g["x"] * TILE + TILE // 2,
                              "gy": oy + g["y"] * TILE + TILE // 2,
                              "gfx": g.get("gfx"),
                              "dir": g.get("dir", "down"),
                              "script": g.get("script", ""),
                              "items": g["items"]})

    # only ship trainer data actually referenced on the map
    trainers_ship = {tid: trainers_db[tid]
                     for tid in used_trainers if tid in trainers_db}
    unresolved = len([t for t in used_trainers if t not in trainers_db])

    # annotate each party mon with its menu-icon filename (img/pokemon/*.png)
    pokemon_sprites.annotate(trainers_ship)

    # annotate each wild-encounter mon with its menu-icon filename
    enc_new, enc_missing = pokemon_sprites.annotate_encounters(out_maps)

    # render overworld sprites for trainers + gift NPCs + item ball
    gfx_ids = {t["gfx"] for t in out_trainers if t.get("gfx")}
    gfx_ids |= {g["gfx"] for g in out_gifts if g.get("gfx")}
    gfx_ids.add("OBJ_EVENT_GFX_ITEM_BALL")  # for item pickups
    sprite_map = sprites.extract_sprites(
        gfx_ids, os.path.join(C.SITE, "img", "sprites"))

    marts = parse_marts()

    world = {
        "tile": TILE,
        "maps": out_maps,
        "trainers": out_trainers,
        "items": out_items,
        "gifts": out_gifts,
        "marts": marts,
        "warpLinks": warp_links,
        "trainerData": trainers_ship,
        "sprites": sprite_map,
    }
    C.write_json(os.path.join(C.SITE_DATA, "world.json"), world)

    print(f"Maps placed:    {len(out_maps)}")
    print(f"Trainers shown: {len(out_trainers)} "
          f"({len(trainers_ship)} unique teams, {unresolved} unresolved)")
    print(f"Items shown:    {len(out_items)} "
          f"({sum(1 for i in out_items if i['hidden'])} hidden)")
    print(f"Gift NPCs:      {len(out_gifts)}")
    print(f"Marts parsed:   {len(marts)}")
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
