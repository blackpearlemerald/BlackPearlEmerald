"""Tests for the damage calculator's save import.

The website reads saves with BPEDocumentation/site/js/save-converter.js and
turns them into calculator sets with js/calc_save_import.js. These tests run
both in Node and compare the Pokémon they find with a reading built from
bpe_save_format.py, whose formats are checked against the game's C code. The
experience tables are compared with the game's own, compiled for the host, when
a C compiler is available. Real player saves are used when they exist on this
computer; they are never committed.
"""

from __future__ import annotations

import json
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "BPETools"))
sys.path.insert(0, str(REPO / "BPETools" / "tests"))
sys.path.insert(0, str(REPO / "BPEDocumentation" / "scripts"))

import bpe_save_format as fmt  # noqa: E402
import build_calc_data  # noqa: E402
from test_bpe_save_format import (REAL_PRE21_SAVES, host_command, host_path,  # noqa: E402
                                  random_legacy_mon, random_legacy_storage)

CALC_DATA = REPO / "BPEDocumentation" / "site" / "calc" / "data" / "bpe_calc_data.json"
IMPORT_JS = REPO / "BPEDocumentation" / "site" / "js" / "calc_save_import.js"

# SaveBlock1 members (test/save.c checks them against include/global.h)
SB1_PARTY_COUNT = 564
SB1_PARTY = 568
SB1_FLAGS = 5864
SB1_VARS = 6164
SB1_DAYCARE = 13480
STATS = ["hp", "attack", "defense", "speed", "spAttack", "spDefense"]
HYPER_TRAINED = ["hyperTrainedHP", "hyperTrainedAttack", "hyperTrainedDefense", "hyperTrainedSpeed",
                 "hyperTrainedSpAttack", "hyperTrainedSpDefense"]
GROWTH_RATES = ["Medium Fast", "Erratic", "Fluctuating", "Medium Slow", "Fast", "Slow"]  # enum GrowthRate order


def node() -> str:
    path = shutil.which("node")
    if path is None:
        raise unittest.SkipTest("node is not installed")
    return path


