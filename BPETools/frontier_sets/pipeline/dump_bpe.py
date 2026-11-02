#!/usr/bin/env python3
"""Dump what BPE knows about species, moves and items for the Node pipeline. Run with python -I."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
os.environ.setdefault('BPE_SHOWDOWN_DATA', ROOT)
src = open('build_sets.py', encoding='utf8').read()
head = src[:src.index('# Tiers and bans')]
ns = {'__file__': os.path.join(ROOT, 'build_sets.py')}
exec(compile(head, 'build_sets_head', 'exec'), ns)

species = {}
for s in sorted(ns['SPECIES']):
    species[s] = dict(moves=sorted(ns['legal_moves'](s)), abilities=sorted(ns['species_abilities'](s)))
allLearn = {ns['norm'](k): sorted(ns['norm'](m.replace('MOVE_', '')) for m in v) for k, v in ns['ALL_LEARN'].items()}
out = dict(species=species, items=sorted(ns['ITEMS']), moves=ns['MOVE_INFO'], defaults=list(ns['DEFAULT_FORMS']),
           abilityAlias=ns['ABILITY_ALIAS'], allLearn=allLearn, frontierBanned=sorted(ns['FRONTIER_BANNED']))
json.dump(out, open('bpe_data.json', 'w', encoding='utf8'))
print(len(species), 'species', len(out['moves']), 'moves', len(out['items']), 'items')
