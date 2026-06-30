/* BPE Emerald interactive world map.
 * World coordinates are GBA pixels with +y pointing DOWN. Leaflet CRS.Simple
 * uses lat = +y UP, so every world (x, y) maps to LatLng(-y, x). */

const W2LL = (x, y) => L.latLng(-y, x);

function prettify(name) {
  if (!name) return "";
  name = name.replace(/^(MAP_|ITEM_|TRAINER_|SPECIES_|MOVE_|ABILITY_)/, "");
  return name.split("_").map(w =>
    w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w)
    .join(" ")
    .replace(/([A-Za-z])(\d)/g, "$1 $2");  // "Route102" -> "Route 102"
}

function trainerPopup(t, spriteFile) {
  if (!t) return "<div class='tcard-name'>Trainer</div>";
  const tImg = spriteFile
    ? `<img class="tcard-sprite" src="img/sprites/${spriteFile}" alt="" ` +
      `onerror="this.remove()">`
    : "";
  let html = `<div class="tcard-head">${tImg}<div class="tcard-id">` +
    `<div class="tcard-name">${t.name || "Trainer"}</div>` +
    `<div class="tcard-class">${t.class || ""}</div></div></div>`;
  for (const m of t.party || []) {
    const icon = m.sprite
      ? `<img class="mon-icon" src="img/pokemon/${m.sprite}" alt="" ` +
        `loading="lazy" onerror="this.remove()">`
      : "";
    html += `<div class="mon">${icon}<div class="mon-body">` +
      `<div class="mon-head">${prettify(m.species)}` +
      `<span class="mon-lvl"> · Lv ${m.level}</span></div>`;
    const meta = [];
    if (m.item) meta.push("@ " + m.item);
    if (m.ability) meta.push(m.ability);
    if (m.nature) meta.push(m.nature);
    if (meta.length) html += `<div class="mon-meta">${meta.join(" · ")}</div>`;
    if (m.moves && m.moves.length) {
      html += `<div class="mon-moves">` +
        m.moves.map(mv => `<span class="move">${mv}</span>`).join("") +
        `</div>`;
    }
    html += `</div></div>`;  // close .mon-body, .mon
  }
  return html;
}

function itemIconUrl(itemConst) {
  const key = (itemConst || "").replace(/^ITEM_/, "").toLowerCase();
  return `sprites/items/${key}.png`;
}

function itemRow(itemConst, qty) {
  const name = prettify(itemConst);
  const icon = `<img class="pop-item-icon" src="${itemIconUrl(itemConst)}" `
    + `alt="" onerror="this.remove()" loading="lazy">`;
  const qtyStr = qty > 1 ? `<span class="pop-item-qty">×${qty}</span>` : "";
  return `<div class="pop-item-row">${icon}<span class="pop-item-name">${name}</span>${qtyStr}</div>`;
}

function itemPopup(it) {
  const tag = it.hidden ? "<small>Hidden item</small>" : "<small>Item Ball</small>";
  const icon = it.hidden ? ""
    : `<img class="pop-item-icon" src="${itemIconUrl(it.item)}" alt="" onerror="this.remove()"> `;
  return `<div class="item-pop">${icon}${prettify(it.item)}${tag}</div>`;
}

function martPopup(mart) {
  let html = `<div class="mart-head">🛒 ${mart.name} Poké Mart</div>`;
  for (const inv of mart.inventories) {
    html += `<div class="mart-cond">${inv.condition}</div>`;
    html += `<div class="mart-list">`;
    for (const item of inv.items) {
      html += itemRow(item, 1);
    }
    html += `</div>`;
  }
  return html;
}

function giftPopup(gift) {
  const src = prettify(gift.script || gift.mapId);
  let html = `<div class="gift-head">🎁 ${prettify(gift.mapId)} Gift</div>`;
  html += `<div class="gift-items">`;
  for (const gi of gift.items) {
    html += itemRow(gi.item, gi.qty);
  }
  html += `</div>`;
  return html;
}

function encSprite(m) {
  // The build annotates each encounter mon with its menu-icon filename.
  if (!m.sprite) return "";
  return `<img class="enc-icon" src="img/pokemon/${m.sprite}" alt="" ` +
    `loading="lazy" onerror="this.remove()">`;
}

