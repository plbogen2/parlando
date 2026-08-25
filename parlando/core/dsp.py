"""Pure Python 16-bit PCM Audio Signal Processing (DSP) & Waveform Manipulation."""

import array
import io
import math
import os
import struct
import wave
from typing import List, Optional, Tuple


DEFAULT_SAMPLE_RATE = 24000
DEFAULT_CHANNELS = 1
DEFAULT_BIT_DEPTH = 16


class AudioBuffer:
    """In-memory 16-bit PCM mono audio buffer for zero-crossing DSP operations."""

    def __init__(self, samples: Optional[array.array] = None, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.samples = samples if samples is not None else array.array("h")

    @classmethod
    def from_wav_file(cls, filepath: str) -> "AudioBuffer":
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 44:
            return cls()
        try:
            with wave.open(filepath, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()

                if sampwidth != 2:
                    return cls(sample_rate=sample_rate)

                raw_array = array.array("h", raw_bytes)
                if n_channels == 2:
                    samples = raw_array[0::2]
                else:
                    samples = raw_array

                return cls(samples=samples, sample_rate=sample_rate)
        except Exception:
            return cls()

    @classmethod
    def from_wav_bytes(cls, data: bytes) -> "AudioBuffer":
        if len(data) < 44:
            return cls()
        try:
            bio = io.BytesIO(data)
            with wave.open(bio, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)
                n_channels = wf.getnchannels()
                raw_array = array.array("h", raw_bytes)
                if n_channels == 2:
                    samples = raw_array[0::2]
                else:
                    samples = raw_array
                return cls(samples=samples, sample_rate=sample_rate)
        except Exception:
            return cls()

    @classmethod
    def create_silence(cls, duration_ms: int, sample_rate: int = DEFAULT_SAMPLE_RATE) -> "AudioBuffer":
        n_samples = int((duration_ms / 1000.0) * sample_rate)
        samples = array.array("h", [0] * n_samples)
        return cls(samples=samples, sample_rate=sample_rate)

    @property
    def duration_ms(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return (len(self.samples) / self.sample_rate) * 1000.0

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0

    def is_empty(self) -> bool:
        return len(self.samples) == 0

    def to_wav_file(self, filepath: str):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(self.samples.tobytes())

    def to_wav_bytes(self) -> bytes:
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(self.samples.tobytes())
        return bio.getvalue()

    def find_nearest_zero_crossing(self, target_idx: int, window_samples: int = 240) -> int:
        n = len(self.samples)
        if n == 0:
            return 0
        target_idx = max(0, min(target_idx, n - 1))
        start = max(0, target_idx - window_samples)
        end = min(n - 1, target_idx + window_samples)

        try:
            import numpy as np
            arr = np.frombuffer(self.samples, dtype=np.int16)[start : end + 1]
            signs = np.signbit(arr)
            zero_crossings = np.where(signs[:-1] != signs[1:])[0]
            if len(zero_crossings) > 0:
                actual_indices = start + zero_crossings
                diffs = np.abs(actual_indices - target_idx)
                best_zc = int(actual_indices[np.argmin(diffs)])
                s1 = abs(self.samples[best_zc])
                s2 = abs(self.samples[min(n - 1, best_zc + 1)])
                return best_zc if s1 <= s2 else min(n - 1, best_zc + 1)
        except ImportError:
            pass

        best_idx = target_idx
        min_val = abs(self.samples[target_idx])

        for i in range(start, end):
            s1 = self.samples[i]
            s2 = self.samples[i + 1]
            if (s1 <= 0 and s2 >= 0) or (s1 >= 0 and s2 <= 0):
                return i if abs(s1) <= abs(s2) else i + 1
            if abs(s1) < min_val:
                min_val = abs(s1)
                best_idx = i

        return best_idx

    def trim_silence(self, threshold_amplitude: int = 150, padding_ms: int = 15) -> "AudioBuffer":
        if len(self.samples) == 0:
            return AudioBuffer(sample_rate=self.sample_rate)

        pad_samples = int((padding_ms / 1000.0) * self.sample_rate)
        n = len(self.samples)

        try:
            import numpy as np
            arr = np.frombuffer(self.samples, dtype=np.int16)
            active = np.where(np.abs(arr) > threshold_amplitude)[0]
            if len(active) == 0:
                return AudioBuffer(sample_rate=self.sample_rate)
            start = max(0, int(active[0]) - pad_samples)
            end = min(n, int(active[-1]) + 1 + pad_samples)
            start_zc = self.find_nearest_zero_crossing(start)
            end_zc = self.find_nearest_zero_crossing(end)
            return AudioBuffer(samples=self.samples[start_zc:end_zc], sample_rate=self.sample_rate)
        except ImportError:
            pass

        start = 0
        for i, s in enumerate(self.samples):
            if abs(s) > threshold_amplitude:
                start = max(0, i - pad_samples)
                break

        end = len(self.samples)
        for i in range(len(self.samples) - 1, -1, -1):
            if abs(self.samples[i]) > threshold_amplitude:
                end = min(len(self.samples), i + pad_samples)
                break

        if start >= end:
            return AudioBuffer(sample_rate=self.sample_rate)

        start_zc = self.find_nearest_zero_crossing(start)
        end_zc = self.find_nearest_zero_crossing(end)
        return AudioBuffer(samples=self.samples[start_zc:end_zc], sample_rate=self.sample_rate)

    def append(self, other: "AudioBuffer"):
        if other.is_empty():
            return
        self.samples.extend(other.samples)

    def crossfade_append(self, other: "AudioBuffer", crossfade_ms: int = 35):
        if self.is_empty():
            self.samples = array.array("h", other.samples)
            return
        if other.is_empty():
            return

        fade_samples = int((crossfade_ms / 1000.0) * self.sample_rate)
        fade_samples = min(fade_samples, len(self.samples), len(other.samples))

        if fade_samples <= 0:
            self.append(other)
            return

        try:
            import numpy as np
            tail_start = len(self.samples) - fade_samples
            arr_a = np.frombuffer(self.samples, dtype=np.int16)[tail_start:]
            arr_b = np.frombuffer(other.samples, dtype=np.int16)[:fade_samples]
            ramp = np.linspace(0.0, np.pi / 2.0, fade_samples, endpoint=False)
            blended = (arr_a * np.cos(ramp) + arr_b * np.sin(ramp)).clip(-32768, 32767).astype(np.int16)

            self.samples = self.samples[:tail_start]
            self.samples.frombytes(blended.tobytes())
            self.samples.extend(other.samples[fade_samples:])
            return
        except ImportError:
            pass

        tail_start = len(self.samples) - fade_samples
        for i in range(fade_samples):
            factor = i / float(fade_samples)
            s_a = self.samples[tail_start + i]
            s_b = other.samples[i]
            blended = int(s_a * math.cos(factor * (math.pi / 2.0)) + s_b * math.sin(factor * (math.pi / 2.0)))
            blended = max(-32768, min(32767, blended))
            self.samples[tail_start + i] = blended

        self.samples.extend(other.samples[fade_samples:])

    @staticmethod
    def _fft(x: List[complex]) -> List[complex]:
        """Recursive Cooley-Tukey radix-2 FFT on complex list with optional numpy acceleration."""
        try:
            import numpy as np
            return list(np.fft.fft(x))
        except ImportError:
            pass

        n = len(x)
        if n <= 1:
            return x
        even = AudioBuffer._fft(x[0::2])
        odd = AudioBuffer._fft(x[1::2])
        t = [math.e ** (-2j * math.pi * k / n) * odd[k] for k in range(n // 2)]
        return [even[k] + t[k] for k in range(n // 2)] + [even[k] - t[k] for k in range(n // 2)]

    def compute_rms(self) -> float:
        """Compute Root Mean Square amplitude of 16-bit PCM samples."""
        if not self.samples:
            return 0.0
        try:
            import numpy as np
            arr = np.frombuffer(self.samples, dtype=np.int16).astype(np.float64)
            return float(np.sqrt(np.mean(arr ** 2)))
        except ImportError:
            pass
        mean_sq = sum(s * s for s in self.samples) / len(self.samples)
        return math.sqrt(mean_sq)

    def compute_zero_crossing_rate(self) -> float:
        """Compute estimated zero crossing frequency (Hz)."""
        n = len(self.samples)
        if n < 2 or self.sample_rate <= 0:
            return 0.0
        try:
            import numpy as np
            arr = np.frombuffer(self.samples, dtype=np.int16)
            zc = int(np.sum(np.signbit(arr[:-1]) != np.signbit(arr[1:])))
            duration_s = n / float(self.sample_rate)
            return (zc / duration_s) / 2.0 if duration_s > 0 else 0.0
        except ImportError:
            pass
        zc = 0
        for i in range(1, n):
            if (self.samples[i - 1] <= 0 and self.samples[i] > 0) or (self.samples[i - 1] >= 0 and self.samples[i] < 0):
                zc += 1
        duration_s = n / float(self.sample_rate)
        return (zc / duration_s) / 2.0 if duration_s > 0 else 0.0

    def analyze_speech_spectrum(self, window_size: int = 2048, hop_size: int = 1024) -> dict:
        """Perform spectral FFT analysis to determine energy distribution across speech formants."""
        n_samples = len(self.samples)
        if n_samples == 0:
            return {"is_speech": False, "rms": 0.0, "reason": "empty_buffer"}

        rms = self.compute_rms()
        if rms < 150.0:  # Silence / noise floor threshold for 16-bit PCM
            return {"is_speech": False, "rms": round(rms, 2), "reason": "silence_or_below_noise_floor"}

        zcr_hz = self.compute_zero_crossing_rate()

        freq_bin_width = self.sample_rate / float(window_size)
        min_speech_bin = max(1, int(80.0 / freq_bin_width))
        max_speech_bin = min(window_size // 2 - 1, int(4000.0 / freq_bin_width))

        try:
            import numpy as np
            arr = np.frombuffer(self.samples, dtype=np.int16).astype(np.float64)
            if n_samples < window_size:
                arr = np.pad(arr, (0, window_size - n_samples))
                windows = [arr]
            else:
                num_windows = min(30, (n_samples - window_size) // hop_size + 1)
                windows = [arr[i * hop_size : i * hop_size + window_size] for i in range(num_windows)]

            hanning = np.hanning(window_size)
            total_power = 0.0
            total_speech_power = 0.0
            peak_speech_bin = 0.0

            for win in windows:
                spectrum = np.abs(np.fft.rfft(win * hanning)) ** 2
                pos_spec = spectrum[1:]
                total_power += float(np.sum(pos_spec))
                speech_slice = spectrum[min_speech_bin : max_speech_bin + 1]
                if len(speech_slice) > 0:
                    total_speech_power += float(np.sum(speech_slice))
                    peak_speech_bin = max(peak_speech_bin, float(np.max(speech_slice)))

            speech_ratio = (total_speech_power / total_power) if total_power > 0 else 0.0
            num_speech_bins = max(1, max_speech_bin - min_speech_bin + 1)
            avg_speech_bin_val = (total_speech_power / num_speech_bins) if total_speech_power > 0 else 1.0
            crest_factor = (peak_speech_bin / avg_speech_bin_val) if avg_speech_bin_val > 0 else 0.0

            is_speech = (rms > 150.0) and (speech_ratio >= 0.50) and (30 <= zcr_hz <= 4500) and (crest_factor > 1.8)
            return {
                "is_speech": is_speech,
                "rms": round(rms, 2),
                "zcr_hz": round(zcr_hz, 1),
                "speech_band_ratio": round(speech_ratio, 4),
                "spectral_crest_factor": round(crest_factor, 2),
            }
        except ImportError:
            pass

        # Extract windows for FFT fallback
        if n_samples < window_size:
            padded = list(self.samples) + [0] * (window_size - n_samples)
            windows = [padded]
        else:
            num_windows = min(30, (n_samples - window_size) // hop_size + 1)
            windows = [list(self.samples[i * hop_size : i * hop_size + window_size]) for i in range(num_windows)]

        total_speech_power = 0.0
        total_power = 0.0
        peak_speech_bin_val = 0.0
        hanning = [0.5 * (1.0 - math.cos(2.0 * math.pi * i / (window_size - 1))) for i in range(window_size)]

        for win in windows:
            complex_in = [win[i] * hanning[i] for i in range(window_size)]
            spectrum = self._fft(complex_in)
            half_n = window_size // 2
            for bin_idx in range(1, half_n):
                power = abs(spectrum[bin_idx]) ** 2
                total_power += power
                if min_speech_bin <= bin_idx <= max_speech_bin:
                    total_speech_power += power
                    if power > peak_speech_bin_val:
                        peak_speech_bin_val = power

        speech_ratio = (total_speech_power / total_power) if total_power > 0 else 0.0
        num_speech_bins = max(1, max_speech_bin - min_speech_bin + 1)
        avg_speech_bin_val = (total_speech_power / num_speech_bins) if total_speech_power > 0 else 1.0
        crest_factor = (peak_speech_bin_val / avg_speech_bin_val) if avg_speech_bin_val > 0 else 0.0

        is_speech = (rms > 150.0) and (speech_ratio >= 0.50) and (30 <= zcr_hz <= 4500) and (crest_factor > 1.8)

        return {
            "is_speech": is_speech,
            "rms": round(rms, 2),
            "zcr_hz": round(zcr_hz, 1),
            "speech_band_ratio": round(speech_ratio, 4),
            "spectral_crest_factor": round(crest_factor, 2),
        }

    def is_valid_speech(self) -> bool:
        """Quick boolean helper to check if audio buffer contains active speech."""
        return self.analyze_speech_spectrum().get("is_speech", False)
