"""Exporter tests for gifts, static legendary encounters, wild held items and the
Features page.

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
    import parse_pokemon
    import parse_trainers
except ImportError:  # Pillow is required by the sprite helpers.
    extract_world = None
import releases


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class TrainerPlacementTests(unittest.TestCase):
    # Shaped like the Route 110 rival: a trigger tile, a scene that moves the
    # rival object, and per-starter battle labels that name no object.
    SCRIPTS = {
        "Trigger": "\tsetvar VAR_0x8008, 1\n\tgoto Scene\n",
        "Scene": "\tapplymovement LOCALID_RIVAL, Walk\n"
                 "\tgoto_if_eq VAR_RESULT, MALE, May\n"
                 "\tgoto_if_eq VAR_RESULT, FEMALE, Brendan\n",
        "May": "\tswitch VAR_STARTER_MON\n\tcase 0, MayTreecko\n\tcase 1, MayTorchic\n",
        "MayTreecko": "\ttrainerbattle_no_intro TRAINER_MAY_TREECKO, Text\n\tgoto Exit\n",
        "MayTorchic": "\ttrainerbattle_no_intro TRAINER_MAY_TORCHIC, Text\n\tgoto Exit\n",
        "Brendan": "\ttrainerbattle_no_intro TRAINER_BRENDAN_TREECKO, Text\n",
        "Exit": "\tremoveobject LOCALID_BIKE\n",
    }

    def test_every_starter_variant_is_found(self):
        battles = extract_world.find_battles("Trigger", self.SCRIPTS)
        self.assertEqual([tid for tid, _, _ in battles],
                         ["TRAINER_MAY_TREECKO", "TRAINER_MAY_TORCHIC", "TRAINER_BRENDAN_TREECKO"])
        self.assertEqual(battles[0][2], ["Trigger", "Scene", "May", "MayTreecko"])
        self.assertEqual(extract_world.find_battle("Trigger", self.SCRIPTS),
                         ("TRAINER_MAY_TREECKO", "MayTreecko"))

    def test_trigger_battle_is_anchored_on_the_object_the_scene_moves(self):
        rival, bike = {"local_id": "LOCALID_RIVAL"}, {"local_id": "LOCALID_BIKE"}
        objects = {"LOCALID_RIVAL": rival, "LOCALID_BIKE": bike}
        for _, _, path in extract_world.find_battles("Trigger", self.SCRIPTS):
            self.assertIs(extract_world.battle_anchor(path, self.SCRIPTS, objects), rival)

    def test_variable_sprite_resolves_through_called_scripts(self):
        local = {"Map_MapScripts": "\tcall SetupRival\n"}
        shared = dict(local, SetupRival="\tsetvar VAR_OBJ_GFX_ID_0, OBJ_EVENT_GFX_CYNTHIA\n")
        self.assertEqual(extract_world.variable_gfx(local, shared),
                         {"OBJ_EVENT_GFX_VAR_0": "OBJ_EVENT_GFX_CYNTHIA"})


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

    def test_gift_egg_takes_the_species_set_before_it(self):
        scripts = {"EggWoman": "\tgoto_if_set FLAG_X, EggWoman_Done\n"
                               "\tsetvar VAR_RESULT, SPECIES_TOGEPI\n"
                               "\tspecial RandomizeEggSpecies\n\tgiveegg VAR_RESULT\n",
                   "EggWoman_Done": "\trelease\n",
                   "Event": "\tgiveegg SPECIES_PICHU\n"}
        self.assertEqual(extract_world.collect_gift_eggs("EggWoman", scripts),
                         [("EggWoman", "SPECIES_TOGEPI")])
        self.assertEqual(extract_world.collect_gift_eggs("Event", scripts),
                         [("Event", "SPECIES_PICHU")])
        self.assertEqual(extract_world.collect_gift_packages("EggWoman", scripts), [])

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

    def test_gift_note_corrects_detected_items(self):
        gift = {"script": "Mom", "items": [
            {"item": "ITEM_CANDY_JAR", "qty": 1, "carePackage": True},
            {"item": "ITEM_TM_REST", "qty": 2, "carePackage": True}]}
        extract_world.apply_gift_note(gift, {
            "note": "<b>Talk to Mom.</b>", "exclude": ["ITEM_CANDY_JAR"],
            "add": [{"item": "ITEM_TM_REST", "qty": 1}, {"item": "ITEM_AMULET_COIN"}]})
        self.assertEqual(gift["note"], "<b>Talk to Mom.</b>")
        self.assertEqual(gift["items"], [
            {"item": "ITEM_TM_REST", "qty": 1, "carePackage": True},
            {"item": "ITEM_AMULET_COIN", "qty": 1, "carePackage": False}])
        self.assertTrue(gift["carePackage"])
        legacy = {"script": "Mom", "carePackage": True, "items": [
            {"item": "ITEM_CANDY_JAR", "qty": 1, "carePackage": True},
            {"item": "ITEM_EXP_SHARE", "qty": 1, "carePackage": True}]}
        extract_world.apply_gift_note(legacy, {
            "exclude": ["ITEM_CANDY_JAR", "ITEM_EXP_SHARE"],
            "add": [{"item": "ITEM_AMULET_COIN"}]})
        self.assertFalse(legacy["carePackage"])  # only ordinary gifts remain
        debug_only = {"script": "Receptionist", "items": [
            {"item": "ITEM_CONTEST_PASS", "qty": 1, "carePackage": False}]}
        extract_world.apply_gift_note(debug_only, {"exclude": ["ITEM_CONTEST_PASS"]})
        self.assertEqual(debug_only["items"], [])  # the marker is dropped

    def test_trainer_who_opens_a_shop_gets_its_items_and_note(self):
        content = (
            "Map_EventScript_Jacek::\n"
            "\tchecktrainerflag TRAINER_JACEK\n"
            "\tgoto_if TRUE, Map_EventScript_JacekShop\n"
            "\ttrainerbattle_no_intro TRAINER_JACEK, Text\n"
            "\tend\n"
            "Map_EventScript_JacekShop::\n"
            "\tpokemart Map_Pokemart_Capsule\n"
            "\tend\n"
            "Map_Pokemart_Capsule:\n"
            "\t.2byte ITEM_ABILITY_CAPSULE\n"
            "\tpokemartlistend\n")
        db = {"TRAINER_JACEK": {"name": "Jacek", "party": []}}
        inventories = extract_world.parse_shop_scripts(content, db)
        self.assertEqual(inventories[0]["trainer"], "TRAINER_JACEK")
        self.assertEqual(inventories[0]["condition"], "After defeating Jacek")
        shipped = dict(db)
        extract_world.annotate_trainer_shops(
            shipped, {"MAP_X": {"inventories": inventories}})
        missing = extract_world.apply_trainer_notes(
            shipped, {"TRAINER_JACEK": "First!", "TRAINER_GONE": "x"})
        self.assertEqual(shipped["TRAINER_JACEK"]["shop"], ["ITEM_ABILITY_CAPSULE"])
        self.assertEqual(shipped["TRAINER_JACEK"]["note"], "First!")
        self.assertEqual(missing, ["TRAINER_GONE"])
        self.assertNotIn("shop", db["TRAINER_JACEK"])  # parsed data untouched

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
class ScriptedTrainerTests(unittest.TestCase):
    def test_cutscene_opponents_are_placed_where_they_are_fought(self):
        # Oceanic Museum 2F: talking to Capt. Stern spawns two grunts on the
        # stairs, and each walks up to the player before its battle.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = {"object_events": [
                {"graphics_id": "OBJ_EVENT_GFX_SCIENTIST_1", "x": 13, "y": 6, "local_id": "LOCALID_STERN",
                 "movement_type": "MOVEMENT_TYPE_FACE_DOWN", "script": "Stern"},
                {"graphics_id": "OBJ_EVENT_GFX_AQUA_MEMBER_M", "x": 6, "y": 1, "local_id": "LOCALID_GRUNT_1",
                 "movement_type": "MOVEMENT_TYPE_FACE_DOWN", "script": "0x0"},
                {"graphics_id": "OBJ_EVENT_GFX_AQUA_MEMBER_M", "x": 6, "y": 1, "local_id": "LOCALID_GRUNT_2",
                 "movement_type": "MOVEMENT_TYPE_FACE_DOWN", "script": "0x0"},
            ]}
            write(root / "data/maps/Museum_2F/map.json", json.dumps(dict(events, id="MAP_MUSEUM_2F", layout="LAYOUT_TEST")))
            write(root / "data/maps/Museum_2F/scripts.inc",
                  "Stern::\n\taddobject LOCALID_GRUNT_1\n\tapplymovement LOCALID_GRUNT_1, Enter1\n"
                  "\taddobject LOCALID_GRUNT_2\n\tapplymovement LOCALID_GRUNT_2, Enter2\n"
                  "\tapplymovement LOCALID_GRUNT_2, Approach\n\ttrainerbattle_no_intro TRAINER_GRUNT_A, Text\n"
                  "\tapplymovement LOCALID_GRUNT_2, Defeated\n\tapplymovement LOCALID_GRUNT_1, Approach\n"
                  "\ttrainerbattle_no_intro TRAINER_GRUNT_B, Text\n\tapplymovement LOCALID_GRUNT_1, Defeated\n\tend\n"
                  "Enter1:\n\twalk_down\n\twalk_right\n\twalk_down\n\twalk_down\n\tstep_end\n"
                  "Enter2:\n\twalk_down\n\twalk_down\n\twalk_down\n\twalk_down\n\twalk_down\n\tstep_end\n"
                  "Approach:\n\twalk_right\n\tstep_end\n"
                  "Defeated:\n\tlock_facing_direction\n\twalk_left\n\tunlock_facing_direction\n\tstep_end\n")
            write(root / "site/img/maps/test.png", "")
            with mock_patch.object(C, "SRC_ROOT", str(root)), mock_patch.object(C, "SITE_MAPS_IMG", str(root / "site/img/maps")):
                trainers = extract_world.load_maps({"LAYOUT_TEST": (20, 20, "test")})["MAP_MUSEUM_2F"]["trainers"]
        # Neither battle is shown on Capt. Stern, and each grunt stands where
        # its own battle starts rather than on the stairs.
        self.assertEqual(sorted((t["trainerId"], t["x"], t["y"], t["gfx"], t["dir"]) for t in trainers),
                         [("TRAINER_GRUNT_A", 7, 6, "OBJ_EVENT_GFX_AQUA_MEMBER_M", "right"),
                          ("TRAINER_GRUNT_B", 8, 4, "OBJ_EVENT_GFX_AQUA_MEMBER_M", "right")])


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class WildHeldItemTests(unittest.TestCase):
    GENERAL = """#define GEN_8 7
