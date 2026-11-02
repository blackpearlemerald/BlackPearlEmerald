#!/usr/bin/env python3
"""Generate src/data/battle_frontier/frontier_sets.h from BPETools/frontier_sets/.

sets.json and rules.json come from the pipeline in BPETools/frontier_sets/pipeline. This
step needs only those two files and the game source, so it can run on any machine.

Rerun it after changing learnsets, evolutions or species abilities:
    python BPETools/generate_frontier_sets.py
    python BPETools/generate_frontier_sets.py --check    # fails if the header is stale
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'BPETools', 'frontier_sets')
OUT = os.path.join(REPO, 'src', 'data', 'battle_frontier', 'frontier_sets.h')

GENS = ['nd', '1', '2', '3', '4', '5', '6', '7', '8', '9']  # FRONTIER_GEN index order
TIERS = ['AG', 'Ubers', 'OU', 'UU', 'RU']  # enum FrontierTier order
DOUBLES = ['DAG', 'DUber', 'DOU']  # Doubles use the first three FrontierTier values
POOLS = TIERS + DOUBLES
# A pool needs enough species for a whole Factory or Dome field, so small tiers borrow from below.
MIN_POOL_SPECIES = 30

# IVs of 30 that make each Hidden Power type under the game's formula, the same as Showdown's.
HP_LOW_IVS = {
    'bug': 'atk def spd', 'dark': '', 'dragon': 'atk', 'electric': 'spa', 'fighting': 'def spa spd spe',
    'fire': 'atk spa spe', 'flying': 'hp atk def spa spd', 'ghost': 'def spd', 'grass': 'atk spa',
    'ground': 'spa spd', 'ice': 'atk def', 'poison': 'def spa spd', 'psychic': 'atk spe',
    'rock': 'def spd spe', 'steel': 'spd', 'water': 'atk def spa',
}

# Base names such as SPECIES_LANDORUS stand for one of these forms.
DEFAULT_FORMS = ('', 'normal', 'hero', 'incarnate', 'altered', 'singlestrike', 'midday', 'disguised', 'tealmask', 'west', 'teal', 'male',
                 'aria', 'ordinary', 'red', 'plant', 'overcast', 'standard', 'fifty', 'fiftypercent', 'solo', 'shield', 'land', 'white',
                 'natural', 'baile', 'core', 'fullbelly', 'zero', 'gulping', 'ice', 'familyofthree', 'twosegment', 'average', 'confined',
                 'amped', 'phantom', 'unremarkable')

norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())


def read(path):
    with open(os.path.join(REPO, path), encoding='utf8') as f:
        return f.read()


def constants(path, prefix):
    """Maps a Showdown-style id to the constant's name, without its prefix."""
    names = {}
    for name, alias_of in re.findall(r'\b%s_(\w+)\s*=\s*(?:%s_(\w+))?' % (prefix, prefix), read(path)):
        names.setdefault(norm(name), alias_of or name)
    return names


class Learnsets:
    """What the game lets a player teach, read from the same data the game uses."""

    def __init__(self):
        self.lists = collections.defaultdict(set)
        files = [os.path.join(REPO, 'src/data/pokemon', f) for f in ('level_up_learnsets/gen_9.h', 'teachable_learnsets.h', 'egg_moves.h')]
        for path in files:
            with open(path, encoding='utf8') as f:
                text = f.read()
            for m in re.finditer(r'\b(s\w+?(?:LevelUp|Teachable|EggMove)Learnset)\[\]\s*=\s*\{(.*?)\};', text, re.S):
                self.lists[m.group(1)] |= set(norm(x) for x in re.findall(r'MOVE_(\w+)', m.group(2)))
        self.species = {}
        self.abilities = {}
        self.pre = {}
        self.banned = set()
        for path in glob.glob(os.path.join(REPO, 'src/data/pokemon/species_info/*families.h')):
            with open(path, encoding='utf8') as f:
                text = f.read().replace('\\\n', ' ')
            macros = dict(re.findall(r'#define (\w+)(?:\([^)]*\))?[ \t]+(.*)', text))
            for block in re.split(r'\n\s*\[SPECIES_', text)[1:]:
                name = norm(block.split(']')[0])
                body = block
                for _ in range(3):  # Forms often go through macros that call macros
                    body += ' '.join(macros[m] for m in set(re.findall(r'\b([A-Z][A-Z0-9_]{3,})\b', body)) if m in macros)
                self.species[name] = set(re.findall(r'\.(?:levelUpLearnset|teachableLearnset|eggMoveLearnset)\s*=\s*(s\w+)', body))
                # The first block is the current one when a config picks between several.
                first = re.search(r'\.abilities\s*=\s*\{(.*?)\}', block)
                self.abilities[name] = set(norm(x) for x in re.findall(r'ABILITY_(\w+)', first.group(1))) if first else set()
                if '.isFrontierBanned = TRUE' in body:
                    self.banned.add(name)
                for target in re.findall(r'SPECIES_(\w+)', ' '.join(re.findall(r'EVOLUTION\((.*?)\)\s*,?\n', block, re.S))):
                    self.pre.setdefault(norm(target), name)

    def moves(self, name):
        out, seen, queue = set(), set(), [name]
        while queue:
            x = queue.pop()
            if x in seen:
                continue
            seen.add(x)
            for table in self.species.get(x, ()):
                out |= self.lists[table]
            if x in self.pre:
                queue.append(self.pre[x])
        if name.startswith('rotom'):  # Form changes add these
            out |= {'overheat', 'hydropump', 'blizzard', 'airslash', 'leafstorm'}
        return out


