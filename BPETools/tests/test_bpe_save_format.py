"""Tests for BPETools/bpe_save_format.py (pre-2.1 reader, 2.1 writer and converter).

Byte vectors come from the game's C code (BPETools/save_format_vectors.py).
Saves written here are also loaded by the game's own save engine, compiled for
the host as BPETools/save_sim/save_verify, when a C compiler is available.
Real player saves are used when they exist on this computer; they are never
committed.
"""

from __future__ import annotations

import json
import os
import pathlib
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "BPETools"))

import bpe_save_format as fmt  # noqa: E402

VECTORS = REPO / "BPETools" / "tests" / "fixtures" / "packed_box_mon_vectors.json"
# Local player saves, never committed. Every release before 2.1 shares one
# layout, so 1.0.1 saves convert through the same path as 2.0.x saves.
REAL_PRE21_SAVES = [
    REPO / "BlackPearlEmerald_v2.0.0-beta.sav",
    REPO / "BPETools" / "Pokemon Black Pearl Emerald v2.0.1(captainvictory).sav",
    REPO / "BPETools" / "Black Pearl Emerald (v1.0.1)(Jester).srm",
    REPO / "BPETools" / "Black Pearl Emerald (v1.0.1)(Jester)(Boats Fixed).srm",
]


def to_wsl(path: pathlib.Path) -> str:
    drive = path.drive.rstrip(":").lower()
    return f"/mnt/{drive}{path.as_posix()[len(path.drive):]}"


def host_command(args: list[str]) -> list[str]:
    if os.name == "nt":
        return ["wsl", "-d", os.environ.get("BPE_WSL_DISTRO", "Ubuntu"), "--cd", to_wsl(REPO), "--exec"] + args
    return args


def host_path(path: pathlib.Path) -> str:
    return to_wsl(path) if os.name == "nt" else str(path)


_VERIFY_TOOL: str | None = None
_VERIFY_TRIED = False


