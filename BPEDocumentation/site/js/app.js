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
    .replace(/^(Tm|Hm) /, (w) => w.toUpperCase())  // "TM Psychic", not "Tm"
    .replace(/([A-Za-z])(\d)/g, "$1 $2");  // "Route102" -> "Route 102"
}

// Detail-panel deep links. The Pokémon/item pages are keyed by the species/item
// id (the constant without its prefix). The build writes each mon's menu-icon as
// "<ID>.png", which is the most reliable species id — trainer parties store a
// display name ("Bronzong"), not a constant, so the sprite name is preferred.
function monPageId(m) {
  if (m && m.sprite) return m.sprite.replace(/\.[a-z0-9]+$/i, "");
  if (m && /^SPECIES_/.test(m.species || "")) return m.species.replace(/^SPECIES_/, "");
  return null;
}
function itemPageId(itemConst) {
  return (itemConst || "").replace(/^ITEM_/, "");
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
  // Curated, like gift notes: who a post-game challenger is.
  if (t.note) html += `<div class="enc-note trainer-note">${t.note}</div>`;
  // Some trainers stay on the map as a shop once beaten.
  if (t.shop && t.shop.length) {
    html += `<div class="trainer-shop"><div class="mart-cond">🛒 Becomes a shop once beaten</div>` +
      `<div class="mart-list">${t.shop.map(it => itemRow(it, 1)).join("")}</div></div>`;
  }
  for (const m of t.party || []) {
    // Trainer mons deep-link into the damage calculator: clicking loads this
    // exact set onto the defender side (see js/calc_deeplink.js).
    const desc = encodeURIComponent(JSON.stringify({
      s: m.species, l: m.level,
      c: t.class || "", tn: t.name || "", m: m.moves || [],
    }));
    const href = `calc.html#mon=${desc}`;
    const tip = `Open ${prettify(m.species)} in the damage calculator`;
    const iconImg = m.sprite
      ? `<img class="mon-icon" src="img/pokemon/${m.sprite}" alt="" ` +
        `loading="lazy" onerror="this.remove()">`
      : "";
    const icon = iconImg
      ? `<a class="mon-icon-link" href="${href}" title="${tip}">${iconImg}</a>`
      : iconImg;
    const name =
      `<a class="mon-name-link" href="${href}" title="${tip}">${prettify(m.species)}</a>`;
    html += `<div class="mon">${icon}<div class="mon-body">` +
      `<div class="mon-head">${name}` +
      `<span class="mon-lvl"> · ${m.standardLevel && m.standardLevel !== m.level
        ? `(nuz:${m.level}) [std:${m.standardLevel}]` : `Lv ${m.level}`}</span></div>`;
    const meta = [];
    if (m.item) meta.push("@ " + m.item);
    if (m.ability) meta.push(m.ability);
    if (m.nature) meta.push(m.nature);
    if (meta.length) html += `<div class="mon-meta">${meta.join(" · ")}</div>`;
    // A Pokémon with no authored moves knows its level-up moves, so a
    // different Standard level can give it different ones.
    const moveRow = (moves, mode) => `<div class="mon-moves">` +
      (mode ? `<span class="mon-moves-mode">${mode}</span>` : "") +
      moves.map(mv => `<span class="move">${mv}</span>`).join("") +
      `</div>`;
    if (m.standardMoves) {
      html += moveRow(m.moves, "nuz") + moveRow(m.standardMoves, "std");
    } else if (m.moves && m.moves.length) {
      html += moveRow(m.moves);
    }
    html += `</div></div>`;  // close .mon-body, .mon
  }
  return html;
}

function itemIconUrl(itemConst) {
  const key = (itemConst || "").replace(/^ITEM_/, "").toLowerCase();
  return `sprites/items/${key}.png`;
}

function itemRow(itemConst, qty, trailing = "") {
  const name = prettify(itemConst);
  const id = itemPageId(itemConst);
  const icon = `<img class="pop-item-icon" src="${itemIconUrl(itemConst)}" `
    + `alt="" onerror="this.style.visibility='hidden'" loading="lazy">`;
  const qtyStr = qty > 1 ? `<span class="pop-item-qty">×${qty}</span>` : "";
  const inner = `${icon}<span class="pop-item-name">${name}</span>${qtyStr}${trailing}`;
  return id
    ? `<a class="pop-item-row" href="item.html?id=${encodeURIComponent(id)}">${inner}</a>`
    : `<div class="pop-item-row">${inner}</div>`;
}

function itemPopup(it) {
  const tag = it.hidden ? "<small>Hidden item</small>" : "<small>Item Ball</small>";
  const id = itemPageId(it.item);
  const icon = `<img class="pop-item-icon" src="${itemIconUrl(it.item)}" alt="" onerror="this.style.visibility='hidden'">`;
  const headInner = `${icon}<span class="item-pop-name">${prettify(it.item)}</span>`;
  const href = id ? `item.html?id=${encodeURIComponent(id)}` : null;
  const head = href
    ? `<a class="item-pop-head" href="${href}">${headInner}</a>` : headInner;
  const link = href
    ? `<a class="pop-item-link" href="${href}">View item details →</a>` : "";
  return `<div class="item-pop">${tag}${head}</div>${link}`;
}

