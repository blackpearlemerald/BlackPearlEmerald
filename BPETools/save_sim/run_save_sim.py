"""Build and run the BPE save engine power-cut simulator.

The simulator compiles src/save_engine.c for the host with AddressSanitizer
and UndefinedBehaviorSanitizer, then runs many seeds in parallel.

    python BPETools/save_sim/run_save_sim.py                 # quick run
    python BPETools/save_sim/run_save_sim.py --seeds 96 --sessions 400

On Windows the build and run happen inside WSL.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BUILD_DIR = REPO / "build" / "save_sim"


def to_wsl(path: pathlib.Path) -> str:
    drive = path.drive.rstrip(":").lower()
    rest = path.as_posix()[len(path.drive):]
    return f"/mnt/{drive}{rest}"


def use_wsl() -> bool:
    return os.name == "nt"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    if use_wsl():
        cmd = ["wsl", "-d", os.environ.get("BPE_WSL_DISTRO", "Ubuntu"), "--cd", to_wsl(REPO), "--exec"] + cmd
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


def build() -> str:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    exe = BUILD_DIR / "save_sim"
    exe_arg = to_wsl(exe) if use_wsl() else str(exe)
    cmd = [
        "cc", "-O2", "-g", "-std=gnu11", "-Wall", "-Wextra", "-Wno-unused-parameter",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
        "-DSAVE_ENGINE_HOST", "-iquote", "include",
        "-o", exe_arg,
        "BPETools/save_sim/save_sim.c", "src/save_engine.c",
    ]
    result = run(cmd)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit("save simulator build failed")
    if result.stderr.strip():
        sys.stderr.write(result.stderr)
    return exe_arg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--sessions", type=int, default=60)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()

    exe = build()
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    totals: dict[str, int] = {}
    failed = False

    def one(seed: int) -> subprocess.CompletedProcess:
        return run([exe, str(seed), str(args.sessions)])

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for seed, result in zip(seeds, pool.map(one, seeds)):
            line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            if result.returncode != 0:
                failed = True
                sys.stderr.write(f"seed {seed} FAILED (exit {result.returncode})\n{result.stdout}{result.stderr}\n")
            for key, value in re.findall(r"(\w+)=(\d+)", line):
                totals[key] = totals.get(key, 0) + int(value)

    print(" ".join(f"{k}={v}" for k, v in totals.items()))
    if failed or totals.get("failures", 0):
        print("save simulator: FAILED")
        return 1
    print("save simulator: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
