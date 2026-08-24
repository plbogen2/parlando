"""Unit tests for audio DSP algorithms."""

import array
import math
import os
import tempfile
import unittest
from audiobook_narrator.dsp import AudioBuffer


class AudioBufferDSPTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sr = 24000

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_sine(self, freq_hz: float, duration_ms: float, amplitude: int = 16000) -> AudioBuffer:
        num_frames = int((duration_ms / 1000.0) * self.sr)
        samples = array.array("h")
        for f in range(num_frames):
            t = f / float(self.sr)
            val = int(amplitude * math.sin(2.0 * math.pi * freq_hz * t))
            samples.append(val)
        return AudioBuffer(samples=samples, sample_rate=self.sr, channels=1)

    def test_silence_generation(self):
        silence = AudioBuffer.create_silence(duration_ms=200, sample_rate=self.sr)
        self.assertEqual(silence.num_frames, 4800)
        self.assertEqual(silence.duration_ms, 200.0)
        self.assertTrue(all(s == 0 for s in silence.samples))

    def test_wav_roundtrip(self):
        orig_buf = self._generate_sine(440.0, 100.0)
        wav_path = os.path.join(self.temp_dir, "test.wav")
        orig_buf.to_wav_file(wav_path)

        loaded_buf = AudioBuffer.from_wav_file(wav_path)
        self.assertEqual(orig_buf.sample_rate, loaded_buf.sample_rate)
        self.assertEqual(orig_buf.channels, loaded_buf.channels)
        self.assertEqual(orig_buf.num_frames, loaded_buf.num_frames)
        self.assertEqual(list(orig_buf.samples), list(loaded_buf.samples))

    def test_zero_crossing_search(self):
        buf = self._generate_sine(100.0, 50.0)
        # Check nearest zero crossing around sample 200
        zc = buf.find_nearest_zero_crossing(200, search_window_frames=50)
        self.assertGreaterEqual(zc, 150)
        self.assertLessEqual(zc, 250)
        # Ensure sample value at or near zero crossing is very small
        sample_val = abs(buf.samples[zc])
        self.assertLessEqual(sample_val, 2000)

    def test_crossfade(self):
        buf_a = self._generate_sine(200.0, 100.0)
        buf_b = self._generate_sine(400.0, 100.0)

        crossfaded = buf_a.crossfade_with(buf_b, crossfade_ms=30)
        # Expected frames: (buf_a.num_frames + buf_b.num_frames) - crossfade_frames
        expected_fade_frames = int((30.0 / 1000.0) * self.sr)
        expected_total = buf_a.num_frames + buf_b.num_frames - expected_fade_frames
        self.assertEqual(crossfaded.num_frames, expected_total)

    def test_normalization(self):
        buf = self._generate_sine(440.0, 50.0, amplitude=5000)
        max_before = max(abs(s) for s in buf.samples)
        self.assertLessEqual(max_before, 5500)

        buf.normalize(target_peak_fraction=0.9)
        max_after = max(abs(s) for s in buf.samples)
        target = int(32767 * 0.9)
        self.assertAlmostEqual(max_after, target, delta=20)


if __name__ == "__main__":
    unittest.main()
