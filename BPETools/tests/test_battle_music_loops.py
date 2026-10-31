"""Every battle theme must loop, or the music stops partway through a battle."""

from __future__ import annotations

import pathlib
import unittest

MIDI_DIR = pathlib.Path(__file__).resolve().parents[2] / "sound" / "songs" / "midi"
LOOP_MARKERS = (b"\xff\x01\x01[", b"\xff\x06\x01[", b"\xff\x07\x01[")
LOOP_END_MARKERS = (b"\xff\x01\x01]", b"\xff\x06\x01]", b"\xff\x07\x01]")


class BattleMusicLoopTest(unittest.TestCase):
    def test_battle_themes_loop(self) -> None:
        songs = sorted(MIDI_DIR.glob("mus_*vs_*.mid"))
        self.assertGreater(len(songs), 20)
        for song in songs:
            data = song.read_bytes()
            with self.subTest(song=song.name):
                self.assertTrue(any(marker in data for marker in LOOP_MARKERS), "no loop start")
                self.assertTrue(any(marker in data for marker in LOOP_END_MARKERS), "no loop end")


if __name__ == "__main__":
    unittest.main()
