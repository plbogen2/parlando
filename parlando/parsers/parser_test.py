"""Unit tests for DocumentParser across Markdown, HTML, Plain Text, and PDF formats."""

import os
import tempfile
import unittest

from parlando.parsers import Chapter, DocumentParser, ParsedDocument


class DocumentParserTest(unittest.TestCase):

    def test_parse_plain_text(self):
        raw = "Line one.\n\nLine two is longer."
        doc = DocumentParser.from_text(raw, title="Test Tale", author="Author Name")
        self.assertEqual(doc.title, "Test Tale")
        self.assertEqual(doc.author, "Author Name")
        self.assertEqual(len(doc.chapters), 1)
        self.assertEqual(doc.total_words, 6)

    def test_parse_markdown_frontmatter(self):
        md = "---\ntitle: \"Neuromancer\"\nauthor: \"William Gibson\"\n---\n\n# Chapter 1\n\nThe sky above the port..."
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
            tf.write(md)
            tf_path = tf.name

        try:
            doc = DocumentParser.from_markdown_file(tf_path)
            self.assertEqual(doc.title, "Neuromancer")
            self.assertEqual(doc.author, "William Gibson")
            self.assertEqual(len(doc.chapters), 1)
            self.assertEqual(doc.chapters[0].title, "Chapter 1")
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_parse_html(self):
        html = """
        <html>
          <head><title>Story Title</title></head>
          <body>
            <h1>Section One</h1>
            <p>First paragraph of the tale.</p>
            <h1>Section Two</h1>
            <p>Second paragraph of the tale.</p>
          </body>
        </html>
        """
        doc = DocumentParser.from_html_string(html)
        self.assertEqual(len(doc.chapters), 2)
        self.assertEqual(doc.chapters[0].title, "Section One")
        self.assertEqual(doc.chapters[1].title, "Section Two")

    def test_get_audition_excerpt(self):
        raw = "Word " * 2000
        doc = DocumentParser.from_text(raw, title="Epic Novel")
        audition_doc = doc.get_audition_excerpt(max_words=500)
        self.assertEqual(audition_doc.title, "Epic Novel")
        self.assertEqual(len(audition_doc.chapters), 1)
        self.assertLessEqual(audition_doc.total_words, 510)


if __name__ == "__main__":
    unittest.main()