#define GEN_9 8
#define GEN_LATEST GEN_9
"""
    POKEMON_C = """static inline bool32 CanFirstMonBoostHeldItemRarity(void)
{
%s    return FALSE;
}

void SetWildMonHeldItem(void)
{
    bool32 itemHeldBoost = CanFirstMonBoostHeldItemRarity();
    u16 chanceNoItem = itemHeldBoost ? 20 : 45;
    u16 chanceNotRare = itemHeldBoost ? 80 : 95;
}
"""

    def rules(self, boost_body, overworld):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "src/pokemon.c", self.POKEMON_C % boost_body)
            write(root / "include/config/general.h", self.GENERAL)
            write(root / "include/config/overworld.h", overworld)
            for name in ("battle.h", "pokemon.h"):
                write(root / "include/config" / name, "")
            with mock_patch.object(parse_pokemon, "REPO", root), \
                    mock_patch.dict(parse_pokemon._GEN_CONFIG_CACHE, clear=True):
                return parse_pokemon.read_wild_held_item_rules()

    def test_current_rules_boost_with_compound_eyes_and_super_luck(self):
        rules = self.rules("""    if (ability == ABILITY_COMPOUND_EYES)
        return TRUE;
    else if ((OW_SUPER_LUCK >= GEN_8) && ability == ABILITY_SUPER_LUCK)
        return TRUE;
