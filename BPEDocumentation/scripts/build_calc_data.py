"""Build the Dynamic-Calc data source for BPE Emerald.

Reads the already-parsed BPE documentation data (species/*.json, moves.json,
abilities.json, trainers.json, world.json) and writes:

  site/calc/data/bpe_calc_data.json   -- the npoint-schema blob the calc loads
  site/calc/img/newhd/<name>.png      -- Pokemon sprites named to the calc's
                                         JS sprite-name convention (copied from
                                         BPE's own img/pokemon sprites)

Schema mirrors the working Dynamic-Calc npoint example (Blaze Black):
  poks[ShowdownName]            = {bs, types, abilities, weightkg, learnset_info}
  moves[Move Name]             = {type, category, basePower}
  formatted_sets[Species][key] = {tr_id, sub_index, level, moves, item, ability,
                                  nature, evs, ivs, sprite, battle_type, ...}

Run:  py BPEDocumentation/scripts/build_calc_data.py
"""
import json
import os
import re
import shutil
import sys

import common

SITE = common.SITE
SPECIES_DIR = os.path.join(SITE, "data", "species")
MOVES_JSON = os.path.join(SITE, "data", "moves.json")
ABIL_JSON = os.path.join(SITE, "data", "abilities.json")
TRAINERS_JSON = os.path.join(SITE, "js", "data", "trainers.json")
WORLD_JSON = os.path.join(SITE, "js", "data", "world.json")

CALC_DIR = os.path.join(SITE, "calc")
OUT_JSON = os.path.join(CALC_DIR, "data", "bpe_calc_data.json")
NEWHD_DIR = os.path.join(CALC_DIR, "img", "newhd")

# ── Name helpers ──────────────────────────────────────────────────────────────

# Internal form suffix -> Showdown form token. Longest suffixes first so that
# e.g. _MEGA_X is matched before _MEGA and _PALDEA_BLAZE before _PALDEAN.
FORM_TOKENS = [
    ("_MEGA_X", "Mega-X"), ("_MEGA_Y", "Mega-Y"), ("_MEGA", "Mega"),
    ("_PRIMAL", "Primal"),
    ("_GIGANTAMAX", "Gmax"), ("_GMAX", "Gmax"),
    ("_ALOLA", "Alola"), ("_GALAR", "Galar"), ("_HISUI", "Hisui"),
    ("_PALDEA_BLAZE", "Paldea-Blaze"), ("_PALDEA_AQUA", "Paldea-Aqua"),
    ("_PALDEA_COMBAT", "Paldea-Combat"), ("_PALDEAN", "Paldea"),
    ("_HEAT", "Heat"), ("_WASH", "Wash"), ("_MOW", "Mow"),
    ("_FROST", "Frost"), ("_FAN", "Fan"),
    ("_ORIGIN", "Origin"), ("_THERIAN", "Therian"), ("_INCARNATE", "Incarnate"),
    ("_SKY", "Sky"), ("_SANDY", "Sandy"), ("_TRASH", "Trash"),
    ("_RAINY", "Rainy"), ("_SNOWY", "Snowy"), ("_SUNSHINE", "Sunshine"),
    ("_ATTACK", "Attack"), ("_DEFENSE", "Defense"), ("_SPEED", "Speed"),
    ("_DUSK_MANE", "Dusk-Mane"), ("_DAWN_WINGS", "Dawn-Wings"),
    ("_ULTRA", "Ultra"), ("_CROWNED", "Crowned"),
    ("_PIROUETTE", "Pirouette"), ("_RESOLUTE", "Resolute"),
    ("_LOW_KEY", "Low-Key"), ("_AMPED", "Amped"),
    ("_SUMMER", "Summer"), ("_AUTUMN", "Autumn"), ("_WINTER", "Winter"),
    ("_SPRING", "Spring"), ("_BLOODMOON", "Bloodmoon"), ("_HERO", "Hero"),
]

# Explicit overrides keyed by internal species id (irregular Showdown spellings).
NAME_OVERRIDES = {
    "NIDORAN_F": "Nidoran-F",
    "NIDORAN_M": "Nidoran-M",
    "KOMMO_O": "Kommo-o",
    "FARFETCHD": "Farfetch'd",
    "SIRFETCHD": "Sirfetch'd",
    "TYPE_NULL": "Type: Null",
    "MR_MIME": "Mr. Mime",
    "MR_MIME_GALAR": "Mr. Mime-Galar",
    "MR_RIME": "Mr. Rime",
    "MIME_JR": "Mime Jr.",
    "HO_OH": "Ho-Oh",
    "PORYGON_Z": "Porygon-Z",
}


