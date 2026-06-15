"""Extract party-Pokemon menu icons for the trainer team popups.

Chain (per party mon, keyed by its Showdown-style species name):
  "Geodude-Alola"
    -> SPECIES_GEODUDE_ALOLA            (normalised-name match against the
                                         species_info enum keys + species.h
                                         base-form aliases)
    -> .iconSprite = gMonIcon_X         (src/data/pokemon/species_info/*.h)
    -> graphics/pokemon/.../icon.png    (src/data/graphics/pokemon.h INCGFX_U8)

Form-only names that share a base folder's graphics and have no species_info
block of their own (Vivillon/Arceus/Florges/Minior/Mothim patterns) fall back
to graphics/pokemon/<base>/icon.png.

Each icon is a 32x64 two-frame vertical strip; frame 0 (top 32x32) is the
standing icon. Palette index 0 is transparent. The extracted RGBA icon is
written to site/img/pokemon/<KEY>.png and the filename is injected as a
"sprite" field on every mon in site/js/data/trainers.json.

Read-only against the game source; writes only under site/.
"""
import glob
import os
import re

from PIL import Image

import common as C

OUT_DIR = os.path.join(C.SITE, "img", "pokemon")

BLOCK_RE = re.compile(r"\[(SPECIES_\w+)\]\s*=\s*\{(.*?)\n    \},", re.DOTALL)
ICON_FIELD_RE = re.compile(r"\.iconSprite\s*=\s*(\w+)")
INCGFX_RE = re.compile(r"(gMonIcon_\w+)\[\]\s*=\s*INCGFX_U8\(\"([^\"]+)\"")
ALIAS_RE = re.compile(r"(SPECIES_\w+)\s*=\s*(SPECIES_\w+)\s*,")

# Showdown uses short regional tags; BPE/expansion enums sometimes use the long
# adjective form. Canonicalise both onto the short tag so they match.
_REGION = [("ALOLAN", "ALOLA"), ("GALARIAN", "GALAR"),
           ("HISUIAN", "HISUI"), ("PALDEAN", "PALDEA")]


def norm(name):
    """Species/enum name -> comparable key: alnum-only, upper, short regions."""
    s = re.sub(r"[^A-Za-z0-9]", "", name).upper()
    for long, short in _REGION:
        s = s.replace(long, short)
    return s


def _build_species_index():
    """norm(species name without SPECIES_) -> 'graphics/pokemon/.../icon.png'."""
    enum_icon = {}  # SPECIES_X -> gMonIcon_Y
    for f in glob.glob(C.src("src", "data", "pokemon", "species_info",
                             "gen_*_families.h")):
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for sp, body in BLOCK_RE.findall(text):
            m = ICON_FIELD_RE.search(body)
            if m:
                enum_icon[sp] = m.group(1)

    sym_png = {}  # gMonIcon_Y -> path (prefer the non-GBA-style asset)
    with open(C.src("src", "data", "graphics", "pokemon.h"),
              "r", encoding="utf-8", errors="replace") as fh:
        for sym, path in INCGFX_RE.findall(fh.read()):
            if "_gba" in path:
                sym_png.setdefault(sym, path)
            else:
                sym_png[sym] = path

    enum_png = {sp: sym_png[sym] for sp, sym in enum_icon.items()
                if sym in sym_png}

    with open(C.src("include", "constants", "species.h"),
              "r", encoding="utf-8", errors="replace") as fh:
        alias = dict(ALIAS_RE.findall(fh.read()))

    def resolve(sp, seen=()):
        if sp in enum_png:
            return enum_png[sp]
        if sp in alias and sp not in seen:
            return resolve(alias[sp], seen + (sp,))
        return None

    key_png = {}
    for sp in set(list(enum_png) + list(alias)):
        png = resolve(sp)
        if png:
            key_png.setdefault(norm(sp[len("SPECIES_"):]), png)
    return key_png


def _icon_path_for(name, key_png):
    """Resolve a Showdown species name to an icon.png path, or None."""
    png = key_png.get(norm(name))
    if png:
        return png
    # form-only / shared-graphics fallback: graphics/pokemon/<base>/icon.png
    base = re.split(r"[ \-]", name)[0].lower()
    cand = os.path.join("graphics", "pokemon", base, "icon.png")
    if os.path.isfile(C.src(cand)):
        return cand.replace(os.sep, "/")
    return None


