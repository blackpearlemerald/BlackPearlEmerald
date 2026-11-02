"""The Battle Facilities page must show exactly the sets the game compiles."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "BPEDocumentation/scripts"))
sys.path.insert(0, str(ROOT / "BPETools"))

import build_facilities  # noqa: E402
import common as C  # noqa: E402
import generate_frontier_sets as generator  # noqa: E402
import releases  # noqa: E402
try:
    import parse_pokemon  # noqa: E402
except ImportError:  # Pillow is required by the sprite helpers.
    parse_pokemon = None

HEADER = ROOT / "src/data/battle_frontier/frontier_sets.h"
TEACHABLE = ROOT / "src/data/pokemon/teachable_learnsets.h"


def team(first):
    return "{%s}," % ", ".join(str(first + i) for i in range(6))


def synthetic_header():
    """One Hidden Power set, one plain set, and enough ids for every Brain table."""
    rows = "\n".join("    SET(GARCHOMP, LEFTOVERS, ROUGH_SKIN, JOLLY, 0, EARTHQUAKE, HIDDEN_POWER, NONE, NONE, IVS_FIRE),"
                     if i == 0 else "    SET(SPECIES_%d, NONE, NONE, TIMID, 1, TACKLE, NONE, NONE, NONE, 0)," % i for i in range(24))
    pool = ", ".join(str(i) for i in range(24))
    tier_teams = "\n".join(team(0) for _ in range(len(generator.BRAIN_TIER_FACILITIES) * len(generator.TIERS) * 2))
    return f"""
static const u8 sFrontierSetEvs[][NUM_STATS] =
{{
    {{0, 252, 0, 0, 4, 252}},
    {{252, 0, 0, 0, 0, 0}},
}};

const struct TrainerMon gFrontierSetMons[] =
{{
{rows}
}};

static const u16 sPool_nd_AG[] =
{{
    {pool}
}};

static const u16 sPool_1_AG[] =
{{
    {pool}
}};

static const u16 sPool_FullDex[] =
{{
    0, 1
}};

static const u16 sPool_FullDexDoubles[] =
{{
    1
}};

const struct FrontierSetPool gFrontierSetPools[FRONTIER_GEN_COUNT][FRONTIER_POOL_COUNT] =
{{
    {{sPool_nd_AG, 24}},
    {{sPool_1_AG, 24}},
}};

const struct FrontierSetPool gFrontierFullDexPools[2] =
{{
    {{sPool_FullDex, 2}},
    {{sPool_FullDexDoubles, 1}},
}};

const u16 gFrontierBrainFullDexTeams[NUM_FRONTIER_FACILITIES][2][PARTY_SIZE] =
{{
    [FRONTIER_FACILITY_TOWER] = {{
        {team(0)}
        {team(6)}
    }},
}};

