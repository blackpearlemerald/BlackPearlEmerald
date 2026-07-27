"""
Verifier for a trainer battle FRONT PIC import.

    py BPETools/sprite_import/verify_trainer_pic.py <name>      e.g. elite_four_drasna

Checks PNG encoding, PLTE-vs-.pal alignment and GBA 5-bit cleanliness, then --
if the ROM has been built since -- decodes the built .4bpp back to palette
indices and diffs against the source PNG. Exits non-zero on any failure.

Front pics are hard-locked to 64x64 (every one of the 227 in this repo is), so
a taller source MUST be scaled down before import, not cropped.

NOTE: never compare images with ImageChops.difference(a,b).getbbox() -- on RGBA
that keys on the ALPHA channel only (Pillow >=9.2) and silently passes even when
every colour differs. Compare palette indices, as below.
"""
from PIL import Image
import sys, os, struct

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)
name = sys.argv[1]
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PNG = os.path.join(R, "graphics", "trainers", "front_pics", f"{name}.png")
PAL = os.path.join(R, "graphics", "trainers", "palettes", f"{name}.pal")
BPP = os.path.join(R, "build", "assets", "graphics", "trainers", "front_pics", f"{name}.png.4bpp")

ok = True
def check(label, cond, detail=""):
    global ok
    ok = ok and cond
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")

print(f"=== {name} (trainer front pic) ===")

with open(PNG, "rb") as f:
    data = f.read()
off, ihdr, plte_n = 8, None, None
while off < len(data):
    ln = struct.unpack(">I", data[off:off+4])[0]; typ = data[off+4:off+8]
    if typ == b"IHDR": ihdr = struct.unpack(">IIBBBBB", data[off+8:off+8+ln])
    elif typ == b"PLTE": plte_n = ln // 3
    off += 12 + ln
    if typ == b"IEND": break
w, h, bd, ct = ihdr[0], ihdr[1], ihdr[2], ihdr[3]
check("PNG is 64x64", (w, h) == (64, 64), f"{w}x{h}")
check("PNG bit depth 4", bd == 4, str(bd))
check("PNG colortype 3 (palette)", ct == 3, str(ct))
check("PLTE has exactly 16 entries", plte_n == 16, str(plte_n))

png = Image.open(PNG)
used = sorted({p for p in png.getdata()})
check("max index <= 15", max(used) <= 15, f"max={max(used)}")

raw = open(PAL, "rb").read()
check(".pal uses CRLF", b"\r\n" in raw)
lines = [l for l in raw.decode().replace("\r\n", "\n").split("\n") if l.strip()]
check(".pal header", lines[0] == "JASC-PAL" and lines[2] == "16", f"{lines[0]}/{lines[2]}")
pal = [tuple(int(v) for v in l.split()) for l in lines[3:19]]
check(".pal has 16 entries", len(pal) == 16, str(len(pal)))
check("index 0 is the transparent teal", pal[0] == (16, 128, 112), str(pal[0]))

plte = png.getpalette()[:48]
embedded = [tuple(plte[i*3:i*3+3]) for i in range(16)]
mism = [i for i in range(16) if embedded[i] != pal[i]]
check("PNG PLTE == .pal entry-for-entry", not mism, f"mismatch at {mism}")
check("all colours GBA 5-bit clean", not [c for c in pal if any(v & 7 for v in c)], "")

q = png.load()
xs = [x for y in range(64) for x in range(64) if q[x, y] != 0]
ys = [y for y in range(64) for x in range(64) if q[x, y] != 0]
print(f"  content x[{min(xs)}..{max(xs)}] y[{min(ys)}..{max(ys)}] "
      f"-> {max(xs)-min(xs)+1}x{max(ys)-min(ys)+1}  (peers sit ~59-62 tall, bottom at y=63)")
check("bottom-aligned near y=63", max(ys) >= 61, f"bottom={max(ys)}")

if not os.path.exists(BPP):
    print("  [SKIP] build artifact not present yet (run make)")
    sys.exit(0 if ok else 1)

tiles = open(BPP, "rb").read()
check(".4bpp is 2048 bytes (64 tiles)", len(tiles) == 2048, str(len(tiles)))

def tile_px(idx, x, y):
    b = tiles[idx*32 + y*4 + (x >> 1)]
    return (b & 0x0F) if (x & 1) == 0 else (b >> 4)

bad = []
for ty in range(8):
    for tx in range(8):
        t = ty*8 + tx
        for y in range(8):
            for x in range(8):
                gx, gy = tx*8 + x, ty*8 + y
                i, j = tile_px(t, x, y), q[gx, gy]
                if i != j:
                    bad.append((gx, gy, j, i))
check("built .4bpp indices match the source PNG exactly",
      not bad, f"{len(bad)}/4096 differ, first={bad[:3]}")

print("\nRESULT:", "ALL CHECKS PASS" if ok else "*** FAILURES ***")
sys.exit(0 if ok else 1)
