"""Revert trainer positions to vanilla Emerald for all non-Route maps.

For each map: loads BPE map.json, loads vanilla map.json from upstream/master,
matches trainers by script name, and applies vanilla values for:
  x, y, movement_type, movement_range_x, movement_range_y,
  trainer_sight_or_berry_tree_id

All other fields (graphics_id, elevation, trainer_type, flag, local_id) are
preserved from BPE. Trainers with no vanilla match are left unchanged.
"""
import json, os, subprocess

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
MAPS_DIR = os.path.join(REPO, "data", "maps")

MAPS_TO_FIX = [
    "RustboroCity_Gym",
    "PetalburgWoods",
    "DewfordTown_Gym",
    "JaggedPass",
    "MtChimney",
    "MtPyre_2F",
    "MtPyre_3F",
    "MtPyre_4F",
    "MtPyre_5F",
    "MtPyre_6F",
    "MtPyre_Summit",
    "AquaHideout_1F",
    "AquaHideout_B1F",
    "AquaHideout_B2F",
    "MagmaHideout_1F",
    "MagmaHideout_2F_1R",
    "MagmaHideout_2F_2R",
    "MagmaHideout_3F_1R",
    "MagmaHideout_3F_2R",
    "MagmaHideout_4F",
    "MossdeepCity_SpaceCenter_1F",
    "SeafloorCavern_Room1",
    "SeafloorCavern_Room3",
    "SeafloorCavern_Room4",
    "VictoryRoad_1F",
    "VictoryRoad_B1F",
    "VictoryRoad_B2F",
]

APPLY_FIELDS = [
    "x", "y", "movement_type",
    "movement_range_x", "movement_range_y",
    "trainer_sight_or_berry_tree_id",
]


def get_vanilla(map_name):
    result = subprocess.run(
        ["git", "show", f"upstream/master:data/maps/{map_name}/map.json"],
        cwd=REPO, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def main():
    total_updated = 0

    for map_name in MAPS_TO_FIX:
        bpe_path = os.path.join(MAPS_DIR, map_name, "map.json")
        with open(bpe_path, "r", encoding="utf-8") as f:
            bpe_data = json.load(f)

        vanilla_data = get_vanilla(map_name)
        if vanilla_data is None:
            print(f"  SKIP {map_name}: not found in upstream")
            continue

        van_by_script = {
            obj["script"]: obj
            for obj in vanilla_data.get("object_events", [])
            if obj.get("trainer_type") == "TRAINER_TYPE_NORMAL"
        }

        updated = []
        for obj in bpe_data.get("object_events", []):
            script = obj.get("script", "")
            if obj.get("trainer_type") != "TRAINER_TYPE_NORMAL":
                continue
            if script not in van_by_script:
                continue  # custom BPE trainer — leave alone
            van_obj = van_by_script[script]
            changed = False
            for field in APPLY_FIELDS:
                if obj.get(field) != van_obj.get(field):
                    obj[field] = van_obj[field]
                    changed = True
            if changed:
                short = script.split("_EventScript_", 1)[-1] if "_EventScript_" in script else script
                updated.append(short)

        with open(bpe_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(bpe_data, f, indent=2)
            f.write("\n")

        total_updated += len(updated)
        if updated:
            print(f"{map_name}: {len(updated)} updated — {', '.join(updated)}")
        else:
            print(f"{map_name}: already correct")

    print(f"\nTotal trainers updated: {total_updated}")


if __name__ == "__main__":
    main()
