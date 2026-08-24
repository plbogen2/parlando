"""Unit tests for all multi-backend voice synthesis engines."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from audiobook_narrator.chunker import ChunkType, NarrativeChunk
from audiobook_narrator.engine import (
    EdgeTTSVoiceEngine,
    GeminiVoiceEngine,
    MockVoiceEngine,
    OpenAIVoiceEngine,
    VoiceEngineError,
    get_voice_engine,
)


class VoiceEngineTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = MockVoiceEngine()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_synthesize_chunk(self):
        chunk = NarrativeChunk(index=0, text="Testing neural signal synthesis.", chunk_type=ChunkType.EXPOSITION)
        out_wav = os.path.join(self.temp_dir, "chunk_0.wav")
        res_path = self.engine.synthesize_chunk(chunk, out_wav)

        self.assertEqual(res_path, out_wav)
        self.assertTrue(os.path.exists(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 1000)

    def test_mock_batch_synthesis(self):
        chunks = [
            NarrativeChunk(index=0, text="First paragraph exposition.", chunk_type=ChunkType.EXPOSITION),
            NarrativeChunk(index=1, text="Second paragraph with dialogue.", chunk_type=ChunkType.DIALOGUE, gender_hint="female"),
            NarrativeChunk(index=2, text="", chunk_type=ChunkType.SECTION_BREAK),
        ]
        wav_paths = self.engine.synthesize_batch(chunks, self.temp_dir, max_workers=2)

        self.assertEqual(len(wav_paths), 3)
        for p in wav_paths:
            self.assertTrue(os.path.exists(p))

    def test_get_voice_engine_factory(self):
        e_mock = get_voice_engine("mock")
        self.assertIsInstance(e_mock, MockVoiceEngine)

        e_edge = get_voice_engine("edge")
        self.assertIsInstance(e_edge, EdgeTTSVoiceEngine)

        e_openai = get_voice_engine("openai")
        self.assertIsInstance(e_openai, OpenAIVoiceEngine)

        e_gemini = get_voice_engine("gemini")
        self.assertIsInstance(e_gemini, GeminiVoiceEngine)

    def test_openai_engine_missing_key(self):
        engine = OpenAIVoiceEngine(api_key="")
        chunk = NarrativeChunk(index=0, text="Test", chunk_type=ChunkType.EXPOSITION)
        out_wav = os.path.join(self.temp_dir, "test.wav")
        with self.assertRaises(VoiceEngineError):
            engine.synthesize_chunk(chunk, out_wav)

    @patch("audiobook_narrator.engine.subprocess.run")
    def test_gemini_engine_success(self, mock_subproc):
        out_wav = os.path.join(self.temp_dir, "gemini_test.wav")
        # Create dummy wav file
        with open(out_wav, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 100)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Success"
        mock_proc.stderr = ""
        mock_subproc.return_value = mock_proc

        engine = GeminiVoiceEngine(binary_path="/bin/true")
        chunk = NarrativeChunk(index=0, text="Test Gemini Voice", chunk_type=ChunkType.EXPOSITION)
        res = engine.synthesize_chunk(chunk, out_wav)
        self.assertEqual(res, out_wav)


if __name__ == "__main__":
    unittest.main()
