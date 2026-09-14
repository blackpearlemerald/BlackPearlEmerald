"""BPE release identity, deterministic packages and UPS validation (stdlib only)."""
from __future__ import annotations

import functools
import hashlib
import json
import re
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_SIZE = 16 * 1024 * 1024
BASE_CRC = "1F1C08FB"
MAX_ROM_SIZE = 32 * 1024 * 1024
MAX_PATCH_SIZE = 40 * 1024 * 1024
VERSION_RE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z")


def version(value):
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise ValueError("Version must be SemVer, e.g. 2.0.0-beta or 2.0.1.")
    pre = VERSION_RE.fullmatch(value)[4]
    if pre and any(p.isdigit() and len(p) > 1 and p.startswith("0") for p in pre.split(".")):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeroes.")
    if len(label(value)) > 26:
        raise ValueError("Version label is too long for the title screen (26 characters).")
    return value


def label(value):
    core, _, pre = value.partition("-")
    return core + (" " + pre.replace(".", " ").title() if pre else "")


def compare_versions(a, b):
    ma, mb = VERSION_RE.fullmatch(version(a)), VERSION_RE.fullmatch(version(b))
    ca, cb = tuple(map(int, ma.group(1, 2, 3))), tuple(map(int, mb.group(1, 2, 3)))
    if ca != cb:
        return (ca > cb) - (ca < cb)
    pa, pb = ma[4], mb[4]
    if pa is None or pb is None:
        return (pa is None) - (pb is None)
    for x, y in zip(pa.split("."), pb.split(".")):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return (int(x) > int(y)) - (int(x) < int(y))
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return (x > y) - (x < y)
    return (len(pa.split(".")) > len(pb.split("."))) - (len(pa.split(".")) < len(pb.split(".")))


VERSION_KEY = functools.cmp_to_key(compare_versions)


def git(*args, root=ROOT):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=root).decode("utf-8").strip()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def crc32(data):
    return f"{zlib.crc32(data):08X}"


def describe(data):
    return {"size": len(data), "crc32": crc32(data), "sha256": sha256(data)}


def json_bytes(data):
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def encode_number(value):
    result = bytearray()
    while True:
        digit = value & 0x7f
        value >>= 7
        if not value:
            result.append(digit | 0x80)
            return result
        result.append(digit)
        value -= 1


def decode_number(data, pos, end):
    value, shift = 0, 1
    for _ in range(6):
        if pos >= end:
            raise ValueError("Truncated UPS integer.")
        digit = data[pos]
        pos += 1
        value += (digit & 0x7f) * shift
        if digit & 0x80:
            return value, pos
        shift <<= 7
        value += shift
    raise ValueError("Oversized UPS integer.")


def create_ups(source, target):
    size = max(len(source), len(target))
    old, new = source.ljust(size, b"\0"), target.ljust(size, b"\0")
    patch = bytearray(b"UPS1") + encode_number(len(source)) + encode_number(len(target))
    pos = cursor = 0
    while pos < size:
        if old[pos] == new[pos]:
            pos += 1
            continue
        patch.extend(encode_number(pos - cursor))
        while pos < size and old[pos] != new[pos]:
            patch.append(old[pos] ^ new[pos])
            pos += 1
        patch.append(0)
        pos += 1
        cursor = pos
    patch.extend(struct.pack("<II", zlib.crc32(source), zlib.crc32(target)))
    patch.extend(struct.pack("<I", zlib.crc32(patch)))
    return bytes(patch)


def inspect_ups(data):
    if len(data) < 18 or len(data) > MAX_PATCH_SIZE or data[:4] != b"UPS1":
        raise ValueError("Invalid UPS header or size.")
    inp, out, check = struct.unpack("<III", data[-12:])
    if zlib.crc32(data[:-4]) != check:
        raise ValueError("UPS checksum mismatch.")
    end = len(data) - 12
    in_size, pos = decode_number(data, 4, end)
    out_size, pos = decode_number(data, pos, end)
    if not 0 <= in_size <= MAX_ROM_SIZE or not 0 <= out_size <= MAX_ROM_SIZE:
        raise ValueError("UPS ROM size exceeds GBA limits.")
    body_start, offset = pos, 0
    while pos < end:
        skip, pos = decode_number(data, pos, end)
        offset += skip
        while pos < end and data[pos]:
            if offset >= max(in_size, out_size):
                raise ValueError("UPS record writes beyond the ROM.")
            offset += 1
            pos += 1
        if pos >= end:
            raise ValueError("Unterminated UPS record.")
        offset += 1
        pos += 1
    return {"input": {"size": in_size, "crc32": f"{inp:08X}"},
            "output": {"size": out_size, "crc32": f"{out:08X}"}, "bodyStart": body_start}


def apply_ups(source, patch):
    info = inspect_ups(patch)
    if {"size": len(source), "crc32": crc32(source)} != info["input"]:
        raise ValueError("The ROM does not match the UPS input.")
    result = bytearray(source.ljust(max(len(source), info["output"]["size"]), b"\0"))
    pos, end, offset = info["bodyStart"], len(patch) - 12, 0
    while pos < end:
        skip, pos = decode_number(patch, pos, end)
        offset += skip
        while patch[pos]:
            result[offset] ^= patch[pos]
            offset += 1
            pos += 1
        offset += 1
        pos += 1
    result = bytes(result[:info["output"]["size"]])
    if crc32(result) != info["output"]["crc32"]:
        raise ValueError("Patched output checksum mismatch.")
    return result


def write_zip(path, files):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)


def read_package(path, *, check_source=True, root=ROOT):
    path = Path(path)
    match = re.fullmatch(r"BlackPearlEmerald_v(.+)\.zip", path.name)
    if not match:
        raise ValueError("Package must be named BlackPearlEmerald_v<version>.zip.")
    release = version(match[1])
    patch_name = f"BlackPearlEmerald_v{release}.ups"
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != 2 or {e.filename for e in entries} != {patch_name, "release.json"}:
            raise ValueError("Package must contain only release.json and its named UPS patch.")
        for entry in entries:
            limit = 16384 if entry.filename == "release.json" else MAX_PATCH_SIZE
            if entry.file_size > limit or entry.flag_bits & 1 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe ZIP entry.")
        metadata = json.loads(archive.read("release.json"))
        patch = archive.read(patch_name)
    if metadata.get("schemaVersion") != 1 or metadata.get("version") != release:
        raise ValueError("Filename, metadata version, or package schema disagree.")
    if metadata.get("patch") != dict(describe(patch), file=patch_name, format="ups"):
        raise ValueError("Patch metadata/checksum mismatch.")
    info = inspect_ups(patch)
    for key, ups_key in (("baseRom", "input"), ("outputRom", "output")):
        record = metadata.get(key, {})
        if not isinstance(record, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", ""))):
            raise ValueError(f"Invalid {key} SHA-256.")
        if any(record.get(k) != v for k, v in info[ups_key].items()):
            raise ValueError(f"{key} does not match the UPS header.")
    if info["input"] != {"size": BASE_SIZE, "crc32": BASE_CRC}:
        raise ValueError("Release patch must use clean US Emerald (CRC32 1F1C08FB).")
    commit = metadata.get("sourceCommit", "")
    if not re.fullmatch(r"[a-f0-9]{40}", str(commit)):
        raise ValueError("A full source commit is required.")
    if check_source:
        # Only commits in the publication checkout's history are eligible.
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root, check=True)
        source_version = json.loads(git("show", f"{commit}:BPE_VERSION.json", root=root))["version"]
        if source_version != release:
            raise ValueError("Package version differs from its recorded game source.")
    return metadata, patch
