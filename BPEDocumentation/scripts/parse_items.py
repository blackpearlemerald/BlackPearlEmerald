"""
BPE Emerald Items data parser.

Reads ROM source files and generates:
  site/data/items_index.json   - All items with basic fields
  site/data/items/{KEY}.json   - Full data per item
  site/sprites/items/{key}.png - Item icon sprites (24x24)

Usage:  py parse_items.py
"""

import re, json, os
from pathlib import Path
import common as C
from PIL import Image

# ── Paths ──────────────────────────────────────────────────────────────────────

HERE     = Path(__file__).resolve().parent
DOC_ROOT = HERE.parent
REPO     = Path(C.SRC_ROOT)
SITE     = Path(C.SITE)
DATA_DIR = SITE / "data"
ITEMS_DIR = DATA_DIR / "items"
ICONS_DST = SITE / "sprites" / "items"

ITEMS_H    = REPO / "src" / "data" / "items.h"
GFX_ITEMS_H = REPO / "src" / "data" / "graphics" / "items.h"
TYPES_INFO_H = REPO / "src" / "data" / "types_info.h"
MOVES_JSON = DATA_DIR / "moves.json"

# ── Pocket metadata ────────────────────────────────────────────────────────────

POCKET_LABELS = {
    "POCKET_ITEMS":      "Items",
    "POCKET_POKE_BALLS": "Poké Balls",
    "POCKET_TM_HM":      "TMs & HMs",
    "POCKET_BERRIES":    "Berries",
    "POCKET_KEY_ITEMS":  "Key Items",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def strip_c_comments(text):
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text

def extract_string_literals(text):
    """Join adjacent C string literals, replacing \\n with a space."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    joined = " ".join(parts)
    joined = re.sub(r"\\n", " ", joined)
    joined = re.sub(r"\s{2,}", " ", joined).strip()
    return joined

def parse_price(raw):
    """Return the modern-gen price from a .price = <expr> value string."""
    raw = raw.strip()
    # Simple integer
    m = re.match(r"^(\d+)$", raw)
    if m:
        return int(m.group(1))
    # Conditional: take first numeric after '?'
    m = re.search(r"\?\s*(\d+)", raw)
    if m:
        return int(m.group(1))
    return 0

def read_jasc_pal(path):
    """Parse a JASC-PAL file into a list of (r, g, b) tuples."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    n = int(lines[2].strip())
    cols = []
    for ln in lines[3:3 + n]:
        parts = ln.split()
        if len(parts) >= 3:
            cols.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return cols


def parse_gfx_symbols():
    """Build {symbol: repo-relative path} maps for item icons and palettes
    from src/data/graphics/items.h (INCGFX/INCBIN declarations)."""
    text = read_file(GFX_ITEMS_H)
    icons, palettes = {}, {}
    # gItemIcon_X[] = INCGFX_U32("graphics/items/icons/x.png", ...)
    for m in re.finditer(r'(gItemIcon_\w+)\[\]\s*=\s*INC\w+\(\s*"([^"]+)"', text):
        icons[m.group(1)] = re.sub(r"\.(?:4|8)bpp(?:\.lz)?$", ".png", m.group(2))
    # gItemIconPalette_Y[] = INCGFX_U16("graphics/items/icon_palettes/y.pal", ...)
    for m in re.finditer(r'(gItemIconPalette_\w+)\[\]\s*=\s*INC\w+\(\s*"([^"]+)"', text):
        palettes[m.group(1)] = re.sub(r"\.gbapal(?:\.lz)?$", ".pal", m.group(2))
    return icons, palettes


def parse_type_tmhm_palettes():
    """Build {TYPE_NAME: palette symbol} from gTypesInfo[].paletteTMHM."""
    if not TYPES_INFO_H.exists():
        # Older releases specify their icon palette directly on the item.
        return {}
    text = strip_c_comments(read_file(TYPES_INFO_H))
    out = {}
    for m in re.finditer(
        r'\[TYPE_(\w+)\]\s*=\s*\{(.*?)\n\s*\}', text, re.DOTALL
    ):
        type_name = m.group(1)
        pm = re.search(r'\.paletteTMHM\s*=\s*(gItemIconPalette_\w+)', m.group(2))
        if pm:
            out[type_name] = pm.group(1)
    return out

# ── 1. Shared static description strings ──────────────────────────────────────

def parse_shared_descriptions(content):
    """Collect  static const u8 sXxxDesc[] = _("...");  entries."""
    descs = {}
    for m in re.finditer(
        r"static\s+const\s+u8\s+(s\w+)\[\]\s*=\s*_\((.*?)\)\s*;",
        content, re.DOTALL
    ):
        var  = m.group(1)
        text = extract_string_literals(m.group(2))
        descs[var] = text
    return descs

# ── 2. Items ───────────────────────────────────────────────────────────────────

def extract_block(content, start_pos):
    """Return the text inside the brace block starting at start_pos (after the '{')."""
    depth = 1
    i = start_pos
    while i < len(content) and depth > 0:
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    return content[start_pos : i - 1]

def parse_items(shared_descs):
    raw     = read_file(ITEMS_H)
    content = strip_c_comments(raw)

    # Only look inside gItemsInfo[] (avoids matching enum declarations above)
    array_m = re.search(r"const struct Item(?:Info)? gItemsInfo\[\]\s*=\s*\{", content)
    if not array_m:
        raise ValueError("gItemsInfo[] not found in items.h")

    body = content[array_m.end():]
    items = []

    for m in re.finditer(r"\[ITEM_(\w+)\]\s*=\s*\{", body):
        key   = m.group(1)
        block = extract_block(body, m.end())

        item = {"id": key}

        # ── Name ─────────────────────────────────────────────────────────────
        nm = (re.search(r'\.name\s*=\s*ITEM_NAME\("([^"]+)"\)', block) or
              re.search(r'\.name\s*=\s*_\("([^"]+)"\)', block))
        if nm:
            item["name"] = nm.group(1)
        elif "gQuestionMarksItemName" in block:
            item["name"] = "????????"
        else:
            item["name"] = key.replace("_", " ").title()

        # ── Price ─────────────────────────────────────────────────────────────
        pm = re.search(r"\.price\s*=\s*([^,\n]+)", block)
        item["price"] = parse_price(pm.group(1)) if pm else 0

        # ── Description ───────────────────────────────────────────────────────
        # Inline COMPOUND_STRING
        dm = re.search(
            r"\.description\s*=\s*COMPOUND_STRING\((.*?)\)(?=\s*[,}])",
            block, re.DOTALL
        )
        if dm:
            item["description"] = extract_string_literals(dm.group(1))
        else:
            # Reference to a shared static variable  (e.g. sFullHealDesc)
            dm = re.search(r"\.description\s*=\s*(s\w+Desc)\b", block)
            item["description"] = shared_descs.get(dm.group(1), "") if dm else ""

        # ── Pocket ────────────────────────────────────────────────────────────
        pm = re.search(r"\.pocket\s*=\s*(POCKET_\w+)", block)
        pocket = pm.group(1) if pm else "POCKET_ITEMS"
        item["pocket"]      = pocket
        item["pocketLabel"] = POCKET_LABELS.get(
            pocket, pocket.replace("POCKET_", "").replace("_", " ").title()
        )

        # ── Sort type / category ──────────────────────────────────────────────
        st = re.search(r"\.sortType\s*=\s*ITEM_TYPE_(\w+)", block)
        item["sortType"] = st.group(1).replace("_", " ").title() if st else ""

        # ── Icon symbols (resolved to PNGs later by render_icons) ──────────────
        ip = re.search(r"\.iconPic\s*=\s*(gItemIcon_\w+)", block)
        item["_iconPic"] = ip.group(1) if ip else None
        ipal = re.search(r"\.iconPalette\s*=\s*(gItemIconPalette_\w+)", block)
        item["_iconPalette"] = ipal.group(1) if ipal else None
        # TMs/HMs carry their move in .secondaryId; their icon is colored by type.
        mv = re.search(r"\.secondaryId\s*=\s*MOVE_(\w+)", block)
        item["_move"] = mv.group(1) if mv else None
        item["icon"] = None  # filled in by render_icons

        items.append(item)

    return items

# ── 3. Render icons (icon shape + per-item palette -> colored PNG) ──────────────

def _render_one(icon_rel, pal_syms_path, dst):
    """Recolor an indexed icon PNG with a JASC palette; index 0 -> transparent.
    Falls back to the icon's own embedded palette if pal_syms_path is None."""
    icon_path = REPO / icon_rel
    if not icon_path.exists():
        return False

    pal = None
    if pal_syms_path is not None:
        pp = REPO / pal_syms_path
        if pp.exists():
            pal = read_jasc_pal(pp)

    im = Image.open(icon_path)
    if im.mode != "P":
        # Already truecolor — just copy through with alpha.
        im.convert("RGBA").save(dst)
        return True

    if pal is None:
        # Use the icon's own embedded palette.
        flat = im.getpalette() or []
        pal = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]

    px = list(im.getdata())
    out_px = []
    for i in px:
        if i == 0:                       # GBA sprite color index 0 = transparent
            out_px.append((0, 0, 0, 0))
        else:
            c = pal[i] if i < len(pal) else (0, 0, 0)
            out_px.append((c[0], c[1], c[2], 255))
    out = Image.new("RGBA", im.size)
    out.putdata(out_px)
    out.save(dst)
    return True