// A Game Corner prize: an item (linked, like a mart row) or a decoration
// (no item page), with its price in coins.
function prizeRow(p) {
  const price = `<span class="pop-item-qty">${p.coins.toLocaleString()} coins</span>`;
  if (p.item) return itemRow(p.item, 1, price);
  // A Pokémon doll borrows that Pokémon's menu icon.
  const mon = (p.decoration || "").match(/^DECOR_(\w+)_DOLL$/);
  const icon = mon
    ? `<img class="pop-item-icon" src="img/pokemon/${mon[1]}.png" alt="" ` +
      `onerror="this.style.visibility='hidden'" loading="lazy">`
    : `<span class="pop-item-icon"></span>`;
  return `<div class="pop-item-row">${icon}` +
         `<span class="pop-item-name">${p.name}</span>${price}</div>`;
}

function martPopup(mart) {
  // Dedicated Poké Mart maps carry no title; NPC vendors (department stores,
  // the Herb Shop, post-game shop NPCs) supply their own.
  const icon = mart.kind === "prizes" ? "🎰" : "🛒";
  let html = `<div class="mart-head">${icon} ${mart.title || mart.name + " Poké Mart"}</div>`;
  let lastVendor = null;
  for (const inv of mart.inventories) {
    if (inv.vendor && inv.vendor !== lastVendor) {
      html += `<div class="mart-vendor">${inv.vendor}</div>`;
      lastVendor = inv.vendor;
    }
    html += `<div class="mart-cond">${inv.condition}</div>`;
    html += `<div class="mart-list">`;
    if (inv.prizes) {
      for (const p of inv.prizes) html += prizeRow(p);
    } else {
      for (const item of inv.items) html += itemRow(item, 1);
    }
    html += `</div>`;
  }
  if (mart.coinSales && mart.coinSales.length) {
    html += `<div class="mart-vendor">Coins</div><div class="mart-list">`;
    for (const s of mart.coinSales) {
      html += `<div class="pop-item-row"><span class="pop-item-icon"></span>` +
              `<span class="pop-item-name">${s.coins.toLocaleString()} coins</span>` +
              `<span class="pop-item-qty">₽${s.price.toLocaleString()}</span></div>`;
    }
    html += `</div>`;
  }
  return html;
}

// A map can be both a shop and a wild-encounter area — Slateport's market
// stalls, the post-game vendors on the Pokémon League approach — so show
// whichever of the two it actually has instead of letting the shop hide the
// encounter list.
function mapPopup(m, marts) {
  const mart = marts && marts[m.id];
  if (!mart) return { title: "Wild Pokémon", html: encounterPopup(m) };
  const shop = mart.kind === "prizes" ? "Prize Corner" : "Poké Mart";
  if (!m.enc) return { title: shop, html: martPopup(mart) };
  return { title: "Shop & Wild Pokémon",
           html: martPopup(mart) + encounterPopup(m) };
}

// Curated "this moved in BPE" signpost. `goto` renders a button the click
// handler wires up to focusMap, so one note can hand off to the next.
function guidePopup(g) {
  let html = `<div class="guide-head">🧭 ${g.title}</div>`;
  html += `<div class="guide-body">${g.body}</div>`;
  if (g.goto && g.goto.mapId) {
    const label = g.goto.label || `Go to ${prettify(g.goto.mapId)}`;
    html += `<button type="button" class="guide-goto"` +
            ` data-map="${g.goto.mapId}"` +
            ` data-guide="${g.goto.guide || ""}">${label} →</button>`;
  }
  return html;
}

// Older exports only contain multi-item care packages; newer ones also carry
// single-item NPC gifts (HMs, TMs, key items).
function giftKind(gift) {
  return gift.carePackage === false ? "Gift" : "Care Package";
}

function giftPopup(gift) {
  let html = `<div class="gift-head">🎁 ${prettify(gift.mapId)} ${giftKind(gift)}</div>`;
  // Curated, like guide bodies: how to make a hidden gift NPC appear.
  if (gift.note) html += `<div class="enc-note gift-note">${gift.note}</div>`;
  html += `<div class="gift-items">`;
  for (const gi of gift.items) {
    html += itemRow(gi.item, gi.qty);
  }
  html += `</div>`;
  return html;
}

// Scripted one-off encounters (legendaries, Snorlax, Kecleon...). The
// pre-Elite Four group size comes from this release's export.
function staticKind(st) {
  if (st.preE4) return "Pre-Elite Four Legendary";
  return st.legendary ? "Legendary Pokémon" : "Static Pokémon";
}

