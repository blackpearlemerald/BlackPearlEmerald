# Publish a BPE release

Add the ZIP produced by `python BPETools/prepare_release.py build` to this
directory. When it reaches `main`, GitHub Actions publishes its matching
documentation and patch. Do not add a ROM or rename an older patch to invent a
new release version. See [the operator guide](../../BPEDocumentation/RELEASING.md).
