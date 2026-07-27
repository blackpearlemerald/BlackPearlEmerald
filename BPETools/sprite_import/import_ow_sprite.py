"""
Import a community/ripped overworld NPC sprite sheet into BPE's OW sprite format.

    py import_ow_sprite.py <sheet.png> <name> [--dry-run]

Produces graphics/object_events/pics/people/<name>.png (288x32, 9 frames of
32x32, 4bpp, 16-colour PLTE) and graphics/object_events/palettes/<name>.pal,
which is a pure asset swap -- no C changes needed.

Assumes the common DS-style source layout: 4 columns (anim frames) x 4 rows
(down, left, right, up), where col0 == col2 is the standing pose. VERIFY that
against the actual sheet before trusting the output -- run with --dry-run first,
it reports the detected grid, which rows mirror each other, and per-row previews.

Validated on shauntal (clean 2x) and marshal (near-2x + stray column), 2026-07-27.
See the `overworld-sprite-import-pipeline` note for the full rationale.
"""
from PIL import Image, ImageChops
from collections import Counter
import sys, os, itertools

TRANSPARENT = (16, 128, 112)   # repo convention: palette index 0
CELL = 32                      # 32x32 frame cell
TARGET_BOTTOM = 30             # feet row; Unova cameos use 30, Sinnoh 29
MAX_COLORS = 15

# emerald 9-frame order -> (source col, source row)
FRAME_MAP = [
    ((0, 0), "0 face south"), ((0, 3), "1 face north"), ((0, 1), "2 face west"),
    ((1, 0), "3 go south A"), ((3, 0), "4 go south B"),
    ((1, 3), "5 go north A"), ((3, 3), "6 go north B"),
    ((1, 1), "7 go west A"),  ((3, 1), "8 go west B"),
]


