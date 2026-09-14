# Publish a BPE release

Choose a version, build locally, then upload the generated patch package. The
website uses that version for its maps, Pokémon, items, trainers, guides,
calculator and patcher. New visitors see the newest release, including Beta;
returning visitors keep their selection. A version in a link takes precedence.

## Prepare the game on your PC

Use the `blackpearlemerald` GitHub account and repository-local author identity.
Install the normal release-build prerequisites from `INSTALL.md`. On Windows,
the helper uses WSL Ubuntu, `make` and `arm-none-eabi-gcc`; the Python helper
itself requires Python 3.12 or newer. The hosted documentation build needs no ROM.

1. Choose the next unused version:

   ```powershell
   python BPETools/prepare_release.py set-version 2.0.1-beta
   ```

2. Commit the game changes and `BPE_VERSION.json`. This one setting generates
   the title-screen label and the package version. Ordinary development commits
   do not need public version bumps and do not change the published website.

3. Build and verify from the clean committed source:

   ```powershell
   python BPETools/prepare_release.py build --base-rom "E:\Projects\OfficialBPEemerald\BPETools\Pokemon Emerald.gba"
   ```

   The base must be clean US Emerald: 16 MiB, CRC32 `1F1C08FB`. The helper exports
   the exact source commit into `.release-work/local/`, builds the game, checks
   its embedded version, creates the UPS patch and applies it locally to verify
   a byte-for-byte match. Build logs and both ROMs stay local. For another build
   of the same commit, supply a fresh `--work-dir` and `--output-dir`.

4. Play-test the resulting game in `.release-work/local/<source commit>/source/`.
   Push its source commit before uploading the package. Do not rename an old
   package to invent a new version; rebuild after changing the version.

Optionally save the base path in ignored `BPETools/release.local.json` as
`{"baseRom":"E:/Projects/OfficialBPEemerald/BPETools/Pokemon Emerald.gba"}`.
Then the build command can omit `--base-rom`.

## Upload the package

The generated `.release-work/packages/BlackPearlEmerald_v<version>.zip` contains
exactly one UPS patch and `release.json`. **Never upload a `.gba`, save file,
build directory or original source archive containing ROMs.**

Copy that ZIP into `releases/packages/`, commit and push to `main`, or use
GitHub's file-upload interface in that directory. Larger ZIPs must use Git push
if the browser upload size limit rejects them. The source commit recorded in
the package must already be part of `main` when publication runs.

The **BPE Documentation** Action validates the filename, source version, patch
and checksums; exports data from the package's recorded source; archives a
complete snapshot under GitHub Release `bpe/v<version>`; and deploys all versions
together. Check that Action's successful deployment before announcing the release.
The workflow's repository token performs automated publication; local GitHub
operations must use `blackpearlemerald`.

The prominent selector changes every page and the default patch in one action.
Links such as `versions/1.0.1/patcher.html` remain pinned to their version.
Calculator teams and battle state are stored separately for each version.

## Repeat runs, corrections and recovery

- Published patch bytes, source commits and version identifiers are immutable.
  Uploading different content under an existing version fails. Use a new game
  version for game changes.
- A failed run leaves the existing Pages deployment in place. Rerun the failed
  Action after fixing the cause; the same package can resume publication.
- Existing snapshots are restored from `documentation-rN.zip` release assets,
  including on a frontend-only change. They are not silently regenerated from
  today's game source. Do not delete those assets or their `bpe/v...` tags.
- For a documentation-only fix, commit the exporter/frontend correction and
  manually run **BPE Documentation** on `main` with `correct_version` set to the
  affected game version and `docs_revision` set to its next revision (2, 3, ...).
  It rebuilds against the same game source and retains the original patch and
  all previous archive revisions. Revisions cannot go backwards or be replaced.
- The pipeline shares identical image directories and checks total Pages size.
  It warns above 700 MiB and stops before 1 GB. Expand hosting before capacity
  is exhausted; do not remove supported history to make room.

## Local checks

```powershell
python -m unittest discover -s BPETools/tests -v
python BPEDocumentation/scripts/releases.py --validate-only
python -m pip install -r BPEDocumentation/requirements.txt
python BPEDocumentation/scripts/releases.py --output .release-work/preview --work-dir .release-work/preview-build
python -m http.server 8000 --directory .release-work/preview
```

Use fresh output and work directories on subsequent runs. `--archive-dir`
selects persistent local snapshots; omit `--github` for a local-only build.
Guide notes live in `BPEDocumentation/content/guides.json` at each game's pinned
source commit. Existing calculator mechanics remain those of the bundled engine;
versioning preserves its code and inputs, not a promise of perfect game parity.

## Historical 1.0.1

`releases/legacy/1.0.1.json` records the official patch and the exact historical
source commit `ed784bef37b5d37431867c57fb03c958913398a0`, retained by
`bpe/source/1.0.1`. All 18,718 tracked game inputs matched the original local
source archive. Applying the official patch to the verified base reproduced the
archive's game byte for byte (output CRC32 `033F628D`). The archived ROM itself
is never published. Older C data formats are handled by the exporters; newer
handwritten guide notes are not applied to this historical release.
