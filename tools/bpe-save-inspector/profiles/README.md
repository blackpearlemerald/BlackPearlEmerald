# BPE save profiles

Each directory contains a compiled DWARF-derived save layout and preprocessor-derived flag/variable table for one immutable published BPE source commit. `inspect_save.py` selects a profile automatically when the supplied ROM hash matches a local release package, or explicitly through `--profile <version>`.

Do not hand-edit generated profile JSON. Use `generate_layout.py` against the release's exact source tree.
