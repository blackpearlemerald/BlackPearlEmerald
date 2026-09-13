/* BPE Emerald — global search.
 *
 * Searches across the four content tabs at once — Pokédex, Trainers, Items and
 * the interactive Map (locations) — and links every result straight to its
 * page:
 *   Pokémon   -> pokemon.html?id=<SPECIES>
 *   Item      -> item.html?id=<ITEM>
 *   Trainer   -> trainers.html?focus=<TRAINER_ID>   (auto-expands that card)
 *   Location  -> index.html?map=<MAP_ID>            (flies the map there)
 *
 * Everything runs client-side over the same JSON the individual pages load, so
 * there is nothing new to generate in the build.
 */
(function () {
  'use strict';

  // ── helpers ─────────────────────────────────────────────────────────────────
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function prettifyMap(id) {
    if (!id) return '';
    var s = id.replace(/^MAP_/, '').replace(/_/g, ' ')
      .split(' ').map(function (w) { return w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w; })
      .join(' ');
    return s.replace(/([A-Za-z])(\d)/g, '$1 $2');
  }
  function prettifyType(t) {
    return (t || '').replace(/^MAP_TYPE_/, '').replace(/_/g, ' ')
      .toLowerCase().replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }
  function pad4(n) { return '#' + String(n || 0).padStart(4, '0'); }

  function itemDisplayName(item, moves) {
    var name = item.name || item.id;
    if (item.pocket !== 'POCKET_TM_HM' || !/^(?:TM|HM)\d+$/i.test(name) || !/^(?:TM|HM)_/.test(item.id || '')) {
      return name;
    }

    var moveId = item.id.slice(3);
    var move = moves && moves[moveId];
    var moveName = move && move.name;
    if (!moveName) {
      moveName = moveId.replace(/_/g, ' ').toLowerCase()
        .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }
    return name + ' - ' + moveName;
  }

  // Highlight the matched run of the query within a display name.
  function highlight(name, q) {
    var safe = esc(name);
    if (!q) return safe;
    var i = name.toLowerCase().indexOf(q);
    if (i < 0) return safe;
    var before = esc(name.slice(0, i));
    var hit = esc(name.slice(i, i + q.length));
    var after = esc(name.slice(i + q.length));
    return before + '<mark>' + hit + '</mark>' + after;
  }

  // ── categories ──────────────────────────────────────────────────────────────
  var CATS = [
    { key: 'pokemon',  label: 'Pokémon',   labelOne: 'Pokémon'  },
    { key: 'trainer',  label: 'Trainers',  labelOne: 'Trainer'  },
    { key: 'item',     label: 'Items',     labelOne: 'Item'     },
    { key: 'location', label: 'Locations', labelOne: 'Location' },
  ];
  var CAT_LABEL = {};
  CATS.forEach(function (c) { CAT_LABEL[c.key] = c.labelOne; });

  var PREVIEW = 6;   // rows shown per category in the combined "All" view
  var CAP = 300;     // hard cap on rendered rows per category

  var records = [];
  var totals = { pokemon: 0, trainer: 0, item: 0, location: 0 };
  var state = { q: '', cat: 'all', expanded: {} };
  var firstHref = null;

  // ── build the searchable record list ────────────────────────────────────────
  function buildPokemon(dex) {
    Object.keys(dex).forEach(function (k) {
      var p = dex[k];
      records.push({
        cat: 'pokemon',
        name: p.name || p.id,
        id: p.id,
        sub: pad4(p.natDexNum),
        icon: p.icon || '',
        iconKind: 'mon',
        badges: (p.types || []).map(function (t) {
          return '<span class="type-badge t-' + t + '">' + t.toLowerCase() + '</span>';
        }).join(''),
        href: 'pokemon.html?id=' + encodeURIComponent(p.id),
        hay: (p.id || '').toLowerCase(),
        sortNum: p.natDexNum || 99999,
      });
    });
    totals.pokemon = Object.keys(dex).length;
  }

  function buildItems(items, moves) {
    Object.keys(items).forEach(function (k) {
      var it = items[k];
      var displayName = itemDisplayName(it, moves);
      records.push({
        cat: 'item',
        name: displayName,
        id: it.id,
        sub: it.pocketLabel || '',
        icon: it.icon || '',
        iconKind: 'item',
        badges: '',
        href: 'item.html?id=' + encodeURIComponent(it.id),
        hay: (displayName + ' ' + (it.id || '') + ' ' + (it.description || '')).toLowerCase(),
      });
    });
    totals.item = Object.keys(items).length;
  }

  function buildLocations(world) {
    (world.maps || []).forEach(function (m) {
      records.push({
        cat: 'location',
        name: prettifyMap(m.id),
        id: m.id,
        sub: prettifyType(m.type),
        icon: '',
        iconKind: 'map',
        badges: '',
        href: 'index.html?map=' + encodeURIComponent(m.id),
        hay: (m.id || '').toLowerCase() + ' ' + (m.name || '').toLowerCase(),
      });
    });
    totals.location = (world.maps || []).length;
  }

  function buildTrainers(trainers, world) {
    // Resolve each trainer's first overworld sprite + map locations from world.json,
    // mirroring how the Trainers page does it.
    var locIndex = {}, spriteIndex = {};
    (world.trainers || []).forEach(function (t) {
      if (!locIndex[t.trainerId]) locIndex[t.trainerId] = [];
      if (!locIndex[t.trainerId].some(function (l) { return l.mapId === t.mapId; })) {
        locIndex[t.trainerId].push({ mapId: t.mapId, mapName: prettifyMap(t.mapId) });
      }
      if (!spriteIndex[t.trainerId]) {
        var sp = world.sprites && world.sprites[t.gfx];
        if (sp) {
          var file = (sp.dirs && (sp.dirs[t.dir] || sp.dirs.down)) || sp.file;
          if (file) spriteIndex[t.trainerId] = file;
        }
      }
    });

    var count = 0;
    Object.keys(trainers).forEach(function (id) {
      var t = trainers[id];
      if (id === 'TRAINER_NONE' || !t.party || !t.party.length) return;
      count++;
      var locs = locIndex[id] || [];
      var species = t.party.map(function (m) { return m.species; }).filter(Boolean);
      var subParts = [];
      if (t.class) subParts.push(t.class);
      if (locs.length) subParts.push(locs[0].mapName + (locs.length > 1 ? ' +' + (locs.length - 1) : ''));
      else subParts.push('Script / Battle only');
      records.push({
        cat: 'trainer',
        name: t.name || t.class || id,
        id: id,
        sub: subParts.join(' · '),
        icon: spriteIndex[id] ? 'img/sprites/' + spriteIndex[id] : '',
        iconKind: 'trainer',
        iconFallback: (t.class || '?').slice(0, 1).toUpperCase(),
        badges: t.class ? '<span class="sr-tag-cls">' + esc(t.class) + '</span>' : '',
        href: 'trainers.html?focus=' + encodeURIComponent(id),
        hay: ((t.class || '') + ' ' + species.join(' ')).toLowerCase(),
      });
    });
    totals.trainer = count;
  }

  // ── scoring / matching ──────────────────────────────────────────────────────
  function score(rec, q) {
    var n = rec.name.toLowerCase();
    if (n === q) return 0;
    if (n.indexOf(q) === 0) return 1;
    var words = n.split(/[^a-z0-9]+/);
    for (var i = 0; i < words.length; i++) { if (words[i] && words[i].indexOf(q) === 0) return 2; }
    if (n.indexOf(q) !== -1) return 3;
    if ((rec.id || '').toLowerCase().indexOf(q) !== -1) return 4;
    if (rec.hay && rec.hay.indexOf(q) !== -1) return 5;
    return -1;
  }

  function search(q) {
    var byCat = { pokemon: [], trainer: [], item: [], location: [] };
    for (var i = 0; i < records.length; i++) {
      var r = records[i];
      var s = score(r, q);
      if (s < 0) continue;
      r._s = s;
      byCat[r.cat].push(r);
    }
    Object.keys(byCat).forEach(function (c) {
      byCat[c].sort(function (a, b) {
        if (a._s !== b._s) return a._s - b._s;
        if (a.sortNum != null && b.sortNum != null && a.sortNum !== b.sortNum) return a.sortNum - b.sortNum;
        if (a.name.length !== b.name.length) return a.name.length - b.name.length;
        return a.name < b.name ? -1 : 1;
      });
    });
    return byCat;
  }

  // ── rendering ───────────────────────────────────────────────────────────────
  function rowHtml(r, q) {
    var ic;
    if (r.iconKind === 'map') {
      ic = '<span class="sr-ic sr-ic-map" aria-hidden="true">📍</span>';
    } else if (r.icon) {
      var cls = 'sr-ic sr-ic-' + r.iconKind;
      ic = '<span class="' + cls + '"><img src="' + esc(r.icon) + '" alt="" loading="lazy"'
         + (r.iconKind === 'trainer'
             ? ' onerror="this.parentNode.classList.add(\'sr-ic-ph\');this.remove();" data-ph="' + esc(r.iconFallback || '?') + '"'
             : ' onerror="this.remove()"')
         + '></span>';
    } else if (r.iconKind === 'trainer') {
      ic = '<span class="sr-ic sr-ic-trainer sr-ic-ph" data-ph="' + esc(r.iconFallback || '?') + '"></span>';
    } else {
      ic = '<span class="sr-ic sr-ic-' + r.iconKind + '"></span>';
    }
    return '<a class="sr-row" href="' + r.href + '">'
      + ic
      + '<span class="sr-main">'
      + '<span class="sr-name">' + highlight(r.name, q) + '</span>'
      + (r.sub ? '<span class="sr-sub">' + esc(r.sub) + '</span>' : '')
      + '</span>'
      + (r.badges ? '<span class="sr-badges">' + r.badges + '</span>' : '')
      + '<span class="sr-cat">' + CAT_LABEL[r.cat] + '</span>'
      + '<span class="sr-go" aria-hidden="true">→</span>'
      + '</a>';
  }

  function render() {
    var statusEl = document.getElementById('search-status');
    var resEl = document.getElementById('search-results');
    var q = state.q;
    firstHref = null;

    if (!q) {
      statusEl.textContent = '';
      resEl.innerHTML = idleHtml();
      renderCats(null);
      return;
    }

    var byCat = search(q);
    var counts = {}; var grand = 0;
    Object.keys(byCat).forEach(function (c) { counts[c] = byCat[c].length; grand += byCat[c].length; });
    renderCats(counts);

    if (grand === 0) {
      statusEl.textContent = '';
      resEl.innerHTML = '<div class="sr-empty">No matches for “' + esc(q) + '”.</div>';
      return;
    }

    statusEl.innerHTML = grand + ' result' + (grand !== 1 ? 's' : '')
      + ' for <strong>“' + esc(q) + '”</strong>';

    var html = '';
    var shownCats = state.cat === 'all'
      ? CATS.map(function (c) { return c.key; })
      : [state.cat];

    shownCats.forEach(function (cat) {
      var list = byCat[cat];
      if (!list.length) return;
      if (firstHref == null) firstHref = list[0].href;

      var single = state.cat !== 'all';
      var limit = single ? CAP : (state.expanded[cat] ? CAP : PREVIEW);
      var slice = list.slice(0, limit);
      var meta = CATS.filter(function (c) { return c.key === cat; })[0];

      html += '<section class="sr-group">'
        + '<div class="sr-group-head">'
        + '<h2>' + meta.label + '</h2>'
        + '<span class="sr-group-count">' + list.length + '</span>'
        + '</div>'
        + '<div class="sr-list">'
        + slice.map(function (r) { return rowHtml(r, q); }).join('')
        + '</div>';

      if (!single && list.length > PREVIEW) {
        var isOpen = !!state.expanded[cat];
        html += '<button class="sr-more" data-cat="' + cat + '">'
          + (isOpen ? 'Show less' : 'Show all ' + list.length + ' ' + meta.label.toLowerCase() + ' →')
          + '</button>';
      } else if (single && list.length > CAP) {
        html += '<div class="sr-capnote">Showing first ' + CAP + ' of ' + list.length
          + ' — refine your search to narrow it down.</div>';
      }
      html += '</section>';
    });

    resEl.innerHTML = html;
  }

  function idleHtml() {
    return '<div class="sr-idle">'
      + '<div class="sr-idle-grid">'
      + CATS.map(function (c) {
          return '<div class="sr-idle-cell"><span class="sr-idle-num">'
            + (totals[c.key] || 0) + '</span><span class="sr-idle-lbl">' + c.label + '</span></div>';
        }).join('')
      + '</div>'
      + '<p class="sr-idle-hint">Start typing to search across all of them at once.</p>'
      + '</div>';
  }

  // Category filter chips (with live counts once a query is active).
  function renderCats(counts) {
    var wrap = document.getElementById('search-cats');
    var grand = counts ? Object.keys(counts).reduce(function (a, k) { return a + counts[k]; }, 0) : null;
    var html = '<button class="sr-chip' + (state.cat === 'all' ? ' active' : '') + '" data-cat="all">All'
      + (grand != null ? '<span class="sr-chip-n">' + grand + '</span>' : '') + '</button>';
    CATS.forEach(function (c) {
      var n = counts ? counts[c.key] : null;
      var dis = counts && !n ? ' disabled' : '';
      html += '<button class="sr-chip' + (state.cat === c.key ? ' active' : '') + dis
        + '" data-cat="' + c.key + '">' + c.label
        + (n != null ? '<span class="sr-chip-n">' + n + '</span>' : '') + '</button>';
    });
    wrap.innerHTML = html;
  }

  // ── events ──────────────────────────────────────────────────────────────────
  function wire() {
    var input = document.getElementById('global-search');
    var debounce = null;
    input.addEventListener('input', function () {
      var v = this.value.trim().toLowerCase();
      clearTimeout(debounce);
      debounce = setTimeout(function () {
        if (v === state.q) return;
        state.q = v;
        state.expanded = {};
        // Falling back to "All" when the active single category has no hits keeps
        // results visible instead of showing an empty pane.
        render();
      }, 110);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && firstHref) { window.location.href = firstHref; }
    });

    document.getElementById('search-cats').addEventListener('click', function (e) {
      var btn = e.target.closest('.sr-chip');
      if (!btn || btn.disabled) return;
      state.cat = btn.dataset.cat;
      state.expanded = {};
      render();
      // Scroll results into view on mobile after switching category.
      var res = document.getElementById('search-results');
      if (window.innerWidth <= 640 && res) res.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('search-results').addEventListener('click', function (e) {
      var more = e.target.closest('.sr-more');
      if (!more) return;
      var cat = more.dataset.cat;
      state.expanded[cat] = !state.expanded[cat];
      render();
    });
  }

  // ── bootstrap ───────────────────────────────────────────────────────────────
  function init() {
    wire();
    renderCats(null);

    // Honour ?q= so other pages / the address bar can deep-link a search.
    var qp = new URLSearchParams(location.search).get('q');
    var input = document.getElementById('global-search');
    if (qp) { input.value = qp; }

    Promise.all([
      fetch('data/pokedex_index.json').then(function (r) { return r.json(); }),
      fetch('data/items_index.json').then(function (r) { return r.json(); }),
      fetch('js/data/trainers.json').then(function (r) { return r.json(); }),
      fetch('js/data/world.json').then(function (r) { return r.json(); }),
      fetch('data/moves.json').then(function (r) { return r.json(); }).catch(function () { return {}; }),
    ]).then(function (res) {
      buildPokemon(res[0]);
      buildItems(res[1], res[4]);
      buildTrainers(res[2], res[3]);
      buildLocations(res[3]);
      if (qp) { state.q = qp.trim().toLowerCase(); }
      render();
      input.focus();
    }).catch(function (err) {
      document.getElementById('search-results').innerHTML =
        '<div class="sr-empty">Failed to load search data. Run the build script first.</div>';
      if (window.console) console.error('[bpe search]', err);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
