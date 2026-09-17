"""Refreshes the packed PC record test vectors from the game's C code.

Runs the "Packed format vectors" test in test/save.c through `make check`
(inside WSL on Windows) and writes BPETools/tests/fixtures/packed_box_mon_vectors.json.
Each vector is an 80-byte struct BoxPokemon exactly as the game stores it
(encrypted) and the 60-byte record that PackBoxMon makes from it.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = REPO / "BPETools" / "tests" / "fixtures" / "packed_box_mon_vectors.json"


def to_wsl(path: pathlib.Path) -> str:
    drive = path.drive.rstrip(":").lower()
    return f"/mnt/{drive}{path.as_posix()[len(path.drive):]}"


def main() -> int:
    command = ["make", "check", f"-j{os.cpu_count() or 4}", "TESTS=Packed format vectors"]
    if os.name == "nt":
        command = ["wsl", "-d", os.environ.get("BPE_WSL_DISTRO", "Ubuntu"), "--cd", to_wsl(REPO), "--exec"] + command
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, errors="replace")
    chunks: dict[int, dict[int, str]] = {}
    for number, part, text in re.findall(r"VECTOR (\d+) (\d+) ([0-9A-F]{40})", result.stdout):
        chunks.setdefault(int(number), {})[int(part)] = text
    vectors = []
    for number in sorted(chunks):
        parts = chunks[number]
        if sorted(parts) != list(range(7)):
            raise SystemExit(f"vector {number} is incomplete")
        joined = "".join(parts[i] for i in range(7))
        vectors.append((joined[:160], joined[160:]))
    if len(vectors) < 16:
        print(result.stdout[-4000:])
        print(result.stderr[-4000:])
        raise SystemExit("no vectors found in the test output")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "description": "struct BoxPokemon (80 bytes, encrypted) and PackBoxMon output (60 bytes), from test/save.c",
        "vectors": [{"boxPokemon": box, "packed": packed} for box, packed in vectors],
    }
    OUTPUT.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(vectors)} vectors to {OUTPUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
