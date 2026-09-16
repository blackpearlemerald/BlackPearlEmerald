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

from inspect_save import (  # noqa: E402
    FOOTER_OFFSET,
    SAVEBLOCK3_CHUNK_SIZE,
    SECTOR_DATA_SIZE,
    SECTOR_SIGNATURE,
    SECTOR_SIZE,
    Schema,
    Symbols,
    checksum,
    inspect_save,
    parse_rom_header,
    parse_pokemon,
    resolve_symbol,
)


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
        cls.schema = Schema(TOOL_DIR / "bpe_layout.json")
        cls.symbols = Symbols(TOOL_DIR / "bpe_symbols.json")
        cls.symbol_document = json.loads((TOOL_DIR / "bpe_symbols.json").read_text(encoding="utf-8"))

    def member_offset(self, root: str, name: str) -> int:
        return int(self.schema.member(root, name)["offset"])

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

    def make_blocks(self, variant: int) -> dict[str, bytearray]:
        blocks = {
            "SaveBlock1": bytearray(int(self.schema.root("SaveBlock1")["size"])),
            "SaveBlock2": bytearray(int(self.schema.root("SaveBlock2")["size"])),
            "SaveBlock3": bytearray(int(self.schema.root("SaveBlock3")["size"])),
            "PokemonStorage": bytearray(int(self.schema.root("PokemonStorage")["size"])),
        }
        sb1, sb2, sb3, storage = blocks.values()
        sb2[0:8] = encode_text("PLAYER", 8)
        sb2[8] = 1
        struct.pack_into("<HHHBBB", sb2, 10, 12345, 54321, 25, 6, 7, 8)
        key = 0x12345678
        struct.pack_into("<I", sb2, self.member_offset("SaveBlock2", "encryptionKey"), key)

        struct.pack_into("<hh", sb1, self.member_offset("SaveBlock1", "pos"), 4, 9)
        location = self.member_offset("SaveBlock1", "location")
        struct.pack_into("<bbbBhh", sb1, location, 0, 9, 1, 0, 4, 9)
        struct.pack_into("<I", sb1, self.member_offset("SaveBlock1", "money"), (1000 + variant) ^ key)
        struct.pack_into("<H", sb1, self.member_offset("SaveBlock1", "coins"), (25 + variant) ^ (key & 0xFFFF))

        flag_id = int(self.symbol_document["flags"]["FLAG_BADGE01_GET"])
        flags_offset = self.member_offset("SaveBlock1", "flags")
        sb1[flags_offset + flag_id // 8] |= 1 << (flag_id & 7)
        var_id = int(self.symbol_document["vars"]["VAR_STARTER_MON"])
        vars_offset = self.member_offset("SaveBlock1", "vars")
        struct.pack_into("<H", sb1, vars_offset + (var_id - 0x4000) * 2, 25 + variant)

        party_count = self.member_offset("SaveBlock1", "playerPartyCount")
        party = self.member_offset("SaveBlock1", "playerParty")
        sb1[party_count] = 1
        sb1[party:party + 100] = self.make_mon()

        boxes = self.member_offset("PokemonStorage", "boxes")
        storage[boxes:boxes + 80] = self.make_mon()[:80]
        names = self.member_offset("PokemonStorage", "boxNames")
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
        self.assertEqual(header["save_block_1_size"], self.schema.root("SaveBlock1")["size"])
        self.assertEqual(header["flags_offset"], self.member_offset("SaveBlock1", "flags"))
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


if __name__ == "__main__":
    unittest.main()
