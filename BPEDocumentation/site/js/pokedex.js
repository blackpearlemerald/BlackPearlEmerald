(function () {
  'use strict';

  var ALL_TYPES = [
    'NORMAL','FIRE','WATER','ELECTRIC','GRASS','ICE',
    'FIGHTING','POISON','GROUND','FLYING','PSYCHIC','BUG',
    'ROCK','GHOST','DRAGON','DARK','STEEL','FAIRY','STELLAR'
  ];

  function typeBadge(type) {
    return '<span class="type-badge t-' + type + '">' + type.toLowerCase() + '</span>';
  }

  function fmtNum(n) {
    return '#' + String(n).padStart(4, '0');
  }

  var state = {
    index: null,
    query: '',
    activeType: null,
    showForms: false,
  };

  function applyFilters() {
    if (!state.index) return [];
    var q = state.query.toLowerCase();

    // Sort all species: push natDexNum=0 to end, then by dex#, then shorter id first (base before forms)
    var all = Object.values(state.index).sort(function (a, b) {
      var na = a.natDexNum || 99999, nb = b.natDexNum || 99999;
      if (na !== nb) return na - nb;
      if (a.id.length !== b.id.length) return a.id.length - b.id.length;
      return a.id < b.id ? -1 : 1;
    });

    var seenDexNums = new Set();
    return all.filter(function (p) {
      if (q && !p.name.toLowerCase().includes(q) && !p.id.toLowerCase().includes(q)) return false;
      if (state.activeType && !p.types.includes(state.activeType)) return false;
      if (!state.showForms && p.natDexNum > 0) {
        if (seenDexNums.has(p.natDexNum)) return false;
        seenDexNums.add(p.natDexNum);
      }
      return true;
    });
  }

  function renderGrid(filtered) {
    var grid = document.getElementById('dex-grid');
    var count = document.getElementById('dex-count');
    count.textContent = filtered.length + ' Pokémon';

    if (filtered.length === 0) {
      grid.innerHTML = '<div class="dex-empty">No Pokémon match your search.</div>';
      return;
    }

    var html = '';
    for (var i = 0; i < filtered.length; i++) {
      var p = filtered[i];
      var imgHtml = p.icon
        ? '<img class="dex-card-icon" src="' + p.icon + '" alt="' + p.name + '" loading="lazy" />'
        : '<div class="dex-card-noimg">?</div>';
      var types = p.types.map(typeBadge).join('');
      html += '<a class="dex-card" href="pokemon.html?id=' + p.id + '">'
        + '<div class="dex-card-num">' + fmtNum(p.natDexNum) + '</div>'
        + imgHtml
        + '<div class="dex-card-name">' + esc(p.name) + '</div>'
        + '<div class="dex-card-types">' + types + '</div>'
        + '</a>';
    }
    grid.innerHTML = html;
  }

  function buildTypeFilters() {
    var container = document.getElementById('type-filters');
    var html = '<button class="type-filter-btn all-btn active" data-type="">All</button>';
    ALL_TYPES.forEach(function (t) {
      html += '<button class="type-filter-btn t-' + t + '" data-type="' + t + '">'
        + t.toLowerCase() + '</button>';
    });
    container.innerHTML = html;

    container.addEventListener('click', function (e) {
      var btn = e.target.closest('.type-filter-btn');
      if (!btn) return;
      container.querySelectorAll('.type-filter-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      state.activeType = btn.dataset.type || null;
      renderGrid(applyFilters());
    });
  }

  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function init() {
    buildTypeFilters();

    document.getElementById('dex-search').addEventListener('input', function (e) {
      state.query = e.target.value;
      renderGrid(applyFilters());
    });

    document.getElementById('show-forms').addEventListener('change', function (e) {
      state.showForms = e.target.checked;
      renderGrid(applyFilters());
    });

    // Load index
    fetch('data/pokedex_index.json')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.index = data;
        renderGrid(applyFilters());
      })
      .catch(function () {
        document.getElementById('dex-grid').innerHTML =
          '<div class="dex-empty">Failed to load Pokédex data. Run the parser script first.</div>';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
