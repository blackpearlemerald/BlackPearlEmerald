(function () {
  'use strict';
  var inCalc = /\/calc\//.test(location.pathname);
  var prefix = inCalc ? '../' : '';
  var calcHref = (inCalc ? 'index.html' : 'calc/index.html') + '?data=bpe&gen=8&dmgGen=8&types=9&customPoks=1';
  var current = inCalc ? 'calc' : (location.pathname.split('/').pop() || 'index.html').replace('.html', '');
  if (current === 'pokemon') current = 'pokedex';
  if (current === 'item') current = 'items';
  var items = [
    ['index.html', 'Interactive Map', 'index'], ['features.html', 'Features', 'features'], ['search.html', 'Global Search', 'search'],
    ['pokedex.html', 'Pokédex', 'pokedex'], ['trainers.html', 'Trainers', 'trainers'],
    ['items.html', 'Items', 'items'], [null, 'Damage Calculator', 'calc'],
    ['patcher.html', 'Rom Patcher', 'patcher'], ['save-converter.html', 'Save Converter', 'save-converter'],
    ['version-history.html', 'Version History', 'version-history'],
    ['socials.html', 'Socials', 'socials']
  ];
  var header = document.createElement('header');
  header.id = 'site-header';
  header.innerHTML = '<div class="bpe-version-bar"><div><span class="bpe-version-caption">GAME &amp; DOCUMENTATION</span>' +
    '<strong class="bpe-current-version" id="bpe-current-version">Loading version…</strong></div>' +
    '<div class="bpe-version-control"><label for="bpe-version-select">Switch version</label>' +
    '<select id="bpe-version-select" disabled><option>Loading releases…</option></select></div></div>' +
    '<nav id="site-nav" aria-label="Main navigation"><a class="nav-brand" href="' + prefix + 'index.html">BPE Emerald</a><div class="nav-links">' +
    items.map(function (item) { return '<a class="nav-link' + (current === item[2] ? ' active' : '') + '" href="' + (item[0] ? prefix + item[0] : calcHref) + '">' + item[1] + '</a>'; }).join('') +
    '</div></nav><p class="bpe-release-notice" role="status" hidden></p>';
  document.body.prepend(header);
  var select = document.getElementById('bpe-version-select');
  var title = document.getElementById('bpe-current-version');
  var notice = header.querySelector('.bpe-release-notice');
  var baseDocumentTitle = document.title;
  function displayLabel(release) {
    return release.label + (release.channel === 'beta' && !/\bbeta$/i.test(release.label) ? ' Beta' : '');
  }
  function showNotice(text) { notice.textContent = text; notice.hidden = false; }
  function switchRelease(release) {
    select.disabled = true;
    return context.switchTo(release).catch(function (error) { select.disabled = false; select.value = context.id; showNotice(error.message); });
  }
  // Older-release banner: name the newest release and offer a one-click switch.
  function showOlderNotice(latest) {
    notice.replaceChildren(document.createTextNode('You are viewing an older release. Match this version to the version shown in your game. The newest release is ' + displayLabel(latest) + '. '));
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'bpe-release-notice-switch';
    button.textContent = 'Switch to ' + displayLabel(latest);
    button.addEventListener('click', function () { button.disabled = true; switchRelease(latest).then(function () { button.disabled = false; }); });
    notice.appendChild(button);
    notice.hidden = false;
  }
  function resize() { document.documentElement.style.setProperty('--bpe-header-height', header.offsetHeight + 'px'); window.dispatchEvent(new Event('bpe:headerresize')); }
  if (window.ResizeObserver) new ResizeObserver(resize).observe(header);
  window.addEventListener('resize', resize);
  resize();
  var context = window.BPERelease;
  if (!context) { title.textContent = 'Version unavailable'; return; }
  context.ready.then(function (release) {
    title.textContent = release.label;
    document.title = baseDocumentTitle + ' — ' + release.label;
    context.remember(release.version);
    if (release.notice) showNotice(release.notice);
    select.replaceChildren(new Option(release.label, release.version));
    return context.catalog();
  }).then(function (catalog) {
    var selectedRelease = catalog.releases.find(function (release) { return release.version === context.id; });
    if (selectedRelease) {
      title.textContent = displayLabel(selectedRelease);
      document.title = baseDocumentTitle + ' — ' + displayLabel(selectedRelease);
    }
    select.replaceChildren();
    catalog.releases.forEach(function (release) {
      select.add(new Option(displayLabel(release) + (release.version === catalog.latest ? ' · Latest' : ''), release.version, false, release.version === context.id));
    });
    if (!catalog.releases.some(function (release) { return release.version === context.id; })) select.add(new Option(title.textContent + ' · Archived', context.id, true, true));
    select.disabled = false;
    select.addEventListener('change', function () {
      var release = catalog.releases.find(function (item) { return item.version === select.value; });
      if (!release || release.version === context.id) return;
      switchRelease(release);
    });
    var latest = catalog.releases.find(function (release) { return release.version === catalog.latest; });
    if (context.id !== catalog.latest && latest) showOlderNotice(latest);
    var params = new URLSearchParams(location.search);
    var missing = params.get('missing');
    if (missing) showNotice(missing.replace(/_/g, ' ') + ' is not available in this release. Showing its listing instead.');
    var missingPage = params.get('missing-page');
    if (missingPage) showNotice('The ' + missingPage + ' page is not available in this release.');
  }).catch(function (error) {
    if (context.id === 'development') title.textContent = 'Development preview';
    else if (title.textContent === 'Loading version…') title.textContent = context.id;
    select.replaceChildren(new Option(title.textContent, context.id));
    showNotice(context.id === 'development' ? 'Unpublished preview. Release packages provide versioned documentation and patches.' : error.message);
  });
}());
