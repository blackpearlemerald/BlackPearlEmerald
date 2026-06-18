"""Revert trainer positions to vanilla Emerald for Routes 125-134.

Matches trainers by script name. Only updates: x, y, movement_type,
movement_range_x, movement_range_y, trainer_sight_or_berry_tree_id.
graphics_id (sprite), elevation, trainer_type, and flag are preserved.
"""
import json, os

BASE = os.path.join(
    os.path.dirname(__file__),
    r"..\data\maps"
)

# Route -> {script_name -> {fields to update to vanilla values}}
UPDATES = {
    "Route125": {
        "Route125_EventScript_Presley": {
            "x": 43,
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route125_EventScript_Auron": {
            "x": 48, "y": 19,
            "movement_type": "MOVEMENT_TYPE_WALK_LEFT_AND_RIGHT",
            "trainer_sight_or_berry_tree_id": "3"
        }
    },
    "Route126": {
        "Route126_EventScript_Barry": {
            "x": 51, "y": 65,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_LEFT_UP_RIGHT_DOWN",
            "movement_range_x": 10, "movement_range_y": 3,
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route126_EventScript_Dean": {
            "x": 56, "y": 22,
            "movement_type": "MOVEMENT_TYPE_WALK_RIGHT_AND_LEFT",
            "movement_range_x": 9, "movement_range_y": 0,
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route126_EventScript_Nikki": {
            "x": 63, "y": 43,
            "movement_type": "MOVEMENT_TYPE_ROTATE_CLOCKWISE",
            "movement_range_x": 0, "movement_range_y": 0,
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route126_EventScript_Brenda": {
            "x": 9, "y": 48,
            "movement_type": "MOVEMENT_TYPE_FACE_UP",
            "movement_range_x": 0, "movement_range_y": 0,
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route126_EventScript_Sienna": {
            "x": 15, "y": 66,
            "movement_type": "MOVEMENT_TYPE_WALK_IN_PLACE_LEFT",
            "trainer_sight_or_berry_tree_id": "7"
        },
        "Route126_EventScript_Pablo": {
            "x": 7, "y": 66,
            "movement_type": "MOVEMENT_TYPE_WALK_IN_PLACE_RIGHT",
            "trainer_sight_or_berry_tree_id": "7"
        },
        "Route126_EventScript_Isobel": {
            "y": 5,
            "movement_type": "MOVEMENT_TYPE_WALK_IN_PLACE_LEFT",
            "trainer_sight_or_berry_tree_id": "7"
        },
        "Route126_EventScript_Leonardo": {
            "x": 56, "y": 5,
            "movement_type": "MOVEMENT_TYPE_WALK_IN_PLACE_RIGHT",
            "trainer_sight_or_berry_tree_id": "7"
        }
    },
    "Route127": {
        "Route127_EventScript_Camden": {
            "x": 45, "y": 42,
            "movement_type": "MOVEMENT_TYPE_FACE_LEFT_AND_RIGHT",
            "trainer_sight_or_berry_tree_id": "2"
        },
        "Route127_EventScript_Donny": {
            "x": 18, "y": 68,
            "movement_type": "MOVEMENT_TYPE_FACE_UP_LEFT_AND_RIGHT",
            "trainer_sight_or_berry_tree_id": "4"
        },
        "Route127_EventScript_Aidan": {
            "x": 15,
            "movement_type": "MOVEMENT_TYPE_FACE_LEFT"
        },
        "Route127_EventScript_Athena": {
            "y": 23,
            "movement_type": "MOVEMENT_TYPE_FACE_RIGHT",
            "trainer_sight_or_berry_tree_id": "2"
        }
    },
    "Route128": {
        "Route128_EventScript_Isaiah": {
            "x": 35, "y": 33,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_RIGHT_UP_LEFT_DOWN",
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route128_EventScript_Katelyn": {
            "x": 78, "y": 24,
            "movement_type": "MOVEMENT_TYPE_WALK_RIGHT_AND_LEFT",
            "trainer_sight_or_berry_tree_id": "7"
        },
        "Route128_EventScript_Carlee": {
            "x": 101, "y": 29,
            "movement_type": "MOVEMENT_TYPE_WALK_UP_AND_DOWN",
            "trainer_sight_or_berry_tree_id": "4"
        },
        "Route128_EventScript_Harrison": {
            "x": 101, "y": 22,
            "movement_type": "MOVEMENT_TYPE_WALK_DOWN_AND_UP",
            "trainer_sight_or_berry_tree_id": "4"
        }
    },
    "Route129": {
        "Route129_EventScript_Chase": {
            "x": 28, "y": 16,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_DOWN_LEFT_UP_RIGHT",
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route129_EventScript_Allison": {
            "x": 10, "y": 14,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_RIGHT_DOWN_LEFT_UP",
            "trainer_sight_or_berry_tree_id": "2"
        },
        "Route129_EventScript_Tisha": {
            "x": 13,
            "movement_type": "MOVEMENT_TYPE_WALK_IN_PLACE_DOWN",
            "trainer_sight_or_berry_tree_id": "5"
        },
        "Route129_EventScript_Reed": {
            "x": 35, "y": 9,
            "movement_type": "MOVEMENT_TYPE_ROTATE_CLOCKWISE",
            "trainer_sight_or_berry_tree_id": "2"
        },
        "Route129_EventScript_Clarence": {
            "x": 13, "y": 27,
            "movement_type": "MOVEMENT_TYPE_WALK_IN_PLACE_UP",
            "trainer_sight_or_berry_tree_id": "5"
        }
    },
    "Route130": {
        "Route130_EventScript_Rodney": {
            "x": 70, "y": 21,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_LEFT_UP_RIGHT_DOWN",
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route130_EventScript_Katie": {
            "x": 7, "y": 21,
            "movement_type": "MOVEMENT_TYPE_WALK_DOWN_AND_UP",
            "trainer_sight_or_berry_tree_id": "5"
        },
        "Route130_EventScript_Santiago": {
            "x": 7, "y": 30,
            "movement_type": "MOVEMENT_TYPE_WALK_UP_AND_DOWN"
        }
    },
    "Route131": {
        "Route131_EventScript_Richard": {
            "x": 41, "y": 32,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_UP_RIGHT_LEFT_DOWN",
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route131_EventScript_Herman": {
            "x": 18, "y": 19,
            "movement_type": "MOVEMENT_TYPE_FACE_DOWN_LEFT_AND_RIGHT",
            "trainer_sight_or_berry_tree_id": "4"
        },
        "Route131_EventScript_Susie": {
            "x": 10, "y": 22,
            "movement_type": "MOVEMENT_TYPE_FACE_DOWN_UP_AND_RIGHT",
            "trainer_sight_or_berry_tree_id": "4"
        },
        "Route131_EventScript_Kara": {
            "x": 31, "y": 25,
            "movement_type": "MOVEMENT_TYPE_WALK_SEQUENCE_LEFT_DOWN_RIGHT_UP",
            "trainer_sight_or_berry_tree_id": "3"
        },
        "Route131_EventScript_Reli": {
            "y": 16,
            "trainer_sight_or_berry_tree_id": "1"
        },
        "Route131_EventScript_Ian": {
            "y": 16,
            "trainer_sight_or_berry_tree_id": "1"
        },
        "Route131_EventScript_Kevin": {
            "x": 52, "y": 20,
            "movement_type": "MOVEMENT_TYPE_WALK_DOWN_AND_UP",
            "trainer_sight_or_berry_tree_id": "5"
        },
        "Route131_EventScript_Talia": {
            "x": 52,
            "movement_type": "MOVEMENT_TYPE_WALK_UP_AND_DOWN",
            "trainer_sight_or_berry_tree_id": "5"
        }
    },
    # Route132: already correct, skip
    # Route133: already correct, skip
    "Route134": {
        "Route134_EventScript_Aaron": {
            "movement_type": "MOVEMENT_TYPE_FACE_RIGHT"
        },
        "Route134_EventScript_Marley": {
            "movement_type": "MOVEMENT_TYPE_FACE_LEFT"
        }
    }
}


def main():
    for route, route_updates in UPDATES.items():
        path = os.path.join(BASE, route, "map.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        applied = []
        for obj in data["object_events"]:
            script = obj.get("script", "")
            if script in route_updates:
                for field, value in route_updates[script].items():
                    obj[field] = value
                applied.append(script.split("_EventScript_")[1])

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

        print(f"{route}: updated {len(applied)} trainer(s): {', '.join(applied)}")


if __name__ == "__main__":
    main()