function staticPopup(st, preE4Count) {
  const id = monPageId(st);
  const name = prettify(st.species);
  const nameHtml = id
    ? `<a class="mon-name-link" href="pokemon.html?id=${encodeURIComponent(id)}">${name}</a>`
    : name;
  let html = `<div class="tcard-head">${encSprite(st)}<div class="tcard-id">` +
    `<div class="tcard-name">${nameHtml}</div>` +
    `<div class="tcard-class">Lv ${st.level} · ${st.place || prettify(st.mapId)}</div></div></div>`;
  if (st.preE4) {
    html += `<div class="enc-note static-rule"><b>Pre-Elite Four pick:</b> one of ${preE4Count} ` +
      `legendaries that are limited before you become Champion.` +
      ` <a href="features.html#legendaries">Legendary rules →</a></div>`;
  }
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
      const id = monPageId(m);
      const cellInner = encSprite(m) + `<span class="enc-sp">${prettify(m.species)}</span>`;
      const cell = id
        ? `<a class="enc-mon" href="pokemon.html?id=${encodeURIComponent(id)}">${cellInner}</a>`
        : `<span class="enc-mon">${cellInner}</span>`;
      return `<div class="enc-row">${cell}` +
        `<span class="enc-pct">${m.pct}%</span>` +
        `<span class="enc-lvl">${lvl}</span></div>`;
    }).join("");
}