def load_sets(learn, species, moves, items, abilities, natures, rules):
    """Turns JSON rows into C rows. A set no longer possible in the game becomes None."""
    with open(os.path.join(DATA, 'sets.json'), encoding='utf8') as f:
        raw = json.load(f)
    aliases = collections.defaultdict(list)
    for a, b in re.findall(r'\bSPECIES_(\w+)\s*=\s*SPECIES_(\w+)', read('include/constants/species.h')):
        aliases[norm(a)] += [norm(a), norm(b)]
        aliases[norm(b)] += [norm(b), norm(a)]
    spreads = {}
    rows = []
    dropped = collections.Counter()
    for name, form, item, ability, nature, evs, set_moves, grade, source in raw['sets']:
        key = next((name + d for d in DEFAULT_FORMS if name + d in species), None)
        if key is None:
            sys.exit('Unknown species in sets.json: ' + name)
        # SPECIES_GASTRODON is another name for SPECIES_GASTRODON_WEST, which holds the data.
        species_key = next((a for a in aliases.get(key, [key]) if a in learn.species), key)
        known = learn.moves(species_key)
        c_moves, hp_type = [], None
        problem = None
        if ability and learn.abilities.get(species_key) and ability not in learn.abilities[species_key]:
            problem = '%s %s' % (name, ability)
        for m in set_moves:
            base = m
            if m.startswith('hiddenpower'):
                base = 'hiddenpower'
                hp_type = m[len(base):] or 'dark'
            if base not in moves:
                sys.exit('Unknown move in sets.json: ' + m)
            if base not in known:
                problem = '%s %s' % (name, base)
            c_moves.append(moves[base])
        if problem:
            dropped[problem] += 1
            rows.append(None)
            continue
        rows.append({
            'name': name, 'key': key, 'species': species[key], 'species_key': species_key, 'rule_species': next(species[a] for a in aliases.get(key, [key]) if species[a] in rules['species']), 'item': items[item] if item else 'NONE', 'ability': abilities[ability] if ability else 'NONE',
            'nature': natures[nature], 'ev': spreads.setdefault(tuple(evs), len(spreads)), 'moves': c_moves, 'hp': hp_type,
        })
    return rows, raw['pools'], sorted(spreads, key=spreads.get), dropped


def ordered_pool(rows, entries, seen=None):
    """Sets strongest first, without repeats or sets the game can't make."""
    seen = set() if seen is None else seen
    out = []
    for idx, _, _ in entries:
        if rows[idx] is not None and idx not in seen:
            seen.add(idx)
            out.append(idx)
    return out


def obeys_rules(row, gen, pool, rules):
    """Whether the game's team checker would accept this set in this pool."""
    g = GENS.index(gen)
    bit = {'AG': 1, 'Ubers': 2, 'OU': 4, 'UU': 8, 'RU': 16, 'DAG': 1, 'DUber': 32, 'DOU': 64}[pool]
    if not rules['species'][row['rule_species']][g] & bit:
        return False
    bans = rules['bans'][gen].get(pool, {'moves': [], 'items': [], 'abilities': []})
    if row['item'] != 'NONE' and (row['item'] in bans['items'] or not rules['items'][row['item']] >> g & 1):
        return False
    if row['ability'] in bans['abilities']:
        return False
    return all(m not in bans['moves'] and rules['moves'][m] >> g & 1 for m in row['moves'])


