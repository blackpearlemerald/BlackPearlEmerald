"""The Dusclops move table must stay sorted and match extraTutors."""
import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'BPEDocumentation', 'scripts'))

import teachable_data  # noqa: E402


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf8') as f:
        return f.read()


class RestoredTutorMoves(unittest.TestCase):
    def setUp(self):
        self.table = re.findall(r'\{(MOVE_\w+), (\d)\},', read('src/data/pokemon/restored_tutor_moves.h'))
        self.moves = [m for m, _ in self.table]

    def test_table_matches_extra_tutors(self):
        extra = json.loads(read('src/data/pokemon/special_movesets.json'))['extraTutors']
        self.assertEqual(sorted(extra), sorted(self.moves))

    def test_every_move_has_a_learner(self):
        learnables = json.loads(read('src/data/pokemon/all_learnables.json'))
        known = {move for moves in learnables.values() for move in moves}
        extra = json.loads(read('src/data/pokemon/special_movesets.json'))['extraLearners']
        known |= {move for moves in extra.values() for move in moves}
        self.assertEqual([m for m in self.moves if m not in known], [])

    def test_table_is_sorted_by_move_id(self):
        order = {}
        for name in re.findall(r'^\s*(MOVE_\w+)\s*[=,]', read('include/constants/moves.h'), re.M):
            order.setdefault(name, len(order))
        ids = [order[m] for m in self.moves]
        self.assertEqual(ids, sorted(ids))

    def test_everything_opens_by_the_third_badge(self):
        self.assertLessEqual(max(int(b) for _, b in self.table), 3)

    def test_documentation_keeps_extra_learners(self):
        # make_teachables.py adds these to a species' teachable list, so the website must too.
        teachable = teachable_data.build(ROOT)
        self.assertIn('HIGH_JUMP_KICK', teachable['Blaziken'])


if __name__ == '__main__':
    unittest.main()