def _extract_icon(png_path):
    """Frame 0 (top 32x32) of an icon strip -> RGBA, index 0 transparent."""
    img = Image.open(C.src(*png_path.split("/")))
    w = 32
    frame = img.crop((0, 0, w, w))
    pal = img.getpalette()
    if img.mode != "P" or pal is None:
        return frame.convert("RGBA")
    out = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    sp, op = frame.load(), out.load()
    for y in range(w):
        for x in range(w):
            c = sp[x, y]
            if c == 0:               # index 0 = transparent
                continue
            op[x, y] = (pal[c * 3], pal[c * 3 + 1], pal[c * 3 + 2], 255)
    return out


def annotate(trainers):
    """Extract icons for every party mon in `trainers` and set mon["sprite"].

    Mutates `trainers` in place (a {TRAINER_X: {...party...}} dict) and writes
    the icon PNGs to site/img/pokemon/. Returns (extracted_count, missing_set).
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    key_png = _build_species_index()
    cache = {}        # icon key -> filename (extract each unique icon once)
    missing = set()

    for t in trainers.values():
        for mon in t.get("party", []):
            species = mon.get("species")
            if not species:
                continue
            fkey = norm(species)
            fname = cache.get(fkey)
            if fname is None:
                path = _icon_path_for(species, key_png)
                if not path:
                    missing.add(species)
                    continue
                try:
                    _extract_icon(path).save(
                        os.path.join(OUT_DIR, fkey + ".png"))
                except Exception as e:  # pragma: no cover
                    print(f"  ! icon {species}: {e}")
                    missing.add(species)
                    continue
                fname = cache[fkey] = fkey + ".png"
            mon["sprite"] = fname
    return len(cache), missing


def _mon_lists(enc):
    """Yield every list-of-mons inside one map's encounter structure."""
    for key in ("land", "water", "rock_smash"):
        if isinstance(enc.get(key), dict) and enc[key].get("mons"):
            yield enc[key]["mons"]
    if isinstance(enc.get("fishing"), dict):
        for rod in enc["fishing"].values():
            if rod:
                yield rod


def annotate_encounters(maps):
    """Extract icons for every wild-encounter mon and set mon["sprite"].

    `maps` is the list of map entries from world.json; each may carry an
    "enc" block. Wild species are raw enum names (SPECIES_STARLY), so the
    SPECIES_ prefix is stripped before resolving — icons are keyed by the
    same norm() filename as trainer icons, so the two share PNG files.
    Writes any new icon PNGs to site/img/pokemon/. Returns (new_count, missing).
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    key_png = _build_species_index()
    cache = {}        # icon key -> filename
    missing = set()

    for m in maps:
        enc = m.get("enc")
        if not enc:
            continue
        for mons in _mon_lists(enc):
            for mon in mons:
                species = mon.get("species")
                if not species:
                    continue
                bare = species[len("SPECIES_"):] if \
                    species.startswith("SPECIES_") else species
                fkey = norm(bare)
                fname = cache.get(fkey)
                if fname is None:
                    if fkey in cache:
                        continue
                    path = _icon_path_for(bare, key_png)
                    out_file = os.path.join(OUT_DIR, fkey + ".png")
                    if not path:
                        missing.add(species)
                        cache[fkey] = None
                        continue
                    if not os.path.isfile(out_file):
                        try:
                            _extract_icon(path).save(out_file)
                        except Exception as e:  # pragma: no cover
                            print(f"  ! icon {species}: {e}")
                            missing.add(species)
                            cache[fkey] = None
                            continue
                    fname = cache[fkey] = fkey + ".png"
                if fname:
                    mon["sprite"] = fname
    new_count = sum(1 for v in cache.values() if v)
    return new_count, missing


def main():
    C.ensure_dirs()
    trainers_path = os.path.join(C.SITE_DATA, "trainers.json")
    trainers = C.load_json(trainers_path)
    count, missing = annotate(trainers)
    C.write_json(trainers_path, trainers)
    print(f"Extracted {count} Pokemon icons "
          f"-> {os.path.relpath(OUT_DIR, C.SITE)}")
    if missing:
        print(f"  {len(missing)} species without an icon: "
              + ", ".join(sorted(missing)))
    return count


if __name__ == "__main__":
    main()
