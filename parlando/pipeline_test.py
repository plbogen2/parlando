"""Unit and integration tests for the unified AudiobookPipeline orchestrator."""

import os
import tempfile
import unittest

from parlando.config import AudioFormat, PacingMode
from parlando.pipeline import AudiobookPipeline, PipelineConfig


class AudiobookPipelineTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.config = PipelineConfig(
            backend="mock",
            pacing_mode=PacingMode.DRAMATIC,
            audio_format=AudioFormat.WAV,
            cache_dir=os.path.join(self.tmp_dir, "cache"),
            generate_player=True,
        )
        self.pipeline = AudiobookPipeline(self.config)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_pipeline_text_run(self):
        raw_text = "# Chapter 1: The Sky\n\nThe sky was grey.\n\n# Chapter 2: The Port\n\nThe matrix waited."
        out_wav = os.path.join(self.tmp_dir, "output.wav")
        res = self.pipeline.run(raw_text, output_path=out_wav)

        self.assertTrue(os.path.exists(res.audio_path))
        self.assertGreater(res.duration_seconds, 0.5)
        self.assertEqual(len(res.chapter_timepoints), 2)
        self.assertEqual(res.chapter_timepoints[0].title, "Chapter 1: The Sky")
        self.assertEqual(res.chapter_timepoints[1].title, "Chapter 2: The Port")
        self.assertTrue(os.path.exists(res.player_path))


if __name__ == "__main__":
    unittest.main()
