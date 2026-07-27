"""
Verifier for an OW sprite import.

    py BPETools/sprite_import/verify_ow_sprite.py <name>

Checks PNG encoding, PLTE-vs-.pal alignment and GBA 5-bit cleanliness, then --
if the ROM has been built since the swap -- decodes the BUILT .4bpp + .gbapal
and diffs them against the source PNG. Exits non-zero on any failure.

Run this after import_ow_sprite.py AND after `make`; a clean build alone does
not prove the sprite is right (misaligned PLTE/.pal builds fine but renders
with scrambled colours in game).
"""
from PIL import Image, ImageChops
import sys, os, struct

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)
name = sys.argv[1]
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(R, "BPETools", "sprite_import", "_previews")
os.makedirs(OUT, exist_ok=True)
PNG = os.path.join(R, "graphics", "object_events", "pics", "people", f"{name}.png")
PAL = os.path.join(R, "graphics", "object_events", "palettes", f"{name}.pal")
BPP = os.path.join(R, "build", "assets", "graphics", "object_events", "pics", "people",
                   f"{name}.png_mwidth_4__mheight_4.4bpp")
GPAL = os.path.join(R, "build", "assets", "graphics", "object_events", "palettes", f"{name}.pal.gbapal")

ok = True
def check(label, cond, detail=""):
    global ok
    ok = ok and cond
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")

print(f"=== {name} ===")

# --- PNG encoding ---
with open(PNG, "rb") as f: data = f.read()
off, ihdr, plte_n = 8, None, None
while off < len(data):
    ln = struct.unpack(">I", data[off:off+4])[0]; typ = data[off+4:off+8]
    if typ == b"IHDR": ihdr = struct.unpack(">IIBBBBB", data[off+8:off+8+ln])
    elif typ == b"PLTE": plte_n = ln // 3
    off += 12 + ln
    if typ == b"IEND": break
w, h, bd, ct = ihdr[0], ihdr[1], ihdr[2], ihdr[3]
check("PNG is 288x32", (w, h) == (288, 32), f"{w}x{h}")
check("PNG bit depth 4", bd == 4, str(bd))
check("PNG colortype 3 (palette)", ct == 3, str(ct))
check("PLTE has exactly 16 entries", plte_n == 16, str(plte_n))

png = Image.open(PNG)
used = sorted({p for p in png.getdata()})
check("max index <= 15", max(used) <= 15, f"max={max(used)}")

# --- .pal ---
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

bad5 = [c for c in pal if any(v & 7 for v in c)]
check("all colours GBA 5-bit clean", not bad5, str(bad5))

# --- built artifacts ---
if not (os.path.exists(BPP) and os.path.exists(GPAL)):
    print("  [SKIP] build artifacts not present yet")
    sys.exit(0 if ok else 1)

tiles = open(BPP, "rb").read(); palb = open(GPAL, "rb").read()
check(".4bpp is 4608 bytes (9 frames x 16 tiles)", len(tiles) == 4608, str(len(tiles)))
check(".gbapal is 32 bytes (16 entries)", len(palb) == 32, str(len(palb)))

gpal = []
for i in range(16):
    v = struct.unpack("<H", palb[i*2:i*2+2])[0]
    gpal.append((((v) & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3))
check(".gbapal round-trips to the .pal colours", gpal == pal,
      str([(i, pal[i], gpal[i]) for i in range(16) if pal[i] != gpal[i]]))

def tile_px(idx, x, y):
    b = tiles[idx*32 + y*4 + (x >> 1)]
    return (b & 0x0F) if (x & 1) == 0 else (b >> 4)

# Compare PALETTE INDICES directly, never ImageChops.difference().getbbox().
# On RGBA images getbbox() keys on the ALPHA channel only (Pillow >=9.2), so two
# images with the same silhouette but totally different colours compare "equal"
# -- that made this check silently pass no matter what. Index comparison is both
# unambiguous and strictly stronger.
sp = png.load()
bad = []
for m in range(9):
    for ty in range(4):
        for tx in range(4):
            t = m*16 + ty*4 + tx
            for y in range(8):
                for x in range(8):
                    gx, gy = m*32 + tx*8 + x, ty*8 + y
                    i, j = tile_px(t, x, y), sp[gx, gy]
                    if i != j:
                        bad.append((gx, gy, j, i))
check("built .4bpp indices match the source PNG exactly",
      not bad, f"{len(bad)}/9216 differ, first={bad[:3]}")

img = Image.new("RGBA", (288, 32), (0, 0, 0, 0)); ip = img.load()
for m in range(9):
    for ty in range(4):
        for tx in range(4):
            t = m*16 + ty*4 + tx
            for y in range(8):
                for x in range(8):
                    i = tile_px(t, x, y)
                    ip[m*32 + tx*8 + x, ty*8 + y] = (0,0,0,0) if i == 0 else (*gpal[i], 255)

SC = 5
bg = Image.new("RGBA", (288*SC, 32*SC), (110, 110, 118, 255))
bg.alpha_composite(img.resize((288*SC, 32*SC), Image.NEAREST))
bg.convert("RGB").save(os.path.join(OUT, f"{name}_from_rom.png"))
print(f"\nwrote {name}_from_rom.png")
print("\nRESULT:", "ALL CHECKS PASS" if ok else "*** FAILURES ***")
sys.exit(0 if ok else 1)
