#!/usr/bin/env python3
"""Build a candidate Frontier set pool from Showdown's Factory sets and Smogon usage stats.

Grades:
  A  Showdown Factory or Battle Stadium set, or usage set from current high-ladder play
     with every chosen part common on that Pokemon.
  B  Usage set from an older generation or with less common parts.
  C  Built from Showdown's curated Random Battle moves, with a role-based item and spread.

Reads only data files. Run with: python -I build_sets.py
"""
import collections
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, '..', '..'))
SCRATCH = os.environ['BPE_SHOWDOWN_DATA']
OUT = os.path.join(ROOT, 'out')

norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
ABILITY_ALIAS = {'asoneglastrier': 'asoneicerider', 'asonespectrier': 'asoneshadowrider'}
norm_ab = lambda s: ABILITY_ALIAS.get(norm(s), norm(s))
hp = lambda s: re.sub(r'^hiddenpower.*', 'hiddenpower', s)


def rd(p):
    return open(os.path.join(REPO, p), encoding='utf8').read()


# BPE data ----------------------------------------------------------------
SPECIES = set(norm(x) for x in re.findall(r'SPECIES_(\w+)\s*=', rd('include/constants/species.h')))
ITEMS = set(norm(x) for x in re.findall(r'\bITEM_(\w+)\s*=', rd('include/constants/items.h')))

MOVE_INFO = {}
for b in re.split(r'\n\s*\[MOVE_', rd('src/data/moves_info.h'))[1:]:
    name = norm(b.split(']')[0])
    cat = re.search(r'\.category\s*=\s*DAMAGE_CATEGORY_(\w+)', b)
    typ = re.search(r'\.type\s*=\s*TYPE_(\w+)', b)
    pow_ = re.search(r'\.power\s*=\s*(\d+)', b)
    MOVE_INFO[name] = dict(cat=cat.group(1) if cat else 'STATUS', type=typ.group(1) if typ else '',
                           power=int(pow_.group(1)) if pow_ else 0)

learn = collections.defaultdict(set)
files = glob.glob(os.path.join(REPO, 'src/data/pokemon/level_up_learnsets/*.h'))
files += [os.path.join(REPO, 'src/data/pokemon/teachable_learnsets.h'), os.path.join(REPO, 'src/data/pokemon/egg_moves.h')]
for f in files:
    t = open(f, encoding='utf8').read()
    for m in re.finditer(r's(\w+?)(?:LevelUp|Teachable|EggMove)Learnset\[\]\s*=\s*\{(.*?)\};', t, re.S):
        for x in re.findall(r'MOVE_(\w+)', m.group(2)):
            learn[norm(m.group(1))].add(norm(x))
for k in list(learn):
    if k.endswith('singlestrike'):
        learn[k[:-12]] |= learn[k]

ALL_LEARN = json.load(open(os.path.join(REPO, 'src/data/pokemon/all_learnables.json'), encoding='utf8'))
ROOST = set(norm(k) for k, v in ALL_LEARN.items() if 'MOVE_ROOST' in v)

pre, abilities = {}, {}
FRONTIER_BANNED = set()
for f in glob.glob(os.path.join(REPO, 'src/data/pokemon/species_info/*families.h')):
    t = open(f, encoding='utf8').read()
    macros = {}
    for mname, body in re.findall(r'#define (\w+_ABILITIES)\s*\{(.*?)\}', t):
        macros.setdefault(mname, body)
    for b in re.split(r'\n\s*\[SPECIES_', t)[1:]:
        a = norm(b.split(']')[0])
        ab = re.findall(r'\.abilities\s*=\s*\{(.*?)\}', b, re.S)
        ab += [macros.get(x, '') for x in re.findall(r'\.abilities\s*=\s*(\w+_ABILITIES)', b)]
        first = b.split('\n')[0]
        if not ab and 'ABILITY_' in first:
            ab = [first]
        abilities[a] = set(norm(x) for s in ab for x in re.findall(r'ABILITY_(\w+)', s)) - {'none'}
        if '.isFrontierBanned = TRUE' in b:
            FRONTIER_BANNED.add(a)
        for e in re.findall(r'EVOLUTION\((.*?)\)\s*,?\n', b, re.S):
            for tgt in re.findall(r'SPECIES_(\w+)', e):
                pre.setdefault(norm(tgt), a)