def run_reader(file_bytes: bytes, calc_data: dict | None = None) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        save = pathlib.Path(directory) / "in.sav"
        save.write_bytes(file_bytes)
        args = [node(), str(REPO / "BPETools" / "tests" / "save_reader_cli.cjs"), str(save)]
        if calc_data is not None:
            data = pathlib.Path(directory) / "calc.json"
            data.write_text(json.dumps(calc_data), encoding="utf-8")
            args.append(str(data))
        result = subprocess.run(args, cwd=REPO, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


# Python reading --------------------------------------------------------------

def summary(values: dict, nickname: list[int]) -> dict:
    return {
        "personality": values["personality"], "otId": values["otId"], "nickname": nickname,
        "species": values["species"], "heldItem": values["heldItem"], "experience": values["experience"],
        "moves": [values[f"move{i}"] for i in range(1, 5)],
        "abilityNum": values["abilityNum"], "hiddenNatureModifier": values["hiddenNatureModifier"],
        "teraType": values["teraType"], "friendship": values["friendship"], "metLocation": values["metLocation"],
        "isEgg": values["isEgg"], "dead": values["dead"],
        "ivs": [values[stat + "IV"] for stat in STATS],
        "evs": [values[stat + "EV"] for stat in STATS],
        "hyperTrained": [values[name] for name in HYPER_TRAINED],
    }


def read_box_mon(record: bytes) -> dict | None:
    mon = fmt.decode_box_mon(record)
    if mon.get("isBadEgg") or not mon.checksum_valid or mon.get("species") == 0:
        return None
    values = dict(mon.fields, personality=mon.personality, otId=mon.otId)
    values["isEgg"] = int(bool(mon.get("isEgg") or mon.get("s3.isEgg")))
    return summary(values, list(mon.nickname) + [mon.get("nickname11"), mon.get("nickname12")])


def read_packed(record: bytes) -> dict | None:
    if fmt.is_packed_empty(record):
        return None
    values = {name: fmt.get_packed(record, name) for name, _, _ in fmt.PACKED_FIELDS}
    if values["isBadEgg"] or values["species"] == 0:
        return None
    return summary(values, [values[f"nickname{i}"] for i in range(12)])


def expected_reading(file_bytes: bytes) -> dict:
    _, image = fmt.find_flash_image(file_bytes)
    load_flags = {}
    if fmt.detect_format(image) == "2.1":
        loaded = fmt.load_v21_image(image)
        sb1, size, read = loaded.save_block_1, fmt.BOX_MON_SIZE, read_packed
        records = loaded.boxes
        names = {"box_restored": "boxRestored", "box_uncommitted": "boxUncommitted", "box_lost": "boxLost"}
        load_flags = {names[flag]: True for flag in loaded.load_flags}
    else:
        legacy = fmt.load_legacy_image(image)
        sb1, size, read = legacy.save_block_1, 80, read_box_mon
        records = legacy.storage[4:4 + 14 * 30 * 80]
    pokemon = []
    for slot in range(min(sb1[SB1_PARTY_COUNT], 6)):
        start = SB1_PARTY + slot * 100
        mon = read_box_mon(sb1[start:start + 80])
        if mon:
            pokemon.append(dict(mon, place="party", slot=slot, level=sb1[start + 84]))
    for index in range(len(records) // size):
        mon = read(records[index * size:(index + 1) * size])
        if mon:
            pokemon.append(dict(mon, place="box", box=index // 30, slot=index % 30))
    for slot in range(2):
        start = SB1_DAYCARE + slot * 140
        mon = read_box_mon(sb1[start:start + 80])
        if mon:
            pokemon.append(dict(mon, place="daycare", slot=slot))
    return {"format": fmt.detect_format(image), "loadFlags": load_flags, "pokemon": pokemon}


# Saves -----------------------------------------------------------------------

def make_mon(rng: random.Random, species: int | None = None, personality: int | None = None, **fields) -> bytes:
    mon = fmt.decode_box_mon(random_legacy_mon(rng, species))
    if personality is not None:
        mon.personality = personality
    mon.fields.update(fields)
    return fmt.encode_box_mon(mon)


def save_block_1(rng: random.Random, party: list[bytes], daycare: list[bytes], flags=(), variables=None) -> bytes:
    sb1 = bytearray(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK1_SIZE))
    sb1[SB1_PARTY_COUNT] = len(party)
    for slot in range(6):
        start = SB1_PARTY + slot * 100
        sb1[start:start + 100] = bytes(100)
        if slot < len(party):
            sb1[start:start + 80] = party[slot]
            sb1[start + 84] = 1 + slot
    for slot in range(2):
        start = SB1_DAYCARE + slot * 140
        sb1[start:start + 80] = daycare[slot] if slot < len(daycare) else bytes(80)
    sb1[SB1_FLAGS:SB1_FLAGS + 300] = bytes(300)
    for flag in flags:
        sb1[SB1_FLAGS + flag // 8] |= 1 << (flag % 8)
    sb1[SB1_VARS:SB1_VARS + 512] = bytes(512)
    for number, value in (variables or {}).items():
        start = SB1_VARS + 2 * (number - 0x4000)
        sb1[start:start + 2] = value.to_bytes(2, "little")
    return bytes(sb1)


def legacy_file(rng: random.Random, sb1: bytes, storage: bytes) -> bytes:
    return fmt.build_legacy_image(bytes(fmt.SAVEBLOCK2_SIZE), sb1, bytes(4), storage,
                                  counter=rng.randrange(1, 1000), rotation=rng.randrange(14))


def convert(file_bytes: bytes) -> bytes:
    _, image = fmt.find_flash_image(file_bytes)
    save, _ = fmt.convert_legacy_to_v21(fmt.load_legacy_image(image), game_id=0x5EED)
    return fmt.build_v21_image(save)


class SaveReaderTests(unittest.TestCase):
    def make_legacy(self, seed: int, fill: float = 0.4) -> bytes:
        rng = random.Random(seed)
        party = [random_legacy_mon(rng) for _ in range(5)] + [make_mon(rng, isEgg=1)]
        storage = bytearray(random_legacy_storage(rng, fill))
        if fill:
            storage[4 + 80 * 2 + 50] ^= 0x10  # a Bad Egg
        return legacy_file(rng, save_block_1(rng, party, [random_legacy_mon(rng)]), bytes(storage))

    def test_pre21_saves_match_python(self):
        for seed, fill in ((1, 0.0), (2, 0.4), (3, 1.0)):
            with self.subTest(seed=seed):
                file_bytes = self.make_legacy(seed, fill) + b"RTC!" + bytes(12)
                self.assertEqual(run_reader(file_bytes), expected_reading(file_bytes))

    def test_21_saves_match_python(self):
        for seed in (4, 5):
            with self.subTest(seed=seed):
                image = convert(self.make_legacy(seed, 0.8))
                reading = run_reader(image)
                self.assertEqual(reading["format"], "2.1")
                self.assertEqual(reading, expected_reading(image))
                self.assertEqual(sum(mon["place"] == "box" for mon in reading["pokemon"]),
                                 sum(mon["place"] == "box" for mon in run_reader(self.make_legacy(seed, 0.8))["pokemon"]))

    def test_damaged_box_sectors_load_like_the_game(self):
        image = bytearray(convert(self.make_legacy(6, 1.0)))
        # Sector 3 was being rewritten: its backup is the committed image.
        original = image[(fmt.SECTOR_BOX_FIRST + 3) * 4096:][:4096]
        image[fmt.SECTOR_BOX_BACKUP * 4096:(fmt.SECTOR_BOX_BACKUP + 1) * 4096] = original
        image[(fmt.SECTOR_BOX_FIRST + 3) * 4096 + 7] ^= 0x01
        # Sector 5 is torn and has no backup.
        image[(fmt.SECTOR_BOX_FIRST + 5) * 4096 + 9] ^= 0x01
        reading = run_reader(bytes(image))
        self.assertEqual(reading["loadFlags"], {"boxRestored": True, "boxLost": True})
        self.assertEqual(reading, expected_reading(bytes(image)))
        lost = range(5 * fmt.BOX_MONS_PER_SECTOR, 6 * fmt.BOX_MONS_PER_SECTOR)
        boxes = [mon["box"] * 30 + mon["slot"] for mon in reading["pokemon"] if mon["place"] == "box"]
        self.assertFalse(set(boxes) & set(lost))
        self.assertTrue(set(boxes) & set(range(3 * fmt.BOX_MONS_PER_SECTOR, 4 * fmt.BOX_MONS_PER_SECTOR)))

    def test_unreadable_files_report_errors(self):
        self.assertIn("does not contain", run_reader(b"\xFF" * fmt.FLASH_SIZE)["error"])
        self.assertIn("too small", run_reader(b"\x00" * 1000)["error"])
        image = bytearray(convert(self.make_legacy(7)))
        image[5] ^= 1  # progress copy A
        image[fmt.SECTOR_PROGRESS_B * 4096 + 5] ^= 1
        self.assertIn("damaged", run_reader(bytes(image))["error"])

    def test_real_saves_match_python(self):
        found = [path for path in REAL_PRE21_SAVES if path.exists()]
        if not found:
            self.skipTest("no local saves")
        for path in found:
            file_bytes = path.read_bytes()
            if fmt.detect_format(fmt.find_flash_image(file_bytes)[1]) == "empty":
                continue
            with self.subTest(save=path.name):
                self.assertEqual(run_reader(file_bytes), expected_reading(file_bytes))
                converted = convert(file_bytes)
                self.assertEqual(run_reader(converted), expected_reading(converted))


class CalculatorSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calc_data = json.loads(CALC_DATA.read_text(encoding="utf-8"))
        cls.save_data = cls.calc_data["save_data"]

    def species_number(self, name: str) -> int:
        return next(i for i, entry in enumerate(self.save_data["species"]) if entry and entry[0] == name)

    def move_number(self, name: str) -> int:
        return self.save_data["moves"].index(name)

    def test_sets_follow_the_game_rules(self):
        rng = random.Random(20)
        bulbasaur = self.species_number("Bulbasaur")
        charizard = self.species_number("Charizard")
        tackle = self.move_number("Tackle")
        # Nature 3 (Adamant) from the personality, changed to 6 (Docile) by a mint
        personality = 25 * 1000 + 3
        party = [
            make_mon(rng, bulbasaur, personality=personality, hiddenNatureModifier=3 ^ 6, experience=1059860,
                     abilityNum=1, move1=tackle, move2=0, move3=0, move4=0, heldItem=0,
                     hyperTrainedAttack=1, attackIV=3, hpIV=12, hpEV=252, dead=0, isEgg=0, **{"s3.isEgg": 0}),
            make_mon(rng, bulbasaur, abilityNum=2, experience=0, dead=0, isEgg=0, **{"s3.isEgg": 0}),
            make_mon(rng, charizard, dead=1, isEgg=0, **{"s3.isEgg": 0}),
            make_mon(rng, charizard, isEgg=1, dead=0),
        ]
        sb1 = save_block_1(rng, party, [])
        reading = run_reader(legacy_file(rng, sb1, bytes(fmt.LEGACY_STORAGE_SIZE)), self.calc_data)
        self.assertEqual(reading["counts"], {"party": 3, "box": 0, "daycare": 0, "eggs": 1, "fainted": 0, "unknown": 0})
        self.assertEqual(reading["party"], ["Bulbasaur (My Box)", "Bulbasaur (My Box 2)", "Charizard (My Box)"])
        first, second = reading["sets"]["Bulbasaur"]["My Box"], reading["sets"]["Bulbasaur"]["My Box 2"]
        self.assertEqual(first["level"], 100)  # Medium Slow reaches 100 at 1,059,860 exp
        self.assertEqual(first["nature"], "Docile")
        self.assertEqual(first["moves"], ["Tackle", "(No Move)", "(No Move)", "(No Move)"])
        self.assertNotIn("item", first)
        self.assertEqual(first["ivs"]["at"], 31)  # hyper trained
        self.assertEqual(first["ivs"]["hp"], 12)
        self.assertEqual(first["evs"]["hp"], 252)
        # Bulbasaur has no second ability; the game falls back to the first
        self.assertEqual(first["ability"], "Overgrow")
        self.assertEqual(second["ability"], "Chlorophyll")
        self.assertEqual(second["level"], 1)
        self.assertFalse(reading["nuzlocke"])

        # In a Nuzlocke run from 2.1 on, EVs do not count and fainted Pokémon are gone.
        randomizer = self.save_data["randomizerVars"][0]
        sb1 = save_block_1(rng, party, [], flags=[self.save_data["nuzlockeFlag"]], variables={randomizer: 1})
        reading = run_reader(legacy_file(rng, sb1, bytes(fmt.LEGACY_STORAGE_SIZE)), self.calc_data)
        self.assertTrue(reading["nuzlocke"])
        self.assertTrue(reading["randomized"])
        self.assertEqual(reading["counts"]["fainted"], 1)
        self.assertEqual(reading["party"], ["Bulbasaur (My Box)", "Bulbasaur (My Box 2)"])
        self.assertEqual(reading["sets"]["Bulbasaur"]["My Box"]["evs"]["hp"], 0)

    def test_real_saves_import_completely(self):
        found = [path for path in REAL_PRE21_SAVES if path.exists()]
        if not found:
            self.skipTest("no local saves")
        for path in found:
            file_bytes = path.read_bytes()
            if fmt.detect_format(fmt.find_flash_image(file_bytes)[1]) == "empty":
                continue
            with self.subTest(save=path.name):
                reading = run_reader(file_bytes, self.calc_data)
                counts = reading["counts"]
                self.assertEqual(counts["unknown"], 0)
                total = counts["party"] + counts["box"] + counts["daycare"] + counts["eggs"] + counts["fainted"]
                self.assertEqual(total, len(reading["pokemon"]))
                self.assertEqual(sum(len(sets) for sets in reading["sets"].values()),
                                 counts["party"] + counts["box"] + counts["daycare"])
                # Levels worked out from experience agree with the party's stored levels.
                party_levels = [mon["level"] for mon in reading["pokemon"] if mon["place"] == "party" and not mon["isEgg"]]
                imported = [reading["sets"][entry.split(" (")[0]][entry[entry.index("(") + 1:-1]]["level"]
                            for entry in reading["party"]]
                self.assertEqual(imported, party_levels)

    def test_experience_matches_the_game(self):
        levels = json.loads(subprocess.run(
            [node(), "-e", "const m = require(process.argv[1]); const g = JSON.parse(process.argv[2]);"
             "console.log(JSON.stringify(g.map(r => Array.from({length: 101}, (_, l) => m.experienceFor(r, l)))))",
             str(IMPORT_JS), json.dumps(GROWTH_RATES)],
            capture_output=True, text=True, check=True, timeout=60).stdout)
        # Level 100 for every growth rate
        self.assertEqual([table[100] for table in levels], [1000000, 600000, 1640000, 1059860, 800000, 1250000])
        self.assertEqual(set(self.save_data["growthRates"]) - set(GROWTH_RATES), set())
        game = game_experience_tables()
        if game is None:
            self.skipTest("no host C compiler")
        self.assertEqual(levels, game)


def game_experience_tables() -> list[list[int]] | None:
    """gExperienceTables from src/data/pokemon/experience_tables.h, compiled for the host."""
    if shutil.which("wsl") is None and shutil.which("cc") is None:
        return None
    build = REPO / "build" / "calc_save_import"
    build.mkdir(parents=True, exist_ok=True)
    (build / "experience.c").write_text(
        "#include <stdio.h>\ntypedef unsigned int u32;\n#define MAX_LEVEL 100\n"
        "#include \"data/pokemon/experience_tables.h\"\n"
        "int main(void) { for (int g = 0; g < 6; g++) { for (int l = 0; l <= MAX_LEVEL; l++)"
        " printf(\"%u \", gExperienceTables[g][l]); printf(\"\\n\"); } return 0; }\n", encoding="utf-8")
    try:
        compiled = subprocess.run(host_command(["cc", "-iquote", "src", "-o", host_path(build / "experience"),
                                                host_path(build / "experience.c")]),
                                  cwd=REPO, capture_output=True, text=True, timeout=120)
        if compiled.returncode != 0:
            raise AssertionError(compiled.stderr)
        output = subprocess.run(host_command([host_path(build / "experience")]), cwd=REPO,
                                capture_output=True, text=True, check=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return [[int(value) for value in line.split()] for line in output.splitlines()]


class SaveNumberingTests(unittest.TestCase):
    def constants(self, text: str, prefix: str) -> dict[str, int]:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "constants.h"
            path.write_text(text, encoding="utf-8")
            return build_calc_data.c_constants(str(path), prefix)

    def test_reads_defines_and_enums(self):
        # 1.0.1 numbered everything with #defines
        self.assertEqual(self.constants(
            "#define SPECIES_NONE 0\n#define SPECIES_BULBASAUR 1 // first\n#define FORMS_START 2\n"
            "#define SPECIES_ROTOM_HEAT (FORMS_START + 3)\n#define SPECIES_ALIAS SPECIES_BULBASAUR\n", "SPECIES_"),
            {"SPECIES_NONE": 0, "SPECIES_BULBASAUR": 1, "SPECIES_ROTOM_HEAT": 5, "SPECIES_ALIAS": 1})
        # Current sources use enums with implicit values, aliases and macro-generated members
        self.assertEqual(self.constants(
            "enum __attribute__((packed)) Item\n{\n    ITEM_NONE = 0,\n    ITEM_A,\n    ITEM_B = 0x10, /* hex */\n"
            "    ITEM_OLD_B = ITEM_B,\n    ITEM_C,\n    #define ENUM_TM(n, id) CAT(ITEM_TM_, id) = CAT(ITEM_TM, n),\n"
            "    RECURSIVELY(R_ZIP(ENUM_TM, NUMBERS, (FOREACH_TM(APPEND_COMMA))))\n    #undef ENUM_TM\n"
            "    ITEM_D = 40,\n    ITEMS_COUNT,\n};\n", "ITEM_"),
            {"ITEM_NONE": 0, "ITEM_A": 1, "ITEM_B": 16, "ITEM_OLD_B": 16, "ITEM_C": 17, "ITEM_D": 40})

    def test_current_source_numbering(self):
        constants = build_calc_data.c_constants(str(REPO / "include/constants/species.h"), "SPECIES_")
        self.assertEqual(constants["SPECIES_BULBASAUR"], 1)
        self.assertEqual(constants["SPECIES_RATTATA_ALOLAN"], constants["SPECIES_RATTATA_ALOLA"])
        items = build_calc_data.c_constants(str(REPO / "include/constants/items.h"), "ITEM")
        self.assertEqual(items["ITEM_HM01"], 824)
        self.assertEqual(items["ITEM_LEVEL_LIMITER"], 1021)
        self.assertEqual(items["ITEMS_COUNT"], 1022)
        flags = build_calc_data.c_constants(str(REPO / "include/constants/flags.h"), "FLAG_NUZLOCKE")
        self.assertEqual(flags, {"FLAG_NUZLOCKE": 0x493})

    def test_committed_calc_data_has_save_numbering(self):
        data = json.loads(CALC_DATA.read_text(encoding="utf-8"))["save_data"]
        self.assertTrue(data["nuzlockeIgnoresEvs"])
        self.assertEqual(data["species"][1][0], "Bulbasaur")
        self.assertEqual(data["moves"][1], "Pound")
        self.assertEqual(len(data["randomizerVars"]), 5)


if __name__ == "__main__":
    unittest.main()