""", "#define OW_SUPER_LUCK GEN_LATEST\n")
        self.assertEqual(rules, ((50, 5), (60, 20), ["COMPOUND_EYES", "SUPER_LUCK"]))
        self.assertEqual(parse_pokemon.wild_held_items("POTION", "REVIVE", rules),
                         [{"item": "POTION", "pct": 50, "boostPct": 60}, {"item": "REVIVE", "pct": 5, "boostPct": 20}])
        self.assertEqual(parse_pokemon.wild_held_items(None, "LIGHT_BALL", rules),
                         [{"item": "LIGHT_BALL", "pct": 5, "boostPct": 20}])
        self.assertEqual(parse_pokemon.wild_held_items("SACRED_ASH", "SACRED_ASH", rules),
                         [{"item": "SACRED_ASH", "pct": 100, "boostPct": 100}])
        self.assertEqual(parse_pokemon.wild_held_items(None, None, rules), [])

    def test_release_1_0_1_had_no_boosting_ability(self):
        rules = self.rules("""    if ((OW_COMPOUND_EYES < GEN_9) && ability == ABILITY_COMPOUND_EYES)
        return TRUE;
    else if ((OW_SUPER_LUCK == GEN_8) && ability == ABILITY_SUPER_LUCK)
        return TRUE;
