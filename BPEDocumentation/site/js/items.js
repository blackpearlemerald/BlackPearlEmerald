(function () {
  'use strict';

  var POCKETS = [
    { key: 'POCKET_ITEMS',      label: 'Items' },
    { key: 'POCKET_POKE_BALLS', label: 'Poké Balls' },
    { key: 'POCKET_TM_HM',      label: 'TMs & HMs' },
    { key: 'POCKET_BERRIES',    label: 'Berries' },
    { key: 'POCKET_KEY_ITEMS',  label: 'Key Items' },
  ];

  var state = {
    index: null,
    moves: {},
    query: '',
    activePocket: null,
  };

  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function itemDisplayName(item) {
    var name = item.name || item.id;
    if (item.pocket !== 'POCKET_TM_HM' || !/^(?:TM|HM)\d+$/i.test(name) || !/^(?:TM|HM)_/.test(item.id || '')) {
      return name;
    }

    var moveId = item.id.slice(3);
    var move = state.moves[moveId];
    var moveName = move && move.name;
    if (!moveName) {
      moveName = moveId.replace(/_/g, ' ').toLowerCase()
        .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }
    return name + ' - ' + moveName;
  }

  function applyFilters() {
    if (!state.index) return [];
    var q = state.query.toLowerCase();
    var all = Object.values(state.index).sort(function (a, b) {
      var aName = itemDisplayName(a);
      var bName = itemDisplayName(b);
      // Sort by pocket order first, then alphabetically
      var pi = POCKETS.findIndex(function (p) { return p.key === a.pocket; });
      var pj = POCKETS.findIndex(function (p) { return p.key === b.pocket; });
      if (state.activePocket) {
        // When filtered to one pocket, just sort alphabetically
        return aName < bName ? -1 : aName > bName ? 1 : 0;
      }
      if (pi !== pj) return pi - pj;
      return aName < bName ? -1 : aName > bName ? 1 : 0;
    });
    return all.filter(function (item) {
      if (q) {
        var nameMatch = itemDisplayName(item).toLowerCase().includes(q);
        var idMatch   = item.id.toLowerCase().includes(q);
        var descMatch = item.description && item.description.toLowerCase().includes(q);
        if (!nameMatch && !idMatch && !descMatch) return false;
      }
      if (state.activePocket && item.pocket !== state.activePocket) return false;
      return true;
    });
  }

  function renderGrid(filtered) {
    var grid  = document.getElementById('items-grid');
    var count = document.getElementById('items-count');
    count.textContent = filtered.length + ' item' + (filtered.length !== 1 ? 's' : '');

    if (filtered.length === 0) {
      grid.innerHTML = '<div class="dex-empty">No items match your search.</div>';
      return;
    }

    var html = '';
    for (var i = 0; i < filtered.length; i++) {
      var item = filtered[i];
      var displayName = itemDisplayName(item);
      var imgHtml = item.icon
        ? '<img class="item-card-icon" src="' + item.icon + '" alt="' + esc(displayName) + '" loading="lazy" />'
        : '<div class="item-card-noimg">?</div>';
      var badge = '<span class="item-pocket-badge pocket-' + esc(item.pocket) + '">'
        + esc(item.pocketLabel) + '</span>';
      html += '<a class="item-card" href="item.html?id=' + esc(item.id) + '">'
        + imgHtml
        + '<div class="item-card-name">' + esc(displayName) + '</div>'
        + badge
        + '</a>';
    }
    grid.innerHTML = html;
  }

  function buildPocketFilters() {
    var container = document.getElementById('pocket-filters');
    var html = '<button class="pocket-btn all-pocket active" data-pocket="">All</button>';
    POCKETS.forEach(function (p) {
      html += '<button class="pocket-btn pb-' + p.key + '" data-pocket="' + p.key + '">'
        + p.label + '</button>';
    });
    container.innerHTML = html;

    container.addEventListener('click', function (e) {
      var btn = e.target.closest('.pocket-btn');
      if (!btn) return;
      container.querySelectorAll('.pocket-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      state.activePocket = btn.dataset.pocket || null;
      renderGrid(applyFilters());
    });
  }

  function init() {
    buildPocketFilters();

    document.getElementById('items-search').addEventListener('input', function (e) {
      state.query = e.target.value;
      renderGrid(applyFilters());
    });

    Promise.all([
      fetch('data/items_index.json').then(function (r) { return r.json(); }),
      fetch('data/moves.json').then(function (r) { return r.json(); }).catch(function () { return {}; }),
    ])
      .then(function (data) {
        state.index = data[0];
        state.moves = data[1];
        renderGrid(applyFilters());
      })
      .catch(function () {
        document.getElementById('items-grid').innerHTML =
          '<div class="dex-empty">Failed to load items data. Run the parser script first.</div>';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