def verify_tool() -> str | None:
    """Builds save_verify from src/save_engine.c once. None if no compiler."""

    global _VERIFY_TOOL, _VERIFY_TRIED
    if _VERIFY_TRIED:
        return _VERIFY_TOOL
    _VERIFY_TRIED = True
    if os.name == "nt" and shutil.which("wsl") is None:
        return None
    output = REPO / "build" / "save_sim" / "save_verify"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(host_command([
            "cc", "-O1", "-std=gnu11", "-DSAVE_ENGINE_HOST", "-iquote", "include",
            "-o", host_path(output), "BPETools/save_sim/save_verify.c", "src/save_engine.c",
        ]), cwd=REPO, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        raise AssertionError("save_verify failed to build:\n" + result.stderr)
    _VERIFY_TOOL = host_path(output)
    return _VERIFY_TOOL


def load_with_game_engine(image: bytes) -> dict | None:
    tool = verify_tool()
    if tool is None:
        return None
    with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
        image_path = pathlib.Path(directory) / "image.sav"
        out_path = pathlib.Path(directory) / "loaded.bin"
        image_path.write_bytes(image)
        result = subprocess.run(host_command([tool, host_path(image_path), host_path(out_path)]),
                                cwd=REPO, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        data = out_path.read_bytes()
    status, flags, game_id, counter = struct.unpack_from("<BIII", data, 0)
    offset = 13
    fields = {}
    for name, size in (("sb2", fmt.SAVEBLOCK2_SIZE), ("header", fmt.storage_header_size(41)),
                       ("sb3", fmt.SAVEBLOCK3_SIZE), ("sb1", fmt.SAVEBLOCK1_SIZE),
                       ("boxes", 41 * 30 * fmt.BOX_MON_SIZE)):
        fields[name] = data[offset:offset + size]
        offset += size
    return {"status": status, "flags": flags, "game_id": game_id, "counter": counter, **fields}


def random_legacy_mon(rng: random.Random, species: int | None = None) -> bytes:
    mon = fmt.BoxMon(personality=rng.getrandbits(32), otId=rng.getrandbits(32),
                     nickname=bytes(rng.randrange(0xFF) for _ in range(10)),
                     otName=bytes(rng.randrange(0xFF) for _ in range(7)))
    for kind, fields in [(None, fmt.HEADER_FIELDS)] + list(enumerate(fmt.SUBSTRUCT_FIELDS)):
        for name, (_, _, _, width) in fields.items():
            key = "s3.isEgg" if kind == 3 and name == "isEgg" else name
            mon.fields[key] = rng.getrandbits(width)
    mon.fields["species"] = species if species is not None else rng.randrange(1, 1500)
    mon.fields["isBadEgg"] = 0
    mon.fields["hasSpecies"] = 1
    mon.fields["heldItem"] = rng.randrange(0, 1000)
    mon.fields["abilityNum"] = rng.randrange(3)
    for move in range(1, 5):
        mon.fields[f"move{move}"] = rng.randrange(0, 900)
    mon.fields["pokeball"] = rng.randrange(0, 20)
    mon.fields["teraType"] = rng.randrange(0, 19)
    return fmt.encode_box_mon(mon)


def random_legacy_storage(rng: random.Random, fill: float) -> bytes:
    storage = bytearray(fmt.LEGACY_STORAGE_SIZE)
    storage[0] = rng.randrange(14)
    for index in range(14 * 30):
        if rng.random() < fill:
            offset = fmt.LEGACY_STORAGE_BOXES_OFFSET + index * 80
            storage[offset:offset + 80] = random_legacy_mon(rng)
    for box in range(14):
        name = fmt.default_box_name(box) if rng.random() < 0.5 else bytes(rng.randrange(0xFF) for _ in range(9))
        offset = fmt.LEGACY_STORAGE_NAMES_OFFSET + box * 9
        storage[offset:offset + 9] = name
        storage[fmt.LEGACY_STORAGE_WALLPAPERS_OFFSET + box] = rng.randrange(16)
    fusions = bytes(rng.getrandbits(8) for _ in range(400))
    storage[fmt.LEGACY_STORAGE_FUSIONS_OFFSET:fmt.LEGACY_STORAGE_FUSIONS_OFFSET + 400] = fusions
    return bytes(storage)


class PackedVectorTests(unittest.TestCase):
    def test_python_packs_exactly_like_the_game(self):
        vectors = json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]
        self.assertGreaterEqual(len(vectors), 40)
        kinds = set()
        for vector in vectors:
            record = bytes.fromhex(vector["boxPokemon"])
            packed, kind = fmt.pack_box_mon(record)
            kinds.add(kind)
            self.assertEqual(packed.hex().upper(), vector["packed"], kind)
        self.assertEqual(kinds, {"empty", "ok", "bad_egg"})

    def test_decode_encode_round_trip_matches_game_records(self):
        vectors = json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]
        for vector in vectors:
            record = bytes.fromhex(vector["boxPokemon"])
            mon = fmt.decode_box_mon(record)
            if not mon.checksum_valid:
                continue
            self.assertEqual(fmt.encode_box_mon(mon), record)

    def test_packed_fields_cover_480_bits_without_overlap(self):
        used = 0
        total = 0
        for _, start, width in fmt.PACKED_FIELDS:
            mask = ((1 << width) - 1) << start
            self.assertEqual(used & mask, 0)
            used |= mask
            total += width
        self.assertEqual(total, 480)
        self.assertEqual(used, (1 << 480) - 1)

    def test_packed_layout_matches_the_c_header(self):
        header = (REPO / "include" / "packed_box_mon.h").read_text(encoding="utf-8")
        self.assertIn("#define PB_SPECIES                 235, 11", header)
        self.assertIn("#define PB_HELD_ITEM               251, 10", header)
        self.assertIn("#define PB_MODERN_FATEFUL_ENCOUNTER 479, 1", header)
        self.assertEqual(fmt.PACKED_FIELD_MAP["species"], (235, 11))
        self.assertEqual(fmt.PACKED_FIELD_MAP["heldItem"], (251, 10))


