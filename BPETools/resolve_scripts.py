#!/usr/bin/env python3
"""
Resolve git merge conflicts in .inc script files for BPE Emerald.
"""
import re
import os

BASE = "/mnt/e/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion"
CONFLICT_RE = re.compile(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> expansion/1\.15\.0\n', re.DOTALL)

def read_file(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

def has_conflicts(content):
    return '<<<<<<< HEAD' in content

def take_head(content):
    return CONFLICT_RE.sub(lambda m: m.group(1), content)

def take_upstream(content):
    return CONFLICT_RE.sub(lambda m: m.group(2), content)

def take_both_head_first(content):
    return CONFLICT_RE.sub(lambda m: m.group(1) + m.group(2), content)

def resolve_file(relpath, resolver_fn):
    path = os.path.join(BASE, relpath)
    content = read_file(path)
    if not has_conflicts(content):
        print(f'  No conflicts: {relpath}')
        return
    resolved = resolver_fn(content)
    if has_conflicts(resolved):
        print(f'  WARNING - still has conflicts: {relpath}')
    else:
        write_file(path, resolved)
        print(f'  Resolved: {relpath}')

# ---------------------------------------------------------------------------
# EverGrandeCity_ChampionsRoom/scripts.inc
# All conflicts: BPE HEAD empty OR has old LOCALID names, upstream has content/new names
# Strategy: take upstream for all 5 conflicts (upstream adds rival/birch scenes + corrects LOCALID names)
# ---------------------------------------------------------------------------
def resolve_champions_room_scripts():
    path = os.path.join(BASE, 'data/maps/EverGrandeCity_ChampionsRoom/scripts.inc')
    content = read_file(path)
    resolved = take_upstream(content)
    if has_conflicts(resolved):
        print('  WARNING - still has conflicts: ChampionsRoom/scripts.inc')
    else:
        write_file(path, resolved)
        print('  Resolved: EverGrandeCity_ChampionsRoom/scripts.inc')

# ---------------------------------------------------------------------------
# EverGrandeCity_Hall5/scripts.inc
# HEAD: 'turnobject OBJ_EVENT_ID_PLAYER, DIR_NORTH\nsetflag FLAG_ENTERED_ELITE_4\n'
# UPSTREAM: 'turnobject LOCALID_PLAYER, DIR_NORTH\n'
# BPE has a custom flag FLAG_ENTERED_ELITE_4 - must keep it
# Use LOCALID_PLAYER (upstream's rename) + keep the BPE flag
# ---------------------------------------------------------------------------
def resolve_hall5_scripts():
    path = os.path.join(BASE, 'data/maps/EverGrandeCity_Hall5/scripts.inc')
    content = read_file(path)
    old = ('<<<<<<< HEAD\n'
           '\tturnobject OBJ_EVENT_ID_PLAYER, DIR_NORTH\n'
           '\tsetflag FLAG_ENTERED_ELITE_4\n'
           '=======\n'
           '\tturnobject LOCALID_PLAYER, DIR_NORTH\n'
           '>>>>>>> expansion/1.15.0\n')
    new = '\tturnobject LOCALID_PLAYER, DIR_NORTH\n\tsetflag FLAG_ENTERED_ELITE_4\n'
    if old in content:
        resolved = content.replace(old, new)
        write_file(path, resolved)
        print('  Resolved: EverGrandeCity_Hall5/scripts.inc')
    else:
        print('  ERROR - pattern not found in Hall5/scripts.inc')

# ---------------------------------------------------------------------------
# LittlerootTown_BrendansHouse_1F/scripts.inc
# HEAD: 'setvar VAR_0x8004, LOCALID_MOM\nsetvar VAR_0x8005, FEMALE\n'
# UPSTREAM: 'setvar VAR_0x8004, LOCALID_PLAYERS_HOUSE_1F_MOM\nsetvar VAR_0x8005, MALE\n'
# BPE changed gender from MALE to FEMALE (for player gender logic)
# Keep BPE: use new LOCALID name from upstream but keep FEMALE
# ---------------------------------------------------------------------------
def resolve_brendans_house_scripts():
    path = os.path.join(BASE, 'data/maps/LittlerootTown_BrendansHouse_1F/scripts.inc')
    content = read_file(path)
    old = ('<<<<<<< HEAD\n'
           '\tsetvar VAR_0x8004, LOCALID_MOM\n'
           '\tsetvar VAR_0x8005, FEMALE\n'
           '=======\n'
           '\tsetvar VAR_0x8004, LOCALID_PLAYERS_HOUSE_1F_MOM\n'
           '\tsetvar VAR_0x8005, MALE\n'
           '>>>>>>> expansion/1.15.0\n')
    # Keep BPE's FEMALE gender but update to new LOCALID name
    new = '\tsetvar VAR_0x8004, LOCALID_PLAYERS_HOUSE_1F_MOM\n\tsetvar VAR_0x8005, FEMALE\n'
    if old in content:
        resolved = content.replace(old, new)
        write_file(path, resolved)
        print('  Resolved: LittlerootTown_BrendansHouse_1F/scripts.inc')
    else:
        print('  ERROR - pattern not found in BrendansHouse/scripts.inc')

# ---------------------------------------------------------------------------
# MeteorFalls_1F_1R/scripts.inc
# HEAD has .set LOCALID constants, UPSTREAM is empty (upstream removed them - moved to header)
# Keep BPE's constants (they may still be needed by BPE scripts)
# ---------------------------------------------------------------------------
# MtChimney/scripts.inc
# HEAD has custom Moltres battle script, UPSTREAM is empty
# Keep BPE's custom content
# Route119/scripts.inc
# HEAD has .set LOCALID constants, UPSTREAM is empty
# Keep BPE's constants
# These all use take_head strategy.

# ---------------------------------------------------------------------------
# Route101/scripts.inc
# HEAD: BPE version of starter selection script
# UPSTREAM: upstream version with different logic (fadescreen, setobjectxy)
# BPE custom starter logic must be kept
# ---------------------------------------------------------------------------
def resolve_route101_scripts():
    path = os.path.join(BASE, 'data/maps/Route101/scripts.inc')
    content = read_file(path)
    # Take HEAD (BPE's custom starter selection)
    resolved = take_head(content)
    if has_conflicts(resolved):
        print('  WARNING - still has conflicts: Route101/scripts.inc')
    else:
        write_file(path, resolved)
        print('  Resolved: Route101/scripts.inc (kept BPE starter logic)')

# ---------------------------------------------------------------------------
# Route104/scripts.inc
# Two conflicts:
# 1. HEAD: 'copyobjectxytoperm LOCALID_RIVAL\n  msgbox ..._DEFAULT\n  goto BattleMay\n'
#    UPSTREAM: 'copyobjectxytoperm LOCALID_ROUTE104_RIVAL\n  msgbox ..._YESNO\n  goto_if_eq YES, BattleMay\n'
#    BPE forced the battle (no YESNO). Use upstream's LOCALID name but keep BPE's MSGBOX_DEFAULT + goto.
# 2. Same pattern for Brendan version.
# ---------------------------------------------------------------------------
def resolve_route104_scripts():
    path = os.path.join(BASE, 'data/maps/Route104/scripts.inc')
    content = read_file(path)

    # First conflict: May battle
    old1 = ('<<<<<<< HEAD\n'
            '\tcopyobjectxytoperm LOCALID_RIVAL\n'
            '\tmsgbox Route104_Text_MayMinesDecentLetsBattle, MSGBOX_DEFAULT\n'
            '\tgoto Route104_EventScript_BattleMay\n'
            '=======\n'
            '\tcopyobjectxytoperm LOCALID_ROUTE104_RIVAL\n'
            '\tmsgbox Route104_Text_MayMinesDecentLetsBattle, MSGBOX_YESNO\n'
            '\tgoto_if_eq VAR_RESULT, YES, Route104_EventScript_BattleMay\n'
            '>>>>>>> expansion/1.15.0\n')
    # Keep BPE forced battle, update LOCALID to upstream name
    new1 = ('\tcopyobjectxytoperm LOCALID_ROUTE104_RIVAL\n'
            '\tmsgbox Route104_Text_MayMinesDecentLetsBattle, MSGBOX_DEFAULT\n'
            '\tgoto Route104_EventScript_BattleMay\n')

    # Second conflict: Brendan battle
    old2 = ('<<<<<<< HEAD\n'
            '\tcopyobjectxytoperm LOCALID_RIVAL\n'
            '\tmsgbox Route104_Text_BrendanDoingGreatLetsBattle, MSGBOX_DEFAULT\n'
            '\tgoto Route104_EventScript_BattleBrendan\n'
            '=======\n'
            '\tcopyobjectxytoperm LOCALID_ROUTE104_RIVAL\n'
            '\tmsgbox Route104_Text_BrendanDoingGreatLetsBattle, MSGBOX_YESNO\n'
            '\tgoto_if_eq VAR_RESULT, YES, Route104_EventScript_BattleBrendan\n'
            '>>>>>>> expansion/1.15.0\n')
    new2 = ('\tcopyobjectxytoperm LOCALID_ROUTE104_RIVAL\n'
            '\tmsgbox Route104_Text_BrendanDoingGreatLetsBattle, MSGBOX_DEFAULT\n'
            '\tgoto Route104_EventScript_BattleBrendan\n')

    found1 = old1 in content
    found2 = old2 in content
    if found1:
        content = content.replace(old1, new1)
    if found2:
        content = content.replace(old2, new2)

    if found1 or found2:
        if not has_conflicts(content):
            write_file(path, content)
            print(f'  Resolved: Route104/scripts.inc (battles 1={found1}, 2={found2})')
        else:
            print(f'  WARNING - still has conflicts in Route104/scripts.inc')
    else:
        print('  ERROR - patterns not found in Route104/scripts.inc')

# ---------------------------------------------------------------------------
# Route110_TrickHouseEnd/scripts.inc
# HEAD: uses LOCALID_TRICK_MASTER + addobject(2), UPSTREAM: renames to LOCALID_TRICK_MASTER_END
# The map.json may have both - need to check what LOCALID is defined in map
# BPE probably kept LOCALID_TRICK_MASTER. Take upstream's rename to LOCALID_TRICK_MASTER_END
# as that's what the map header will define.
# Actually: keep BPE (take head) since BPE may have custom trick house content.
# Check: HEAD has addobject(2) which is extra. The TRICK_MASTER_END rename is upstream.
# We should take HEAD to preserve BPE's addobject(2) but also update the LOCALID name.
# ---------------------------------------------------------------------------
def resolve_trick_house_end_scripts():
    path = os.path.join(BASE, 'data/maps/Route110_TrickHouseEnd/scripts.inc')
    content = read_file(path)
    old = ('<<<<<<< HEAD\n'
           '\taddobject LOCALID_TRICK_MASTER\n'
           '\taddobject(2)\n'
           '\tshowobjectat LOCALID_TRICK_MASTER, MAP_ROUTE110_TRICK_HOUSE_END\n'
           '\tturnobject LOCALID_TRICK_MASTER, DIR_EAST\n'
           '=======\n'
           '\taddobject LOCALID_TRICK_MASTER_END\n'
           '\tshowobjectat LOCALID_TRICK_MASTER_END, MAP_ROUTE110_TRICK_HOUSE_END\n'
           '\tturnobject LOCALID_TRICK_MASTER_END, DIR_EAST\n'
           '>>>>>>> expansion/1.15.0\n')
    # Keep BPE's addobject(2), use upstream's LOCALID_TRICK_MASTER_END rename
    new = ('\taddobject LOCALID_TRICK_MASTER_END\n'
           '\taddobject(2)\n'
           '\tshowobjectat LOCALID_TRICK_MASTER_END, MAP_ROUTE110_TRICK_HOUSE_END\n'
           '\tturnobject LOCALID_TRICK_MASTER_END, DIR_EAST\n')
    if old in content:
        resolved = content.replace(old, new)
        write_file(path, resolved)
        print('  Resolved: Route110_TrickHouseEnd/scripts.inc')
    else:
        print('  ERROR - pattern not found in Route110_TrickHouseEnd/scripts.inc')

if __name__ == '__main__':
    print('Resolving ChampionsRoom/scripts.inc...')
    resolve_champions_room_scripts()

    print('Resolving Hall5/scripts.inc...')
    resolve_hall5_scripts()

    print('Resolving BrendansHouse_1F/scripts.inc...')
    resolve_brendans_house_scripts()

    print('Resolving MeteorFalls_1F_1R/scripts.inc (take HEAD)...')
    resolve_file('data/maps/MeteorFalls_1F_1R/scripts.inc', take_head)

    print('Resolving MtChimney/scripts.inc (take HEAD)...')
    resolve_file('data/maps/MtChimney/scripts.inc', take_head)

    print('Resolving Route101/scripts.inc...')
    resolve_route101_scripts()

    print('Resolving Route104/scripts.inc...')
    resolve_route104_scripts()

    print('Resolving Route110_TrickHouseEnd/scripts.inc...')
    resolve_trick_house_end_scripts()

    print('Resolving Route119/scripts.inc (take HEAD)...')
    resolve_file('data/maps/Route119/scripts.inc', take_head)

    print('Done.')
