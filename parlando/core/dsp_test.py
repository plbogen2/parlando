"""Unit tests for AudioBuffer and Zero-Crossing DSP algorithms."""

import array
import math
import os
import tempfile
import unittest

from parlando.core.dsp import AudioBuffer, DEFAULT_SAMPLE_RATE


class AudioBufferDSPTest(unittest.TestCase):

    def test_create_silence(self):
        buf = AudioBuffer.create_silence(duration_ms=100, sample_rate=24000)
        self.assertEqual(len(buf.samples), 2400)
        self.assertAlmostEqual(buf.duration_ms, 100.0)
        self.assertEqual(set(buf.samples), {0})

    def test_from_and_to_wav_file(self):
        samples = array.array("h", [int(10000 * math.sin(2 * math.pi * 440 * i / 24000)) for i in range(2400)])
        buf = AudioBuffer(samples=samples, sample_rate=24000)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name

        try:
            buf.to_wav_file(wav_path)
            self.assertTrue(os.path.exists(wav_path))
            self.assertGreater(os.path.getsize(wav_path), 44)

            loaded = AudioBuffer.from_wav_file(wav_path)
            self.assertEqual(loaded.sample_rate, 24000)
            self.assertEqual(len(loaded.samples), 2400)
            self.assertEqual(loaded.samples[0], buf.samples[0])
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_find_nearest_zero_crossing(self):
        samples = array.array("h", [1000, 800, 500, 100, -100, -500, -800, -1000])
        buf = AudioBuffer(samples=samples, sample_rate=24000)
        zc = buf.find_nearest_zero_crossing(target_idx=2, window_samples=5)
        self.assertTrue(zc in (3, 4))

    def test_crossfade_append(self):
        s1 = array.array("h", [1000] * 2400)
        s2 = array.array("h", [2000] * 2400)
        b1 = AudioBuffer(samples=s1, sample_rate=24000)
        b2 = AudioBuffer(samples=s2, sample_rate=24000)

        b1.crossfade_append(b2, crossfade_ms=35)
        self.assertGreater(len(b1.samples), 2400)


if __name__ == "__main__":
    unittest.main()