class V21FormatTests(unittest.TestCase):
    def make_save(self, rng: random.Random) -> fmt.V21Save:
        boxes = bytearray(41 * 30 * 60)
        for index in range(len(boxes) // 60):
            if rng.random() < 0.3:
                boxes[index * 60:(index + 1) * 60] = bytes(rng.getrandbits(8) for _ in range(60))
        return fmt.V21Save(
            game_id=rng.getrandbits(32) | 1,
            save_block_2=bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK2_SIZE)),
            storage_header=bytes(rng.getrandbits(8) for _ in range(fmt.storage_header_size(41))),
            save_block_3=bytes(rng.getrandbits(8) for _ in range(4)),
            save_block_1=bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK1_SIZE)),
            boxes=bytes(boxes),
            hall_of_fame=(bytes(4096), b"\x01" * 4096),
        )

    def test_crc_is_standard(self):
        self.assertEqual(fmt.zlib.crc32(b"123456789"), 0xCBF43926)

    def test_build_and_load_round_trip(self):
        rng = random.Random(7)
        save = self.make_save(rng)
        image = fmt.build_v21_image(save)
        loaded = fmt.load_v21_image(image)
        for name in ("game_id", "save_block_2", "storage_header", "save_block_3", "save_block_1", "boxes"):
            self.assertEqual(getattr(loaded, name), getattr(save, name), name)
        self.assertEqual(loaded.load_flags, set())
        self.assertEqual(fmt.detect_format(image), "2.1")

    def test_the_game_engine_loads_python_images(self):
        rng = random.Random(11)
        save = self.make_save(rng)
        image = fmt.build_v21_image(save)
        result = load_with_game_engine(image)
        if result is None:
            self.skipTest("no host C compiler")
        self.assertEqual(result["status"], 1)  # SAVE_ENGINE_LOAD_OK
        self.assertEqual(result["flags"], 0)
        self.assertEqual(result["game_id"], save.game_id)
        self.assertEqual(result["sb2"], save.save_block_2)
        self.assertEqual(result["header"], save.storage_header)
        self.assertEqual(result["sb3"], save.save_block_3)
        self.assertEqual(result["sb1"], save.save_block_1)
        self.assertEqual(result["boxes"], save.boxes)

    def test_one_damaged_copy_still_loads(self):
        rng = random.Random(3)
        save = self.make_save(rng)
        image = bytearray(fmt.build_v21_image(save))
        image[fmt.SECTOR_PROGRESS_B * 4096 + 100] ^= 0x40
        loaded = fmt.load_v21_image(bytes(image))
        self.assertEqual(loaded.save_block_2, save.save_block_2)
        result = load_with_game_engine(bytes(image))
        if result is not None:
            self.assertEqual(result["status"], 2)  # SAVE_ENGINE_LOAD_OK_BACKUP
            self.assertEqual(result["sb2"], save.save_block_2)


