"""Parlando Core Audio & Narrative Processing Subsystem."""

from .chunker import ChunkType, NarrativeChunk, NarrativeChunker
from .dsp import AudioBuffer, DEFAULT_SAMPLE_RATE, DEFAULT_CHANNELS, DEFAULT_BIT_DEPTH
from .prosody import ProsodyDirector, ProsodyMarkup
from .stitcher import AudioStitcher, ChapterTimepoint, StitchedAudioResult

__all__ = [
    "AudioBuffer",
    "AudioStitcher",
    "ChapterTimepoint",
    "ChunkType",
    "DEFAULT_BIT_DEPTH",
    "DEFAULT_CHANNELS",
    "DEFAULT_SAMPLE_RATE",
    "NarrativeChunk",
    "NarrativeChunker",
    "ProsodyDirector",
    "ProsodyMarkup",
    "StitchedAudioResult",
]
