"""Parlando Pluggable Neural Voice Engine Subsystem."""

from .base import BaseVoiceEngine, VoiceEngineError
from .edge import EdgeTTSVoiceEngine
from .openai import OpenAIVoiceEngine
from .gemini import GeminiVoiceEngine
from .mock import MockVoiceEngine


def get_voice_engine(backend: str = "edge", **kwargs) -> BaseVoiceEngine:
    backend_clean = (backend or "edge").lower().strip()
    if backend_clean in ("edge", "edge-tts", "edgetts"):
        return EdgeTTSVoiceEngine(**kwargs)
    elif backend_clean in ("openai", "oai"):
        return OpenAIVoiceEngine(**kwargs)
    elif backend_clean in ("gemini", "google"):
        return GeminiVoiceEngine(**kwargs)
    elif backend_clean in ("mock", "test", "synthetic"):
        return MockVoiceEngine(**kwargs)
    else:
        raise ValueError(f"Unknown voice backend: {backend}. Supported: edge, openai, gemini, mock.")


__all__ = [
    "BaseVoiceEngine",
    "EdgeTTSVoiceEngine",
    "GeminiVoiceEngine",
    "MockVoiceEngine",
    "OpenAIVoiceEngine",
    "VoiceEngineError",
    "get_voice_engine",
]
