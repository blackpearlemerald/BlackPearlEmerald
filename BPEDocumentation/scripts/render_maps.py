"""Render every map layout to a PNG by decoding GBA tilesets + blockdata.

Read-only against the game source. Output -> site/img/maps/<Layout>.png
"""
import os
import re
import struct
import sys

from PIL import Image

import common as C

TILES_RE = re.compile(
    r'(gTilesetTiles_\w+)\[\]\s*=\s*INC(?:GFX|BIN)_\w+\("([^"]+tiles\.(?:png|4bpp(?:\.lz)?))"')
# in headers.h: "gTileset_X =" struct ... ".tiles = gTilesetTiles_Y,"
HEADER_TILESET_RE = re.compile(
    r'gTileset_(\w+)\s*=\s*\{.*?\.tiles\s*=\s*(gTilesetTiles_\w+)',
    re.DOTALL)


def build_tileset_index():
    """struct symbol 'gTileset_General' -> absolute folder w/ tiles.png.

    The struct's .tiles array symbol may be spelled differently than the
    struct symbol (e.g. gTileset_BuildingFrlg -> gTilesetTiles_Building_Frlg),
    so resolve struct -> tiles symbol (headers.h) -> folder (graphics.{c,h}).
    """
    # tiles array symbol -> folder
    tiles_folder = {}
    for rel in (("src", "graphics.c"),
                ("src", "data", "tilesets", "graphics.h")):
        path = C.src(*rel)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for sym, png in TILES_RE.findall(f.read()):
                tiles_folder[sym] = C.src(*os.path.dirname(png).split("/"))
    # struct symbol -> tiles array symbol
    with open(C.src("src", "data", "tilesets", "headers.h"),
              "r", encoding="utf-8") as f:
        header_text = f.read()
    index = {}
    for name, tiles_sym in HEADER_TILESET_RE.findall(header_text):
        folder = tiles_folder.get(tiles_sym)
        if folder:
            index["gTileset_" + name] = folder
    return index


class Tileset:
    """Lazily decoded tiles + palettes + metatiles for one tileset folder."""
    _cache = {}

    def __init__(self, folder):
        self.folder = folder
        # raw 4bpp indices: PIL 'P' mode, value 0-15 per pixel
        img = Image.open(os.path.join(folder, "tiles.png")).convert("P")
        self.tpix = img.load()
        self.tw = img.width // 8            # tiles per row (=16)
        self.ntiles = (img.width // 8) * (img.height // 8)
        with open(os.path.join(folder, "metatiles.bin"), "rb") as f:
            self.metatiles = f.read()
        # palettes 00..15 (only some used; index by slot number)
        self.pals = []
        for i in range(16):
            p = os.path.join(folder, "palettes", f"{i:02}.pal")
            self.pals.append(C.load_jasc_pal(p) if os.path.isfile(p) else
                             [(0, 0, 0)] * 16)

    @classmethod
    def get(cls, folder):
        ts = cls._cache.get(folder)
        if ts is None:
            ts = cls._cache[folder] = Tileset(folder)
        return ts

    def tile_indices(self, tid):
        """Return 64 palette-index values (row-major) for local tile id."""
        col = (tid % self.tw) * 8
        row = (tid // self.tw) * 8
        px = self.tpix
        out = []
        for y in range(row, row + 8):
            for x in range(col, col + 8):
                out.append(px[x, y])
        return out


def make_tile_image(prim, sec, tid, pal_slot, hflip, vflip):
    """8x8 RGBA tile. Color index 0 -> transparent."""
    if tid < C.NUM_TILES_IN_PRIMARY:
        ts, local = prim, tid
    else:
        ts, local = sec, tid - C.NUM_TILES_IN_PRIMARY
    if local >= ts.ntiles:
        return Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    palts = prim if pal_slot < C.NUM_PALS_IN_PRIMARY else sec
    palette = palts.pals[pal_slot]
    idx = ts.tile_indices(local)
    out = Image.new("RGBA", (8, 8))
    op = out.load()
    for y in range(8):
        for x in range(8):
            ci = idx[y * 8 + x]
            if ci == 0:
                continue  # transparent
            r, g, b = palette[ci]
            sx = 7 - x if hflip else x
            sy = 7 - y if vflip else y
            op[sx, sy] = (r, g, b, 255)
    return out


# 2x2 sub-tile placement within a 16x16 metatile, per layer
SUBPOS = [(0, 0), (8, 0), (0, 8), (8, 8)]


def render_layout(layout, tsindex, tile_cache):
    prim = Tileset.get(tsindex[layout["primary_tileset"]])
    sec_sym = layout.get("secondary_tileset") or layout["primary_tileset"]
    sec = Tileset.get(tsindex[sec_sym])

    w, h = layout["width"], layout["height"]
    with open(C.src(*layout["blockdata_filepath"].split("/")), "rb") as f:
        block = f.read()
    img = Image.new("RGBA", (w * 16, h * 16), (0, 0, 0, 0))

    def metatile_entries(mid):
        if mid < C.NUM_METATILES_IN_PRIMARY:
            ts, local = prim, mid
        else:
            ts, local = sec, mid - C.NUM_METATILES_IN_PRIMARY
        base = local * 16
        data = ts.metatiles
        if base + 16 > len(data):
            return None
        return struct.unpack_from("<8H", data, base)

    for by in range(h):
        for bx in range(w):
            off = (by * w + bx) * 2
            if off + 2 > len(block):
                continue
            val = struct.unpack_from("<H", block, off)[0]
            mid = val & C.MAPGRID_METATILE_ID_MASK
            ents = metatile_entries(mid)
            if ents is None:
                continue
            px0, py0 = bx * 16, by * 16
            # layer 0 = entries 0-3 (bottom), layer 1 = entries 4-7 (top)
            for layer in (0, 1):
                for i in range(4):
                    ent = ents[layer * 4 + i]
                    tid = ent & C.TILE_ID_MASK
                    if tid == 0 and (ent >> C.TILE_PAL_SHIFT) == 0:
                        pass  # still draw; tile 0 may be a real tile
                    hflip = bool(ent & C.TILE_HFLIP)
                    vflip = bool(ent & C.TILE_VFLIP)
                    pal = ent >> C.TILE_PAL_SHIFT
                    key = (id(prim), id(sec), tid, pal, hflip, vflip)
                    timg = tile_cache.get(key)
                    if timg is None:
                        timg = make_tile_image(prim, sec, tid, pal, hflip, vflip)
                        tile_cache[key] = timg
                    sx, sy = SUBPOS[i]
                    img.alpha_composite(timg, (px0 + sx, py0 + sy))
    return img


def main(only=None):
    C.ensure_dirs()
    tsindex = build_tileset_index()
    layouts = C.load_json(C.src("data", "layouts", "layouts.json"))["layouts"]
    tile_cache = {}
    rendered = 0
    for layout in layouts:
        name = layout["name"]
        if only and name not in only:
            continue
        try:
            img = render_layout(layout, tsindex, tile_cache)
        except Exception as e:
            print(f"  ! {name}: {e}")
            continue
        out = os.path.join(C.SITE_MAPS_IMG, name + ".png")
        img.save(out)
        rendered += 1
        if rendered % 25 == 0:
            print(f"  ... {rendered} rendered")
    print(f"Rendered {rendered} layouts -> {C.SITE_MAPS_IMG}")


if __name__ == "__main__":
    sel = set(sys.argv[1:]) or None
    main(sel)