def base_learn(s):
    if s in learn:
        return s
    c = [k for k in learn if s.startswith(k)]
    return max(c, key=len) if c else None


def legal_moves(s):
    out, seen, q = set(), set(), [s, base_learn(s) or s]
    while q:
        x = q.pop()
        if x in seen or x is None:
            continue
        seen.add(x)
        out |= learn.get(x, set())
        if x in ROOST:
            out.add('roost')
        b = base_learn(x)
        if b and b != x:
            q.append(b)
        for k in (x, b):
            if k in pre:
                q.append(pre[k])
    if s.startswith('rotom'):
        out |= {'overheat', 'hydropump', 'blizzard', 'airslash', 'leafstorm'}
    return out


DEFAULT_FORMS = ('normal', 'hero', 'incarnate', 'altered', 'singlestrike', 'midday', 'disguised', 'tealmask', 'west', 'teal', 'male',
                 'aria', 'ordinary', 'red', 'plant', 'overcast', 'standard', 'fifty', 'fiftypercent', 'solo', 'shield', 'land', 'white',
                 'natural', 'baile', 'core', 'fullbelly', 'zero', 'gulping', 'ice', 'familyofthree', 'twosegment', 'average', 'confined',
                 'amped', 'phantom', 'unremarkable')


def species_id(name):
    s = norm(name)
    if s in SPECIES:
        return s
    for suffix in DEFAULT_FORMS:
        if s + suffix in SPECIES:
            return s + suffix
    c = sorted((k for k in SPECIES if k.startswith(s)), key=len)
    return c[0] if c else None


def species_abilities(s):
    if s in abilities and abilities[s]:
        return abilities[s]
    c = [k for k in abilities if s.startswith(k) and abilities[k]]
    if c:
        return abilities[max(c, key=len)]
    # Base names such as SPECIES_THUNDURUS are aliases of a default form.
    for suffix in DEFAULT_FORMS:
        if abilities.get(s + suffix):
            return abilities[s + suffix]
    c = sorted((k for k in abilities if k.startswith(s) and abilities[k] and not re.search(r'mega[xy]?$', k)), key=len)
    return abilities[c[0]] if c else set()


# Tiers and bans ----------------------------------------------------------
t = open(os.path.join(SCRATCH, 'formats-data.ts'), encoding='utf8').read()
TIER = {}
for m in re.finditer(r'\n\t(\w+): \{(.*?)\n\t\}', t, re.S):
    a = re.search(r'natDexTier: "([^"]+)"', m.group(2))
    c = re.search(r'\btier: "([^"]+)"', m.group(2))
    v = a.group(1) if a else (c.group(1) if c else None)
    if v:
        TIER[m.group(1)] = v
BUCKET = {'AG': 'AG', 'Uber': 'Ubers', 'OU': 'OU', '(OU)': 'OU', 'UUBL': 'OU', 'UU': 'UU', 'RUBL': 'UU', 'RU': 'RU'}

BASE_MOVES = {'assist', 'batonpass', 'lastrespects', 'shedtail', 'fissure', 'guillotine', 'horndrill', 'sheercold',
              'doubleteam', 'minimize', 'terablast', 'terastarstorm', 'tera', 'swagger'}
BASE_ABILITIES = {'arenatrap', 'moody', 'powerconstruct', 'shadowtag', 'sandveil', 'snowcloak'}
BASE_ITEMS = {'kingsrock', 'quickclaw', 'razorfang', 'brightpowder', 'laxincense'}
TIER_ALIAS = {}
for k in TIER:
    a = species_id(k)
    if a and a != k:
        TIER_ALIAS.setdefault(a, k)

