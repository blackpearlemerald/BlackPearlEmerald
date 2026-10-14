"""Build site/data/trainer_ai.json for the Trainer AI page.

The Trainer AI document is handwritten content that describes the battle AI
of one game release, so it is read from BPEDocumentation/content/trainer_ai.json
at the selected game source (like features.json). Releases whose pinned source
predates that file get no document; the page then says so instead of showing
another release's AI.

Each entry's rules are a nested list: a string is one line, and a list
indents the lines under the string before it, as in "If AI is faster:" followed
by ["+6"].
"""
import os

import common as C

CONTENT_PATH = C.src("BPEDocumentation", "content", "trainer_ai.json")
SCHEMA_VERSION = 1
MAX_DEPTH = 5


def _text(value, where, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Trainer AI content: {where} must be non-empty trimmed text.")
    return value


def _texts(values, where):
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"Trainer AI content: {where} must be a list.")
    return [_text(value, where) for value in values]


def _rules(rules, where, depth=1):
    """Validate a nested rule list: strings, each optionally followed by one list."""
    if not isinstance(rules, list) or not rules:
        raise ValueError(f"Trainer AI content: {where} rules must be a non-empty list.")
    if depth > MAX_DEPTH:
        raise ValueError(f"Trainer AI content: {where} rules nest deeper than {MAX_DEPTH} levels.")
    out = []
    for rule in rules:
        if isinstance(rule, list):
            if not out or isinstance(out[-1], list):
                raise ValueError(f"Trainer AI content: {where} has an indented list with no line above it.")
            out.append(_rules(rule, where, depth + 1))
        else:
            out.append(_text(rule, f"{where} rule"))
    return out


def _table(table, where):
    if not isinstance(table, dict):
        raise ValueError(f"Trainer AI content: {where} table must be an object.")
    columns = table.get("columns")
    rows = table.get("rows")
    if not isinstance(columns, list) or len(columns) < 2 or not isinstance(rows, list) or not rows:
        raise ValueError(f"Trainer AI content: {where} table needs columns and rows.")
    if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
        raise ValueError(f"Trainer AI content: {where} table rows must match its columns.")
    return {"columns": [_text(c, f"{where} table column") for c in columns],
            "rows": [[_text(cell, f"{where} table cell") for cell in row] for row in rows]}


def _entry(entry, sid):
    if not isinstance(entry, dict):
        raise ValueError(f"Trainer AI content: section {sid} entries must be objects.")
    name = _text(entry.get("name"), f"{sid} entry name")
    out = {"name": name}
    if "text" in entry:
        out["text"] = _texts(entry["text"], f"{name} text")
    if "rules" in entry:
        out["rules"] = _rules(entry["rules"], name)
    if "table" in entry:
        out["table"] = _table(entry["table"], name)
    if "notes" in entry:
        out["notes"] = _texts(entry["notes"], f"{name} notes")
    if entry.get("wide") is True:
        out["wide"] = True
    if not {"text", "rules", "table"} & out.keys():
        raise ValueError(f"Trainer AI content: {name} needs text, rules or a table.")
    return out


def validate_content(content):
    """Return normalised content or raise ValueError."""
    if not isinstance(content, dict) or content.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Trainer AI content: unsupported schemaVersion.")
    sections = content.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Trainer AI content: sections must be a non-empty list.")
    ids = set()
    out_sections = []
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"Trainer AI content: section {i} must be an object.")
        sid = _text(section.get("id"), f"section {i} id")
        if sid in ids:
            raise ValueError(f"Trainer AI content: duplicate section id {sid}.")
        ids.add(sid)
        entries = section.get("entries")
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Trainer AI content: section {sid} needs entries.")
        out = {"id": sid, "title": _text(section.get("title"), f"section {sid} title"),
               "entries": [_entry(entry, sid) for entry in entries]}
        intro = _texts(section.get("intro"), f"section {sid} intro")
        if intro:
            out["intro"] = intro
        out_sections.append(out)
    return {"title": _text(content.get("title"), "title"),
            "intro": _texts(content.get("intro"), "intro"),
            "sections": out_sections}


def build(content_path=CONTENT_PATH, site=C.SITE):
    content = validate_content(C.load_json(content_path)) if os.path.isfile(content_path) else None
    data = {"schemaVersion": SCHEMA_VERSION, "curated": content is not None}
    if content:
        data.update(content)
    C.write_json(os.path.join(site, "data", "trainer_ai.json"), data)
    if content:
        entries = sum(len(section["entries"]) for section in content["sections"])
        print(f"Trainer AI: {len(content['sections'])} sections, {entries} entries")
    else:
        print("Trainer AI: no document for this release")
    return data


def main():
    C.ensure_dirs()
    return build()


if __name__ == "__main__":
    main()
