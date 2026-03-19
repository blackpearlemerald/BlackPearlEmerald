#!/usr/bin/env python3
"""
Resolve git merge conflicts in BPE Emerald map files.
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

def resolve_take_head(content):
    """Take HEAD (BPE) side of all conflicts."""
    pattern = r'<<<<<<< HEAD\n(.*?)=======\n.*?>>>>>>> expansion/1\.15\.0\n'
    return re.sub(pattern, r'\1', content, flags=re.DOTALL)

def resolve_take_upstream(content):
    """Take upstream side of all conflicts."""
    pattern = r'<<<<<<< HEAD\n.*?=======\n(.*?)>>>>>>> expansion/1\.15\.0\n'
    return re.sub(pattern, r'\1', content, flags=re.DOTALL)

def resolve_take_both(content):
    """Take both sides - head first, then upstream."""
    pattern = r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> expansion/1\.15\.0\n'
    return re.sub(pattern, r'\1\2', content, flags=re.DOTALL)

def fix_file(relpath, resolver_fn):
    path = os.path.join(BASE, relpath)
    content = read_file(path)
    if not has_conflicts(content):
        print(f"  No conflicts: {relpath}")
        return
    resolved = resolver_fn(content)
    if has_conflicts(resolved):
        print(f"  WARNING - still has conflicts: {relpath}")
    else:
        write_file(path, resolved)
        print(f"  Resolved: {relpath}")

# ---------------------------------------------------------------------------
# EverGrandeCity_ChampionsRoom/map.json
# Conflict: upstream adds local_id + changes graphics to WALLACE
# BPE: uses OBJ_EVENT_GFX_PANTS (custom Cynthia-related NPC)
# Resolution: keep BPE graphics, add upstream's local_id
# ---------------------------------------------------------------------------
def resolve_champions_room_map():
    path = os.path.join(BASE, "data/maps/EverGrandeCity_ChampionsRoom/map.json")
    content = read_file(path)
    # The conflict is just the first object's graphics_id vs local_id+graphics_id
    # HEAD has only graphics_id: OBJ_EVENT_GFX_PANTS
    # Upstream has local_id: LOCALID_CHAMPIONS_ROOM_WALLACE + graphics_id: OBJ_EVENT_GFX_WALLACE
    # Keep BPE graphics_id (PANTS), add upstream's local_id
    old = ('    {\n'
           '<<<<<<< HEAD\n'
           '      "graphics_id": "OBJ_EVENT_GFX_PANTS",\n'
           '=======\n'
           '      "local_id": "LOCALID_CHAMPIONS_ROOM_WALLACE",\n'
           '      "graphics_id": "OBJ_EVENT_GFX_WALLACE",\n'
           '>>>>>>> expansion/1.15.0\n'
           '      "x": 6,\n'
           '      "y": 5,')
    new = ('    {\n'
           '      "local_id": "LOCALID_CHAMPIONS_ROOM_WALLACE",\n'
           '      "graphics_id": "OBJ_EVENT_GFX_PANTS",\n'
           '      "x": 6,\n'
           '      "y": 5,')
    if old in content:
        content = content.replace(old, new)
        write_file(path, content)
        print("  Resolved: EverGrandeCity_ChampionsRoom/map.json")
    else:
        print(f"  ERROR - pattern not found in ChampionsRoom/map.json")
        print(repr(content[content.find('<<<<<<'):content.find('>>>>>>>') + 30] if '<<<<<<' in content else 'no conflict'))

# ---------------------------------------------------------------------------
# EverGrandeCity_HallOfFame/map.json
# Same pattern - upstream adds local_id + changes graphics to WALLACE
# BPE: uses OBJ_EVENT_GFX_PANTS (custom NPC)
# ---------------------------------------------------------------------------
def resolve_hall_of_fame_map():
    path = os.path.join(BASE, "data/maps/EverGrandeCity_HallOfFame/map.json")
    content = read_file(path)
    old = ('    {\n'
           '<<<<<<< HEAD\n'
           '      "graphics_id": "OBJ_EVENT_GFX_PANTS",\n'
           '=======\n'
           '      "local_id": "LOCALID_HALL_OF_FAME_WALLACE",\n'
           '      "graphics_id": "OBJ_EVENT_GFX_WALLACE",\n'
           '>>>>>>> expansion/1.15.0\n'
           '      "x": 6,\n'
           '      "y": 16,')
    new = ('    {\n'
           '      "local_id": "LOCALID_HALL_OF_FAME_WALLACE",\n'
           '      "graphics_id": "OBJ_EVENT_GFX_PANTS",\n'
           '      "x": 6,\n'
           '      "y": 16,')
    if old in content:
        content = content.replace(old, new)
        write_file(path, content)
        print("  Resolved: EverGrandeCity_HallOfFame/map.json")
    else:
        print(f"  ERROR - pattern not found in HallOfFame/map.json")

# ---------------------------------------------------------------------------
# EverGrandeCity_PokemonLeague_1F/map.json
# Two conflicts: upstream adds local_id to two guard NPCs, changes GFX_MAN_5 -> GFX_MAN_3
# BPE: uses GFX_MAN_5 for guards (custom choice)
# Resolution: add upstream's local_ids, keep BPE's GFX_MAN_5
# ---------------------------------------------------------------------------
def resolve_pokemon_league_1f_map():
    path = os.path.join(BASE, "data/maps/EverGrandeCity_PokemonLeague_1F/map.json")
    content = read_file(path)
    # First guard conflict
    old1 = ('    {\n'
            '<<<<<<< HEAD\n'
            '      "graphics_id": "OBJ_EVENT_GFX_MAN_5",\n'
            '=======\n'
            '      "local_id": "LOCALID_LEAGUE_GUARD_1",\n'
            '      "graphics_id": "OBJ_EVENT_GFX_MAN_3",\n'
            '>>>>>>> expansion/1.15.0\n'
            '      "x": 8,\n'
            '      "y": 2,')
    new1 = ('    {\n'
            '      "local_id": "LOCALID_LEAGUE_GUARD_1",\n'
            '      "graphics_id": "OBJ_EVENT_GFX_MAN_5",\n'
            '      "x": 8,\n'
            '      "y": 2,')
    # Second guard conflict
    old2 = ('    {\n'
            '<<<<<<< HEAD\n'
            '      "graphics_id": "OBJ_EVENT_GFX_MAN_5",\n'
            '=======\n'
            '      "local_id": "LOCALID_LEAGUE_GUARD_2",\n'
            '      "graphics_id": "OBJ_EVENT_GFX_MAN_3",\n'
            '>>>>>>> expansion/1.15.0\n'
            '      "x": 11,\n'
            '      "y": 2,')
    new2 = ('    {\n'
            '      "local_id": "LOCALID_LEAGUE_GUARD_2",\n'
            '      "graphics_id": "OBJ_EVENT_GFX_MAN_5",\n'
            '      "x": 11,\n'
            '      "y": 2,')
    found1 = old1 in content
    found2 = old2 in content
    if found1:
        content = content.replace(old1, new1)
    if found2:
        content = content.replace(old2, new2)
    if found1 or found2:
        write_file(path, content)
        print(f"  Resolved: EverGrandeCity_PokemonLeague_1F/map.json (guard1={found1}, guard2={found2})")
    else:
        print(f"  ERROR - patterns not found in PokemonLeague_1F/map.json")

if __name__ == '__main__':
    print("Resolving ChampionsRoom...")
    resolve_champions_room_map()
    print("Resolving HallOfFame...")
    resolve_hall_of_fame_map()
    print("Resolving PokemonLeague_1F...")
    resolve_pokemon_league_1f_map()
    print("Done.")
