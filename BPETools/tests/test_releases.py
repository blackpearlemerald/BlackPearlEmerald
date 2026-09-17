"""Release integrity tests use synthetic bytes, never a user's ROM."""
import json
from pathlib import Path
import random
import re
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch
import subprocess
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_lib import (BASE_SIZE, MAX_ROM_SIZE, VERSION_KEY, apply_ups, create_ups,
                         decode_number, describe, encode_number, inspect_ups,
                         json_bytes, read_package, version, write_zip)
from generate_release_header import generate


class UpsTests(unittest.TestCase):
    def test_round_trip_empty_grow_shrink_and_long_offsets(self):
        rng = random.Random(47)
        cases = [(b"", b""), (b"", b"abc"), (b"abc", b""), (b"a"*20000, b"a"*19000+b"bc"),
                 (b"abc", b"abd"), (b"abc", b"abc"), (bytes(range(256)), b"\0"*512)]
        for _ in range(30):
            source = rng.randbytes(rng.randrange(1, 3000))
            target = bytearray(source)
            for _ in range(20):
                target[rng.randrange(len(target))] = rng.randrange(256)
            cases.append((source, bytes(target)))
        for source, target in cases:
            with self.subTest(lengths=(len(source), len(target))):
                self.assertEqual(apply_ups(source, create_ups(source, target)), target)

    def test_corruption_and_wrong_base_rejected(self):
        patch = create_ups(b"original", b"updated")
        with self.assertRaises(ValueError):
            apply_ups(b"different", patch)
        bad = bytearray(patch)
        bad[7] ^= 4
        with self.assertRaises(ValueError):
            inspect_ups(bad)

    def test_truncated_and_out_of_bounds_records_rejected(self):
        for body in (b"\x00", encode_number(9000) + b"\x01\0"):
            patch = bytearray(b"UPS1") + encode_number(2) + encode_number(2) + body + struct.pack("<II", 0, 0)
            patch += struct.pack("<I", zlib.crc32(patch))
            with self.assertRaises(ValueError):
                inspect_ups(patch)

    def test_number_boundaries(self):
        for n in (0, 127, 128, 255, 16383, 16384, MAX_ROM_SIZE):
            encoded = encode_number(n)
            self.assertEqual(decode_number(encoded, 0, len(encoded)), (n, len(encoded)))


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.name = "BlackPearlEmerald_v2.0.0-beta.2.ups"
        # Structurally valid metadata-only fixture; actual round trips are tested above.
        patch = bytearray(b"UPS1") + encode_number(BASE_SIZE) + encode_number(MAX_ROM_SIZE)
        patch += struct.pack("<II", int("1F1C08FB", 16), 0)
        patch += struct.pack("<I", zlib.crc32(patch))
        self.patch = bytes(patch)
        self.meta = {"schemaVersion": 1, "version": "2.0.0-beta.2", "sourceCommit": "a"*40,
                     "patch": dict(describe(self.patch), file=self.name, format="ups"),
                     "baseRom": {"size": BASE_SIZE, "crc32": "1F1C08FB", "sha256": "0"*64},
                     "outputRom": {"size": MAX_ROM_SIZE, "crc32": "00000000", "sha256": "0"*64}}
        self.path = self.root / "BlackPearlEmerald_v2.0.0-beta.2.zip"

    def tearDown(self):
        self.temp.cleanup()

    def package(self, extra=None):
        files = {self.name: self.patch, "release.json": json_bytes(self.meta)}
        files.update(extra or {})
        write_zip(self.path, files)

    def test_valid_package_and_deterministic_zip(self):
        self.package()
        first = self.path.read_bytes()
        self.package()
        self.assertEqual(first, self.path.read_bytes())
        self.assertEqual(read_package(self.path, check_source=False)[0], self.meta)

    def test_filename_metadata_mismatch(self):
        self.meta["version"] = "2.0.0"
        self.package()
        with self.assertRaises(ValueError):
            read_package(self.path, check_source=False)

    def test_modified_patch(self):
        self.package({self.name: self.patch[:-1]+b"x"})
        with self.assertRaises(ValueError):
            read_package(self.path, check_source=False)

    def test_rom_extra_path_traversal_and_duplicate_entries(self):
        for name in ("game.gba", "../release.json", "C:/game.gba"):
            self.package({name: b"unwanted"})
            with self.assertRaises(ValueError):
                read_package(self.path, check_source=False)
        self.package()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(self.path, "a") as archive:
                archive.writestr("release.json", json_bytes(self.meta))
        with self.assertRaises(ValueError):
            read_package(self.path, check_source=False)

    def test_incorrect_base_and_missing_commit_rejected(self):
        self.meta["baseRom"]["crc32"] = "12345678"
        self.package()
        with self.assertRaises(ValueError):
            read_package(self.path, check_source=False)

    def test_package_uses_recorded_source_not_upload_commit(self):
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=self.root).decode().strip()
        git("init", "-q")
        git("config", "user.name", "blackpearlemerald")
        git("config", "user.email", "328855025+blackpearlemerald@users.noreply.github.com")
        config = self.root / "BPE_VERSION.json"
        config.write_text(json.dumps({"version": self.meta["version"]}))
        git("add", "BPE_VERSION.json")
        git("commit", "-qm", "Release source")
        self.meta["sourceCommit"] = git("rev-parse", "HEAD")
        config.write_text(json.dumps({"version": "2.1.0-beta"}))
        git("add", "BPE_VERSION.json")
        git("commit", "-qm", "Later development")
        self.package()
        self.assertEqual(read_package(self.path, root=self.root)[0], self.meta)
        self.meta["sourceCommit"] = git("rev-parse", "HEAD")
        self.package()
        with self.assertRaises(ValueError):
            read_package(self.path, root=self.root)
        self.meta["baseRom"]["crc32"] = "1F1C08FB"
        self.meta["sourceCommit"] = "main"
        self.package()
        with self.assertRaises(ValueError):
            read_package(self.path, check_source=False)


