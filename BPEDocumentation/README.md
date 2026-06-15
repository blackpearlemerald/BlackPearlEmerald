# BPE Emerald — Interactive World Map

A fully interactive, GitHub-Pages-hostable map of the entire game. Every map
(towns, routes, caves, interiors, dungeons) is rendered from the **real game
data** and stitched into position. Pan/zoom on desktop and mobile; click any
trainer to see their full team, or any item to see what it is.

**The original game files are never modified.** The build scripts only *read*
the surrounding game source repo and write into `site/`.

## Layout

```
BPEDocumentation/            (lives inside the pokeemerald-expansion repo)
  scripts/          read-only Python parsers + renderer
    common.py           paths + GBA tileset constants + parsing helpers
    parse_trainers.py   trainers.party  -> site/js/data/trainers.json
    render_maps.py      tilesets + blockdata -> site/img/maps/*.png
    extract_world.py    connections/warps/objects -> site/js/data/world.json
    sprites.py          overworld trainer sprites -> site/img/sprites/*.png
    build_all.py        runs all of the above
  site/             the static site (this is what GitHub Pages serves)
    index.html
    css/style.css
    js/app.js           Leaflet map: image overlays, markers, popups
    js/data/world.json  generated: map positions, trainers, items, warp links
    img/maps/*.png      generated map images (one per layout)
    lib/                vendored Leaflet 1.9.4 (offline-capable)
```

## Regenerate

Requires Python 3 with Pillow (`py -m pip install pillow`).

```sh
cd scripts
py build_all.py
```

This re-reads the game source and regenerates all images + JSON. Re-run it
whenever the game's maps, trainers, or items change.

## Preview locally

```sh
py -m http.server -d site 8000
# open http://localhost:8000
```

## How it works

- **Map graphics** are decoded straight from the GBA tilesets: each layout's
  `map.bin` block grid is composited from `metatiles.bin` + `tiles.png` +
  JASC palettes (`render_maps.py`).
- **World position** comes from each `map.json`'s `connections` array. Maps are
  grouped into connected components and laid out by accumulating connection
  offsets; the component containing Littleroot Town is the contiguous Hoenn
  overworld. Interiors/caves (reached by warps, not connections) are placed as
  floating "islands" anchored near the warp that leads into them, with a
  connector line.
- **Trainers** are object events whose script resolves to a `TRAINER_*` id; the
  team is read from `trainers.party`. Each trainer is drawn as its actual
  overworld sprite (frame 0 of its `OBJ_EVENT_GFX_*` object-event graphic,
  extracted by `sprites.py`).
- **Items** are `OBJ_EVENT_GFX_ITEM_BALL` object events (item id in the
  `trainer_sight_or_berry_tree_id` field) plus hidden items in `bg_events`.
- **Wild encounters** come from `src/data/wild_encounters.json`. Each map's
  grass/surf/rock-smash/fishing slots are converted to per-species percentages
  using the group's slot rate tables (fishing split into Old/Good/Super Rod).
  Click any map to see its encounter list.

## Publish to GitHub Pages

The `site/` folder is fully static and committed (including the generated
images + JSON), so no build step runs on GitHub. To host it, enable GitHub
Pages on this repo and point it at the `BPEDocumentation/site` directory on the
branch you publish.
