"""Unit tests for AudioStitcher and ChapterTimepoint tracking."""

import array
import math
import os
import tempfile
import unittest

from parlando.core.chunker import ChunkType, NarrativeChunk
from parlando.core.dsp import AudioBuffer, DEFAULT_SAMPLE_RATE
from parlando.core.stitcher import AudioStitcher, ChapterTimepoint


class AudioStitcherTest(unittest.TestCase):

    def setUp(self):
        self.stitcher = AudioStitcher(crossfade_ms=20, sample_rate=24000)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, f))
        os.rmdir(self.tmp_dir)

    def test_assemble_chunks_pipeline(self):
        c1_path = os.path.join(self.tmp_dir, "c1.wav")
        c2_path = os.path.join(self.tmp_dir, "c2.wav")

        s1 = array.array("h", [int(5000 * math.sin(2 * math.pi * 440 * i / 24000)) for i in range(2400)])
        s2 = array.array("h", [int(5000 * math.sin(2 * math.pi * 440 * i / 24000)) for i in range(2400)])
        AudioBuffer(samples=s1, sample_rate=24000).to_wav_file(c1_path)
        AudioBuffer(samples=s2, sample_rate=24000).to_wav_file(c2_path)

        chunks = [
            NarrativeChunk(text="Chapter 1", chunk_type=ChunkType.HEADING, chapter_index=0, pause_after_ms=50),
            NarrativeChunk(text="Hello world.", chunk_type=ChunkType.NARRATION, chapter_index=0, pause_after_ms=100),
        ]

        res = self.stitcher.assemble_chunks(chunks, [c1_path, c2_path])
        self.assertFalse(res.master_buffer.is_empty())
        self.assertEqual(len(res.chapter_timepoints), 1)
        self.assertEqual(res.chapter_timepoints[0].title, "Chapter 1")


if __name__ == "__main__":
    unittest.main()