def load_and_crop(path):
    im = Image.open(path).convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y][3] == 0:
                px[x, y] = (0, 0, 0, 0)
    # trim stray fully-empty edge rows/cols (sheets are often 1px off)
    bbox = im.getchannel("A").point(lambda a: 255 if a else 0).getbbox()
    w = im.width - (im.width % 4)
    h = im.height - (im.height % 4)
    if (w, h) != im.size:
        # only trim if what we drop is genuinely empty
        if bbox and bbox[2] <= w and bbox[3] <= h:
            print(f"  cropping {im.size} -> ({w}, {h}) (stray empty edge)")
            im = im.crop((0, 0, w, h))
        else:
            print(f"  WARNING: {im.size} not divisible by 4 and the excess is NOT empty")
    return im


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def to_native(sheet):
    """2x-downscale if the sheet is (near-)2x; majority vote, ties -> darker."""
    W, H = sheet.size
    px = sheet.load()
    bad = 0
    for y in range(0, H - 1, 2):
        for x in range(0, W - 1, 2):
            if not (px[x, y] == px[x+1, y] == px[x, y+1] == px[x+1, y+1]):
                bad += 1
    total = (W // 2) * (H // 2)
    pct = 100.0 * bad / total
    print(f"  2x-block check: {bad}/{total} mismatched ({pct:.2f}%)")
    if pct > 5.0:
        print("  -> treating as NATIVE resolution (no downscale)")
        return sheet
    print("  -> 2x upscale; downscaling with majority-vote (ties -> darker)")
    out = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    op = out.load()
    for y in range(0, H - 1, 2):
        for x in range(0, W - 1, 2):
            q = [px[x, y], px[x+1, y], px[x, y+1], px[x+1, y+1]]
            opq = [p for p in q if p[3] == 255]
            if not opq:
                continue
            cnt = Counter(opq)
            top = max(cnt.values())
            op[x // 2, y // 2] = min([k for k, v in cnt.items() if v == top], key=lum)
    return out


def gba(c):
    return ((c[0] >> 3) << 3, (c[1] >> 3) << 3, (c[2] >> 3) << 3)


def dist(a, b):
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return 2 * dr * dr + 4 * dg * dg + 3 * db * db


def build_palette(frames):
    counts = {}
    for f in frames:
        for p in f.getdata():
            if p[3] >= 128:
                g = gba(p)
                counts[g] = counts.get(g, 0) + 1
    print(f"  opaque colours after GBA 5-bit quantise: {len(counts)}")
    remap = {c: c for c in counts}
    worst = 0
    while len(counts) > MAX_COLORS:
        cols = list(counts)
        best = None
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                d = dist(cols[i], cols[j])
                if best is None or d < best[0]:
                    best = (d, cols[i], cols[j])
        d, a, b = best
        loser, winner = (a, b) if counts[a] <= counts[b] else (b, a)
        worst = max(worst, d)
        print(f"    merge {loser} -> {winner}  dist={d} ({counts[loser]}px)")
        counts[winner] += counts.pop(loser)
        for k, v in remap.items():
            if v == loser:
                remap[k] = winner
    print(f"  final {len(counts)} colours, worst merge distance {worst}")
    ordered = [TRANSPARENT] + [c for c, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return ordered, remap


def report_layout(native, NFW, NFH):
    def fr(c, r):
        return native.crop((c * NFW, r * NFH, c * NFW + NFW, r * NFH + NFH))

    # NEVER use ImageChops.difference().getbbox() here: on RGBA it keys on the
    # ALPHA channel only (Pillow >=9.2), so two frames with the same silhouette
    # but completely different colours compare "identical" and every layout
    # conclusion below silently becomes garbage. Count differing pixels instead,
    # and report the count -- near-identical (0-2px) is the useful signal, since
    # artists often hand-tweak a pixel or two in the repeated stand frame.
    def diffpx(a, b):
        if a.size != b.size:
            return 10 ** 6
        pa, pb = a.load(), b.load()
        return sum(1 for y in range(a.height) for x in range(a.width) if pa[x, y] != pb[x, y])

    print("  column pairwise differing pixels (the repeated STAND pose shows ~0):")
    for r in range(4):
        parts = [f"c{a}/c{b}={diffpx(fr(a, r), fr(b, r))}" for a, b in itertools.combinations(range(4), 2)]
        tops = []
        for c in range(4):
            bb = fr(c, r).getchannel("A").point(lambda v: 255 if v else 0).getbbox()
            tops.append(bb[1] if bb else -1)
        print(f"    row{r}: " + "  ".join(parts) + f"   | content-top per col {tops}")
    print("  mirror pairs (identifies the left/right rows):")
    for a, b in itertools.combinations(range(4), 2):
        hits = [c for c in range(4)
                if diffpx(fr(c, a), fr(c, b).transpose(Image.FLIP_LEFT_RIGHT)) <= 2]
        if hits:
            print(f"    row{a} ~= mirror(row{b}) on cols {hits}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    src, name = args[0], args[1]
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    print(f"source: {src}")
    sheet = load_and_crop(src)
    native = to_native(sheet)
    NFW, NFH = native.width // 4, native.height // 4
    print(f"  native frame: {NFW}x{NFH}")

    report_layout(native, NFW, NFH)

    frames = [native.crop((c * NFW, r * NFH, c * NFW + NFW, r * NFH + NFH))
              for (c, r), _ in FRAME_MAP]

    stand = frames[0]
    bb = stand.getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox()
    print(f"  down-stand content {bb} -> w={bb[2]-bb[0]} h={bb[3]-bb[1]}"
          f"   (a correct human NPC is ~12-18 wide, ~19-21 tall)")

    ordered, remap = build_palette(frames)

    y_off = TARGET_BOTTOM - (bb[3] - 1)
    x_off = (CELL - NFW) // 2
    print(f"  paste offset x={x_off} y={y_off}")

    out = Image.new("P", (CELL * 9, CELL), 0)
    flat = []
    for c in ordered:
        flat += list(c)
    flat += [0, 0, 0] * (16 - len(ordered))
    out.putpalette(flat)
    op = out.load()
    index_of = {c: i for i, c in enumerate(ordered)}
    clipped = 0
    for i, f in enumerate(frames):
        fp = f.load()
        for y in range(NFH):
            for x in range(NFW):
                r, g, b, a = fp[x, y]
                if a < 128:
                    continue
                gx, gy = i * CELL + x_off + x, y_off + y
                if 0 <= gx - i * CELL < CELL and 0 <= gy < CELL:
                    op[gx, gy] = index_of[remap[gba((r, g, b))]]
                else:
                    clipped += 1
    # never let this pass silently -- a sprite too tall for the 32x32 cell would
    # otherwise lose its head or feet and still build + verify cleanly
    print(f"  pixels clipped by the 32x32 cell: {clipped}" + ("" if clipped == 0 else "   *** ART IS BEING LOST ***"))

    png_path = os.path.join(repo, "graphics", "object_events", "pics", "people", f"{name}.png")
    pal_path = os.path.join(repo, "graphics", "object_events", "palettes", f"{name}.pal")
    if dry:
        print(f"\n[dry-run] would write:\n  {png_path}\n  {pal_path}")
        return
    out.save(png_path, bits=4)
    lines = ["JASC-PAL", "0100", "16"]
    for i in range(16):
        c = ordered[i] if i < len(ordered) else (0, 0, 0)
        lines.append(f"{c[0]} {c[1]} {c[2]}")
    with open(pal_path, "w", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nwrote {png_path}\nwrote {pal_path}")
    print(f"now run:  py BPETools/sprite_import/verify_ow_sprite.py {name}")


if __name__ == "__main__":
    main()
