#!/usr/bin/env python3
"""Offline, source-aware inspector for Black Pearl Emerald .sav and .srm files."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = TOOL_DIR.parents[1]
SECTOR_SIZE = 0x1000
SECTOR_DATA_SIZE = 3968
SAVEBLOCK3_CHUNK_SIZE = 116
SECTORS_COUNT = 32
SAVE_SIZE = SECTOR_SIZE * SECTORS_COUNT
FOOTER_OFFSET = SECTOR_DATA_SIZE + SAVEBLOCK3_CHUNK_SIZE
SIGNATURE_OFFSET = FOOTER_OFFSET + 4
SECTOR_SIGNATURE = 0x08012025

SUBSTRUCTURE_ORDERS = [
    [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 2, 3, 1],
    [0, 3, 1, 2], [0, 3, 2, 1], [1, 0, 2, 3], [1, 0, 3, 2],
    [1, 2, 0, 3], [1, 2, 3, 0], [1, 3, 0, 2], [1, 3, 2, 0],
    [2, 0, 1, 3], [2, 0, 3, 1], [2, 1, 0, 3], [2, 1, 3, 0],
    [2, 3, 0, 1], [2, 3, 1, 0], [3, 0, 1, 2], [3, 0, 2, 1],
    [3, 1, 0, 2], [3, 1, 2, 0], [3, 2, 0, 1], [3, 2, 1, 0],
]


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_s16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_game_text(data: bytes) -> str:
    table = {
        0x00: " ", 0x2D: "&", 0x2E: "+", 0x35: "=", 0x36: ";",
        0x5B: "%", 0x5C: "(", 0x5D: ")", 0x79: "↑", 0x7A: "↓",
        0x7B: "←", 0x7C: "→", 0xAB: "!", 0xAC: "?", 0xAD: ".",
        0xAE: "-", 0xB0: "…", 0xB5: "♂", 0xB6: "♀", 0xB7: "$",
        0xB8: ",", 0xB9: "×", 0xBA: "/", 0xF0: ":",
    }
    for index, char in enumerate("0123456789", 0xA1):
        table[index] = char
    for index, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 0xBB):
        table[index] = char
    for index, char in enumerate("abcdefghijklmnopqrstuvwxyz", 0xD5):
        table[index] = char
    result: list[str] = []
    for value in data:
        if value == 0xFF:
            break
        if value in (0xFC, 0xFD):
            result.append(f"<{value:02X}>")
        elif value == 0xFE:
            result.append("\n")
        else:
            result.append(table.get(value, f"<{value:02X}>"))
    return "".join(result).rstrip()


class Schema:
    def __init__(self, path: Path) -> None:
        self.document = json.loads(path.read_text(encoding="utf-8"))
        self.types: dict[str, dict[str, Any]] = self.document["types"]
        self.roots: dict[str, str] = self.document["roots"]

    def resolve(self, type_id: str) -> tuple[str, dict[str, Any]]:
        seen: set[str] = set()
        while True:
            if type_id in seen:
                raise ValueError(f"Recursive typedef at {type_id}")
            seen.add(type_id)
            value = self.types[type_id]
            if value["kind"] not in {"typedef", "const_type", "volatile_type", "restrict_type"}:
                return type_id, value
            type_id = value["target"]

    def root(self, name: str) -> dict[str, Any]:
        return self.resolve(self.roots[name])[1]

    def member(self, root_or_type: str | dict[str, Any], name: str) -> dict[str, Any]:
        value = self.root(root_or_type) if isinstance(root_or_type, str) and root_or_type in self.roots else root_or_type
        if isinstance(value, str):
            value = self.resolve(value)[1]
        for member in value.get("members", []):
            if member["name"] == name:
                return member
        raise KeyError(f"No member {name!r}")

    def size(self, type_id: str) -> int:
        _, value = self.resolve(type_id)
        if "size" in value:
            return int(value["size"])
        if value["kind"] == "array_type":
            count = 1
            for dimension in value["dimensions"]:
                count *= int(dimension)
            return count * self.size(value["target"])
        raise ValueError(f"Type {type_id} has no size")

    def array(self, member: dict[str, Any]) -> tuple[str, list[int]]:
        _, value = self.resolve(member["type"])
        if value["kind"] != "array_type":
            raise ValueError(f"{member['name']} is not an array")
        return value["target"], [int(item) for item in value["dimensions"]]

    def enum_values(self, enum_name: str) -> dict[int, list[str]]:
        values: dict[int, list[str]] = defaultdict(list)
        for entry in self.types.values():
            if entry.get("kind") == "enumeration_type" and entry.get("name") == enum_name:
                for name, value in entry.get("values", {}).items():
                    values[int(value)].append(name)
        return dict(values)

    def decode(self, data: bytes, type_id: str, offset: int = 0) -> Any:
        _, value = self.resolve(type_id)
        kind = value["kind"]
        if kind in {"base_type", "enumeration_type", "pointer_type"}:
            size = int(value.get("size", 4))
            raw = data[offset:offset + size]
            if len(raw) != size:
                return {"error": "outside block", "offset": offset, "size": size}
            signed = value.get("encoding") in (5, 6)
            number = int.from_bytes(raw, "little", signed=signed)
            if kind == "pointer_type":
                return f"0x{number:0{size * 2}X}"
            if kind == "enumeration_type":
                names = [name for name, enum_value in value.get("values", {}).items() if enum_value == number]
                return {"value": number, "names": names}
            return number
        if kind == "array_type":
            dimensions = [int(item) for item in value["dimensions"]]
            element_type = value["target"]
            element_size = self.size(element_type)

            def decode_dimension(base: int, remaining: list[int]) -> list[Any]:
                if len(remaining) == 1:
                    return [self.decode(data, element_type, base + i * element_size) for i in range(remaining[0])]
                stride = element_size
                for dimension in remaining[1:]:
                    stride *= dimension
                return [decode_dimension(base + i * stride, remaining[1:]) for i in range(remaining[0])]

            return decode_dimension(offset, dimensions)
        if kind in {"structure_type", "union_type"}:
            result: dict[str, Any] = {}
            for member in value.get("members", []):
                member_offset = offset + int(member.get("offset", 0))
                if "bit_size" in member:
                    storage_size = self.size(member["type"])
                    storage = int.from_bytes(data[member_offset:member_offset + storage_size], "little")
                    if "data_bit_offset" in member:
                        shift = int(member["data_bit_offset"]) - int(member.get("offset", 0)) * 8
                    else:
                        shift = storage_size * 8 - int(member.get("bit_offset", 0)) - int(member["bit_size"])
                    result[member["name"]] = (storage >> shift) & ((1 << int(member["bit_size"])) - 1)
                else:
                    result[member["name"]] = self.decode(data, member["type"], member_offset)
            return result
        return {"unsupported_type": kind, "offset": offset}


class Symbols:
    def __init__(self, path: Path) -> None:
        self.document = json.loads(path.read_text(encoding="utf-8"))
        self.definitions: dict[str, dict[str, Any]] = self.document.get("definitions", {})
        self.reverse: dict[str, dict[int, list[str]]] = {}
        for group in ("flags", "vars", "game_stats", "maps"):
            values: dict[int, list[str]] = defaultdict(list)
            for name, number in self.document.get(group, {}).items():
                values[int(number)].append(name)
            self.reverse[group] = dict(values)

    def names(self, group: str, value: int) -> list[str]:
        return self.reverse.get(group, {}).get(value, [])


def locate_save_payload(file_data: bytes) -> tuple[int, bytes, int]:
    if len(file_data) < SAVE_SIZE:
        raise ValueError(f"File is {len(file_data)} bytes; a GBA flash save needs at least {SAVE_SIZE} bytes")
    signature = struct.pack("<I", SECTOR_SIGNATURE)
    candidates: Counter[int] = Counter()
    position = file_data.find(signature)
    while position >= 0:
        for physical_sector in range(SECTORS_COUNT):
            start = position - SIGNATURE_OFFSET - physical_sector * SECTOR_SIZE
            if 0 <= start <= len(file_data) - SAVE_SIZE:
                candidates[start] += 1
        position = file_data.find(signature, position + 1)
    if not candidates:
        raise ValueError("No Pokémon Emerald sector signatures found; this may be an emulator save state, not SRAM")
    offset, score = max(candidates.items(), key=lambda item: (item[1], -item[0]))
    if score < 4:
        raise ValueError(f"Only {score} sector signatures aligned; file does not look like an Emerald .sav/.srm")
    return offset, file_data[offset:offset + SAVE_SIZE], score


def checksum(data: bytes, size: int) -> int:
    total = 0
    for offset in range(0, size - (size % 4), 4):
        total = (total + read_u32(data, offset)) & 0xFFFFFFFF
    return ((total >> 16) + total) & 0xFFFF


def section_sizes(schema: Schema) -> dict[int, int]:
    result = {0: min(int(schema.root("SaveBlock2")["size"]), SECTOR_DATA_SIZE)}
    sb1_size = int(schema.root("SaveBlock1")["size"])
    storage_size = int(schema.root("PokemonStorage")["size"])
    for section_id in range(1, 5):
        result[section_id] = max(0, min(sb1_size - (section_id - 1) * SECTOR_DATA_SIZE, SECTOR_DATA_SIZE))
    for section_id in range(5, 14):
        result[section_id] = max(0, min(storage_size - (section_id - 5) * SECTOR_DATA_SIZE, SECTOR_DATA_SIZE))
    return result


def parse_physical_sectors(payload: bytes, sizes: dict[int, int]) -> list[dict[str, Any]]:
    sectors: list[dict[str, Any]] = []
    for physical in range(SECTORS_COUNT):
        start = physical * SECTOR_SIZE
        raw = payload[start:start + SECTOR_SIZE]
        section_id, stored_checksum, signature, counter = struct.unpack_from("<HHII", raw, FOOTER_OFFSET)
        size = sizes.get(section_id)
        computed = checksum(raw, size) if size is not None else None
        sectors.append({
            "physical_sector": physical,
            "section_id": section_id,
            "counter": counter,
            "signature_valid": signature == SECTOR_SIGNATURE,
            "stored_checksum": stored_checksum,
            "computed_checksum": computed,
            "checksum_valid": computed == stored_checksum if computed is not None else None,
            "raw": raw,
        })
    return sectors


def slot_candidates(sectors: list[dict[str, Any]], slot_number: int) -> list[dict[str, Any]]:
    physical = sectors[slot_number * 14:(slot_number + 1) * 14]
    counters = sorted({sector["counter"] for sector in physical if sector["signature_valid"]})
    candidates: list[dict[str, Any]] = []
    for counter in counters:
        matching = [
            sector for sector in physical
            if sector["counter"] == counter and sector["signature_valid"] and sector["checksum_valid"]
            and 0 <= sector["section_id"] < 14
        ]
        by_id: dict[int, dict[str, Any]] = {}
        for sector in matching:
            by_id[sector["section_id"]] = sector
        candidates.append({
            "slot": slot_number,
            "counter": counter,
            "valid_section_ids": sorted(by_id),
            "complete": len(by_id) == 14,
            "sections": by_id,
        })
    return candidates


def counter_is_newer(left: int, right: int) -> bool:
    difference = (left - right) & 0xFFFFFFFF
    return difference != 0 and difference < 0x80000000


def choose_candidate(candidates: list[dict[str, Any]], forced_slot: int | None) -> dict[str, Any]:
    if forced_slot is not None:
        candidates = [candidate for candidate in candidates if candidate["slot"] == forced_slot]
    if not candidates:
        raise ValueError("No valid save-slot sectors were found")
    best = candidates[0]
    for candidate in candidates[1:]:
        best_count = len(best["valid_section_ids"])
        candidate_count = len(candidate["valid_section_ids"])
        if candidate_count > best_count or (
            candidate_count == best_count and counter_is_newer(candidate["counter"], best["counter"])
        ):
            best = candidate
    return best


def reconstruct(candidate: dict[str, Any], schema: Schema) -> dict[str, bytes]:
    sections: dict[int, dict[str, Any]] = candidate["sections"]

    def section_data(section_id: int) -> bytes:
        sector = sections.get(section_id)
        return sector["raw"][:SECTOR_DATA_SIZE] if sector else bytes(SECTOR_DATA_SIZE)

    save_block_2 = section_data(0)[:int(schema.root("SaveBlock2")["size"])]
    save_block_1 = b"".join(section_data(i) for i in range(1, 5))[:int(schema.root("SaveBlock1")["size"])]
    storage = b"".join(section_data(i) for i in range(5, 14))[:int(schema.root("PokemonStorage")["size"])]
    save_block_3 = b"".join(
        sections[i]["raw"][SECTOR_DATA_SIZE:FOOTER_OFFSET] if i in sections else bytes(SAVEBLOCK3_CHUNK_SIZE)
        for i in range(14)
    )[:int(schema.root("SaveBlock3")["size"])]
    return {"save_block_1": save_block_1, "save_block_2": save_block_2, "save_block_3": save_block_3, "pokemon_storage": storage}


def array_offset_and_count(schema: Schema, root: str, member_name: str) -> tuple[int, str, int]:
    member = schema.member(root, member_name)
    target, dimensions = schema.array(member)
    count = 1
    for dimension in dimensions:
        count *= dimension
    return int(member["offset"]), target, count


def warp(data: bytes, offset: int, symbols: Symbols) -> dict[str, Any]:
    map_group, map_number, warp_id = struct.unpack_from("<bbb", data, offset)
    map_id = (map_number & 0xFF) | ((map_group & 0xFF) << 8)
    return {
        "map_group": map_group,
        "map_number": map_number,
        "map_id": f"0x{map_id:04X}",
        "map_names": symbols.names("maps", map_id),
        "warp_id": warp_id,
        "x": read_s16(data, offset + 4),
        "y": read_s16(data, offset + 6),
    }


def decrypt_box_pokemon(record: bytes) -> bytes:
    if len(record) < 80:
        return record
    output = bytearray(record)
    key = read_u32(record, 0) ^ read_u32(record, 4)
    for offset in range(32, 80, 4):
        struct.pack_into("<I", output, offset, read_u32(record, offset) ^ key)
    return bytes(output)


def enum_label(values: dict[int, list[str]], number: int) -> dict[str, Any]:
    return {"id": number, "names": values.get(number, [])}


def parse_pokemon(record: bytes, is_party: bool, schema: Schema, enum_maps: dict[str, dict[int, list[str]]]) -> dict[str, Any]:
    decrypted = decrypt_box_pokemon(record)
    personality = read_u32(decrypted, 0)
    ot_id = read_u32(decrypted, 4)
    flags = decrypted[19]
    order = SUBSTRUCTURE_ORDERS[personality % 24]

    def substructure(kind: int) -> bytes:
        index = order.index(kind)
        return decrypted[32 + index * 12:32 + (index + 1) * 12]

    growth, attacks, condition, misc = (substructure(index) for index in range(4))
    species = read_u16(growth, 0) & 0x7FF
    held_item = read_u16(growth, 2) & 0x3FF
    experience = read_u32(growth, 4) & 0x1FFFFF
    moves = [read_u16(attacks, offset) & 0x7FF for offset in (0, 2, 4, 6)]
    iv_data = read_u32(misc, 4)
    ribbon_data = read_u32(misc, 8)
    stored_checksum = read_u16(decrypted, 28)
    computed_checksum = sum(read_u16(decrypted, offset) for offset in range(32, 80, 2)) & 0xFFFF
    has_species = bool(flags & 0x02)
    result: dict[str, Any] = {
        "present": has_species or species != 0,
        "checksum_valid": stored_checksum == computed_checksum,
        "stored_checksum": stored_checksum,
        "computed_checksum": computed_checksum,
        "personality": personality,
        "original_trainer_id": ot_id & 0xFFFF,
        "original_trainer_secret_id": ot_id >> 16,
        "nickname": decode_game_text(decrypted[8:18]),
        "original_trainer_name": decode_game_text(decrypted[20:27]),
        "language": decrypted[18] & 0x07,
        "has_species_flag": has_species,
        "is_egg": bool(flags & 0x04) or bool((iv_data >> 30) & 1),
        "is_dead": bool(flags & 0x10),
        "days_since_form_change": (flags >> 5) & 0x07,
        "species": enum_label(enum_maps["Species"], species),
        "held_item": enum_label(enum_maps["Item"], held_item),
        "experience": experience,
        "friendship": growth[9],
        "pokeball": read_u16(growth, 10) & 0x3F,
        "moves": [enum_label(enum_maps["Move"], move) for move in moves],
        "move_pp": [attacks[offset] & 0x7F for offset in (8, 9, 10, 11)],
        "pp_bonuses": growth[8],
        "evs": {
            "hp": condition[0], "attack": condition[1], "defense": condition[2],
            "speed": condition[3], "special_attack": condition[4], "special_defense": condition[5],
        },
        "contest": {
            "cool": condition[6], "beauty": condition[7], "cute": condition[8],
            "smart": condition[9], "tough": condition[10], "sheen": condition[11],
        },
        "ivs": {
            "hp": iv_data & 0x1F, "attack": (iv_data >> 5) & 0x1F,
            "defense": (iv_data >> 10) & 0x1F, "speed": (iv_data >> 15) & 0x1F,
            "special_attack": (iv_data >> 20) & 0x1F, "special_defense": (iv_data >> 25) & 0x1F,
        },
        "ability_slot": (ribbon_data >> 29) & 0x03,
        "met_location": misc[1],
        "met_level": read_u16(misc, 2) & 0x7F,
        "met_game": (read_u16(misc, 2) >> 7) & 0x0F,
        "dynamax_level": (read_u16(misc, 2) >> 11) & 0x0F,
        "shiny": ((ot_id & 0xFFFF) ^ (ot_id >> 16) ^ (personality & 0xFFFF) ^ (personality >> 16)) < 8,
    }
    if is_party and len(record) >= 100:
        result["party_data"] = {
            "status": read_u32(record, 80), "level": record[84], "mail": record[85],
            "current_hp": read_u16(record, 86), "maximum_hp": read_u16(record, 88),
            "attack": read_u16(record, 90), "defense": read_u16(record, 92),
            "speed": read_u16(record, 94), "special_attack": read_u16(record, 96),
            "special_defense": read_u16(record, 98),
        }
    return result


def parse_items(block: bytes, base_offset: int, count: int, encrypted: bool, key: int, item_names: dict[int, list[str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for slot in range(count):
        offset = base_offset + slot * 4
        item_id = read_u16(block, offset)
        stored_quantity = read_u16(block, offset + 2)
        quantity = stored_quantity ^ (key & 0xFFFF) if encrypted else stored_quantity
        if item_id or quantity:
            result.append({"slot": slot, "item": enum_label(item_names, item_id), "quantity": quantity})
    return result


def parse_rom_header(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    marker = b"pokemon emerald version"
    name_offset = data.find(marker)
    if name_offset < 8:
        raise ValueError(f"No public Emerald ROM header found in {path}")
    start = name_offset - 8
    u32_fields = {
        "version": 0, "language": 4, "flags_offset": 80, "vars_offset": 84,
        "pokedex_offset": 88, "seen_1_offset": 92, "seen_2_offset": 96,
        "pokedex_var_index": 100, "pokedex_flag": 104, "mystery_event_flag": 108,
        "pokedex_count": 112, "save_block_2_size": 136, "save_block_1_size": 140,
        "party_count_offset": 144, "party_offset": 148, "warp_flags_offset": 152,
        "trainer_id_offset": 156, "player_name_offset": 160, "player_gender_offset": 164,
        "pc_items_offset": 236, "game_clear_flag": 220, "ribbon_flag": 224,
    }
    result = {name: read_u32(data, start + offset) for name, offset in u32_fields.items()}
    result.update({
        "path": str(path.resolve()), "sha256": sha256(data), "file_size": len(data),
        "header_file_offset": start, "game_name": data[start + 8:start + 40].split(b"\0", 1)[0].decode("ascii", "replace"),
        "player_name_length": data[start + 116], "trainer_name_length": data[start + 117],
        "pokemon_name_length": data[start + 118],
        "bag_counts": {
            "items": data[start + 228], "key_items": data[start + 229], "poke_balls": data[start + 230],
            "tm_hm": data[start + 231], "berries": data[start + 232], "pc_items": data[start + 233],
        },
    })
    result["release"] = identify_release_by_rom_sha(result["sha256"], DEFAULT_REPO_ROOT)
    return result


def release_manifests(repo_root: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    packages = repo_root / "releases" / "packages"
    if not packages.is_dir():
        return manifests
    for path in sorted(packages.glob("*.zip")):
        try:
            with zipfile.ZipFile(path) as archive:
                document = json.loads(archive.read("release.json"))
            document["package"] = path.relative_to(repo_root).as_posix()
            manifests.append(document)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            continue
    return manifests


def identify_release_by_rom_sha(rom_sha256: str, repo_root: Path) -> dict[str, Any] | None:
    for manifest in release_manifests(repo_root):
        if manifest.get("outputRom", {}).get("sha256", "").lower() == rom_sha256.lower():
            return {
                "version": manifest.get("version"), "source_commit": manifest.get("sourceCommit"),
                "package": manifest.get("package"),
            }
    return None


def inspect_save(path: Path, schema: Schema, symbols: Symbols, rom: Path | None = None,
                 forced_slot: int | None = None, include_raw: bool = False) -> tuple[dict[str, Any], dict[str, bytes]]:
    file_data = path.read_bytes()
    payload_offset, payload, signature_score = locate_save_payload(file_data)
    sizes = section_sizes(schema)
    physical = parse_physical_sectors(payload, sizes)
    candidates = slot_candidates(physical, 0) + slot_candidates(physical, 1)
    selected = choose_candidate(candidates, forced_slot)
    blocks = reconstruct(selected, schema)
    sb1, sb2, sb3, storage = (
        blocks["save_block_1"], blocks["save_block_2"], blocks["save_block_3"], blocks["pokemon_storage"]
    )
    enum_maps = {name: schema.enum_values(name) for name in ("Species", "Item", "Move")}

    sb1_root, sb2_root = schema.root("SaveBlock1"), schema.root("SaveBlock2")
    encryption_key = read_u32(sb2, int(schema.member(sb2_root, "encryptionKey")["offset"]))
    flags_member = schema.member(sb1_root, "flags")
    flags_target, flag_dimensions = schema.array(flags_member)
    del flags_target
    flags_offset, flags_size = int(flags_member["offset"]), flag_dimensions[0]
    flags: list[dict[str, Any]] = []
    for flag_id in range(1, flags_size * 8):
        names = symbols.names("flags", flag_id)
        definitions = [symbols.definitions[name] | {"name": name} for name in names if name in symbols.definitions]
        flags.append({
            "id": flag_id, "hex_id": f"0x{flag_id:04X}",
            "set": bool(sb1[flags_offset + flag_id // 8] & (1 << (flag_id & 7))),
            "names": names, "definitions": definitions,
        })

    vars_member = schema.member(sb1_root, "vars")
    _, var_dimensions = schema.array(vars_member)
    vars_offset, var_count = int(vars_member["offset"]), var_dimensions[0]
    variables: list[dict[str, Any]] = []
    for index in range(var_count):
        var_id = 0x4000 + index
        names = symbols.names("vars", var_id)
        definitions = [symbols.definitions[name] | {"name": name} for name in names if name in symbols.definitions]
        variables.append({
            "id": var_id, "hex_id": f"0x{var_id:04X}", "value": read_u16(sb1, vars_offset + index * 2),
            "hex_value": f"0x{read_u16(sb1, vars_offset + index * 2):04X}", "names": names,
            "definitions": definitions,
        })

    stat_member = schema.member(sb1_root, "gameStats")
    _, stat_dimensions = schema.array(stat_member)
    stat_offset = int(stat_member["offset"])
    game_stats = [
        {
            "id": index, "names": symbols.names("game_stats", index),
            "value": read_u32(sb1, stat_offset + index * 4) ^ encryption_key,
        }
        for index in range(stat_dimensions[0])
    ]

    party_count_offset = int(schema.member(sb1_root, "playerPartyCount")["offset"])
    party_member = schema.member(sb1_root, "playerParty")
    party_type, party_dimensions = schema.array(party_member)
    party_size = schema.size(party_type)
    party = [
        parse_pokemon(
            sb1[int(party_member["offset"]) + index * party_size:int(party_member["offset"]) + (index + 1) * party_size],
            True, schema, enum_maps,
        ) | {"slot": index}
        for index in range(party_dimensions[0])
    ]

    storage_root = schema.root("PokemonStorage")
    boxes_member = schema.member(storage_root, "boxes")
    box_type, box_dimensions = schema.array(boxes_member)
    box_size = schema.size(box_type)
    boxes: list[dict[str, Any]] = []
    boxes_base = int(boxes_member["offset"])
    names_member = schema.member(storage_root, "boxNames")
    box_names_type, box_names_dimensions = schema.array(names_member)
    del box_names_type
    box_name_length = box_names_dimensions[1]
    for box_index in range(box_dimensions[0]):
        mons: list[dict[str, Any]] = []
        for slot in range(box_dimensions[1]):
            offset = boxes_base + (box_index * box_dimensions[1] + slot) * box_size
            mon = parse_pokemon(storage[offset:offset + box_size], False, schema, enum_maps)
            if mon["present"]:
                mons.append(mon | {"slot": slot})
        name_offset = int(names_member["offset"]) + box_index * box_name_length
        boxes.append({"box": box_index, "name": decode_game_text(storage[name_offset:name_offset + box_name_length]), "pokemon": mons})

    bag_member = schema.member(sb1_root, "bag")
    _, bag_type = schema.resolve(bag_member["type"])
    bag_base = int(bag_member["offset"])
    bag: dict[str, Any] = {}
    for field in bag_type["members"]:
        _, dimensions = schema.array(field)
        bag[field["name"]] = parse_items(
            sb1, bag_base + int(field["offset"]), dimensions[0], True, encryption_key, enum_maps["Item"]
        )
    pc_member = schema.member(sb1_root, "pcItems")
    _, pc_dimensions = schema.array(pc_member)
    pc_items = parse_items(sb1, int(pc_member["offset"]), pc_dimensions[0], False, encryption_key, enum_maps["Item"])

    location_member = schema.member(sb1_root, "location")
    pos_member = schema.member(sb1_root, "pos")
    money_offset = int(schema.member(sb1_root, "money")["offset"])
    coins_offset = int(schema.member(sb1_root, "coins")["offset"])
    dex_seen_member, dex_caught_member = schema.member(sb1_root, "dexSeen"), schema.member(sb1_root, "dexCaught")
    _, dex_dimensions = schema.array(dex_seen_member)
    dex_count = dex_dimensions[0] * 8

    pokedex = []
    for number in range(1, dex_count + 1):
        bit = number - 1
        seen = bool(sb1[int(dex_seen_member["offset"]) + bit // 8] & (1 << (bit & 7)))
        caught = bool(sb1[int(dex_caught_member["offset"]) + bit // 8] & (1 << (bit & 7)))
        pokedex.append({"number": number, "species_names": enum_maps["Species"].get(number, []), "seen": seen, "caught": caught})

    warnings: list[str] = []
    if not selected["complete"]:
        warnings.append("Selected save slot is incomplete; missing sections were filled with zeroes in reconstructed blocks.")
    rom_header = None
    if rom is not None:
        rom_header = parse_rom_header(rom)
        checks = {
            "save_block_1_size": int(sb1_root["size"]),
            "save_block_2_size": int(sb2_root["size"]),
            "flags_offset": flags_offset,
            "vars_offset": vars_offset,
            "party_count_offset": party_count_offset,
            "party_offset": int(party_member["offset"]),
        }
        mismatches = {
            name: {"layout": expected, "rom": rom_header[name]}
            for name, expected in checks.items() if rom_header[name] != expected
        }
        rom_header["layout_mismatches"] = mismatches
        if mismatches:
            warnings.append("The supplied ROM and generated source layout do not match; semantic fields may be wrong.")
        release = rom_header.get("release")
        layout_commit = schema.document.get("source", {}).get("git_commit")
        if release and layout_commit and release.get("source_commit") != layout_commit:
            warnings.append(
                f"ROM is release {release.get('version')} from {release.get('source_commit')}, "
                f"but the selected inspector profile is from {layout_commit}. Use the matching release profile."
            )
    else:
        warnings.append("No ROM was supplied, so the generated source layout could not be cross-checked against the player's build.")

    slots_summary = []
    for slot in (0, 1):
        slot_values = [candidate for candidate in candidates if candidate["slot"] == slot]
        best_for_slot = max(slot_values, key=lambda value: len(value["valid_section_ids"]), default=None)
        slots_summary.append(None if best_for_slot is None else {
            "slot": slot, "counter": best_for_slot["counter"], "complete": best_for_slot["complete"],
            "valid_section_ids": best_for_slot["valid_section_ids"],
        })

    report: dict[str, Any] = {
        "format": "bpe-save-inspector-v1",
        "input": {"path": str(path.resolve()), "extension": path.suffix.lower(), "file_size": len(file_data), "sha256": sha256(file_data)},
        "payload": {"offset": payload_offset, "size": len(payload), "aligned_sector_signatures": signature_score},
        "layout": schema.document.get("source", {}),
        "rom": rom_header,
        "warnings": warnings,
        "slots": slots_summary,
        "selected_slot": {"slot": selected["slot"], "counter": selected["counter"], "complete": selected["complete"]},
        "sector_health": [
            {key: value for key, value in sector.items() if key != "raw"} for sector in physical
        ],
        "trainer": {
            "name": decode_game_text(sb2[0:8]), "gender": sb2[8],
            "public_id": read_u16(sb2, 10), "secret_id": read_u16(sb2, 12),
            "play_time": {"hours": read_u16(sb2, 14), "minutes": sb2[16], "seconds": sb2[17], "vblanks": sb2[18]},
        },
        "world": {
            "position": {"x": read_s16(sb1, int(pos_member["offset"])), "y": read_s16(sb1, int(pos_member["offset"]) + 2)},
            "location": warp(sb1, int(location_member["offset"]), symbols),
            "continue_game_warp": warp(sb1, int(schema.member(sb1_root, "continueGameWarp")["offset"]), symbols),
            "dynamic_warp": warp(sb1, int(schema.member(sb1_root, "dynamicWarp")["offset"]), symbols),
            "last_heal_location": warp(sb1, int(schema.member(sb1_root, "lastHealLocation")["offset"]), symbols),
            "escape_warp": warp(sb1, int(schema.member(sb1_root, "escapeWarp")["offset"]), symbols),
        },
        "economy": {"money": read_u32(sb1, money_offset) ^ encryption_key, "coins": read_u16(sb1, coins_offset) ^ (encryption_key & 0xFFFF)},
        "encryption_key": f"0x{encryption_key:08X}",
        "party_count": sb1[party_count_offset], "party": party,
        "boxes": boxes,
        "bag": bag, "pc_items": pc_items,
        "flags": flags, "active_flags": [flag for flag in flags if flag["set"]],
        "variables": variables, "nonzero_variables": [variable for variable in variables if variable["value"] != 0],
        "game_stats": game_stats,
        "pokedex": pokedex,
        "save_block_3": schema.decode(sb3, schema.roots["SaveBlock3"]),
        "block_hashes": {name: {"size": len(data), "sha256": sha256(data)} for name, data in blocks.items()},
    }
    if include_raw:
        report["raw_blocks_base64"] = {name: base64.b64encode(data).decode("ascii") for name, data in blocks.items()}
    return report, blocks


SOURCE_EXTENSIONS = {".c", ".h", ".inc", ".s", ".asm"}
SKIP_SOURCE_DIRS = {".git", "build", "tools", "node_modules", ".release-work"}


def classify_reference(symbol: str, line: str) -> str:
    lowered = line.lower()
    if symbol.startswith("FLAG_"):
        if "flagset" in lowered or "setflag" in lowered:
            return "set"
        if "flagclear" in lowered or "clearflag" in lowered:
            return "clear"
        if "flagtoggle" in lowered or "toggleflag" in lowered:
            return "toggle"
        if any(term in lowered for term in ("flagget", "checkflag", "goto_if_set", "goto_if_unset")):
            return "check_or_gate"
    if symbol.startswith("VAR_"):
        if any(term in lowered for term in ("varset", "setvar", "addvar", "subvar", "copyvar", "setorcopyvar")):
            return "write"
        if any(term in lowered for term in ("varget", "checkvar", "compare", "specialvar", "switch")):
            return "read_or_gate"
    return "reference"


def find_source_references(symbol: str, repo_root: Path) -> list[dict[str, Any]]:
    expression = re.compile(rf"\b{re.escape(symbol)}\b")
    references: list[dict[str, Any]] = []
    for current, directories, files in os.walk(repo_root):
        directories[:] = [directory for directory in directories if directory not in SKIP_SOURCE_DIRS]
        for filename in files:
            path = Path(current) / filename
            if path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, 1):
                if not expression.search(line):
                    continue
                start, end = max(0, line_number - 2), min(len(lines), line_number + 1)
                references.append({
                    "operation": classify_reference(symbol, line),
                    "file": path.relative_to(repo_root).as_posix(), "line": line_number,
                    "source": line.strip(),
                    "context": [{"line": index + 1, "source": lines[index].rstrip()} for index in range(start, end)],
                })
    return references


def find_git_source_references(symbol: str, repo_root: Path, commit: str) -> list[dict[str, Any]]:
    command = [
        "git", "-C", str(repo_root), "grep", "-n", "-I", "-w", "-e", symbol, commit, "--",
        "*.c", "*.h", "*.inc", "*.s", "*.asm",
    ]
    process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if process.returncode not in (0, 1):
        raise ValueError(process.stderr.strip() or f"Unable to search source commit {commit}")
    file_cache: dict[str, list[str]] = {}
    references: list[dict[str, Any]] = []
    prefix = f"{commit}:"
    for output_line in process.stdout.splitlines():
        if not output_line.startswith(prefix):
            continue
        remainder = output_line[len(prefix):]
        try:
            file_name, line_text, source = remainder.split(":", 2)
            line_number = int(line_text)
        except (ValueError, TypeError):
            continue
        if file_name not in file_cache:
            shown = subprocess.run(
                ["git", "-C", str(repo_root), "show", f"{commit}:{file_name}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            file_cache[file_name] = shown.stdout.splitlines() if shown.returncode == 0 else []
        lines = file_cache[file_name]
        start, end = max(0, line_number - 2), min(len(lines), line_number + 1)
        references.append({
            "operation": classify_reference(symbol, source), "file": file_name, "line": line_number,
            "source": source.strip(),
            "context": [{"line": index + 1, "source": lines[index].rstrip()} for index in range(start, end)],
            "source_commit": commit,
        })
    return references


def resolve_symbol(report: dict[str, Any], symbols: Symbols, symbol: str, repo_root: Path,
                   source_commit: str | None = None) -> dict[str, Any]:
    if symbol in symbols.document.get("flags", {}):
        number = int(symbols.document["flags"][symbol])
        state = next(flag for flag in report["flags"] if flag["id"] == number)
        kind = "flag"
    elif symbol in symbols.document.get("vars", {}):
        number = int(symbols.document["vars"][symbol])
        state = next(variable for variable in report["variables"] if variable["id"] == number)
        kind = "variable"
    else:
        try:
            number = int(symbol, 0)
        except ValueError as exc:
            raise ValueError(f"Unknown BPE flag or variable symbol: {symbol}") from exc
        if 0 < number < 0x4000:
            state = next(flag for flag in report["flags"] if flag["id"] == number)
            kind = "flag"
        elif 0x4000 <= number < 0x8000:
            state = next(variable for variable in report["variables"] if variable["id"] == number)
            kind = "variable"
        else:
            raise ValueError(f"ID 0x{number:X} is outside persistent flag/variable ranges")
    names = state["names"] or [symbol]
    references: list[dict[str, Any]] = []
    for name in names:
        if source_commit:
            references.extend(find_git_source_references(name, repo_root, source_commit))
        else:
            references.extend(find_source_references(name, repo_root))
    unique = {(item["file"], item["line"], item["source"]): item for item in references}
    return {
        "kind": kind, "requested": symbol, "state": state,
        "source_references": sorted(unique.values(), key=lambda item: (item["file"], item["line"])),
        "interpretation_note": "Operations are classified from explicit source calls only; inspect the supplied context before assigning story meaning.",
    }


def write_json(document: Any, output: Path | None) -> None:
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"Wrote {output.resolve()}")


def add_common_save_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("save", type=Path, help="Pokémon Emerald .sav or .srm file")
    parser.add_argument("--rom", type=Path, help="Matching BPE .gba used to validate compiled offsets")
    parser.add_argument("--slot", type=int, choices=(0, 1), help="Force physical save slot instead of selecting newest valid slot")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, help="Override the generated structure layout")
    parser.add_argument("--symbols", type=Path, help="Override the generated flag/variable symbol table")
    parser.add_argument("--profile", help="Use a bundled release profile, such as 2.0.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Create a complete decoded save report")
    add_common_save_args(inspect_parser)
    inspect_parser.add_argument("-o", "--output", type=Path)
    inspect_parser.add_argument("--include-raw", action="store_true", help="Embed reconstructed blocks as base64")

    query_parser = subparsers.add_parser("query", help="Read flags/vars and show every source reference")
    add_common_save_args(query_parser)
    query_parser.add_argument("symbols_to_query", nargs="+", help="Names such as FLAG_BADGE01_GET or VAR_0x40AA")
    query_parser.add_argument("--source-root", type=Path, default=DEFAULT_REPO_ROOT)
    query_parser.add_argument("-o", "--output", type=Path)

    extract_parser = subparsers.add_parser("extract", help="Extract every reconstructed raw save block")
    add_common_save_args(extract_parser)
    extract_parser.add_argument("output_directory", type=Path)

    dump_parser = subparsers.add_parser("dump", help="Decode an entire compiled C save structure")
    add_common_save_args(dump_parser)
    dump_parser.add_argument("block", choices=("SaveBlock1", "SaveBlock2", "SaveBlock3", "PokemonStorage"))
    dump_parser.add_argument("-o", "--output", type=Path)

    diff_parser = subparsers.add_parser("diff", help="Compare progression-relevant data in two saves")
    diff_parser.add_argument("before", type=Path)
    diff_parser.add_argument("after", type=Path)
    diff_parser.add_argument("--rom", type=Path)
    diff_parser.add_argument("-o", "--output", type=Path)

    args = parser.parse_args()
    profile = args.profile
    rom_argument = getattr(args, "rom", None)
    if profile is None and rom_argument is not None and rom_argument.exists():
        rom_hash = sha256(rom_argument.read_bytes())
        release = identify_release_by_rom_sha(rom_hash, DEFAULT_REPO_ROOT)
        if release:
            candidate = TOOL_DIR / "profiles" / str(release["version"])
            if candidate.is_dir():
                profile = str(release["version"])
    if profile:
        profile_dir = TOOL_DIR / "profiles" / profile
        if not profile_dir.is_dir():
            parser.error(f"Unknown inspector profile {profile!r}")
        layout_path = args.layout or profile_dir / "bpe_layout.json"
        symbols_path = args.symbols or profile_dir / "bpe_symbols.json"
    else:
        layout_path = args.layout or TOOL_DIR / "bpe_layout.json"
        symbols_path = args.symbols or TOOL_DIR / "bpe_symbols.json"
    schema, symbols = Schema(layout_path), Symbols(symbols_path)

    try:
        if args.command == "inspect":
            report, _ = inspect_save(args.save, schema, symbols, args.rom, args.slot, args.include_raw)
            write_json(report, args.output)
        elif args.command == "query":
            report, _ = inspect_save(args.save, schema, symbols, args.rom, args.slot)
            result = {
                "save": report["input"], "selected_slot": report["selected_slot"], "warnings": report["warnings"],
                "source_commit": schema.document.get("source", {}).get("git_commit"),
                "queries": [
                    resolve_symbol(
                        report, symbols, symbol, args.source_root.resolve(),
                        schema.document.get("source", {}).get("git_commit"),
                    )
                    for symbol in args.symbols_to_query
                ],
            }
            write_json(result, args.output)
        elif args.command == "extract":
            report, blocks = inspect_save(args.save, schema, symbols, args.rom, args.slot)
            args.output_directory.mkdir(parents=True, exist_ok=True)
            for name, data in blocks.items():
                (args.output_directory / f"{name}.bin").write_bytes(data)
            write_json({"report": report["input"], "selected_slot": report["selected_slot"], "blocks": report["block_hashes"]}, args.output_directory / "manifest.json")
        elif args.command == "dump":
            _, blocks = inspect_save(args.save, schema, symbols, args.rom, args.slot)
            block_names = {"SaveBlock1": "save_block_1", "SaveBlock2": "save_block_2", "SaveBlock3": "save_block_3", "PokemonStorage": "pokemon_storage"}
            write_json(schema.decode(blocks[block_names[args.block]], schema.roots[args.block]), args.output)
        elif args.command == "diff":
            before, _ = inspect_save(args.before, schema, symbols, args.rom)
            after, _ = inspect_save(args.after, schema, symbols, args.rom)
            before_flags = {item["id"]: item for item in before["flags"]}
            after_flags = {item["id"]: item for item in after["flags"]}
            before_vars = {item["id"]: item for item in before["variables"]}
            after_vars = {item["id"]: item for item in after["variables"]}
            result = {
                "before": before["input"], "after": after["input"],
                "flag_changes": [
                    {"id": number, "names": after_flags[number]["names"], "before": before_flags[number]["set"], "after": after_flags[number]["set"]}
                    for number in before_flags if before_flags[number]["set"] != after_flags[number]["set"]
                ],
                "variable_changes": [
                    {"id": number, "hex_id": f"0x{number:04X}", "names": after_vars[number]["names"], "before": before_vars[number]["value"], "after": after_vars[number]["value"]}
                    for number in before_vars if before_vars[number]["value"] != after_vars[number]["value"]
                ],
                "location": {"before": before["world"]["location"], "after": after["world"]["location"]},
                "economy": {"before": before["economy"], "after": after["economy"]},
            }
            write_json(result, args.output)
    except (OSError, ValueError, KeyError, struct.error) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
