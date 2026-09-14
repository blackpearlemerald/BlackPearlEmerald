# BPE patch-package releases and versioned documentation

Status: implemented and deployed. Version `1.0.1` (documentation revision 2)
and `2.0.0-beta` (revision 1) are live, with Beta selected for new visitors.
Local build/patch verification, maintainer mGBA testing, hosted publication,
archive recovery and a documentation-only correction passed. See
[RELEASING.md](RELEASING.md) for the operating procedure and rollout checks.
This document preserves the accepted design and acceptance criteria.

## Outcome and maintainer workflow

One public BPE version selects the matching game patch and all documentation.
The maintainer builds and tests locally, then uploads one patch package to
publish a release. Ordinary development commits do not publish game releases
or advance public documentation to unreleased game data.

1. Choose a version, for example `2.0.0-beta` (displayed as **2.0.0 Beta**).
2. Update the shared BPE version configuration and commit the game source.
3. Manually run the local release helper against that clean commit. It builds
   the release game, creates the patch using the local Emerald ROM, tests the
   patch, and prepares one ZIP with release metadata.
4. Make the source commit available in this repository. Add the ZIP to
   `releases/packages/` and push it, or upload it through GitHub's repository
   file interface. Publication starts when the package commit reaches `main`.
5. GitHub validates the package, exports documentation from its recorded
   source commit, assembles the release history, and publishes the site.

The maintainer supplies the version once. The local tooling generates the
title label, filenames, and metadata from it. The package upload can be a later
commit than the source build. No manually maintained source hash is required.

The base Emerald ROM and compiled game stay on the maintainer's PC. This design
does not require a self-hosted Actions runner, remote ROM storage, or a GitHub
game-build job for publication. Existing unrelated CI can be reviewed separately;
it must never upload original or compiled ROMs.

## Original repository findings (before implementation)

- `site/js/patcher.js` and `site/patcher.html` hard-code 1.0.1. Its official UPS
  patch is in `site/patches/BlackPearlEmerald_v1.0.1.zip`.
- `scripts/build_all.py` already generates map, trainer, Pokemon, item, and
  damage-calculator data. Some modules hard-code their own source/output roots.
- `.github/workflows/docs.yml` deploys committed `BPEDocumentation/site` files
  on `main`; it does not regenerate them after game changes.
- `.github/workflows/build.yml` watches pushes to `master` and `upcoming`,
  unlike the website workflow. Its job named `release` compiles a release build;
  it is not this proposed patch-package publication process.
- The title screen uses image assets. There is no verified shared BPE release
  value supplying the intended `2.0.0 Beta` label.
- Historical commit `3adfc461062b48b6cd0218f05d07baee32872572` is named
  `1.0.1 OFFICIAL`. The original source archive also exists locally at
  `E:\Projects\PokemonBlackPearlEmerald\pokeemerald-expansion_1.0.1_SOURCECODE.zip`.
  Neither has yet been proven an exact match to the distributed patch.
- The site currently occupies approximately 51 MiB, including about 19.5 MiB
  for the existing patch ZIP.

## 1. Shared game version and local packaging

Introduce a small machine-readable BPE release configuration, separate from
upstream `GAME_VERSION`. Use a validated semantic-version identifier such as
`2.0.0-beta`; derive the display label **2.0.0 Beta**. A later `2.0.0` stable
release has a distinct identifier and cannot replace the Beta patch.

Generate the title-screen version through the build system, using a text label
or generated title asset. Record the same version in the compiled game in a
machine-readable form so the local helper can verify it. Ensure version changes
invalidate the relevant incremental-build outputs.

The local helper must:

- Require a committed, clean source checkout before building; ignored local
  build outputs and the user's base-ROM path must not become release inputs.
- Capture the full game source commit, version, release build settings, and
  toolchain identity before building. Fail if tracked source changes during
  packaging. Include the shared version configuration in that source commit.
- Build the normal release configuration, verify its embedded BPE version,
  create a UPS patch against the configured local clean Emerald ROM, then
  apply it locally and compare the result with the built game byte for byte.
- Validate the base game against the documented US Emerald input checksum
  (currently CRC32 `1F1C08FB`), with SHA-256 recorded for stronger identification.
- Produce `BlackPearlEmerald_v<version>.zip` containing exactly the patch and
  generated `release.json`. Use an explicit packaging allowlist to exclude ROMs,
  saves, credentials, and unrelated local files.

Planned metadata fields: package schema version, BPE version, source commit,
patch filename/format/size/SHA-256, base-ROM size/CRC32/SHA-256, output-ROM
size/CRC32/SHA-256, and build/toolchain details. Do not include local ROM paths
or other machine-specific private information. The output checksum describes
the local game; the game itself is never included.

The outer filename supplies the public version identifier. Validation requires
it to agree with `release.json` and the version configuration at `sourceCommit`.
Renaming an already-built patch alone cannot create a correctly versioned game.

## 2. Package-upload publication workflow

