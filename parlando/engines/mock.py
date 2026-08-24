"""Fast, deterministic offline mock voice synthesis engine for testing."""

import array
import math
from typing import Optional

from parlando.core.chunker import ChunkType, NarrativeChunk
from parlando.core.dsp import AudioBuffer
from .base import BaseVoiceEngine


class MockVoiceEngine(BaseVoiceEngine):
    """Generates synthetic harmonics for fast, offline testing."""

    VOICE_FREQUENCIES = {
        "en-US-ChristopherNeural": 130.0,
        "en-US-GuyNeural": 115.0,
        "en-US-JennyNeural": 220.0,
        "en-GB-SoniaNeural": 210.0,
        "Fenrir": 120.0,
        "Aoede": 230.0,
        "Puck": 160.0,
        "default": 150.0,
    }

    def __init__(self, sample_rate: int = 24000, words_per_second: float = 3.2, default_voice: str = "default", **kwargs):
        self.sample_rate = sample_rate
        self.words_per_second = words_per_second
        self.default_voice = default_voice

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        text = chunk.text.strip()
        word_count = max(1, len(text.split())) if text else 1
        duration_s = word_count / self.words_per_second
        n_samples = max(240, int(duration_s * self.sample_rate))

        base_freq = self.VOICE_FREQUENCIES.get(chunk.character or self.default_voice, 150.0)
        if chunk.chunk_type == ChunkType.HEADING:
            base_freq *= 0.85
        elif chunk.chunk_type == ChunkType.DIALOGUE:
            base_freq *= 1.15

        samples = array.array("h")
        for i in range(n_samples):
            t = i / float(self.sample_rate)
            val = (
                0.60 * math.sin(2 * math.pi * base_freq * t)
                + 0.25 * math.sin(2 * math.pi * (2 * base_freq) * t)
                + 0.15 * math.sin(2 * math.pi * (3 * base_freq) * t)
            )

            envelope = 1.0
            attack_samples = int(0.02 * self.sample_rate)
            decay_samples = int(0.03 * self.sample_rate)
            if i < attack_samples:
                envelope = i / float(attack_samples)
            elif i > (n_samples - decay_samples):
                envelope = (n_samples - i) / float(decay_samples)

            clamped = max(-32767, min(32767, int(val * envelope * 8000)))
            samples.append(clamped)

        buf = AudioBuffer(samples=samples, sample_rate=self.sample_rate)
        buf.to_wav_file(output_path)
        return output_path
