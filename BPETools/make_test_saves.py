"""Makes 2.1 test saves for checking a build in an emulator.

    python BPETools/make_test_saves.py <2.0.x save> [--out-dir .]

Writes, next to each other (all are ignored by Git):
  <prefix>_converted.sav   the save converted to 2.1, like the website does
  <prefix>_full_pc.sav     the same game with all 41 boxes completely full
  <prefix>_outdated.sav    an unchanged copy of the 2.0.x save (the game must
                           refuse to save over it and point to the converter)

Rename a file to match the ROM's name (for example
BlackPearlEmerald_v2.1.0-savetest.sav) before loading it in the emulator.
PC Pokémon added to the full save cycle through National Pokédex numbers 1–1025
and use field values from the game's own packed-record test vectors.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "BPETools"))

import bpe_save_format as fmt  # noqa: E402

VECTORS = REPO / "BPETools" / "tests" / "fixtures" / "packed_box_mon_vectors.json"


def valid_pc_records() -> list[bytes]:
    records = []
    for vector in json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]:
        packed, kind = fmt.pack_box_mon(bytes.fromhex(vector["boxPokemon"]))
        if kind == "ok" and not fmt.get_packed(packed, "isEgg"):
            records.append(packed)
    return records


def set_packed(data: bytearray, name: str, value: int) -> None:
    start, width = fmt.PACKED_FIELD_MAP[name]
    number = int.from_bytes(data, "little")
    mask = ((1 << width) - 1) << start
    number = (number & ~mask) | ((value << start) & mask)
    data[:] = number.to_bytes(fmt.BOX_MON_SIZE, "little")


# Game text: "TEST" and "BPE"
NICKNAME = [0xCE, 0xBF, 0xCD, 0xCE] + [0xFF] * 8
OT_NAME = [0xBC, 0xCA, 0xBF] + [0xFF] * 4


def make_playable(record: bytes, personality: int, species: int) -> bytes:
    """The vectors hold random field values (random text bytes, held mail,
    Nuzlocke deaths); keep the species, moves, stats and form data but make
    the rest ordinary so the save is pleasant to play with."""

    data = bytearray(record)
    set_packed(data, "personality", personality)
    set_packed(data, "species", species)  # A National Pokédex number: never a battle-only form
    for i, char in enumerate(NICKNAME):
        set_packed(data, f"nickname{i}", char)
    for i, char in enumerate(OT_NAME):
        set_packed(data, f"otName{i}", char)
    set_packed(data, "language", 2)
    set_packed(data, "dead", 0)
    set_packed(data, "pokerus", 0)
    set_packed(data, "heldItem", 0)
    set_packed(data, "isShadow", 0)
    set_packed(data, "hiddenNatureModifier", 0)
    set_packed(data, "teraType", 0)
    set_packed(data, "metLocation", 0)  # MAPSEC_LITTLEROOT_TOWN
    set_packed(data, "metGame", 3)      # VERSION_EMERALD
    set_packed(data, "metLevel", 5)
    set_packed(data, "experience", min(fmt.get_packed(bytes(data), "experience"), 50000))
    return bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("save", type=pathlib.Path)
    parser.add_argument("--out-dir", type=pathlib.Path, default=REPO)
    parser.add_argument("--prefix", default="BlackPearlEmerald_v2.1.0-savetest")
    args = parser.parse_args()

    file_bytes = args.save.read_bytes()
    offset, image = fmt.find_flash_image(file_bytes)
    if fmt.detect_format(image) != "2.0":
        raise SystemExit("expected a 2.0.x save")
    legacy = fmt.load_legacy_image(image)
    rng = random.Random(2101)
    game_id = rng.getrandbits(32) | 1

    def write(name: str, save: fmt.V21Save) -> None:
        output = bytearray(file_bytes)
        output[offset:offset + fmt.FLASH_SIZE] = fmt.build_v21_image(save)
        loaded = fmt.load_v21_image(bytes(output[offset:offset + fmt.FLASH_SIZE]))
        assert loaded.boxes == save.boxes and loaded.save_block_1 == save.save_block_1
        path = args.out_dir / f"{args.prefix}_{name}.sav"
        path.write_bytes(output)
        print(f"wrote {path}")

    converted, report = fmt.convert_legacy_to_v21(legacy, game_id)
    print(f"converted: {report.pc_pokemon} PC Pokémon, {report.dropped_bad_eggs} Bad Eggs removed")
    write("converted", converted)

    records = valid_pc_records()
    boxes = bytearray(converted.boxes)
    filled = 0
    for index in range(fmt.TOTAL_BOXES_V21 * fmt.IN_BOX_COUNT):
        start = index * fmt.BOX_MON_SIZE
        if fmt.is_packed_empty(boxes[start:start + fmt.BOX_MON_SIZE]):
            record = make_playable(records[index % len(records)], rng.getrandbits(32), 1 + index % 1025)
            boxes[start:start + fmt.BOX_MON_SIZE] = record
            filled += 1
    full = fmt.V21Save(**{**converted.__dict__, "boxes": bytes(boxes)})
    print(f"full PC: added {filled} Pokémon")
    write("full_pc", full)

    outdated = args.out_dir / f"{args.prefix}_outdated.sav"
    outdated.write_bytes(file_bytes)
    print(f"wrote {outdated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
