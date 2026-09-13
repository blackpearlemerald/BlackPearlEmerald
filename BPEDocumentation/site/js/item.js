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

  function prettify(name) {
    if (!name) return '';
    name = name.replace(/^(ITEM_|MAP_)/, '');
    return name.split('_').map(function(w) {
      return w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w;
    }).join(' ').replace(/([A-Za-z])(\d)/g, '$1 $2');
  }

  function whereToFind(locs, itemId) {
    if (!locs) return '';
    var marts = locs.marts || [];
    var overworld = locs.overworld || [];
    var gifts = locs.gifts || [];
    if (!marts.length && !overworld.length && !gifts.length) return '';

    // Each link deep-links into the map and tells it what to snap to.
    function link(mapId, extra, label, trailing) {
      var href = 'index.html?map=' + encodeURIComponent(mapId) + extra;
      return '<div class="where-row">'
        + '<a href="' + href + '" class="where-map-link">' + esc(label) + '</a>'
        + (trailing || '')
        + '</div>';
    }

    var html = '<div class="item-where-card"><h3>Where to Find</h3>';

    if (marts.length) {
      html += '<div class="where-section"><div class="where-section-label">🛒 Poké Mart</div>';
      marts.forEach(function(m) {
        html += link(m.mapId, '&mart=1', m.martName,
          '<span class="where-cond">' + esc(m.condition) + '</span>');
      });
      html += '</div>';
    }

    if (overworld.length) {
      // Deduplicate by mapId
      var seen = {};
      var unique = overworld.filter(function(o) {
        if (seen[o.mapId]) return false;
        seen[o.mapId] = true;
        return true;
      });
      html += '<div class="where-section"><div class="where-section-label">⚪ Item Ball</div>';
      unique.forEach(function(o) {
        var hiddenLabel = o.hidden ? ' <span class="where-hidden">(hidden)</span>' : '';
        html += link(o.mapId, '&item=' + encodeURIComponent(itemId), o.mapName, hiddenLabel);
      });
      html += '</div>';
    }

    if (gifts.length) {
      html += '<div class="where-section"><div class="where-section-label">🎁 Care Package</div>';
      gifts.forEach(function(g) {
        var qtyLabel = g.qty > 1 ? ' <span class="where-qty">×' + g.qty + '</span>' : '';
        html += link(g.mapId, '&gift=' + encodeURIComponent(itemId), g.mapName, qtyLabel);
      });
      html += '</div>';
    }

    html += '</div>';
    return html;
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
      + '</div>'
      + whereToFind(item.locations, item.id);
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
