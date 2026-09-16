(function () {
  'use strict';

  // All text comes from this release's data/features.json and is inserted as
  // text, never as HTML.
  var status = document.getElementById('features-status');
  var intro = document.getElementById('features-intro');
  var sectionsRoot = document.getElementById('features-sections');
  var legendaries = document.getElementById('legendaries');
  var legendariesBody = document.getElementById('legendaries-body');
  var legendariesHint = document.getElementById('legendaries-hint');

  function element(name, className, text) {
    var node = document.createElement(name);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function renderSections(sections) {
    var fragment = document.createDocumentFragment();
    sections.forEach(function (section) {
      var block = element('section', 'features-section');
      block.id = section.id;
      block.appendChild(element('h2', '', section.title));
      var grid = element('div', 'features-grid');
      section.items.forEach(function (item) {
        var card = element('article', 'features-card');
        card.appendChild(element('h3', '', item.title));
        card.appendChild(element('p', '', item.body));
        grid.appendChild(card);
      });
      block.appendChild(grid);
      fragment.appendChild(block);
    });
    sectionsRoot.replaceChildren(fragment);
  }

  function legendaryRow(entry) {
    var row = element('li', 'legendary-row');
    var id = entry.species.replace(/^SPECIES_/, '');
    var mon = element('a', 'legendary-mon');
    mon.href = 'pokemon.html?id=' + encodeURIComponent(id);
    if (entry.sprite) {
      var icon = element('img', 'legendary-icon');
      icon.src = 'img/pokemon/' + entry.sprite;
      icon.alt = '';
      icon.loading = 'lazy';
      icon.addEventListener('error', function () { icon.remove(); });
      mon.appendChild(icon);
    }
    mon.appendChild(element('span', 'legendary-name', entry.name));
    row.appendChild(mon);
    row.appendChild(element('span', 'legendary-level', 'Lv ' + entry.level));
    var place = element('a', 'legendary-place', entry.place);
    place.href = 'index.html?map=' + encodeURIComponent(entry.mapId) + '&static=' + encodeURIComponent(id);
    place.title = 'Show on the interactive map';
    row.appendChild(place);
    if (entry.note) row.appendChild(element('p', 'legendary-note', entry.note));
    return row;
  }

  function legendaryGroup(title, entries, description) {
    var group = element('section', 'legendary-group');
    group.appendChild(element('h3', '', title));
    if (description) group.appendChild(element('p', 'legendary-group-text', description));
    var list = element('ul', 'legendary-list');
    entries.forEach(function (entry) { list.appendChild(legendaryRow(entry)); });
    group.appendChild(list);
    return group;
  }

  function renderLegendaries(data) {
    var groups = data.legendaries || { preE4: [], others: [] };
    var pre = groups.preE4 || [], others = groups.others || [];
    if (!pre.length && !others.length) return;
    var fragment = document.createDocumentFragment();
    if (data.legendaryIntro) fragment.appendChild(element('p', 'legendary-intro', data.legendaryIntro));
    if (data.rules && data.rules.length) {
      var rules = element('ul', 'legendary-rules');
      data.rules.forEach(function (rule) { rules.appendChild(element('li', '', rule)); });
      fragment.appendChild(rules);
    }
    if (pre.length) {
      fragment.appendChild(legendaryGroup('Pre-Elite Four legendaries (' + pre.length + ')', pre,
        'You can battle only one of these before becoming Champion.'));
    }
    if (others.length) {
      fragment.appendChild(legendaryGroup(data.curated ? 'Other legendaries and special encounters' : 'Other legendaries', others));
    }
    legendariesBody.replaceChildren(fragment);
    legendariesHint.textContent = pre.length + others.length + ' encounters';
    legendaries.hidden = false;
    if (location.hash === '#legendaries') {
      legendaries.open = true;
      legendaries.scrollIntoView();
    }
  }

  fetch('data/features.json', { cache: 'no-cache' }).then(function (response) {
    if (!response.ok) throw new Error('unavailable');
    return response.json();
  }).then(function (data) {
    if (data.curated) {
      if (data.intro) { intro.textContent = data.intro; intro.hidden = false; }
      renderSections(data.sections || []);
      status.hidden = true;
    } else {
      status.textContent = 'This release has no feature overview. Legendary encounters below are read from its game data.';
    }
    renderLegendaries(data);
    if (!data.curated && legendaries.hidden) status.textContent = 'This release has no feature overview.';
  }).catch(function () {
    status.textContent = 'Features could not be loaded. Please try again.';
    status.classList.add('is-error');
  });

  window.addEventListener('hashchange', function () {
    if (location.hash === '#legendaries' && !legendaries.hidden) {
      legendaries.open = true;
      legendaries.scrollIntoView();
    }
  });
}());
