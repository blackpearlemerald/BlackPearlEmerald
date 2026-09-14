(function () {
  'use strict';

  var context = window.BPERelease;
  var list = document.getElementById('version-history-list');
  var status = document.getElementById('version-history-status');

  function element(name, className, text) {
    var node = document.createElement(name);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function badge(text, modifier) {
    return element('span', 'version-badge' + (modifier ? ' ' + modifier : ''), text);
  }

  function renderRelease(release, catalog) {
    var entry = element('article', 'version-entry' + (release.version === catalog.latest ? ' is-latest' : ''));
    var head = element('header', 'version-entry-head');
    var title = element('div', 'version-title-row');
    var download = element('a', 'version-download', 'Manual patch download');
    var changes = element('section', 'version-changes');
    var changeList = element('ul');

    title.appendChild(element('h2', '', release.label));
    if (release.version === catalog.latest) title.appendChild(badge('Latest'));
    if (release.version.indexOf('-') >= 0) title.appendChild(badge('Beta', 'is-beta'));
    if (release.version === context.id) title.appendChild(badge('Selected', 'is-selected'));

    download.href = new URL(release.patchUrl, context.siteRoot).href;
    download.setAttribute('download', '');
    download.setAttribute('aria-label', 'Download the ' + release.label + ' patch');
    head.appendChild(title);
    head.appendChild(download);

    changes.appendChild(element('h3', '', 'Changes'));
    release.changes.forEach(function (change) {
      changeList.appendChild(element('li', '', change));
    });
    changes.appendChild(changeList);
    entry.appendChild(head);
    entry.appendChild(changes);
    return entry;
  }

  if (!context) {
    status.textContent = 'Version history is unavailable.';
    status.classList.add('is-error');
    return;
  }

  context.catalog().then(function (catalog) {
    var fragment = document.createDocumentFragment();
    catalog.releases.forEach(function (release) {
      fragment.appendChild(renderRelease(release, catalog));
    });
    list.replaceChildren(fragment);
    status.hidden = true;
  }).catch(function () {
    status.textContent = 'Version history could not be loaded. Please try again.';
    status.classList.add('is-error');
  });
}());
