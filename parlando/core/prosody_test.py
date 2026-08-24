"""Unit tests for ProsodyDirector text normalization and voice allocation."""

import unittest
from parlando.core.chunker import ChunkType, NarrativeChunk
from parlando.core.prosody import ProsodyDirector
from parlando.config import VOICE_PROFILES


class ProsodyDirectorTest(unittest.TestCase):

    def setUp(self):
        self.profile = VOICE_PROFILES["cyberpunk_noir"]
        self.director = ProsodyDirector(voice_profile=self.profile)

    def test_abbreviation_expansion(self):
        raw = "Dr. McCoy met with Col. Smith and Prof. Jones."
        clean = self.director.normalize_text(raw)
        self.assertIn("Doctor McCoy", clean)
        self.assertIn("Colonel Smith", clean)
        self.assertIn("Professor Jones", clean)

    def test_voice_allocation_dialogue_gender(self):
        chunk_m = NarrativeChunk(text="Look out!", chunk_type=ChunkType.DIALOGUE, gender="male")
        markup_m = self.director.process_chunk(chunk_m)
        self.assertEqual(markup_m.voice_name, "en-US-GuyNeural")

        chunk_f = NarrativeChunk(text="I see it.", chunk_type=ChunkType.DIALOGUE, gender="female")
        markup_f = self.director.process_chunk(chunk_f)
        self.assertEqual(markup_f.voice_name, "en-US-JennyNeural")

        chunk_n = NarrativeChunk(text="The terminal hummed.", chunk_type=ChunkType.NARRATION)
        markup_n = self.director.process_chunk(chunk_n)
        self.assertEqual(markup_n.voice_name, "en-US-ChristopherNeural")


if __name__ == "__main__":
    unittest.main()