class VersionTests(unittest.TestCase):
    def test_semantic_order_with_beta_and_stable(self):
        versions = ["2.0.0-beta.10", "1.0.1", "2.0.0", "2.0.0-beta.2", "2.0.1-beta"]
        self.assertEqual(sorted(versions, key=VERSION_KEY), ["1.0.1", "2.0.0-beta.2", "2.0.0-beta.10", "2.0.0", "2.0.1-beta"])

    def test_invalid_versions_rejected(self):
        for v in ("../../oops", "2.0.0 Beta", "2.0.0-beta.01", "02.0.0", "2.0.0+build", "2.0.0;whoami"):
            with self.assertRaises(ValueError):
                version(v)

    def test_title_label_updates_with_version(self):
        with tempfile.TemporaryDirectory() as folder:
            config, header = Path(folder)/"version.json", Path(folder)/"version.h"
            config.write_text(json.dumps({"version": "2.0.0-beta"}))
            generate(config, header)
            first = header.read_text()
            self.assertIn('BPE_RELEASE:2.0.0-beta', first)
            config.write_text(json.dumps({"version": "2.0.1-beta"}))
            generate(config, header)
            self.assertNotEqual(first, header.read_text())
            self.assertIn('BPE_RELEASE:2.0.1-beta', header.read_text())

    def test_version_history_covers_published_releases_with_concise_notes(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import releases
        history = releases.release_history()
        self.assertTrue({"1.0.1", "2.0.0-beta", "2.0.1"}.issubset(history))
        self.assertEqual(history["2.0.1"]["channel"], "beta")
        self.assertEqual(history["2.0.1"]["changes"], ["Increased the base Shiny rate from 1 in 8,192 to 1 in 512."])
        self.assertEqual(history["2.0.0-beta"]["channel"], "beta")
        self.assertNotIn("Terastallization", " ".join(history["2.0.0-beta"]["changes"]))
        self.assertTrue(all("\n" not in note and len(note) <= 220
                            for entry in history.values() for note in entry["changes"]))
        self.assertEqual(releases.website_label({"label": "2.0.1", "channel": "beta"}), "2.0.1 Beta")
        self.assertEqual(releases.website_label({"label": "2.0.0 Beta", "channel": "beta"}), "2.0.0 Beta")


class ArchiveTests(unittest.TestCase):
    def test_encounters_support_historical_maps_without_region(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import parse_pokemon
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, region in (("Route101", None), ("Route102", "REGION_HOENN"), ("PalletTown", "REGION_KANTO")):
                directory = root / "data/maps" / name
                directory.mkdir(parents=True)
                entry = {"id": "MAP_" + name.upper()}
                if region:
                    entry["region"] = region
                (directory / "map.json").write_text(json.dumps(entry))
            (root / "src/data").mkdir(parents=True)
            (root / "src/field_specials.c").write_text("")
            encounters = [{"map": "MAP_" + name, "land_mons": {"mons": [
                {"species": "SPECIES_POOCHYENA", "min_level": 2, "max_level": 3}
            ]}} for name in ("ROUTE101", "ROUTE102", "PALLETTOWN", "MISSING_MAP")]
            (root / "src/data/wild_encounters.json").write_text(json.dumps({"wild_encounter_groups": [{"encounters": encounters}]}))
            with mock_patch.object(parse_pokemon, "REPO", root):
                result = parse_pokemon.parse_encounters()
            self.assertEqual({entry["map"] for entry in result["POOCHYENA"]}, {"MAP_ROUTE101", "MAP_ROUTE102"})

    def test_static_encounters_are_listed_once_per_map(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import parse_pokemon
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data/maps").mkdir(parents=True)
            (root / "src/data").mkdir(parents=True)
            (root / "src/field_specials.c").write_text("")
            (root / "src/data/wild_encounters.json").write_text(json.dumps({"wild_encounter_groups": []}))
            statics = [
                {"mapId": "MAP_FALLARBOR_TOWN_MOVE_RELEARNERS_HOUSE", "place": "Fallarbor Town Move Relearners House",
                 "species": "SPECIES_ROTOM", "level": 30, "preE4": True},
                {"mapId": "MAP_ROUTE120", "place": "Route 120", "species": "SPECIES_KECLEON", "level": 30},
                {"mapId": "MAP_ROUTE120", "place": "Route 120", "species": "SPECIES_KECLEON", "level": 30},
            ]
            with mock_patch.object(parse_pokemon, "REPO", root):
                result = parse_pokemon.parse_encounters(statics)
            self.assertEqual(result["ROTOM"], [{"map": "MAP_FALLARBOR_TOWN_MOVE_RELEARNERS_HOUSE",
                                                "mapName": "Fallarbor Town Move Relearners House",
                                                "minLevel": 30, "maxLevel": 30, "type": "static"}])
            self.assertEqual(len(result["KECLEON"]), 1)

    def test_conditional_stat_macros_match_release_configuration(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import parse_pokemon
        source = "#if P_UPDATED_STATS >= GEN_6\n#define ALAKAZAM_SP_DEF 95\n#elif P_UPDATED_STATS >= GEN_2\n#define ALAKAZAM_SP_DEF 85\n#else\n#define ALAKAZAM_SP_DEF 135\n#endif\n"
        for generation, expected in ((9, 95), (3, 85), (1, 135)):
            with mock_patch.object(parse_pokemon, "gen_config", return_value={"P_UPDATED_STATS":generation,"GEN_6":6,"GEN_2":2}):
                self.assertEqual(parse_pokemon._collect_stat_macros(source)["ALAKAZAM_SP_DEF"], expected)

    def test_type_macros_match_release_configuration(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import parse_pokemon
        source = """\
#define CONDITIONAL_TYPE (P_UPDATED_TYPES >= GEN_6 ? TYPE_FAIRY : TYPE_PSYCHIC)
#if P_UPDATED_TYPES >= GEN_6
#define BRACED_TYPES { TYPE_FAIRY, TYPE_FAIRY }
#else
#define BRACED_TYPES { TYPE_NORMAL, TYPE_NORMAL }
#endif
#define DUAL_TYPES { TYPE_ELECTRIC, TYPE_GHOST }
"""
        cases = (
            (9, ["PSYCHIC", "FAIRY"], ["FAIRY"]),
            (3, ["PSYCHIC"], ["NORMAL"]),
        )
        for generation, conditional, braced in cases:
            config = {"P_UPDATED_TYPES": generation, "GEN_6": 6}
            with mock_patch.object(parse_pokemon, "gen_config", return_value=config):
                macros = parse_pokemon._collect_object_macros(source)
                self.assertEqual(
                    parse_pokemon._parse_species_types(
                        ".types = MON_TYPES(TYPE_PSYCHIC, CONDITIONAL_TYPE),", macros
                    ),
                    conditional,
                )
                self.assertEqual(parse_pokemon._parse_species_types(".types = BRACED_TYPES,", macros), braced)
                self.assertEqual(
                    parse_pokemon._parse_species_types(".types = DUAL_TYPES,", macros),
                    ["ELECTRIC", "GHOST"],
                )
                with self.assertRaises(ValueError):
                    parse_pokemon._parse_species_types(".types = UNKNOWN_TYPE_MACRO,", macros)

    def test_generated_updated_types_do_not_fall_back_to_normal(self):
        species_dir = Path(__file__).resolve().parents[2] / "BPEDocumentation/site/data/species"
        expected = {
            "RALTS": ["PSYCHIC", "FAIRY"],
            "KIRLIA": ["PSYCHIC", "FAIRY"],
            "GARDEVOIR": ["PSYCHIC", "FAIRY"],
            "CLEFFA": ["FAIRY"],
            "CLEFAIRY": ["FAIRY"],
            "CLEFABLE": ["FAIRY"],
            "IGGLYBUFF": ["NORMAL", "FAIRY"],
            "JIGGLYPUFF": ["NORMAL", "FAIRY"],
            "WIGGLYTUFF": ["NORMAL", "FAIRY"],
            "MAGNEMITE": ["ELECTRIC", "STEEL"],
            "MAGNETON": ["ELECTRIC", "STEEL"],
            "TOGEPI": ["FAIRY"],
            "TOGETIC": ["FAIRY", "FLYING"],
            "TOGEKISS": ["FAIRY", "FLYING"],
            "ROTOM": ["ELECTRIC", "GHOST"],
            "COTTONEE": ["GRASS", "FAIRY"],
            "WHIMSICOTT": ["GRASS", "FAIRY"],
        }
        for species, types in expected.items():
            with self.subTest(species=species):
                data = json.loads((species_dir / f"{species}.json").read_text(encoding="utf-8"))
                self.assertEqual(data["types"], types)

    def test_special_moves_are_parsed_and_standard_moves_are_not_duplicated(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import parse_pokemon

        def species(**overrides):
            data = {
                "levelUpMoves": [],
                "eggMoves": [],
                "tmMoves": [],
                "hmMoves": [],
                "tutorMoves": [],
            }
            data.update(overrides)
            return data

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src/data/pokemon/species_info").mkdir(parents=True)
            (root / "src/daycare.c").write_text("""
static const struct BreedingSpecialMove sBreedingSpecialMoveItemTable[] =
{
    { SPECIES_PICHU, ITEM_LIGHT_BALL, MOVE_VOLT_TACKLE },
};
""", encoding="utf-8")
            (root / "src/tv.c").write_text("""
} sPokeOutbreakSpeciesList[] = {
    {
        .species = SPECIES_SEEDOT,
        .moves = {MOVE_BIDE, MOVE_LEECH_SEED, MOVE_NATURE_POWER},
        .level = 3,
        .location = MAP_NUM(MAP_ROUTE102)
    },
};
""", encoding="utf-8")
            (root / "src/data/pokemon/form_change_tables.h").write_text("""
static const struct Fusion sNecrozmaFusionTable[] = {
    {1, ITEM_N_SOLARIZER, SPECIES_NECROZMA, SPECIES_SOLGALEO, SPECIES_NECROZMA_DUSK_MANE, MOVE_SUNSTEEL_STRIKE, FORGET_EXTRA_MOVES},
};
static const struct Fusion sCalyrexFusionTable[] = {
    {3, ITEM_REINS_OF_UNITY, SPECIES_CALYREX, SPECIES_GLASTRIER, SPECIES_CALYREX_ICE, MOVE_GLACIAL_LANCE, FORGET_EXTRA_MOVES},
};
static const struct FormChange sNecrozmaDuskManeFormChangeTable[] = {
    {FORM_CHANGE_BATTLE_ULTRA_BURST, SPECIES_NECROZMA_ULTRA, ITEM_ULTRANECROZIUM_Z},
};
static const struct FormChange sZacianFormChangeTable[] = {
    {FORM_CHANGE_BEGIN_BATTLE, SPECIES_ZACIAN_CROWNED, ITEM_RUSTED_SWORD, MOVE_IRON_HEAD, MOVE_BEHEMOTH_BLADE},
};
""", encoding="utf-8")
            (root / "src/data/pokemon/species_info/gen_7_families.h").write_text("""
[SPECIES_NECROZMA_DUSK_MANE] = {
    .formChangeTable = sNecrozmaDuskManeFormChangeTable,
},
""", encoding="utf-8")

            all_species = {
                "PICHU": species(),
                "SEEDOT": species(eggMoves=["LEECH_SEED"]),
                "NECROZMA_DUSK_MANE": species(),
                "NECROZMA_ULTRA": species(),
                "CALYREX_ICE": species(levelUpMoves=[{"level": 1, "move": "GLACIAL_LANCE"}]),
                "ZACIAN_CROWNED": species(),
            }
            with mock_patch.object(parse_pokemon, "REPO", root):
                count = parse_pokemon.apply_special_moves(all_species)

            self.assertEqual(count, 6)
            self.assertEqual(
                [move["move"] for move in all_species["PICHU"]["specialMoves"]],
                ["VOLT_TACKLE"],
            )
            self.assertEqual(
                [move["move"] for move in all_species["SEEDOT"]["specialMoves"]],
                ["BIDE", "NATURE_POWER"],
            )
            self.assertIn("Route 102", all_species["SEEDOT"]["specialMoves"][0]["method"])
            self.assertEqual(
                [move["move"] for move in all_species["NECROZMA_DUSK_MANE"]["specialMoves"]],
                ["SUNSTEEL_STRIKE"],
            )
            self.assertEqual(
                [move["move"] for move in all_species["NECROZMA_ULTRA"]["specialMoves"]],
                ["SUNSTEEL_STRIKE"],
            )
            self.assertEqual(
                [move["move"] for move in all_species["ZACIAN_CROWNED"]["specialMoves"]],
                ["BEHEMOTH_BLADE"],
            )
            self.assertNotIn("specialMoves", all_species["CALYREX_ICE"])

    def test_archive_checksums_inventory_and_traversal(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
        import releases
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            (source / "release.json").write_text('{"version":"1.0.1"}')
            (source / "index.html").write_text("historical page")
            archive = root / "doc.zip"
            releases.freeze_snapshot(source, archive)
            # Exercise archive integrity independently of the full export checks.
            with mock_patch.object(releases, "validate_snapshot"):
                self.assertEqual(releases.restore_snapshot(archive, root / "restored")["version"], "1.0.1")
                with zipfile.ZipFile(archive) as bundle:
                    files = {n: bundle.read(n) for n in bundle.namelist()}
                original = dict(files)
                for number, extra in enumerate(({"index.html": b"tampered"}, {"game.gba": b"extra"}, {"../outside": b"escape"})):
                    changed = dict(original, **extra)
                    if "../outside" in extra:
                        checks = json.loads(changed["checksums.json"])
                        checks["../outside"] = releases.sha256(b"escape")
                        changed["checksums.json"] = json_bytes(checks)
                    write_zip(archive, changed)
                    with self.assertRaises(ValueError):
                        releases.restore_snapshot(archive, root / str(number))

    def test_identical_assets_shared_and_urls_rewritten(self):
        import releases
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for version_id in ("1.0.1", "2.0.0-beta"):
                snapshot = root / "versions" / version_id
                asset = snapshot / "img/maps"
                asset.mkdir(parents=True)
                (asset / "test.png").write_bytes(b"identical image")
                (snapshot / "index.html").write_text('<img src="img/maps/test.png">')
                (snapshot / "app.js").write_text('const path = `img/maps/${map}.png`;')
            with mock_patch.object(releases, "validate_snapshot"):
                releases.share_assets(root)
            self.assertEqual(len(list((root / "assets").iterdir())), 1)
            for page in (root / "versions").glob("*/index.html"):
                path = re.search(r'src="([^"]+)"', page.read_text())[1]
                self.assertEqual((page.parent / path).read_bytes(), b"identical image")
                self.assertIn("../../assets/", (page.parent / "app.js").read_text())


if __name__ == "__main__":
    unittest.main()
