"""Audiobook Narrator - Neural Speech Synthesis & Audio Engineering Pipeline.

Transform manuscripts, Markdown chapters, EPUBs, HTML, and live Web URLs into fluid,
studio-quality audiobooks with intelligent prosody, semantic chunking, and zero-crossing stitching.
"""

from .chunker import (
    ChunkType,
    NarrativeChunk,
    NarrativeChunker,
)
from .config import (
    AudioFormat,
    PACING_PRESETS,
    PacingConfig,
    PacingMode,
    VALID_NEURAL_VOICES,
    VOICE_PROFILES,
    VoiceProfile,
)
from .dsp import (
    AudioBuffer,
    DEFAULT_SAMPLE_RATE,
)
from .engine import (
    BaseVoiceEngine,
    EdgeTTSVoiceEngine,
    GeminiVoiceEngine,
    MockVoiceEngine,
    OpenAIVoiceEngine,
    get_voice_engine,
)
from .exporter import (
    AudioExporter,
)
from .parser import (
    Chapter,
    DocumentParser,
    ParsedDocument,
)
from .prosody import (
    ProsodyDirector,
)
from .stitcher import (
    AudioStitcher,
    ChapterTimepoint,
    StitchedAudioResult,
)

__version__ = "1.0.0"
__author__ = "Paul L. Bogen"
__license__ = "MIT"

__all__ = [
    "AudioFormat",
    "AudioBuffer",
    "AudioExporter",
    "AudioStitcher",
    "BaseVoiceEngine",
    "Chapter",
    "ChapterTimepoint",
    "ChunkType",
    "DEFAULT_SAMPLE_RATE",
    "DocumentParser",
    "EdgeTTSVoiceEngine",
    "GeminiVoiceEngine",
    "MockVoiceEngine",
    "NarrativeChunk",
    "NarrativeChunker",
    "OpenAIVoiceEngine",
    "PACING_PRESETS",
    "PacingConfig",
    "PacingMode",
    "ParsedDocument",
    "ProsodyDirector",
    "StitchedAudioResult",
    "VALID_NEURAL_VOICES",
    "VOICE_PROFILES",
    "VoiceProfile",
    "get_voice_engine",
]
