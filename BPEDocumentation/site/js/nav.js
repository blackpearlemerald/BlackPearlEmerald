(function () {
  // The calculator lives in the /calc/ subdirectory; doc pages are one level up.
  var inCalc = /\/calc\//.test(location.pathname);
  var prefix = inCalc ? '../' : '';
  var calcQuery = '?data=bpe&gen=8&dmgGen=8&types=9&customPoks=1';
  var calcHref = (inCalc ? 'index.html' : 'calc/index.html') + calcQuery;

  var NAV_ITEMS = [
    { href: prefix + 'index.html',    label: 'Interactive Map', key: 'index'    },
    { href: prefix + 'search.html',   label: 'Global Search',   key: 'search'   },
    { href: prefix + 'pokedex.html',  label: 'Pokédex',         key: 'pokedex'  },
    { href: prefix + 'trainers.html', label: 'Trainers',        key: 'trainers' },
    { href: prefix + 'items.html',    label: 'Items',           key: 'items'    },
    { href: calcHref,                 label: 'Damage Calculator', key: 'calc'   },
    { href: prefix + 'patcher.html',  label: 'The Patcher',     key: 'patcher'  },
    { href: prefix + 'socials.html',  label: 'Socials',         key: 'socials'  },
  ];

  // Resolve which nav item is active.
  var currentKey;
  if (inCalc) {
    currentKey = 'calc';
  } else {
    var current = location.pathname.split('/').pop();
    if (!current || current === '') current = 'index.html';
    if (current === 'pokemon.html') current = 'pokedex.html';
    if (current === 'item.html')    current = 'items.html';
    currentKey = current.replace('.html', '');
  }

  var links = NAV_ITEMS.map(function (p) {
    var cls = 'nav-link' + (currentKey === p.key ? ' active' : '');
    return '<a href="' + p.href + '" class="' + cls + '">' + p.label + '</a>';
  }).join('');

  var nav = document.createElement('nav');
  nav.id = 'site-nav';
  nav.innerHTML =
    '<a class="nav-brand" href="' + prefix + 'index.html">BPE Emerald</a>' +
    '<div class="nav-links">' + links + '</div>';

  document.body.prepend(nav);
}());
