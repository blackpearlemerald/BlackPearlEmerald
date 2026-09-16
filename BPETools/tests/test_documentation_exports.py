"""Exporter tests for gifts, static legendary encounters and the Features page.

All inputs are small synthetic game-source fragments written to temporary
directories; nothing reads or writes the real site output.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
try:
    import common as C
    import extract_world
    import build_features
except ImportError:  # Pillow is required by the sprite helpers.
    extract_world = None
import releases


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class GiftTests(unittest.TestCase):
    def test_single_item_gift_is_recorded_as_ordinary_gift(self):
        scripts = {"Hiker": "\tgoto_if_set FLAG_X, Hiker_Done\n\tgiveitem ITEM_HM_FLASH\n\trelease\n", "Hiker_Done": "\trelease\n"}
        packages = extract_world.collect_gift_packages("Hiker", scripts)
        self.assertEqual(packages, [("Hiker", [("ITEM_HM_FLASH", 1)])])
        items, care = extract_world.merge_gift_packages(packages)
        self.assertFalse(care)
        self.assertEqual(items, [{"item": "ITEM_HM_FLASH", "qty": 1, "carePackage": False}])

    def test_care_package_behaviour_is_preserved(self):
        scripts = {"Leader": "\tgiveitem ITEM_POTION, 5\n\tgiveitem ITEM_TM_ROAR\n\tgoto Leader_Retry\n",
                   "Leader_Retry": "\tgiveitem ITEM_POTION, 5\n\tgiveitem ITEM_TM_ROAR\n"}
        items, care = extract_world.merge_gift_packages(extract_world.collect_gift_packages("Leader", scripts))
        self.assertTrue(care)
        # Alternate paths to the same package are not extra copies.
        self.assertEqual(items, [{"item": "ITEM_POTION", "qty": 5, "carePackage": True},
                                 {"item": "ITEM_TM_ROAR", "qty": 1, "carePackage": True}])

    def test_mixed_and_choice_gifts_and_purchases(self):
        scripts = {"Npc": "\tcall Npc_Package\n\tgoto Npc_Single\n",
                   "Npc_Package": "\tgiveitem ITEM_POTION\n\tgiveitem ITEM_ANTIDOTE\n",
                   "Npc_Single": "\tgiveitem ITEM_HM_CUT\n",
                   "Prize": "\tremovecoins 1000\n\tadditem ITEM_TM_PSYCHIC\n"}
        items, care = extract_world.merge_gift_packages(extract_world.collect_gift_packages("Npc", scripts))
        self.assertTrue(care)
        self.assertEqual([(i["item"], i["carePackage"]) for i in items],
                         [("ITEM_POTION", True), ("ITEM_ANTIDOTE", True), ("ITEM_HM_CUT", False)])
        choice = {"Rydel": "\tgoto_if_eq VAR_RESULT, 0, Rydel_Mach\n\tgoto Rydel_Acro\n",
                  "Rydel_Mach": "\tgiveitem ITEM_MACH_BIKE\n", "Rydel_Acro": "\tgiveitem ITEM_ACRO_BIKE\n"}
        items, care = extract_world.merge_gift_packages(extract_world.collect_gift_packages("Rydel", choice))
        self.assertFalse(care)  # mutually exclusive single gifts never form a package
        self.assertEqual([i["item"] for i in items], ["ITEM_MACH_BIKE", "ITEM_ACRO_BIKE"])
        self.assertEqual(extract_world.collect_gift_packages("Prize", scripts), [])

    def test_load_maps_records_local_single_gifts_but_not_shared_distributions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = {"object_events": [
                {"graphics_id": "OBJ_EVENT_GFX_HIKER", "x": 3, "y": 4, "script": "GraniteCave_1F_EventScript_Hiker"},
                {"graphics_id": "OBJ_EVENT_GFX_GENTLEMAN", "x": 5, "y": 4, "script": "CableClub_EventScript_MysteryGiftMan"},
            ]}
            write(root / "data/maps/GraniteCave_1F/map.json", json.dumps(dict(events, id="MAP_GRANITE_CAVE_1F", layout="LAYOUT_TEST")))
            write(root / "data/maps/GraniteCave_1F/scripts.inc", "GraniteCave_1F_EventScript_Hiker::\n\tgiveitem ITEM_HM_FLASH\n\tend\n")
            write(root / "data/scripts/cable_club.inc", "CableClub_EventScript_MysteryGiftMan::\n\tgiveitem ITEM_EON_TICKET\n\tend\n")
            write(root / "site/img/maps/test.png", "")
            with mock_patch.object(C, "SRC_ROOT", str(root)), mock_patch.object(C, "SITE_MAPS_IMG", str(root / "site/img/maps")):
                maps = extract_world.load_maps({"LAYOUT_TEST": (10, 10, "test")})
        gifts = maps["MAP_GRANITE_CAVE_1F"]["gifts"]
        self.assertEqual(len(gifts), 1)
        self.assertEqual((gifts[0]["x"], gifts[0]["y"], gifts[0]["carePackage"]), (3, 4, False))
        self.assertEqual(gifts[0]["items"], [{"item": "ITEM_HM_FLASH", "qty": 1, "carePackage": False}])


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class StaticEncounterTests(unittest.TestCase):
    SCRIPTS = {
        "Legendary_EventScript_BattleArticuno": "\tsetwildbattle SPECIES_ARTICUNO, 75\n\tdowildbattle\n\tsetvar VAR_PREE4_LEGENDARY 1\n\tgoto_if_unset FLAG_SYS_GAME_CLEAR, Global_Hide\n",
        "Global_Hide": "\tsetflag FLAG_HIDE_OVERWORLD_ARTICUNO\n",
        "Mew": "\tseteventmon SPECIES_MEW, 30\n\tspecial BattleSetup_StartLegendaryBattle\n\tgoto_if_eq VAR_RESULT, B_OUTCOME_WON, Mew_Defeated\n",
        "Mew_Defeated": "\tsetvar VAR_PREE4_LEGENDARY 14\n",
        "Regirock": "\tsetwildbattle SPECIES_REGIROCK, 40\n\tspecial StartRegiBattle\n\tsetvar VAR_0x8004, SPECIES_REGIROCK\n\tspecial TryRecordPreE4LegendaryCatch\n",
        "Sign": "\tcall_if_eq VAR_ROAMER_POKEMON, 0, Sign_Latios\n\tcall_if_ne VAR_ROAMER_POKEMON, 0, Sign_Latias\n",
        "Sign_Latios": "\tseteventmon SPECIES_LATIOS, 50, ITEM_SOUL_DEW\n",
        "Sign_Latias": "\tseteventmon SPECIES_LATIAS, 50, ITEM_SOUL_DEW\n",
        "Trigger": "\tapplymovement LOCALID_TERRA_CAVE_GROUDON, Approach\n\tsetwildbattle SPECIES_GROUDON, 70\n",
    }

    def test_pre_elite_four_group_levels_and_branches(self):
        articuno = extract_world.static_encounter("Legendary_EventScript_BattleArticuno", self.SCRIPTS)
        self.assertEqual(articuno, {"species": "SPECIES_ARTICUNO", "level": 75, "preE4": True})
        # The pick can be set in a branch reached only after the battle.
        self.assertEqual(extract_world.static_encounter("Mew", self.SCRIPTS),
                         {"species": "SPECIES_MEW", "level": 30, "preE4": True})
        # Current releases report the battle to the catch special instead.
        self.assertEqual(extract_world.static_encounter("Regirock", self.SCRIPTS),
                         {"species": "SPECIES_REGIROCK", "level": 40, "preE4": True})

    def test_ambiguous_scripts_are_skipped_and_triggers_anchor_to_the_pokemon(self):
        self.assertIsNone(extract_world.static_encounter("Sign", self.SCRIPTS))
        self.assertIsNone(extract_world.static_encounter("Missing", self.SCRIPTS))
        objects = {"LOCALID_TERRA_CAVE_GROUDON": {"x": 17, "y": 22}}
        groudon = extract_world.static_encounter("Trigger", self.SCRIPTS, objects)
        self.assertEqual(groudon, {"species": "SPECIES_GROUDON", "level": 70, "preE4": False, "anchor": (17, 22)})

    def test_legendary_species_flags_new_and_old_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root / "src/data/pokemon/species_info/gen_1.h",
                  "    [SPECIES_SNORLAX] =\n    {\n        .catchRate = 25,\n    },\n"
                  "    [SPECIES_ARTICUNO] =\n    {\n        .isSubLegendary = TRUE,\n    },\n"
                  "    [SPECIES_MEW] =\n    {\n        .isMythical = TRUE,\n    },\n"
                  "    [SPECIES_MEWTWO] =\n    {\n        .isLegendary = TRUE,\n    },\n")
            with mock_patch.object(C, "SRC_ROOT", str(root)):
                self.assertEqual(extract_world.load_legendary_species(), {"SPECIES_ARTICUNO", "SPECIES_MEW", "SPECIES_MEWTWO"})

    def test_load_maps_collects_statics_per_object_without_trigger_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = {"object_events": [
                {"graphics_id": "OBJ_EVENT_GFX_KECLEON", "x": 1, "y": 1, "script": "Kecleon"},
                {"graphics_id": "OBJ_EVENT_GFX_KECLEON", "x": 2, "y": 2, "script": "Kecleon"},
                {"graphics_id": "OBJ_EVENT_GFX_GROUDON", "x": 9, "y": 9, "local_id": "LOCALID_TERRA_CAVE_GROUDON", "script": "0x0"},
            ], "coord_events": [{"type": "trigger", "x": 9, "y": 12, "script": "Trigger"},
                                {"type": "trigger", "x": 9, "y": 13, "script": "Trigger"}]}
            write(root / "data/maps/TerraCave_End/map.json", json.dumps(dict(events, id="MAP_TERRA_CAVE_END", layout="LAYOUT_TEST")))
            write(root / "data/maps/TerraCave_End/scripts.inc",
                  "Trigger::\n\tapplymovement LOCALID_TERRA_CAVE_GROUDON, Approach\n\tsetwildbattle SPECIES_GROUDON, 70\n\tend\n")
            write(root / "data/scripts/kecleon.inc", "Kecleon::\n\tsetwildbattle SPECIES_KECLEON, 30\n\tend\n")
            write(root / "site/img/maps/test.png", "")
            with mock_patch.object(C, "SRC_ROOT", str(root)), mock_patch.object(C, "SITE_MAPS_IMG", str(root / "site/img/maps")):
                statics = extract_world.load_maps({"LAYOUT_TEST": (20, 20, "test")})["MAP_TERRA_CAVE_END"]["statics"]
        self.assertEqual([(s["species"], s["x"], s["y"]) for s in statics],
                         [("SPECIES_KECLEON", 1, 1), ("SPECIES_KECLEON", 2, 2), ("SPECIES_GROUDON", 9, 9)])
        self.assertEqual(statics[-1]["place"], "Terra Cave End")


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class FeaturesTests(unittest.TestCase):
    STATICS = [
        {"mapId": "MAP_ROUTE134", "place": "Route 134", "species": "SPECIES_SUICUNE", "level": 75, "preE4": True, "legendary": True, "sprite": "SUICUNE.png"},
        {"mapId": "MAP_FARAWAY_ISLAND_INTERIOR", "place": "Faraway Island Interior", "species": "SPECIES_MEW", "level": 30, "preE4": True, "legendary": True},
        {"mapId": "MAP_DESERT_RUINS", "place": "Desert Ruins", "species": "SPECIES_REGIROCK", "level": 40, "legendary": True},
        {"mapId": "MAP_PETALBURG_CITY", "place": "Petalburg City", "species": "SPECIES_SNORLAX", "level": 50},
        {"mapId": "MAP_ROUTE120", "place": "Route 120", "species": "SPECIES_KECLEON", "level": 30},
        {"mapId": "MAP_ROUTE120", "place": "Route 120", "species": "SPECIES_KECLEON", "level": 30},
    ]
    CONTENT = {"schemaVersion": 1, "intro": "Main features.",
               "sections": [{"id": "adventure", "title": "Your adventure", "items": [{"title": "Level caps", "body": "Caps follow badges."}]}],
               "legendaries": {"rules": ["Battle only one."],
                               "preE4": {"SPECIES_MEW": "Faraway Island.", "SPECIES_SUICUNE": None, "SPECIES_ZAPDOS": "Not in this release."},
                               "others": {"SPECIES_SNORLAX": "Needs the Poké Flute.", "SPECIES_GROUDON": "Missing here."}}}

    def build(self, content):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            write(site / "js/data/world.json", json.dumps({"statics": self.STATICS}))
            write(site / "data/pokedex_index.json", json.dumps({"MEW": {"name": "Mew"}}))
            content_path = site / "content.json"
            if content is not None:
                write(content_path, json.dumps(content))
            data = build_features.build(str(content_path), str(site))
            self.assertEqual(json.loads((site / "data/features.json").read_text(encoding="utf-8")), data)
            releases.validate_features(site)
            return data

    def test_curated_content_orders_notes_and_drops_unknown_species(self):
        data = self.build(self.CONTENT)
        self.assertTrue(data["curated"])
        self.assertEqual(data["sections"][0]["items"][0]["title"], "Level caps")
        pre = data["legendaries"]["preE4"]
        self.assertEqual([(e["name"], e["level"], e.get("note")) for e in pre],
                         [("Mew", 30, "Faraway Island."), ("Suicune", 75, None)])
        self.assertEqual(pre[1]["sprite"], "SUICUNE.png")
        self.assertEqual([e["species"] for e in data["legendaries"]["others"]], ["SPECIES_SNORLAX"])

    def test_release_without_content_shows_only_extracted_legendaries(self):
        data = self.build(None)
        self.assertFalse(data["curated"])
        self.assertNotIn("sections", data)
        self.assertEqual(len(data["legendaries"]["preE4"]), 2)
        # Without curation only flagged legendaries are listed, not Kecleon/Snorlax.
        self.assertEqual([e["species"] for e in data["legendaries"]["others"]], ["SPECIES_REGIROCK"])

    def test_invalid_content_fails_the_export(self):
        broken = [dict(self.CONTENT, schemaVersion=2), dict(self.CONTENT, sections=[]),
                  dict(self.CONTENT, sections=[{"id": "legendaries", "title": "X", "items": [{"title": "a", "body": "b"}]}]),
                  dict(self.CONTENT, legendaries={"preE4": {"ARTICUNO": "no prefix"}}),
                  dict(self.CONTENT, legendaries={"rules": [" padded "]})]
        for content in broken:
            with self.subTest(content=content), self.assertRaises(ValueError):
                build_features.validate_content(content)

    def test_repository_content_is_valid(self):
        path = Path(__file__).resolve().parents[2] / "BPEDocumentation/content/features.json"
        if path.is_file():
            build_features.validate_content(json.loads(path.read_text(encoding="utf-8")))

    def test_snapshot_validation_rejects_malformed_features_data(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            for data in ({"schemaVersion": 1, "curated": True, "legendaries": {"preE4": [], "others": []}},
                         {"schemaVersion": 1, "curated": False, "legendaries": {"preE4": [{"species": "MEW"}], "others": []}},
                         []):
                write(site / "data/features.json", json.dumps(data))
                with self.subTest(data=data), self.assertRaises(ValueError):
                    releases.validate_features(site)


if __name__ == "__main__":
    unittest.main()
