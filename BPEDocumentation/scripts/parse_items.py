"""
BPE Emerald Items data parser.

Reads ROM source files and generates:
  site/data/items_index.json   - All items with basic fields
  site/data/items/{KEY}.json   - Full data per item
  site/sprites/items/{key}.png - Item icon sprites (24x24)

Usage:  py parse_items.py
"""

import re, json, os, shutil
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

HERE     = Path(__file__).resolve().parent
DOC_ROOT = HERE.parent
REPO     = DOC_ROOT.parent
SITE     = DOC_ROOT / "site"
DATA_DIR = SITE / "data"
ITEMS_DIR = DATA_DIR / "items"
ICONS_DST = SITE / "sprites" / "items"

ITEMS_H   = REPO / "src" / "data" / "items.h"
GFX_ICONS = REPO / "graphics" / "items" / "icons"

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

def icon_filename(key):
    """Map an ITEM_* key to its PNG filename in graphics/items/icons/."""
    if key.startswith("TM_"):
        return "tm.png"
    if key.startswith("HM_"):
        return "hm.png"
    return key.lower() + ".png"

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
    array_m = re.search(r"const struct ItemInfo gItemsInfo\[\]\s*=\s*\{", content)
    if not array_m:
        print("  ERROR: gItemsInfo[] not found in items.h")
        return []

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

        # ── Icon path ─────────────────────────────────────────────────────────
        fname = icon_filename(key)
        item["icon"] = f"sprites/items/{fname}" if (GFX_ICONS / fname).exists() else None

        items.append(item)

    return items

# ── 3. Copy icons ──────────────────────────────────────────────────────────────

def copy_icons(items):
    ICONS_DST.mkdir(parents=True, exist_ok=True)
    copied = skipped = missing = 0
    seen = set()
    for item in items:
        fname = icon_filename(item["id"])
        src   = GFX_ICONS / fname
        dst   = ICONS_DST / fname
        if not src.exists():
            missing += 1
            continue
        if fname in seen:
            skipped += 1
            continue
        seen.add(fname)
        if not dst.exists():
            shutil.copy2(src, dst)
            copied += 1
    print(f"  icons: {copied} copied, {skipped} shared/skipped, {missing} not found")

# ── 4. JSON output ─────────────────────────────────────────────────────────────

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)

# ── 5. Location cross-reference ────────────────────────────────────────────────

WORLD_JSON = DATA_DIR.parent / "js" / "data" / "world.json"


def _prettify_map(map_id):
    """MAP_OLDALE_TOWN -> Oldale Town"""
    s = map_id.replace("MAP_", "").replace("_", " ").title()
    # collapse multi-word "Town Town" / "City City" patterns
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

    # Mart locations
    for map_id, mart in world.get("marts", {}).items():
        mart_name = mart.get("name", _prettify_map(map_id))
        for inv in mart.get("inventories", []):
            for item_const in inv.get("items", []):
                key = item_const.replace("ITEM_", "")
                if key in locs:
                    # Avoid duplicates
                    entry = {"mapId": map_id, "martName": mart_name,
                             "condition": inv["condition"]}
                    if entry not in locs[key]["marts"]:
                        locs[key]["marts"].append(entry)

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

    # Gift NPC bundles
    for gift in world.get("gifts", []):
        map_name = map_names.get(gift["mapId"], _prettify_map(gift["mapId"]))
        for gi in gift.get("items", []):
            item_const = gi.get("item") or ""
            key = item_const.replace("ITEM_", "")
            if key in locs:
                qty = gi.get("qty", 1)
                entry = {"mapId": gift["mapId"], "mapName": map_name,
                         "qty": qty}
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

    print("  [3] Copying icons …")
    copy_icons(items)

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