class LegacyTests(unittest.TestCase):
    def make_legacy(self, rng: random.Random, fill: float = 0.4, **kwargs):
        sb2 = bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK2_SIZE))
        sb1 = bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK1_SIZE))
        sb3 = bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK3_SIZE))
        storage = random_legacy_storage(rng, fill)
        hof = (bytes(rng.getrandbits(8) for _ in range(4096)), bytes(rng.getrandbits(8) for _ in range(4096)))
        image = fmt.build_legacy_image(sb2, sb1, sb3, storage, hall_of_fame=hof, **kwargs)
        return image, (sb2, sb1, sb3, storage, hof)

    def test_reads_back_what_the_legacy_writer_wrote(self):
        rng = random.Random(21)
        for rotation in (0, 5, 13):
            image, (sb2, sb1, sb3, storage, _) = self.make_legacy(rng, rotation=rotation, counter=8 + rotation)
            legacy = fmt.load_legacy_image(image)
            self.assertEqual(legacy.save_block_2, sb2)
            self.assertEqual(legacy.save_block_1, sb1)
            self.assertEqual(legacy.save_block_3, sb3)
            self.assertEqual(legacy.storage, storage)
            self.assertEqual(fmt.detect_format(image), "2.0")

    def test_newest_complete_slot_wins_and_damaged_slot_is_ignored(self):
        rng = random.Random(5)
        old, old_blocks = self.make_legacy(rng, counter=10)
        new, new_blocks = self.make_legacy(rng, counter=11)
        combined = bytearray(old)
        combined[14 * 4096:28 * 4096] = new[14 * 4096:28 * 4096]
        self.assertEqual(fmt.load_legacy_image(bytes(combined)).save_block_2, new_blocks[0])
        combined[(14 + 6) * 4096 + 500] ^= 1  # damage the newer slot
        self.assertEqual(fmt.load_legacy_image(bytes(combined)).save_block_2, old_blocks[0])

    def test_conversion_keeps_every_pc_pokemon(self):
        rng = random.Random(99)
        for fill in (0.0, 0.35, 1.0):
            image, (sb2, sb1, sb3, storage, hof) = self.make_legacy(rng, fill=fill)
            legacy = fmt.load_legacy_image(image)
            save, report = fmt.convert_legacy_to_v21(legacy, game_id=0x1234567)
            converted = fmt.build_v21_image(save)
            loaded = fmt.load_v21_image(converted)
            self.assertEqual(loaded.save_block_1, sb1)
            self.assertEqual(loaded.save_block_2, sb2)
            self.assertEqual(loaded.save_block_3, sb3)
            self.assertEqual(loaded.hall_of_fame, hof)
            count = 0
            for index in range(14 * 30):
                record = storage[4 + index * 80:4 + (index + 1) * 80]
                expected, kind = fmt.pack_box_mon(record)
                self.assertEqual(loaded.boxes[index * 60:(index + 1) * 60], expected if kind == "ok" else bytes(60))
                count += kind == "ok"
            self.assertEqual(report.pc_pokemon, count)
            self.assertFalse(any(loaded.boxes[14 * 30 * 60:]))
            # Box names and wallpapers
            header = loaded.storage_header
            self.assertEqual(header[0], storage[0])
            for box in range(41):
                name = header[1 + box * 9:1 + (box + 1) * 9]
                wallpaper = header[1 + 41 * 9 + box]
                if box < 14:
                    self.assertEqual(name, storage[fmt.LEGACY_STORAGE_NAMES_OFFSET + box * 9:][:9])
                    self.assertEqual(wallpaper, storage[fmt.LEGACY_STORAGE_WALLPAPERS_OFFSET + box])
                else:
                    self.assertEqual(name, fmt.default_box_name(box))
                    self.assertEqual(wallpaper, box % 4)
            self.assertEqual(header[412:812], storage[fmt.LEGACY_STORAGE_FUSIONS_OFFSET:][:400])

            result = load_with_game_engine(converted)
            if result is not None:
                self.assertEqual(result["status"], 1)
                self.assertEqual(result["boxes"], loaded.boxes)
                self.assertEqual(result["sb1"], sb1)
                self.assertEqual(result["header"], header)

    def test_bad_eggs_are_dropped_and_counted(self):
        rng = random.Random(4)
        image, (sb2, sb1, sb3, storage, hof) = self.make_legacy(rng, fill=1.0)
        storage = bytearray(storage)
        storage[4 + 80 * 7 + 40] ^= 0xFF  # corrupt one record's secure data
        image = fmt.build_legacy_image(sb2, sb1, sb3, bytes(storage))
        save, report = fmt.convert_legacy_to_v21(fmt.load_legacy_image(image), game_id=5)
        self.assertEqual(report.dropped_bad_eggs, 1)
        self.assertEqual(report.pc_pokemon, 14 * 30 - 1)
        self.assertEqual(save.boxes[7 * 60:8 * 60], bytes(60))

    def test_real_pre21_saves_convert(self):
        found = [path for path in REAL_PRE21_SAVES if path.exists()]
        if not found:
            self.skipTest("no local pre-2.1 saves")
        converted_any = False
        for path in found:
            with self.subTest(save=path.name):
                offset, image = fmt.find_flash_image(path.read_bytes())
                if fmt.detect_format(image) == "empty":
                    continue  # A blank flash file
                self.assertEqual(fmt.detect_format(image), "2.0")
                legacy = fmt.load_legacy_image(image)
                save, report = fmt.convert_legacy_to_v21(legacy, game_id=0xBEEF)
                converted = fmt.build_v21_image(save)
                loaded = fmt.load_v21_image(converted)
                self.assertEqual(loaded.save_block_1, legacy.save_block_1)
                self.assertEqual(loaded.save_block_2, legacy.save_block_2)
                self.assertEqual(loaded.save_block_3, legacy.save_block_3)
                self.assertEqual(loaded.hall_of_fame, legacy.hall_of_fame)
                converted_any = True
                # Every PC Pokémon keeps its identity and species
                for index in range(14 * 30):
                    record = legacy.storage[4 + index * 80:4 + (index + 1) * 80]
                    mon = fmt.decode_box_mon(record)
                    packed = loaded.boxes[index * 60:(index + 1) * 60]
                    if mon.checksum_valid and mon.get("species"):
                        self.assertEqual(fmt.get_packed(packed, "personality"), mon.personality)
                        self.assertEqual(fmt.get_packed(packed, "otId"), mon.otId)
                        self.assertEqual(fmt.get_packed(packed, "species"), mon.get("species"))
                        self.assertEqual(fmt.get_packed(packed, "experience"), mon.get("experience"))
                result = load_with_game_engine(converted)
                if result is not None:
                    self.assertEqual(result["status"], 1)
                    self.assertEqual(result["boxes"], loaded.boxes)
                    self.assertEqual(result["sb1"], legacy.save_block_1)
        self.assertTrue(converted_any, "no local save could be converted")


