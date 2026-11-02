#!/usr/bin/env python3
"""Reject sets that break set-building sense, then write out/checked/ and print a review sample.

Run with: python -I validate_sets.py
"""
import collections
import glob
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, '..', '..'))
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
hp = lambda s: re.sub(r'^hiddenpower.*', 'hiddenpower', s)

MI = {}
for b in re.split(r'\n\s*\[MOVE_', open(os.path.join(REPO, 'src/data/moves_info.h'), encoding='utf8').read())[1:]:
    n = norm(b.split(']')[0])
    c = re.search(r'\.category\s*=\s*DAMAGE_CATEGORY_(\w+)', b)
    t = re.search(r'\.type\s*=\s*TYPE_(\w+)', b)
    p = re.search(r'\.power\s*=\s*(\d+)', b)
    MI[n] = (c.group(1) if c else 'STATUS', t.group(1) if t else '', int(p.group(1)) if p else 0)

TYPES = {}
for f in glob.glob(os.path.join(REPO, 'src/data/pokemon/species_info/*families.h')):
    for b in re.split(r'\n\s*\[SPECIES_', open(f, encoding='utf8').read())[1:]:
        m = re.search(r'\.types\s*=\s*MON_TYPES\(([^)]*)\)', b)
        if m:
            TYPES[norm(b.split(']')[0])] = set(re.findall(r'TYPE_(\w+)', m.group(1)))


def types(s):
    if s in TYPES:
        return TYPES[s]
    c = [k for k in TYPES if s.startswith(k)]
    return TYPES[max(c, key=len)] if c else set()


NATURES = set('hardy lonely brave adamant naughty bold docile relaxed impish lax timid hasty serious jolly naive modest mild quiet bashful rash calm gentle sassy careful quirky'.split())
ORB = {'flameorb': {'guts', 'flareboost', 'marvelscale', 'quickfeet', 'magicguard', 'toxicboost'},
       'toxicorb': {'poisonheal', 'toxicboost', 'guts', 'marvelscale', 'quickfeet', 'magicguard'}}
ORB_MOVES = {'trick', 'switcheroo', 'fling', 'facade', 'psychoshift'}
WEATHER_ROCK = {'heatrock': {'sunnyday', 'drought', 'orichalcumpulse'}, 'damprock': {'raindance', 'drizzle'},
                'smoothrock': {'sandstorm', 'sandstream', 'sandspit'}, 'icyrock': {'hail', 'snowscape', 'snowwarning', 'chillyreception'}}
LOCKED = {'lightball': ('pikachu',), 'thickclub': ('cubone', 'marowak'), 'leek': ('farfetchd', 'sirfetchd'), 'luckypunch': ('chansey',),
          'souldew': ('latias', 'latios'), 'adamantorb': ('dialga',), 'lustrousorb': ('palkia',), 'griseousorb': ('giratina',),
          'griseouscore': ('giratina',), 'adamantcrystal': ('dialga',), 'lustrousglobe': ('palkia',)}


