"""Unit tests for narrative chunker."""

import unittest
from audiobook_narrator.chunker import ChunkType, NarrativeChunker


class NarrativeChunkerTest(unittest.TestCase):

    def setUp(self):
        self.chunker = NarrativeChunker(max_chunk_chars=300)

    def test_dialogue_and_exposition_segmentation(self):
        text = 'Case leaned against the damp counter. "I can\'t jack in," he muttered. "My nerves are fried."'
        chunks = self.chunker.chunk_text(text)

        self.assertGreaterEqual(len(chunks), 2)
        # Verify exposition vs dialogue classification
        types = [c.chunk_type for c in chunks]
        self.assertIn(ChunkType.EXPOSITION, types)
        self.assertIn(ChunkType.DIALOGUE, types)

    def test_section_break_handling(self):
        text = "End of section.\n\n* * *\n\nBeginning of next section."
        chunks = self.chunker.chunk_text(text)
        types = [c.chunk_type for c in chunks]
        self.assertIn(ChunkType.SECTION_BREAK, types)

    def test_punctuation_pause_calculation(self):
        pause_ellipsis = self.chunker._calculate_punctuation_pause("He drifted away...")
        pause_period = self.chunker._calculate_punctuation_pause("He stopped.")
        pause_comma = self.chunker._calculate_punctuation_pause("Running fast,")

        self.assertGreater(pause_ellipsis, pause_period)
        self.assertGreater(pause_period, pause_comma)

    def test_speaker_gender_inference(self):
        gender_f = self.chunker._infer_speaker_gender('"Stay back," she whispered quietly.', 0, 12)
        gender_m = self.chunker._infer_speaker_gender('"Let us go," he said sternly.', 0, 13)

        self.assertEqual(gender_f, "female")
        self.assertEqual(gender_m, "male")


if __name__ == "__main__":
    unittest.main()