BANS = {
    'OU': (BASE_MOVES, BASE_ABILITIES, BASE_ITEMS),
    'Ubers': ({'assist', 'batonpass', 'doubleteam', 'minimize', 'terablast', 'fissure', 'guillotine', 'horndrill', 'sheercold'},
              set(), {'brightpowder', 'laxincense'}),
    'UU': (BASE_MOVES, BASE_ABILITIES | {'drizzle', 'drought'}, BASE_ITEMS | {'lightclay'}),
    'RU': (BASE_MOVES, BASE_ABILITIES | {'drizzle', 'drought'}, BASE_ITEMS | {'lightclay', 'slowbronite'}),
    'AG': ({'terablast'}, set(), set()),
    'DOU': ({'assist', 'coaching', 'darkvoid', 'swagger', 'terablast', 'doubleteam', 'minimize', 'fissure', 'guillotine', 'horndrill', 'sheercold'},
            {'commander', 'powerconstruct', 'shadowtag', 'sandveil', 'snowcloak'}, {'eeviumz', 'brightpowder', 'laxincense'}),
    'FullDex': ({'terablast'}, set(), set()),
    'FullDexDoubles': ({'terablast'}, set(), set()),
    'DUber': ({'assist', 'terablast', 'doubleteam', 'minimize', 'fissure', 'guillotine', 'horndrill', 'sheercold'}, set(), set()),
}
DOU_BANNED = set(norm(x) for x in """Annihilape Arceus Calyrex-Ice Calyrex-Shadow Deoxys-Attack Dialga Dialga-Origin Espathra
Eternatus Genesect Gengar-Mega Giratina Giratina-Origin Groudon Ho-Oh Koraidon Kyogre Kyurem-White Lugia Lunala Magearna
Marshadow Melmetal Metagross-Mega Mewtwo Miraidon Necrozma-Dawn-Wings Necrozma-Dusk-Mane Necrozma-Ultra Palkia Palkia-Origin
Rayquaza Reshiram Shedinja Solgaleo Stakataka Terapagos Urshifu Urshifu-Rapid-Strike Xerneas Yveltal Zacian Zacian-Crowned
Zamazenta Zamazenta-Crowned Zekrom Zygarde-50 Zygarde-Complete""".split())

# Set rules ---------------------------------------------------------------
PHYS_SETUP = {'swordsdance', 'bulkup', 'dragondance', 'bellydrum', 'coil', 'howl', 'shiftgear', 'curse', 'victorydance', 'honeclaws', 'tidyup', 'filletaway'}
SPEC_SETUP = {'nastyplot', 'calmmind', 'quiverdance', 'tailglow', 'geomancy', 'takeheart'}
GROUPS = [
    {'recover', 'roost', 'softboiled', 'slackoff', 'synthesis', 'moonlight', 'morningsun', 'milkdrink', 'shoreup', 'strengthsap', 'rest'},
    {'protect', 'detect', 'kingsshield', 'spikyshield', 'banefulbunker', 'silktrap', 'burningbulwark', 'obstruct'},
    {'uturn', 'voltswitch', 'flipturn', 'partingshot', 'teleport', 'chillyreception'},
    {'toxic', 'willowisp', 'thunderwave', 'spore', 'sleeppowder', 'glare', 'stunspore', 'hypnosis', 'lovelykiss', 'yawn'},
]
UTILITY_ATTACKS = {'uturn', 'voltswitch', 'flipturn', 'knockoff', 'fakeout', 'rapidspin', 'mortalspin', 'trailblaze', 'icywind',
                   'snarl', 'electroweb', 'bulldoze', 'foulplay', 'nightshade', 'seismictoss', 'superfang', 'ruination'}
TYPE_Z = {'normaliumz': 'NORMAL', 'firiumz': 'FIRE', 'wateriumz': 'WATER', 'electriumz': 'ELECTRIC', 'grassiumz': 'GRASS', 'iciumz': 'ICE',
          'fightiniumz': 'FIGHTING', 'poisoniumz': 'POISON', 'groundiumz': 'GROUND', 'flyiniumz': 'FLYING', 'psychiumz': 'PSYCHIC',
          'buginiumz': 'BUG', 'rockiumz': 'ROCK', 'ghostiumz': 'GHOST', 'dragoniumz': 'DRAGON', 'darkiniumz': 'DARK', 'steeliumz': 'STEEL', 'fairiumz': 'FAIRY'}
