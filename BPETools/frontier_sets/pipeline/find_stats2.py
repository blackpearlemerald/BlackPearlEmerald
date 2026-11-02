#!/usr/bin/env python3
"""For each Gen 1-9 format, download the month with the most data, using the top cutoff with real volume.

Stats files before 2016-11 name Gen 6 formats without a prefix. Run with python -I.
"""
import json
import os
import re
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'stats')
BASE = 'https://www.smogon.com/stats'
TIERS = ['ou', 'ubers', 'uu', 'ru', 'nu', 'pu', 'anythinggoes', 'doublesou', 'doublesubers', 'doublesuu']
EXTRA = ['gen9nationaldex', 'gen9nationaldexubers', 'gen9nationaldexuu', 'gen9nationaldexru', 'gen9nationaldexag', 'gen9nationaldexdoubles', 'gen9nationaldexdoublesubers']
UA = {'User-Agent': 'BPE-frontier-set-research'}
SIZE_UNITS = {'K': 1e3, 'M': 1e6, 'G': 1e9, '': 1}


def get(url, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
        except Exception as e:
            err = e
            time.sleep(2 * (i + 1))
    raise err


months = [f'{y}-{m:02d}' for y in range(2026, 2013, -1) for m in range(12, 0, -1) if not (y == 2026 and m > 10)]
want = {f'gen{g}{t}' for g in range(1, 10) for t in TIERS} | set(EXTRA)
best = {}
for month in months:
    try:
        html = get(f'{BASE}/{month}/chaos/').decode('utf8', 'replace')
    except Exception:
        continue
    for name, cut, size in re.findall(r'href="([a-z0-9]+)-(\d+)\.json">[^<]*</a>\s+\S+\s+\S+\s+(\d+)', html):
        cut = int(cut)
        if not name.startswith('gen'):
            name = 'gen6' + name
        if name not in want or cut < 1500:
            continue
        size = int(size)
        # Prefer the highest cutoff that still has real data; favour newer months a little.
        score = size * (1.6 if cut >= 1760 else 1.3 if cut >= 1630 else 1.0)
        if name not in best or score > best[name][0] * 1.15:
            best[name] = (score, month, cut, size)
    time.sleep(.12)

print(len(best), 'of', len(want), 'formats found')
os.makedirs(OUT, exist_ok=True)
got = {}
for name, (_, month, cut, size) in sorted(best.items()):
    prefix = name if int(month[:4]) > 2016 or (month >= '2016-11') or not name.startswith('gen6') else name[4:]
    fn = f'{month}-{name}-{cut}.json'
    path = os.path.join(OUT, fn)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        try:
            open(path, 'wb').write(get(f'{BASE}/{month}/chaos/{prefix}-{cut}.json'))
        except Exception as e:
            print('failed', name, month, cut, e)
            continue
    d = json.load(open(path, encoding='utf8'))
    got[name] = dict(file=fn, month=month, cutoff=cut, battles=d['info']['number of battles'], species=len(d['data']))
    time.sleep(.15)
json.dump(got, open(os.path.join(ROOT, 'stats_index.json'), 'w'), indent=1)
for k in sorted(got):
    print(k, got[k]['month'], got[k]['cutoff'], got[k]['battles'], got[k]['species'])
