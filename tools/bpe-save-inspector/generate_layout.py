#!/usr/bin/env python3
"""Generate a JSON description of BPE's compiled save structures from DWARF."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parents[1]
VENDOR_DIR = TOOL_DIR / "vendor"
sys.path.insert(0, str(VENDOR_DIR))

try:
    from elftools.elf.elffile import ELFFile
except ImportError as exc:  # pragma: no cover - installation error path
    raise SystemExit(
        "The vendored pyelftools package is missing. Reinstall this tool's dependencies."
    ) from exc

ROOT_VARIABLES = {
    "bpe_layout_save_block_1": "SaveBlock1",
    "bpe_layout_save_block_2": "SaveBlock2",
    "bpe_layout_save_block_3": "SaveBlock3",
    "bpe_layout_pokemon_storage": "PokemonStorage",
    "bpe_layout_save_sector": "SaveSector",
    "bpe_layout_pokemon": "Pokemon",
    "bpe_layout_box_pokemon": "BoxPokemon",
}
# Roots that only exist in some source versions (2.1 added PackedBoxMon).
OPTIONAL_ROOT_VARIABLES = {
    "bpe_layout_packed_box_mon": "PackedBoxMon",
}


def _decode(value: Any) -> Any:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _attr(die: Any, name: str, default: Any = None) -> Any:
    attribute = die.attributes.get(name)
    return _decode(attribute.value) if attribute is not None else default


def _member_offset(die: Any) -> int | None:
    value = _attr(die, "DW_AT_data_member_location")
    return value if isinstance(value, int) else None


class DwarfSchema:
    def __init__(self) -> None:
        self.types: dict[str, dict[str, Any]] = {}
        self._busy: set[str] = set()

    def add_type(self, die: Any | None) -> str | None:
        if die is None:
            return None
        key = f"0x{die.offset:x}"
        if key in self.types or key in self._busy:
            return key
        self._busy.add(key)
        tag = die.tag.removeprefix("DW_TAG_")
        entry: dict[str, Any] = {"kind": tag}
        name = _attr(die, "DW_AT_name")
        size = _attr(die, "DW_AT_byte_size")
        if name is not None:
            entry["name"] = name
        if size is not None:
            entry["size"] = size

        if tag in {"typedef", "const_type", "volatile_type", "restrict_type", "pointer_type"}:
            entry["target"] = self.add_type(die.get_DIE_from_attribute("DW_AT_type"))
        elif tag == "array_type":
            entry["target"] = self.add_type(die.get_DIE_from_attribute("DW_AT_type"))
            dimensions: list[int | None] = []
            for child in die.iter_children():
                if child.tag != "DW_TAG_subrange_type":
                    continue
                count = _attr(child, "DW_AT_count")
                upper = _attr(child, "DW_AT_upper_bound")
                dimensions.append(count if isinstance(count, int) else upper + 1 if isinstance(upper, int) else None)
            entry["dimensions"] = dimensions
        elif tag in {"structure_type", "union_type"}:
            members: list[dict[str, Any]] = []
            for child in die.iter_children():
                if child.tag != "DW_TAG_member":
                    continue
                member: dict[str, Any] = {
                    "name": _attr(child, "DW_AT_name", "<anonymous>"),
                    "type": self.add_type(child.get_DIE_from_attribute("DW_AT_type")),
                }
                offset = _member_offset(child)
                if offset is not None:
                    member["offset"] = offset
                for dwarf_name, json_name in (
                    ("DW_AT_bit_size", "bit_size"),
                    ("DW_AT_bit_offset", "bit_offset"),
                    ("DW_AT_data_bit_offset", "data_bit_offset"),
                ):
                    value = _attr(child, dwarf_name)
                    if value is not None:
                        member[json_name] = value
                members.append(member)
            entry["members"] = members
        elif tag == "enumeration_type":
            values: dict[str, int] = {}
            for child in die.iter_children():
                if child.tag == "DW_TAG_enumerator":
                    values[str(_attr(child, "DW_AT_name"))] = int(_attr(child, "DW_AT_const_value"))
            entry["values"] = values
        elif tag == "base_type":
            entry["encoding"] = _attr(die, "DW_AT_encoding")

        self.types[key] = entry
        self._busy.remove(key)
        return key


def extract_schema(object_path: Path) -> dict[str, Any]:
    with object_path.open("rb") as stream:
        dwarf = ELFFile(stream).get_dwarf_info()
        variables: dict[str, Any] = {}
        for cu in dwarf.iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag == "DW_TAG_variable":
                    name = _attr(die, "DW_AT_name")
                    if name in ROOT_VARIABLES or name in OPTIONAL_ROOT_VARIABLES:
                        variables[name] = die

        missing = sorted(set(ROOT_VARIABLES) - set(variables))
        if missing:
            raise RuntimeError(f"Layout probe variables missing from DWARF: {', '.join(missing)}")

        schema = DwarfSchema()
        root_names = ROOT_VARIABLES | OPTIONAL_ROOT_VARIABLES
        roots = {
            root_names[name]: schema.add_type(die.get_DIE_from_attribute("DW_AT_type"))
            for name, die in variables.items()
        }
        return {"format": 1, "roots": roots, "types": schema.types}


def windows_path_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        raise RuntimeError(f"Expected a Windows drive path, got {resolved}")
    tail = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def compile_probe(repo_root: Path, output: Path) -> None:
    repo_wsl = windows_path_to_wsl(repo_root)
    probe_wsl = windows_path_to_wsl(TOOL_DIR / "bpe_layout_probe.c")
    output_wsl = windows_path_to_wsl(output)
    command = [
        "wsl",
        "arm-none-eabi-gcc",
        "-mthumb",
        "-mthumb-interwork",
        "-mabi=apcs-gnu",
        "-mtune=arm7tdmi",
        "-march=armv4t",
        "-Og",
        "-g3",
        "-gdwarf-4",
        "-fno-eliminate-unused-debug-types",
        "-iquote",
        f"{repo_wsl}/include",
        "-DMODERN=1",
        "-DTESTING=0",
        "-DEMERALD",
        "-DRELEASE",
        "-std=gnu17",
        "-c",
        probe_wsl,
        "-o",
        output_wsl,
    ]
    subprocess.run(command, cwd=repo_root, check=True)


def _compiler_prefix(repo_root: Path) -> list[str]:
    return [
        "wsl",
        "arm-none-eabi-gcc",
        "-iquote",
        f"{windows_path_to_wsl(repo_root)}/include",
        "-DMODERN=1",
        "-DTESTING=0",
        "-DEMERALD",
        "-DRELEASE",
        "-std=gnu17",
    ]


class MacroEvaluator:
    _CAST = re.compile(r"\((?:u|s)?(?:8|16|32|64)\)")
    _SUFFIX = re.compile(r"(?<=\b\d)[uUlL]+\b|(?<=\b0[xX][0-9a-fA-F])[uUlL]+\b")

    def __init__(self, macros: dict[str, str]) -> None:
        self.macros = macros
        self.cache: dict[str, int] = {"TRUE": 1, "FALSE": 0}
        self.busy: set[str] = set()

    def name(self, name: str) -> int:
        if name in self.cache:
            return self.cache[name]
        if name in self.busy or name not in self.macros:
            raise ValueError(name)
        self.busy.add(name)
        try:
            value = self.expression(self.macros[name])
            self.cache[name] = value
            return value
        finally:
            self.busy.remove(name)

    def expression(self, expression: str) -> int:
        expression = self._CAST.sub("", expression)
        expression = self._SUFFIX.sub("", expression)
        node = ast.parse(expression, mode="eval").body
        return self._node(node)

    def _node(self, node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, bool)):
            return int(node.value)
        if isinstance(node, ast.Name):
            return self.name(node.id)
        if isinstance(node, ast.UnaryOp):
            value = self._node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.Invert):
                return ~value
        if isinstance(node, ast.BinOp):
            left, right = self._node(node.left), self._node(node.right)
            operations = {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.Div: lambda: left // right,
                ast.FloorDiv: lambda: left // right,
                ast.Mod: lambda: left % right,
                ast.LShift: lambda: left << right,
                ast.RShift: lambda: left >> right,
                ast.BitOr: lambda: left | right,
                ast.BitAnd: lambda: left & right,
                ast.BitXor: lambda: left ^ right,
            }
            for kind, operation in operations.items():
                if isinstance(node.op, kind):
                    return operation()
        raise ValueError(ast.dump(node))


def _definition_details(repo_root: Path, names: set[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    constants_root = repo_root / "include" / "constants"
    for path in constants_root.rglob("*.h"):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            match = re.match(r"\s*#\s*define\s+([A-Za-z_]\w*)\b(.*)", line)
            if match and match.group(1) in names and match.group(1) not in result:
                comment = ""
                if "//" in line:
                    comment = line.split("//", 1)[1].strip()
                result[match.group(1)] = {
                    "file": path.relative_to(repo_root).as_posix(),
                    "line": line_number,
                    "comment": comment,
                }
    return result


def _parse_map_enum(repo_root: Path) -> dict[str, int]:
    text = (repo_root / "include" / "constants" / "map_groups.h").read_text(encoding="utf-8")
    maps: dict[str, int] = {}
    for name, number, group in re.findall(
        r"\b(MAP_[A-Z0-9_]+)\s*=\s*\(\s*(\d+)\s*\|\s*\(\s*(\d+)\s*<<\s*8\s*\)\s*\)",
        text,
    ):
        maps[name] = int(number) | (int(group) << 8)
    return maps


def generate_symbols(repo_root: Path, schema: dict[str, Any]) -> dict[str, Any]:
    probe = windows_path_to_wsl(TOOL_DIR / "bpe_constants_probe.c")
    command = _compiler_prefix(repo_root) + ["-dM", "-E", probe]
    output = subprocess.check_output(command, cwd=repo_root, text=True, errors="replace")
    macros: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"#define\s+([A-Za-z_]\w*)\s+(.*)", line)
        if match and "(" not in match.group(1):
            macros[match.group(1)] = match.group(2).strip()
    evaluator = MacroEvaluator(macros)

    groups: dict[str, dict[str, int]] = {"flags": {}, "vars": {}, "game_stats": {}}
    prefixes = (("FLAG_", "flags"), ("VAR_", "vars"), ("GAME_STAT_", "game_stats"))
    for name in sorted(macros):
        for prefix, group in prefixes:
            if not name.startswith(prefix) or name.endswith("_FRLG"):
                continue
            try:
                value = evaluator.name(name)
            except (SyntaxError, ValueError, ZeroDivisionError):
                continue
            if group == "flags" and not (0 < value < 0x4000):
                continue
            if group == "vars" and not (0x4000 <= value < 0x8000):
                continue
            groups[group][name] = value
            break

    groups["maps"] = _parse_map_enum(repo_root)
    all_names = {name for values in groups.values() for name in values}
    definitions = _definition_details(repo_root, all_names)
    expected_definition_files = {
        "flags": "include/constants/flags.h",
        "vars": "include/constants/vars.h",
        "game_stats": "include/constants/game_stat.h",
    }
    for group, expected_file in expected_definition_files.items():
        groups[group] = {
            name: value
            for name, value in groups[group].items()
            if definitions.get(name, {}).get("file") == expected_file
        }
    retained_names = {name for values in groups.values() for name in values}
    definitions = {name: value for name, value in definitions.items() if name in retained_names}
    return {"format": 1, **groups, "definitions": definitions}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--object", type=Path, help="Use an already-compiled layout probe object")
    parser.add_argument("--output", type=Path, default=TOOL_DIR / "bpe_layout.json")
    parser.add_argument("--symbols-output", type=Path, default=TOOL_DIR / "bpe_symbols.json")
    parser.add_argument("--source-commit", help="Recorded source commit when --repo-root is an exported tree")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    object_path = (args.object or TOOL_DIR / ".bpe_layout_probe.o").resolve()
    if args.object is None:
        compile_probe(repo_root, object_path)

    result = extract_schema(object_path)
    source_commit = args.source_commit or subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    result["source"] = {
        "git_commit": source_commit,
        "game_version": "EMERALD",
        "release_build": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + os.linesep, encoding="utf-8")
    symbols_output = args.symbols_output
    symbols_output.parent.mkdir(parents=True, exist_ok=True)
    symbols_output.write_text(
        json.dumps(generate_symbols(repo_root, result), indent=2) + os.linesep,
        encoding="utf-8",
    )
    print(f"Wrote {args.output} from {object_path}")
    print(f"Wrote {symbols_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
