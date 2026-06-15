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
import sprites

TILE = 16  # px per metatile block
PAD = 24   # px gap between islands when packing

TRAINER_TOK_RE = re.compile(r"\bTRAINER_[A-Z0-9_]+\b")

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


def resolve_trainer(script_label, scripts, depth=0):
    """Follow a trainer object's script to the first TRAINER_* id."""
    if not script_label or depth > 4:
        return None
    body = scripts.get(script_label)
    if body is None:
        return None
    m = TRAINER_TOK_RE.search(body)
    if m and m.group(0) not in ("TRAINER_TYPE_NORMAL", "TRAINER_TYPE_NONE"):
        return m.group(0)
    # follow a goto/call to another local script
    g = re.search(r"\b(?:goto|call)\s+(\w+)", body)
    if g:
        return resolve_trainer(g.group(1), scripts, depth + 1)
    return None


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

        trainers, items = [], []
        for ev in mj.get("object_events", []):
            x, y = int(ev.get("x", 0)), int(ev.get("y", 0))
            if ev.get("trainer_type") not in (None, "TRAINER_TYPE_NONE",
                                              "0", 0):
                tid = resolve_trainer(ev.get("script"), scripts)
                if tid:
                    trainers.append({"x": x, "y": y, "trainerId": tid,
                                     "gfx": ev.get("graphics_id")})
            if ev.get("graphics_id") == "OBJ_EVENT_GFX_ITEM_BALL":
                items.append({"x": x, "y": y,
                              "item": ev.get("trainer_sight_or_berry_tree_id"),
                              "hidden": False})
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
            "connections": mj.get("connections") or [],
            "warps": warps, "trainers": trainers, "items": items,
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

    # 2. iteratively place remaining components anchored to placed maps
    remaining = [c for i, c in enumerate(comps) if i != main_idx]
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

    return placed, warp_links


def build():
    dims = load_layout_dims()
    maps = load_maps(dims)
    placed, warp_links = assemble(maps)
    trainers_db = parse_trainers.build()
    encounters = build_encounters()

    out_maps, out_trainers, out_items = [], [], []
    used_trainers = set()
    unresolved = 0
    enc_count = 0
    for mid, (ox, oy) in placed.items():
        m = maps[mid]
        entry = {"id": mid, "name": m["name"], "img": m["img"],
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
                                 "trainerId": tid, "gfx": t.get("gfx")})
        for it in m["items"]:
            out_items.append({"mapId": mid,
                              "gx": ox + it["x"] * TILE + TILE // 2,
                              "gy": oy + it["y"] * TILE + TILE // 2,
                              "item": it["item"], "hidden": it["hidden"]})

    # only ship trainer data actually referenced on the map
    trainers_ship = {tid: trainers_db[tid]
                     for tid in used_trainers if tid in trainers_db}
    unresolved = len([t for t in used_trainers if t not in trainers_db])

    # render overworld sprites for the trainer graphics ids in use
    gfx_ids = {t["gfx"] for t in out_trainers if t.get("gfx")}
    sprite_map = sprites.extract_sprites(
        gfx_ids, os.path.join(C.SITE, "img", "sprites"))

    world = {
        "tile": TILE,
        "maps": out_maps,
        "trainers": out_trainers,
        "items": out_items,
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
    print(f"Warp links:     {len(warp_links)}")
    print(f"Maps w/ encs:   {enc_count}")
    print(f"Trainer sprites:{len(sprite_map)} unique gfx")
    return world


if __name__ == "__main__":
    C.ensure_dirs()
    build()
