"""Unit tests for NarrativeChunker prose segmentation."""

import unittest
from parlando.core.chunker import ChunkType, NarrativeChunker


class NarrativeChunkerTest(unittest.TestCase):

    def setUp(self):
        self.chunker = NarrativeChunker(target_chunk_words=15, max_chunk_words=30)

    def test_heading_detection(self):
        text = "# Chapter 1: The Matrix\n\nThe sky was grey."
        chunks = self.chunker.chunk_text(text)
        self.assertEqual(chunks[0].chunk_type, ChunkType.HEADING)
        self.assertEqual(chunks[0].text, "Chapter 1: The Matrix")
        self.assertEqual(chunks[1].chunk_type, ChunkType.NARRATION)

    def test_dialogue_extraction(self):
        text = 'Case looked at her. "Where are we going?" he asked softly.'
        chunks = self.chunker.chunk_text(text)
        types = [c.chunk_type for c in chunks]
        self.assertIn(ChunkType.DIALOGUE, types)
        dialogue_chunks = [c for c in chunks if c.chunk_type == ChunkType.DIALOGUE]
        self.assertEqual(dialogue_chunks[0].text, "Where are we going?")

    def test_section_break(self):
        text = "End of part one.\n\n* * *\n\nBeginning of part two."
        chunks = self.chunker.chunk_text(text)
        self.assertTrue(any(c.chunk_type == ChunkType.SECTION_BREAK for c in chunks))


if __name__ == "__main__":
    unittest.main()
