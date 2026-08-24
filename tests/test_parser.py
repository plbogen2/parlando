"""Unit tests for document parser."""

import os
import tempfile
import unittest
from audiobook_narrator.parser import DocumentParser, ParsedDocument


class DocumentParserTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_plain_text(self):
        sample_path = os.path.join(self.temp_dir, "story.txt")
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write("Chapter 1: The Beginning\n\nIt was a dark and stormy night.\n\nChapter 2: The Grid\n\nThe console hummed.")

        doc = DocumentParser.parse_file(sample_path, title="My Story", author="Gibby")
        self.assertEqual(doc.title, "My Story")
        self.assertEqual(doc.author, "Gibby")
        self.assertEqual(len(doc.chapters), 2)
        self.assertIn("dark and stormy", doc.chapters[0].content)
        self.assertIn("console hummed", doc.chapters[1].content)

    def test_parse_markdown_frontmatter(self):
        sample_path = os.path.join(self.temp_dir, "story.md")
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: Digital Rain\nauthor: Case\n---\n\n# Chapter 1\n\nData streamed past.")

        doc = DocumentParser.parse_file(sample_path)
        self.assertEqual(doc.title, "Digital Rain")
        self.assertEqual(doc.author, "Case")
        self.assertEqual(len(doc.chapters), 1)
        self.assertEqual(doc.chapters[0].title, "Chapter 1")
        self.assertIn("Data streamed past", doc.chapters[0].content)

    def test_clean_prose_text(self):
        raw = '“Hello,” he said — “check [this link](http://matrix.net) and **bold** text.”'
        cleaned = DocumentParser.clean_prose_text(raw)
        self.assertEqual(cleaned, '"Hello," he said — "check this link and bold text."')

    def test_parse_html(self):
        sample_path = os.path.join(self.temp_dir, "article.html")
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write("<html><head><title>Cyber Deck Tech</title></head><body><h1>Overview</h1><p>Neural interfaces bridge the cortex.</p></body></html>")

        doc = DocumentParser.parse_file(sample_path)
        self.assertEqual(doc.title, "Cyber Deck Tech")
        self.assertIn("Neural interfaces", doc.chapters[0].content)

    def test_parse_pdf(self):
        sample_path = os.path.join(self.temp_dir, "story.pdf")
        pdf_bytes = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 73 >> stream
BT
/F1 12 Tf
72 712 Td
(Chapter 1: The Sprawl) Tj
0 -20 Td
(The sky above the port was the color of television, tuned to a dead channel.) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000368 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
445
%%EOF
"""
        with open(sample_path, "wb") as f:
            f.write(pdf_bytes)

        doc = DocumentParser.parse_file(sample_path, title="Neuromancer", author="William Gibson")
        self.assertEqual(doc.title, "Neuromancer")
        self.assertEqual(doc.author, "William Gibson")
        self.assertEqual(doc.source_format, "pdf")
        self.assertTrue(len(doc.chapters) >= 1)
        self.assertIn("dead channel", doc.chapters[0].content)


if __name__ == "__main__":
    unittest.main()
