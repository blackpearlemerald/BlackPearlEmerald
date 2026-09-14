import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "BPEDocumentation/scripts"))
try:
    from PIL import Image
    import map_overview
except ImportError:
    Image = None
from releases import validate_map_overview


@unittest.skipIf(Image is None, "Install BPEDocumentation/requirements.txt to test overview rendering")
class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.images = self.root / "img/maps"
        self.images.mkdir(parents=True)
        Image.new("RGBA", (32, 32), "red").save(self.images / "a.png")
        Image.new("RGBA", (16, 32), "blue").save(self.images / "b.png")
        self.world = {"maps": [dict(img="a.png", x=-16, y=-16, w=32, h=32),
                               dict(img="b.png", x=0, y=-16, w=16, h=32)]}

    def test_negative_coordinates_overlap_and_deterministic_output(self):
        overview = map_overview.build(self.world, self.root)
        first = (self.images / "world-overview.png").read_bytes()
        with Image.open(self.images / "world-overview.png") as image:
            self.assertEqual(image.size, (2, 2))
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
            self.assertEqual(image.getpixel((1, 0)), (0, 0, 255, 255))
        self.assertEqual(overview["x"], -16)
        validate_map_overview(self.root, self.world)
        map_overview.build(self.world, self.root)
        self.assertEqual(first, (self.images / "world-overview.png").read_bytes())

    def test_sparse_world_uses_bounded_canvas(self):
        self.world["maps"][1]["x"] = 100_000
        overview = map_overview.build(self.world, self.root)
        self.assertLessEqual(overview["width"], 2048)
        validate_map_overview(self.root, self.world)

    def test_missing_mismatched_and_unsafe_assets_rejected(self):
        map_overview.build(self.world, self.root)
        for changes in ({"url": "img/maps/missing.png"}, {"url": "../outside.png"},
                        {"width": 99}, {"x": 0}, {"detailZoom": float("nan")}):
            world = copy.deepcopy(self.world)
            world["overview"].update(changes)
            with self.assertRaises(ValueError):
                validate_map_overview(self.root, world)
        self.world["maps"][0]["w"] = 64
        with self.assertRaises(ValueError):
            map_overview.build(self.world, self.root)

    def test_historical_snapshots_without_overview_remain_valid(self):
        validate_map_overview(self.root, self.world)