""", "#define OW_COMPOUND_EYES GEN_LATEST\n#define OW_SUPER_LUCK GEN_LATEST\n")
        self.assertEqual(rules[2], [])
        self.assertEqual(parse_pokemon.wild_held_items("POTION", None, rules),
                         [{"item": "POTION", "pct": 50, "boostPct": 50}])


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class DefaultTrainerMovesTests(unittest.TestCase):
    LEARNSET = [(0, "EVO"), (1, "TACKLE"), (1, "GROWL"), (5, "EMBER"), (5, "TACKLE"),
                (9, "BITE"), (12, "FLAMETHROWER"), (20, "FIRE_BLAST")]

    def test_last_four_distinct_level_up_moves_like_the_game(self):
        moveset = parse_trainers.initial_moveset
        self.assertEqual(moveset(self.LEARNSET, 1), ["TACKLE", "GROWL"])
        self.assertEqual(moveset(self.LEARNSET, 9), ["TACKLE", "GROWL", "EMBER", "BITE"])
        self.assertEqual(moveset(self.LEARNSET, 19), ["GROWL", "EMBER", "BITE", "FLAMETHROWER"])

    def test_species_names_become_trainerproc_constants(self):
        name = parse_trainers.species_constant
        self.assertEqual(name("Rattata-Alola"), "SPECIES_RATTATA_ALOLA")
        self.assertEqual(name("Mr. Mime"), "SPECIES_MR_MIME")
        self.assertEqual(name("Farfetch’d"), "SPECIES_FARFETCHD")
        self.assertEqual(name("Nidoran♀"), "SPECIES_NIDORAN_F")
        self.assertEqual(name("Flabébé"), "SPECIES_FLABEBE")

    def test_only_moveless_pokemon_are_filled_and_standard_levels_can_differ(self):
        trainers = {"TRAINER_A": {"party": [
            {"species": "Charmander", "level": 20, "standardLevel": 9},
            {"species": "Charmander", "level": 12, "standardLevel": 13},
            {"species": "Charmander", "level": 5, "moves": ["Scratch"]},
        ]}}
        data = ({"SPECIES_CHARMANDER": self.LEARNSET}, {"FIRE_BLAST": "Fire Blast"})
        with mock_patch.object(parse_trainers, "_level_up_learnsets", return_value=data):
            parse_trainers.fill_default_moves(trainers)
        first, second, authored = trainers["TRAINER_A"]["party"]
        self.assertEqual(first["moves"], ["Ember", "Bite", "Flamethrower", "Fire Blast"])
        self.assertEqual(first["standardMoves"], ["Tackle", "Growl", "Ember", "Bite"])
        self.assertNotIn("standardMoves", second)
        self.assertEqual(authored["moves"], ["Scratch"])

    def test_unknown_species_fails_the_export(self):
        trainers = {"TRAINER_A": {"party": [{"species": "Missingno", "level": 5}]}}
        with mock_patch.object(parse_trainers, "_level_up_learnsets", return_value=({}, {})):
            with self.assertRaises(ValueError):
                parse_trainers.fill_default_moves(trainers)


@unittest.skipIf(extract_world is None, "Install BPEDocumentation/requirements.txt to test exporters")
class EvolutionLabelTests(unittest.TestCase):
    ITEMS = """const struct ItemInfo gItemsInfo[] =
{
    [ITEM_KINGS_ROCK] = { .name = ITEM_NAME("King's Rock"), },
    [ITEM_POKE_BALL] = { .name = ITEM_NAME("Poké Ball"), },
    [ITEM_LEADERS_CREST] = { .name = ITEM_NAME("Leader's Crest"), },
};
"""
    SECTIONS = {"map_sections": [{"id": "MAPSEC_NEW_MAUVILLE", "name": "NEW MAUVILLE"}]}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        write(root / "src/data/items.h", self.ITEMS)
        write(root / "src/data/region_map/region_map_sections.json", json.dumps(self.SECTIONS))
        write(root / "data/maps/Route1/scripts.inc", "Script::\n\ttryspecialevo EVO_TRIGGER_DARK_SCROLL\n\tend\n")
        with mock_patch.object(parse_pokemon, "REPO", root):
            self.names = parse_pokemon.EvoNames(
                {"RAGE_FIST": {"name": "Rage Fist"}}, {"BISHARP": "Bisharp", "SHELMET": "Shelmet"})

    def labels(self, source, text, form_pickers=True):
        evos = parse_pokemon._parse_evolutions(".evolutions = EVOLUTION(%s)," % text)
        return [parse_pokemon._evo_label(evo, source, self.names, form_pickers)
                for evo in evos if parse_pokemon._evo_possible(evo, source, self.names)]

    def test_every_condition_is_written_out(self):
        self.assertEqual(self.labels("BASCULIN_WHITE_STRIPED", """
            {EVO_LEVEL, 0, SPECIES_BASCULEGION_M, CONDITIONS({IF_RECOIL_DAMAGE_GE, 294}, {IF_GENDER, MON_MALE})},
            {EVO_LEVEL, 0, SPECIES_BASCULEGION_F, CONDITIONS({IF_RECOIL_DAMAGE_GE, 294}, {IF_GENDER, MON_FEMALE})}"""),
            ["Level up after taking 294 recoil damage without fainting (male)",
             "Level up after taking 294 recoil damage without fainting (female)"])
        self.assertEqual(self.labels("X", """
            {EVO_LEVEL, 0, SPECIES_ANNIHILAPE, CONDITIONS({IF_USED_MOVE_X_TIMES, MOVE_RAGE_FIST, 20})},
            {EVO_LEVEL, 0, SPECIES_KINGAMBIT, CONDITIONS({IF_DEFEAT_X_WITH_ITEMS, SPECIES_BISHARP, ITEM_LEADERS_CREST, 3})},
            {EVO_TRADE, 0, SPECIES_POLITOED, CONDITIONS({IF_HOLD_ITEM, ITEM_KINGS_ROCK})},
            {EVO_TRADE, 0, SPECIES_ESCAVALIER, CONDITIONS({IF_TRADE_PARTNER_SPECIES, SPECIES_SHELMET})},
            {EVO_LEVEL, 0, SPECIES_MAGNEZONE, CONDITIONS({IF_IN_MAPSEC, MAPSEC_NEW_MAUVILLE})},
            {EVO_LEVEL, 0, SPECIES_ESPEON, CONDITIONS({IF_MIN_FRIENDSHIP, FRIENDSHIP_EVO_THRESHOLD}, {IF_NOT_TIME, TIME_NIGHT})},
            {EVO_LEVEL, 20, SPECIES_HITMONTOP, CONDITIONS({IF_ATK_EQ_DEF})},
            {EVO_LEVEL, 7, SPECIES_SILCOON, CONDITIONS({IF_PID_UPPER_MODULO_10_GT, 4})}"""),
            ["Level up after using Rage Fist 20 times",
             "Level up after defeating 3 Bisharp holding Leader's Crest",
             "Trade holding King's Rock",
             "Trade for Shelmet",
             "Level up in New Mauville",
             "Friendship (not at night)",
             "Lv. 20 with Attack = Defense",
             "Lv. 7 (50% chance)"])

    def test_shedinja_shares_ninjasks_level(self):
        self.assertEqual(self.labels("NINCADA", """{EVO_LEVEL, 20, SPECIES_NINJASK},
            {EVO_SPLIT_FROM_EVO, SPECIES_NINJASK, SPECIES_SHEDINJA, CONDITIONS({IF_BAG_ITEM_COUNT, ITEM_POKE_BALL, 1})}"""),
            ["Lv. 20", "Lv. 20 with a free party slot and a Poké Ball in the bag"])

    def test_older_methods_read_like_conditions(self):
        self.assertEqual(self.labels("BASCULIN_WHITE_STRIPED", """
            {EVO_LEVEL_RECOIL_DAMAGE_FEMALE, 1, SPECIES_BASCULEGION_F},
            {EVO_TRADE_ITEM, ITEM_KINGS_ROCK, SPECIES_POLITOED},
            {EVO_LEVEL_FEMALE, 20, SPECIES_WORMADAM},
            {EVO_FRIENDSHIP_NIGHT, 0, SPECIES_UMBREON}"""),
            ["Level up after taking recoil damage without fainting (female)",
             "Trade holding King's Rock", "Lv. 20 (female)", "Friendship (night)"])

    def test_impossible_evolutions_are_left_out(self):
        self.assertEqual(self.labels("CUBONE", """{EVO_LEVEL, 28, SPECIES_MAROWAK, CONDITIONS({IF_NOT_REGION, REGION_ALOLA})},
            {EVO_LEVEL, 28, SPECIES_MAROWAK_ALOLA, CONDITIONS({IF_REGION, REGION_ALOLA})},
            {EVO_NONE, 0, SPECIES_MAROWAK_ALOLA_TOTEM}"""), ["Lv. 28"])
        # Only a map script can start a script evolution.
        self.assertEqual(self.labels("KUBFU", """{EVO_SCRIPT_TRIGGER, EVO_TRIGGER_DARK_SCROLL, SPECIES_URSHIFU_SINGLE_STRIKE},
            {EVO_SCRIPT_TRIGGER, EVO_TRIGGER_WATER_SCROLL, SPECIES_URSHIFU_RAPID_STRIKE}"""), ["Special event"])

    def test_forms_shown_as_one_pokemon_name_what_picks_the_form(self):
        self.assertEqual(self.labels("ESPURR", """{EVO_LEVEL, 25, SPECIES_MEOWSTIC_M, CONDITIONS({IF_GENDER, MON_MALE})}""",
                                     form_pickers=False), ["Lv. 25 (form by gender)"])


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

    def test_item_table_is_kept(self):
        table = {"columns": ["Option", "A", "B"], "rows": [["Starters", "Same", "Random"]]}
        content = dict(self.CONTENT, sections=[{"id": "adventure", "title": "Your adventure",
                                                "items": [{"title": "Presets", "body": "Compare.", "table": table}]}])
        item = self.build(content)["sections"][0]["items"][0]
        self.assertEqual(item["table"], table)
        self.assertNotIn("table", self.build(self.CONTENT)["sections"][0]["items"][0])

    def test_invalid_content_fails_the_export(self):
        def with_table(table):
            return dict(self.CONTENT, sections=[{"id": "adventure", "title": "Your adventure",
                                                 "items": [{"title": "Presets", "body": "Compare.", "table": table}]}])
        broken = [dict(self.CONTENT, schemaVersion=2), dict(self.CONTENT, sections=[]),
                  with_table([]), with_table({"columns": ["Option", "A"], "rows": []}),
                  with_table({"columns": ["Option", "A"], "rows": [["Starters"]]}),
                  with_table({"columns": ["Option", "A"], "rows": [["Starters", ""]]}),
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
