"""Prosody direction, phonetic conditioning, and vocal profile assignment."""

import re
from typing import List, Optional
from .chunker import ChunkType, NarrativeChunk
from .config import VoiceProfile, PACING_PRESETS


class ProsodyDirector:
    """Controls vocal inflection, dialogue voice mapping, and phonetic conditioning."""

    def __init__(self, profile: VoiceProfile):
        self.profile = profile

    def process_chunks(self, chunks: List[NarrativeChunk]) -> List[NarrativeChunk]:
        """Apply voice allocation, prosody conditioning, and phonetic expansions."""
        processed: List[NarrativeChunk] = []

        for chunk in chunks:
            # Skip empty section breaks for audio synthesis
            if chunk.chunk_type == ChunkType.SECTION_BREAK:
                processed.append(chunk)
                continue

            # Voice assignment based on profile and character mapping
            assigned_voice = self._resolve_voice(chunk)
            
            # Phonetic and prosodic text conditioning
            conditioned_text = self._condition_text_for_speech(chunk.text, chunk.chunk_type)

            # Build SSML representation if SSML synthesis is enabled
            ssml = self._generate_ssml(conditioned_text, chunk)

            chunk.voice_override = assigned_voice
            chunk.text = conditioned_text
            chunk.prompt_directive = self._build_directive(chunk)
            chunk.metadata["ssml"] = ssml
            
            processed.append(chunk)

        return processed

    def _resolve_voice(self, chunk: NarrativeChunk) -> str:
        """Select appropriate neural voice according to speaker and profile."""
        if chunk.voice_override:
            return chunk.voice_override

        if chunk.chunk_type == ChunkType.DIALOGUE:
            if chunk.gender_hint == "female" and "female" in self.profile.character_voices:
                return self.profile.character_voices["female"]
            elif chunk.gender_hint == "male" and "male" in self.profile.character_voices:
                return self.profile.character_voices["male"]
        
        return self.profile.voice

    def _condition_text_for_speech(self, text: str, chunk_type: ChunkType) -> str:
        """Expand numbers, acronyms, and format punctuation for optimal neural prosody."""
        s = text

        # Expand common abbreviations
        abbr_map = {
            r"\bMr\.(?=\s|$)": "Mister",
            r"\bMrs\.(?=\s|$)": "Missus",
            r"\bMs\.(?=\s|$)": "Mizz",
            r"\bDr\.(?=\s|$)": "Doctor",
            r"\bProf\.(?=\s|$)": "Professor",
            r"\bSt\.(?=\s|$)": "Saint",
            r"\bvs\.(?=\s|$)": "versus",
            r"\betc\.(?=\s|$)": "et cetera",
            r"\be\.g\.(?=\s|$)": "for example",
            r"\bi\.e\.(?=\s|$)": "that is",
        }
        for pattern, repl in abbr_map.items():
            s = re.sub(pattern, repl, s)

        # Expand four-digit years (1900-2099) if standalone: e.g. 2026 -> twenty twenty-six
        s = re.sub(r"\b(19|20)(\d{2})\b", self._expand_year, s)

        # Expand standalone numbers under 100 to words for smoother natural speech
        s = re.sub(r"\b\d+\b", self._expand_number, s)

        # Smooth out dialogue punctuation (prevent hard unnatural pauses at quotes)
        s = s.replace('"', '').replace("'", "'")

        # Em-dashes: replace with a spaced comma or dash for subtle pause
        s = s.replace("—", " — ")

        return s.strip()

    def _expand_year(self, match: re.Match) -> str:
        """Convert a 4-digit year into verbal syllables."""
        century = int(match.group(1))
        decade = int(match.group(2))
        
        words_tens = {
            19: "nineteen",
            20: "twenty",
        }
        cent_str = words_tens.get(century, str(century))
        
        if decade == 0:
            return f"{cent_str} hundred"
        elif decade < 10:
            return f"{cent_str} oh-{self._number_to_word(decade)}"
        else:
            return f"{cent_str} {self._number_to_word(decade)}"

    def _expand_number(self, match: re.Match) -> str:
        """Expand small integers to written English words."""
        num_str = match.group(0)
        try:
            val = int(num_str)
            if 0 <= val <= 20:
                return self._number_to_word(val)
        except ValueError:
            pass
        return num_str

    def _number_to_word(self, n: int) -> str:
        """Translate single/double digit numbers to English words."""
        units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                 "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
        if 0 <= n <= 20:
            return units[n]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
        if 21 <= n < 100:
            t = tens[n // 10]
            u = units[n % 10] if (n % 10) != 0 else ""
            return f"{t}-{u}" if u else t
        return str(n)

    def _generate_ssml(self, text: str, chunk: NarrativeChunk) -> str:
        """Generate SSML markup with fine-grained prosody and break tags."""
        pause_sec = chunk.pause_after_ms / 1000.0
        return f'<speak><p><s>{text}</s></p><break time="{pause_sec:.2f}s"/></speak>'

    def _build_directive(self, chunk: NarrativeChunk) -> str:
        """Construct prompt directive for neural guidance."""
        base_tone = self.profile.system_tone or "Studio audiobook narration."
        if chunk.chunk_type == ChunkType.DIALOGUE:
            return f"{base_tone} Deliver dialogue with organic emotion, authentic character cadence, and conversational presence."
        elif chunk.chunk_type == ChunkType.HEADING:
            return f"{base_tone} Announce chapter title clearly with authority."
        else:
            return f"{base_tone} Fluid, immersive exposition."
