#!/usr/bin/env python3
import re

BASE = "/mnt/e/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion"
pattern = re.compile(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> expansion/1\.15\.0\n', re.DOTALL)

files = [
    'data/maps/TrainerHill_Entrance/map.json',
    'data/maps/VerdanturfTown_Mart/map.json',
    'data/maps/VictoryRoad_1F/map.json',
]

import os
for relpath in files:
    fname = os.path.join(BASE, relpath)
    with open(fname, 'r') as f:
        content = f.read()
    matches = list(pattern.finditer(content))
    for i, m in enumerate(matches):
        short = relpath.split('/')[-2]
        print(f'=== {short} Conflict {i+1} ===')
        print('HEAD:', repr(m.group(1)[:200]))
        print('UPSTREAM:', repr(m.group(2)[:300]))
