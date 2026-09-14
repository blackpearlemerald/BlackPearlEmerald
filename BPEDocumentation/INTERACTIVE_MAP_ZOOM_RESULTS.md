**Interactive map zoom implementation — September 14, 2026**

The map now scales terrain and sprites through two shared parent transforms.
Image positions and native pixel dimensions stay fixed during pinching. A
spatial index supplies only the buffered view, additions are scheduled in short
batches, and offscreen image elements are released after movement settles.
World data and selection remain independent of the rendered image elements.

A 1074 × 1208 overview generated from the selected release's positioned terrain
provides distant views and background coverage while nearby detail loads. The
checked-in dataset's overview is 198,194 bytes (about 194 KiB), with approximately
5 MiB of decoded RGBA pixels. Its export is bounded to 2048 pixels per side and
never allocates a full-resolution world canvas. Each release gets its own asset.

Pinch zoom no longer snaps to quarter steps on release. The +/− controls remain
hidden. Touch input interrupts custom warp flights, optional guide animation
pauses during movement, and unchanged header sizes no longer invalidate the map.
Reduced-motion settings disable optional zoom/warp animation. An overview load
failure falls back to native terrain images.

The staged comparison supported retaining the original pixel images in shared
groups, avoiding a sprite-canvas rewrite. The world overview addressed the
remaining distant-view cost; a full terrain tile pyramid was not necessary for
the measured scenarios. Original full-resolution art is used at close zoom.

**Local before/after comparison**

The same pinned Leaflet pinch handler was driven with simulated finger positions
inside a 390 × 844 iframe in the Codex Chromium browser. Each scenario comprised
three 90-frame pinch-in/out reversals with a moving midpoint. Measurements are
from the desktop host's high-refresh display, not from an iPhone or Safari.
Frame callback intervals are a proxy, not a measurement of presented frames or
physical touch-to-display latency. The original renderer used the same map data.

| Scenario | Original p95 frame interval | Updated p95 frame interval | Original p95 movement scripting | Updated p95 movement scripting |
| --- | ---: | ---: | ---: | ---: |
| World overview | 36.4 ms | 12.1 ms | 3.9 ms | 0.3 ms |
| Mauville City | 24.2 ms | 6.2 ms | 4.8 ms | 0.2 ms |
| Route 124 | 24.3 ms | 6.1 ms | 4.4 ms | 0.2 ms |

Updated p99 frame intervals were 14.2, 6.2, and 6.2 ms respectively. No tasks over
50 ms were recorded in the final default-layer run. The original run recorded
one 59 ms task. At the end of Route 124, attached map images fell from 1,324 to
29 (12 terrain images, 16 sprite images, and the overview). Counts depend on the
current view and enabled layers; this is not a fixed memory claim.

The early grouped-image version still missed the overview target. The final
numbers above include the generated overview and native-size child geometry.

With all optional layers enabled (including hidden items and 494 labels), the
updated p95 frame intervals were 18.2 ms at the overview, 6.2 ms in Mauville,
and 12.1 ms on Route 124. No tasks over 50 ms were recorded in that run.

**Verification and remaining device check**

Automated checks cover spatial lookup, negative coordinates, edge contacts,
fractional zoom without per-image geometry writes, image ordering, viewport
release, stale queues, overview/detail transitions, load-failure fallback,
cleanup, deterministic overview composition, dimension limits, and invalid
overview metadata/assets. Existing release integrity and version routing checks
remain part of validation. Mobile browser checks confirmed a Route 118 trainer
and item still open the correct details after fractional wheel zoom, and the
version selector preserves the map route while changing release data. The documentation workflow runs the new checks too.

Use `?map-perf=1` on a versioned map URL to enable on-device frame diagnostics in
the toggle panel. Normal map URLs do not collect these measurements. Test slow
and fast pinches, direction reversals, moving the midpoint, zoom limits, and
immediate tapping after release. Verify both releases, optional layers, trainer
stacks, hidden items, gifts/guides, and warp navigation.

The maintainer's iPhone 12 Safari test remains necessary to confirm the actual
touch latency and subjective smoothness. Local Chromium results do not establish
the plan's physical-device acceptance gate, Safari memory behavior, or sustained
five-minute phone performance. No 60 fps claim is made for that device yet.
