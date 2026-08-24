"""Unit tests for standalone HTML5 Player Generator."""

import os
import tempfile
import unittest

from parlando.core.stitcher import ChapterTimepoint
from parlando.export.player import HTMLPlayerGenerator


class HTMLPlayerGeneratorTest(unittest.TestCase):

    def test_generate_player_html(self):
        tps = [
            ChapterTimepoint(title="Prologue", start_ms=0, end_ms=5000, chapter_index=0),
            ChapterTimepoint(title="Chapter 1", start_ms=5000, end_ms=12000, chapter_index=1),
        ]
        html = HTMLPlayerGenerator.generate_player_html(
            title="Cyber Deck",
            author="William Gibson",
            audio_filename="cyber_deck.m4b",
            chapter_timepoints=tps,
        )
        self.assertIn("Cyber Deck", html)
        self.assertIn("William Gibson", html)
        self.assertIn("cyber_deck.m4b", html)
        self.assertIn("Prologue", html)
        self.assertIn("visualizer", html)

    def test_write_player_file(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            path = tf.name

        try:
            res = HTMLPlayerGenerator.write_player_file(
                path, "Title", "Author", "audio.mp3", []
            )
            self.assertTrue(os.path.exists(res))
            self.assertGreater(os.path.getsize(res), 100)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
