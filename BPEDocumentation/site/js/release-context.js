(function () {
  'use strict';
  var root = new URL('../', document.currentScript.src);
  var match = root.pathname.match(/\/versions\/([^/]+)\/$/);
  var id = match ? decodeURIComponent(match[1]) : 'development';
  var siteRoot = match ? new URL('../../', root) : root;
  var preference = 'bpe:' + siteRoot.pathname + ':selected-release';
  var context = window.BPERelease = { id: id, root: root, siteRoot: siteRoot, leaving: false };
  function getJson(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (response) {
      if (!response.ok) throw new Error('Release information is unavailable.');
      return response.json();
    });
  }
  context.ready = getJson(new URL('release.json', root)).then(function (release) {
    if (release.version !== id) throw new Error('The page and release information do not match.');
    return release;
  });
  context.ready.catch(function () {});
  context.catalog = function () { return getJson(new URL('versions.json', siteRoot)); };
  context.remember = function (value) { try { window.localStorage.setItem(preference, value); } catch (_) {} };
  context.switchTo = async function (release) {
    if (release.version === id || context.leaving) return;
    var relative = location.pathname.slice(root.pathname.length) || 'index.html';
    var targetRoot = new URL(release.path, siteRoot);
    var target = new URL(relative, targetRoot);
    target.search = location.search;
    target.hash = location.hash;
    var entity = new URLSearchParams(location.search).get('id');
    var detail = relative === 'pokemon.html' ? ['data/species/', 'pokedex.html'] : relative === 'item.html' ? ['data/items/', 'items.html'] : null;
    if (detail && entity) {
      var response = await fetch(new URL(detail[0] + encodeURIComponent(entity) + '.json', targetRoot));
      if (response.status === 404) {
        target = new URL(detail[1], targetRoot);
        target.searchParams.set('missing', entity);
      } else if (!response.ok) throw new Error('Could not check this page in the selected release. Please retry.');
    }
    // Pages added in later releases are absent from older snapshots.
    var laterPages = { 'features.html': 'Features', 'save-converter.html': 'Save Converter' };
    if (laterPages[relative]) {
      var page = await fetch(new URL(relative, targetRoot), { method: 'HEAD', cache: 'no-cache' });
      if (page.status === 404) {
        target = new URL('index.html', targetRoot);
        target.searchParams.set('missing-page', laterPages[relative]);
      } else if (!page.ok) throw new Error('Could not check this page in the selected release. Please retry.');
    }
    var mapId = target.searchParams.get('map');
    if ((relative === 'index.html' || relative === '') && mapId) {
      var world = await getJson(new URL('js/data/world.json', targetRoot));
      if (!world.maps.some(function (map) { return map.id === mapId; })) {
        target.search = '';
        target.hash = '';
        target.searchParams.set('missing', mapId);
      }
    }
    context.remember(release.version);
    context.leaving = true;
    window.dispatchEvent(new Event('bpe:versionchange'));
    location.assign(target.href);
  };
  // Calculator game state is scoped by repository and release. Display settings are shared.
  var shared = ['themeIndex', 'boxspriteindex', 'boxrolls', 'battlenotes'];
  var memory = Object.create(null);
  var keyFor = function (key) { return 'bpe:' + siteRoot.pathname + ':calc:' + (shared.indexOf(key) >= 0 ? 'display' : id) + ':' + key; };
  var storage = {
    getItem: function (key) { try { return window.localStorage.getItem(keyFor(key)); } catch (_) { return memory[key] || null; } },
    setItem: function (key, value) { memory[key] = String(value); try { window.localStorage.setItem(keyFor(key), String(value)); } catch (_) {} },
    removeItem: function (key) { delete memory[key]; try { window.localStorage.removeItem(keyFor(key)); } catch (_) {} }
  };
  window.BPEStorage = new Proxy(storage, {
    get: function (object, key) {
      if (key in object) return object[key];
      var value = object.getItem(key);
      return value === null ? undefined : value;
    },
    set: function (object, key, value) { object.setItem(key, value); return true; },
    deleteProperty: function (object, key) { object.removeItem(key); return true; }
  });
}());