// Mirage Island legendary pool: no fixed encounter rate — one random uncaught
// legendary from the pool is present each visit, so show the whole pool with a
// "random" tag instead of a percentage.
function mirageRows(mons) {
  return mons
    .map(m => {
      const id = monPageId(m);
      const cellInner = encSprite(m) + `<span class="enc-sp">${prettify(m.species)}</span>`;
      const cell = id
        ? `<a class="enc-mon" href="pokemon.html?id=${encodeURIComponent(id)}">${cellInner}</a>`
        : `<span class="enc-mon">${cellInner}</span>`;
      return `<div class="enc-row">${cell}<span class="enc-pct enc-rand">random</span></div>`;
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
  if (e.mirage && e.mirage.mons && e.mirage.mons.length) {
    html += `<div class="enc-cat">✨ Mirage Island Legendary` +
      `<span class="enc-rate"> · Lv ${e.mirage.level}</span></div>`;
    html += `<div class="enc-note">After you become Champion, Mirage Island always ` +
      `appears off Route 130 and hosts <b>one legendary at a time</b>, picked at ` +
      `<b>random</b> from the pool below — so which one you meet is a random chance ` +
      `every visit. It's always one you haven't caught yet; leave and return to ` +
      `re-roll. Catch it and it leaves the pool. Evolving or hatching one doesn't ` +
      `count: a Cosmog you catch leaves Cosmoem, Solgaleo and Lunala on the island.</div>`;
    html += mirageRows(e.mirage.mons);
  }
  return html;
}

async function main() {
  // A documentation correction can update this release's renderer and assets.
  const world = await fetch("js/data/world.json", { cache: "no-cache" }).then(r => r.json());
  const TILE = world.tile || 16;

  const map = L.map("map", {
    crs: L.CRS.Simple,
    zoomControl: false,
    minZoom: -6,
    maxZoom: 4,
    zoomSnap: 0,
    bounceAtZoomLimits: false,
    wheelPxPerZoomLevel: 80,
    preferCanvas: true,
    // Pinch frames draw directly into bounded canvases; avoid CSS surface scaling.
    zoomAnimation: false,
    fadeAnimation: false,
    markerZoomAnimation: false,
    attributionControl: false,
    maxBoundsViscosity: 0.6,
  });

  const overview = world.overview;
  const terrainImages = BPEWorldImages.renderer(overview && {
    url: overview.url,
    bounds: L.latLngBounds(W2LL(overview.x, overview.y), W2LL(overview.x + overview.w, overview.y + overview.h)),
    detailZoom: overview.detailZoom,
  }, { budget: 32 * 1024 * 1024 });
  const spriteImages = BPEWorldImages.renderer();

  // ---- map images ----
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const m of world.maps) {
    const bounds = [W2LL(m.x, m.y), W2LL(m.x + m.w, m.y + m.h)];
    BPEWorldImages.image("img/maps/" + m.img, bounds, terrainImages, {
      className: "map-img", interactive: false,
    }).addTo(map);
    minX = Math.min(minX, m.x); minY = Math.min(minY, m.y);
    maxX = Math.max(maxX, m.x + m.w); maxY = Math.max(maxY, m.y + m.h);
  }

  // Map clicks open the encounter menu. A single map-level handler is used
  // (rather than per-overlay popups) because the marker canvas sits above the
  // image overlays and would otherwise swallow their click events.

  // ---- detail panel ----------------------------------------------------------
  // Object/encounter details render in a custom panel (#detail) instead of
  // Leaflet popups: a roomy floating card on desktop, a full-screen sheet on
  // mobile. Far easier to read than the cramped anchored bubbles.
  const detailRoot = document.getElementById("detail");
  const detailBody = document.getElementById("detail-body");
  const detailKind = document.getElementById("detail-kind");
  let detailHideTimer = null;
  let openStack = null;
  let selectionOutline = null;
  // What the panel shows, so returning to the map can reopen it (see saveView).
  let selection = null;
  let restoring = false;
  const isPhone = () => window.matchMedia("(max-width: 640px)").matches;

  function spriteBoundsAt(gx, gy, sp) {
    const sw = sp ? sp.w : TILE, sh = sp ? sp.h : TILE;
    const yBot = gy + TILE / 2;
    return [W2LL(gx - sw / 2, yBot), W2LL(gx + sw / 2, yBot - sh)];
  }

  function selectBounds(bounds) {
    if (selectionOutline) {
      map.removeLayer(selectionOutline);
      selectionOutline = null;
    }
    if (!bounds) return;
    selectionOutline = L.rectangle(L.latLngBounds(bounds).pad(0.1), {
      color: "#a855f7",
      weight: 3,
      opacity: 1,
      fillColor: "#c084fc",
      fillOpacity: 0.12,
      interactive: false,
    }).addTo(map).bringToFront();
  }

  // Pan a point target into the open area beside the desktop card so it isn't
  // hidden behind it. No-op on phones (the sheet covers the map anyway).
  function revealAt(ll) {
    if (isPhone() || restoring) return;
    const size = map.getSize();
    const cardReserve = 408;                 // card width + margins, in px
    const z = map.getZoom();
    const cur = map.latLngToContainerPoint(ll);
    const want = L.point((size.x - cardReserve) / 2, size.y / 2);
    if (Math.abs(cur.x - want.x) < 40 && Math.abs(cur.y - want.y) < 40) return;
    const off = want.subtract(L.point(size.x / 2, size.y / 2));
    map.panTo(map.unproject(map.project(ll, z).subtract(off), z),
              { animate: true, duration: 0.4 });
  }

  function updateDetail(kind, html) {
    detailKind.textContent = kind || "";
    detailBody.innerHTML = html;
    detailBody.scrollTop = 0;
  }

  // Open (or re-target) the panel and outline the selected map object.
  function openDetail(kind, html, ll, selectionBounds, sel) {
    if (detailHideTimer) { clearTimeout(detailHideTimer); detailHideTimer = null; }
    selection = sel || null;
    saveView();
    updateDetail(kind, html);
    detailRoot.hidden = false;
    detailRoot.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => detailRoot.classList.add("open"));
    selectBounds(selectionBounds);
    if (ll) revealAt(ll);
    return detailBody;
  }

  function closeDetail() {
    detailRoot.classList.remove("open");
    detailRoot.setAttribute("aria-hidden", "true");
    openStack = null;
    selection = null;
    saveView();
    selectBounds(null);
    detailHideTimer = setTimeout(() => { detailRoot.hidden = true; }, 220);
  }

  detailRoot.addEventListener("click", (ev) => {
    if (ev.target.closest("[data-detail-close]")) closeDetail();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !detailRoot.hidden) closeDetail();
  });

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
  const spriteHoverHits = [];

  function addSpriteHover(layer, hitBounds, displayBounds, stack, priority) {
    const b = L.latLngBounds(hitBounds);
    spriteHoverHits.push({
      layer,
      x0: b.getWest(), x1: b.getEast(),
      yTop: -b.getNorth(), yBot: -b.getSouth(),
      bounds: displayBounds,
      stack: stack || null,
      priority,
    });
  }

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

  function staticAt(latlng) {
    if (!map.hasLayer(staticLayer)) return null;
    const p = map.latLngToContainerPoint(latlng);
    let best = null, bestD = 18;
    for (const h of staticHits) {
      const d = p.distanceTo(map.latLngToContainerPoint(h.ll));
      if (d < bestD) { bestD = d; best = h.st; }
    }
    return best;
  }

  function openStatic(st) {
    const bounds = spriteBoundsAt(st.gx, st.gy, STATIC_ICON);
    openDetail(staticKind(st), staticPopup(st, preE4Count),
      L.latLngBounds(bounds).getCenter(), bounds,
      { k: "static", i: statics.indexOf(st) });
  }

  function guideAt(latlng) {
    if (!map.hasLayer(guideLayer)) return null;
    const p = map.latLngToContainerPoint(latlng);
    let best = null, bestD = 22;   // matches the 36px marker
    for (const h of guideHits) {
      const d = p.distanceTo(map.latLngToContainerPoint(h.ll));
      if (d < bestD) { bestD = d; best = h.guide; }
    }
    return best;
  }

  // Open a guide note and wire its "take me there" button to focusMap.
  function openGuide(g) {
    const sp = g.gfx && world.sprites && world.sprites[g.gfx];
    const bounds = spriteBoundsAt(g.gx, g.gy, sp);
    openDetail("Guide", guidePopup(g), L.latLngBounds(bounds).getCenter(), bounds,
      { k: "guide", i: world.guides.indexOf(g) });
    const btn = detailBody.querySelector(".guide-goto");
    if (btn) btn.addEventListener("click", (ev) => {
      ev.preventDefault();
      focusMap(btn.dataset.map, { guide: btn.dataset.guide || null });
    });
  }

  // show a trainer stack's current member; cycle via the marker or the button.
  // firstOpen=true pans/pulses the location; cycling just swaps the content.
  function showStack(st, firstOpen, gift) {
    const t = st.trainers[st.idx];
    renderStack(st);                          // map sprite matches the panel
    const sp = spriteFor(t);
    const n = st.trainers.length;
    const nav = n > 1
      ? `<div class="stack-nav">Trainer ${st.idx + 1} / ${n}` +
        `<button type="button" class="stack-cycle">Next ▸</button></div>`
      : "";
    const html = nav + trainerPopup(world.trainerData[t.trainerId], sp.file)
      + (gift ? giftPopup(gift) : "");
    const title = gift ? "Trainer & " + giftKind(gift) : "Trainer";
    const sel = { k: "trainer", gx: st.gx, gy: st.gy, idx: st.idx,
                  gift: gift ? world.gifts.indexOf(gift) : -1 };
    if (firstOpen) {
      const bounds = sp.bounds;
      openDetail(title, html, L.latLngBounds(bounds).getCenter(), bounds, sel);
    } else {
      updateDetail(title, html);
      selectBounds(sp.bounds);
      selection = sel;
      saveView();
    }
    if (n > 1) {
      const btn = detailBody.querySelector(".stack-cycle");
      if (btn) btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        st.idx = (st.idx + 1) % n;
        showStack(st, false, gift);
      });
    }
  }

  map.on("click", (e) => {
    // priority: warp endpoint -> trainer sprite -> item -> map encounters
    const target = warpEndAt(e.latlng);
    if (target) { flyTarget(target); return; }
    const x = e.latlng.lng, y = -e.latlng.lat;
    const gf = giftAt(e.latlng);
    const hit = trainerAt(x, y);
    if (hit) {
      const st = hit.stack;
      const coLocatedGift = gf
        && Math.abs(gf.gx - st.gx) < 1
        && Math.abs(gf.gy - st.gy) < 1 ? gf : null;
      if (st === openStack)                  // tapping the same marker cycles
        st.idx = (st.idx + 1) % st.trainers.length;
      openStack = st;
      showStack(st, true, coLocatedGift);
      return;
    }
    openStack = null;
    const gd = guideAt(e.latlng);
    if (gd) {
      openGuide(gd);
      return;
    }
    const sw = staticAt(e.latlng);
    if (sw) {
      openStatic(sw);
      return;
    }
    const it = itemAt(e.latlng);
    if (it) {
      openItem(it);
      return;
    }
    if (gf) {
      openGift(gf);
      return;
    }
    const m = mapAt(x, y);
    if (!m) return;
    openMapPopup(m, e.latlng);
  });

  function openItem(it) {
    const bounds = spriteBoundsAt(it.gx, it.gy, it.hidden ? null : ballSprite);
    openDetail("Item", itemPopup(it), L.latLngBounds(bounds).getCenter(), bounds,
      { k: "item", i: world.items.indexOf(it) });
  }

  function openGift(g) {
    const sp = world.sprites && world.sprites[g.gfx];
    const bounds = spriteBoundsAt(g.gx, g.gy, sp);
    openDetail(giftKind(g), giftPopup(g), L.latLngBounds(bounds).getCenter(), bounds,
      { k: "gift", i: world.gifts.indexOf(g) });
  }

  function openMapPopup(m, ll) {
    const pop = mapPopup(m, world.marts);
    openDetail(pop.title, pop.html, ll, null, { k: "map", id: m.id });
  }
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
  const cancelFlight = () => { ++flyToken; };
  map.on("dragstart zoomstart", cancelFlight);
  map.getContainer().addEventListener("touchstart", cancelFlight, { passive: true });
  map.getContainer().addEventListener("pointerdown", cancelFlight, { passive: true });
  function flyTarget(ll) {
    const z = map.getZoom();          // keep the current zoom; pan only
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      cancelFlight();
      map.setView(ll, z, { animate: false });
      return;
    }
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
      st.overlay = BPEWorldImages.image("img/sprites/" + sp.file, sp.bounds, spriteImages,
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
    if (st.overlay) {
      addSpriteHover(trainerLayer,
        [W2LL(st.gx - maxW / 2, yBot),
         W2LL(st.gx + maxW / 2, yBot - maxH)],
        sp.bounds, st, 0);
    }
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
      BPEWorldImages.image("img/sprites/" + file, bounds, spriteImages, {
        className: "sprite item-ball-sprite", interactive: false,
      }).addTo(itemLayer);
      addSpriteHover(itemLayer, bounds, bounds, null, 2);
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
      const file = (sp.dirs && (sp.dirs[gift.dir] || sp.dirs.down)) || sp.file;
      const bounds = spriteBoundsAt(gift.gx, gift.gy, sp);
      BPEWorldImages.image("img/sprites/" + file, bounds, spriteImages,
        { className: "sprite", interactive: false }).addTo(giftLayer);
      addSpriteHover(giftLayer, bounds, bounds, null, 3);
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

  // ---- static encounters (legendaries etc.) ----
  // Menu icons share the bounded sprite renderer with the overworld sprites.
  const staticLayer = L.layerGroup();
  const staticHits = [];  // {ll, st}
  const STATIC_ICON = { w: 32, h: 32 };
  const statics = world.statics || [];
  const preE4Count = statics.filter(st => st.preE4).length;
  for (const st of statics) {
    const ll = W2LL(st.gx, st.gy);
    const bounds = spriteBoundsAt(st.gx, st.gy, STATIC_ICON);
    if (st.sprite) {
      BPEWorldImages.image("img/pokemon/" + st.sprite, bounds, spriteImages,
        { className: "sprite", interactive: false }).addTo(staticLayer);
      addSpriteHover(staticLayer, bounds, bounds, null, 1);
    } else {
      L.circleMarker(ll, {
        radius: 6, color: "#3b1d00", weight: 1.5,
        fillColor: "#f5b82e", fillOpacity: 0.95,
        interactive: false, renderer: canvas,
      }).addTo(staticLayer);
    }
    if (st.preE4 || st.legendary) {
      L.marker(ll, {
        interactive: false,
        icon: L.divIcon({ className: "static-badge", html: '<span class="static-star">★</span>', iconSize: [0, 0] }),
      }).addTo(staticLayer);
    }
    staticHits.push({ ll, st });
  }

  // ---- guide notes ----
  const guideLayer = L.layerGroup();
  const guideHits = [];  // {ll, guide}
  for (const g of (world.guides || [])) {
    const ll = W2LL(g.gx, g.gy);
    const sp = g.gfx && world.sprites && world.sprites[g.gfx];
    if (sp) {
      const file = (sp.dirs && (sp.dirs[g.dir] || sp.dirs.down)) || sp.file;
      const bounds = spriteBoundsAt(g.gx, g.gy, sp);
      BPEWorldImages.image("img/sprites/" + file, bounds, spriteImages,
        { className: "sprite guide-sprite", interactive: false }).addTo(guideLayer);
      addSpriteHover(guideLayer, bounds, bounds, null, 1);
    } else {
      // The glyph lives in an inner span: Leaflet drives the outer div's
      // `transform` for positioning, so nothing may animate transform on it.
      L.marker(ll, {
        interactive: false,
        icon: L.divIcon({
          className: "guide-badge",
          html: '<span class="guide-mark">?</span>',
          iconSize: [36, 36],
          iconAnchor: [18, 18],
        }),
      }).addTo(guideLayer);
    }
    guideHits.push({ ll, guide: g });
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
  staticLayer.addTo(map);
  guideLayer.addTo(map);

  // Hover feedback uses world-space sprite rectangles and is throttled to one
  // update per animation frame, avoiding hundreds of DOM pointer listeners.
  let hoveredSprite = null;
  let hoverOutline = null;
  let hoverFrame = null;
  let hoverLatLng = null;
  let hoverSuspended = false;

  function spriteHoverAt(x, y) {
    let best = null, bestD = Infinity;
    for (const hit of spriteHoverHits) {
      if (!map.hasLayer(hit.layer)) continue;
      if (x < hit.x0 || x > hit.x1 || y < hit.yTop || y > hit.yBot) continue;
      const dx = x - (hit.x0 + hit.x1) / 2;
      const dy = y - (hit.yTop + hit.yBot) / 2;
      const d = dx * dx + dy * dy;
      if (d < bestD || (d === bestD && hit.priority < best.priority)) {
        best = hit;
        bestD = d;
      }
    }
    return best;
  }

  function setHovered(hit) {
    if (hit === hoveredSprite) return;
    if (hoverOutline) {
      map.removeLayer(hoverOutline);
      hoverOutline = null;
    }
    hoveredSprite = hit;
    map.getContainer().classList.toggle("sprite-hover", Boolean(hit));
    if (!hit) return;
    const bounds = hit.stack
      ? spriteFor(hit.stack.trainers[hit.stack.idx]).bounds
      : hit.bounds;
    hoverOutline = L.rectangle(L.latLngBounds(bounds).pad(0.1), {
      color: "#e9d5ff",
      weight: 2,
      opacity: 1,
      fillColor: "#e9d5ff",
      fillOpacity: 0.06,
      interactive: false,
    }).addTo(map).bringToFront();
    if (selectionOutline) selectionOutline.bringToFront();
  }

  function clearHovered() {
    hoverLatLng = null;
    if (hoverFrame !== null) {
      cancelAnimationFrame(hoverFrame);
      hoverFrame = null;
    }
    setHovered(null);
  }

  map.on("mousemove", (e) => {
    if (hoverSuspended) return;
    hoverLatLng = e.latlng;
    if (hoverFrame !== null) return;
    hoverFrame = requestAnimationFrame(() => {
      hoverFrame = null;
      if (!hoverLatLng || hoverSuspended) return;
      setHovered(spriteHoverAt(hoverLatLng.lng, -hoverLatLng.lat));
    });
  });
  map.on("mouseout", clearHovered);
  map.on("movestart", () => {
    hoverSuspended = true;
    map.getContainer().classList.add("map-moving");
    clearHovered();
  });
  map.on("moveend", () => {
    hoverSuspended = false;
    map.getContainer().classList.remove("map-moving");
  });

  // ---- toggles ----
  const toggles = {};
  function showLayer(layer, on) {
    if (on) layer.addTo(map); else map.removeLayer(layer);
  }
  const bind = (id, layer) => {
    const el = document.getElementById(id);
    if (!el) return;
    toggles[id] = { el, layer };
    // Back navigation can restore the checkbox states, so follow them.
    showLayer(layer, el.checked);
    el.addEventListener("change", () => {
      showLayer(layer, el.checked);
      setHovered(null);
      saveView();
    });
  };
  bind("t-trainers", trainerLayer);
  bind("t-items", itemLayer);
  bind("t-hidden", hiddenLayer);
  bind("t-warps", warpLayer);
  bind("t-labels", labelLayer);
  bind("t-gifts", giftLayer);
  bind("t-guides", guideLayer);
  bind("t-statics", staticLayer);

  const giftCount = (world.gifts || []).length;
  const martCount = Object.keys(world.marts || {}).length;
  const guideCount = (world.guides || []).length;
  document.getElementById("counts").innerHTML =
    `${world.maps.length} maps · ${world.trainers.length} trainers<br>` +
    `${world.items.length} items (${world.items.filter(i => i.hidden).length} hidden)<br>` +
    `${martCount} shops · ${giftCount} gifts · ${guideCount} guides` +
    (statics.length ? `<br>${statics.length} static Pokémon` : "");

  document.getElementById("panel-toggle").addEventListener("click", () => {
    document.getElementById("panel").classList.toggle("open");
  });

  document.getElementById("loading").style.display = "none";

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
  //   opts.guide -> a curated guide note (by id, or the first one on the map)
  // Falls back to the map's wild-encounter popup.
  function focusMap(id, opts) {
    opts = opts || {};
    const m = world.maps.find((mm) => mm.id === id);
    if (!m) return false;

    // Snap to a curated guide note — used by the "take me there" hand-off.
    if (opts.guide) {
      const notes = world.guides || [];
      const hit = notes.find((g) => g.id === opts.guide)
               || notes.find((g) => g.mapId === id);
      if (hit) {
        ensureLayer(guideLayer, "t-guides");
        const ll = W2LL(hit.gx, hit.gy);
        // Deliberately unanimated: a guide hand-off usually crosses most of
        // Hoenn, and Leaflet's pan animation stalls over offsets that large
        // under CRS.Simple (same reason flyTarget interpolates by hand).
        map.setView(ll, 2, { animate: false });
        openGuide(hit);
        return true;
      }
    }

    // Snap to a static encounter (?static=SPECIES_ID or the bare id).
    if (opts.static) {
      const want = String(opts.static).replace(/^SPECIES_/, "");
      const hit = statics.find((st) => st.mapId === id
        && st.species.replace(/^SPECIES_/, "") === want);
      if (hit) {
        ensureLayer(staticLayer, "t-statics");
        map.setView(W2LL(hit.gx, hit.gy), 2, { animate: false });
        openStatic(hit);
        return true;
      }
    }

    // Snap to a specific item ball / hidden item on this map.
    if (opts.item) {
      const want = "ITEM_" + opts.item;
      const hit = world.items.find((it) => it.mapId === id && it.item === want)
                || world.items.find((it) => it.mapId === id && it.item === opts.item);
      if (hit) {
        ensureLayer(hit.hidden ? hiddenLayer : itemLayer,
                    hit.hidden ? "t-hidden" : "t-items");
        map.setView(W2LL(hit.gx, hit.gy), 2, { animate: true });
        openItem(hit);
        return true;
      }
    }

    // Snap to the care package on this map that contains the requested item.
    if (opts.gift) {
      const want = String(opts.gift).replace(/^ITEM_/, "");
      const g = (world.gifts || []).find((gg) =>
        gg.mapId === id && (gg.items || []).some((gi) =>
          String(gi.item || "").replace(/^ITEM_/, "") === want));
      if (g) {
        ensureLayer(giftLayer, "t-gifts");
        map.setView(W2LL(g.gx, g.gy), 2, { animate: true });
        openGift(g);
        return true;
      }
    }

    // Otherwise frame the whole map and open the most relevant popup.
    const bounds = L.latLngBounds(W2LL(m.x, m.y), W2LL(m.x + m.w, m.y + m.h));
    map.fitBounds(bounds.pad(0.3), { maxZoom: 2, animate: true });
    openMapPopup(m, W2LL(m.x + m.w / 2, m.y + m.h / 2));
    return true;
  }

  // ---- remembered view ------------------------------------------------------
  // Leaving the map for a Pokémon, item or calculator page and coming back
  // returns to the same spot, zoom, layers and open card. The browser session
  // keeps it, so a new visit still starts on the whole region. The position is
  // shared between releases (their worlds line up); the card is not, because
  // it is stored by index into this release's world data.
  const release = window.BPERelease;
  const viewKey = "bpe:" + (release ? release.siteRoot.pathname : "/") + ":map-view";
  const releaseId = release ? release.id : "";
  let viewReady = false;

  function saveView() {
    if (!viewReady) return;
    const c = map.getCenter();
    const layers = {};
    for (const id in toggles) layers[id] = toggles[id].el.checked;
    const state = { lat: c.lat, lng: c.lng, zoom: map.getZoom(), layers,
                    release: releaseId, sel: selection };
    try { sessionStorage.setItem(viewKey, JSON.stringify(state)); } catch (_) {}
  }

  function loadView() {
    try {
      const state = JSON.parse(sessionStorage.getItem(viewKey));
      if (state && isFinite(state.lat) && isFinite(state.lng) && isFinite(state.zoom))
        return state;
    } catch (_) {}
    return null;
  }

  function reopenSelection(sel) {
    if (!sel) return;
    if (sel.k === "map") {
      const m = world.maps.find((mm) => mm.id === sel.id);
      if (m) openMapPopup(m, null);
    } else if (sel.k === "item" && world.items[sel.i]) {
      openItem(world.items[sel.i]);
    } else if (sel.k === "gift" && world.gifts && world.gifts[sel.i]) {
      openGift(world.gifts[sel.i]);
    } else if (sel.k === "static" && statics[sel.i]) {
      openStatic(statics[sel.i]);
    } else if (sel.k === "guide" && world.guides && world.guides[sel.i]) {
      openGuide(world.guides[sel.i]);
    } else if (sel.k === "trainer") {
      const st = stackMap.get(sel.gx + "," + sel.gy);
      if (!st) return;
      st.idx = sel.idx >= 0 && sel.idx < st.trainers.length ? sel.idx : 0;
      openStack = st;
      showStack(st, true, (world.gifts || [])[sel.gift] || null);
    }
  }

  function restoreView(state) {
    for (const id in state.layers || {}) {
      const t = toggles[id];
      if (!t) continue;
      t.el.checked = Boolean(state.layers[id]);
      showLayer(t.layer, t.el.checked);
    }
    map.setView(L.latLng(state.lat, state.lng), state.zoom, { animate: false });
    if (state.release === releaseId) {
      restoring = true;
      try { reopenSelection(state.sel); } finally { restoring = false; }
    }
  }

  window.bpe = { map, world, W2LL, focusMap, terrainImages, spriteImages };
  window.bpe.performance = BPEMapPerformance(map, [terrainImages, spriteImages]);
  let mapWidth = map.getContainer().clientWidth, mapHeight = map.getContainer().clientHeight;
  window.addEventListener('bpe:headerresize', function () {
    const el = map.getContainer();
    if (el.clientWidth === mapWidth && el.clientHeight === mapHeight) return;
    mapWidth = el.clientWidth; mapHeight = el.clientHeight;
    map.invalidateSize({ pan: false });
  });

  // Honour ?map=MAP_ID (+ optional &item=/&gift=/&mart=) — clicking a location
  // in the Pokédex / item pages deep-links here. Going Back to a deep link
  // returns to where the map was left rather than to the link's target.
  const params = new URLSearchParams(location.search);
  const focusId = params.get("map");
  const navEntry = performance.getEntriesByType
    && performance.getEntriesByType("navigation")[0];
  const saved = loadView();
  viewReady = true;
  map.on("moveend", saveView);
  if (saved && (!focusId || (navEntry && navEntry.type === "back_forward"))) {
    restoreView(saved);
    saveView();
  } else if (focusId) {
    // Defer so the initial world fitBounds/layout settles first, then fly in.
    setTimeout(() => focusMap(focusId, {
      item: params.get("item"),
      gift: params.get("gift"),
      mart: params.get("mart"),
      guide: params.get("guide"),
      static: params.get("static"),
    }), 0);
  }
}

main().catch(e => {
  document.getElementById("loading").textContent = "Failed to load: " + e;
  console.error(e);
});
