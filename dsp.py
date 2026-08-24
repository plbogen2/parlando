"""Audio Digital Signal Processing (DSP) engine for zero-crossing alignment, crossfading, and stitching."""

import array
import math
import os
import struct
import wave
from dataclasses import dataclass
from typing import List, Optional, Tuple
from .config import (
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLE_WIDTH,
)


@dataclass
class AudioBuffer:
    """In-memory 16-bit PCM audio buffer with DSP manipulation methods."""
    samples: array.array
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS

    def __post_init__(self):
        if not isinstance(self.samples, array.array):
            self.samples = array.array("h", self.samples)

    @property
    def num_frames(self) -> int:
        return len(self.samples) // self.channels

    @property
    def duration_sec(self) -> float:
        return self.num_frames / float(self.sample_rate)

    @property
    def duration_ms(self) -> float:
        return self.duration_sec * 1000.0

    @classmethod
    def from_wav_file(cls, path: str) -> "AudioBuffer":
        """Read a WAV file into an AudioBuffer."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"WAV audio file not found: {path}")

        with wave.open(path, "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sample_rate = wf.getframerate()
            nframes = wf.getnframes()
            raw_bytes = wf.readframes(nframes)

            if sampwidth == 2:
                samples = array.array("h")
                samples.frombytes(raw_bytes)
            elif sampwidth == 1:
                # Convert 8-bit unsigned to 16-bit signed
                samples = array.array("h", [(b - 128) * 256 for b in raw_bytes])
            elif sampwidth == 4:
                # Downscale 32-bit signed to 16-bit
                raw_32 = array.array("i")
                raw_32.frombytes(raw_bytes)
                samples = array.array("h", [s >> 16 for s in raw_32])
            else:
                raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

            return cls(samples=samples, sample_rate=sample_rate, channels=channels)

    def to_wav_file(self, path: str) -> None:
        """Write the AudioBuffer to a standard 16-bit RIFF/WAVE file."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(DEFAULT_SAMPLE_WIDTH)
            wf.setframerate(self.sample_rate)
            wf.writeframes(self.samples.tobytes())

    @classmethod
    def create_silence(cls, duration_ms: int, sample_rate: int = DEFAULT_SAMPLE_RATE, channels: int = DEFAULT_CHANNELS) -> "AudioBuffer":
        """Generate a silent PCM buffer for the given duration in milliseconds."""
        if duration_ms <= 0:
            return cls(samples=array.array("h"), sample_rate=sample_rate, channels=channels)

        num_samples = int((duration_ms / 1000.0) * sample_rate) * channels
        samples = array.array("h", [0] * num_samples)
        return cls(samples=samples, sample_rate=sample_rate, channels=channels)

    def clone(self) -> "AudioBuffer":
        """Create a deep copy of this audio buffer."""
        return AudioBuffer(
            samples=array.array("h", self.samples),
            sample_rate=self.sample_rate,
            channels=self.channels,
        )

    def slice_ms(self, start_ms: float, end_ms: Optional[float] = None) -> "AudioBuffer":
        """Slice the buffer by millisecond offsets."""
        start_frame = max(0, int((start_ms / 1000.0) * self.sample_rate))
        if end_ms is not None:
            end_frame = min(self.num_frames, int((end_ms / 1000.0) * self.sample_rate))
        else:
            end_frame = self.num_frames

        start_idx = start_frame * self.channels
        end_idx = end_frame * self.channels
        return AudioBuffer(
            samples=array.array("h", self.samples[start_idx:end_idx]),
            sample_rate=self.sample_rate,
            channels=self.channels,
        )

    def find_nearest_zero_crossing(self, frame_index: int, search_window_frames: int = 120) -> int:
        """Locate the closest zero-crossing index within a search window to eliminate DC pops."""
        if self.num_frames <= 1:
            return 0

        target = max(0, min(self.num_frames - 1, frame_index))
        window_start = max(0, target - search_window_frames)
        window_end = min(self.num_frames - 1, target + search_window_frames)

        best_frame = target
        best_diff = float("inf")

        for f in range(window_start, window_end):
            idx1 = f * self.channels
            idx2 = (f + 1) * self.channels
            s1 = self.samples[idx1]
            s2 = self.samples[idx2]

            # Check if sign changes across zero
            if (s1 <= 0 and s2 >= 0) or (s1 >= 0 and s2 <= 0):
                diff = abs(f - target)
                if diff < best_diff:
                    best_diff = diff
                    best_frame = f if abs(s1) <= abs(s2) else f + 1

        return best_frame

    def apply_fade_in(self, duration_ms: float) -> "AudioBuffer":
        """Apply a smooth quarter-sine fade-in curve to prevent start clicks."""
        fade_frames = int((duration_ms / 1000.0) * self.sample_rate)
        fade_frames = min(fade_frames, self.num_frames)
        if fade_frames <= 0:
            return self

        for f in range(fade_frames):
            # Equal power quarter-sine fade-in curve
            t = f / float(fade_frames)
            gain = math.sin(t * (math.pi / 2.0))
            for ch in range(self.channels):
                idx = f * self.channels + ch
                self.samples[idx] = int(self.samples[idx] * gain)

        return self

    def apply_fade_out(self, duration_ms: float) -> "AudioBuffer":
        """Apply a smooth quarter-cosine fade-out curve to prevent ending clicks."""
        fade_frames = int((duration_ms / 1000.0) * self.sample_rate)
        fade_frames = min(fade_frames, self.num_frames)
        if fade_frames <= 0:
            return self

        start_f = self.num_frames - fade_frames
        for i, f in enumerate(range(start_f, self.num_frames)):
            t = i / float(fade_frames)
            gain = math.cos(t * (math.pi / 2.0))
            for ch in range(self.channels):
                idx = f * self.channels + ch
                self.samples[idx] = int(self.samples[idx] * gain)

        return self

    def crossfade_with(self, next_buffer: "AudioBuffer", crossfade_ms: int = 30) -> "AudioBuffer":
        """Stitch two audio buffers with zero-crossing alignment and equal-power crossfading."""
        if self.sample_rate != next_buffer.sample_rate:
            raise ValueError(f"Sample rate mismatch: {self.sample_rate} vs {next_buffer.sample_rate}")
        if self.channels != next_buffer.channels:
            raise ValueError(f"Channel count mismatch: {self.channels} vs {next_buffer.channels}")

        if self.num_frames == 0:
            return next_buffer.clone()
        if next_buffer.num_frames == 0:
            return self.clone()

        crossfade_frames = int((crossfade_ms / 1000.0) * self.sample_rate)
        max_possible_fade = min(crossfade_frames, self.num_frames // 2, next_buffer.num_frames // 2)

        if max_possible_fade <= 4:
            # Buffer too short for crossfade; perform simple zero-crossing splice
            zc_self = self.find_nearest_zero_crossing(self.num_frames - 1)
            zc_next = next_buffer.find_nearest_zero_crossing(0)
            
            combined_samples = array.array("h")
            combined_samples.extend(self.samples[:zc_self * self.channels])
            combined_samples.extend(next_buffer.samples[zc_next * self.channels:])
            return AudioBuffer(samples=combined_samples, sample_rate=self.sample_rate, channels=self.channels)

        # Crossfade overlapping region
        overlap_frames = max_possible_fade
        out_samples = array.array("h")

        # Head of first buffer (unfaded)
        unfaded_self_end = (self.num_frames - overlap_frames) * self.channels
        out_samples.extend(self.samples[:unfaded_self_end])

        # Crossfaded overlap region
        for f in range(overlap_frames):
            t = f / float(overlap_frames)
            # Equal power crossfade curves: cos(t * pi/2), sin(t * pi/2)
            gain_a = math.cos(t * (math.pi / 2.0))
            gain_b = math.sin(t * (math.pi / 2.0))

            idx_a = (self.num_frames - overlap_frames + f) * self.channels
            idx_b = f * self.channels

            for ch in range(self.channels):
                val_a = self.samples[idx_a + ch]
                val_b = next_buffer.samples[idx_b + ch]
                mixed = int(val_a * gain_a + val_b * gain_b)
                # Hard clamp to 16-bit signed bounds
                clamped = max(-32768, min(32767, mixed))
                out_samples.append(clamped)

        # Tail of second buffer (unfaded)
        unfaded_next_start = overlap_frames * self.channels
        out_samples.extend(next_buffer.samples[unfaded_next_start:])

        return AudioBuffer(samples=out_samples, sample_rate=self.sample_rate, channels=self.channels)

    def append(self, other: "AudioBuffer") -> "AudioBuffer":
        """Directly append another buffer."""
        if self.num_frames == 0:
            return other.clone()
        if other.num_frames == 0:
            return self.clone()

        new_samples = array.array("h", self.samples)
        new_samples.extend(other.samples)
        return AudioBuffer(samples=new_samples, sample_rate=self.sample_rate, channels=self.channels)

    def normalize(self, target_peak_fraction: float = 0.95) -> "AudioBuffer":
        """Normalize buffer peak amplitude to avoid clipping and maximize dynamic clarity."""
        if self.num_frames == 0:
            return self

        max_sample = max(abs(s) for s in self.samples)
        if max_sample == 0:
            return self

        target_max = int(32767 * target_peak_fraction)
        scale_factor = target_max / float(max_sample)

        if abs(scale_factor - 1.0) < 0.02:
            return self  # Already near target

        for i in range(len(self.samples)):
            scaled = int(self.samples[i] * scale_factor)
            self.samples[i] = max(-32768, min(32767, scaled))

        return self
