(function () {
  'use strict';

  // ── Helpers ────────────────────────────────────────────────────
  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function fmtNum(n) { return '#' + String(n).padStart(4, '0'); }

  function typeBadge(type) {
    return '<span class="type-badge t-' + type + '">' + type.toLowerCase() + '</span>';
  }

  function prettifyConstant(s) {
    return s.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  // Height: stored in dm (decimeters). 7 -> 0.7 m
  function fmtHeight(dm) {
    var m = (dm / 10).toFixed(1);
    var ft = Math.floor(dm * 0.3281);
    var inch = Math.round((dm * 0.3281 - ft) * 12);
    return m + ' m (' + ft + '\'' + inch + '")';
  }

  // Weight: stored in hg (hectograms). 69 -> 6.9 kg
  function fmtWeight(hg) {
    var kg = (hg / 10).toFixed(1);
    var lb = (hg * 0.2205).toFixed(1);
    return kg + ' kg (' + lb + ' lbs)';
  }

  function fmtGender(ratio) {
    if (ratio < 0) return 'Genderless';
    if (ratio === 0) return '100% ♂';
    if (ratio === 100) return '100% ♀';
    return (100 - ratio).toFixed(1) + '% ♂ / ' + ratio.toFixed(1) + '% ♀';
  }

  function statColor(val) {
    if (val >= 130) return '#4db87a';
    if (val >= 90)  return '#80c858';
    if (val >= 60)  return '#c8b820';
    if (val >= 40)  return '#e07830';
    return '#d84848';
  }

  // ── Stat bar section ──────────────────────────────────────────
  var STAT_LABELS = { hp:'HP', atk:'Atk', def:'Def', spa:'Sp.A', spd:'Sp.D', spe:'Spe' };

  function renderStats(stats) {
    var total = Object.values(stats).reduce(function (a, b) { return a + b; }, 0);
    var rows = Object.entries(stats).map(function (kv) {
      var key = kv[0], val = kv[1];
      var pct = Math.min(100, Math.round(val / 255 * 100));
      return '<div class="stat-row">'
        + '<span class="stat-label">' + STAT_LABELS[key] + '</span>'
        + '<span class="stat-val">' + val + '</span>'
        + '<div class="stat-bar-bg"><div class="stat-bar-fill" style="width:' + pct + '%;background:' + statColor(val) + '"></div></div>'
        + '</div>';
    }).join('');
    return rows
      + '<div class="stat-row stat-total">'
      + '<span class="stat-label">BST</span>'
      + '<span class="stat-val">' + total + '</span>'
      + '</div>';
  }

  // ── Abilities section ─────────────────────────────────────────
  function renderAbilities(abilities, abData) {
    var slots = [
      { key: abilities[0], label: 'Ability 1' },
      { key: abilities[1], label: 'Ability 2' },
      { key: abilities[2], label: 'Hidden', hidden: true },
    ];
    return slots.filter(function (s) { return s.key; }).map(function (s) {
      var ab = abData[s.key] || { name: prettifyConstant(s.key), description: '' };
      return '<div class="ability-row">'
        + '<span class="ability-name" title="' + esc(ab.description) + '">' + esc(ab.name) + '</span>'
        + (s.hidden ? '<span class="ability-tag">Hidden</span>' : '')
        + '</div>'
        + (ab.description ? '<div class="ability-desc">' + esc(ab.description) + '</div>' : '');
    }).join('');
  }

  // ── Evolution chain ───────────────────────────────────────────
  // Evolutions are pre-merged by the parser: each entry has a `methods` array
  // (one or more human labels for the ways to reach `target`). Older data may
  // still carry the raw {method, conditions, ...} shape — fall back to that.
  function evoMethodText(evo) {
    if (evo.methods && evo.methods.length) return evo.methods.join(' / ');
    return evoMethodLabel(evo);
  }

  function evoMethodLabel(evo) {
    var m = evo.method || '';
    var conds = evo.conditions || [];
    var hasFriendship = conds.indexOf('IF_MIN_FRIENDSHIP') !== -1;
    var isNight = conds.indexOf('IF_TIME') !== -1;
    var isDay   = conds.indexOf('IF_NOT_TIME') !== -1;
    var isMap   = conds.indexOf('IF_IN_MAP') !== -1;
    var isFairy = conds.indexOf('IF_KNOWS_MOVE_TYPE') !== -1;

    if (m === 'EVO_LEVEL' || m.startsWith('EVO_LEVEL_')) {
      if (evo.level) return 'Lv. ' + evo.level;
      if (hasFriendship && isNight) return 'Friendship (night)';
      if (hasFriendship && isDay)   return 'Friendship (day)';
      if (hasFriendship && isFairy) return 'Friendship + Fairy move';
      if (hasFriendship)            return 'Friendship';
      if (isMap)                    return 'Level up in area';
      return 'Level up';
    }
    if (m === 'EVO_FRIENDSHIP') return 'Friendship';
    if (m === 'EVO_FRIENDSHIP_DAY') return 'Friendship (day)';
    if (m === 'EVO_FRIENDSHIP_NIGHT') return 'Friendship (night)';
    if (m.includes('ITEM_HOLD')) return 'Hold ' + (evo.item || '');
    if (m.includes('ITEM')) return evo.item || 'Use item';
    if (m === 'EVO_TRADE') return 'Trade';
    if (m === 'EVO_MOVE') return 'Know ' + (evo.move || '');
    if (m === 'EVO_BEAUTY') return 'Max Beauty';
    return prettifyConstant(m.replace('EVO_', ''));
  }

  function buildEvoChain(speciesId, index) {
    // Walk back to the root
    function getRoot(id) {
      var visited = new Set();
      while (index[id] && index[id].preEvolution && !visited.has(id)) {
        visited.add(id);
        id = index[id].preEvolution;
      }
      return id;
    }

    // Walk forward collecting chain segments
    function buildBranch(id, depth) {
      if (depth > 10) return [];
      var sp = index[id];
      if (!sp) return [];
      var node = { id: id, sp: sp };
      var branches = [];
      if (sp.evolutions && sp.evolutions.length > 0) {
        sp.evolutions.forEach(function (evo) {
          branches.push({ evo: evo, next: buildBranch(evo.target, depth + 1) });
        });
      }
      return [{ node: node, branches: branches }];
    }

    var root = getRoot(speciesId);
    return buildBranch(root, 0);
  }

  function renderEvoNode(id, sp, currentId, isSmall) {
    var icon = sp ? sp.icon : null;
    var name = sp ? sp.name : prettifyConstant(id);
    var img = icon
      ? '<img class="evo-sprite" src="' + icon + '" alt="' + esc(name) + '" loading="lazy" />'
      : '<div class="evo-sprite" style="display:flex;align-items:center;justify-content:center;font-size:28px;color:#2a3a48">?</div>';
    var cls = 'evo-node' + (id === currentId ? ' current' : '');
    return '<a href="pokemon.html?id=' + id + '" class="' + cls + '">'
      + img
      + '<span class="evo-name">' + esc(name) + '</span>'
      + '</a>';
  }

  function renderEvoChainHtml(chain, currentId, index) {
    if (!chain || chain.length === 0) return '<em style="color:#4a6070;font-size:13px">Does not evolve.</em>';

    function renderBranch(items) {
      return items.map(function (item) {
        var nodeHtml = renderEvoNode(item.node.id, item.node.sp, currentId);
        if (!item.branches || item.branches.length === 0) return nodeHtml;
        var nexts = item.branches.map(function (b) {
          var method = evoMethodText(b.evo);
          var nextItems = b.next || [];
          var nextHtml = renderBranch(nextItems);
          return '<div class="evo-arrow">&#8594;<div class="evo-method">' + esc(method) + '</div></div>'
            + nextHtml;
        }).join('<div style="width:8px"></div>');
        return nodeHtml + nexts;
      }).join('');
    }

    return '<div class="evo-chain">' + renderBranch(chain) + '</div>';
  }

  // ── Learnset table ────────────────────────────────────────────
  function renderMoveRow(move, moveData) {
    var m = moveData[move] || {};
    var name = m.name || prettifyConstant(move);
    var type = m.type ? typeBadge(m.type) : '';
    var cat = m.category ? '<span class="cat-badge ' + m.category + '">' + m.category.toLowerCase() + '</span>' : '';
    var power = m.power ? m.power : '<span class="dash">—</span>';
    var acc = m.accuracy ? m.accuracy + '%' : '<span class="dash">—</span>';
    var pp = m.pp || '<span class="dash">—</span>';
    return '<td class="col-move">' + esc(name) + '</td>'
      + '<td>' + type + '</td>'
      + '<td>' + cat + '</td>'
      + '<td class="col-power">' + power + '</td>'
      + '<td class="col-acc">' + acc + '</td>'
      + '<td class="col-pp">' + pp + '</td>';
  }

  function renderLearnsetTable(moves, moveData, hasLevel) {
    if (!moves || moves.length === 0) return '<div class="dex-empty" style="padding:16px">None</div>';
    var header = '<thead><tr><th>' + (hasLevel ? 'Lv.' : '#') + '</th><th>Move</th><th>Type</th><th>Cat</th><th>Pwr</th><th>Acc</th><th>PP</th></tr></thead>';
    var rows;
    if (hasLevel) {
      rows = moves.map(function (entry, i) {
        return '<tr><td class="col-level">' + entry.level + '</td>' + renderMoveRow(entry.move, moveData) + '</tr>';
      }).join('');
    } else {
      rows = moves.map(function (move, i) {
        return '<tr><td class="col-level" style="color:#3a4a58">' + (i + 1) + '</td>' + renderMoveRow(move, moveData) + '</tr>';
      }).join('');
    }
    return '<table class="learnset-table">' + header + '<tbody>' + rows + '</tbody></table>';
  }

  // ── Encounters ────────────────────────────────────────────────
  var ENC_TYPE_LABELS = {
    'land_mons': 'Grass', 'water_mons': 'Surf',
    'rock_smash_mons': 'Rock Smash', 'fishing_mons': 'Fishing'
  };
  var ENC_TYPE_CSS = {
    'land_mons': 'land', 'water_mons': 'water_mons',
    'rock_smash_mons': 'rock_smash_mons', 'fishing_mons': 'fishing'
  };

  function renderEncounters(encounters) {
    if (!encounters || encounters.length === 0) {
      return '<div class="dex-empty" style="padding:16px">Not found in the wild.</div>';
    }
    var rows = encounters.map(function (enc) {
      var mapLink = 'index.html?map=' + enc.map;
      var typeLabel = ENC_TYPE_LABELS[enc.type] || enc.type;
      var typeCss = ENC_TYPE_CSS[enc.type] || 'land';
      return '<tr>'
        + '<td><a class="enc-map-link" href="' + mapLink + '">' + esc(enc.mapName) + '</a></td>'
        + '<td>' + enc.minLevel + '–' + enc.maxLevel + '</td>'
        + '<td><span class="enc-type-badge ' + typeCss + '">' + typeLabel + '</span></td>'
        + '</tr>';
    }).join('');
    return '<table class="enc-table">'
      + '<thead><tr><th>Location</th><th>Levels</th><th>Method</th></tr></thead>'
      + '<tbody>' + rows + '</tbody></table>';
  }

  // ── Main render ───────────────────────────────────────────────
  function render(pkmn, moves, abilities) {
    var content = document.getElementById('pokemon-content');
    document.title = 'BPE Emerald — ' + pkmn.name;

    var spriteHtml = pkmn.sprite
      ? '<img class="pkmn-sprite" src="' + pkmn.sprite + '" alt="' + esc(pkmn.name) + '" />'
      : '<div class="pkmn-noimg">?</div>';

    var typeBadges = pkmn.types.map(typeBadge).join('');

    var metaRows = [
      ['Height', fmtHeight(pkmn.height)],
      ['Weight', fmtWeight(pkmn.weight)],
      ['Catch rate', pkmn.catchRate],
      ['Growth', prettifyConstant(pkmn.growthRate)],
      ['Gender', fmtGender(pkmn.genderRatio)],
      ['Egg groups', (pkmn.eggGroups || []).map(prettifyConstant).join(', ') || '—'],
    ].map(function (row) {
      return '<span class="pkmn-meta-label">' + row[0] + '</span><span class="pkmn-meta-value">' + esc(String(row[1])) + '</span>';
    }).join('');

    var statsHtml = renderStats(pkmn.baseStats);
    var abilitiesHtml = renderAbilities(pkmn.abilities, abilities);

    // Need full index for evo chain
    var evoHtml = '<em style="color:#4a6070;font-size:13px">Loading…</em>';

    var lvlMoves = renderLearnsetTable(pkmn.levelUpMoves, moves, true);
    var tmMoves = renderLearnsetTable(pkmn.tmMoves, moves, false);
    var hmMoves = renderLearnsetTable(pkmn.hmMoves, moves, false);
    var eggMoves = renderLearnsetTable(pkmn.eggMoves, moves, false);
    var tutorMoves = renderLearnsetTable(pkmn.tutorMoves, moves, false);
    var encHtml = renderEncounters(pkmn.encounters);

    var descHtml = pkmn.description
      ? '<p style="color:#7e93a8;font-size:14px;line-height:1.6;margin:0 0 12px">' + esc(pkmn.description) + '</p>'
      : '';

    content.innerHTML = ''
      + '<div class="pkmn-header">'
      +   '<span class="pkmn-num">' + fmtNum(pkmn.natDexNum) + '</span>'
      +   '<h1 class="pkmn-name">' + esc(pkmn.name) + '</h1>'
      +   (pkmn.category ? '<span class="pkmn-category">' + esc(pkmn.category) + ' Pokémon</span>' : '')
      + '</div>'
      + '<div class="pkmn-types-row">' + typeBadges + '</div>'
      + (descHtml)
      + '<div class="pkmn-layout">'
      +   '<div class="pkmn-sprite-box">'
      +     spriteHtml
      +     '<div class="pkmn-meta-grid">' + metaRows + '</div>'
      +   '</div>'
      +   '<div class="pkmn-info-box">'
      +     '<div class="info-card"><h3>Base Stats</h3>' + statsHtml + '</div>'
      +     '<div class="info-card"><h3>Abilities</h3>' + abilitiesHtml + '</div>'
      +     '<div class="info-card" id="evo-card"><h3>Evolution Chain</h3>' + evoHtml + '</div>'
      +   '</div>'
      + '</div>'
      + '<div class="dex-section">'
      +   '<h2>Learnset</h2>'
      +   '<div class="tab-bar">'
      +     '<button class="tab-btn active" data-tab="lv">Level Up (' + (pkmn.levelUpMoves || []).length + ')</button>'
      +     '<button class="tab-btn" data-tab="tm">TM (' + (pkmn.tmMoves || []).length + ')</button>'
      +     '<button class="tab-btn" data-tab="hm">HM (' + (pkmn.hmMoves || []).length + ')</button>'
      +     '<button class="tab-btn" data-tab="egg">Egg (' + (pkmn.eggMoves || []).length + ')</button>'
      +     '<button class="tab-btn" data-tab="tutor">Tutor (' + (pkmn.tutorMoves || []).length + ')</button>'
      +   '</div>'
      +   '<div id="tab-lv" class="tab-panel active">' + lvlMoves + '</div>'
      +   '<div id="tab-tm" class="tab-panel">' + tmMoves + '</div>'
      +   '<div id="tab-hm" class="tab-panel">' + hmMoves + '</div>'
      +   '<div id="tab-egg" class="tab-panel">' + eggMoves + '</div>'
      +   '<div id="tab-tutor" class="tab-panel">' + tutorMoves + '</div>'
      + '</div>'
      + '<div class="dex-section"><h2>Wild Encounters</h2>' + encHtml + '</div>';

    // Wire up tab buttons
    content.querySelectorAll('.tab-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        content.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
        content.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('active'); });
        btn.classList.add('active');
        var panel = document.getElementById('tab-' + btn.dataset.tab);
        if (panel) panel.classList.add('active');
      });
    });

    return content;
  }

  // ── Load and hydrate evolution chain ─────────────────────────
  function hydrateEvoChain(pkmn, index) {
    var card = document.getElementById('evo-card');
    if (!card) return;

    function buildChain(id, depth, visited) {
      if (depth > 10 || visited.has(id)) return [];
      visited.add(id);
      var sp = index[id];
      if (!sp) return [];
      var branches = (sp.evolutions || []).map(function (evo) {
        return { evo: evo, next: buildChain(evo.target, depth + 1, new Set(visited)) };
      });
      return [{ node: { id: id, sp: sp }, branches: branches }];
    }

    function getRoot(id) {
      var seen = new Set();
      while (index[id] && index[id].preEvolution && !seen.has(id)) {
        seen.add(id);
        id = index[id].preEvolution;
      }
      return id;
    }

    var root = getRoot(pkmn.id);
    var chain = buildChain(root, 0, new Set());

    function renderNode(id, sp) {
      var isCurrent = id === pkmn.id;
      var icon = sp ? sp.icon : null;
      var name = sp ? sp.name : prettifyConstant(id);
      var imgHtml = icon
        ? '<img class="evo-sprite" src="' + icon + '" alt="' + esc(name) + '" loading="lazy" />'
        : '<div class="evo-sprite" style="display:flex;align-items:center;justify-content:center;font-size:28px;color:#2a3a48">?</div>';
      var cls = 'evo-node' + (isCurrent ? ' current' : '');
      return '<a href="pokemon.html?id=' + id + '" class="' + cls + '">'
        + imgHtml
        + '<span class="evo-name">' + esc(name) + '</span>'
        + '</a>';
    }

    function methodLabel(evo) { return evoMethodText(evo); }

    function arrowHtml(evo) {
      return '<div class="evo-arrow">&#8594;<div class="evo-method">'
        + esc(methodLabel(evo)) + '</div></div>';
    }

    function renderBranch(items) {
      if (!items || items.length === 0) return '';
      return items.map(function (item) {
        var nodeHtml = renderNode(item.node.id, item.node.sp);
        var branches = item.branches || [];
        if (branches.length === 0) return nodeHtml;

        // Single evolution path (e.g. Abra → Kadabra → Alakazam): keep it as a
        // simple horizontal sequence.
        if (branches.length === 1) {
          return '<div class="evo-seq">' + nodeHtml
            + arrowHtml(branches[0].evo) + renderBranch(branches[0].next)
            + '</div>';
        }

        // Multiple evolutions from one Pokémon (e.g. Eevee): fan the branches
        // out from the source like spokes on a wheel.
        var spokes = branches.map(function (b) {
          return '<div class="evo-spoke">' + arrowHtml(b.evo) + renderBranch(b.next) + '</div>';
        }).join('');
        return '<div class="evo-branch">' + nodeHtml
          + '<div class="evo-spokes">' + spokes + '</div></div>';
      }).join('');
    }

    var html;
    if (chain.length === 0 || (chain[0].branches.length === 0 && !pkmn.preEvolution)) {
      html = '<em style="color:#4a6070;font-size:13px">Does not evolve.</em>';
    } else {
      html = '<div class="evo-chain">' + renderBranch(chain) + '</div>';
    }

    card.querySelector('h3').insertAdjacentHTML('afterend', html);
    var loading = card.querySelector('em');
    if (loading && loading.textContent === 'Loading…') loading.remove();
  }

  // ── Bootstrap ─────────────────────────────────────────────────
  function init() {
    var params = new URLSearchParams(window.location.search);
    var speciesId = params.get('id');
    if (!speciesId) {
      document.getElementById('pokemon-content').innerHTML =
        '<div class="dex-empty">No Pokémon specified. <a href="pokedex.html" style="color:#4db87a">Back to Pokédex</a></div>';
      return;
    }

    // Load species data, moves, and abilities in parallel
    Promise.all([
      fetch('data/species/' + speciesId + '.json').then(function (r) {
        if (!r.ok) throw new Error('not found');
        return r.json();
      }),
      fetch('data/moves.json').then(function (r) { return r.json(); }),
      fetch('data/abilities.json').then(function (r) { return r.json(); }),
    ]).then(function (results) {
      var pkmn = results[0], movesData = results[1], abData = results[2];
      render(pkmn, movesData, abData);

      // Load index separately for evo chain (lighter if cached)
      fetch('data/pokedex_index.json')
        .then(function (r) { return r.json(); })
        .then(function (index) { hydrateEvoChain(pkmn, index); })
        .catch(function () {});

    }).catch(function (e) {
      document.getElementById('pokemon-content').innerHTML =
        '<div class="dex-empty">Could not load data for <strong>' + esc(speciesId) + '</strong>.<br>'
        + 'Run the parser script first, or <a href="pokedex.html" style="color:#4db87a">go back</a>.</div>';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
