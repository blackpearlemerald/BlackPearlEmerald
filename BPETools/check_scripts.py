#!/usr/bin/env python3
import re, os

BASE = "/mnt/e/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion"
CONFLICT_RE = re.compile(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> expansion/1\.15\.0\n', re.DOTALL)

files = [
    'data/maps/EverGrandeCity_ChampionsRoom/scripts.inc',
    'data/maps/EverGrandeCity_Hall5/scripts.inc',
    'data/maps/LittlerootTown_BrendansHouse_1F/scripts.inc',
    'data/maps/MeteorFalls_1F_1R/scripts.inc',
    'data/maps/MtChimney/scripts.inc',
    'data/maps/Route101/scripts.inc',
    'data/maps/Route104/scripts.inc',
    'data/maps/Route110_TrickHouseEnd/scripts.inc',
    'data/maps/Route119/scripts.inc',
]

for relpath in files:
    path = os.path.join(BASE, relpath)
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    matches = list(CONFLICT_RE.finditer(content))
    short = relpath.split('/')[-2]
    print(f'=== {short} ({len(matches)} conflicts) ===')
    for i, m in enumerate(matches):
        head = m.group(1)
        upstream = m.group(2)
        print(f'  Conflict {i+1}:')
        print(f'    HEAD ({len(head)} chars): {repr(head[:300])}')
        print(f'    UPSTREAM ({len(upstream)} chars): {repr(upstream[:300])}')
