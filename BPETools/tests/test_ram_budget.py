"""Checks limits that were lowered to fit the 41-box PC into RAM (BPE 2.1)."""

import json
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]

MAP_OFFSET_W = 15
MAP_OFFSET_H = 14
PYRAMID_FLOOR_SQUARES_WIDE = 4
PYRAMID_FLOOR_SQUARES_HIGH = 4


def define(path: str, name: str) -> int:
    text = (REPO / path).read_text(encoding="utf-8")
    match = re.search(rf"#define\s+{name}\s+(0x[0-9A-Fa-f]+|\d+)", text)
    if not match:
        raise AssertionError(f"{name} not found in {path}")
    return int(match.group(1), 0)


class MapBufferTests(unittest.TestCase):
    def test_every_layout_fits_the_map_buffer(self):
        limit = define("include/fieldmap.h", "MAX_MAP_DATA_SIZE")
        layouts = json.loads((REPO / "data/layouts/layouts.json").read_text(encoding="utf-8"))["layouts"]
        checked = 0
        for layout in layouts:
            if "width" not in layout:
                continue
            blockdata = REPO / layout["blockdata_filepath"]
            if not blockdata.exists():
                continue  # FRLG layouts removed from BPE
            size = (layout["width"] + MAP_OFFSET_W) * (layout["height"] + MAP_OFFSET_H)
            self.assertLessEqual(size, limit, f"{layout['name']} needs {size} map tiles")
            checked += 1
            if layout["name"].startswith("BattlePyramidSquare"):
                pyramid = (layout["width"] * PYRAMID_FLOOR_SQUARES_WIDE + MAP_OFFSET_W) * (
                    layout["height"] * PYRAMID_FLOOR_SQUARES_HIGH + MAP_OFFSET_H)
                self.assertLessEqual(pyramid, limit, "Battle Pyramid floor")
        self.assertGreater(checked, 100)

    def test_trainer_hill_floor_fits_the_map_buffer(self):
        limit = define("include/fieldmap.h", "MAX_MAP_DATA_SIZE")
        width = define("include/constants/trainer_hill.h", "HILL_FLOOR_WIDTH")
        main = define("include/constants/trainer_hill.h", "HILL_FLOOR_HEIGHT_MAIN")
        margin = define("include/constants/trainer_hill.h", "HILL_FLOOR_HEIGHT_MARGIN")
        self.assertLessEqual((width + MAP_OFFSET_W) * (main + margin + MAP_OFFSET_H), limit)


class HeapTests(unittest.TestCase):
    def test_fixed_heap_areas_are_inside_the_heap(self):
        heap_size = define("include/malloc.h", "HEAP_SIZE")
        offsets = []
        for path in list((REPO / "include").glob("*.h")) + list((REPO / "src").glob("*.c")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"gHeap\s*(?:\+\s*|\[)(0x[0-9A-Fa-f]+|\d+)", text):
                offsets.append((int(match.group(1), 0), path.name))
        self.assertTrue(offsets)
        for offset, name in offsets:
            self.assertLess(offset, heap_size, f"{name} uses gHeap offset {offset:#x}")


if __name__ == "__main__":
    unittest.main()