def build_pools(rows, pools, rules):
    table = {}
    for gen in GENS:
        tiers = [pools.get('%s-%s' % (gen, t), []) for t in TIERS]
        for i, tier in enumerate(TIERS):
            seen = set()
            pool = ordered_pool(rows, tiers[i], seen)
            for lower in tiers[i + 1:]:
                if tier != 'AG' and len({rows[x]['name'] for x in pool}) >= MIN_POOL_SPECIES:
                    break
                pool += ordered_pool(rows, lower, seen)
            table[gen, tier] = pool
        dou = ordered_pool(rows, pools.get(gen + '-DOU', []))
        seen = set()
        duber = ordered_pool(rows, pools.get(gen + '-DUber', []), seen)
        table[gen, 'DOU'] = dou
        table[gen, 'DUber'] = duber
        table[gen, 'DAG'] = duber + [x for x in dou if x not in seen]
    dropped = 0
    for (gen, pool), ids in table.items():
        table[gen, pool] = [x for x in ids if obeys_rules(rows[x], gen, pool, rules)]
        dropped += len(ids) - len(table[gen, pool])
        if pool in TIERS and len({rows[x]['name'] for x in table[gen, pool]}) < MIN_POOL_SPECIES:
            sys.exit('%s %s has too few species' % (gen, pool))
    return table, dropped


def build_full_dex(rows, pools, learn):
    def allowed(idx):
        return not ({rows[idx]['key'], rows[idx]['name'], rows[idx]['species_key']} & learn.banned)

    singles = []
    seen = set()
    for tier in TIERS[1:]:
        singles += [x for x in ordered_pool(rows, pools['nd-' + tier], seen) if allowed(x)]
    seen = set()
    doubles = []
    for tier in ('DUber', 'DOU'):
        doubles += [x for x in ordered_pool(rows, pools['nd-' + tier], seen) if allowed(x)]
    return singles, doubles


def c_array(values, per_line=16):
    return ',\n'.join('    ' + ', '.join(str(v) for v in values[i:i + per_line]) for i in range(0, len(values), per_line))


