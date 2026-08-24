"""Contraction-Safe Prosody Markup, Pronunciation Normalization, and Voice Allocation."""

import dataclasses
import re
from typing import Dict, List, Optional
from .chunker import ChunkType, NarrativeChunk
from parlando.config import PacingConfig, VoiceProfile


@dataclasses.dataclass
class ProsodyMarkup:
    raw_text: str
    clean_text: str
    ssml_rate: str
    ssml_pitch: str
    voice_name: str
    pause_before_ms: int
    pause_after_ms: int


class ProsodyDirector:
    """Calculates vocal delivery, pace modulation, and text normalization."""

    CONTRACTION_MAP = {
        r"\bwon't\b": "won't",
        r"\bcan't\b": "can't",
        r"\bshan't\b": "shan't",
        r"\blet's\b": "let's",
    }

    EXPANSION_RULES = [
        (r'\bMr\.\s+', 'Mister '),
        (r'\bMrs\.\s+', 'Missus '),
        (r'\bMs\.\s+', 'Miz '),
        (r'\bDr\.\s+', 'Doctor '),
        (r'\bProf\.\s+', 'Professor '),
        (r'\bSt\.\s+', 'Saint '),
        (r'\bGen\.\s+', 'General '),
        (r'\bCol\.\s+', 'Colonel '),
        (r'\bCapt\.\s+', 'Captain '),
        (r'\bLt\.\s+', 'Lieutenant '),
        (r'\bSgt\.\s+', 'Sergeant '),
        (r'\b([12][0-9]{3})s\b', r'\1s'),
    ]

    def __init__(self, voice_profile: Optional[VoiceProfile] = None, pacing: Optional[PacingConfig] = None):
        self.profile = voice_profile or VoiceProfile(name="default", primary_voice="en-US-ChristopherNeural")
        self.pacing = pacing or PacingConfig()

    def process_chunk(self, chunk: NarrativeChunk, dialogue_voice_override: Optional[str] = None) -> ProsodyMarkup:
        normalized_text = self.normalize_text(chunk.text)
        assigned_voice = self._allocate_voice(chunk, dialogue_voice_override)

        speed_offset_pct = 0
        if self.pacing and self.pacing.speed_multiplier != 1.0:
            speed_offset_pct = int(round((self.pacing.speed_multiplier - 1.0) * 100))

        if chunk.chunk_type == ChunkType.HEADING:
            rate_val = -4 + speed_offset_pct
            pitch = "-1Hz"
        elif chunk.chunk_type == ChunkType.DIALOGUE:
            rate_val = 2 + speed_offset_pct
            pitch = "+1Hz" if chunk.gender == "female" else "+0Hz"
        else:
            base_offset = int(self.profile.rate_offset.replace("%", "").replace("+", "")) if self.profile.rate_offset else 0
            rate_val = base_offset + speed_offset_pct
            pitch = self.profile.pitch_offset

        rate = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"

        return ProsodyMarkup(
            raw_text=chunk.text,
            clean_text=normalized_text,
            ssml_rate=rate,
            ssml_pitch=pitch,
            voice_name=assigned_voice,
            pause_before_ms=chunk.pause_before_ms,
            pause_after_ms=chunk.pause_after_ms,
        )

    def normalize_text(self, text: str) -> str:
        s = text
        for pat, repl in self.EXPANSION_RULES:
            s = re.sub(pat, repl, s)

        s = re.sub(r'(?<=\d),(?=\d{3}\b)', '', s)
        s = re.sub(r'—', ' -- ', s)
        s = re.sub(r'–', ' - ', s)
        s = re.sub(r'\.{3,}', '...', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _allocate_voice(self, chunk: NarrativeChunk, dialogue_voice_override: Optional[str] = None) -> str:
        if chunk.chunk_type == ChunkType.DIALOGUE:
            if dialogue_voice_override:
                return dialogue_voice_override
            if chunk.gender and chunk.gender in self.profile.secondary_voices:
                return self.profile.secondary_voices[chunk.gender]
            if "female" in self.profile.secondary_voices and chunk.gender == "female":
                return self.profile.secondary_voices["female"]
            if "male" in self.profile.secondary_voices and chunk.gender == "male":
                return self.profile.secondary_voices["male"]

        return self.profile.primary_voice
