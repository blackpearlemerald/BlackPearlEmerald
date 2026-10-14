(function () {
  'use strict';

  // All text comes from this release's data/trainer_ai.json and is inserted as
  // text, never as HTML.
  var status = document.getElementById('ai-status');
  var title = document.getElementById('ai-title');
  var intro = document.getElementById('ai-intro');
  var tools = document.getElementById('ai-tools');
  var toc = document.getElementById('ai-toc');
  var filter = document.getElementById('ai-filter');
  var empty = document.getElementById('ai-empty');
  var sectionsRoot = document.getElementById('ai-sections');

  // A line that starts with a score change ("+6", "-20", "Additional +1") or
  // says the move is never used gets the score styling.
  var SCORE_LINE = /^(?:(?:Additional|Total|Starts at|Base:?)\s+)?[+\-−]\d|^Never used/;

  function element(name, className, text) {
    var node = document.createElement(name);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function renderRules(rules) {
    var list = element('ul', 'ai-rules');
    var last = null;
    rules.forEach(function (rule) {
      if (Array.isArray(rule)) {
        last.appendChild(renderRules(rule));
        return;
      }
      last = element('li', SCORE_LINE.test(rule) ? 'is-score' : (/:$/.test(rule) ? 'is-condition' : ''));
      last.appendChild(element('span', '', rule));
      list.appendChild(last);
    });
    return list;
  }

  function renderTable(table) {
    var wrap = element('div', 'ai-table-wrap');
    var grid = element('table', 'ai-table');
    var headRow = element('tr');
    table.columns.forEach(function (column) {
      var cell = element('th', '', column);
      cell.scope = 'col';
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

  function flatten(rules, out) {
    rules.forEach(function (rule) {
      if (Array.isArray(rule)) flatten(rule, out); else out.push(rule);
    });
    return out;
  }

  function slug(text) {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  function renderEntry(entry, sectionId) {
    var card = element('article', entry.wide || entry.table ? 'ai-entry is-wide' : 'ai-entry');
    card.id = sectionId + '-' + slug(entry.name);
    var heading = element('h3');
    var anchor = element('a', '', entry.name);
    anchor.href = '#' + card.id;
    heading.appendChild(anchor);
    card.appendChild(heading);
    (entry.text || []).forEach(function (text) { card.appendChild(element('p', '', text)); });
    if (entry.table) card.appendChild(renderTable(entry.table));
    if (entry.rules) card.appendChild(renderRules(entry.rules));
    if (entry.notes && entry.notes.length) {
      var notes = element('div', 'ai-notes');
      entry.notes.forEach(function (note) { notes.appendChild(element('p', '', note)); });
      card.appendChild(notes);
    }
    // Matching searches the name first; the body text catches moves listed
    // inside a group heading such as "Spikes, Toxic Spikes".
    card.dataset.name = entry.name.toLowerCase();
    card.dataset.body = (entry.text || []).concat(flatten(entry.rules || [], []), entry.notes || []).join(' ').toLowerCase();
    return card;
  }

  function render(data) {
    title.textContent = data.title;
    data.intro.forEach(function (text) { intro.appendChild(element('p', '', text)); });
    var fragment = document.createDocumentFragment();
    data.sections.forEach(function (section) {
      var block = element('section', 'ai-section');
      block.id = section.id;
      block.appendChild(element('h2', '', section.title));
      (section.intro || []).forEach(function (text) { block.appendChild(element('p', 'ai-section-intro', text)); });
      var grid = element('div', 'ai-entries');
      section.entries.forEach(function (entry) { grid.appendChild(renderEntry(entry, section.id)); });
      block.appendChild(grid);
      fragment.appendChild(block);
      var link = element('a', '', section.title);
      link.href = '#' + section.id;
      toc.appendChild(link);
    });
    sectionsRoot.replaceChildren(fragment);
    tools.hidden = false;
    status.hidden = true;
    if (location.hash) {
      var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) target.scrollIntoView();
    }
  }

  function applyFilter() {
    var query = filter.value.trim().toLowerCase();
    var any = false;
    sectionsRoot.querySelectorAll('.ai-section').forEach(function (section) {
      var shown = 0;
      section.querySelectorAll('.ai-entry').forEach(function (card) {
        var match = !query || card.dataset.name.indexOf(query) !== -1 || card.dataset.body.indexOf(query) !== -1;
        card.hidden = !match;
        if (match) shown++;
      });
      section.hidden = shown === 0;
      if (shown) any = true;
    });
    empty.hidden = any;
  }

  filter.addEventListener('input', applyFilter);

  fetch('data/trainer_ai.json', { cache: 'no-cache' }).then(function (response) {
    if (!response.ok) throw new Error('unavailable');
    return response.json();
  }).then(function (data) {
    if (data.curated) render(data);
    else status.textContent = 'This release has no Trainer AI document.';
  }).catch(function () {
    status.textContent = 'The Trainer AI document could not be loaded. Please try again.';
    status.classList.add('is-error');
  });
}());
