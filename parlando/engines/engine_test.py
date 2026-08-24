"""Unit tests for Mock and Pluggable Voice engines."""

import os
import tempfile
import unittest

from parlando.core.chunker import ChunkType, NarrativeChunk
from parlando.engines import MockVoiceEngine, get_voice_engine


class VoiceEngineTest(unittest.TestCase):

    def setUp(self):
        self.engine = MockVoiceEngine(sample_rate=24000)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, f))
        os.rmdir(self.tmp_dir)

    def test_mock_synthesize_chunk(self):
        out_wav = os.path.join(self.tmp_dir, "test.wav")
        chunk = NarrativeChunk(text="The sky was the color of television.", chunk_type=ChunkType.NARRATION)
        res = self.engine.synthesize_chunk(chunk, out_wav)
        self.assertEqual(res, out_wav)
        self.assertTrue(os.path.exists(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 44)

    def test_synthesize_batch(self):
        chunks = [
            NarrativeChunk(text="First sentence.", chunk_type=ChunkType.NARRATION),
            NarrativeChunk(text="", chunk_type=ChunkType.SECTION_BREAK, pause_after_ms=200),
            NarrativeChunk(text="Second sentence.", chunk_type=ChunkType.NARRATION),
        ]
        results = self.engine.synthesize_batch(chunks, self.tmp_dir, max_workers=2)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(os.path.exists(r))

    def test_get_voice_engine_factory(self):
        mock_e = get_voice_engine("mock")
        self.assertIsInstance(mock_e, MockVoiceEngine)
        with self.assertRaises(ValueError):
            get_voice_engine("invalid_backend_name")


if __name__ == "__main__":
    unittest.main()