function monRows(mons) {
  return mons
    .slice().sort((a, b) => b.pct - a.pct)
    .map(m => {
      const lvl = m.min === m.max ? `Lv ${m.min}` : `Lv ${m.min}–${m.max}`;
      return `<div class="enc-row">` +
        encSprite(m) +
        `<span class="enc-sp">${prettify(m.species)}</span>` +
        `<span class="enc-pct">${m.pct}%</span>` +
        `<span class="enc-lvl">${lvl}</span></div>`;
    }).join("");
}

const ENC_LABELS = { land: "🌿 Grass", water: "🌊 Surf", rock_smash: "🪨 Rock Smash" };
const ROD_LABELS = { old: "Old Rod", good: "Good Rod", super: "Super Rod" };

// Towers/facilities that the game types as UNDERGROUND (cave tileset) but read
// as buildings to players. Matched by map-id prefix, overriding the type.
const BUILDING_MAP_PREFIXES = [
  "MAP_SKY_PILLAR", "MAP_MIRAGE_TOWER", "MAP_NEW_MAUVILLE",
];

// "land_mons" covers both overworld grass and cave floors. Pick the wording
// from the map type so caves don't say "Grass".
function landLabel(m) {
  if (BUILDING_MAP_PREFIXES.some(p => m.id.startsWith(p))) return "🏠 Building";
  if (m.type === "MAP_TYPE_UNDERGROUND") return "🦇 Cave";
  if (m.type === "MAP_TYPE_INDOOR") return "🏠 Building";
  return ENC_LABELS.land;
}

function encounterPopup(m) {
  let html = `<div class="tcard-name">${prettify(m.id)}</div>`;
  const e = m.enc;
  if (!e) {
    return html + `<div class="enc-none">No wild encounters in this area.</div>`;
  }
  for (const key of ["land", "water", "rock_smash"]) {
    if (e[key]) {
      const label = key === "land" ? landLabel(m) : ENC_LABELS[key];
      html += `<div class="enc-cat">${label}` +
        (e[key].rate != null ? `<span class="enc-rate"> · rate ${e[key].rate}</span>` : "") +
        `</div>${monRows(e[key].mons)}`;
    }
  }
  if (e.fishing) {
    html += `<div class="enc-cat">🎣 Fishing</div>`;
    for (const rod of ["old", "good", "super"]) {
      if (e.fishing[rod]) {
        html += `<div class="enc-rod">${ROD_LABELS[rod]}</div>${monRows(e.fishing[rod])}`;
      }
    }
  }
  return html;
}