NATURES_DOWN_ATK = {'modest', 'timid', 'bold', 'calm'}
NATURES_DOWN_SPA = {'adamant', 'jolly', 'impish', 'careful'}
BANNED_AS_SOURCE = {'nothing', ''}


def mega_form(species, item):
    i = norm(item)
    if i in ('eviolite', 'meteorite') or not re.search(r'ite[xy]?$', i):
        return None
    suffix = 'megax' if i.endswith('itex') else 'megay' if i.endswith('itey') else 'mega'
    form = species + suffix
    return form if form in SPECIES else None


def cat(move):
    return MOVE_INFO.get(hp(move), {}).get('cat')


def pick_moves(pool, cls, item, doubles):
    """pool is [(move, share)] sorted by share. Returns four moves or None."""
    only_attacks = item in ('choiceband', 'choicespecs', 'choicescarf', 'assaultvest')
    chosen, taken_groups, seen_types = [], set(), {}
    for mv, share in pool:
        if len(chosen) == 4:
            break
        c = cat(mv)
        if c is None:
            continue
        if only_attacks and c == 'STATUS' and not (mv in ('trick', 'switcheroo') and item.startswith('choice')):
            continue
        if cls == 'phys' and (mv in SPEC_SETUP or (c == 'SPECIAL' and share < .5 and mv not in UTILITY_ATTACKS)):
            continue
        if cls == 'spec' and (mv in PHYS_SETUP or (c == 'PHYSICAL' and share < .5 and mv not in UTILITY_ATTACKS)):
            continue
        group = next((i for i, g in enumerate(GROUPS) if mv in g), None)
        if group is not None and group in taken_groups and share < .45:
            continue
        info = MOVE_INFO[hp(mv)]
        key = (info['type'], c)
        if c != 'STATUS' and mv not in UTILITY_ATTACKS and key in seen_types and share < .45:
            continue
        chosen.append((mv, share))
        if group is not None:
            taken_groups.add(group)
        if c != 'STATUS':
            seen_types[key] = mv
    if len(chosen) < 4:
        return None
    attacks = sum(cat(m) != 'STATUS' for m, _ in chosen)
    if attacks == 0 or (cls in ('phys', 'spec') and attacks < 2):
        return None
    return chosen


def classify(spread):
    nat, evs = spread.split(':')
    v = [int(x) for x in evs.split('/')]
    return nat.lower(), v, ('mixed' if v[1] >= 128 and v[3] >= 128 else 'phys' if v[1] >= 128 else 'spec' if v[3] >= 128 else 'bulky')


