**Interactive map: smooth pinch zoom on iPhone 12 Safari**

Plan prepared September 14, 2026, from repository commit `12b58897f9` and the
maintainer's report. Implementation now uses two shared image transforms,
viewport culling, a small generated overview, continuous pinch scale, and
optional phone diagnostics. See `INTERACTIVE_MAP_ZOOM_RESULTS.md` for measured
results and remaining physical-device verification. The original plan below
records the intended stages and acceptance targets.

The intended result is a map that follows both fingers immediately, keeps the
pinch midpoint anchored, and stops without a visible hitch or snap. Prioritize
iPhone 12 Safari. Keep the intentionally hidden +/− controls hidden. Preserve
the existing artwork, map contents, layer toggles, details, and version selection.

The recommended approach is to keep Leaflet and make the visible scene much
cheaper to scale: draw fewer independent images, reuse rendered artwork during
gestures, and load only the detail needed for the current view. Measure each
stage against the same phone scenarios. A successful smaller change can end the
optimization work once it passes the full acceptance criteria.

**What the source review establishes**

The current implementation in `site/js/app.js` initializes Leaflet 1.9.4 with
`zoomAnimation: false`, `markerZoomAnimation: false`, `zoomSnap: 0.25`, and
`zoomControl: false`. It immediately attaches every terrain image and every
enabled sprite layer, including objects far outside the screen.

The checked-in `site/js/data/world.json` contains:

| Content | Current scene cost |
| --- | --- |
| Map terrain | 494 image overlays using 382 distinct map images |
| Trainers | 524 sprite overlays representing 528 trainers |
| Visible items | 289 sprite overlays |
| Gifts and guides | 17 additional sprite overlays, plus badges/fallback markers |
| Warp links | 261 connections, each drawn as two lines and two endpoint circles |
| Optional labels | 494 markers when enabled |

