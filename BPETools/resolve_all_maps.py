#!/usr/bin/env python3
"""
Resolve git merge conflicts in all BPE Emerald map JSON files.
Strategy:
- When BPE has a custom graphics_id (CYNTHIA, PANTS, MAN_5, etc.) vs upstream's graphics: keep BPE graphics, add upstream's local_id
- When BPE has empty HEAD (no content) vs upstream adds new objects: take upstream's new objects
- When BPE has content and upstream has different content: keep BPE content, add upstream's local_id if present
"""
import re
import os

BASE = "/mnt/e/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion"

def read_file(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

def has_conflicts(content):
    return '<<<<<<< HEAD' in content

CONFLICT_RE = re.compile(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> expansion/1\.15\.0\n', re.DOTALL)

def resolve_json_conflicts(content, filename):
    """
    Resolve conflicts in a JSON map file.
    For each conflict:
    - If HEAD is empty: take upstream (upstream added new objects)
    - If upstream adds local_id + different graphics vs HEAD has only graphics:
      keep HEAD's graphics, add upstream's local_id
    - Otherwise: keep HEAD (BPE custom content)
    """
    def resolver(m):
        head = m.group(1)
        upstream = m.group(2)

        # Case 1: HEAD is empty, upstream adds content -> take upstream
        if head.strip() == '':
            return upstream

        # Case 2: HEAD has only graphics_id, upstream has local_id + graphics_id
        # Pattern: head = '      "graphics_id": "...",\n'
        # Pattern: upstream = '      "local_id": "...",\n      "graphics_id": "...",\n'
        head_gfx_match = re.match(r'^      "graphics_id": "([^"]+)",\n$', head)
        upstream_local_match = re.match(r'^      "local_id": "([^"]+)",\n      "graphics_id": "([^"]+)",\n$', upstream)

        if head_gfx_match and upstream_local_match:
            # Keep BPE graphics, add upstream's local_id
            local_id = upstream_local_match.group(1)
            bpe_graphics = head_gfx_match.group(1)
            return f'      "local_id": "{local_id}",\n      "graphics_id": "{bpe_graphics}",\n'

        # Case 3: HEAD has content, upstream has different content -> keep HEAD (BPE custom)
        return head

    resolved = CONFLICT_RE.sub(resolver, content)
    return resolved

# Define all files to resolve
JSON_FILES = [
    'data/maps/LavaridgeTown/map.json',
    'data/maps/LavaridgeTown_Gym_1F/map.json',
    'data/maps/LilycoveCity_ContestHall/map.json',
    'data/maps/LittlerootTown_BrendansHouse_1F/map.json',
    'data/maps/LittlerootTown_BrendansHouse_2F/map.json',
    'data/maps/LittlerootTown_MaysHouse_1F/map.json',
    'data/maps/LittlerootTown_MaysHouse_2F/map.json',
    'data/maps/LittlerootTown_ProfessorBirchsLab/map.json',
    'data/maps/OldaleTown/map.json',
    'data/maps/Route103/map.json',
    'data/maps/Route104/map.json',
    'data/maps/Route110/map.json',
    'data/maps/Route119/map.json',
    'data/maps/Route120/map.json',
    'data/maps/RustboroCity/map.json',
    'data/maps/SootopolisCity/map.json',
    'data/maps/TrainerHill_Entrance/map.json',
    'data/maps/VerdanturfTown_Mart/map.json',
    'data/maps/VictoryRoad_1F/map.json',
]

if __name__ == '__main__':
    for relpath in JSON_FILES:
        path = os.path.join(BASE, relpath)
        content = read_file(path)
        if not has_conflicts(content):
            print(f'  No conflicts: {relpath}')
            continue
        resolved = resolve_json_conflicts(content, relpath)
        if has_conflicts(resolved):
            print(f'  WARNING - still has conflicts: {relpath}')
            # Show remaining conflicts
            remaining = CONFLICT_RE.findall(resolved)
            for r in remaining:
                print(f'    HEAD: {repr(r[0][:100])}')
                print(f'    UPSTREAM: {repr(r[1][:100])}')
        else:
            write_file(path, resolved)
            print(f'  Resolved: {relpath}')
    print('Done.')