Add a publication workflow triggered by package changes on `main`. This is a
repository-file upload/push, not a GitHub Release asset-upload event. A manual
rerun entry point should support recovery without requiring another version.

Process every unregistered package so a push containing several releases, or a
retried deployment, does not lose releases. Validate packages on pull requests
where applicable, but reserve release writes and Pages deployment for `main`.
Use the trusted workflow/exporter from the publishing checkout and check out
the recorded game commit into a separate read-only input tree. Do not execute
scripts supplied inside a release ZIP.

Validation must check:

- Valid filename/version/schema, a full source commit available in this
  repository's approved history, and agreement with that commit's BPE version.
- Safe ZIP paths, bounded extraction sizes, the expected file allowlist, patch
  structure and checksums, and matching metadata. Extract only validated entries.
- A new version has not already been registered to different patch bytes or a
  different source commit. Identical reruns are resumable; changed replacements
  are rejected and require a new version.
- Required documentation data, images, guides, calculator inputs, pages, links,
  and the selected patch are present and internally consistent.

GitHub can validate patch bytes and recorded metadata without the base ROM.
It cannot independently prove the full patched game matches the source merely
from a filename or checksum. The trusted local build and round-trip verification
establish that association; the package preserves it for publication.

After validation, archive the release bundle and assemble a Pages artifact
containing the new release plus all previously registered versions. Publish
the version catalog and the matching patch/docs paths in the same deployment.
The selector must not advertise a release whose files are unavailable.

Build jobs may finish out of order. Serialize deployment, refresh the complete
release registry before assembly, and prevent an older job from replacing a
newer catalog. Reconciliation on the next run/manual rerun must recover any
validated but not-yet-deployed releases. On failure, retain the previous site.

Use the repository Actions token for the eventual automation with minimal
required permissions. Maintainer setup, commits, and interactive GitHub writes
must follow the `blackpearlemerald` account policy in `AGENTS.md`.

## 3. Documentation export and historical snapshots

Refactor every exporter to accept explicit source and output directories.
`common.py`, `parse_pokemon.py`, and `parse_items.py` currently resolve paths
independently; changing only `common.py` will not cover the whole build.

Generate each release from its recorded game commit into an empty directory.
Do not reuse committed generated data from a different release. Record the game
source commit, exporter revision, schema version, and output checksums in the
documentation build metadata. Fail on missing required content instead of
silently producing an incomplete successful release.

Snapshot the full game-dependent site: maps and sprites, encounters, species,
evolutions, moves, abilities, items, shops, trainers, search, guides, change notes,
calculator data, and calculation rules/code. Retain each snapshot's compatible
frontend; do not assume future schemas can be read by old code.

Move handwritten guide notes and release explanations into version-aware
content associated with the game source. Raw exporters cannot infer the intent
behind every gameplay change. When fixing an exporter later, use the historical
guide content for the target game, not whichever notes are currently newest.

Documentation-only corrections keep the public game version and record a new
internal documentation revision. Provide an explicit workflow selecting the
target release and rebuilding against its pinned game source. Preserve the
original archived documentation bundle and immutable patch/source mapping.
Ordinary game-source commits must not run this correction path automatically.

Replace the current unversioned site-deployment behavior when activating this
pipeline so it cannot overwrite the versioned site with current working data.

## 4. Website selector and navigation

Add a large, persistent **GAME & DOCUMENTATION: 2.0.0 Beta** selector above the
navigation on every page, including the patcher and calculator. Make it easy
to see and operate on mobile and with a keyboard; show Latest/Beta/Older labels
in text. Replace fixed header offsets and the calculator's copied navigation
styles with shared layout behavior so the larger bar does not cover content.

Use addresses such as `versions/2.0.0-beta/pokemon.html?id=SPECIES_PIKACHU` and
`versions/1.0.1/patcher.html`, relative to the GitHub Pages repository base path.
These are planned URL shapes; adapt query names to the actual existing routes.

The main navigation includes a **Version History** page. It reads the validated
global release catalog, lists every published game version newest-first, links
directly to that version's hosted patch archive, and shows only curated,
player-facing one-line changes. Publication requires a matching history entry so
a release cannot appear without its download and changelog.

- Explicit versioned URLs win over saved preferences and remain shareable.
- Unversioned entry links preserve the page/query/hash and choose the remembered
  release; new visitors use the newest published release, including Beta.
- Switch to the equivalent page/entity using stable identifiers where possible.
  If the entity is missing, explain that and open its listing in the chosen
  release. Do not silently show another release's data.
- Keep internal links, map popups, searches, and calculator deep links inside
  the selected version. Reset obsolete in-memory data by navigating to the new
  release rather than partially swapping an already-running page.
- Separate game-dependent calculator saved state by release; shared cosmetic
  preferences can remain global. Handle unavailable browser storage gracefully.
- Read a current global release catalog from archived pages so older snapshots
  can still offer newly published versions. Page identity must remain pinned
  even if that catalog cannot be fetched.