That is **1,324 image overlays in the default scene**, plus vector paths and
badges. `preferCanvas: true` affects vector paths; it does not batch these
image overlays into a canvas. See the [Leaflet rendering options](https://leafletjs.com/reference.html#map-prefercanvas).

Leaflet's pinch handler already schedules movement through animation frames.
Each attached ImageOverlay listens for zoom changes and recalculates its
position, width, and height. Turning on zoom animation alone does not eliminate
those updates during the active pinch. This makes per-image updates the leading
performance hypothesis, to be confirmed by profiling. See the pinned
[pinch handler](https://github.com/Leaflet/Leaflet/blob/v1.9.4/src/map/handler/Map.TouchZoom.js)
and [ImageOverlay implementation](https://github.com/Leaflet/Leaflet/blob/v1.9.4/src/layer/ImageOverlay.js).

The distinct terrain PNGs total about 11 MiB compressed, while their dimensions
represent about 294 MiB of uncompressed RGBA pixels. This is an estimate of image
payload size, not a measurement of Safari memory. It supports investigating
decoded-image pressure as well as JavaScript time.

The existing hover handler is already frame-throttled and suspended during map
movement. Warp paths already share a canvas, which transforms during zoom and
reprojects at the end. Preserve these useful behaviors; measure any release-time
redraw before changing them. See the [Leaflet renderer implementation](https://github.com/Leaflet/Leaflet/blob/v1.9.4/src/layer/vector/Renderer.js).

**1. Record a repeatable baseline on the affected phone**

Record the iOS/Safari version, selected BPE release and documentation revision,
viewport, orientation, and enabled layers. Run on iPhone 12 Safari with normal
power settings and a cool device. Compare the published snapshot with the local
candidate so differences in historical map data do not distort the comparison.

Repeat each scenario at least three times:

- Pinch slowly from the whole-world view into a town and back out.
- Pinch quickly through several zoom levels and reverse direction immediately.
- Pinch over dense trainer/item areas and large terrain images such as Route 124.
- Move both fingers while pinching, then continue with one-finger panning.
- Zoom repeatedly with warp links enabled, then with every optional layer enabled.
- Repeat just after a cold load, after images have loaded, and after several
  minutes of movement. Include minimum/maximum zoom and a landscape rotation.

Add a development-only measurement switch that captures animation-frame
intervals, gesture duration, active image/path counts, image decoding and layer
rebuild timings, and cache size. Collect timings in memory and summarize after
the gesture; avoid per-frame logging. Use Safari's
[Web Inspector timelines](https://webkit.org/web-inspector/timelines-tab/)
through a Mac when available to separate script, layout, paint, and compositing
cost. Without that connection, use the on-device measurements and visual review,
and state that the cause attribution is less precise.

Frame callbacks are a diagnostic proxy, not proof that Safari presented every
frame. Use device observation/recording and rendering timelines alongside them.
Desktop mobile emulation and the existing screenshot script, which disables the
GPU, cannot establish iPhone gesture performance.

Deliver a baseline table and identify whether the main cost occurs during the
pinch, on finger release, during image loading, or in more than one of these.

**2. Make gesture behavior consistent**

Test `zoomSnap: 0` so releasing the fingers does not round the zoom to a quarter
step. Keep the current zoom limits. Evaluate disabling bounce at those limits
if it causes an unwanted settle-back motion. These settings affect gesture feel;
they are not substitutes for reducing rendering work. See the
[Leaflet zoom and touch options](https://leafletjs.com/reference.html#map-zoomsnap).

Retain Leaflet's native pinch handling and midpoint calculations. Avoid adding
another touch handler or smoothing filter that competes with Leaflet or makes
the artwork lag behind the fingers. Test zoom animation settings for the final
settle and programmatic navigation after rendering work is reduced; keep marker
behavior consistent so badges do not blink or drift.

Use one gesture lifecycle to suspend optional work until movement settles:
hover feedback, decorative guide animation, and nonessential layer rebuilding.
Coalesce `zoomend` and `moveend` so they do not trigger duplicate rebuilding.
Cancel the custom `flyTarget` animation when the user starts dragging or pinching;
its current cancellation token only supersedes earlier programmatic flights.

Handle canceled touches, a finger being lifted, orientation changes, and the
page returning from the background. Resume detail taps immediately after settling
without turning the final pinch contact into an accidental map selection.
Check header resize events and invalidate the map only when its dimensions
actually change. Keep page zoom and scrolling usable outside the map surface.

**3. Remove most of the work attached to every pinch frame**

Separate world data and hit testing from the objects currently being drawn.
Build a spatial lookup once, using a uniform grid unless measurements justify
a more complex index. Query a viewport plus a measured surrounding margin.
Keep drawing order deterministic when maps overlap or layers are reattached.

For terrain, mount only images intersecting that buffered view. For sprites,
replace the hundreds of independent ImageOverlays with a small number of
viewport-sized, cached canvas layers. Group by meaningful render order and
toggle behavior. Draw decoded sprites into those surfaces while stationary;
scale and translate the surfaces as a unit while the user pinches. Keep the
number of transformed surfaces bounded as world content grows.

Integrate this as a Leaflet layer with explicit ownership of its transforms.
The implementation must handle both continuous pinch `zoom` events and
programmatic zoom transitions; relying only on `zoomanim` is insufficient.
During movement, avoid resizing image elements or canvas backing stores,
recreating sprite nodes, or doing full-world scans on each frame. Prefer
transform updates for cached artwork, then verify Safari's actual rendering
cost; transforms are not an automatic guarantee of GPU-only work. See Google's
[animation performance guidance](https://web.dev/articles/animations-guide).

Preserve trainer direction, stack cycling, gift/trainer overlap behavior,
selection outlines, and the existing tap priorities. Use world coordinates for
hit testing, with the existing screen-space tap tolerances where appropriate.
Layer visibility must govern both drawing and selection. Keep badges and labels
readable; virtualize them, and pause their optional animation during movement.

Reuse decoded sprite images with a bounded cache. Compare canvas pixel ratios
of 1 and 2 on the phone and select the smallest that passes visual review;
do not automatically allocate every surface at the full device pixel ratio.
Disable image smoothing when drawing pixel art. Repaint at the final scale after
the gesture, using short scheduled batches with a starting budget of 4 ms each.
Deduplicate pending work and discard results belonging to an obsolete view.

Keep a surrounding buffer and a coarse world overview available so a fast zoom
out or a two-finger translation cannot reveal empty space. Do not freeze a small
viewport screenshot and assume it covers every possible gesture. Refresh
coverage incrementally when needed without blocking finger tracking, retaining
the previous valid artwork until replacement content is ready.

Measure warp redraws separately. Cull connections using segment/view
intersection, including lines whose endpoints are both offscreen. Compare the
current canvas padding of 0.5 with smaller buffered sizes; choose the smallest
that preserves coverage during fast gestures. Do not attribute already-cached
warp rendering to the image-overlay problem without evidence.

Run the full performance gate after this stage. If every scenario passes,
proceed to validation and publication without adding a tile exporter.

**4. If terrain still misses the target, introduce tiled map images**

Viewport culling helps at close zoom, but the whole-world view still exposes
nearly every map. If traces show terrain updates, image decoding, or memory
pressure remain the limiting factor, replace terrain ImageOverlays with a sparse
multi-resolution tile set served through Leaflet's GridLayer/TileLayer.

Generate tiles during documentation export from the positioned map images and
the selected release's `world.json`. Start with 256-pixel tiles and compare 512
only if measured request or decode overhead warrants it. Generate overview
levels through native game-pixel resolution; magnify native tiles at higher zoom
instead of exporting redundant enlarged images. Preserve the current coordinate
mapping, negative world positions, overlap order, transparency, and pixel art.

Compose each output tile from intersecting maps instead of allocating one giant
world canvas. Omit empty tiles with an explicit manifest so empty areas do not
produce repeated failed requests. Verify seams, fractional zoom levels, and
min/max zoom behavior under `L.CRS.Simple`.

Retain loaded parent/overview tiles until sharper replacements are decoded.
Tune the tile buffer and update scheduling with the fast pinch-out scenario;
delaying all tile updates until the gesture ends can leave coverage gaps. Keep
cache eviction bounded and cancel or ignore stale work. Leaflet already supplies
tile buffering and zoom-update controls to build on; see its
[GridLayer source](https://github.com/Leaflet/Leaflet/blob/v1.9.4/src/layer/tile/GridLayer.js).

This stage touches `scripts/build_all.py`, world extraction/rendering integration,
a new tile-generation module, frontend layer setup, and snapshot validation.
Retain individual map images used by other documentation pages. Measure total
archive and assembled-site size, including image deduplication, before accepting
the additional assets.

**5. Define “butter smooth” as a release gate**

Use these initial targets for warm, repeatable iPhone 12 Safari runs. They are
acceptance targets, not measurements or promises about every device condition.

| Check | Acceptance target |
| --- | --- |
| Finger tracking | Visually continuous motion aiming for 60 fps; no delayed easing behind the fingers |
| Frame intervals | At least 95% at or below 20 ms and 99% at or below 33.4 ms in each repeated scenario |
| Main-thread work | Pinch-related script/layout/paint work ideally below 8 ms per frame at the 95th percentile; no app-caused task over 50 ms during the gesture or final settle |
| Finger release | No visible position jump, snap to a quarter step, blank frame, or heavy final redraw |
| Cached detail | Final-resolution artwork restored within 150 ms when required images are decoded; network-dependent refinement measured separately |
| Coverage and accuracy | No disappearing maps, tile seams, drifting sprites, or changed tap targets |
| Repeated use | Cache reaches its configured bound, active layer counts return to their expected range, and performance does not progressively degrade over a five-minute session |

Cold-load testing must also keep finger tracking responsive while assets arrive.
If a scenario fails, report it separately; an average across easy and difficult
areas must not hide it. Record the cache limits chosen from device testing and
retain before/after results for the same locations and layer settings.

**6. Validate behavior and deliver through documentation revisions**

Add focused tests for the new coordinate/bounds math, visible-object lookup,
cache eviction and stale work, and tile generation if introduced. Browser checks
must cover fractional zoom, interrupted gestures, layer toggles, stacked
trainers, hidden items, gifts/guides, overlapping maps, warp destinations,
details, and deep links. Include existing desktop wheel/trackpad and keyboard
zoom behavior without restoring the visible +/− controls. Respect reduced-motion
preferences for optional/programmatic animation while keeping direct pinch
feedback responsive.

Preview both supported releases using their pinned game data. Verify the version
selector and map/detail links stay within the selected release. Perform the
final subjective test on the maintainer's iPhone 12 Safari as well as collecting
the measurements; desktop automation supplements that check.

Follow `RELEASE_VERSIONING_PLAN.md` and `RELEASING.md`. Run the existing checks
when implementing this site/export change:

```text
python -m unittest discover -s BPETools/tests -v
node BPETools/tests/test_release_context.cjs
python BPEDocumentation/scripts/releases.py --validate-only
```

Also complete a real documentation export and browser check, including validation
of generated tile assets if added. Update `RELEASING.md` if the operator's steps
change. Use fresh preview directories under `.release-work/`.

Publication is a documentation correction for each affected published release,
using `correct_version` and the next available `docs_revision`. Read the actual
revision at implementation time rather than assuming the revision recorded here
is still current. A frontend commit alone does not replace archived snapshots.
Preserve each pinned source commit, patch bytes, earlier documentation archives,
and game version. Verify the required GitHub account and author before any
future commit or GitHub write, and confirm the BPE Documentation workflow and
hosted phone behavior after publication.

If a regression appears, use the existing recovery procedure or publish a new
documentation correction restoring the prior implementation; do not overwrite
an immutable revision. The final handoff should include the chosen rendering
approach, before/after phone results, cache/asset-size measurements, regression
check results, and the published documentation revisions.
