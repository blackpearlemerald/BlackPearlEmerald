"""Build site/data/features.json for the Features page.

The curated feature overview is handwritten content that belongs to the game
release, so it is read from BPEDocumentation/content/features.json at the
selected game source (like guides.json). Releases whose pinned source predates
that file get no curated overview; the page then shows only the legendary
encounters extracted from that release's own game data.

Legendary encounters come from world.json's static encounters (extracted from
the map scripts by extract_world.py), so levels, locations and the
pre-Elite Four group always match the release. Run after extract_world and
parse_pokemon.
"""
import os

import common as C

CONTENT_PATH = C.src("BPEDocumentation", "content", "features.json")
SCHEMA_VERSION = 1


def _text(value, where, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Features content: {where} must be non-empty trimmed text.")
    return value


def _table(table, where):
    """Validate an optional comparison table: a header row and rows of the same width."""
    if not isinstance(table, dict):
        raise ValueError(f"Features content: {where} table must be an object.")
    columns = table.get("columns")
    rows = table.get("rows")
    if not isinstance(columns, list) or len(columns) < 2 or not isinstance(rows, list) or not rows:
        raise ValueError(f"Features content: {where} table needs columns and rows.")
    if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
        raise ValueError(f"Features content: {where} table rows must match its columns.")
    return {"columns": [_text(c, f"{where} table column") for c in columns],
            "rows": [[_text(cell, f"{where} table cell") for cell in row] for row in rows]}


def _item(item, sid):
    out = {"title": _text(item.get("title"), f"{sid} item title"),
           "body": _text(item.get("body"), f"{sid} item body")}
    if "table" in item:
        out["table"] = _table(item["table"], f"{sid} item {out['title']}")
    return out


def validate_content(content):
    """Return normalised curated content or raise ValueError."""
    if not isinstance(content, dict) or content.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Features content: unsupported schemaVersion.")
    sections = content.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Features content: sections must be a non-empty list.")
    ids = set()
    out_sections = []
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"Features content: section {i} must be an object.")
        sid = _text(section.get("id"), f"section {i} id")
        if sid in ids or sid == "legendaries":
            raise ValueError(f"Features content: duplicate or reserved section id {sid}.")
        ids.add(sid)
        items = section.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"Features content: section {sid} needs items.")
        out_sections.append({
            "id": sid,
            "title": _text(section.get("title"), f"section {sid} title"),
            "items": [_item(item, sid) for item in items if isinstance(item, dict)],
        })
        if len(out_sections[-1]["items"]) != len(items):
            raise ValueError(f"Features content: section {sid} items must be objects.")
    legendaries = content.get("legendaries") or {}
    if not isinstance(legendaries, dict):
        raise ValueError("Features content: legendaries must be an object.")
    rules = legendaries.get("rules") or []
    if not isinstance(rules, list):
        raise ValueError("Features content: legendaries.rules must be a list.")
    notes = {}
    for key in ("preE4", "others"):
        group = legendaries.get(key) or {}
        if not isinstance(group, dict):
            raise ValueError(f"Features content: legendaries.{key} must map species to notes.")
        for species, note in group.items():
            if not str(species).startswith("SPECIES_"):
                raise ValueError(f"Features content: {species} is not a SPECIES_ constant.")
            # null keeps the species in this position without a note.
            _text(note, f"note for {species}", required=False)
        notes[key] = dict(group)
    return {
        "intro": _text(content.get("intro"), "intro", required=False),
        "sections": out_sections,
        "legendaryIntro": _text(legendaries.get("intro"), "legendaries.intro", required=False),
        "rules": [_text(rule, "legendary rule") for rule in rules],
        "notes": notes,
    }


def _entry(static, names, note=None):
    bare = static["species"][len("SPECIES_"):]
    entry = {"species": static["species"],
             "name": (names.get(bare) or {}).get("name") or C.prettify_constant(static["species"]),
             "level": static["level"], "mapId": static["mapId"], "place": static["place"]}
    if static.get("sprite"):
        entry["sprite"] = static["sprite"]
    if note:
        entry["note"] = note
    return entry


def build_legendaries(statics, names, content):
    """Split static encounters into the pre-Elite Four group and others.

    With curated content, the order and selection of "other" encounters and
    each note come from the content; the extracted data supplies species,
    level and location. Notes for species the release does not contain are
    dropped with a warning instead of inventing an entry.
    """
    first = {}
    for static in statics:
        first.setdefault(static["species"], static)
    pre = [s for s in first.values() if s.get("preE4")]
    notes = (content or {}).get("notes", {})
    pre_notes = notes.get("preE4", {})
    other_notes = notes.get("others", {})
    order = {species: i for i, species in enumerate(pre_notes)}
    pre.sort(key=lambda s: (order.get(s["species"], len(order)), s["place"], s["species"]))
    pre_out = [_entry(s, names, pre_notes.get(s["species"])) for s in pre]
    for species in pre_notes:
        if species not in first or not first[species].get("preE4"):
            print(f"  ! features: {species} is not a pre-Elite Four encounter here - note dropped")
    if content:
        others = []
        for species, note in other_notes.items():
            static = first.get(species)
            if not static or static.get("preE4"):
                print(f"  ! features: no static encounter for {species} - note dropped")
                continue
            others.append(_entry(static, names, note))
    else:
        others = [_entry(s, names) for s in sorted(
            (s for s in first.values() if s.get("legendary") and not s.get("preE4")),
            key=lambda s: (s["place"], s["species"]))]
    return {"preE4": pre_out, "others": others}


def build(content_path=CONTENT_PATH, site=C.SITE):
    world_path = os.path.join(site, "js", "data", "world.json")
    world = C.load_json(world_path)
    names_path = os.path.join(site, "data", "pokedex_index.json")
    names = C.load_json(names_path) if os.path.isfile(names_path) else {}
    content = validate_content(C.load_json(content_path)) if os.path.isfile(content_path) else None
    data = {"schemaVersion": SCHEMA_VERSION, "curated": content is not None,
            "legendaries": build_legendaries(world.get("statics") or [], names, content)}
    if content:
        data.update(intro=content["intro"], sections=content["sections"],
                    legendaryIntro=content["legendaryIntro"], rules=content["rules"])
    C.write_json(os.path.join(site, "data", "features.json"), data)
    print(f"Features: {'curated' if content else 'no curated content'}, "
          f"{len(data['legendaries']['preE4'])} pre-Elite Four legendaries, "
          f"{len(data['legendaries']['others'])} other static legendaries")
    return data


def main():
    C.ensure_dirs()
    return build()


if __name__ == "__main__":
    main()