def normalize(s):
    """Showdown-style id: strip every non-alphanumeric, lowercase."""
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()


def canon_name(internal_id, display_name):
    """Compute the Showdown species name from internal id + base display name."""
    if internal_id in NAME_OVERRIDES:
        return NAME_OVERRIDES[internal_id]
    base = display_name
    for suffix, token in FORM_TOKENS:
        if internal_id.endswith(suffix):
            return "%s-%s" % (base, token)
    return base


def js_sprite_name(showdown_name):
    """Replicate the calc's JS transform used to build sprite filenames:
    name.toLowerCase().replace(" ","-").replace(".","").replace("’","").replace(":","-")
    NOTE: JS String.replace(str, str) only replaces the FIRST occurrence."""
    s = showdown_name.lower()
    s = s.replace(" ", "-", 1)
    s = s.replace(".", "", 1)
    s = s.replace("’", "", 1)
    s = s.replace(":", "-", 1)
    return s


def title_word(w):
    return w[:1].upper() + w[1:].lower() if w else w


# ── Stat / field mapping ──────────────────────────────────────────────────────

BS_MAP = [("hp", "hp"), ("atk", "at"), ("def", "df"),
          ("spa", "sa"), ("spd", "sd"), ("spe", "sp")]


def map_base_stats(bs):
    return {short: bs[long] for long, short in BS_MAP}


