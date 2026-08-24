"""End-to-end integration tests for audiobook narrator."""

import os
import tempfile
import unittest
from audiobook_narrator.cli import build_parser, run_pipeline


class IntegrationPipelineTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_md = os.path.join(self.temp_dir, "sample.md")
        with open(self.sample_md, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "title: Cyber Deck Chronicles\n"
                "author: William Gibson\n"
                "---\n\n"
                "# Chapter 1: The Port\n\n"
                "The sky above the port was grey.\n\n"
                '"Can you jack in?" she whispered.\n\n'
                '"Not yet," Case replied.\n'
            )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_pipeline_e2e_mp3(self):
        parser = build_parser()
        args = parser.parse_args([
            self.sample_md,
            "--mock",
            "--output-dir", self.temp_dir,
            "--output-format", "mp3",
            "--profile", "cyberpunk_noir",
        ])

        out_path = run_pipeline(args)
        self.assertTrue(os.path.exists(out_path))
        self.assertTrue(out_path.endswith(".mp3"))
        self.assertGreater(os.path.getsize(out_path), 5000)

    def test_mock_pipeline_e2e_m4b(self):
        parser = build_parser()
        args = parser.parse_args([
            self.sample_md,
            "--mock",
            "--output-dir", self.temp_dir,
            "--output-format", "m4b",
            "--speed", "1.1",
        ])

        out_path = run_pipeline(args)
        self.assertTrue(os.path.exists(out_path))
        self.assertTrue(out_path.endswith(".m4b"))
        self.assertGreater(os.path.getsize(out_path), 3000)

    def test_dry_run_mode(self):
        parser = build_parser()
        args = parser.parse_args([
            self.sample_md,
            "--dry-run",
        ])
        out_path = run_pipeline(args)
        self.assertEqual(out_path, "")


if __name__ == "__main__":
    unittest.main()