def render(rows, table, full_dex, spreads, rules, constant_names):
    used = sorted({x for pool in table.values() for x in pool} | set(full_dex[0]) | set(full_dex[1]))
    new_id = {old: new for new, old in enumerate(used)}
    out = ['// Generated by BPETools/generate_frontier_sets.py. Do not edit.',
           '// Sets come from Pokemon Showdown, see BPETools/frontier_sets/README.md.', '']
    for t, low in sorted(HP_LOW_IVS.items()):
        v = [30 if stat in low.split() else 31 for stat in ('hp', 'atk', 'def', 'spe', 'spa', 'spd')]
        out.append('#define IVS_%s TRAINER_PARTY_IVS(%s)' % (t.upper(), ', '.join(map(str, v))))
    out += ['', 'static const u8 sFrontierSetEvs[][NUM_STATS] =', '{']
    out += ['    {%s},' % ', '.join(map(str, s)) for s in spreads]
    out += ['};', '',
            '#define SET(species_, item, ability_, nature_, evs, move1, move2, move3, move4, ivs) \\',
            '    {.species = SPECIES_##species_, .heldItem = ITEM_##item, .ability = ABILITY_##ability_, .nature = NATURE_##nature_, \\',
            '     .ev = sFrontierSetEvs[evs], .iv = ivs, .ball = BALL_POKE, \\',
            '     .moves = {MOVE_##move1, MOVE_##move2, MOVE_##move3, MOVE_##move4}}', '',
            'const struct TrainerMon gFrontierSetMons[] =', '{']
    for idx in used:
        r = rows[idx]
        moves = (r['moves'] + ['NONE'] * 4)[:4]
        ivs = 'IVS_' + r['hp'].upper() if r['hp'] else '0'
        out.append('    SET(%s, %s, %s, %s, %d, %s, %s),' % (r['species'], r['item'], r['ability'], r['nature'], r['ev'], ', '.join(moves), ivs))
    out += ['};', '', 'const u32 gFrontierSetMonsCount = ARRAY_COUNT(gFrontierSetMons);', '', '#undef SET', '']

    for (gen, pool), ids in table.items():
        if ids:
            out += ['static const u16 sPool_%s_%s[] =' % (gen, pool), '{', c_array([new_id[x] for x in ids]), '};', '']
    out += ['static const u16 sPool_FullDex[] =', '{', c_array([new_id[x] for x in full_dex[0]]), '};', '',
            'static const u16 sPool_FullDexDoubles[] =', '{', c_array([new_id[x] for x in full_dex[1]]), '};', '',
            'const struct FrontierSetPool gFrontierSetPools[FRONTIER_GEN_COUNT][FRONTIER_POOL_COUNT] =', '{']
    for gen in GENS:
        out.append('    {')
        for pool in POOLS:
            if table[gen, pool]:
                out.append('        {sPool_%s_%s, %d},' % (gen, pool, len(table[gen, pool])))
            else:
                out.append('        {NULL, 0},')
        out.append('    },')
    out += ['};', '',
            'const struct FrontierSetPool gFrontierFullDexPools[2] =', '{',
            '    {sPool_FullDex, %d},' % len(full_dex[0]), '    {sPool_FullDexDoubles, %d},' % len(full_dex[1]), '};', '']

    # Species and what each generation allows them to do
    out += ['// One byte per generation: FRONTIER_SPECIES_* bits, see frontier_sets.h.',
            'const u8 gFrontierSpeciesRules[NUM_SPECIES][FRONTIER_GEN_COUNT] =', '{']
    for name, masks in rules['species'].items():
        if any(masks):
            out.append('    [SPECIES_%s] = {%s},' % (name, ', '.join(map(str, masks))))
    out += ['};', '', '// Bit n is set if generation n has the move.',
            'const u16 gFrontierMoveGens[MOVES_COUNT] =', '{']
    for name, mask in rules['moves'].items():
        if constant_names['moves'].get(name):
            out.append('    [MOVE_%s] = %d,' % (name, mask))
    out += ['};', '', '// Bit n is set if generation n has the item.',
            'const u16 gFrontierItemGens[ITEMS_COUNT] =', '{']
    for name, mask in rules['items'].items():
        if name in constant_names['items']:
            out.append('    [ITEM_%s] = %d,' % (name, mask))
    out += ['};', '']

    lists = {}

    def ban_list(prefix, names):
        if not names:
            return 'NULL'
        key = (prefix, tuple(names))
        if key not in lists:
            lists[key] = 'sBan%d' % len(lists)
            out.extend(['static const u16 %s[] = {%s};' % (lists[key], ', '.join('%s_%s' % (prefix, n) for n in names))])
        return lists[key]

    bans = {}
    for gen in GENS:
        for pool in POOLS:
            b = rules['bans'][gen].get(pool)
            if b:
                moves = [n for n in b['moves'] if constant_names['moves'].get(n)]
                bans[gen, pool] = '{%s, %s, %s, %d, %d, %d}' % (
                    ban_list('MOVE', moves), ban_list('ITEM', b['items']), ban_list('ABILITY', b['abilities']),
                    len(moves), len(b['items']), len(b['abilities']))
    out += ['', 'const struct FrontierBans gFrontierBans[FRONTIER_GEN_COUNT][FRONTIER_POOL_COUNT] =', '{']
    for gen in GENS:
        out.append('    {')
        out += ['        %s,' % bans.get((gen, pool), '{0}') for pool in POOLS]
        out.append('    },')
    out += ['};', '']
    return '\n'.join(out), len(used)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--check', action='store_true', help='fail if the header is out of date')
    args = parser.parse_args()

    species = constants('include/constants/species.h', 'SPECIES')
    moves = constants('include/constants/moves.h', 'MOVE')
    items = constants('include/constants/items.h', 'ITEM')
    abilities = constants('include/constants/abilities.h', 'ABILITY')
    natures = {norm(n): n for n in re.findall(r'\bNATURE_(\w+)', read('include/constants/pokemon.h'))}
    real_items = set(re.findall(r'\bITEM_(\w+)\s*=', re.split(r'\n\s*ITEMS_COUNT,', read('include/constants/items.h'))[0]))
    enum_end = read('include/constants/moves.h').index('MOVES_COUNT_GEN9')
    real_moves = {n: True for n in re.findall(r'\bMOVE_(\w+)\s*=', read('include/constants/moves.h')[:enum_end])}

    learn = Learnsets()
    with open(os.path.join(DATA, 'rules.json'), encoding='utf8') as f:
        rules = json.load(f)
    rows, pools, spreads, dropped = load_sets(learn, species, moves, items, abilities, natures, rules)
    table, rule_drops = build_pools(rows, pools, rules)
    full_dex = build_full_dex(rows, pools, learn)
    text, count = render(rows, table, full_dex, spreads, rules, {'moves': real_moves, 'items': real_items})
    text = text.replace('\r\n', '\n')

    if args.check:
        with open(OUT, encoding='utf8', newline='') as f:
            if f.read() != text:
                sys.exit('frontier_sets.h is stale. Run python BPETools/generate_frontier_sets.py')
        print('frontier_sets.h is up to date')
        return
    with open(OUT, 'w', encoding='utf8', newline='') as f:
        f.write(text)
    entries = sum(len(p) for p in table.values())
    print('%d sets, %d pool entries, %d EV spreads; %d sets dropped, %d pool entries broke their rules' % (count, entries, len(spreads), sum(dropped.values()), rule_drops))
    print('Dropped (set count): ' + ', '.join('%s %d' % x for x in dropped.most_common()))
    print('Full Dex pools: %d singles, %d doubles' % (len(full_dex[0]), len(full_dex[1])))
    for gen in GENS:
        print(gen, ' '.join('%s %d/%d' % (p, len(table[gen, p]), len({rows[x]['name'] for x in table[gen, p]})) for p in POOLS))


if __name__ == '__main__':
    main()
