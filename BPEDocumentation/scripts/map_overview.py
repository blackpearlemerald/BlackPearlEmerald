"""Render a small terrain overview from this release's positioned map images.

Each map is sampled on the same world pixel grid before composition. No full
resolution world canvas is allocated; the overview is at most 2048 px per side.
"""
import math
from pathlib import Path

from PIL import Image


def build(world, site):
    maps = world["maps"]
    factor = 16
    min_x, min_y = min(m["x"] for m in maps), min(m["y"] for m in maps)
    max_x, max_y = max(m["x"] + m["w"] for m in maps), max(m["y"] + m["h"] for m in maps)
    while True:
        x, y = math.floor(min_x / factor) * factor, math.floor(min_y / factor) * factor
        width, height = math.ceil((max_x - x) / factor), math.ceil((max_y - y) / factor)
        if max(width, height) <= 2048:
            break
        factor *= 2
    overview = Image.new("RGBA", (width, height))
    directory = Path(site) / "img/maps"
    for m in maps:
        left, top = math.floor((m["x"] - x) / factor), math.floor((m["y"] - y) / factor)
        right, bottom = math.ceil((m["x"] + m["w"] - x) / factor), math.ceil((m["y"] + m["h"] - y) / factor)
        with Image.open(directory / m["img"]) as image:
            if image.size != (m["w"], m["h"]):
                raise ValueError(f"Map image dimensions disagree with world data: {m['img']}")
            sampled = image.convert("RGBA").transform((right - left, bottom - top), Image.Transform.AFFINE,
                (factor, 0, left * factor + x - m["x"], 0, factor, top * factor + y - m["y"]),
                resample=Image.Resampling.NEAREST)
            overview.alpha_composite(sampled, (left, top))
    filename = "world-overview.png"
    overview.save(directory / filename)
    world["overview"] = dict(url="img/maps/" + filename, x=x, y=y, w=width * factor, h=height * factor,
                             width=width, height=height, detailZoom=-math.log2(factor))
    return world["overview"]