def usage_sets(path, doubles):
    d = json.load(open(path, encoding='utf8'))
    meta = d['info']['metagame']
    gen = int(re.match(r'gen(\d)', meta).group(1))
    current = os.path.basename(path).startswith('2026') and gen == 9
    for name, v in d['data'].items():
        species = species_id(name)
        if not species or v.get('usage', 0) < .005 or v.get('Raw count', 0) < 60:
            continue
        W = sum(v['Abilities'].values())
        if W <= 0:
            continue
        spreads = sorted(v['Spreads'].items(), key=lambda kv: -kv[1])
        classes = collections.defaultdict(list)
        for sp, w in spreads:
            if sp.startswith('Other'):
                continue
            nat, evs, cls = classify(sp)
            if (cls == 'phys' and nat in NATURES_DOWN_ATK) or (cls == 'spec' and nat in NATURES_DOWN_SPA):
                continue
            classes[cls].append((sp, w))
        for cls, group in classes.items():
            share = sum(w for _, w in group) / W
            if share < .15 or group[0][1] / W < .04 or cls == 'mixed':
                continue
            sp = group[0][0]
            nat, evs, _ = classify(sp)
            lm = legal_moves(species)
            pool = sorted(((m, w / W) for m, w in v['Moves'].items() if m and w / W >= .10 and hp(m) in lm), key=lambda kv: -kv[1])
            items = sorted(((i, w / W) for i, w in v['Items'].items() if i not in BANNED_AS_SOURCE and w / W >= .12 and i in ITEMS), key=lambda kv: -kv[1])
            made = 0
            for item, ishare in items:
                if made == 2:
                    break
                form = mega_form(species, item)
                if re.search(r'ite[xy]?$', item) and item not in ('eviolite', 'meteorite') and not form:
                    continue
                if cls == 'bulky' and item in ('focussash', 'expertbelt', 'lifeorb', 'widelens'):
                    continue
                if (item == 'choiceband' and cls != 'phys') or (item == 'choicespecs' and cls != 'spec') or (item == 'choicescarf' and cls == 'bulky'):
                    continue
                chosen = pick_moves(pool, cls, item, doubles)
                if not chosen:
                    continue
                if item in TYPE_Z and not any(MOVE_INFO[hp(m)]['type'] == TYPE_Z[item] and cat(m) != 'STATUS' for m, _ in chosen):
                    continue
                legal_ab = species_abilities(species)
                ab = next((norm_ab(a) for a, w in sorted(v['Abilities'].items(), key=lambda kv: -kv[1]) if norm_ab(a) in legal_ab and w / W >= .2), None)
                if not ab:
                    continue
                low = min(s for _, s in chosen)
                if low < .12:
                    continue
                grade = 'A' if current and low >= .25 and ishare >= .15 else 'B'
                yield dict(species=species, form=form or species, item=item, ability=ab, nature=nat, evs=evs,
                           moves=sorted(m for m, _ in chosen), grade=grade, source=meta,
                           evidence=dict(usage=round(v['usage'], 4), raw=v['Raw count'], lowestMove=round(low, 2), item=round(ishare, 2)))
                made += 1


def factory_sets():
    def walk(o, tn=None):
        for k, v in o.items():
            if isinstance(v, dict) and 'sets' in v:
                yield tn, k, v['sets']
            elif isinstance(v, dict):
                yield from walk(v, k)
    for g in ('gen9-factory', 'gen8-factory', 'gen7-factory', 'gen9-bss', 'gen8-bss', 'gen7-bss'):
        o = json.load(open(os.path.join(SCRATCH, g + '.json'), encoding='utf8'))
        for tn, k, ss in walk(o):
            if tn in ('Mono', 'LC'):
                continue
            for s in ss:
                species = species_id(s.get('species', k))
                if not species:
                    continue
                as_list = lambda x: x if isinstance(x, list) else [x]
                items = [norm(i) for i in as_list(s.get('item', []))]
                item = next((i for i in items if i in ITEMS), None)
                if not item or len(s.get('moves', [])) < 4:
                    continue
                form = None
                if re.search(r'mega[xy]?$', species):
                    form, species = species, re.sub(r'mega[xy]?$', '', species)
                elif mega_form(species, item):
                    form = mega_form(species, item)
                lm = legal_moves(species)
                moves, bad = [], False
                for slot in s['moves'][:4]:
                    opts = [norm(x) for x in as_list(slot)]
                    good = next((m for m in opts if hp(m) in lm and hp(m) in MOVE_INFO), None)
                    if not good:
                        bad = True
                        break
                    moves.append(good)
                if bad or len(set(moves)) < 4:
                    continue
                ab = next((norm_ab(a) for a in as_list(s.get('ability', [])) if norm_ab(a) in species_abilities(species)), None)
                if not ab:
                    continue
                e = s.get('evs', {})
                evs = [e.get(k2, 0) for k2 in ('hp', 'atk', 'def', 'spa', 'spd', 'spe')]
                nat = norm(as_list(s.get('nature', ['serious']))[0])
                yield dict(species=species, form=form or species, item=item, ability=ab, nature=nat, evs=evs,
                           moves=sorted(moves), grade='A', source=g, evidence={})


