(function () {
  'use strict';

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

  var state = {
    all: [],
    query: '',
    mapOnly: true,
  };

  function applyFilters() {
    var q = state.query.toLowerCase();
    return state.all.filter(function (t) {
      if (state.mapOnly && t.locs.length === 0) return false;
      if (!q) return true;
      if (t.name.toLowerCase().includes(q)) return true;
      if (t.trClass.toLowerCase().includes(q)) return true;
      if (t.party.some(function (m) { return m.species && m.species.toLowerCase().includes(q); })) return true;
      return false;
    });
  }

  function render(filtered) {
    var grid = document.getElementById('trainer-grid');
    var countEl = document.getElementById('trainer-count');
    countEl.textContent = filtered.length + ' trainers';

    if (filtered.length === 0) {
      grid.innerHTML = '<div class="dex-empty">No trainers match your search.</div>';
      return;
    }

    grid.innerHTML = filtered.map(trainerCard).join('');

    grid.querySelectorAll('.tr-card').forEach(function (card) {
      card.addEventListener('click', function (e) {
        if (e.target.tagName === 'A') return;
        card.classList.toggle('expanded');
      });
    });
  }

  // ── Card HTML ───────────────────────────────────────────────────────────────

  function trainerCard(t) {
    var spriteHtml = t.sprite
      ? '<img class="tr-sprite" src="img/sprites/' + esc(t.sprite) + '" alt="" onerror="this.style.display=\'none\'">'
      : '<div class="tr-sprite-ph">' + esc(t.pic || t.trClass || '?') + '</div>';

    var locHtml;
    if (t.locs.length) {
      var shown = t.locs.slice(0, 3).map(function (l) {
        return '<a class="tr-loc-link" href="index.html?map=' + encodeURIComponent(l.mapId) + '">' + esc(l.mapName) + '</a>';
      }).join(' · ');
      var extra = t.locs.length > 3 ? ' <span class="tr-loc-more">+' + (t.locs.length - 3) + '</span>' : '';
      locHtml = shown + extra;
    } else {
      locHtml = '<span class="tr-loc-none">Script / Battle only</span>';
    }

    var partyHtml = t.party.map(function (m) {
      var icon = m.sprite
        ? '<img class="tr-mon-icon" src="img/pokemon/' + esc(m.sprite) + '" alt="' + esc(m.species) + '" onerror="this.remove()" loading="lazy">'
        : '';
      return '<div class="tr-mon-chip" title="' + esc(m.species) + ' Lv ' + m.level + '">'
        + icon + '<span class="tr-mon-lv">Lv ' + m.level + '</span></div>';
    }).join('');

    var detailHtml = t.party.map(function (m) {
      var head = '<strong>' + esc(m.species) + '</strong>'
        + (m.item ? ' @ ' + esc(m.item) : '');
      var metaParts = ['Lv. ' + m.level];
      if (m.nature) metaParts.push(esc(m.nature));
      if (m.ability) metaParts.push(esc(m.ability));
      if (m.tera) metaParts.push('Tera: ' + esc(m.tera));
      var icon = m.sprite
        ? '<img class="tr-d-icon" src="img/pokemon/' + esc(m.sprite) + '" alt="" onerror="this.remove()">'
        : '';
      var moves = (m.moves || []).map(function (mv) {
        return '<span class="tr-d-move">' + esc(mv) + '</span>';
      }).join('');
      return '<div class="tr-mon-detail">'
        + icon
        + '<div class="tr-mon-d-body">'
        + '<div class="tr-mon-d-head">' + head + '</div>'
        + '<div class="tr-mon-d-meta">' + metaParts.join(' · ') + '</div>'
        + (moves ? '<div class="tr-mon-d-moves">' + moves + '</div>' : '')
        + '</div></div>';
    }).join('');

    return '<div class="tr-card">'
      + '<div class="tr-card-top">'
      + spriteHtml
      + '<div class="tr-card-info">'
      + '<div class="tr-card-name">' + esc(t.name) + '</div>'
      + '<span class="tr-class-badge">' + esc(t.trClass) + '</span>'
      + '<div class="tr-card-locs">' + locHtml + '</div>'
      + '</div></div>'
      + '<div class="tr-party">' + partyHtml + '</div>'
      + '<div class="tr-detail">' + detailHtml + '</div>'
      + '</div>';
  }

  // ── Bootstrap ───────────────────────────────────────────────────────────────

  function init() {
    var searchEl = document.getElementById('trainer-search');
    var mapOnlyEl = document.getElementById('tr-map-only');

    searchEl.addEventListener('input', function () {
      state.query = this.value.trim();
      render(applyFilters());
    });

    mapOnlyEl.addEventListener('change', function () {
      state.mapOnly = this.checked;
      render(applyFilters());
    });

    Promise.all([
      fetch('js/data/trainers.json').then(function (r) { return r.json(); }),
      fetch('js/data/world.json').then(function (r) { return r.json(); }),
    ]).then(function (results) {
      var trainersData = results[0];
      var world = results[1];

      // Location index: TRAINER_ID -> [{mapId, mapName}] (deduplicated by mapId)
      var locIndex = {};
      (world.trainers || []).forEach(function (t) {
        if (!locIndex[t.trainerId]) locIndex[t.trainerId] = [];
        if (!locIndex[t.trainerId].some(function (l) { return l.mapId === t.mapId; })) {
          locIndex[t.trainerId].push({ mapId: t.mapId, mapName: prettifyMap(t.mapId) });
        }
      });

      // Sprite index: TRAINER_ID -> "file.png" (first OW sprite from world)
      var spriteIndex = {};
      (world.trainers || []).forEach(function (t) {
        if (spriteIndex[t.trainerId]) return;
        var sp = world.sprites && world.sprites[t.gfx];
        if (!sp) return;
        var file = (sp.dirs && (sp.dirs[t.dir] || sp.dirs.down)) || sp.file;
        if (file) spriteIndex[t.trainerId] = file;
      });

      // Build combined list
      state.all = Object.keys(trainersData)
        .filter(function (id) {
          var t = trainersData[id];
          return id !== 'TRAINER_NONE' && t.party && t.party.length > 0;
        })
        .map(function (id) {
          var t = trainersData[id];
          return {
            id: id,
            name: t.name || '',
            trClass: t.class || '',
            pic: t.pic || '',
            party: t.party || [],
            locs: locIndex[id] || [],
            sprite: spriteIndex[id] || null,
          };
        })
        .sort(function (a, b) {
          // Map trainers first, then by class+name
          if ((a.locs.length > 0) !== (b.locs.length > 0)) {
            return a.locs.length > 0 ? -1 : 1;
          }
          var ka = (a.trClass + ' ' + a.name).toLowerCase();
          var kb = (b.trClass + ' ' + b.name).toLowerCase();
          return ka < kb ? -1 : ka > kb ? 1 : 0;
        });

      render(applyFilters());
    }).catch(function () {
      document.getElementById('trainer-grid').innerHTML =
        '<div class="dex-empty">Failed to load trainer data. Run the build script first.</div>';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
