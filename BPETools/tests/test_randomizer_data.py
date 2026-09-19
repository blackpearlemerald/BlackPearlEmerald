"""Checks the randomizer's generated tables (BPETools/generate_randomizer_data.py)."""

import importlib.util
import json
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
GENERATED = REPO / "src" / "data" / "randomizer" / "generated.h"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_randomizer_data", REPO / "BPETools" / "generate_randomizer_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeneratedTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()
        cls.text = GENERATED.read_text(encoding="utf-8")

    def test_header_is_up_to_date(self):
        self.assertEqual(self.generator.main_text(), self.text,
                         "Run python BPETools/generate_randomizer_data.py")

    def test_every_map_section_has_a_badge_tier(self):
        tiers = json.loads((REPO / "BPETools" / "randomizer_badge_tiers.json").read_text(encoding="utf-8"))
        for path in (REPO / "data" / "maps").glob("*/map.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["id"] in tiers["maps"]:
                continue
            self.assertIn(data.get("region_map_section"), tiers["sections"], data["id"])

    def test_field_items_keep_their_order(self):
        # Existing locations must keep their index, so a later run may only append.
        flags = re.findall(r"\{(FLAG_\w+|0),", self.text.split("sRandomizerFieldItems[] =", 1)[1].split("};", 1)[0])
        self.assertEqual(self.generator.previous_item_order(), flags)
        self.assertEqual(len(set(flag for flag in flags if flag != "0")), len([flag for flag in flags if flag != "0"]))

    def test_starter_gifts_are_not_gift_sources(self):
        # The Johto starters follow the Starters option, not Gifts.
        sources = self.text.split("sRandomizerSpeciesSources[NUM_SPECIES] =", 1)[1].split("};", 1)[0]
        for species in ("SPECIES_CHIKORITA", "SPECIES_CYNDAQUIL", "SPECIES_TOTODILE"):
            line = next((line for line in sources.splitlines() if f"[{species}]" in line), "")
            self.assertNotIn("RANDOMIZER_SOURCE_GIFT", line, species)


if __name__ == "__main__":
    unittest.main()
