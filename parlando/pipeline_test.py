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

    def test_pipeline_with_custom_cast(self):
        raw_text = (
            "# Chapter 1: The Night\n\n"
            '"I am ready," Case said.\n\n'
            'Linda Lee touched his arm. "Wait for me."'
        )
        custom_cast = {
            "Case": {"gender": "male", "voice": "Charon"},
            "Linda Lee": {"gender": "female", "voice": "Leda"},
        }
        cfg = PipelineConfig(
            backend="mock",
            characters=custom_cast,
            cache_dir=os.path.join(self.tmp_dir, "cast_cache"),
            generate_player=False,
        )
        pipeline = AudiobookPipeline(cfg)
        out_wav = os.path.join(self.tmp_dir, "cast_output.wav")
        res = pipeline.run(raw_text, output_path=out_wav)

        self.assertTrue(os.path.exists(res.audio_path))
        self.assertEqual(res.voice_map["Case"], "Charon")
        self.assertEqual(res.voice_map["Linda Lee"], "Leda")
        self.assertEqual(res.characters["Case"].gender, "male")
        self.assertEqual(res.characters["Linda Lee"].gender, "female")


if __name__ == "__main__":
    unittest.main()