def random_sets(path, doubles):
    src = os.path.basename(path).replace('.json', '')
    d = json.load(open(path, encoding='utf8'))
    for name, v in d.items():
        species = species_id(name)
        if not species:
            continue
        lm = legal_moves(species)
        for s in v.get('sets', []):
            role = s.get('role', '')
            mvs = [norm(m) for m in s.get('movepool', [])]
            mvs = [m for m in mvs if hp(m) in lm and hp(m) in MOVE_INFO and m != 'terablast']
            if len(mvs) < 4:
                continue
            phys = sum(cat(m) == 'PHYSICAL' for m in mvs)
            spec = sum(cat(m) == 'SPECIAL' for m in mvs)
            bulky = any(x in role for x in ('Bulky', 'Staller', 'Support', 'Protect', 'Redirection'))
            attacker = 'phys' if phys >= spec else 'spec'
            cls = attacker if not bulky or role in ('Bulky Attacker', 'Bulky Setup') else 'bulky'
            item = 'sitrusberry' if doubles else ('leftovers' if bulky else 'lifeorb')
            pool = [(m, 1 - i * .01) for i, m in enumerate(mvs)]
            chosen = pick_moves(pool, cls, item, doubles)
            if not chosen:
                continue
            legal_ab = species_abilities(species)
            ab = next((norm(a) for a in s.get('abilities', []) if norm(a) in legal_ab), None)
            if not ab:
                continue
            if cls == 'bulky':
                nat, evs = ('bold' if phys <= spec else 'impish'), [252, 0, 128, 0, 128, 0]
            elif bulky:
                nat, evs = ('adamant' if cls == 'phys' else 'modest'), [252, 252 if cls == 'phys' else 0, 0, 252 if cls == 'spec' else 0, 4, 0]
            else:
                nat, evs = ('jolly' if cls == 'phys' else 'timid'), [4, 252 if cls == 'phys' else 0, 0, 252 if cls == 'spec' else 0, 0, 252]
            yield dict(species=species, form=species, item=item, ability=ab, nature=nat, evs=evs,
                       moves=sorted(m for m, _ in chosen), grade='C', source=src, role=role, evidence={})


def frontier_banned(s):
    return any(x in FRONTIER_BANNED or any(b.startswith(x) or x.startswith(b) for b in FRONTIER_BANNED if len(b) >= 5)
               for x in (s['species'], s['form']))


def allowed(s, tier):
    if tier.startswith('FullDex') and frontier_banned(s):
        return False
    bm, ba, bi = BANS[tier]
    return not (set(s['moves']) & bm or s['ability'] in ba or s['item'] in bi)


def add(pools, tier, s):
    if allowed(s, tier):
        key = (s['form'], s['item'], tuple(s['moves']))
        cur = pools[tier].get(key)
        if cur is None or cur['grade'] > s['grade']:
            pools[tier][key] = s


def singles_tier(s):
    return BUCKET.get(TIER.get(s['form']) or TIER.get(s['species']) or TIER.get(TIER_ALIAS.get(s['form'], '')))


pools = collections.defaultdict(dict)
counts = collections.Counter()

for s in factory_sets():
    t2 = singles_tier(s)
    counts['factory'] += 1
    if t2:
        add(pools, t2, s)
        add(pools, 'AG', s)

singles_files = ['2026-10-gen9nationaldex-1760', '2026-10-gen9nationaldexubers-1760', '2026-10-gen9nationaldexuu-1760', '2026-10-gen9anythinggoes-1760',
                 '2026-10-gen9ubers-1760', '2026-10-gen9ou-1825', '2026-10-gen9uu-1760', '2026-10-gen9ru-1760', '2026-10-gen9nu-1760', '2026-10-gen9pu-1760',
                 '2026-10-gen9zu-1760', '2026-10-gen8ou-1760', '2026-10-gen7ou-1760', '2026-10-gen6ou-1760', '2026-10-gen5ou-1760', '2019-10-gen7ou-1825',
                 '2019-10-gen7ubers-1760', '2019-10-gen7uu-1760', '2019-10-gen7ru-1760', '2019-10-gen7nu-1760', '2019-10-gen7pu-1760', '2022-10-gen8ubers-1760',
                 '2022-10-gen8uu-1760', '2022-10-gen8ru-1760', '2022-10-gen8nu-1760', '2022-10-gen8pu-1760']
for f in singles_files:
    for s in usage_sets(os.path.join(ROOT, 'stats', f + '.json'), False):
        t2 = singles_tier(s)
        counts['usage singles'] += 1
        if t2:
            add(pools, t2, s)
            add(pools, 'AG', s)