if __name__ == "__main__":
    unittest.main()


def run_js_converter(file_bytes: bytes, game_id: int) -> tuple[dict, bytes | None]:
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as directory:
        source = pathlib.Path(directory) / "in.sav"
        target = pathlib.Path(directory) / "out.sav"
        source.write_bytes(file_bytes)
        result = subprocess.run([node, str(REPO / "BPETools" / "tests" / "save_converter_cli.cjs"),
                                 str(source), str(target), str(game_id)],
                                cwd=REPO, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        report = json.loads(result.stdout)
        return report, (target.read_bytes() if target.exists() else None)


class WebsiteConverterTests(unittest.TestCase):
    def python_conversion(self, file_bytes: bytes, game_id: int) -> bytes:
        offset, image = fmt.find_flash_image(file_bytes)
        save, _ = fmt.convert_legacy_to_v21(fmt.load_legacy_image(image), game_id=game_id)
        converted = bytearray(file_bytes)
        converted[offset:offset + fmt.FLASH_SIZE] = fmt.build_v21_image(save, counter=1)
        return bytes(converted)

    def test_matches_python_byte_for_byte(self):
        rng = random.Random(1234)
        for fill in (0.0, 0.5, 1.0):
            sb2 = bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK2_SIZE))
            sb1 = bytes(rng.getrandbits(8) for _ in range(fmt.SAVEBLOCK1_SIZE))
            sb3 = bytes(rng.getrandbits(8) for _ in range(4))
            storage = bytearray(random_legacy_storage(rng, fill))
            if fill:
                storage[4 + 80 * 3 + 50] ^= 0x10  # a Bad Egg
            hof = (bytes(rng.getrandbits(8) for _ in range(4096)), bytes(rng.getrandbits(8) for _ in range(4096)))
            image = fmt.build_legacy_image(sb2, sb1, sb3, bytes(storage), hall_of_fame=hof,
                                           counter=rng.randrange(1, 1000), rotation=rng.randrange(14))
            # Emulator trailer bytes after the flash image must survive
            file_bytes = image + b"RTC!" + bytes(12)
            report, output = run_js_converter(file_bytes, 0xC0FFEE)
            self.assertNotIn("error", report)
            self.assertEqual(output, self.python_conversion(file_bytes, 0xC0FFEE))
            result = load_with_game_engine(output[:fmt.FLASH_SIZE])
            if result is not None:
                self.assertEqual(result["status"], 1)
                self.assertEqual(result["sb1"], sb1)

    def test_rejects_saves_it_must_not_convert(self):
        report, output = run_js_converter(b"\xFF" * fmt.FLASH_SIZE, 1)
        self.assertIn("does not contain", report["error"])
        self.assertIsNone(output)
        rng = random.Random(8)
        save = fmt.V21Save(game_id=9, save_block_2=bytes(fmt.SAVEBLOCK2_SIZE),
                           storage_header=bytes(fmt.storage_header_size(41)), save_block_3=bytes(4),
                           save_block_1=bytes(fmt.SAVEBLOCK1_SIZE), boxes=bytes(41 * 30 * 60),
                           hall_of_fame=(bytes(4096), bytes(4096)))
        report, _ = run_js_converter(fmt.build_v21_image(save), 1)
        self.assertIn("already", report["error"])
        damaged = bytearray(fmt.build_legacy_image(bytes(fmt.SAVEBLOCK2_SIZE), bytes(fmt.SAVEBLOCK1_SIZE),
                                                   bytes(4), random_legacy_storage(rng, 0.2)))
        damaged[(14 + 3) * 4096 + 10] ^= 1  # counter 5 writes slot 1
        report, _ = run_js_converter(bytes(damaged), 1)
        self.assertIn("no complete save slot", report["error"])
        report, _ = run_js_converter(b"\x00" * 1000, 1)
        self.assertIn("too small", report["error"])

    def test_real_pre21_saves_match_python(self):
        found = [path for path in REAL_PRE21_SAVES if path.exists()]
        if not found:
            self.skipTest("no local pre-2.1 saves")
        for path in found:
            file_bytes = path.read_bytes()
            if fmt.detect_format(fmt.find_flash_image(file_bytes)[1]) != "2.0":
                continue
            with self.subTest(save=path.name):
                report, output = run_js_converter(file_bytes, 77)
                self.assertNotIn("error", report)
                self.assertEqual(output, self.python_conversion(file_bytes, 77))
