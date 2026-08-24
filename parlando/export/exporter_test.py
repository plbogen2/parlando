"""Unit tests for AudioExporter container packaging and metadata tagging."""

import array
import math
import os
import tempfile
import unittest

from parlando.core.dsp import AudioBuffer
from parlando.core.stitcher import ChapterTimepoint
from parlando.export.exporter import AudioExporter
from parlando.config import AudioFormat


class AudioExporterTest(unittest.TestCase):

    def setUp(self):
        self.exporter = AudioExporter(sample_rate=24000)
        self.tmp_dir = tempfile.mkdtemp()
        samples = array.array("h", [int(5000 * math.sin(2 * math.pi * 440 * i / 24000)) for i in range(24000)])
        self.audio_buf = AudioBuffer(samples=samples, sample_rate=24000)

    def tearDown(self):
        for f in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, f))
        os.rmdir(self.tmp_dir)

    def test_export_wav(self):
        wav_path = os.path.join(self.tmp_dir, "test.wav")
        res = self.exporter.export(self.audio_buf, wav_path, title="WAV Book", author="Author", audio_format=AudioFormat.WAV)
        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 44)

    def test_export_m4b_with_chapters(self):
        m4b_path = os.path.join(self.tmp_dir, "test.m4b")
        tps = [
            ChapterTimepoint(title="Chapter 1", start_ms=0, end_ms=500, chapter_index=0),
            ChapterTimepoint(title="Chapter 2", start_ms=500, end_ms=1000, chapter_index=1),
        ]
        res = self.exporter.export(self.audio_buf, m4b_path, title="M4B Book", author="Author", chapter_timepoints=tps, audio_format=AudioFormat.M4B)
        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 0)


if __name__ == "__main__":
    unittest.main()
