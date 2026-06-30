# Vendored: Dynamic-Calc

Source: https://github.com/hzla/Dynamic-Calc (branch `master`)
Pinned commit: `0c79efccc369eea3137c1ffabfe8f2005f4ff8d0`
License: MIT (see upstream repo)

## Local modifications for BPE Emerald
- `js/showdown_hooks.js` — loads local `./data/bpe_calc_data.json` when `?data=bpe`
  (or no `data` param) instead of fetching from api.npoint.io.
- `index.html` — added `"bpe": "BPE Emerald"` to the `SOURCES` map; removed Google
  Analytics snippets.
- `js/*` — `boxSprites` limited to `["newhd"]`; the `img/newhd/` sprite folder is
  generated from BPE's own Pokémon sprites by `scripts/build_calc_data.py`.

## Excluded from vendoring (not needed / too large)
- `*_mastersheet*.html` and `*_mastersheet_files/` (other romhacks, 9–13 MB each)
- `img/front`, `img/back`, `img/newhd`, `img/pokesprite` (Showdown HD sprite sheets,
  ~186 MB) — replaced by BPE's own sprites in `img/newhd/` (generated).

## Regenerating data
Run `py BPEDocumentation/scripts/build_calc_data.py` to (re)build
`calc/data/bpe_calc_data.json` and the `calc/img/newhd/` sprite folder.