def main():
    species_files = sorted(
        f for f in os.listdir(SPECIES_DIR) if f.endswith(".json"))
    moves_data = common.load_json(MOVES_JSON)
    abil_data = common.load_json(ABIL_JSON)
    trainers = common.load_json(TRAINERS_JSON)

    # move id -> Showdown display name
    move_name = {mid: m.get("name", mid) for mid, m in moves_data.items()}

    # ── poks ─────────────────────────────────────────────────────────────────
    poks = {}
    norm_index = {}   # normalize(name) -> ShowdownName (for trainer matching)
    sprite_src_for = {}  # ShowdownName -> site-relative sprite path

    for fn in species_files:
        sid = fn[:-5]
        d = common.load_json(os.path.join(SPECIES_DIR, fn))
        name = canon_name(sid, d["name"])
        if name in poks:
            # keep first; alt/totem dupes fall through to the base entry
            continue

        abilities = {}
        slot_keys = ["0", "1", "H"]
        for i, ab in enumerate(d.get("abilities", [])):
            if ab:
                an = abil_data.get(ab, {}).get("name")
                if an:
                    abilities[slot_keys[i] if i < 3 else str(i)] = an

        tms = []
        for mid in (d.get("tmMoves", []) + d.get("tutorMoves", [])
                    + d.get("hmMoves", [])):
            mn = move_name.get(mid)
            if mn and mn not in tms:
                tms.append(mn)
        learnset = []
        for lm in d.get("levelUpMoves", []):
            mn = move_name.get(lm["move"])
            if mn:
                learnset.append([lm["level"], mn])

        entry = {
            "bs": map_base_stats(d["baseStats"]),
            "types": [title_word(t) for t in d.get("types", [])],
            "learnset_info": {"tms": tms, "learnset": learnset},
        }
        if abilities:
            entry["abilities"] = abilities
        if d.get("weight") is not None:
            entry["weightkg"] = round(d["weight"] / 10.0, 1)
        poks[name] = entry
        norm_index[normalize(name)] = name
        norm_index.setdefault(normalize(sid), name)
        if d.get("sprite"):
            sprite_src_for[name] = d["sprite"].replace("/", os.sep)

    # ── moves ────────────────────────────────────────────────────────────────
    # NOTE: the doc's moves.json carries power=0 for ~100 damaging moves
    # (Flamethrower, Thunderbolt, Surf, ...) — a parse artifact, not a BPE
    # rebalance. The calc copies basePower unconditionally, so emitting those
    # would zero out their damage. We only override moves with a real power and
    # let the calc's accurate built-in Gen 9 data fill in the rest.
    out_moves = {}
    for mid, m in moves_data.items():
        nm = m.get("name")
        if not nm or nm == "-":
            continue
        power = m.get("power", 0) or 0
        if power <= 0:
            continue
        out_moves[nm] = {
            "type": title_word(m["type"]),
            "category": title_word(m["category"]),
            "basePower": power,
        }

    # ── formatted_sets (trainer teams, grouped by tr_id) ──────────────────────
    # Each trainer needs a UNIQUE label: the calc isolates a trainer's team by
    # the label in the set name, and BPE has hundreds of duplicate names
    # ("GRUNT"). Non-unique labels would both break team grouping and collide
    # in formatted_sets[species] (overwriting sets). We disambiguate repeats by
    # appending an incrementing number, mirroring upstream ("Grunt6").
    formatted_sets = {}
    unmatched = set()
    tr_id = 0
    label_counts = {}
    EV_KEYS = [("hp", "hp"), ("atk", "at"), ("def", "df"),
               ("spa", "sa"), ("spd", "sd"), ("spe", "sp")]

    for internal_tid in sorted(trainers.keys()):
        t = trainers[internal_tid]
        party = t.get("party") or []
        if not party or internal_tid == "TRAINER_NONE":
            continue
        tr_id += 1
        base_label = ("%s %s" % (t.get("class", ""), t.get("name", ""))).strip() \
            or "Trainer"
        label_counts[base_label] = label_counts.get(base_label, 0) + 1
        label = base_label if label_counts[base_label] == 1 \
            else "%s %d" % (base_label, label_counts[base_label])
        trainer_sprite = ("../img/sprites/%s" % t["pic"].replace(" ", "_")) \
            if t.get("pic") else None

        for sub_index, mon in enumerate(party):
            sp = mon.get("species")
            if not sp:
                continue
            # resolve to a poks key; fall back to the raw string (built-in dex)
            key = norm_index.get(normalize(sp), sp)
            if normalize(sp) not in norm_index:
                unmatched.add(sp)

            evs = {}
            for long, short in EV_KEYS:
                if mon.get("evs", {}).get(long):
                    evs[short] = mon["evs"][long]
            set_data = {
                "tr_id": tr_id,
                "sub_index": sub_index,
                "level": mon.get("level", 50),
                "moves": [m for m in (mon.get("moves") or []) if m] or ["-"],
                "nature": mon.get("nature", "Hardy"),
                "evs": evs,
                "ivs": {},
                "form": 0,
                "noCh": False,
                "battle_type": "Singles",
                "reward_item": "None",
            }
            if mon.get("ability"):
                set_data["ability"] = mon["ability"]
            if mon.get("item"):
                set_data["item"] = mon["item"]
            if trainer_sprite:
                set_data["sprite"] = trainer_sprite

            sets = formatted_sets.setdefault(key, {})
            set_name = "Lvl %d %s " % (set_data["level"], label)
            # ensure uniqueness within this species (same name/level trainers,
            # or a trainer carrying two of the same species)
            uniq = set_name
            n = 2
            while uniq in sets:
                uniq = "Lvl %d %s (%d) " % (set_data["level"], label, n)
                n += 1
            sets[uniq] = set_data

    blob = {
        "title": "BPE Emerald",
        "poks": poks,
        "moves": out_moves,
        "formatted_sets": formatted_sets,
    }
    common.write_json(OUT_JSON, blob)

    # ── sprites: copy BPE pokemon sprites into calc/img/newhd named per JS ─────
    if os.path.isdir(NEWHD_DIR):
        shutil.rmtree(NEWHD_DIR)
    os.makedirs(NEWHD_DIR, exist_ok=True)
    copied = missing = 0
    missing_names = []
    for name in poks:
        rel = sprite_src_for.get(name)
        src = os.path.join(SITE, rel) if rel else None
        if src and os.path.exists(src):
            dst = os.path.join(NEWHD_DIR, js_sprite_name(name) + ".png")
            shutil.copyfile(src, dst)
            copied += 1
        else:
            missing += 1
            if len(missing_names) < 20:
                missing_names.append((name, rel or "(no sprite field)"))

    # ── report ────────────────────────────────────────────────────────────────
    print("Wrote %s" % OUT_JSON)
    print("  poks:           %d" % len(poks))
    print("  moves:          %d" % len(out_moves))
    print("  trainers:       %d" % tr_id)
    print("  set species:    %d" % len(formatted_sets))
    print("Sprites -> %s" % NEWHD_DIR)
    print("  copied:  %d   missing: %d" % (copied, missing))
    if missing_names:
        print("  missing sprite sources (first 20):")
        for nm, sf in missing_names:
            print("    %-24s expected img/pokemon/%s" % (nm, sf))
    if unmatched:
        print("WARNING: %d trainer species not found in poks (using built-in "
              "dex fallback):" % len(unmatched))
        for s in sorted(unmatched):
            print("    %s" % s)


if __name__ == "__main__":
    main()