doubles_files = ['2026-10-gen9nationaldexdoubles-1760', '2026-10-gen9nationaldexdoublesubers-1760', '2026-10-gen9doublesou-1825', '2026-10-gen9doublesubers-1760',
                 '2026-10-gen9doublesuu-1760', '2019-10-gen7doublesou-1825', '2019-10-gen7doublesuu-1760', '2022-10-gen8doublesou-1825',
                 '2022-10-gen8doublesubers-1760', '2022-10-gen8doublesuu-1760']
for f in doubles_files:
    for s in usage_sets(os.path.join(ROOT, 'stats', f + '.json'), True):
        counts['usage doubles'] += 1
        banned = s['form'] in DOU_BANNED or s['species'] in DOU_BANNED
        add(pools, 'DUber', s)
        add(pools, 'DAG', s) if False else None
        if not banned:
            add(pools, 'DOU', s)

# Full Dex takes every singles or doubles set. Curated Random Battle sets (grade C) only fill
# Pokemon with no better set, and never enter a Smogon tier pool.
for tier in ('Ubers', 'OU', 'UU', 'RU'):
    for s in pools[tier].values():
        add(pools, 'FullDex', s)
for s in pools['DOU'].values():
    add(pools, 'FullDexDoubles', s)
have = lambda tier: set(x['form'] for x in pools[tier].values())
for g in ('gen9-sets', 'gen8-sets', 'gen7-sets', 'gen6-sets', 'gen5-sets', 'gen4-sets'):
    path = os.path.join(SCRATCH, g + '.json')
    if not os.path.exists(path):
        path = os.path.join(ROOT, 'randbats', g + '.json')
    if not os.path.exists(path):
        continue
    for s in random_sets(path, False):
        if s['form'] not in have('FullDex'):
            add(pools, 'FullDex', s)
for s in random_sets(os.path.join(SCRATCH, 'gen9-doubles.json'), True):
    if s['form'] not in have('FullDexDoubles'):
        add(pools, 'FullDexDoubles', s)

os.makedirs(OUT, exist_ok=True)
summary = {}
for tier, p in pools.items():
    sets = sorted(p.values(), key=lambda s: (s['form'], s['grade']))
    json.dump(sets, open(os.path.join(OUT, tier + '.json'), 'w', encoding='utf8'), indent=0)
    g = collections.Counter(s['grade'] for s in sets)
    sp = set(s['form'] for s in sets)
    a = set(s['form'] for s in sets if s['grade'] == 'A')
    ab = set(s['form'] for s in sets if s['grade'] in 'AB')
    summary[tier] = dict(sets=len(sets), A=g['A'], B=g['B'], C=g['C'], species=len(sp), speciesA=len(a), speciesAB=len(ab))
sizes = collections.Counter()
members = collections.defaultdict(set)
for k, v in TIER.items():
    b = BUCKET.get(v)
    if b and (k in SPECIES or species_id(k)):
        sizes[b] += 1
        members[b].add(k)
for tier in ('AG', 'Ubers', 'OU', 'UU', 'RU', 'DOU', 'DUber', 'FullDex', 'FullDexDoubles'):
    print(tier, summary.get(tier), 'tier size', sizes.get(tier))
print(dict(counts))
for tier in ('Ubers', 'OU', 'UU', 'RU'):
    miss = sorted(members[tier] - set(s['form'] for s in pools[tier].values()))
    print(tier, 'missing', len(miss), miss[:90])
json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)

full = [k for k, v in TIER.items() if BUCKET.get(v) and k in SPECIES and not frontier_banned(dict(species=k, form=k))]
inpool = set(x['form'] for x in pools['FullDex'].values())
ab_pool = set(x['form'] for x in pools['FullDex'].values() if x['grade'] in 'AB')
print('Full Dex eligible', len(full), 'with any set', sum(k in inpool for k in full), 'grade A or B', sum(k in ab_pool for k in full))
print('Full Dex no set', sorted(k for k in full if k not in inpool)[:70])
print('banned species found', len(FRONTIER_BANNED))
