"""Black Pearl Emerald save formats.

Reads the pre-2.1 flash layout used by 2.0.0-beta through 2.0.7-beta, and reads
and writes the 2.1 layout described in include/save_engine.h and
include/packed_box_mon.h. The website Save Converter
(BPEDocumentation/site/js/save-converter.js) implements the same rules, and
BPETools/tests/test_bpe_save_format.py checks both against byte vectors
produced by the game's own C code.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

SECTOR_SIZE = 4096
SECTOR_COUNT = 32
FLASH_SIZE = SECTOR_SIZE * SECTOR_COUNT

# ---------------------------------------------------------------------------
# 2.1 format (include/save_engine.h)

PAYLOAD_SIZE = 4080
CRC_OFFSET = 4080
KIND_OFFSET = 4084
ID_OFFSET = 4085
VERSION_OFFSET = 4086
SIGNATURE_OFFSET = 4088
COUNTER_OFFSET = 4092

SIGNATURE_V2 = 0x32455042
SIGNATURE_LEGACY = 0x08012025
FORMAT_VERSION = 1

KIND_PROGRESS = 1
KIND_BOX = 2

PROGRESS_PARTS = 5
SECTOR_PROGRESS_A = 0
SECTOR_PROGRESS_B = 5
SECTOR_BOX_FIRST = 10
BOX_SECTOR_COUNT = 19
SECTOR_BOX_BACKUP = 29
SECTOR_HOF_1 = 30
SECTOR_HOF_2 = 31

BOX_MON_SIZE = 60
BOX_MONS_PER_SECTOR = 66
BOX_GAME_ID_OFFSET = BOX_MON_SIZE * BOX_MONS_PER_SECTOR
META_SIZE = 4 + 4 * BOX_SECTOR_COUNT + 4

# Game structure sizes for 2.1 (checked by test/save.c)
TOTAL_BOXES_V21 = 41
IN_BOX_COUNT = 30
BOX_NAME_LENGTH = 8
MAX_FUSION_STORAGE = 4
POKEMON_SIZE = 100
SAVEBLOCK1_SIZE = 15836
SAVEBLOCK2_SIZE = 2852
SAVEBLOCK3_SIZE = 4


def storage_header_size(total_boxes: int) -> int:
    unaligned = 1 + total_boxes * (BOX_NAME_LENGTH + 1) + total_boxes
    return ((unaligned + 3) & ~3) + MAX_FUSION_STORAGE * POKEMON_SIZE


def sector_crc(sector: bytes) -> int:
    crc = zlib.crc32(sector[:CRC_OFFSET])
    return zlib.crc32(sector[KIND_OFFSET:SECTOR_SIZE], crc) & 0xFFFFFFFF


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def is_sector_valid(sector: bytes, kind: int, sector_id: int) -> bool:
    return (
        u32(sector, SIGNATURE_OFFSET) == SIGNATURE_V2
        and sector[KIND_OFFSET] == kind
        and sector[ID_OFFSET] == sector_id
        and u16(sector, VERSION_OFFSET) == FORMAT_VERSION
        and u32(sector, CRC_OFFSET) == sector_crc(sector)
    )


def finish_sector(payload: bytes, kind: int, sector_id: int, counter: int) -> bytes:
    if len(payload) > PAYLOAD_SIZE:
        raise ValueError("payload too large for a sector")
    sector = bytearray(SECTOR_SIZE)
    sector[: len(payload)] = payload
    sector[KIND_OFFSET] = kind
    sector[ID_OFFSET] = sector_id
    struct.pack_into("<H", sector, VERSION_OFFSET, FORMAT_VERSION)
    struct.pack_into("<I", sector, SIGNATURE_OFFSET, SIGNATURE_V2)
    struct.pack_into("<I", sector, COUNTER_OFFSET, counter)
    struct.pack_into("<I", sector, CRC_OFFSET, sector_crc(bytes(sector)))
    return bytes(sector)


@dataclass
class V21Save:
    """Everything the 2.1 format stores, as the game holds it in RAM."""

    game_id: int
    save_block_2: bytes
    storage_header: bytes
    save_block_3: bytes
    save_block_1: bytes
    boxes: bytes  # packed records, TOTAL_BOXES * 30 * 60 bytes
    hall_of_fame: tuple[bytes, bytes] | None = None
    counter: int = 0
    load_flags: set[str] = field(default_factory=set)


def build_v21_image(save: V21Save, counter: int = 1, both_copies: bool = True) -> bytes:
    """Builds a complete 2.1 flash image. The second progress copy, when
    written, is identical with the next counter so either copy can load."""

    image = bytearray(b"\xFF" * FLASH_SIZE)
    mon_count = len(save.boxes) // BOX_MON_SIZE
    if len(save.boxes) % BOX_MON_SIZE or mon_count > BOX_SECTOR_COUNT * BOX_MONS_PER_SECTOR:
        raise ValueError("bad box data size")

    box_counter = counter + (1 if both_copies else 0)
    crcs = []
    for index in range(BOX_SECTOR_COUNT):
        first = index * BOX_MONS_PER_SECTOR
        count = max(0, min(BOX_MONS_PER_SECTOR, mon_count - first))
        payload = bytearray(BOX_GAME_ID_OFFSET + 4)
        payload[: count * BOX_MON_SIZE] = save.boxes[first * BOX_MON_SIZE:(first + count) * BOX_MON_SIZE]
        struct.pack_into("<I", payload, BOX_GAME_ID_OFFSET, save.game_id)
        sector = finish_sector(bytes(payload), KIND_BOX, index, box_counter)
        crcs.append(u32(sector, CRC_OFFSET))
        start = (SECTOR_BOX_FIRST + index) * SECTOR_SIZE
        image[start:start + SECTOR_SIZE] = sector

    part0 = bytearray(struct.pack("<I", save.game_id))
    for crc in crcs:
        part0 += struct.pack("<I", crc)
    part0 += struct.pack("<I", 0)
    part0 += save.save_block_2 + save.storage_header + save.save_block_3
    if len(part0) > PAYLOAD_SIZE:
        raise ValueError("progress part 0 is too large")
    if len(save.save_block_1) > PAYLOAD_SIZE * (PROGRESS_PARTS - 1):
        raise ValueError("SaveBlock1 is too large")
    parts = [bytes(part0)] + [
        save.save_block_1[(i - 1) * PAYLOAD_SIZE:i * PAYLOAD_SIZE] for i in range(1, PROGRESS_PARTS)
    ]

    copies = [(SECTOR_PROGRESS_A, counter)]
    if both_copies:
        copies.append((SECTOR_PROGRESS_B, counter + 1))
    for first_sector, copy_counter in copies:
        for part, payload in enumerate(parts):
            start = (first_sector + part) * SECTOR_SIZE
            image[start:start + SECTOR_SIZE] = finish_sector(payload, KIND_PROGRESS, part, copy_counter)

    if save.hall_of_fame is not None:
        for sector_number, data in zip((SECTOR_HOF_1, SECTOR_HOF_2), save.hall_of_fame):
            image[sector_number * SECTOR_SIZE:(sector_number + 1) * SECTOR_SIZE] = data
    return bytes(image)


def load_v21_image(image: bytes, total_boxes: int = TOTAL_BOXES_V21) -> V21Save:
    """Loads a 2.1 flash image with the same rules as SaveEngine_Load."""

    def sector(number: int) -> bytes:
        return image[number * SECTOR_SIZE:(number + 1) * SECTOR_SIZE]

    copies = []
    for copy, first in enumerate((SECTOR_PROGRESS_A, SECTOR_PROGRESS_B)):
        parts = [sector(first + part) for part in range(PROGRESS_PARTS)]
        if all(is_sector_valid(p, KIND_PROGRESS, i) for i, p in enumerate(parts)) and len(
            {u32(p, COUNTER_OFFSET) for p in parts}
        ) == 1:
            copies.append((u32(parts[0], COUNTER_OFFSET), copy, parts))
    if not copies:
        raise ValueError("no valid 2.1 progress copy")
    # Like FindNewestCopy: the higher counter wins, copy A on a tie
    counter, _, parts = max(copies, key=lambda entry: (entry[0], -entry[1]))

    header_size = storage_header_size(total_boxes)
    part0 = parts[0]
    game_id = u32(part0, 0)
    committed = [u32(part0, 4 + 4 * i) for i in range(BOX_SECTOR_COUNT)]
    offset = META_SIZE
    sb2 = part0[offset:offset + SAVEBLOCK2_SIZE]
    offset += SAVEBLOCK2_SIZE
    header = part0[offset:offset + header_size]
    offset += header_size
    sb3 = part0[offset:offset + SAVEBLOCK3_SIZE]
    sb1 = b"".join(p[:PAYLOAD_SIZE] for p in parts[1:])[:SAVEBLOCK1_SIZE]

    backup = sector(SECTOR_BOX_BACKUP)
    backup_id = backup[ID_OFFSET]
    backup_valid = backup_id < BOX_SECTOR_COUNT and is_sector_valid(backup, KIND_BOX, backup_id)
    backup_valid = backup_valid and u32(backup, BOX_GAME_ID_OFFSET) == game_id
    backup_crc = u32(backup, CRC_OFFSET)

    mon_count = total_boxes * IN_BOX_COUNT
    boxes = bytearray(mon_count * BOX_MON_SIZE)
    flags: set[str] = set()
    for index in range(BOX_SECTOR_COUNT):
        first = index * BOX_MONS_PER_SECTOR
        count = max(0, min(BOX_MONS_PER_SECTOR, mon_count - first))
        data = sector(SECTOR_BOX_FIRST + index)
        valid = is_sector_valid(data, KIND_BOX, index)
        same_game = u32(data, BOX_GAME_ID_OFFSET) == game_id
        crc = u32(data, CRC_OFFSET)
        source = None
        if valid and same_game and crc == committed[index]:
            source = data
        elif backup_valid and backup_id == index and backup_crc == committed[index]:
            source = backup
            flags.add("box_restored")
        elif valid and same_game:
            source = data
            flags.add("box_uncommitted")
        elif backup_valid and backup_id == index:
            source = backup
            flags.add("box_restored")
        elif not valid:
            flags.add("box_lost")
        if source is not None:
            boxes[first * BOX_MON_SIZE:(first + count) * BOX_MON_SIZE] = source[: count * BOX_MON_SIZE]

    return V21Save(
        game_id=game_id,
        save_block_2=sb2,
        storage_header=header,
        save_block_3=sb3,
        save_block_1=sb1,
        boxes=bytes(boxes),
        hall_of_fame=(sector(SECTOR_HOF_1), sector(SECTOR_HOF_2)),
        counter=counter,
        load_flags=flags,
    )


# ---------------------------------------------------------------------------
# 80-byte struct BoxPokemon (unchanged from 2.0.0-beta through 2.1)

SUBSTRUCT_ORDER = [
    # For each personality % 24, the positions of substructs 0, 1, 2 and 3
    # (sSubstructOffsets in src/pokemon.c).
]
_OFFSETS = [
    [0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 2, 3, 1, 1, 2, 3, 2, 3, 1, 1, 2, 3, 2, 3],
    [1, 1, 2, 3, 2, 3, 0, 0, 0, 0, 0, 0, 2, 3, 1, 1, 3, 2, 2, 3, 1, 1, 3, 2],
    [2, 3, 1, 1, 3, 2, 2, 3, 1, 1, 3, 2, 0, 0, 0, 0, 0, 0, 3, 2, 3, 2, 1, 1],
    [3, 2, 3, 2, 1, 1, 3, 2, 3, 2, 1, 1, 3, 2, 3, 2, 1, 1, 0, 0, 0, 0, 0, 0],
]
SUBSTRUCT_ORDER = [[_OFFSETS[kind][mod] for kind in range(4)] for mod in range(24)]


def _bits(value: int, start: int, width: int) -> int:
    return (value >> start) & ((1 << width) - 1)


def _put(value: int, start: int, width: int, field_value: int) -> int:
    mask = ((1 << width) - 1) << start
    return (value & ~mask) | ((field_value << start) & mask)


# Bit fields as (container byte offset in the 80-byte record or substruct,
# container size in bytes, bit start within the container, width).
HEADER_FIELDS = {
    "language": (18, 1, 0, 3),
    "hiddenNatureModifier": (18, 1, 3, 5),
    "isBadEgg": (19, 1, 0, 1),
    "hasSpecies": (19, 1, 1, 1),
    "isEgg": (19, 1, 2, 1),
    "blockBoxRS": (19, 1, 3, 1),
    "dead": (19, 1, 4, 1),
    "daysSinceFormChange": (19, 1, 5, 3),
    "markings": (27, 1, 0, 4),
    "compressedStatus": (27, 1, 4, 4),
    "hpLost": (30, 2, 0, 14),
    "shinyModifier": (30, 2, 14, 1),
}

SUBSTRUCT_FIELDS = [
    {  # PokemonSubstruct0
        "species": (0, 2, 0, 11), "teraType": (0, 2, 11, 5),
        "heldItem": (2, 2, 0, 10),
        "experience": (4, 4, 0, 21), "nickname11": (4, 4, 21, 8),
        "ppBonuses": (8, 1, 0, 8), "friendship": (9, 1, 0, 8),
        "pokeball": (10, 2, 0, 6), "nickname12": (10, 2, 6, 8),
    },
    {  # PokemonSubstruct1
        "move1": (0, 2, 0, 11), "evolutionTracker1": (0, 2, 11, 5),
        "move2": (2, 2, 0, 11), "evolutionTracker2": (2, 2, 11, 5),
        "move3": (4, 2, 0, 11),
        "move4": (6, 2, 0, 11), "hyperTrainedHP": (6, 2, 14, 1), "hyperTrainedAttack": (6, 2, 15, 1),
        "pp1": (8, 1, 0, 7), "hyperTrainedDefense": (8, 1, 7, 1),
        "pp2": (9, 1, 0, 7), "hyperTrainedSpeed": (9, 1, 7, 1),
        "pp3": (10, 1, 0, 7), "hyperTrainedSpAttack": (10, 1, 7, 1),
        "pp4": (11, 1, 0, 7), "hyperTrainedSpDefense": (11, 1, 7, 1),
    },
    {  # PokemonSubstruct2
        "hpEV": (0, 1, 0, 8), "attackEV": (1, 1, 0, 8), "defenseEV": (2, 1, 0, 8),
        "speedEV": (3, 1, 0, 8), "spAttackEV": (4, 1, 0, 8), "spDefenseEV": (5, 1, 0, 8),
        "cool": (6, 1, 0, 8), "beauty": (7, 1, 0, 8), "cute": (8, 1, 0, 8),
        "smart": (9, 1, 0, 8), "tough": (10, 1, 0, 8), "sheen": (11, 1, 0, 8),
    },
    {  # PokemonSubstruct3
        "pokerus": (0, 1, 0, 8), "metLocation": (1, 1, 0, 8),
        "metLevel": (2, 2, 0, 7), "metGame": (2, 2, 7, 4), "dynamaxLevel": (2, 2, 11, 4), "otGender": (2, 2, 15, 1),
        "hpIV": (4, 4, 0, 5), "attackIV": (4, 4, 5, 5), "defenseIV": (4, 4, 10, 5),
        "speedIV": (4, 4, 15, 5), "spAttackIV": (4, 4, 20, 5), "spDefenseIV": (4, 4, 25, 5),
        "isEgg": (4, 4, 30, 1), "gigantamaxFactor": (4, 4, 31, 1),
        "coolRibbon": (8, 4, 0, 3), "beautyRibbon": (8, 4, 3, 3), "cuteRibbon": (8, 4, 6, 3),
        "smartRibbon": (8, 4, 9, 3), "toughRibbon": (8, 4, 12, 3), "championRibbon": (8, 4, 15, 1),
        "winningRibbon": (8, 4, 16, 1), "victoryRibbon": (8, 4, 17, 1), "artistRibbon": (8, 4, 18, 1),
        "effortRibbon": (8, 4, 19, 1), "marineRibbon": (8, 4, 20, 1), "landRibbon": (8, 4, 21, 1),
        "skyRibbon": (8, 4, 22, 1), "countryRibbon": (8, 4, 23, 1), "nationalRibbon": (8, 4, 24, 1),
        "earthRibbon": (8, 4, 25, 1), "worldRibbon": (8, 4, 26, 1), "isShadow": (8, 4, 27, 1),
        "abilityNum": (8, 4, 29, 2), "modernFatefulEncounter": (8, 4, 31, 1),
    },
]


def _read_field(data: bytes, base: int, spec: tuple[int, int, int, int]) -> int:
    offset, size, start, width = spec
    container = int.from_bytes(data[base + offset:base + offset + size], "little")
    return _bits(container, start, width)


def _write_field(data: bytearray, base: int, spec: tuple[int, int, int, int], value: int) -> None:
    offset, size, start, width = spec
    container = int.from_bytes(data[base + offset:base + offset + size], "little")
    container = _put(container, start, width, value)
    data[base + offset:base + offset + size] = container.to_bytes(size, "little")


def box_mon_checksum(decrypted: bytes) -> int:
    total = 0
    for offset in range(32, 80, 4):
        word = u32(decrypted, offset)
        total += word + (word >> 16)
    return total & 0xFFFF


def crypt_box_mon(record: bytes) -> bytes:
    """Encrypts or decrypts the secure part of an 80-byte record."""

    output = bytearray(record[:80])
    key = u32(record, 0) ^ u32(record, 4)
    for offset in range(32, 80, 4):
        struct.pack_into("<I", output, offset, u32(record, offset) ^ key)
    return bytes(output)


@dataclass
class BoxMon:
    """Decoded struct BoxPokemon (decrypted fields)."""

    personality: int = 0
    otId: int = 0
    nickname: bytes = b"\x00" * 10
    otName: bytes = b"\x00" * 7
    checksum: int = 0
    fields: dict[str, int] = field(default_factory=dict)
    checksum_valid: bool = True

    def get(self, name: str) -> int:
        return self.fields.get(name, 0)


def decode_box_mon(record: bytes) -> BoxMon:
    decrypted = crypt_box_mon(record)
    mon = BoxMon(
        personality=u32(decrypted, 0),
        otId=u32(decrypted, 4),
        nickname=decrypted[8:18],
        otName=decrypted[20:27],
        checksum=u16(decrypted, 28),
    )
    for name, spec in HEADER_FIELDS.items():
        mon.fields[name] = _read_field(decrypted, 0, spec)
    order = SUBSTRUCT_ORDER[mon.personality % 24]
    for kind in range(4):
        base = 32 + 12 * order[kind]
        for name, spec in SUBSTRUCT_FIELDS[kind].items():
            mon.fields[("s3." if kind == 3 and name == "isEgg" else "") + name] = _read_field(decrypted, base, spec)
    mon.checksum_valid = box_mon_checksum(decrypted) == mon.checksum
    return mon


def encode_box_mon(mon: BoxMon) -> bytes:
    """Builds an encrypted 80-byte record with a correct checksum."""

    data = bytearray(80)
    struct.pack_into("<II", data, 0, mon.personality, mon.otId)
    data[8:18] = mon.nickname
    data[20:27] = mon.otName
    for name, spec in HEADER_FIELDS.items():
        _write_field(data, 0, spec, mon.get(name))
    order = SUBSTRUCT_ORDER[mon.personality % 24]
    for kind in range(4):
        base = 32 + 12 * order[kind]
        for name, spec in SUBSTRUCT_FIELDS[kind].items():
            key = "s3." + name if kind == 3 and name == "isEgg" else name
            _write_field(data, base, spec, mon.get(key))
    struct.pack_into("<H", data, 28, box_mon_checksum(bytes(data)))
    return crypt_box_mon(bytes(data))


# ---------------------------------------------------------------------------
# 60-byte packed PC records (include/packed_box_mon.h)

PACKED_FIELDS: list[tuple[str, int, int]] = (
    [("personality", 0, 32), ("otId", 32, 32)]
    + [(f"nickname{i}", 64 + 8 * i, 8) for i in range(12)]
    + [(f"otName{i}", 160 + 8 * i, 8) for i in range(7)]
    + [
        ("language", 216, 3), ("hiddenNatureModifier", 219, 5), ("isBadEgg", 224, 1), ("isEgg", 225, 1),
        ("dead", 226, 1), ("daysSinceFormChange", 227, 3), ("markings", 230, 4), ("shinyModifier", 234, 1),
        ("species", 235, 11), ("teraType", 246, 5), ("heldItem", 251, 10), ("experience", 261, 21),
        ("ppBonuses", 282, 8), ("friendship", 290, 8), ("pokeball", 298, 6),
    ]
    + [(f"move{i + 1}", 304 + 11 * i, 11) for i in range(4)]
    + [("evolutionTracker1", 348, 5), ("evolutionTracker2", 353, 5)]
    + [(name, 358 + i, 1) for i, name in enumerate(
        ["hyperTrainedHP", "hyperTrainedAttack", "hyperTrainedDefense", "hyperTrainedSpeed",
         "hyperTrainedSpAttack", "hyperTrainedSpDefense"])]
    + [(name, 364 + 8 * i, 8) for i, name in enumerate(
        ["hpEV", "attackEV", "defenseEV", "speedEV", "spAttackEV", "spDefenseEV"])]
    + [("pokerus", 412, 8), ("metLocation", 420, 8), ("metLevel", 428, 7), ("metGame", 435, 4),
       ("dynamaxLevel", 439, 4), ("otGender", 443, 1)]
    + [(name, 444 + 5 * i, 5) for i, name in enumerate(
        ["hpIV", "attackIV", "defenseIV", "speedIV", "spAttackIV", "spDefenseIV"])]
    + [("gigantamaxFactor", 474, 1), ("championRibbon", 475, 1), ("isShadow", 476, 1),
       ("abilityNum", 477, 2), ("modernFatefulEncounter", 479, 1)]
)
PACKED_FIELD_MAP = {name: (start, width) for name, start, width in PACKED_FIELDS}


def get_packed(record: bytes, name: str) -> int:
    start, width = PACKED_FIELD_MAP[name]
    return _bits(int.from_bytes(record[:BOX_MON_SIZE], "little"), start, width)


def pack_box_mon(record80: bytes) -> tuple[bytes, str]:
    """Packs an encrypted 80-byte record exactly like PackBoxMon. Returns the
    60 bytes and one of "empty", "ok", "bad_egg"."""

    mon = decode_box_mon(record80)
    bad_egg = bool(mon.get("isBadEgg")) or not mon.checksum_valid
    if not bad_egg and mon.get("species") == 0:
        return bytes(BOX_MON_SIZE), "empty"

    values = dict(mon.fields)
    values["personality"] = mon.personality
    values["otId"] = mon.otId
    for i in range(10):
        values[f"nickname{i}"] = mon.nickname[i]
    values["nickname10"] = mon.get("nickname11")
    values["nickname11"] = mon.get("nickname12")
    for i in range(7):
        values[f"otName{i}"] = mon.otName[i]
    values["isBadEgg"] = int(bad_egg)
    values["isEgg"] = int(bool(mon.get("isEgg") or mon.get("s3.isEgg") or bad_egg))

    packed = 0
    for name, start, width in PACKED_FIELDS:
        packed = _put(packed, start, width, values.get(name, 0))
    return packed.to_bytes(BOX_MON_SIZE, "little"), ("bad_egg" if bad_egg else "ok")


def is_packed_empty(record: bytes) -> bool:
    return not any(record[:BOX_MON_SIZE])


# ---------------------------------------------------------------------------
# Pre-2.1 layout (2.0.0-beta to 2.0.7-beta)

LEGACY_SECTORS_PER_SLOT = 14
LEGACY_DATA_SIZE = 3968
LEGACY_SB3_CHUNK = 116
LEGACY_FOOTER = LEGACY_DATA_SIZE + LEGACY_SB3_CHUNK
LEGACY_TOTAL_BOXES = 14
LEGACY_STORAGE_SIZE = 34144
LEGACY_STORAGE_BOXES_OFFSET = 4
LEGACY_STORAGE_NAMES_OFFSET = 33604
LEGACY_STORAGE_WALLPAPERS_OFFSET = 33730
LEGACY_STORAGE_FUSIONS_OFFSET = 33744


def legacy_checksum(data: bytes, size: int) -> int:
    total = 0
    for offset in range(0, size - size % 4, 4):
        total += u32(data, offset)
    total &= 0xFFFFFFFF
    return ((total >> 16) + total) & 0xFFFF


def _legacy_section_sizes() -> dict[int, int]:
    sizes = {0: SAVEBLOCK2_SIZE}
    for section in range(1, 5):
        sizes[section] = max(0, min(SAVEBLOCK1_SIZE - (section - 1) * LEGACY_DATA_SIZE, LEGACY_DATA_SIZE))
    for section in range(5, 14):
        sizes[section] = max(0, min(LEGACY_STORAGE_SIZE - (section - 5) * LEGACY_DATA_SIZE, LEGACY_DATA_SIZE))
    return sizes


@dataclass
class LegacySave:
    save_block_2: bytes
    save_block_1: bytes
    save_block_3: bytes
    storage: bytes
    hall_of_fame: tuple[bytes, bytes]
    slot: int
    counter: int
    other_slot_valid: bool


def find_flash_image(file_data: bytes) -> tuple[int, bytes]:
    """Returns the offset and 128 KiB flash image inside a .sav/.srm file."""

    if len(file_data) < FLASH_SIZE:
        raise ValueError("file is smaller than 128 KiB; not a GBA flash save")
    best = (0, -1)
    for start in range(0, len(file_data) - FLASH_SIZE + 1, 4):
        score = 0
        for sector in range(SECTOR_COUNT):
            signature = u32(file_data, start + sector * SECTOR_SIZE + SIGNATURE_OFFSET)
            if signature in (SIGNATURE_LEGACY, SIGNATURE_V2):
                score += 1
        if score > best[1]:
            best = (start, score)
        if start >= 0x10000:
            break
    return best[0], file_data[best[0]:best[0] + FLASH_SIZE]


def detect_format(image: bytes) -> str:
    v2 = legacy = 0
    for sector in range(SECTOR_BOX_BACKUP):
        signature = u32(image, sector * SECTOR_SIZE + SIGNATURE_OFFSET)
        v2 += signature == SIGNATURE_V2
        legacy += signature == SIGNATURE_LEGACY
    if v2:
        return "2.1"
    if legacy:
        return "2.0"
    return "empty"


def load_legacy_image(image: bytes) -> LegacySave:
    sizes = _legacy_section_sizes()
    slots = []
    for slot in range(2):
        sections: dict[int, bytes] = {}
        counter = None
        any_signature = False
        for physical in range(LEGACY_SECTORS_PER_SLOT):
            raw = image[(slot * LEGACY_SECTORS_PER_SLOT + physical) * SECTOR_SIZE:][:SECTOR_SIZE]
            section_id, stored, signature, sector_counter = struct.unpack_from("<HHII", raw, LEGACY_FOOTER)
            if signature != SIGNATURE_LEGACY:
                continue
            any_signature = True
            if section_id >= LEGACY_SECTORS_PER_SLOT:
                continue
            if legacy_checksum(raw, sizes[section_id]) != stored:
                continue
            sections[section_id] = raw
            counter = sector_counter
        slots.append((sections, counter, any_signature))

    valid = [(counter, slot) for slot, (sections, counter, _) in enumerate(slots)
             if len(sections) == LEGACY_SECTORS_PER_SLOT
             and len({u32(s, LEGACY_FOOTER + 8) for s in sections.values()}) == 1]
    if not valid:
        raise ValueError("no complete save slot; the save is empty or corrupted")
    if len(valid) == 2:
        (c0, _), (c1, _) = valid
        # Same wrap-around rule as GetSaveValidStatus
        if (c0 == 0xFFFFFFFF and c1 == 0) or (c0 == 0 and c1 == 0xFFFFFFFF):
            chosen = 1 if (c0 + 1) & 0xFFFFFFFF < (c1 + 1) & 0xFFFFFFFF else 0
        else:
            chosen = 1 if c0 < c1 else 0
    else:
        chosen = valid[0][1]
    sections, counter, _ = slots[chosen]

    sb2 = sections[0][:SAVEBLOCK2_SIZE]
    sb1 = b"".join(sections[i][:sizes[i]] for i in range(1, 5))
    storage = b"".join(sections[i][:sizes[i]] for i in range(5, 14))
    sb3 = b"".join(sections[i][LEGACY_DATA_SIZE:LEGACY_FOOTER] for i in range(14))[:SAVEBLOCK3_SIZE]
    hof = (image[28 * SECTOR_SIZE:29 * SECTOR_SIZE], image[29 * SECTOR_SIZE:30 * SECTOR_SIZE])
    return LegacySave(
        save_block_2=sb2, save_block_1=sb1, save_block_3=sb3, storage=storage,
        hall_of_fame=hof, slot=chosen, counter=counter,
        other_slot_valid=len(valid) == 2,
    )


# ---------------------------------------------------------------------------
# Conversion

CHAR_TABLE = {**{str(d): 0xA1 + d for d in range(10)}, "B": 0xBC, "O": 0xC9, "X": 0xD2}
EOS = 0xFF
MAX_DEFAULT_WALLPAPER = 3  # WALLPAPER_SAVANNA


def default_box_name(box: int) -> bytes:
    text = [CHAR_TABLE[c] for c in f"BOX{box + 1}"] + [EOS]
    return bytes(text + [0] * (BOX_NAME_LENGTH + 1 - len(text)))


@dataclass
class ConversionReport:
    party_count: int = 0
    pc_pokemon: int = 0
    dropped_bad_eggs: int = 0
    source_slot: int = 0
    source_counter: int = 0


def convert_legacy_to_v21(legacy: LegacySave, game_id: int, total_boxes: int = TOTAL_BOXES_V21) -> tuple[V21Save, ConversionReport]:
    report = ConversionReport(source_slot=legacy.slot, source_counter=legacy.counter)
    storage = legacy.storage

    header = bytearray(storage_header_size(total_boxes))
    header[0] = storage[0]
    names_offset = 1
    wallpapers_offset = 1 + total_boxes * (BOX_NAME_LENGTH + 1)
    fusions_offset = storage_header_size(total_boxes) - MAX_FUSION_STORAGE * POKEMON_SIZE
    for box in range(total_boxes):
        name_start = names_offset + box * (BOX_NAME_LENGTH + 1)
        if box < LEGACY_TOTAL_BOXES:
            src = LEGACY_STORAGE_NAMES_OFFSET + box * (BOX_NAME_LENGTH + 1)
            header[name_start:name_start + BOX_NAME_LENGTH + 1] = storage[src:src + BOX_NAME_LENGTH + 1]
            header[wallpapers_offset + box] = storage[LEGACY_STORAGE_WALLPAPERS_OFFSET + box]
        else:
            header[name_start:name_start + BOX_NAME_LENGTH + 1] = default_box_name(box)
            header[wallpapers_offset + box] = box % (MAX_DEFAULT_WALLPAPER + 1)
    header[fusions_offset:fusions_offset + MAX_FUSION_STORAGE * POKEMON_SIZE] = storage[
        LEGACY_STORAGE_FUSIONS_OFFSET:LEGACY_STORAGE_FUSIONS_OFFSET + MAX_FUSION_STORAGE * POKEMON_SIZE]

    boxes = bytearray(total_boxes * IN_BOX_COUNT * BOX_MON_SIZE)
    for box in range(LEGACY_TOTAL_BOXES):
        for slot in range(IN_BOX_COUNT):
            src = LEGACY_STORAGE_BOXES_OFFSET + (box * IN_BOX_COUNT + slot) * 80
            packed, kind = pack_box_mon(storage[src:src + 80])
            if kind == "bad_egg":
                report.dropped_bad_eggs += 1
                continue
            if kind == "ok":
                report.pc_pokemon += 1
                dst = (box * IN_BOX_COUNT + slot) * BOX_MON_SIZE
                boxes[dst:dst + BOX_MON_SIZE] = packed

    save = V21Save(
        game_id=game_id,
        save_block_2=legacy.save_block_2,
        storage_header=bytes(header),
        save_block_3=legacy.save_block_3,
        save_block_1=legacy.save_block_1,
        boxes=bytes(boxes),
        hall_of_fame=legacy.hall_of_fame,
    )
    return save, report


def build_legacy_image(save_block_2: bytes, save_block_1: bytes, save_block_3: bytes, storage: bytes,
                       counter: int = 5, rotation: int = 3, slot: int | None = None,
                       hall_of_fame: tuple[bytes, bytes] | None = None) -> bytes:
    """Builds a 2.0.x flash image the way the 2.0.x game writes one (used by
    tests to make saves). The slot defaults to counter % 2, like the game."""

    sizes = _legacy_section_sizes()
    blocks = {0: save_block_2}
    for section in range(1, 5):
        blocks[section] = save_block_1[(section - 1) * LEGACY_DATA_SIZE:][:sizes[section]]
    for section in range(5, 14):
        blocks[section] = storage[(section - 5) * LEGACY_DATA_SIZE:][:sizes[section]]
    image = bytearray(b"\xFF" * FLASH_SIZE)
    slot = counter % 2 if slot is None else slot
    for section in range(LEGACY_SECTORS_PER_SLOT):
        raw = bytearray(SECTOR_SIZE)
        raw[: len(blocks[section])] = blocks[section]
        chunk = save_block_3[section * LEGACY_SB3_CHUNK:(section + 1) * LEGACY_SB3_CHUNK]
        raw[LEGACY_DATA_SIZE:LEGACY_DATA_SIZE + len(chunk)] = chunk
        struct.pack_into("<HHII", raw, LEGACY_FOOTER, section, legacy_checksum(bytes(raw), sizes[section]),
                         SIGNATURE_LEGACY, counter)
        physical = slot * LEGACY_SECTORS_PER_SLOT + (section + rotation) % LEGACY_SECTORS_PER_SLOT
        image[physical * SECTOR_SIZE:(physical + 1) * SECTOR_SIZE] = raw
    if hall_of_fame is not None:
        image[28 * SECTOR_SIZE:29 * SECTOR_SIZE] = hall_of_fame[0]
        image[29 * SECTOR_SIZE:30 * SECTOR_SIZE] = hall_of_fame[1]
    return bytes(image)
