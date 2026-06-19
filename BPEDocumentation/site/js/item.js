(function () {
  'use strict';

  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function fmtPrice(price) {
    if (!price || price === 0) return 'Not for sale';
    return '₽' + price.toLocaleString();
  }

  function render(item) {
    var content = document.getElementById('item-content');
    document.title = 'BPE Emerald — ' + item.name;

    var iconHtml = item.icon
      ? '<img class="item-icon-large" src="' + item.icon + '" alt="' + esc(item.name) + '" />'
      : '<div class="item-icon-large-noimg">?</div>';

    var badge = '<span class="item-pocket-badge pocket-' + esc(item.pocket) + '">'
      + esc(item.pocketLabel) + '</span>';

    var metaRows = [
      ['Pocket',    item.pocketLabel || '—'],
      ['Price',     fmtPrice(item.price)],
    ];
    if (item.sortType) {
      metaRows.push(['Category', item.sortType]);
    }

    var metaHtml = metaRows.map(function (row) {
      return '<div class="item-meta-row">'
        + '<span class="item-meta-label">' + esc(row[0]) + '</span>'
        + '<span class="item-meta-value">' + esc(String(row[1])) + '</span>'
        + '</div>';
    }).join('');

    var descHtml = item.description
      ? '<p class="item-description">' + esc(item.description) + '</p>'
      : '';

    content.innerHTML =
      '<div class="item-header">'
      + iconHtml
      + '<div>'
      +   '<h1 class="item-title">' + esc(item.name) + '</h1>'
      +   badge
      + '</div>'
      + '</div>'
      + descHtml
      + '<div class="item-meta-card">'
      +   '<h3>Details</h3>'
      +   metaHtml
      + '</div>';
  }

  function init() {
    var params = new URLSearchParams(window.location.search);
    var itemId = params.get('id');
    if (!itemId) {
      document.getElementById('item-content').innerHTML =
        '<div class="dex-empty">No item specified. '
        + '<a href="items.html" style="color:#4db87a">Back to Items</a></div>';
      return;
    }

    fetch('data/items/' + encodeURIComponent(itemId) + '.json')
      .then(function (r) {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then(function (item) { render(item); })
      .catch(function () {
        document.getElementById('item-content').innerHTML =
          '<div class="dex-empty">Could not load data for <strong>' + esc(itemId) + '</strong>.<br>'
          + 'Run the parser script first, or '
          + '<a href="items.html" style="color:#4db87a">go back</a>.</div>';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
