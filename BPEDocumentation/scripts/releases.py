"""Validate patch packages, freeze release documentation, and assemble GitHub Pages."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "BPETools"))
from release_lib import VERSION_KEY, describe, git, inspect_ups, json_bytes, label, read_package, sha256, version, write_zip
from prepare_release import export_source

SITE = ROOT / "BPEDocumentation/site"
REPOSITORY = "blackpearlemerald/BlackPearlEmerald"
PAGES_LIMIT = 1_000_000_000


def gh(*args):
    return subprocess.check_output(["gh", *args], cwd=ROOT).decode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def candidates():
    result = {}
    for path in sorted((ROOT / "releases/packages").glob("*.zip")):
        meta, patch = read_package(path)
        result[meta["version"]] = (meta, patch)
    for path in sorted((ROOT / "releases/legacy").glob("*.json")):
        meta = read_json(path)
        release = version(meta["version"])
        if release in result:
            raise ValueError(f"Duplicate release: {release}")
        # Legacy imports are explicitly reviewed, tracked records, not package data.
        archive_path = (ROOT / meta["legacyArchive"]).resolve()
        if not archive_path.is_relative_to(ROOT):
            raise ValueError("Legacy archive must be in this repository.")
        if sha256(archive_path.read_bytes()) != meta["legacyArchiveSha256"]:
            raise ValueError("Legacy archive checksum mismatch.")
        with zipfile.ZipFile(archive_path) as archive:
            patch = archive.read(meta["patch"]["file"])
        if dict(describe(patch), file=meta["patch"]["file"], format="ups") != meta["patch"]:
            raise ValueError("Legacy patch checksum mismatch.")
        info = inspect_ups(patch)
        for field, key in (("baseRom", "input"), ("outputRom", "output")):
            if any(meta[field][k] != v for k, v in info[key].items()):
                raise ValueError("Legacy ROM metadata mismatch.")
        git("cat-file", "-e", meta["sourceCommit"] + "^{commit}")
        result[release] = meta, patch
    return result


def copy_frontend(destination):
    def ignored(folder, names):
        relative = Path(folder).relative_to(SITE).as_posix()
        skip = {"node_modules", ".git", "__pycache__", "package-lock.json", "package.json"}
        if relative == ".":
            skip |= {"data", "img", "sprites", "patches", "release.json", "versions.json"}
        if relative == "js":
            skip.add("data")
        if relative == "calc/data":
            skip.add("bpe_calc_data.json")
        if relative == "calc/img":
            skip.add("newhd")
        return set(names) & skip
    shutil.copytree(SITE, destination, ignore=ignored)


def validate_snapshot(path, shared=False):
    path = Path(path)
    required = ["index.html", "pokedex.html", "items.html", "trainers.html", "patcher.html", "search.html",
                "calc/index.html", "js/nav.js", "js/release-context.js", "css/header.css",
                "data/pokedex_index.json", "data/items_index.json", "data/moves.json", "data/abilities.json",
                "js/data/world.json", "js/data/trainers.json", "calc/data/bpe_calc_data.json"]
    for name in required:
        if not (path / name).is_file():
            raise ValueError(f"Incomplete documentation: {name}")
    pokedex = read_json(path / "data/pokedex_index.json")
    items = read_json(path / "data/items_index.json")
    world = read_json(path / "js/data/world.json")
    if len(pokedex) < 300 or len(items) < 100 or len(world.get("maps", [])) < 100:
        raise ValueError("Documentation export is unexpectedly incomplete.")
    for species in pokedex:
        if not (path / "data/species" / (species + ".json")).is_file():
            raise ValueError(f"Missing species detail: {species}")
    for item in items:
        if not (path / "data/items" / (item + ".json")).is_file():
            raise ValueError(f"Missing item detail: {item}")
    for entry in world["maps"]:
        # The renderer writes one image for every placed map layout.
        image = entry.get("img")
        if image and not shared and not (path / "img/maps" / image).is_file():
            raise ValueError(f"Missing map image: {image}")
    for file in path.rglob("*"):
        if file.is_file() and file.suffix.lower() in {".gba", ".elf", ".sav", ".sa1"}:
            raise ValueError(f"ROM/save files cannot be published: {file.name}")
    if (path / "release.json").exists():
        release = read_json(path / "release.json")
        patch = path / release["patch"]["url"]
        if not patch.is_file() or sha256(patch.read_bytes()) != release["patch"]["archiveSha256"]:
            raise ValueError("Hosted patch checksum mismatch.")


def freeze_snapshot(path, archive):
    files = {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    files["checksums.json"] = json_bytes({name: sha256(data) for name, data in files.items()})
    write_zip(archive, files)


def restore_snapshot(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        names = [e.filename for e in entries]
        if len(names) != len(set(names)) or "checksums.json" not in names or sum(e.file_size for e in entries) > PAGES_LIMIT:
            raise ValueError("Invalid documentation archive.")
        checks = json.loads(bundle.read("checksums.json"))
        if set(names) != set(checks) | {"checksums.json"}:
            raise ValueError("Documentation archive inventory mismatch.")
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in entry.filename or ":" in entry.filename or entry.is_dir():
                raise ValueError("Unsafe documentation archive path.")
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symlinks cannot be published.")
            data = bundle.read(entry)
            if entry.filename != "checksums.json" and sha256(data) != checks[entry.filename]:
                raise ValueError(f"Documentation checksum mismatch: {name}")
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    validate_snapshot(destination)
    return read_json(destination / "release.json")


def build_snapshot(metadata, patch, destination, work, revision, exporter):
    source = work / (metadata["sourceCommit"] + "-" + metadata["version"])
    export_source(metadata["sourceCommit"], source)
    copy_frontend(destination)
    command = [sys.executable, str(Path(__file__).with_name("build_all.py")), "--source-root", str(source), "--output-dir", str(destination)]
    subprocess.run(command, check=True, env=dict(os.environ, PYTHONUTF8="1"))
    release = {"schemaVersion": 1, "version": metadata["version"], "label": label(metadata["version"]),
               "sourceCommit": metadata["sourceCommit"], "exporterCommit": exporter, "documentationRevision": revision,
               "baseRom": metadata["baseRom"], "outputRom": metadata["outputRom"], "patch": dict(metadata["patch"])}
    patch_url = "patches/BlackPearlEmerald_v" + metadata["version"] + ".zip"
    write_zip(destination / patch_url, {metadata["patch"]["file"]: patch})
    release["patch"].update(url=patch_url, archiveSha256=sha256((destination / patch_url).read_bytes()))
    write_json(destination / "release.json", release)
    write_json(destination / "package.json", metadata)
    validate_snapshot(destination)
    return release


def download_archives(archive_dir):
    pages = json.loads(gh("api", f"repos/{REPOSITORY}/releases?per_page=100", "--paginate", "--slurp"))
    for record in [item for page in pages for item in page]:
        if not record["tag_name"].startswith("bpe/v"):
            continue
        release = version(record["tag_name"][5:])
        target = archive_dir / release
        target.mkdir(parents=True, exist_ok=True)
        assets = [a for a in record["assets"] if re.fullmatch(r"documentation-r[1-9]\d*\.zip", a["name"])]
        if not assets and not record["draft"]:
            raise ValueError(f"Published release {release} has no documentation archive; refusing to erase history.")
        for asset in assets:
            path = target / asset["name"]
            if not path.exists():
                subprocess.run(["gh", "release", "download", record["tag_name"], "--repo", REPOSITORY, "--pattern", asset["name"], "--dir", str(target)], check=True)


def upload_archive(release, archive, work):
    tag = "bpe/v" + release["version"]
    found = subprocess.run(["gh", "release", "view", tag, "--repo", REPOSITORY, "--json", "tagName,assets"], capture_output=True)
    if found.returncode:
        notes = work / "release-notes.md"
        notes.write_text(f"BPE Emerald {release['label']}. Documentation and patch were built from source `{release['sourceCommit']}`. Supply your own clean US Emerald ROM to the website patcher.\n", encoding="utf-8")
        subprocess.run(["gh", "release", "create", tag, "--repo", REPOSITORY, "--target", release["sourceCommit"], "--draft", "--title", "BPE Emerald " + release["label"], "--notes-file", str(notes)], check=True)
    else:
        ref = json.loads(gh("api", f"repos/{REPOSITORY}/git/ref/tags/{tag}"))["object"]
        while ref["type"] == "tag":
            ref = json.loads(gh("api", f"repos/{REPOSITORY}/git/tags/{ref['sha']}"))["object"]
        if ref["sha"] != release["sourceCommit"]:
            raise ValueError(f"Release tag {tag} points to a different source commit.")
    assets = json.loads(found.stdout)["assets"] if found.returncode == 0 else []
    if not any(asset["name"] == archive.name for asset in assets):
        subprocess.run(["gh", "release", "upload", tag, str(archive), "--repo", REPOSITORY], check=True)
    subprocess.run(["gh", "release", "edit", tag, "--repo", REPOSITORY, "--draft=false", "--prerelease=" + str("-" in release["version"]).lower(), "--latest=false"], check=True)


def write_entry_pages(output, catalog):
    write_json(output / "versions.json", catalog)
    for relative in [p.name for p in SITE.glob("*.html")] + ["calc/index.html"]:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        prefix = "../" if relative.startswith("calc/") else ""
        links = ''.join(f'<li><a href="{prefix}{html.escape(r["path"])}{relative}">{html.escape(r["label"])}</a></li>' for r in catalog["releases"])
        body = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BPE Emerald releases</title>'
        body += '<body style="background:#101c27;color:#eaf8f0;font:18px system-ui;padding:32px"><h1>Choose your game version</h1><ul>' + links + '</ul>'
        body += '<script>fetch(' + json.dumps(prefix + 'versions.json') + ',{cache:"no-cache"}).then(function(r){if(!r.ok)throw Error();return r.json()}).then(function(c){var base=new URL(' + json.dumps(prefix or './') + ',location.href),saved;try{saved=localStorage.getItem("bpe:"+base.pathname+":selected-release")}catch(e){}var r=c.releases.find(function(x){return x.version===saved})||c.releases.find(function(x){return x.version===c.latest});if(r){var u=new URL(r.path+' + json.dumps(relative) + ',base);u.search=location.search;u.hash=location.hash;location.replace(u.href)}}).catch(function(){});</script></body></html>'
        target.write_text(body, encoding="utf-8")
    (output / ".nojekyll").touch()
    (output / "404.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Release not found</title><h1>This release or page is unavailable</h1><p>Check the version in your link. No other game version has been substituted.</p></html>', encoding="utf-8")


def share_assets(output):
    """Share identical asset directories while retaining their internal URLs.

    Game data and executable calculator code remain in each snapshot. Asset
    directories have content-addressed URLs and are never updated in place.
    """
    output = output.resolve()
    for snapshot in (output / "versions").iterdir():
        mappings = []
        for group in ("img/maps", "img/pokemon", "img/sprites", "sprites/pokemon", "sprites/icons", "sprites/items", "calc/img"):
            source = (snapshot / group).resolve()
            if not source.is_dir():
                continue
            if not source.is_relative_to(snapshot.resolve()) or not snapshot.resolve().is_relative_to(output):
                raise ValueError("Asset source escaped the generated website directory.")
            digest = hashlib.sha256()
            for file in sorted(source.rglob("*")):
                if file.is_file():
                    digest.update(file.relative_to(source).as_posix().encode() + b"\0")
                    digest.update(hashlib.sha256(file.read_bytes()).digest())
            destination = output / "assets" / digest.hexdigest()
            if not destination.exists():
                shutil.copytree(source, destination)
            mappings.append((source, destination))
            # Both absolute paths have been verified inside this generated output.
            shutil.rmtree(source)
        for file in snapshot.rglob("*"):
            if not file.is_file() or file.suffix not in {".html", ".js", ".css", ".json"}:
                continue
            if file.name in {"checksums.json", "package.json", "release.json"}:
                continue
            rel = file.relative_to(snapshot).as_posix()
            if file.suffix in {".html", ".css"}:
                base = file.parent
            else:
                base = snapshot / "calc" if rel.startswith("calc/") else snapshot
            text = file.read_text(encoding="utf-8")
            original = text
            for source, destination in mappings:
                old = os.path.relpath(source, base).replace(os.sep, "/") + "/"
                new = os.path.relpath(destination, base).replace(os.sep, "/") + "/"
                # Paths occur as JSON values, HTML attributes, CSS URLs, and JS
                # string prefixes. Dynamic filename suffixes keep working.
                pattern = r"(?P<quote>[\"'`(])(?:\./)?" + re.escape(old)
                text = re.sub(pattern, lambda m: m["quote"] + new, text)
            if text != original:
                file.write_text(text, encoding="utf-8", newline="\n")
        (snapshot / "checksums.json").unlink(missing_ok=True)
        validate_snapshot(snapshot, shared=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".release-work/site")
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".release-work/publish")
    parser.add_argument("--archive-dir", type=Path, default=ROOT / ".release-work/archives")
    parser.add_argument("--github", action="store_true", help="Restore/archive GitHub Releases. Only use from trusted main publication.")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--correct-version", type=version)
    parser.add_argument("--docs-revision", type=int, default=1)
    args = parser.parse_args()
    available = candidates()
    if args.validate_only:
        print(f"Validated {len(available)} release packages/imports.")
        return
    if args.output.exists() or args.work_dir.exists():
        raise ValueError("Output/work directory already exists. Choose fresh paths; existing releases are never deleted.")
    args.output.mkdir(parents=True)
    args.work_dir.mkdir(parents=True)
    args.archive_dir.mkdir(parents=True, exist_ok=True)
    if args.docs_revision < 1 or (args.correct_version and args.docs_revision < 2):
        raise ValueError("Documentation corrections require an explicit revision of 2 or higher.")
    if args.github:
        if os.environ.get("GITHUB_REPOSITORY", REPOSITORY).lower() != REPOSITORY.lower():
            raise ValueError("Publication is restricted to the BPE repository.")
        if not os.environ.get("GITHUB_ACTIONS") and json.loads(gh("api", "user"))["login"] != "blackpearlemerald":
            raise ValueError("Use the blackpearlemerald GitHub account for publication.")
        download_archives(args.archive_dir)
    exporter = git("rev-parse", "HEAD")
    versions = set(available) | {p.name for p in args.archive_dir.iterdir() if p.is_dir()}
    if not versions:
        raise ValueError("No verified release packages are available. Existing site must remain deployed.")
    if args.correct_version and args.correct_version not in available:
        raise ValueError("The selected correction needs its original package/import record.")
    releases, uploads = [], []
    for release_id in sorted(versions, key=VERSION_KEY, reverse=True):
        directory = args.archive_dir / release_id
        directory.mkdir(exist_ok=True)
        archives = sorted(directory.glob("documentation-r*.zip"), key=lambda p: int(re.search(r"-r(\d+)", p.name)[1]))
        latest = archives[-1] if archives else None
        dest = args.output / "versions" / release_id
        previous = None
        if latest:
            previous = restore_snapshot(latest, args.work_dir / ("previous-" + release_id))
            if release_id in available:
                metadata, _ = available[release_id]
                if previous["sourceCommit"] != metadata["sourceCommit"] or previous["patch"]["sha256"] != metadata["patch"]["sha256"]:
                    raise ValueError(f"Release {release_id} is immutable; choose a new version.")
        revision = args.docs_revision if args.correct_version == release_id else 1
        requested = directory / f"documentation-r{revision}.zip"
        correction = args.correct_version == release_id
        if correction and previous and revision < previous["documentationRevision"]:
            raise ValueError("Documentation revision cannot go backwards.")
        if previous and (not correction or requested.exists()):
            chosen = requested if correction else latest
            release = restore_snapshot(chosen, dest)
            if correction and release["exporterCommit"] != exporter:
                raise ValueError("That documentation revision already exists. Choose a new revision.")
        else:
            if release_id not in available:
                raise ValueError(f"No source package for {release_id}")
            metadata, patch = available[release_id]
            release = build_snapshot(metadata, patch, dest, args.work_dir, revision, exporter)
            freeze_snapshot(dest, requested)
        uploads.append((release, requested if correction or not previous else latest))
        releases.append(dict(version=release_id, label=release["label"], path=f"versions/{release_id}/", documentationRevision=release["documentationRevision"]))
    catalog = {"schemaVersion": 1, "latest": releases[0]["version"], "releases": releases}
    share_assets(args.output)
    write_entry_pages(args.output, catalog)
    total = sum(p.stat().st_size for p in args.output.rglob("*") if p.is_file())
    if total >= PAGES_LIMIT:
        raise ValueError("Site exceeds GitHub Pages capacity. Expand archive hosting before publishing; no history has been deleted.")
    if total >= 700 * 1024 * 1024:
        print("::warning::Site is above 700 MiB. Plan expanded archive hosting before reaching the Pages limit.")
    # Upload only after every version and the complete site passed validation.
    # Reused archives also pass here to finish a previous interrupted draft.
    if args.github:
        for release, archive in uploads:
            upload_archive(release, archive, args.work_dir)
    print(f"Prepared {len(releases)} releases, {total / 1024**2:.1f} MiB: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        raise SystemExit(f"Publication stopped: {error}")
