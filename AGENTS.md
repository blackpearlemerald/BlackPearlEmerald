# Project GitHub Account Policy

- Use only the GitHub account `blackpearlemerald` for this project.
- Never use the GitHub account `ColeHarding3` for any project-related action.
- Before any GitHub write operation, verify that `blackpearlemerald` is the active authenticated account.
- Before creating a commit, verify that the repository-local author identity belongs to `blackpearlemerald` and does not use the name or email associated with `ColeHarding3`.
- If `blackpearlemerald` is unavailable or lacks permission, stop and ask the user for help. Do not fall back to another account.

# Personal Windows Execution Safeguards

- On Windows, launch Unreal Engine `Build.bat` and `UnrealEditor-Cmd.exe` with `sandbox_permissions="require_escalated"` on the first attempt. Do not probe them inside the restricted sandbox; denial can leave a modal CLR error dialog.
- If an ordinary `dotnet build`, `dotnet test`, or `dotnet run` fails because a required NuGet, AppData, SDK, or cache path is denied, retry once with scoped escalation instead of repeatedly relaunching or force-killing `dotnet.exe`.
- Start persistent .NET services detached and hidden, redirect stdout and stderr to workspace logs, and retain process IDs for graceful shutdown.

# BPE Release and Documentation Policy

The agreed design is **upload a patch package to publish a release**. Read
[the release versioning plan](BPEDocumentation/RELEASE_VERSIONING_PLAN.md)
before implementing or changing the game version, release packaging,
documentation export, version selector, patcher, or publication workflows.

## Implementation status and operating instructions

- The release workflow is implemented and deployed. Initial hosted publication passed for `1.0.1` (documentation revision 2) and `2.0.0-beta` (revision 1). Beta is the newest published release. The maintainer verified its smaller bottom-left title label and normal game startup/loading in mGBA.
- Read [RELEASING.md](BPEDocumentation/RELEASING.md) for the concrete commands, validation, retries and documentation corrections. Keep that operator guide current when changing the workflow.
- `BPE_VERSION.json` is the shared version setting. Use `python BPETools/prepare_release.py set-version <version>`, commit the source, then `python BPETools/prepare_release.py build --base-rom "<local clean ROM>"`. The default package output is `.release-work/packages/`.
- Publish only the generated package by adding it to `releases/packages/` on `main`. Never stage `.release-work/`, a `.gba` or `BPETools/release.local.json`. Verify the active GitHub account and local author before committing or pushing.
- Before release tooling changes, run `python -m unittest discover -s BPETools/tests -v`, `node BPETools/tests/test_release_context.cjs` and `python BPEDocumentation/scripts/releases.py --validate-only`, plus an actual export/browser check when the change affects publication or the site. Hosted success must be confirmed in the BPE Documentation workflow.

## Release procedure

1. The maintainer chooses a BPE version before building locally. One version configuration must generate the in-game title-screen label, package filename, and release metadata. Do not repurpose the upstream `GAME_VERSION` setting, which selects Emerald/FireRed/LeafGreen.
2. Commit the release source, including its version configuration. Build and package from that exact clean source commit; ensure the commit is available in the remote repository before publication.
3. Build the game and create and round-trip-test the patch locally, using the maintainer's local clean Emerald ROM. Keep both the original ROM and compiled `.gba` files on the maintainer's PC. Never put either ROM in Git, GitHub Releases, Actions artifacts, caches, packages, or uploads.
4. Produce one ZIP, such as `BlackPearlEmerald_v2.0.0-beta.zip`, containing the patch and generated `release.json`. Metadata must identify the source commit, version, patch checksum, expected base-ROM checksum, and expected output checksum. The filename determines the public release identifier but must agree with the metadata and the version at the recorded source commit.
5. Upload/commit the package under `releases/packages/`. Publication starts when that package reaches `main`. GitHub exports documentation from the recorded source commit, validates the package and site, and publishes the matching documentation and patch together. A separate local Actions runner is not part of this design.

## Invariants for future work

- Keep the **Rom Patcher** page minimal: unmodified Pokémon Emerald ROM + the selected Black Pearl Emerald version patch → **Patch & Download**. Patching starts on that button click. Avoid explanatory cards, technical details and extra notices in the normal page; show concise loading/error feedback when needed.
- Ask the maintainer to perform mGBA testing. Do not control mGBA or automate its UI unless the maintainer explicitly changes this preference. Put requested test ROM copies in the project root with a clear versioned filename, keep them ignored by Git, and report the path.
- Ordinary game commits do not create public releases, require a new public version per commit, or replace published documentation. A new patch package is the release trigger. Renaming an old patch does not change the version inside the game.
- Never generate a release's documentation from whichever commit happens to be latest when its patch is uploaded. Use the package's recorded game source commit and record the exporter revision separately.
- One prominent, persistent version selector controls the entire site, including maps, Pokemon, items, trainers, guides, search, calculator data/rules, and the patcher. Explicit versioned URLs take precedence over remembered preferences.
- New visitors default to the newest published release, including Beta. Returning visitors retain their selection. Stable and Beta versions have distinct identities and visible labels.
- Released patch bytes and their source/version mapping are immutable. Reject reused version identifiers with different content. Exact reruns may resume a failed publication without creating a duplicate.
- Preserve older release documentation and patches. Documentation-only corrections may retain the game version, with a separate documentation revision rebuilt against that release's pinned source. Never silently replace historical data with current game data.
- Publish only complete, validated documentation/patch pairs. Missing or invalid patches must not silently fall back to another version. Failed builds or deployments must leave the previous public site intact.
- The verified 1.0.1 source is `ed784bef37b5d37431867c57fb03c958913398a0`, retained by tag `bpe/source/1.0.1`. Its 18,718 tracked inputs match the original archive, and the official patch reproduces that archive's game exactly. Keep the legacy record and source tag; current documentation is not a substitute.
- Game/save compatibility is separate from documentation version selection. Do not promise that saves can move between game versions without separate testing.
