"""Unit tests for prosody director."""

import unittest
from audiobook_narrator.chunker import ChunkType, NarrativeChunk
from audiobook_narrator.config import VOICE_PROFILES
from audiobook_narrator.prosody import ProsodyDirector


class ProsodyDirectorTest(unittest.TestCase):

    def setUp(self):
        self.profile = VOICE_PROFILES["cyberpunk_noir"]
        self.director = ProsodyDirector(self.profile)

    def test_voice_allocation_dialogue_gender(self):
        chunk_f = NarrativeChunk(index=0, text="Watch out!", chunk_type=ChunkType.DIALOGUE, gender_hint="female")
        chunk_m = NarrativeChunk(index=1, text="I got this.", chunk_type=ChunkType.DIALOGUE, gender_hint="male")
        chunk_narr = NarrativeChunk(index=2, text="The neon buzzed.", chunk_type=ChunkType.EXPOSITION)

        processed = self.director.process_chunks([chunk_f, chunk_m, chunk_narr])

        self.assertEqual(processed[0].voice_override, "Aoede")
        self.assertEqual(processed[1].voice_override, "Puck")
        self.assertEqual(processed[2].voice_override, "Fenrir")

    def test_abbreviation_expansion(self):
        text = "Dr. McCoy met with Prof. Smith vs. Mr. Anderson."
        expanded = self.director._condition_text_for_speech(text, ChunkType.EXPOSITION)
        self.assertIn("Doctor McCoy", expanded)
        self.assertIn("Professor Smith", expanded)
        self.assertIn("versus", expanded)
        self.assertIn("Mister Anderson", expanded)

    def test_year_expansion(self):
        text = "Back in 1984 and 2026, the matrix was born."
        expanded = self.director._condition_text_for_speech(text, ChunkType.EXPOSITION)
        self.assertIn("nineteen eighty-four", expanded)
        self.assertIn("twenty twenty-six", expanded)


if __name__ == "__main__":
    unittest.main()
