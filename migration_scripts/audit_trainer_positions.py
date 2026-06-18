"""Audit trainer positions across all non-Route maps.

For each map that has trainers, compares BPE's object_events against
upstream/master by script name. Reports maps where any vanilla-matched
trainer differs in x, y, movement_type, movement_range_x, movement_range_y,
or trainer_sight_or_berry_tree_id.

Skips:
  - Route* maps (already done)
  - Trainers whose script name doesn't appear in vanilla (custom BPE trainers)
  - Maps with no trainers in BPE
  - Maps with no vanilla counterpart (BPE-only maps)
"""
import json, os, subprocess, sys

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
MAPS_DIR = os.path.join(REPO, "data", "maps")

COMPARE_FIELDS = ["x", "y", "movement_type", "movement_range_x",
                  "movement_range_y", "trainer_sight_or_berry_tree_id"]


def get_vanilla(map_name):
    """Return parsed vanilla map.json, or None if not in upstream."""
    result = subprocess.run(
        ["git", "show", f"upstream/master:data/maps/{map_name}/map.json"],
        cwd=REPO, capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def trainers_by_script(obj_events):
    return {
        obj["script"]: obj
        for obj in obj_events
        if obj.get("trainer_type") == "TRAINER_TYPE_NORMAL"
    }


def main():
    map_names = sorted(os.listdir(MAPS_DIR))

    results = []   # (map_name, [(script_suffix, field, bpe_val, van_val), ...])
    no_vanilla = []
    skipped_routes = 0
    bpe_only_maps = 0

    for map_name in map_names:
        # Skip Route* (already done) and non-directories
        map_path = os.path.join(MAPS_DIR, map_name, "map.json")
        if not os.path.isfile(map_path):
            continue
        if map_name.startswith("Route"):
            skipped_routes += 1
            continue

        with open(map_path, "r", encoding="utf-8") as f:
            bpe_data = json.load(f)

        bpe_trainers = trainers_by_script(bpe_data.get("object_events", []))
        if not bpe_trainers:
            continue  # No trainers in BPE map

        vanilla_data = get_vanilla(map_name)
        if vanilla_data is None:
            bpe_only_maps += 1
            continue  # BPE-only map, no vanilla reference

        van_trainers = trainers_by_script(vanilla_data.get("object_events", []))

        diffs = []
        for script, bpe_obj in bpe_trainers.items():
            if script not in van_trainers:
                continue  # Custom BPE trainer, skip
            van_obj = van_trainers[script]
            trainer_diffs = []
            for field in COMPARE_FIELDS:
                bpe_val = bpe_obj.get(field)
                van_val = van_obj.get(field)
                if str(bpe_val) != str(van_val):
                    trainer_diffs.append((field, bpe_val, van_val))
            if trainer_diffs:
                short = script.split("_EventScript_", 1)[-1] if "_EventScript_" in script else script
                diffs.append((short, trainer_diffs))

        if diffs:
            results.append((map_name, diffs))

    # ---- Report ----
    print(f"Skipped {skipped_routes} Route* maps (already done).")
    print(f"Skipped {bpe_only_maps} BPE-only maps (no vanilla reference).\n")

    if not results:
        print("All non-Route maps match vanilla trainer positions!")
        return

    total_trainers = sum(len(d) for _, d in results)
    print(f"Found {len(results)} maps with {total_trainers} trainers needing relocation:\n")
    print(f"{'Map':<45} {'Trainers':>8}  Names")
    print("-" * 90)
    for map_name, diffs in results:
        names = ", ".join(t[0] for t in diffs)
        print(f"{map_name:<45} {len(diffs):>8}  {names}")

    print()
    print("=" * 90)
    print("DETAIL (fields that differ):")
    print("=" * 90)
    for map_name, diffs in results:
        print(f"\n{map_name}:")
        for trainer_name, trainer_diffs in diffs:
            field_strs = []
            for field, bpe_val, van_val in trainer_diffs:
                short_field = field.replace("movement_type", "mt").replace(
                    "trainer_sight_or_berry_tree_id", "sight").replace(
                    "movement_range_x", "rx").replace("movement_range_y", "ry")
                field_strs.append(f"{short_field}: {bpe_val!r} -> {van_val!r}")
            print(f"  {trainer_name}: {', '.join(field_strs)}")


if __name__ == "__main__":
    main()
