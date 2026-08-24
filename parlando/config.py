"""Global configuration, voice decks, and pacing profile presets for Parlando."""

import dataclasses
from enum import Enum
from typing import Dict, List, Optional


DEFAULT_SAMPLE_RATE = 24000
DEFAULT_BIT_DEPTH = 16
DEFAULT_CHANNELS = 1  # Mono for speech synthesis


class AudioFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    M4B = "m4b"
    AAC = "aac"


class PacingMode(str, Enum):
    NORMAL = "normal"
    BRISK = "brisk"
    DRAMATIC = "dramatic"
    CINEMATIC = "cinematic"
    CONTEMPLATIVE = "contemplative"


@dataclasses.dataclass
class PacingConfig:
    """Micro-pause envelopes in milliseconds."""
    sentence_pause_ms: int = 220
    comma_pause_ms: int = 75
    semicolon_pause_ms: int = 140
    colon_pause_ms: int = 150
    dash_pause_ms: int = 320
    ellipsis_pause_ms: int = 370
    paragraph_pause_ms: int = 650
    dialogue_turnaround_ms: int = 400
    chapter_pause_ms: int = 1200
    speed_multiplier: float = 1.0


PACING_PRESETS: Dict[PacingMode, PacingConfig] = {
    PacingMode.NORMAL: PacingConfig(
        sentence_pause_ms=220,
        comma_pause_ms=75,
        semicolon_pause_ms=140,
        colon_pause_ms=150,
        dash_pause_ms=320,
        ellipsis_pause_ms=370,
        paragraph_pause_ms=650,
        dialogue_turnaround_ms=400,
        chapter_pause_ms=1200,
        speed_multiplier=1.0,
    ),
    PacingMode.BRISK: PacingConfig(
        sentence_pause_ms=160,
        comma_pause_ms=50,
        semicolon_pause_ms=100,
        colon_pause_ms=110,
        dash_pause_ms=220,
        ellipsis_pause_ms=280,
        paragraph_pause_ms=450,
        dialogue_turnaround_ms=280,
        chapter_pause_ms=800,
        speed_multiplier=1.10,
    ),
    PacingMode.DRAMATIC: PacingConfig(
        sentence_pause_ms=280,
        comma_pause_ms=90,
        semicolon_pause_ms=180,
        colon_pause_ms=200,
        dash_pause_ms=400,
        ellipsis_pause_ms=500,
        paragraph_pause_ms=800,
        dialogue_turnaround_ms=500,
        chapter_pause_ms=1500,
        speed_multiplier=0.95,
    ),
    PacingMode.CINEMATIC: PacingConfig(
        sentence_pause_ms=320,
        comma_pause_ms=100,
        semicolon_pause_ms=200,
        colon_pause_ms=220,
        dash_pause_ms=450,
        ellipsis_pause_ms=550,
        paragraph_pause_ms=900,
        dialogue_turnaround_ms=550,
        chapter_pause_ms=1800,
        speed_multiplier=0.92,
    ),
    PacingMode.CONTEMPLATIVE: PacingConfig(
        sentence_pause_ms=380,
        comma_pause_ms=120,
        semicolon_pause_ms=220,
        colon_pause_ms=250,
        dash_pause_ms=500,
        ellipsis_pause_ms=650,
        paragraph_pause_ms=1100,
        dialogue_turnaround_ms=650,
        chapter_pause_ms=2200,
        speed_multiplier=0.88,
    ),
}


@dataclasses.dataclass
class VoiceProfile:
    name: str
    primary_voice: str
    secondary_voices: Dict[str, str] = dataclasses.field(default_factory=dict)
    default_pacing: PacingMode = PacingMode.NORMAL
    pitch_offset: str = "+0Hz"
    rate_offset: str = "+0%"
    volume_offset: str = "+0%"


VOICE_PROFILES: Dict[str, VoiceProfile] = {
    "cyberpunk_noir": VoiceProfile(
        name="cyberpunk_noir",
        primary_voice="en-US-ChristopherNeural",
        secondary_voices={"male": "en-US-GuyNeural", "female": "en-US-JennyNeural"},
        default_pacing=PacingMode.DRAMATIC,
        rate_offset="+0%",
    ),
    "space_opera": VoiceProfile(
        name="space_opera",
        primary_voice="en-GB-RyanNeural",
        secondary_voices={"male": "en-US-ChristopherNeural", "female": "en-GB-SoniaNeural"},
        default_pacing=PacingMode.CINEMATIC,
        rate_offset="-2%",
    ),
    "classic_fiction": VoiceProfile(
        name="classic_fiction",
        primary_voice="en-GB-SoniaNeural",
        secondary_voices={"male": "en-GB-RyanNeural", "female": "en-US-JennyNeural"},
        default_pacing=PacingMode.NORMAL,
        rate_offset="+0%",
    ),
}

VALID_NEURAL_VOICES = [
    "en-US-ChristopherNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-AriaNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "Fenrir", "Aoede", "Puck", "Charon", "Kore", "Leda",
    "alloy", "echo", "fable", "onyx", "nova", "shimmer"
]
