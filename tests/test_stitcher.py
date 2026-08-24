"""Unit tests for audio stitcher."""

import os
import tempfile
import unittest
from audiobook_narrator.chunker import ChunkType, NarrativeChunk
from audiobook_narrator.dsp import AudioBuffer
from audiobook_narrator.engine import MockVoiceEngine
from audiobook_narrator.stitcher import AudioStitcher


class AudioStitcherTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = MockVoiceEngine()
        self.stitcher = AudioStitcher(voice_engine=self.engine)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_assemble_chunks_pipeline(self):
        chunks = [
            NarrativeChunk(index=0, text="Chapter 1: The Sky", chunk_type=ChunkType.HEADING, pause_after_ms=300),
            NarrativeChunk(index=1, text="The sky above the port was grey.", chunk_type=ChunkType.EXPOSITION, pause_after_ms=200),
            NarrativeChunk(index=2, text="I can see the signal.", chunk_type=ChunkType.DIALOGUE, gender_hint="female", pause_after_ms=200),
            NarrativeChunk(index=3, text="Chapter 2: The Deck", chunk_type=ChunkType.HEADING, pause_after_ms=300),
            NarrativeChunk(index=4, text="The Ono-Sendai console flickered.", chunk_type=ChunkType.EXPOSITION, pause_after_ms=200),
        ]
        out_wav = os.path.join(self.temp_dir, "master.wav")
        res = self.stitcher.assemble_chunks(chunks, out_wav, max_workers=2, normalize=True)

        self.assertTrue(os.path.exists(res.master_wav_path))
        self.assertGreater(res.duration_sec, 2.0)
        self.assertEqual(len(res.chapter_timepoints), 2)
        self.assertEqual(res.chapter_timepoints[0].title, "Chapter 1: The Sky")
        self.assertEqual(res.chapter_timepoints[1].title, "Chapter 2: The Deck")

        # Verify WAV validity
        buf = AudioBuffer.from_wav_file(out_wav)
        self.assertEqual(buf.num_frames, res.total_samples)


if __name__ == "__main__":
    unittest.main()
