"""Parlando Core Audio & Narrative Processing Subsystem."""

from .chunker import ChunkType, NarrativeChunk, NarrativeChunker
from .dsp import AudioBuffer, DEFAULT_SAMPLE_RATE, DEFAULT_CHANNELS, DEFAULT_BIT_DEPTH
from .prosody import ProsodyDirector, ProsodyMarkup
from .speaker import CharacterProfile, GenericSpeakerDetector, SceneAwareVoiceCaster, normalize_character_input
from .stitcher import AudioStitcher, ChapterTimepoint, StitchedAudioResult

__all__ = [
    "AudioBuffer",
    "AudioStitcher",
    "ChapterTimepoint",
    "CharacterProfile",
    "ChunkType",
    "DEFAULT_BIT_DEPTH",
    "DEFAULT_CHANNELS",
    "DEFAULT_SAMPLE_RATE",
    "GenericSpeakerDetector",
    "NarrativeChunk",
    "NarrativeChunker",
    "ProsodyDirector",
    "ProsodyMarkup",
    "SceneAwareVoiceCaster",
    "StitchedAudioResult",
    "normalize_character_input",
]
