# BPE save profiles

Each directory contains a compiled DWARF-derived save layout and preprocessor-derived flag/variable table for one immutable published BPE source commit. `inspect_save.py` selects a profile automatically when the supplied ROM hash matches a local release package, or explicitly through `--profile <version>`.

Do not hand-edit generated profile JSON. Use `generate_layout.py` against the release's exact source tree.

The 2.0.0-beta and 2.0.1 profiles describe the pre-2.1 save format (80-byte PC records). There is no 2.1 release profile yet; the unversioned layout in the tool directory describes the current 2.1 source. The inspector rejects a profile whose format does not match the save.