async function main() {
  const world = await fetch("js/data/world.json").then(r => r.json());
  const TILE = world.tile || 16;

  const map = L.map("map", {
    crs: L.CRS.Simple,
    minZoom: -6,
    maxZoom: 4,
    zoomSnap: 0.25,
    wheelPxPerZoomLevel: 80,
    preferCanvas: true,
    attributionControl: false,
    maxBoundsViscosity: 0.6,
  });

  // ---- map images ----
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const m of world.maps) {
    const bounds = [W2LL(m.x, m.y), W2LL(m.x + m.w, m.y + m.h)];
    L.imageOverlay("img/maps/" + m.img, bounds, {
      className: "map-img", interactive: false,
    }).addTo(map);
    minX = Math.min(minX, m.x); minY = Math.min(minY, m.y);
    maxX = Math.max(maxX, m.x + m.w); maxY = Math.max(maxY, m.y + m.h);
  }

  // Map clicks open the encounter menu. A single map-level handler is used
  // (rather than per-overlay popups) because the marker canvas sits above the
  // image overlays and would otherwise swallow their click events.
  const encPopup = L.popup({ maxWidth: 300, maxHeight: 380,
                             className: "enc-popup", autoPan: true });
  function mapAt(x, y) {
    let best = null;
    for (const m of world.maps) {
      if (x >= m.x && x < m.x + m.w && y >= m.y && y < m.y + m.h) {
        // prefer the smallest matching map when islands overlap edges
        if (!best || m.w * m.h < best.w * best.h) best = m;
      }
    }
    return best;
  }
  // hit-test arrays (populated below); resolved here because overlay/canvas
  // clicks bubble to the map, so all object clicks go through one handler.
  const trainerHits = [];  // {x0,x1,yTop,yBot, gxTop, trainerId}
  const itemHits = [];     // {ll, it}
  const objPopup = L.popup({ autoPan: true, maxWidth: 320, maxHeight: 360 });

  function trainerAt(x, y) {
    if (!map.hasLayer(trainerLayer)) return null;
    // among sprite rects under the click, prefer the one whose foot position
    // (tile centre) is nearest -- sprites are tall and overlap neighbours above
    let best = null, bestD = Infinity;
    for (const t of trainerHits) {
      if (x >= t.x0 && x <= t.x1 && y >= t.yTop && y <= t.yBot) {
        const dx = x - t.stack.gx, dy = y - t.stack.gy;
        const d = dx * dx + dy * dy;
        if (d < bestD) { bestD = d; best = t; }
      }
    }
    return best;
  }
  function itemAt(latlng) {
    const p = map.latLngToContainerPoint(latlng);
    let best = null, bestD = 12;  // px hit radius
    for (const h of itemHits) {
      const layer = h.it.hidden ? hiddenLayer : itemLayer;
      if (!map.hasLayer(layer)) continue;
      const d = p.distanceTo(map.latLngToContainerPoint(h.ll));
      if (d < bestD) { bestD = d; best = h.it; }
    }
    return best;
  }

  function giftAt(latlng) {
    if (!map.hasLayer(giftLayer)) return null;
    const p = map.latLngToContainerPoint(latlng);
    let best = null, bestD = 14;
    for (const h of giftHits) {
      const d = p.distanceTo(map.latLngToContainerPoint(h.ll));
      if (d < bestD) { bestD = d; best = h.gift; }
    }
    return best;
  }

  // show a trainer stack's current member; cycle via the marker or the button
  let openStack = null;
  function showStack(st) {
    const t = st.trainers[st.idx];
    renderStack(st);                          // map sprite matches the popup
    const sp = spriteFor(t);
    const n = st.trainers.length;
    const nav = n > 1
      ? `<div class="stack-nav">Trainer ${st.idx + 1} / ${n}` +
        `<button type="button" class="stack-cycle">Next ▸</button></div>`
      : "";
    objPopup.setLatLng(W2LL(t.gx, sp.yTop))
      .setContent(nav + trainerPopup(world.trainerData[t.trainerId], sp.file))
      .openOn(map);
    if (n > 1) {
      const el = objPopup.getElement();
      const btn = el && el.querySelector(".stack-cycle");
      if (btn) L.DomEvent.on(btn, "click", (ev) => {
        L.DomEvent.stop(ev);
        st.idx = (st.idx + 1) % n;
        showStack(st);
      });
    }
  }

  map.on("click", (e) => {
    // priority: warp endpoint -> trainer sprite -> item -> map encounters
    const target = warpEndAt(e.latlng);
    if (target) { flyTarget(target); return; }
    const x = e.latlng.lng, y = -e.latlng.lat;
    const hit = trainerAt(x, y);
    if (hit) {
      const st = hit.stack;
      if (st === openStack)                  // tapping the same marker cycles
        st.idx = (st.idx + 1) % st.trainers.length;
      openStack = st;
      showStack(st);
      return;
    }
    openStack = null;
    const it = itemAt(e.latlng);
    if (it) {
      objPopup.setLatLng(e.latlng).setContent(itemPopup(it)).openOn(map);
      return;
    }
    const gf = giftAt(e.latlng);
    if (gf) {
      objPopup.setLatLng(e.latlng).setContent(giftPopup(gf)).openOn(map);
      return;
    }
    const m = mapAt(x, y);
    if (!m) return;
    if (world.marts && world.marts[m.id]) {
      objPopup.setLatLng(e.latlng)
        .setContent(martPopup(world.marts[m.id])).openOn(map);
      return;
    }
    encPopup.setLatLng(e.latlng).setContent(encounterPopup(m)).openOn(map);
  });
  const worldBounds = L.latLngBounds(W2LL(minX, minY), W2LL(maxX, maxY));
  map.fitBounds(worldBounds.pad(0.05));
  map.setMaxBounds(worldBounds.pad(0.5));

  const canvas = L.canvas({ padding: 0.5 });

  // ---- warp links ----
  const warpLayer = L.layerGroup();
  // Custom eased pan. Leaflet's flyTo misbehaves under CRS.Simple at large
  // pixel coordinates and its built-in pan animation stalls over the huge
  // offsets between distant map ends, so we interpolate the centre ourselves.
  // (CRS.Simple is linear, so a linear latlng lerp gives a constant-speed pan.)
  let flyToken = 0;
  function flyTarget(ll) {
    const z = map.getZoom();          // keep the current zoom; pan only
    const start = map.getCenter();
    const dur = 650;
    const t0 = performance.now();
    const token = ++flyToken;
    const ease = (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);
    function step(now) {
      if (token !== flyToken) return;              // superseded by a newer pan
      const t = Math.min(1, (now - t0) / dur);
      const k = ease(t);
      map.setView([start.lat + (ll.lat - start.lat) * k,
                   start.lng + (ll.lng - start.lng) * k],
                  z, { animate: false });
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // endpoint nodes for hit-testing inside the single map-click handler
  // (canvas marker clicks also bubble to the map, so we resolve both here)
  const warpEnds = [];  // {ll, target}
  for (const wl of world.warpLinks) {
    const a = W2LL(wl.from[0], wl.from[1]);
    const b = W2LL(wl.to[0], wl.to[1]);
    // thick black border underneath
    L.polyline([a, b], {
      color: "#000", weight: 4.5, opacity: 0.7, interactive: false,
      lineCap: "round", renderer: canvas,
    }).addTo(warpLayer);
    // bright line on top
    L.polyline([a, b], {
      color: "#5fd0ff", weight: 2.5, opacity: 0.95, interactive: false,
      lineCap: "round", renderer: canvas,
    }).addTo(warpLayer);
    // endpoint dots (non-interactive; resolved via map click below)
    for (const [here, there] of [[a, b], [b, a]]) {
      L.circleMarker(here, {
        radius: 5, color: "#000", weight: 1.5,
        fillColor: "#5fd0ff", fillOpacity: 1, interactive: false,
        renderer: canvas,
      }).addTo(warpLayer);
      warpEnds.push({ ll: here, target: there });
    }
  }

  // returns the warp target if the click landed on an endpoint, else null
  function warpEndAt(latlng) {
    if (!map.hasLayer(warpLayer)) return null;
    const p = map.latLngToContainerPoint(latlng);
    let best = null, bestD = 11;  // px hit radius
    for (const e of warpEnds) {
      const d = p.distanceTo(map.latLngToContainerPoint(e.ll));
      if (d < bestD) { bestD = d; best = e.target; }
    }
    return best;
  }

  // ---- trainers (overworld sprites, world-anchored so they scale with the
  // map). Trainers sharing a tile (Winstrate family, rival variants, ...)
  // collapse into one cycling marker with a "xN" badge; clicking cycles. ----
  const trainerLayer = L.layerGroup();

  function spriteFor(t) {
    const s = world.sprites[t.gfx];
    const sw = s ? s.w : TILE, sh = s ? s.h : TILE;
    const yBot = t.gy + TILE / 2, yTop = yBot - sh;
    const file = s ? ((s.dirs && (s.dirs[t.dir] || s.dirs.down)) || s.file)
                   : null;
    return { file, sw, sh, yTop,
             bounds: [W2LL(t.gx - sw / 2, yBot), W2LL(t.gx + sw / 2, yTop)] };
  }

  // group trainers by tile
  const stackMap = new Map();
  for (const t of world.trainers) {
    const key = t.gx + "," + t.gy;
    let st = stackMap.get(key);
    if (!st) stackMap.set(key, st = { trainers: [], idx: 0, gx: t.gx, gy: t.gy });
    st.trainers.push(t);
  }

  function renderStack(st) {           // point the overlay at the current trainer
    const sp = spriteFor(st.trainers[st.idx]);
    if (st.overlay && sp.file) {
      st.overlay.setUrl("img/sprites/" + sp.file);
      st.overlay.setBounds(sp.bounds);
    }
  }

  for (const st of stackMap.values()) {
    const sp = spriteFor(st.trainers[0]);
    if (sp.file) {
      st.overlay = L.imageOverlay("img/sprites/" + sp.file, sp.bounds,
        { className: "sprite", interactive: false }).addTo(trainerLayer);
    } else {
      L.circleMarker(W2LL(st.gx, st.gy), {
        radius: 5, color: "#5a0000", weight: 1, fillColor: "#e23b3b",
        fillOpacity: 0.95, interactive: false, renderer: canvas,
      }).addTo(trainerLayer);
    }
    // hit rect spans the largest sprite in the stack
    let maxW = TILE, maxH = TILE;
    for (const t of st.trainers) {
      const s = world.sprites[t.gfx];
      if (s) { maxW = Math.max(maxW, s.w); maxH = Math.max(maxH, s.h); }
    }
    const yBot = st.gy + TILE / 2;
    trainerHits.push({ x0: st.gx - maxW / 2, x1: st.gx + maxW / 2,
                       yTop: yBot - maxH, yBot, stack: st });
    if (st.trainers.length > 1) {
      L.marker(W2LL(st.gx + maxW / 2, yBot - maxH), {
        interactive: false,
        icon: L.divIcon({ className: "stack-badge",
                          html: "×" + st.trainers.length,
                          iconSize: [0, 0] }),
      }).addTo(trainerLayer);
    }
  }

  // ---- items (visible + hidden split into two layers) ----
  const itemLayer = L.layerGroup();
  const hiddenLayer = L.layerGroup();
  const ballSprite = world.sprites && world.sprites["OBJ_EVENT_GFX_ITEM_BALL"];
  for (const it of world.items) {
    const hidden = it.hidden;
    const ll = W2LL(it.gx, it.gy);
    if (!hidden && ballSprite) {
      const sw = ballSprite.w, sh = ballSprite.h;
      const file = (ballSprite.dirs && ballSprite.dirs.down) || ballSprite.file;
      const bounds = [
        W2LL(it.gx - sw / 2, it.gy + TILE / 2),
        W2LL(it.gx + sw / 2, it.gy + TILE / 2 - sh),
      ];
      L.imageOverlay("img/sprites/" + file, bounds, {
        className: "sprite item-ball-sprite", interactive: false,
      }).addTo(itemLayer);
    } else {
      L.circleMarker(ll, {
        radius: hidden ? 4 : 5,
        color: hidden ? "#3a4654" : "#7a5b00",
        weight: 1,
        fillColor: hidden ? "#7a8aa0" : "#f4c542",
        fillOpacity: hidden ? 0.8 : 0.95,
        interactive: false,
        renderer: canvas,
      }).addTo(hidden ? hiddenLayer : itemLayer);
    }
    itemHits.push({ ll, it });
  }

  // ---- gift NPCs ----
  const giftLayer = L.layerGroup();
  const giftHits = [];  // {ll, gift}
  for (const gift of (world.gifts || [])) {
    const ll = W2LL(gift.gx, gift.gy);
    const sp = world.sprites && world.sprites[gift.gfx];
    if (sp) {
      const sw = sp.w, sh = sp.h;
      const file = (sp.dirs && (sp.dirs[gift.dir] || sp.dirs.down)) || sp.file;
      const yBot = gift.gy + TILE / 2;
      L.imageOverlay("img/sprites/" + file,
        [W2LL(gift.gx - sw / 2, yBot), W2LL(gift.gx + sw / 2, yBot - sh)],
        { className: "sprite", interactive: false }).addTo(giftLayer);
    } else {
      L.circleMarker(ll, {
        radius: 5, color: "#004d33", weight: 1.5,
        fillColor: "#2ecc71", fillOpacity: 0.9,
        interactive: false, renderer: canvas,
      }).addTo(giftLayer);
    }
    // Gift badge
    L.marker(ll, {
      interactive: false,
      icon: L.divIcon({ className: "gift-badge", html: "🎁", iconSize: [0, 0] }),
    }).addTo(giftLayer);
    giftHits.push({ ll, gift });
  }

  // ---- map labels ----
  const labelLayer = L.layerGroup();
  for (const m of world.maps) {
    L.marker(W2LL(m.x + m.w / 2, m.y + m.h / 2), {
      interactive: false,
      icon: L.divIcon({
        className: "map-label", html: prettify(m.id),
        iconSize: [0, 0],
      }),
    }).addTo(labelLayer);
  }

  warpLayer.addTo(map);
  trainerLayer.addTo(map);
  itemLayer.addTo(map);
  giftLayer.addTo(map);

  // ---- toggles ----
  const bind = (id, layer) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", () => {
      if (el.checked) layer.addTo(map); else map.removeLayer(layer);
    });
  };
  bind("t-trainers", trainerLayer);
  bind("t-items", itemLayer);
  bind("t-hidden", hiddenLayer);
  bind("t-warps", warpLayer);
  bind("t-labels", labelLayer);
  bind("t-gifts", giftLayer);

  const giftCount = (world.gifts || []).length;
  const martCount = Object.keys(world.marts || {}).length;
  document.getElementById("counts").innerHTML =
    `${world.maps.length} maps · ${world.trainers.length} trainers<br>` +
    `${world.items.length} items (${world.items.filter(i => i.hidden).length} hidden)<br>` +
    `${martCount} marts · ${giftCount} gift NPCs`;

  document.getElementById("panel-toggle").addEventListener("click", () => {
    document.getElementById("panel").classList.toggle("open");
  });

  document.getElementById("loading").style.display = "none";

  // Briefly pulse a ring at a location so a deep-linked target is easy to spot.
  function pulseAt(ll) {
    const pm = L.circleMarker(ll, {
      radius: 7, color: "#ffd54a", weight: 3,
      fillColor: "#ffd54a", fillOpacity: 0.35, interactive: false,
    }).addTo(map);
    let r = 7, grow = true, n = 0;
    const iv = setInterval(() => {
      r += grow ? 3 : -3;
      if (r >= 22) grow = false;
      else if (r <= 7) grow = true;
      pm.setRadius(r);
      if (++n > 26) { clearInterval(iv); map.removeLayer(pm); }
    }, 80);
  }

  // Make a layer visible and tick its toggle (deep-links may target a layer
  // the user has turned off — e.g. hidden items).
  function ensureLayer(layer, toggleId) {
    if (!map.hasLayer(layer)) layer.addTo(map);
    const cb = document.getElementById(toggleId);
    if (cb) cb.checked = true;
  }

  // Pan/zoom to a specific map and snap to what the deep-link asked for:
  //   opts.item  -> the exact item-ball/hidden-item of that item id
  //   opts.gift  -> the gift NPC on that map (optionally giving that item)
  //   opts.mart  -> the map's Poké Mart popup
  // Falls back to the map's wild-encounter popup.
  function focusMap(id, opts) {
    opts = opts || {};
    const m = world.maps.find((mm) => mm.id === id);
    if (!m) return false;

    // Snap to a specific item ball / hidden item on this map.
    if (opts.item) {
      const want = "ITEM_" + opts.item;
      const hit = world.items.find((it) => it.mapId === id && it.item === want)
                || world.items.find((it) => it.mapId === id && it.item === opts.item);
      if (hit) {
        ensureLayer(hit.hidden ? hiddenLayer : itemLayer,
                    hit.hidden ? "t-hidden" : "t-items");
        const ll = W2LL(hit.gx, hit.gy);
        map.setView(ll, 2, { animate: true });
        objPopup.setLatLng(ll).setContent(itemPopup(hit)).openOn(map);
        pulseAt(ll);
        return true;
      }
    }

    // Snap to a gift NPC on this map.
    if (opts.gift) {
      const g = (world.gifts || []).find((gg) => gg.mapId === id);
      if (g) {
        ensureLayer(giftLayer, "t-gifts");
        const ll = W2LL(g.gx, g.gy);
        map.setView(ll, 2, { animate: true });
        objPopup.setLatLng(ll).setContent(giftPopup(g)).openOn(map);
        pulseAt(ll);
        return true;
      }
    }

    // Otherwise frame the whole map and open the most relevant popup.
    const bounds = L.latLngBounds(W2LL(m.x, m.y), W2LL(m.x + m.w, m.y + m.h));
    map.fitBounds(bounds.pad(0.3), { maxZoom: 2, animate: true });
    const center = W2LL(m.x + m.w / 2, m.y + m.h / 2);
    if (world.marts && world.marts[id]) {
      objPopup.setLatLng(center).setContent(martPopup(world.marts[id])).openOn(map);
    } else {
      encPopup.setLatLng(center).setContent(encounterPopup(m)).openOn(map);
    }
    return true;
  }

  window.bpe = { map, world, W2LL, focusMap };

  // Honour ?map=MAP_ID (+ optional &item=/&gift=/&mart=) — clicking a location
  // in the Pokédex / item pages deep-links here.
  const params = new URLSearchParams(location.search);
  const focusId = params.get("map");
  if (focusId) {
    // Defer so the initial world fitBounds/layout settles first, then fly in.
    setTimeout(() => focusMap(focusId, {
      item: params.get("item"),
      gift: params.get("gift"),
      mart: params.get("mart"),
    }), 0);
  }
}

main().catch(e => {
  document.getElementById("loading").textContent = "Failed to load: " + e;
  console.error(e);
});
