"""Parlando - Studio-Grade Neural Prose & Audiobook Synthesis Engine."""

from .config import (
    AudioFormat,
    PACING_PRESETS,
    PacingConfig,
    PacingMode,
    VALID_NEURAL_VOICES,
    VOICE_PROFILES,
    VoiceProfile,
)
from .core import (
    AudioBuffer,
    AudioStitcher,
    ChapterTimepoint,
    ChunkType,
    NarrativeChunk,
    NarrativeChunker,
    ProsodyDirector,
    ProsodyMarkup,
    StitchedAudioResult,
)
from .engines import (
    BaseVoiceEngine,
    EdgeTTSVoiceEngine,
    GeminiVoiceEngine,
    MockVoiceEngine,
    OpenAIVoiceEngine,
    VoiceEngineError,
    get_voice_engine,
)
from .export import (
    AudioExporter,
    HTMLPlayerGenerator,
)
from .parsers import (
    Chapter,
    DocumentParser,
    ParsedDocument,
)
from .pipeline import (
    AudiobookPipeline,
    PipelineConfig,
    PipelineResult,
)
from .web import (
    AudiobookWebHandler,
    start_web_studio,
)

__version__ = "1.0.0"
__author__ = "Dr. Paul Logasa Bogen II"
__license__ = "MIT"

__all__ = [
    "AudioBuffer",
    "AudioExporter",
    "AudioFormat",
    "AudioStitcher",
    "AudiobookPipeline",
    "AudiobookWebHandler",
    "BaseVoiceEngine",
    "Chapter",
    "ChapterTimepoint",
    "ChunkType",
    "DocumentParser",
    "EdgeTTSVoiceEngine",
    "GeminiVoiceEngine",
    "HTMLPlayerGenerator",
    "MockVoiceEngine",
    "NarrativeChunk",
    "NarrativeChunker",
    "OpenAIVoiceEngine",
    "PACING_PRESETS",
    "PacingConfig",
    "PacingMode",
    "ParsedDocument",
    "PipelineConfig",
    "PipelineResult",
    "ProsodyDirector",
    "ProsodyMarkup",
    "StitchedAudioResult",
    "VALID_NEURAL_VOICES",
    "VOICE_PROFILES",
    "VoiceEngineError",
    "VoiceProfile",
    "get_voice_engine",
    "start_web_studio",
]