def render_icons(items):
    """Resolve each item's icon shape + palette and write a colored 24x24 PNG.
    Mirrors the game's GetItemIconPic / GetItemIconPalette logic."""
    ICONS_DST.mkdir(parents=True, exist_ok=True)
    icon_map, pal_map = parse_gfx_symbols()
    type_pal = parse_type_tmhm_palettes()
    moves = {}
    if MOVES_JSON.exists():
        with open(MOVES_JSON, "r", encoding="utf-8") as f:
            moves = json.load(f)
    else:
        print("  ! moves.json not found — TM/HM icons will use a default color")

    rendered = missing = 0
    legacy_icons = {}
    legacy_table = REPO / "src/data/item_icon_table.h"
    if legacy_table.exists():
        legacy_icons = {key: (icon, palette) for key, icon, palette in re.findall(r"\[ITEM_(\w+)\]\s*=\s*\{(gItemIcon_\w+),\s*(gItemIconPalette_\w+)\}", read_file(legacy_table))}
    for item in items:
        key = item["id"]
        icon_sym = pal_sym = None

        if key in legacy_icons:
            icon_sym, pal_sym = legacy_icons[key]
        elif item["pocket"] == "POCKET_TM_HM":
            # TM/HM: a TM/HM disc colored by the move's type. The item->move
            # link is ITEM_TM_<MOVE>/ITEM_HM_<MOVE> -> MOVE_<MOVE>, so the move
            # is the key minus its prefix (HMs have no .secondaryId field).
            is_hm = key.startswith("HM_")
            icon_sym = "gItemIcon_HM" if is_hm else "gItemIcon_TM"
            mv = item.get("_move") or key[3:]
            mtype = moves.get(mv, {}).get("type") if mv else None
            pal_sym = type_pal.get(mtype)
        else:
            icon_sym = item.get("_iconPic")
            pal_sym = item.get("_iconPalette")

        icon_rel = icon_map.get(icon_sym) if icon_sym else None
        pal_rel = pal_map.get(pal_sym) if pal_sym else None

        if not icon_rel:
            missing += 1
            item["icon"] = None
            continue

        dst = ICONS_DST / f"{key.lower()}.png"
        if _render_one(icon_rel, pal_rel, dst):
            item["icon"] = f"sprites/items/{key.lower()}.png"
            rendered += 1
        else:
            missing += 1
            item["icon"] = None

    print(f"  icons: {rendered} rendered, {missing} without artwork")