const u16 gFrontierBrainTierTeams[2][FRONTIER_TIER_COUNT][2][PARTY_SIZE] =
{{
{tier_teams}
}};
"""


def write_site(site):
    data = site / "data"
    data.mkdir(parents=True)
    species = {"GARCHOMP": {"name": "Garchomp", "icon": "sprites/icons/garchomp.png"}}
    species.update({"SPECIES_%d" % i: {"name": "Mon %d" % i} for i in range(1, 24)})
    (data / "pokedex_index.json").write_text(json.dumps(species), encoding="utf-8")
    (data / "items_index.json").write_text(json.dumps({"LEFTOVERS": {"name": "Leftovers"}}), encoding="utf-8")
    (data / "moves.json").write_text(json.dumps({"EARTHQUAKE": {"name": "Earthquake"}}), encoding="utf-8")
    (data / "abilities.json").write_text(json.dumps({"ROUGH_SKIN": {"name": "Rough Skin"}}), encoding="utf-8")


class HeaderParsing(unittest.TestCase):
    def setUp(self):
        self.header = build_facilities.parse_header(synthetic_header())

    def test_sets_keep_hidden_power_and_drop_empty_slots(self):
        first = self.header["sets"][0]
        self.assertEqual(first["hp"], "FIRE")
        self.assertEqual(first["moves"], ["EARTHQUAKE", "HIDDEN_POWER"])
        self.assertEqual(self.header["spreads"][0], [0, 252, 0, 0, 4, 252])

    def test_a_pool_size_mismatch_stops_the_export(self):
        with self.assertRaises(ValueError):
            build_facilities.parse_header(synthetic_header().replace("{sPool_FullDex, 2}", "{sPool_FullDex, 3}"))

    def test_gens_use_the_strongest_sets_with_gold_first(self):
        pool = self.header["pools"]["1_AG"]
        self.assertEqual(build_facilities.strongest_team(pool, self.header["sets"], 1), [0, 1, 2, 3, 4, 5])
        self.assertEqual(build_facilities.strongest_team(pool, self.header["sets"], 0), [6, 7, 8, 9, 10, 11])

    def test_tables_resolve_names_and_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            write_site(site)
            tables = build_facilities.build_tables(self.header, generator, str(site))
        row = tables["sets"][0]
        self.assertEqual(tables["species"][row[0]], ["GARCHOMP", "Garchomp", "sprites/icons/garchomp.png"])
        self.assertEqual([tables["moves"][m] for m in row[5:]], ["Earthquake", "Hidden Power Fire"])
        self.assertEqual(tables["pools"]["fullDex"], {"singles": [0, 1], "doubles": [1]})
        self.assertEqual(tables["pools"]["smogon"]["1"], {"singles": {"AG": list(range(24))}})
        self.assertEqual(tables["brains"]["fullDex"]["tower"], [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]])
        self.assertEqual(tables["sets"][1][1:3], [-1, -1])


class AvailabilityAndValidation(unittest.TestCase):
    def test_a_source_without_sets_omits_the_data(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / "data").mkdir()
            stale = site / "data/frontier_sets.json"
            stale.write_text("{}", encoding="utf-8")
            result = build_facilities.build(site=str(site), sets_folder=str(site / "missing"), header_path=str(site / "missing.h"))
            self.assertIsNone(result)
            self.assertFalse(stale.exists())
            self.assertFalse(json.loads((site / "data/facilities.json").read_text(encoding="utf-8"))["available"])
            releases.validate_facilities(site)

    def export(self, site):
        """Export the synthetic header to a site, with no handwritten text."""
        header = site / "frontier_sets.h"
        header.write_text(synthetic_header(), encoding="utf-8")
        with patch.object(build_facilities, "load_generator", return_value=generator):
            build_facilities.build(content_path=str(site / "none.json"), site=str(site), header_path=str(header), sets_folder=str(site))

    def test_the_export_passes_validation_and_a_bad_id_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            write_site(site)
            self.export(site)
            releases.validate_facilities(site)
            path = site / "data/frontier_sets.json"
            tables = json.loads(path.read_text(encoding="utf-8"))
            tables["pools"]["fullDex"]["singles"].append(len(tables["sets"]))
            path.write_text(json.dumps(tables), encoding="utf-8")
            with self.assertRaises(ValueError):
                releases.validate_facilities(site)

    def test_validation_rejects_sets_marked_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / "data").mkdir()
            (site / "data/facilities.json").write_text('{"schemaVersion":1,"available":false}', encoding="utf-8")
            (site / "data/frontier_sets.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                releases.validate_facilities(site)


class GameHeader(unittest.TestCase):
    def setUp(self):
        if not HEADER.exists():
            self.skipTest("this source has no Frontier sets")
        self.header = build_facilities.parse_header(HEADER.read_text(encoding="utf-8"))

    def test_every_compiled_set_is_read(self):
        text = HEADER.read_text(encoding="utf-8")
        self.assertEqual(len(self.header["sets"]), len(re.findall(r"^    SET\(", text, re.M)))
        ids = [i for pool in self.header["pools"].values() for i in pool]
        self.assertEqual(max(ids), len(self.header["sets"]) - 1)

    def test_every_rule_set_and_brain_is_present(self):
        pools = build_facilities.build_pools(self.header, generator)
        self.assertEqual(list(pools["smogon"]), generator.GENS)
        self.assertEqual(sorted(g for g in generator.GENS if "doubles" not in pools["smogon"][g]), ["1", "2"])
        self.assertEqual(set(pools["smogon"]["nd"]["doubles"]), {"AG", "Ubers", "OU"})
        brains = build_facilities.build_brains(self.header, generator)
        self.assertEqual(set(brains["fullDex"]), set(generator.BRAIN_FACILITIES))
        self.assertEqual(set(brains["nationalDex"]), set(generator.BRAIN_TIER_FACILITIES))
        self.assertEqual(set(brains["gens"]), set(generator.GENS) - {"nd"})

    def test_pools_match_what_the_generator_computes(self):
        if not TEACHABLE.exists():
            self.skipTest("teachable_learnsets.h is written by the build")
        species = generator.constants("include/constants/species.h", "SPECIES")
        moves = generator.constants("include/constants/moves.h", "MOVE")
        items = generator.constants("include/constants/items.h", "ITEM")
        abilities = generator.constants("include/constants/abilities.h", "ABILITY")
        natures = {generator.norm(n): n for n in re.findall(r"\bNATURE_(\w+)", generator.read("include/constants/pokemon.h"))}
        with open(os.path.join(generator.DATA, "rules.json"), encoding="utf8") as f:
            rules = json.load(f)
        learn = generator.Learnsets()
        rows, pools, _, _ = generator.load_sets(learn, species, moves, items, abilities, natures, rules)
        table, _ = generator.build_pools(rows, pools, rules)
        full_dex = generator.build_full_dex(rows, pools, learn)
        brains = generator.build_brains(rows, table, full_dex)
        used = sorted({x for pool in table.values() for x in pool} | set(full_dex[0]) | set(full_dex[1]))
        new_id = {old: new for new, old in enumerate(used)}

        self.assertEqual(len(self.header["sets"]), len(used))
        for (gen, pool), ids in table.items():
            self.assertEqual(self.header["pools"].get(f"{gen}_{pool}", []), [new_id[x] for x in ids], (gen, pool))
        self.assertEqual(self.header["pools"]["FullDex"], [new_id[x] for x in full_dex[0]])
        self.assertEqual(self.header["pools"]["FullDexDoubles"], [new_id[x] for x in full_dex[1]])
        exported = build_facilities.build_brains(self.header, generator)
        for facility, teams in brains["full_dex"].items():
            self.assertEqual(exported["fullDex"][facility], [[new_id[x] for x in t] for t in teams])
        for (tier, facility), teams in brains["tiers"].items():
            self.assertEqual(exported["nationalDex"][facility][tier], [[new_id[x] for x in t] for t in teams])


@unittest.skipIf(parse_pokemon is None, "Install BPEDocumentation/requirements.txt to test exporters")
class DusclopsMoves(unittest.TestCase):
    def entries(self):
        return {"A": {"tmMoves": [], "hmMoves": [], "tutorMoves": ["ROOST", "SWAGGER", "PURSUIT"]},
                "B": {"tmMoves": [], "hmMoves": [], "tutorMoves": ["SWAGGER"]}}

    def test_moves_list_their_badges_in_order(self):
        table = "static const struct RestoredTutorMove sRestoredTutorMoves[] =\n{\n    {MOVE_PURSUIT, 2},\n    {MOVE_ROOST, 0},\n};\n"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "src/data/pokemon"
            path.mkdir(parents=True)
            (path / "restored_tutor_moves.h").write_text(table, encoding="utf-8")
            with patch.object(parse_pokemon, "REPO", Path(folder)):
                entries = self.entries()
                self.assertEqual(parse_pokemon.apply_dusclops_moves(entries), 1)
        self.assertEqual(entries["A"]["dusclopsMoves"], [{"move": "ROOST", "badges": 0}, {"move": "PURSUIT", "badges": 2}])
        self.assertNotIn("dusclopsMoves", entries["B"])
        self.assertIn("ROOST", entries["A"]["tutorMoves"])

    def test_older_sources_without_the_table_still_export(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(parse_pokemon, "REPO", Path(folder)):
                entries = self.entries()
                self.assertEqual(parse_pokemon.apply_dusclops_moves(entries), 0)
        self.assertEqual(entries, self.entries())


if __name__ == "__main__":
    unittest.main()
