from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_DIR))
sys.path.insert(0, str(TOOL_DIR.parents[1] / "BPETools"))

import bpe_save_format as fmt  # noqa: E402

from inspect_save import (  # noqa: E402
    FOOTER_OFFSET,
    SAVEBLOCK3_CHUNK_SIZE,
    SECTOR_DATA_SIZE,
    SECTOR_SIGNATURE,
    SECTOR_SIZE,
    Schema,
    Symbols,
    checksum,
    decode_game_text,
    inspect_save,
    parse_rom_header,
    parse_pokemon,
    resolve_symbol,
)

# Old-format (2.0.x) saves are built and decoded with the 2.0.1 release profile;
# the unversioned layout describes the current (2.1) source.
OLD_PROFILE_DIR = TOOL_DIR / "profiles" / "2.0.1"



def encode_text(value: str, length: int) -> bytes:
    output = bytearray([0xFF] * length)
    for index, char in enumerate(value[:length]):
        if "A" <= char <= "Z":
            output[index] = 0xBB + ord(char) - ord("A")
        elif "a" <= char <= "z":
            output[index] = 0xD5 + ord(char) - ord("a")
        elif "0" <= char <= "9":
            output[index] = 0xA1 + ord(char) - ord("0")
        elif char == " ":
            output[index] = 0
    return bytes(output)


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = Schema(OLD_PROFILE_DIR / "bpe_layout.json")
        cls.symbols = Symbols(OLD_PROFILE_DIR / "bpe_symbols.json")
        cls.symbol_document = json.loads((OLD_PROFILE_DIR / "bpe_symbols.json").read_text(encoding="utf-8"))
        cls.current_schema = Schema(TOOL_DIR / "bpe_layout.json")
        cls.current_symbols = Symbols(TOOL_DIR / "bpe_symbols.json")
        cls.current_symbol_document = json.loads((TOOL_DIR / "bpe_symbols.json").read_text(encoding="utf-8"))
        cls.vectors = json.loads(
            (TOOL_DIR.parents[1] / "BPETools" / "tests" / "fixtures" / "packed_box_mon_vectors.json").read_text(encoding="utf-8")
        )["vectors"]

    def member_offset(self, root: str, name: str, schema: Schema | None = None) -> int:
        return int((schema or self.schema).member(root, name)["offset"])

    def make_mon(self) -> bytes:
        record = bytearray(100)
        struct.pack_into("<II", record, 0, 0, 0)
        record[8:18] = encode_text("PIKACHU", 10)
        record[18] = 2
        record[19] = 0x02
        record[20:27] = encode_text("BPE", 7)
        growth = memoryview(record)[32:44]
        attacks = memoryview(record)[44:56]
        condition = memoryview(record)[56:68]
        misc = memoryview(record)[68:80]
        struct.pack_into("<H", growth, 0, 25)
        struct.pack_into("<H", growth, 2, 1)
        struct.pack_into("<I", growth, 4, 1000)
        growth[9] = 200
        for index, move in enumerate((33, 45, 98, 0)):
            struct.pack_into("<H", attacks, index * 2, move)
        attacks[8:12] = bytes((35, 40, 30, 0))
        condition[0:6] = bytes((1, 2, 3, 4, 5, 6))
        struct.pack_into("<I", misc, 4, 31 | (30 << 5) | (29 << 10))
        stored = sum(struct.unpack_from("<24H", record, 32)) & 0xFFFF
        struct.pack_into("<H", record, 28, stored)
        struct.pack_into("<IBB7H", record, 80, 0, 12, 0, 30, 35, 20, 18, 22, 21, 19)
        return bytes(record)

    def make_blocks(self, variant: int, schema: Schema | None = None) -> dict[str, bytearray]:
        schema = schema or self.schema
        symbol_document = self.symbol_document if schema is self.schema else self.current_symbol_document

        def member_offset(root: str, name: str) -> int:
            return self.member_offset(root, name, schema)

        blocks = {
            "SaveBlock1": bytearray(int(schema.root("SaveBlock1")["size"])),
            "SaveBlock2": bytearray(int(schema.root("SaveBlock2")["size"])),
            "SaveBlock3": bytearray(int(schema.root("SaveBlock3")["size"])),
            "PokemonStorage": bytearray(int(schema.root("PokemonStorage")["size"])),
        }
        sb1, sb2, sb3, storage = blocks.values()
        sb2[0:8] = encode_text("PLAYER", 8)
        sb2[8] = 1
        struct.pack_into("<HHHBBB", sb2, 10, 12345, 54321, 25, 6, 7, 8)
        key = 0x12345678
        struct.pack_into("<I", sb2, member_offset("SaveBlock2", "encryptionKey"), key)

        struct.pack_into("<hh", sb1, member_offset("SaveBlock1", "pos"), 4, 9)
        location = member_offset("SaveBlock1", "location")
        struct.pack_into("<bbbBhh", sb1, location, 0, 9, 1, 0, 4, 9)
        struct.pack_into("<I", sb1, member_offset("SaveBlock1", "money"), (1000 + variant) ^ key)
        struct.pack_into("<H", sb1, member_offset("SaveBlock1", "coins"), (25 + variant) ^ (key & 0xFFFF))

        flag_id = int(symbol_document["flags"]["FLAG_BADGE01_GET"])
        flags_offset = member_offset("SaveBlock1", "flags")
        sb1[flags_offset + flag_id // 8] |= 1 << (flag_id & 7)
        var_id = int(symbol_document["vars"]["VAR_STARTER_MON"])
        vars_offset = member_offset("SaveBlock1", "vars")
        struct.pack_into("<H", sb1, vars_offset + (var_id - 0x4000) * 2, 25 + variant)

        party_count = member_offset("SaveBlock1", "playerPartyCount")
        party = member_offset("SaveBlock1", "playerParty")
        sb1[party_count] = 1
        sb1[party:party + 100] = self.make_mon()

        boxes = member_offset("PokemonStorage", "boxes")
        box_type, _ = schema.array(schema.member("PokemonStorage", "boxes"))
        if schema.size(box_type) == fmt.BOX_MON_SIZE:
            packed, kind = fmt.pack_box_mon(self.make_mon()[:80])
            self.assertEqual(kind, "ok")
            storage[boxes:boxes + fmt.BOX_MON_SIZE] = packed
        else:
            storage[boxes:boxes + 80] = self.make_mon()[:80]
        names = member_offset("PokemonStorage", "boxNames")
        storage[names:names + 9] = encode_text("BOX ONE", 9)
        sb3[0] = 7 + variant
        return blocks

    def make_slot(self, blocks: dict[str, bytearray], counter: int, rotation: int) -> bytes:
        logical: dict[int, bytes] = {0: bytes(blocks["SaveBlock2"])}
        for section_id in range(1, 5):
            start = (section_id - 1) * SECTOR_DATA_SIZE
            logical[section_id] = bytes(blocks["SaveBlock1"][start:start + SECTOR_DATA_SIZE])
        for section_id in range(5, 14):
            start = (section_id - 5) * SECTOR_DATA_SIZE
            logical[section_id] = bytes(blocks["PokemonStorage"][start:start + SECTOR_DATA_SIZE])

        sectors = [bytearray(SECTOR_SIZE) for _ in range(14)]
        for physical in range(14):
            section_id = (physical + rotation) % 14
            body = logical[section_id]
            sectors[physical][:len(body)] = body
            sb3_start = section_id * SAVEBLOCK3_CHUNK_SIZE
            chunk = blocks["SaveBlock3"][sb3_start:sb3_start + SAVEBLOCK3_CHUNK_SIZE]
            sectors[physical][SECTOR_DATA_SIZE:SECTOR_DATA_SIZE + len(chunk)] = chunk
            struct.pack_into("<HHII", sectors[physical], FOOTER_OFFSET, section_id, checksum(body, len(body)), SECTOR_SIGNATURE, counter)
        return b"".join(sectors)

    def make_save(self) -> bytes:
        return (
            self.make_slot(self.make_blocks(0), 10, 3)
            + self.make_slot(self.make_blocks(1), 11, 8)
            + bytes([0xFF]) * (4 * SECTOR_SIZE)
        )

    def test_sav_and_srm_select_newest_and_decode_bpe_data(self) -> None:
        for suffix in (".sav", ".srm"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"player{suffix}"
                path.write_bytes(self.make_save())
                report, _ = inspect_save(path, self.schema, self.symbols)
                self.assertEqual(report["selected_slot"], {"slot": 1, "counter": 11, "complete": True})
                self.assertEqual(report["trainer"]["name"], "PLAYER")
                self.assertEqual(report["economy"], {"money": 1001, "coins": 26})
                self.assertEqual(report["world"]["location"]["map_names"], ["MAP_LITTLEROOT_TOWN"])
                badge = next(item for item in report["flags"] if "FLAG_BADGE01_GET" in item["names"])
                starter = next(item for item in report["variables"] if "VAR_STARTER_MON" in item["names"])
                self.assertTrue(badge["set"])
                self.assertEqual(starter["value"], 26)
                self.assertEqual(report["save_block_3"]["dexNavChain"], 8)
                self.assertEqual(report["party_count"], 1)
                self.assertEqual(report["party"][0]["species"]["id"], 25)
                self.assertTrue(report["party"][0]["checksum_valid"])
                self.assertEqual(report["boxes"][0]["pokemon"][0]["species"]["id"], 25)

    def test_blank_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.sav"
            path.write_bytes(bytes([0xFF]) * (32 * SECTOR_SIZE))
            with self.assertRaisesRegex(ValueError, "No Pokémon Emerald sector signatures"):
                inspect_save(path, self.schema, self.symbols)

    def test_flag_query_is_tied_to_source_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "player.srm"
            path.write_bytes(self.make_save())
            report, _ = inspect_save(path, self.schema, self.symbols)
            result = resolve_symbol(report, self.symbols, "FLAG_BADGE01_GET", TOOL_DIR.parents[1])
            self.assertTrue(result["state"]["set"])
            self.assertTrue(result["source_references"])
            self.assertTrue(any(item["operation"] in {"set", "check_or_gate"} for item in result["source_references"]))

    def test_public_rom_header_matches_generated_layout(self) -> None:
        rom = TOOL_DIR.parents[1] / "pokeemerald-release.gba"
        if not rom.exists():
            self.skipTest("Local test ROM is not present")
        header = parse_rom_header(rom)
        self.assertEqual(header["save_block_1_size"], self.current_schema.root("SaveBlock1")["size"])
        self.assertEqual(header["flags_offset"], self.member_offset("SaveBlock1", "flags", self.current_schema))
        self.assertEqual(header["bag_counts"]["tm_hm"], 250)

    def test_cli_auto_selects_release_profile_from_rom_hash(self) -> None:
        releases = {
            "2.0.0-beta": "4f39a49bd4e8cb1adead8b8f2e7999d957c6bcb1",
            "2.0.1": "6c25a87610754b62145b83095b4290d00c27831e",
        }
        for version, commit in releases.items():
            with self.subTest(version=version):
                rom = TOOL_DIR.parents[1] / f"BlackPearlEmerald_v{version}.gba"
                if not rom.exists():
                    self.skipTest(f"Local {version} release ROM is not present")
                with tempfile.TemporaryDirectory() as directory:
                    save_path = Path(directory) / "player.srm"
                    report_path = Path(directory) / "report.json"
                    save_path.write_bytes(self.make_save())
                    process = subprocess.run(
                        [sys.executable, str(TOOL_DIR / "inspect_save.py"), "inspect", str(save_path), "--rom", str(rom), "-o", str(report_path)],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(process.returncode, 0, process.stderr)
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    self.assertEqual(report["layout"]["git_commit"], commit)
                    self.assertEqual(report["rom"]["release"]["version"], version)
                    self.assertFalse(report["rom"]["layout_mismatches"])


    # ------------------------------------------------------------------
    # 2.1 saves

    GAME_ID = 0x5EEDBEEF

    def fixture_mons(self) -> list[tuple[bytes, bytes]]:
        """Real (80-byte encrypted, 60-byte packed) pairs from test/save.c."""
        result = []
        for vector in self.vectors:
            record, packed = bytes.fromhex(vector["boxPokemon"]), bytes.fromhex(vector["packed"])
            made, kind = fmt.pack_box_mon(record)
            if kind == "ok" and any(packed):
                self.assertEqual(made, packed)
                result.append((record, packed))
        return result

    def v21_save(self, variant: int) -> fmt.V21Save:
        schema = self.current_schema
        blocks = self.make_blocks(variant, schema)
        storage = bytearray(blocks["PokemonStorage"])
        boxes_offset = self.member_offset("PokemonStorage", "boxes", schema)
        for (box, slot), (_, packed) in zip(((3, 7), (40, 29)), self.fixture_mons()):
            start = boxes_offset + (box * fmt.IN_BOX_COUNT + slot) * fmt.BOX_MON_SIZE
            storage[start:start + fmt.BOX_MON_SIZE] = packed
        return fmt.V21Save(
            game_id=self.GAME_ID,
            save_block_2=bytes(blocks["SaveBlock2"]),
            storage_header=bytes(storage[:boxes_offset]),
            save_block_3=bytes(blocks["SaveBlock3"]),
            save_block_1=bytes(blocks["SaveBlock1"]),
            boxes=bytes(storage[boxes_offset:]),
        )

    def inspect_v21(self, image: bytes, suffix: str = ".sav", **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"player{suffix}"
            path.write_bytes(image)
            return inspect_save(path, self.current_schema, self.current_symbols, **kwargs)

    def test_v21_save_decodes_party_boxes_flags_and_health(self) -> None:
        image = fmt.build_v21_image(self.v21_save(1), counter=6)
        # An emulator wrapper in front of the flash image must still be found.
        for suffix, data in ((".sav", image), (".srm", bytes(64) + image)):
            with self.subTest(suffix=suffix):
                report, blocks = self.inspect_v21(data, suffix)
                self.assertEqual(report["save_format"], "2.1")
                self.assertEqual(report["format"], "bpe-save-inspector-v1")
                self.assertEqual(report["payload"]["offset"], len(data) - len(image))
                self.assertEqual(report["selected_slot"], {"slot": 1, "copy": "B", "counter": 7, "complete": True})
                engine = report["save_engine"]
                self.assertEqual(engine["game_id"], f"0x{self.GAME_ID:08X}")
                self.assertEqual(engine["load_result"], "ok")
                self.assertEqual(engine["load_flags"], [])
                self.assertEqual(engine["total_boxes"], 41)
                self.assertEqual([copy["counter"] for copy in engine["progress_copies"]], [6, 7])
                self.assertTrue(all(copy["complete"] for copy in engine["progress_copies"]))
                self.assertEqual(engine["box_sectors_not_committed"], [])

                health = report["sector_health"]
                self.assertEqual(len(health), 32)
                self.assertEqual([item["role"] for item in health[:10]], ["progress_copy_a"] * 5 + ["progress_copy_b"] * 5)
                self.assertTrue(all(item["valid"] and item["crc_valid"] and item["signature_valid"] for item in health[:29]))
                self.assertTrue(all(item["committed"] for item in health[10:29]))
                self.assertEqual(health[10]["box_sector"], 0)
                self.assertEqual(health[29]["role"], "box_backup")
                self.assertFalse(health[29]["valid"])
                self.assertEqual({item["role"] for item in health[30:]}, {"hall_of_fame"})
                self.assertNotIn("raw", health[0])

                self.assertEqual(report["trainer"]["name"], "PLAYER")
                self.assertEqual(report["economy"], {"money": 1001, "coins": 26})
                self.assertEqual(report["world"]["location"]["map_names"], ["MAP_LITTLEROOT_TOWN"])
                badge = next(item for item in report["flags"] if "FLAG_BADGE01_GET" in item["names"])
                starter = next(item for item in report["variables"] if "VAR_STARTER_MON" in item["names"])
                self.assertTrue(badge["set"])
                self.assertEqual(starter["value"], 26)
                self.assertEqual(report["save_block_3"]["dexNavChain"], 8)
                self.assertEqual(report["party_count"], 1)
                self.assertEqual(report["party"][0]["species"]["id"], 25)
                self.assertTrue(report["party"][0]["checksum_valid"])

                self.assertEqual(len(report["boxes"]), 41)
                self.assertEqual(report["boxes"][0]["name"], "BOX ONE")
                occupied = {(box["box"], mon["slot"]): mon for box in report["boxes"] for mon in box["pokemon"]}
                self.assertEqual(sorted(occupied), [(0, 0), (3, 7), (40, 29)])
                pikachu = occupied[(0, 0)]
                self.assertTrue(pikachu["packed"])
                self.assertIsNone(pikachu["checksum_valid"])
                self.assertNotIn("move_pp", pikachu)
                self.assertNotIn("contest", pikachu)
                self.assertEqual(pikachu["species"]["id"], 25)
                self.assertEqual(pikachu["nickname"], "PIKACHU")
                self.assertEqual(pikachu["original_trainer_name"], "BPE")
                self.assertEqual(pikachu["experience"], 1000)
                self.assertEqual(pikachu["friendship"], 200)
                self.assertEqual([move["id"] for move in pikachu["moves"]], [33, 45, 98, 0])
                self.assertEqual(pikachu["evs"]["speed"], 4)
                self.assertEqual(
                    pikachu["ivs"],
                    {"hp": 31, "attack": 30, "defense": 29, "speed": 0, "special_attack": 0, "special_defense": 0},
                )
                for position, (record, _) in zip(((3, 7), (40, 29)), self.fixture_mons()):
                    expected = fmt.decode_box_mon(record)
                    mon = occupied[position]
                    self.assertEqual(mon["personality"], expected.personality)
                    self.assertEqual(mon["species"]["id"], expected.get("species"))
                    self.assertTrue(mon["species"]["names"])
                    self.assertEqual(mon["held_item"]["id"], expected.get("heldItem"))
                    self.assertEqual(mon["experience"], expected.get("experience"))
                    self.assertEqual(mon["is_egg"], bool(expected.get("isEgg") or expected.get("s3.isEgg")))
                    nickname = bytes(expected.nickname) + bytes((expected.get("nickname11"), expected.get("nickname12")))
                    self.assertEqual(mon["nickname"], decode_game_text(nickname))

                self.assertEqual(len(blocks["pokemon_storage"]), self.current_schema.root("PokemonStorage")["size"])
                dumped = self.current_schema.decode(blocks["pokemon_storage"], self.current_schema.roots["PokemonStorage"])
                self.assertEqual(len(dumped["boxes"]), 41)

    def test_v21_damaged_newer_copy_falls_back_to_older(self) -> None:
        older = fmt.build_v21_image(self.v21_save(0), counter=4, both_copies=False)
        newer = fmt.build_v21_image(self.v21_save(1), counter=5, both_copies=False)
        size = fmt.SECTOR_SIZE
        image = bytearray(newer)
        image[0:5 * size] = older[0:5 * size]  # copy A: older progress
        image[5 * size:10 * size] = newer[0:5 * size]  # copy B: newer progress
        report, _ = self.inspect_v21(bytes(image))
        self.assertEqual(report["selected_slot"]["copy"], "B")
        self.assertEqual(report["economy"]["money"], 1001)
        self.assertEqual(report["save_engine"]["load_flags"], [])

        image[7 * size + 100] ^= 0xFF  # corrupt copy B, part 2
        report, _ = self.inspect_v21(bytes(image))
        self.assertEqual(report["selected_slot"], {"slot": 0, "copy": "A", "counter": 4, "complete": True})
        self.assertEqual(report["economy"]["money"], 1000)
        self.assertEqual(report["save_engine"]["load_result"], "ok_backup")
        self.assertFalse(report["sector_health"][7]["valid"])
        self.assertFalse(report["sector_health"][7]["crc_valid"])
        self.assertEqual(report["save_engine"]["progress_copies"][1]["valid_parts"], [0, 1, 3, 4])
        self.assertTrue(any("copy B is damaged" in warning for warning in report["warnings"]))
        # The box sectors belong to the newer commit, so the game keeps them as uncommitted.
        self.assertIn("box_uncommitted", report["save_engine"]["load_flags"])
        self.assertEqual(len(report["save_engine"]["box_sectors_not_committed"]), 19)

    def test_v21_box_sector_restored_from_backup(self) -> None:
        image = bytearray(fmt.build_v21_image(self.v21_save(0), counter=2))
        size = fmt.SECTOR_SIZE
        image[29 * size:30 * size] = image[10 * size:11 * size]
        image[10 * size + 5] ^= 0x55
        report, _ = self.inspect_v21(bytes(image))
        self.assertEqual(report["save_engine"]["load_flags"], ["box_restored"])
        self.assertTrue(report["sector_health"][29]["matches_commit"])
        problems = report["save_engine"]["box_sectors_not_committed"]
        self.assertEqual([(item["box_sector"], item["status"]) for item in problems], [(0, "invalid")])
        self.assertEqual(report["boxes"][0]["pokemon"][0]["species"]["id"], 25)

    def test_v21_forced_copy(self) -> None:
        image = fmt.build_v21_image(self.v21_save(0), counter=2)
        report, _ = self.inspect_v21(image, forced_slot=0)
        self.assertEqual(report["selected_slot"]["copy"], "A")
        self.assertTrue(any("forced" in warning for warning in report["warnings"]))

    def test_format_and_layout_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            new_path = Path(directory) / "new.sav"
            new_path.write_bytes(fmt.build_v21_image(self.v21_save(0)))
            with self.assertRaisesRegex(ValueError, "BPE 2.1 save"):
                inspect_save(new_path, self.schema, self.symbols)
            old_path = Path(directory) / "old.sav"
            old_path.write_bytes(self.make_save())
            with self.assertRaisesRegex(ValueError, r"pre-2\.1 .*--profile 2\.0\.1"):
                inspect_save(old_path, self.current_schema, self.current_symbols)

    def test_v21_cli_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save, before = root / "player.srm", root / "before.srm"
            save.write_bytes(fmt.build_v21_image(self.v21_save(1)))
            before.write_bytes(fmt.build_v21_image(self.v21_save(0)))
            script = str(TOOL_DIR / "inspect_save.py")
            commands = {
                "query": ["query", str(save), "FLAG_BADGE01_GET", "-o", str(root / "query.json")],
                "extract": ["extract", str(save), str(root / "raw")],
                "dump": ["dump", str(save), "PokemonStorage", "-o", str(root / "dump.json")],
                "diff": ["diff", str(before), str(save), "-o", str(root / "diff.json")],
            }
            for name, arguments in commands.items():
                with self.subTest(command=name):
                    process = subprocess.run(
                        [sys.executable, script, *arguments], capture_output=True, text=True, encoding="utf-8",
                    )
                    self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(
                (root / "raw" / "pokemon_storage.bin").stat().st_size,
                self.current_schema.root("PokemonStorage")["size"],
            )
            difference = json.loads((root / "diff.json").read_text(encoding="utf-8"))
            self.assertEqual(difference["economy"]["after"]["money"], 1001)
            self.assertTrue(any("VAR_STARTER_MON" in item["names"] for item in difference["variable_changes"]))
            query = json.loads((root / "query.json").read_text(encoding="utf-8"))
            self.assertTrue(query["queries"][0]["state"]["set"])
            process = subprocess.run(
                [sys.executable, script, "--profile", "2.0.1", "inspect", str(save)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("BPE 2.1 save", process.stderr)

if __name__ == "__main__":
    unittest.main()