# ── 4. JSON output ─────────────────────────────────────────────────────────────

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)

# ── 5. Location cross-reference ────────────────────────────────────────────────

WORLD_JSON = DATA_DIR.parent / "js" / "data" / "world.json"


def _prettify_map(map_id):
    """MAP_ROUTE103 -> Route 103, MAP_OLDALE_TOWN -> Oldale Town"""
    s = map_id.replace("MAP_", "").replace("_", " ").title()
    s = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)  # "Route103" -> "Route 103"
    return s


def build_locations(items_dict):
    """Return {item_id: {marts, overworld, gifts}} using world.json."""
    if not WORLD_JSON.exists():
        print("  ! world.json not found — skip location data")
        return {}

    with open(WORLD_JSON, "r", encoding="utf-8") as f:
        world = json.load(f)

    locs = {k: {"marts": [], "overworld": [], "gifts": []}
            for k in items_dict}

    map_names = {m["id"]: _prettify_map(m["id"]) for m in world.get("maps", [])}

    # Mart locations. A mart can stock an item across several inventory tiers;
    # emit ONE entry per mart with the clearest condition — "Always available"
    # if it's in every tier, otherwise the trigger of the earliest tier it
    # appears in (so an item only in the expanded list reads e.g. "After
    # meeting the Devon researcher", and a Petalburg-only expanded item reads
    # "Never unlocks (unused in-game)").
    # A map may hold several independent NPC vendors (department-store floors,
    # the Slateport stalls, the post-game shop NPCs), so tiers are grouped by
    # vendor and each vendor is reported as its own location. Dedicated Poké
    # Mart maps have no vendor on their tiers and fall into a single group,
    # which keeps their output identical to before.
    for map_id, mart in world.get("marts", {}).items():
        mart_name = mart.get("name", _prettify_map(map_id))
        groups = {}
        for inv in mart.get("inventories", []):
            groups.setdefault(inv.get("vendor"), []).append(inv)

        for vendor, invs in groups.items():
            if vendor and vendor.lower() not in ("clerk", "clerk left",
                                                 "clerk right"):
                label = f"{vendor} ({mart_name})"
            else:
                label = mart_name
            for key in locs:
                item_const = "ITEM_" + key
                present = [i for i, inv in enumerate(invs)
                           if item_const in inv.get("items", [])]
                if not present:
                    continue
                if len(present) == len(invs):
                    condition = (invs[0]["condition"] if len(invs) == 1
                                 else "Always available")
                else:
                    condition = invs[present[0]]["condition"]
                locs[key]["marts"].append(
                    {"mapId": map_id, "martName": label,
                     "condition": condition})

    # Overworld item ball pickups
    for it in world.get("items", []):
        item_const = it.get("item") or ""
        key = item_const.replace("ITEM_", "")
        if key in locs:
            entry = {"mapId": it["mapId"],
                     "mapName": map_names.get(it["mapId"],
                                              _prettify_map(it["mapId"])),
                     "hidden": it.get("hidden", False)}
            locs[key]["overworld"].append(entry)

    # NPC gifts and care packages
    for gift in world.get("gifts", []):
        map_name = map_names.get(gift["mapId"], _prettify_map(gift["mapId"]))
        for gi in gift.get("items", []):
            item_const = gi.get("item") or ""
            key = item_const.replace("ITEM_", "")
            if key in locs:
                qty = gi.get("qty", 1)
                entry = {"mapId": gift["mapId"], "mapName": map_name,
                         "qty": qty,
                         # Gifts list each item's own kind; older exports
                         # only marked the whole gift.
                         "carePackage": gi.get("carePackage",
                                               gift.get("carePackage", False))}
                locs[key]["gifts"].append(entry)

    return locs


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("BPE Items parser")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    print("  [1] Shared descriptions …")
    raw     = read_file(ITEMS_H)
    content = strip_c_comments(raw)
    shared  = parse_shared_descriptions(content)
    print(f"       -> {len(shared)} shared descriptions")

    print("  [2] Parsing items …")
    items = parse_items(shared)
    # Drop the NONE placeholder
    items = [i for i in items if i["id"] != "NONE" and i["name"] != "????????"]
    print(f"       -> {len(items)} items")

    print("  [3] Rendering icons …")
    render_icons(items)

    print("  [4] Building location data …")
    index = {item["id"]: item for item in items}
    locations = build_locations(index)
    for item in items:
        item["locations"] = locations.get(item["id"],
                                          {"marts": [], "overworld": [], "gifts": []})
    locs_with_data = sum(1 for i in items
                         if any(i["locations"][k] for k in ("marts","overworld","gifts")))
    print(f"       -> {locs_with_data}/{len(items)} items have location data")

    print("  [5] Writing JSON …")
    # Drop internal resolution fields before serializing.
    for item in items:
        for k in ("_iconPic", "_iconPalette", "_move"):
            item.pop(k, None)
    index = {item["id"]: item for item in items}
    write_json(DATA_DIR / "items_index.json", index)
    for item in items:
        write_json(ITEMS_DIR / f"{item['id']}.json", item)

    idx_kb   = os.path.getsize(DATA_DIR / "items_index.json") // 1024
    with_icon = sum(1 for i in items if i["icon"])
    print(f"       -> items_index.json: {idx_kb} KB")
    print(f"\nDone!  {with_icon}/{len(items)} items have icons")


if __name__ == "__main__":
    main()
