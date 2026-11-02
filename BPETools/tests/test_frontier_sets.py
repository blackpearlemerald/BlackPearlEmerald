"""The generated Frontier set tables must match their sources and the game's Hidden Power formula."""
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'BPETools'))

import generate_frontier_sets  # noqa: E402

# The order of the game's Hidden Power types, from isHiddenPowerType in gTypesInfo.
HP_TYPES = ['fighting', 'flying', 'poison', 'ground', 'rock', 'bug', 'ghost', 'steel', 'fire', 'water', 'grass', 'electric', 'psychic', 'ice', 'dragon', 'dark']


class FrontierSets(unittest.TestCase):
    def test_hidden_power_ivs_give_their_type(self):
        for hp_type, low in generate_frontier_sets.HP_LOW_IVS.items():
            ivs = {s: 30 if s in low.split() else 31 for s in ('hp', 'atk', 'def', 'spe', 'spa', 'spd')}
            bits = sum((ivs[s] & 1) << i for i, s in enumerate(('hp', 'atk', 'def', 'spe', 'spa', 'spd')))
            self.assertEqual(HP_TYPES[15 * bits // 63], hp_type)

    def test_header_is_up_to_date(self):
        path = os.path.join(ROOT, 'src/data/pokemon/teachable_learnsets.h')
        if not os.path.exists(path):
            self.skipTest('teachable_learnsets.h is written by the build')
        subprocess.run([sys.executable, os.path.join(ROOT, 'BPETools/generate_frontier_sets.py'), '--check'], check=True, capture_output=True)

    def test_rule_tables_cover_every_generation(self):
        with open(os.path.join(ROOT, 'BPETools/frontier_sets/rules.json'), encoding='utf8') as f:
            rules = json.load(f)
        self.assertEqual(rules['gens'], generate_frontier_sets.GENS)
        self.assertTrue(all(len(masks) == 10 for masks in rules['species'].values()))

    def test_showdown_notice_ships_with_the_sets(self):
        with open(os.path.join(ROOT, 'BPETools/frontier_sets/LICENSE-pokemon-showdown.txt'), encoding='utf8') as f:
            self.assertTrue(re.search('Permission is hereby granted', f.read()))


if __name__ == '__main__':
    unittest.main()
