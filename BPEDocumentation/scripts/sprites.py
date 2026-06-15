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
# pic tables are named sPicTable_X (vanilla) or gObjectEventPicTable_X
# (custom/expansion); both contain "PicTable".
PICTBL_RE = re.compile(r"(\w*PicTable\w*)\[\]\s*=\s*\{(.*?)\};", re.DOTALL)
PIC_RE = re.compile(r"(gObjectEventPic_\w+)\[\]\s*=\s*INCGFX_\w+\(\"([^\"]+)\"")


def _read(*parts):
    p = C.src(*parts)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def build_index():
    pointers = dict(PTR_RE.findall(_read(*OEDIR, "object_event_graphics_info_pointers.h")))

    info = {}  # 'gObjectEventGraphicsInfo_X' -> (w, h, picTableSymbol)
    info_text = _read(*OEDIR, "object_event_graphics_info.h")
    for name, body in INFO_RE.findall(info_text):
        w = re.search(r"\.width\s*=\s*(\d+)", body)
        h = re.search(r"\.height\s*=\s*(\d+)", body)
        img = re.search(r"\.images\s*=\s*(\w+)", body)
        if w and h and img:
            info["gObjectEventGraphicsInfo_" + name] = (
                int(w.group(1)), int(h.group(1)), img.group(1))
    # macro form (Sinnoh/Unova E4 cameos etc.): expands to a 32x32 info whose
    # .images = sPicTable_<name>
    for name in re.findall(
            r"gObjectEventGraphicsInfo_(\w+)\s*=\s*DS_STYLE_OW_GRAPHICS_INFO\("
            r"\s*(\w+)", info_text):
        info["gObjectEventGraphicsInfo_" + name[0]] = (32, 32,
                                                       "sPicTable_" + name[1])

    pictbl = {}  # 'sPicTable_X' -> 'gObjectEventPic_X'
    for sym, body in PICTBL_RE.findall(_read(*OEDIR, "object_event_pic_tables.h")):
        m = re.search(r"gObjectEventPic_\w+", body)
        if m:
            pictbl[sym] = m.group(0)

    pics = dict((s, p) for s, p in PIC_RE.findall(_read(*OEDIR, "object_event_graphics.h")))

    return pointers, info, pictbl, pics


# Standard overworld people frame order: 0 = south(down), 1 = north(up),
# 2 = west(left); east(right) is west flipped horizontally.
DIR_FRAME = {"down": 0, "up": 1, "left": 2}


def _extract_frame(img, pal, i, w, h):
    """Frame i of a horizontal sprite strip, index 0 transparent -> RGBA."""
    src = img.crop((i * w, 0, i * w + w, h))
    if img.mode != "P" or pal is None:
        return src.convert("RGBA")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    for y in range(h):
        for x in range(w):
            c = sp[x, y]
            if c == 0:               # index 0 = transparent
                continue
            op[x, y] = (pal[c * 3], pal[c * 3 + 1], pal[c * 3 + 2], 255)
    return out


def extract_sprites(gfx_ids, out_dir):
    """Render the four facing frames (down/up/left/right) per graphics id.

    Returns gfx_id -> {w, h, dirs: {down, up, left, right: filename}}.
    Sprites with fewer frames fall back to frame 0 for missing directions.
    """
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
            img = Image.open(C.src(*png.split("/")))
            pal = img.getpalette()
            nframes = max(1, img.width // w)
            base = gfx.replace("OBJ_EVENT_GFX_", "")
            dirs = {}
            for d, idx in DIR_FRAME.items():
                frame = _extract_frame(img, pal, idx if idx < nframes else 0,
                                       w, h)
                fname = f"{base}_{d}.png"
                frame.save(os.path.join(out_dir, fname))
                dirs[d] = fname
            # east = west flipped (or frame 0 flipped if no west frame)
            east_src = _extract_frame(img, pal, 2 if 2 < nframes else 0, w, h)
            east = east_src.transpose(Image.FLIP_LEFT_RIGHT)
            fname = f"{base}_right.png"
            east.save(os.path.join(out_dir, fname))
            dirs["right"] = fname
        except Exception as e:
            print(f"  ! sprite {gfx}: {e}")
            continue
        result[gfx] = {"w": w, "h": h, "dirs": dirs}
    return result