Choose the default by validated version ordering, not filename string ordering
or upload time. Importing 1.0.1 after 2.0.0 Beta must not make 1.0.1 the default.

## 5. Patcher integration

Replace hard-coded version names and patch locations in `site/js/patcher.js`
and `site/patcher.html` with the selected release's validated metadata.
The visible target, patch bytes, validation requirements, and downloaded game
filename must all describe the same version.

Continue client-side ROM validation and patching, with no ROM uploads. Verify
the hosted patch against its recorded checksum before enabling patching.
Changing versions must terminate/reset the current operation before initializing
the new patch; ensure delayed callbacks cannot download the previous version.
If a patch is missing or corrupt, show an error and stop.

Only the actual patch file should be presented to the vendored patcher runtime;
the publisher can unpack the validated upload package and produce a small
runtime archive if needed. Preserve the vendored license and creator credit.

## 6. Backfill 1.0.1 and introduce 2.0.0 Beta

Verify the candidate 1.0.1 commit/archive against the official patch using the
maintainer's local ROM. Account for the historical toolchain when comparing
outputs. Do not label today's source or documentation as 1.0.1 merely because
some existing notes still use that version.

Implement compatibility importers for the historical source formats, including
trainer party definitions and tileset references that differ from current
exporter expectations. Audit guides and calculator mechanics against 1.0.1.
Keep the existing official patch bytes unchanged. If provenance or particular
documentation cannot be verified, record the gap instead of claiming complete
historical compatibility.

Bootstrap a provenance record for this legacy patch explicitly; the new
packaging helper did not create it. After verifying that import, prepare
2.0.0 Beta through the new local helper and test the two releases side by side.
Save-file compatibility is a separate game feature and test effort.

## 7. Archive retention and hosting capacity

Persist each release's patch, generated documentation bundle, and metadata in
GitHub Releases, backed by a tracked/archived release registry. Tags must identify
the recorded game commit, not the later package-upload commit. Keep original
release records and patch bytes immutable; documentation corrections get their
own revisioned bundle. Temporary Actions artifacts and caches are not the
historical source of truth.

Initially serve versioned snapshots and patch downloads through GitHub Pages,
deduplicating identical assets by content hash when assembling the site. Freeze
hashed assets and update the small release catalog separately; validate all
rewritten URLs, including calculator and worker paths. Never delete historical
patches just to fit a new deployment.

GitHub Pages currently limits a published site to 1 GB. Measure total output
on every deployment and flag capacity planning at 700 MiB. Before reaching the
limit, provision archive/CDN storage that preserves old URLs or their resolution
and supports browser patch fetches, HTTPS, and required cross-origin access.
Permanent archives preserve recovery, but downloadable ZIPs alone do not replace
live browsable historical documentation. Hosting expansion is a separate setup
decision if growth requires it.

Repository browser uploads currently have a 25 MiB per-file limit; larger
packages should use a normal Git push within GitHub's file limits. If packages
eventually exceed Git's supported size, revise ingestion explicitly to use
release assets or another package store rather than silently changing triggers.

## 8. Implementation sequence and acceptance checks

1. Add shared BPE version configuration and title-screen generation; build the
   local helper, clean-source checks, package schema, and round-trip validation.
2. Refactor exporters for explicit roots, add strict validation, and verify the
   1.0.1 compatibility import and game-dependent calculator behavior.
3. Implement the release catalog, snapshot paths, shared version bar, navigation,
   storage isolation, and patcher metadata integration.
4. Implement package ingestion, permanent archives, publication/retry logic,
   documentation corrections, and deployment-size checks. Replace the current
   deployment workflow only when the replacement is ready.
5. Validate a historical release and a new Beta locally and in a staged site;
   then enable package-triggered publication and update operator documentation.

Acceptance checks must cover:

- Title label, filename, metadata, website banner, patch target, and output game
  version agree; a renamed or mismatched package fails validation.
- Uploading a package after newer source commits still exports the recorded
  release source. Ordinary game commits leave published versions unchanged.
- A dirty source tree, missing source commit, invalid ZIP, corrupt patch, reused
  version, or incomplete documentation prevents publication.
- A multi-package push, identical retry, failed deployment, and out-of-order
  builds preserve all previous versions and select the correct latest release.
- Switching known changed encounters/items/trainers/maps and calculator inputs
  proves the entire release changes together. Missing entities stay within the
  chosen release with an explanation.
- Deep links, refresh/back navigation, old-version bookmarks, new/returning
  visitor defaults, keyboard use, small screens, and unavailable storage work.
- Switching while the patcher is loading/working cannot download the wrong game.
- Package, release, Pages, artifact, and cache allowlists exclude original and
  compiled ROMs. The local round-trip output matches the local release build.
- Documentation corrections retain the target game source/version and patch,
  record their documentation revision, and preserve the original archive.

## References

- [GitHub Actions workflow triggers and path filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [GitHub file-size limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
