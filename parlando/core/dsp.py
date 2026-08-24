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

        start = 0
        for i, s in enumerate(self.samples):
            if abs(s) > threshold_amplitude:
                start = max(0, i - int((padding_ms / 1000.0) * self.sample_rate))
                break

        end = len(self.samples)
        for i in range(len(self.samples) - 1, -1, -1):
            if abs(self.samples[i]) > threshold_amplitude:
                end = min(len(self.samples), i + int((padding_ms / 1000.0) * self.sample_rate))
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

        tail_start = len(self.samples) - fade_samples
        for i in range(fade_samples):
            factor = i / float(fade_samples)
            s_a = self.samples[tail_start + i]
            s_b = other.samples[i]
            blended = int(s_a * math.cos(factor * (math.pi / 2.0)) + s_b * math.sin(factor * (math.pi / 2.0)))
            blended = max(-32768, min(32767, blended))
            self.samples[tail_start + i] = blended

        self.samples.extend(other.samples[fade_samples:])
