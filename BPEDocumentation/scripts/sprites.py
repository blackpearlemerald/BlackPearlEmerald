"""Extract overworld object-event sprites (frame 0) for trainer markers.

Chain: OBJ_EVENT_GFX_X
  -> object_event_graphics_info_pointers.h : gObjectEventGraphicsInfo_X
  -> object_event_graphics_info.h          : width/height + sPicTable_X
  -> object_event_pic_tables.h             : gObjectEventPic_X
  -> object_event_graphics.h               : graphics/.../x.png

Frame 0 (top-left, width x height) is the facing-down standing pose. Palette
index 0 is transparent. Read-only against the game source.
"""
import os
import re

from PIL import Image

import common as C

OEDIR = ("src", "data", "object_events")

PTR_RE = re.compile(r"\[(OBJ_EVENT_GFX_\w+)\]\s*=\s*&(gObjectEventGraphicsInfo_\w+)")
INFO_RE = re.compile(
    r"gObjectEventGraphicsInfo_(\w+)\s*=\s*\{(.*?)\};", re.DOTALL)
PICTBL_RE = re.compile(r"(sPicTable_\w+)\[\]\s*=\s*\{(.*?)\};", re.DOTALL)
PIC_RE = re.compile(r"(gObjectEventPic_\w+)\[\]\s*=\s*INCGFX_\w+\(\"([^\"]+)\"")


def _read(*parts):
    p = C.src(*parts)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def build_index():
    pointers = dict(PTR_RE.findall(_read(*OEDIR, "object_event_graphics_info_pointers.h")))

    info = {}  # 'gObjectEventGraphicsInfo_X' -> (w, h, picTableSymbol)
    for name, body in INFO_RE.findall(_read(*OEDIR, "object_event_graphics_info.h")):
        w = re.search(r"\.width\s*=\s*(\d+)", body)
        h = re.search(r"\.height\s*=\s*(\d+)", body)
        img = re.search(r"\.images\s*=\s*(\w+)", body)
        if w and h and img:
            info["gObjectEventGraphicsInfo_" + name] = (
                int(w.group(1)), int(h.group(1)), img.group(1))

    pictbl = {}  # 'sPicTable_X' -> 'gObjectEventPic_X'
    for sym, body in PICTBL_RE.findall(_read(*OEDIR, "object_event_pic_tables.h")):
        m = re.search(r"gObjectEventPic_\w+", body)
        if m:
            pictbl[sym] = m.group(0)

    pics = dict((s, p) for s, p in PIC_RE.findall(_read(*OEDIR, "object_event_graphics.h")))

    return pointers, info, pictbl, pics


def _extract_frame0(png_rel, w, h):
    img = Image.open(C.src(*png_rel.split("/")))
    src = img.crop((0, 0, w, h))
    pal = img.getpalette()
    if src.mode != "P" or pal is None:
        return src.convert("RGBA")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    for y in range(h):
        for x in range(w):
            i = sp[x, y]
            if i == 0:               # index 0 = transparent
                continue
            op[x, y] = (pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2], 255)
    return out


def extract_sprites(gfx_ids, out_dir):
    """Render frame 0 for each graphics id. Returns gfx_id -> {file, w, h}."""
    os.makedirs(out_dir, exist_ok=True)
    pointers, info, pictbl, pics = build_index()
    result = {}
    for gfx in sorted(gfx_ids):
        info_sym = pointers.get(gfx)
        if not info_sym or info_sym not in info:
            continue
        w, h, pictbl_sym = info[info_sym]
        pic_sym = pictbl.get(pictbl_sym)
        png = pics.get(pic_sym) if pic_sym else None
        if not png:
            continue
        try:
            frame = _extract_frame0(png, w, h)
        except Exception as e:
            print(f"  ! sprite {gfx}: {e}")
            continue
        fname = gfx.replace("OBJ_EVENT_GFX_", "") + ".png"
        frame.save(os.path.join(out_dir, fname))
        result[gfx] = {"file": fname, "w": w, "h": h}
    return result