def problems(s):
    out = []
    m, it, ab, ev, sp = s['moves'], s['item'], s['ability'], s['evs'], s['species']
    if len(set(m)) != 4:
        out.append('moves')
    if sum(ev) > 510 or max(ev) > 255:
        out.append('evs')
    if s['nature'] not in NATURES:
        out.append('nature')
    cats = [MI.get(hp(x), ('STATUS', '', 0)) for x in m]
    attacks = [c for c in cats if c[0] != 'STATUS']
    t = types(sp)
    if not attacks:
        out.append('no attacks')
    if ev[1] >= 128 and not any(c[0] == 'PHYSICAL' and (c[2] >= 50 or c[2] <= 1) for c in cats) and 'foulplay' not in m:
        out.append('attack EVs with no physical move')
    if ev[3] >= 128 and not any(c[0] == 'SPECIAL' and (c[2] >= 50 or c[2] <= 1) for c in cats):
        out.append('special EVs with no special move')
    if it in ('choiceband', 'choicespecs', 'choicescarf', 'assaultvest') and any(
            MI.get(hp(x), ('STATUS',))[0] == 'STATUS' and x not in ('trick', 'switcheroo') for x in m):
        out.append('choice or vest with status move')
    if it == 'choicescarf' and ev[5] == 0:
        out.append('scarf with no speed')
    if s['grade'] != 'A' or s.get('evidence'):
        down_atk = s['nature'] in ('modest', 'timid', 'bold', 'calm')
        down_spa = s['nature'] in ('adamant', 'jolly', 'impish', 'careful')
        if down_atk and any(c[0] == 'PHYSICAL' and c[2] >= 60 for c in cats) and 'foulplay' not in m and 'bodypress' not in m:
            out.append('nature lowers the attack it uses')
        if down_spa and any(c[0] == 'SPECIAL' and c[2] >= 60 for c in cats):
            out.append('nature lowers the attack it uses')
        if 'facade' in m and it not in ORB and ab != 'guts':
            out.append('facade with no status')
        setups = set(m) & {'swordsdance', 'dragondance', 'bulkup', 'nastyplot', 'calmmind', 'quiverdance', 'irondefense', 'amnesia', 'cosmicpower', 'coil', 'curse', 'shiftgear'}
        if len(setups) > 1 and 'storedpower' not in m and 'bodypress' not in m:
            out.append('two setup moves')
        if setups and 'trickroom' in m:
            out.append('setup move with trick room')
    if it == 'focussash' and ev[0] >= 100 and s['grade'] != 'A':
        out.append('focus sash on a bulky spread')
    if s['grade'] == 'C' and 'bodypress' in m and ev[1] < 128 and ev[2] < 128:
        out.append('body press with no investment')
    if it == 'lifeorb' and len(attacks) < 2:
        out.append('life orb on non-attacker')
    if it in ORB and ab not in ORB[it] and not set(m) & ORB_MOVES:
        out.append('orb with no use')
    if it == 'blacksludge' and 'POISON' not in t and not set(m) & {'trick', 'switcheroo'}:
        out.append('black sludge on non-poison')
    if it in WEATHER_ROCK and not (WEATHER_ROCK[it] & (set(m) | {ab})):
        out.append('weather rock with no weather')
    if it == 'lightclay' and not set(m) & {'reflect', 'lightscreen', 'auroraveil'}:
        out.append('light clay with no screens')
    if it in LOCKED and not any(sp.startswith(x) for x in LOCKED[it]):
        out.append('item for another Pokemon')
    if 'trickroom' in m and ev[5] >= 100:
        out.append('trick room with speed EVs')
    if set(m) & {'swordsdance', 'dragondance', 'bulkup'} and sum(c[0] == 'PHYSICAL' for c in cats) == 0:
        out.append('physical setup without physical moves')
    if set(m) & {'nastyplot', 'calmmind', 'quiverdance'} and sum(c[0] == 'SPECIAL' for c in cats) == 0 and 'storedpower' not in m:
        out.append('special setup without special moves')
    if t and s['grade'] != 'A' and not any(c[1] in t for c in attacks) and not set(m) & {'foulplay', 'bodypress', 'seismictoss', 'nightshade', 'superfang'}:
        out.append('no same-type attack')
    return out


os.makedirs(os.path.join(ROOT, 'out', 'checked'), exist_ok=True)
rej = collections.Counter()
out = {}
random.seed(7)
for tier in ('AG', 'Ubers', 'OU', 'UU', 'RU', 'DOU', 'DUber', 'FullDex', 'FullDexDoubles'):
    d = json.load(open(os.path.join(ROOT, 'out', tier + '.json'), encoding='utf8'))
    keep = []
    for s in d:
        p = problems(s)
        if p:
            rej.update(p)
        else:
            keep.append(s)
    json.dump(keep, open(os.path.join(ROOT, 'out', 'checked', tier + '.json'), 'w', encoding='utf8'), indent=0)
    g = collections.Counter(s['grade'] for s in keep)
    sp = set(s['form'] for s in keep)
    spa = set(s['form'] for s in keep if s['grade'] == 'A')
    spb = set(s['form'] for s in keep if s['grade'] in 'AB')
    print(tier, 'sets', len(keep), dict(g), 'species', len(sp), 'A', len(spa), 'AB', len(spb), 'dropped', len(d) - len(keep))
    out[tier] = keep
print(rej.most_common())
