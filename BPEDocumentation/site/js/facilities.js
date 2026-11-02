(function () {
  'use strict';

  // All text comes from this release's data/facilities.json and data/frontier_sets.json
  // and is inserted as text, never as HTML. Neither falls back to another release.
  var status = document.getElementById('facilities-status');
  var intro = document.getElementById('facilities-intro');
  var sectionsRoot = document.getElementById('facilities-sections');
  var setsSection = document.getElementById('sets');
  var rulesSelect = document.getElementById('sets-rules');
  var styleSelect = document.getElementById('sets-style');
  var genField = document.getElementById('sets-gen-field');
  var genSelect = document.getElementById('sets-gen');
  var tierField = document.getElementById('sets-tier-field');
  var tierSelect = document.getElementById('sets-tier');
  var search = document.getElementById('sets-search');
  var summary = document.getElementById('sets-summary');
  var list = document.getElementById('sets-list');
  var more = document.getElementById('sets-more');
  var brainsSection = document.getElementById('brains');
  var brainsText = document.getElementById('brains-text');
  var brainsList = document.getElementById('brains-list');

  var PAGE_SIZE = 48;
  var STATS = ['HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe']; // The game's order for set EVs
  var TIER_NAMES = { AG: 'Anything Goes', Ubers: 'Ubers', OU: 'OU', UU: 'UU', RU: 'RU' };
  var BRAINS = [
    ['tower', 'Anabel', 'Battle Tower'], ['dome', 'Tucker', 'Battle Dome'], ['palace', 'Spenser', 'Battle Palace'],
    ['arena', 'Greta', 'Battle Arena'], ['pike', 'Lucy', 'Battle Pike'], ['pyramid', 'Brandon', 'Battle Pyramid']
  ];

  var tables = null;
  var shownIds = [];
  var shownCount = 0;

  function element(name, className, text) {
    var node = document.createElement(name);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function renderTable(table) {
    var wrap = element('div', 'features-table-wrap');
    var grid = element('table', 'features-table');
    var headRow = element('tr');
    table.columns.forEach(function (column, i) {
      var cell = element('th', '', column);
      cell.scope = 'col';
      if (i === 0) cell.className = 'features-table-label';
      headRow.appendChild(cell);
    });
    grid.appendChild(element('thead')).appendChild(headRow);
    var body = element('tbody');
    table.rows.forEach(function (row) {
      var tr = element('tr');
      row.forEach(function (value, i) {
        var cell = element(i === 0 ? 'th' : 'td', '', value);
        if (i === 0) cell.scope = 'row';
        tr.appendChild(cell);
      });
      body.appendChild(tr);
    });
    grid.appendChild(body);
    wrap.appendChild(grid);
    return wrap;
  }

  function renderSections(sections) {
    var fragment = document.createDocumentFragment();
    sections.forEach(function (section) {
      var block = element('section', 'features-section');
      block.id = section.id;
      block.appendChild(element('h2', '', section.title));
      var grid = element('div', 'features-grid');
      section.items.forEach(function (item) {
        var card = element('article', item.table ? 'features-card is-wide' : 'features-card');
        card.appendChild(element('h3', '', item.title));
        card.appendChild(element('p', '', item.body));
        if (item.table) card.appendChild(renderTable(item.table));
        grid.appendChild(card);
      });
      block.appendChild(grid);
      fragment.appendChild(block);
    });
    sectionsRoot.replaceChildren(fragment);
  }

  function formatEvs(spread) {
    return spread.map(function (value, i) { return value ? value + ' ' + STATS[i] : null; })
      .filter(Boolean).join(' / ') || 'None';
  }

  function detail(label, value) {
    var row = element('div', 'set-detail');
    row.appendChild(element('dt', '', label));
    var cell = element('dd');
    if (value.nodeType) cell.appendChild(value); else cell.textContent = value;
    row.appendChild(cell);
    return row;
  }

  function renderSet(id, rank) {
    var row = tables.sets[id];
    var species = tables.species[row[0]];
    var item = tables.items[row[1]];
    var card = element('article', 'set-card');
    var head = element('div', 'set-head');
    var mon = element('a', 'set-mon');
    mon.href = 'pokemon.html?id=' + encodeURIComponent(species[0]);
    if (species[2]) {
      var icon = element('img', 'set-icon');
      icon.src = species[2];
      icon.alt = '';
      icon.loading = 'lazy';
      icon.addEventListener('error', function () { icon.remove(); });
      mon.appendChild(icon);
    }
    mon.appendChild(element('span', '', species[1]));
    head.appendChild(mon);
    if (rank) head.appendChild(element('span', 'set-rank', '#' + rank));
    card.appendChild(head);
    var details = element('dl', 'set-details');
    var itemLink = 'No item';
    if (item) {
      itemLink = element('a', '', item[1]);
      itemLink.href = 'item.html?id=' + encodeURIComponent(item[0]);
    }
    details.appendChild(detail('Item', itemLink));
    details.appendChild(detail('Ability', tables.abilities[row[2]] || 'None'));
    details.appendChild(detail('Nature', tables.natures[row[3]]));
    details.appendChild(detail('EVs', formatEvs(tables.spreads[row[4]])));
    card.appendChild(details);
    var moves = element('ul', 'set-moves');
    row.slice(5).forEach(function (move) { moves.appendChild(element('li', '', tables.moves[move])); });
    card.appendChild(moves);
    return card;
  }

  function fold(text) {
    return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function currentPool() {
    if (rulesSelect.value === 'fullDex') return tables.pools.fullDex[styleSelect.value];
    return tables.pools.smogon[genSelect.value][styleSelect.value][tierSelect.value];
  }

  function genLabel(gen) {
    return gen === 'nd' ? 'National Dex' : 'Gen ' + gen;
  }

  function setOptions(select, values, label) {
    var previous = select.value;
    select.replaceChildren();
    values.forEach(function (value) { select.add(new Option(label(value), value)); });
    if (values.indexOf(previous) !== -1) select.value = previous;
  }

  // Only what the game offers for this battle type: Doubles have no Gen 1, Gen 2, UU or RU.
  function syncControls() {
    var smogon = rulesSelect.value === 'smogon';
    genField.hidden = tierField.hidden = !smogon;
    if (!smogon) return;
    var style = styleSelect.value;
    var gens = Object.keys(tables.pools.smogon).filter(function (gen) { return tables.pools.smogon[gen][style]; });
    gens.sort(function (a, b) { return (a === 'nd' ? 0 : Number(a)) - (b === 'nd' ? 0 : Number(b)); });
    setOptions(genSelect, gens, genLabel);
    setOptions(tierSelect, Object.keys(TIER_NAMES).filter(function (tier) {
      return tables.pools.smogon[genSelect.value][style][tier];
    }), function (tier) { return TIER_NAMES[tier]; });
  }

  function showMore() {
    var fragment = document.createDocumentFragment();
    shownIds.slice(shownCount, shownCount + PAGE_SIZE).forEach(function (entry) {
      fragment.appendChild(renderSet(entry[0], entry[1]));
    });
    list.appendChild(fragment);
    shownCount = Math.min(shownCount + PAGE_SIZE, shownIds.length);
    more.hidden = shownCount >= shownIds.length;
  }

  function renderSets() {
    var query = fold(search.value.trim());
    shownIds = [];
    var species = {};
    currentPool().forEach(function (id, position) {
      var mon = tables.species[tables.sets[id][0]];
      if (query && fold(mon[1]).indexOf(query) === -1) return;
      shownIds.push([id, position + 1]);
      species[mon[0]] = true;
    });
    var count = shownIds.length;
    if (!count) summary.textContent = 'No sets for that Pokémon under these rules.';
    else summary.textContent = count.toLocaleString() + (count === 1 ? ' set' : ' sets') + ' for '
      + Object.keys(species).length.toLocaleString() + ' Pokémon.';
    list.replaceChildren();
    shownCount = 0;
    showMore();
  }

  function renderTeam(name, ids) {
    var block = element('div', 'brain-team');
    block.appendChild(element('h4', '', name));
    var grid = element('div', 'sets-grid');
    ids.forEach(function (id) { grid.appendChild(renderSet(id)); });
    block.appendChild(grid);
    return block;
  }

  function renderBrain(label, teams) {
    var brain = element('details', 'brain');
    brain.appendChild(element('summary', '', label));
    brain.appendChild(renderTeam('Silver', teams[0]));
    brain.appendChild(renderTeam('Gold', teams[1]));
    return brain;
  }

  // Brains fight with the singles sets of the chosen rule set.
  function renderBrains() {
    var fragment = document.createDocumentFragment();
    var brains = tables.brains;
    if (rulesSelect.value === 'fullDex') {
      brainsText.textContent = 'A team\'s first three fight in the usual format. Noland uses random rentals, so he has no team here.';
      BRAINS.forEach(function (brain) {
        if (brains.fullDex[brain[0]]) fragment.appendChild(renderBrain(brain[1] + ', ' + brain[2], brains.fullDex[brain[0]]));
      });
    } else if (genSelect.value === 'nd') {
      brainsText.textContent = 'National Dex teams for this tier. A team\'s first three fight in the usual format, and all six in 6 vs 6.';
      BRAINS.slice(0, 2).forEach(function (brain) {
        var teams = brains.nationalDex[brain[0]][tierSelect.value];
        if (teams) fragment.appendChild(renderBrain(brain[1] + ', ' + brain[2], teams));
      });
    } else {
      brainsText.textContent = 'In ' + genLabel(genSelect.value) + ', Anabel and Tucker use the strongest sets of the tier: Gold is its first six Pokémon, Silver the next six.';
      var teams = brains.gens[genSelect.value][tierSelect.value];
      if (teams) fragment.appendChild(renderBrain('Anabel and Tucker', teams));
    }
    brainsList.replaceChildren(fragment);
  }

  function update() {
    syncControls();
    renderSets();
    renderBrains();
  }

  function fetchJson(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (response) {
      if (!response.ok) throw new Error('unavailable');
      return response.json();
    });
  }

  fetchJson('data/facilities.json').then(function (data) {
    if (!data.available) {
      status.textContent = 'This release has no Battle Facilities data.';
      return null;
    }
    if (data.intro) { intro.textContent = data.intro; intro.hidden = false; }
    renderSections(data.sections || []);
    if (data.showdownLicense) {
      document.getElementById('sets-license-text').textContent = data.showdownLicense;
      document.getElementById('sets-license').hidden = false;
    }
    document.getElementById('sets-credit').hidden = false;
    return fetchJson('data/frontier_sets.json');
  }).then(function (loaded) {
    if (!loaded) return;
    tables = loaded;
    status.hidden = true;
    setsSection.hidden = false;
    brainsSection.hidden = false;
    [rulesSelect, styleSelect, genSelect, tierSelect].forEach(function (select) {
      select.addEventListener('change', update);
    });
    search.addEventListener('input', renderSets);
    more.addEventListener('click', showMore);
    update();
  }).catch(function () {
    status.textContent = 'Battle facilities could not be loaded. Please try again.';
    status.classList.add('is-error');
  });
}());
