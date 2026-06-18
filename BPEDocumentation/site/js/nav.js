(function () {
  var NAV_ITEMS = [
    { href: 'index.html',   label: 'Interactive Map'    },
    { href: 'search.html',  label: 'Global Search'      },
    { href: 'pokedex.html', label: 'Pokédex'            },
    { href: 'items.html',   label: 'Items'              },
    { href: 'calc.html',    label: 'Damage Calculator'  },
  ];

  // Resolve current page filename ('index.html', 'search.html', etc.)
  var current = location.pathname.split('/').pop();
  if (!current || current === '') current = 'index.html';

  var links = NAV_ITEMS.map(function (p) {
    var cls = 'nav-link' + (current === p.href ? ' active' : '');
    return '<a href="' + p.href + '" class="' + cls + '">' + p.label + '</a>';
  }).join('');

  var nav = document.createElement('nav');
  nav.id = 'site-nav';
  nav.innerHTML =
    '<span class="nav-brand">BPE Emerald</span>' +
    '<div class="nav-links">' + links + '</div>';

  document.body.prepend(nav);
}());
