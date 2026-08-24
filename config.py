"""Configuration, voice profiles, pacing presets, and audio specs."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class PacingMode(str, Enum):
    """Pacing modulation presets for audio synthesis."""
    NORMAL = "normal"
    DRAMATIC = "dramatic"
    REFLECTIVE = "reflective"
    BRISK = "brisk"
    TECHNICAL = "technical"


class AudioFormat(str, Enum):
    """Supported audio container formats."""
    WAV = "wav"
    MP3 = "mp3"
    M4B = "m4b"
    AAC = "aac"
    FLAC = "flac"


@dataclass
class PacingConfig:
    """Pause durations and timing envelopes in milliseconds."""
    paragraph_pause_ms: int = 500
    sentence_pause_ms: int = 250
    dialogue_pause_ms: int = 180
    clause_pause_ms: int = 100
    chapter_pause_ms: int = 1200
    crossfade_ms: int = 30


@dataclass
class VoiceProfile:
    """Voice profile defining acoustic persona, neural voice mapping, and timing."""
    name: str
    voice: str
    description: str
    pacing_mode: PacingMode = PacingMode.NORMAL
    speed: float = 1.0
    pacing: PacingConfig = field(default_factory=PacingConfig)
    system_tone: Optional[str] = None
    character_voices: Dict[str, str] = field(default_factory=dict)


PACING_PRESETS: Dict[PacingMode, PacingConfig] = {
    PacingMode.NORMAL: PacingConfig(
        paragraph_pause_ms=450,
        sentence_pause_ms=220,
        dialogue_pause_ms=180,
        clause_pause_ms=90,
        chapter_pause_ms=1000,
        crossfade_ms=30,
    ),
    PacingMode.DRAMATIC: PacingConfig(
        paragraph_pause_ms=600,
        sentence_pause_ms=300,
        dialogue_pause_ms=150,
        clause_pause_ms=120,
        chapter_pause_ms=1500,
        crossfade_ms=35,
    ),
    PacingMode.REFLECTIVE: PacingConfig(
        paragraph_pause_ms=650,
        sentence_pause_ms=320,
        dialogue_pause_ms=220,
        clause_pause_ms=140,
        chapter_pause_ms=1600,
        crossfade_ms=40,
    ),
    PacingMode.BRISK: PacingConfig(
        paragraph_pause_ms=300,
        sentence_pause_ms=150,
        dialogue_pause_ms=120,
        clause_pause_ms=60,
        chapter_pause_ms=800,
        crossfade_ms=20,
    ),
    PacingMode.TECHNICAL: PacingConfig(
        paragraph_pause_ms=400,
        sentence_pause_ms=200,
        dialogue_pause_ms=160,
        clause_pause_ms=80,
        chapter_pause_ms=1100,
        crossfade_ms=25,
    ),
}


VOICE_PROFILES: Dict[str, VoiceProfile] = {
    "cyberpunk_noir": VoiceProfile(
        name="cyberpunk_noir",
        voice="Fenrir",
        description="Atmospheric, resonant, gritty narrative voice tuned for street-level cybernetics and urban sprawl.",
        pacing_mode=PacingMode.DRAMATIC,
        speed=0.98,
        pacing=PACING_PRESETS[PacingMode.DRAMATIC],
        system_tone="Grim, cinematic, noir delivery with measured cadence.",
        character_voices={
            "female": "Aoede",
            "male": "Puck",
            "narrator": "Fenrir",
        },
    ),
    "reflective_narrative": VoiceProfile(
        name="reflective_narrative",
        voice="Aoede",
        description="Contemplative, warm, lyrical voice ideal for memoirs, introspective literary fiction, and essayistic prose.",
        pacing_mode=PacingMode.REFLECTIVE,
        speed=0.95,
        pacing=PACING_PRESETS[PacingMode.REFLECTIVE],
        system_tone="Thoughtful, measured, lyrical vocal delivery.",
        character_voices={
            "female": "Aoede",
            "male": "Charon",
            "narrator": "Aoede",
        },
    ),
    "dramatic_fiction": VoiceProfile(
        name="dramatic_fiction",
        voice="Puck",
        description="Dynamic, expressive voice with intense emotional range and distinct dialogue cadence.",
        pacing_mode=PacingMode.DRAMATIC,
        speed=1.0,
        pacing=PACING_PRESETS[PacingMode.DRAMATIC],
        system_tone="High-contrast dynamic storytelling with expressive inflection.",
        character_voices={
            "female": "Kore",
            "male": "Puck",
            "narrator": "Puck",
        },
    ),
    "technical_expository": VoiceProfile(
        name="technical_expository",
        voice="Charon",
        description="Crisp, authoritative, analytical articulation designed for documentation, science, and technical manuals.",
        pacing_mode=PacingMode.TECHNICAL,
        speed=1.02,
        pacing=PACING_PRESETS[PacingMode.TECHNICAL],
        system_tone="Clear, neutral, authoritative technical instruction.",
        character_voices={
            "female": "Leda",
            "male": "Charon",
            "narrator": "Charon",
        },
    ),
    "balanced_neutral": VoiceProfile(
        name="balanced_neutral",
        voice="Kore",
        description="Natural, warm standard narration suitable for general fiction and non-fiction.",
        pacing_mode=PacingMode.NORMAL,
        speed=1.0,
        pacing=PACING_PRESETS[PacingMode.NORMAL],
        system_tone="Clean, engaging studio narration.",
        character_voices={
            "female": "Kore",
            "male": "Oran",
            "narrator": "Kore",
        },
    ),
}

# Supported Gemini neural voices
VALID_NEURAL_VOICES = {
    "Kore",
    "Charon",
    "Fenrir",
    "Puck",
    "Leda",
    "Oran",
    "Zephyr",
    "Aoede",
}

# Standard audio hardware specs
SAMPLE_RATE_24K = 24000
SAMPLE_RATE_44K = 44100
SAMPLE_RATE_48K = 48000
DEFAULT_SAMPLE_RATE = SAMPLE_RATE_24K
DEFAULT_SAMPLE_WIDTH = 2  # 16-bit PCM (2 bytes per sample)
DEFAULT_CHANNELS = 1     # Mono
