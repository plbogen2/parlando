"""Unit tests for HTML player generator."""

import os
import tempfile
import unittest

from audiobook_narrator.player import HTMLPlayerGenerator
from audiobook_narrator.stitcher import ChapterTimepoint, StitchedAudioResult


class HTMLPlayerGeneratorTest(unittest.TestCase):
    """Test suite for HTML player generation."""

    def test_generate_player_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_audio = os.path.join(tmp_dir, "test.mp3")
            with open(dummy_audio, "wb") as f:
                f.write(b"ID3" + b"\x00" * 100)

            out_html = os.path.join(tmp_dir, "test_player.html")
            stitched = StitchedAudioResult(
                master_wav_path=dummy_audio,
                duration_sec=120.0,
                total_samples=2880000,
                sample_rate=24000,
                chapter_timepoints=[
                    ChapterTimepoint(chapter_num=1, title="Chapter 1: The Matrix", start_time_sec=0.0, end_time_sec=60.0, duration_sec=60.0),
                    ChapterTimepoint(chapter_num=2, title="Chapter 2: Zion", start_time_sec=60.0, end_time_sec=120.0, duration_sec=60.0),
                ],
            )

            res = HTMLPlayerGenerator.generate(
                stitched_result=stitched,
                audio_file_path=dummy_audio,
                output_html_path=out_html,
                title="Neuromancer",
                author="William Gibson",
                embed_audio=False,
            )

            self.assertTrue(os.path.exists(out_html))
            with open(out_html, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Neuromancer", content)
            self.assertIn("William Gibson", content)
            self.assertIn("Chapter 1: The Matrix", content)
            self.assertIn("Chapter 2: Zion", content)


if __name__ == "__main__":
    unittest.main()
