"""Build and verify a release locally, then prepare one uploadable patch ZIP.

Set the version, commit the source, then run:
  python BPETools/prepare_release.py build --base-rom "path/to/Emerald.gba"
On Windows the isolated build runs in WSL Ubuntu. ROMs never leave this PC.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import tarfile
from pathlib import Path
from release_lib import (ROOT, BASE_SIZE, BASE_CRC, apply_ups, create_ups,
                         describe, git, json_bytes, label, read_package, version, write_zip)


def export_source(commit, destination, root=ROOT):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError(f"Build directory already exists: {destination}. Use a new --work-dir.")
    destination.mkdir(parents=True)
    archive = destination.parent / (destination.name + ".tar")
    try:
        subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), commit], cwd=root, check=True)
        with tarfile.open(archive) as source:
            source.extractall(destination, filter="data")
    finally:
        archive.unlink(missing_ok=True)
    (destination / ".histignore").touch()


def build(args):
    if os.environ.get("GITHUB_ACTIONS"):
        raise ValueError("ROM builds and patch creation must run on your local PC.")
    base_path = args.base_rom
    if base_path is None:
        config = ROOT / "BPETools/release.local.json"
        if config.exists():
            base_path = Path(json.loads(config.read_text())["baseRom"])
    if base_path is None:
        raise ValueError("Supply --base-rom with the path to your clean US Emerald ROM.")
    base = Path(base_path).read_bytes()
    base_info = describe(base)
    if base_info["size"] != BASE_SIZE or base_info["crc32"] != BASE_CRC:
        raise ValueError(f"Expected clean 16 MiB US Emerald, CRC32 {BASE_CRC}; got {base_info['crc32']}.")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Commit or set aside source changes before building a release.")
    commit = git("rev-parse", "HEAD")
    release = version(json.loads(git("show", f"{commit}:BPE_VERSION.json"))["version"])
    work = (args.work_dir or ROOT / ".release-work/local" / commit).resolve()
    source = work / "source"
    export_source(commit, source)
    if os.name == "nt":
        linux_path = subprocess.check_output(["wsl", "-d", args.distro, "--", "wslpath", "-a", str(source)]).decode().strip()
        prefix = ["wsl", "-d", args.distro, "--cd", linux_path, "--"]
    else:
        prefix = []
    compiler = subprocess.check_output(prefix + ["arm-none-eabi-gcc", "--version"], cwd=source).decode().splitlines()[0]
    with (work / "build.log").open("wb") as log:
        print(f"Building BPE {label(release)} locally. Log: {work / 'build.log'}", flush=True)
        subprocess.run(prefix + ["make", "release", f"-j{args.jobs}"], cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
    target = (source / "pokeemerald-release.gba").read_bytes()
    marker = ("BPE_RELEASE:" + release + "\0").encode("ascii")
    if marker not in target:
        raise ValueError("The compiled game does not contain the expected release version.")
    if git("rev-parse", "HEAD") != commit or git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Source changed during the build; commit changes and rebuild.")
    patch = create_ups(base, target)
    if apply_ups(base, patch) != target:
        raise ValueError("Local patch round-trip did not reproduce the built game.")
    patch_name = f"BlackPearlEmerald_v{release}.ups"
    metadata = {"schemaVersion": 1, "version": release, "sourceCommit": commit,
                "patch": dict(describe(patch), file=patch_name, format="ups"),
                "baseRom": base_info, "outputRom": describe(target),
                "build": {"target": "release", "compiler": compiler, "roundTripVerified": True}}
    output = args.output_dir / f"BlackPearlEmerald_v{release}.zip"
    if output.exists():
        raise ValueError(f"Refusing to replace an existing release package: {output}")
    write_zip(output, {patch_name: patch, "release.json": json_bytes(metadata)})
    read_package(output)
    print(f"Verified package: {output}\nSource commit: {commit}\nUpload the ZIP under releases/packages/ after pushing this source commit.\nThe original and compiled ROMs remain local.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    choose = commands.add_parser("set-version", help="Choose the title-screen and next package version, then commit the source.")
    choose.add_argument("version", type=version)
    run = commands.add_parser("build", help="Build locally from committed source and verify the patch.")
    run.add_argument("--base-rom", type=Path)
    run.add_argument("--distro", default="Ubuntu")
    run.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 2))
    run.add_argument("--work-dir", type=Path)
    run.add_argument("--output-dir", type=Path, default=ROOT / ".release-work/packages")
    check = commands.add_parser("validate", help="Validate an upload package without accessing a ROM.")
    check.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "set-version":
            (ROOT / "BPE_VERSION.json").write_bytes(json_bytes({"version": args.version}))
            print(f"Version set to {label(args.version)}. Commit the source, then run build.")
        elif args.command == "build":
            build(args)
        else:
            metadata, _ = read_package(args.package)
            print(f"Validated {metadata['version']} from {metadata['sourceCommit']}")
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release stopped: {error}\n")


if __name__ == "__main__":
    main()
