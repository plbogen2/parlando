"""Generic, Multi-Cast Speaker Detection, Dialogue Attribution, and Conflict-Free Voice Allocation."""

import dataclasses
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from .chunker import ChunkType, NarrativeChunk


@dataclasses.dataclass
class CharacterProfile:
    name: str
    gender: str = "unknown"  # "male", "female", "neutral", "unknown"
    line_count: int = 0
    assigned_voice: Optional[str] = None
    interacts_with: Set[str] = dataclasses.field(default_factory=set)
    aliases: Set[str] = dataclasses.field(default_factory=set)


def normalize_character_input(
    cast_input: Optional[Union[Dict[str, Any], List[Any], str]] = None
) -> Dict[str, CharacterProfile]:
    """Parses and normalizes user-provided character definitions into CharacterProfile objects.

    Supported formats:
      - Dict[str, CharacterProfile]
      - Dict[str, Dict[str, Any]]: e.g. {"Case": {"gender": "male", "voice": "Puck"}}
      - Dict[str, str]: e.g. {"Case": "male", "Linda Lee": "female"} or {"Case": "Puck"}
      - List[CharacterProfile | Dict | str]: e.g. ["Case:male:Puck", "Linda Lee:female:Aoede", "Clerk:male"]
      - JSON string or path to a .json file
    """
    if not cast_input:
        return {}

    # If file path
    if isinstance(cast_input, str) and os.path.isfile(cast_input):
        with open(cast_input, "r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_character_input(data)

    # If JSON string
    if isinstance(cast_input, str) and (cast_input.strip().startswith("{") or cast_input.strip().startswith("[")):
        try:
            data = json.loads(cast_input)
            return normalize_character_input(data)
        except Exception:
            pass

    # If comma-separated string like "Case:male:Puck, Linda Lee:female"
    if isinstance(cast_input, str):
        items = [item.strip() for item in cast_input.split(",") if item.strip()]
        return normalize_character_input(items)

    result: Dict[str, CharacterProfile] = {}

    # If list of items
    if isinstance(cast_input, (list, tuple)):
        for item in cast_input:
            if isinstance(item, CharacterProfile):
                result[item.name] = item
            elif isinstance(item, dict):
                name = item.get("name")
                if name:
                    gender = item.get("gender", "unknown").lower()
                    voice = item.get("voice") or item.get("assigned_voice")
                    aliases = set(item.get("aliases", []))
                    result[name] = CharacterProfile(
                        name=name,
                        gender=gender,
                        assigned_voice=voice,
                        aliases=aliases,
                    )
            elif isinstance(item, str):
                # Parse format: "Name:gender:voice" or "Name:gender" or "Name:voice"
                parts = [p.strip() for p in item.split(":")]
                if parts:
                    name = parts[0]
                    gender = "unknown"
                    voice = None
                    if len(parts) >= 2:
                        val2 = parts[1].lower()
                        if val2 in ("male", "female", "neutral", "unknown", "m", "f", "n"):
                            g_map = {"m": "male", "f": "female", "n": "neutral"}
                            gender = g_map.get(val2, val2)
                        else:
                            voice = parts[1]
                    if len(parts) >= 3:
                        voice = parts[2]
                    result[name] = CharacterProfile(name=name, gender=gender, assigned_voice=voice)
        return result

    # If dict mapping name -> definition
    if isinstance(cast_input, dict):
        for k, v in cast_input.items():
            if isinstance(v, CharacterProfile):
                result[k] = v
            elif isinstance(v, dict):
                gender = v.get("gender", "unknown").lower()
                voice = v.get("voice") or v.get("assigned_voice")
                aliases = set(v.get("aliases", []))
                result[k] = CharacterProfile(name=k, gender=gender, assigned_voice=voice, aliases=aliases)
            elif isinstance(v, str):
                v_lower = v.lower().strip()
                if v_lower in ("male", "female", "neutral", "unknown", "m", "f", "n"):
                    g_map = {"m": "male", "f": "female", "n": "neutral"}
                    gender = g_map.get(v_lower, v_lower)
                    result[k] = CharacterProfile(name=k, gender=gender)
                else:
                    # Treat as voice name
                    result[k] = CharacterProfile(name=k, assigned_voice=v)
            else:
                result[k] = CharacterProfile(name=k)

    return result


class GenericSpeakerDetector:
    """Deterministic, syntax-driven speaker attribution and pronoun resolution engine."""

    SPEECH_VERBS = {
        "said", "says", "saying", "whispered", "whispers", "muttered", "mutters",
        "asked", "asks", "shouted", "shouts", "rasped", "rasps", "replied", "replies",
        "exclaimed", "exclaims", "grunted", "grunts", "groaned", "groans", "laughed", "laughs",
        "called", "calls", "demanded", "demands", "agreed", "agrees", "added", "adds",
        "mused", "muses", "murmured", "murmurs", "barked", "barks", "snarled", "snarls",
        "chuckled", "chuckles", "hissed", "hisses", "snapped", "snaps", "breathed", "breathes",
        "inquired", "inquires", "yelled", "yells", "screamed", "screams", "sighed", "sighs",
        "remarked", "remarks", "commented", "comments", "insisted", "insists", "observed", "observes",
        "echoed", "echoes", "protested", "protests", "warned", "warns", "threatened", "threatens",
        "ordered", "orders", "begged", "begs", "implored", "implores", "gasped", "gasps",
    }

    MALE_TITLES = {"mr", "mister", "lord", "sir", "father", "brother", "son", "king", "prince", "guy", "fellow", "he", "him", "his"}
    FEMALE_TITLES = {"ms", "miss", "mrs", "missus", "lady", "madam", "mother", "sister", "daughter", "queen", "princess", "she", "her", "hers"}

    STOP_WORDS = {
        "the", "a", "an", "then", "and", "but", "so", "as", "when", "while", "after", "before",
        "with", "at", "by", "from", "into", "through", "suddenly", "quietly", "slowly", "finally",
        "chapter", "you", "youre", "your", "they", "we", "it", "its", "what", "how", "why", "where",
        "below", "above", "behind", "inside", "outside", "near", "against", "not", "ten"
    }

    def __init__(self, predefined_characters: Optional[Union[Dict[str, Any], List[Any], str]] = None):
        self.characters: Dict[str, CharacterProfile] = {}
        self.predefined = normalize_character_input(predefined_characters)
        # Pre-seed characters with user configurations
        for name, profile in self.predefined.items():
            self.characters[name] = dataclasses.replace(profile)

        self.last_speakers: List[str] = []
        self.active_male_speaker: Optional[str] = None
        self.active_female_speaker: Optional[str] = None
        self.recent_proper_names: List[str] = []

        # If predefined characters have known genders, initialize active speakers
        for name, profile in self.characters.items():
            if profile.gender == "female" and not self.active_female_speaker:
                self.active_female_speaker = name
            elif profile.gender == "male" and not self.active_male_speaker:
                self.active_male_speaker = name

    def attribute_chunks(self, chunks: List[NarrativeChunk]) -> List[NarrativeChunk]:
        """Attributes speakers to all dialogue chunks and tracks character conversation graphs."""
        for i, chunk in enumerate(chunks):
            if chunk.chunk_type in (ChunkType.NARRATION, ChunkType.HEADING):
                self._update_subject_context(chunk.text)
                continue

            if chunk.chunk_type == ChunkType.DIALOGUE:
                speaker, gender = self._detect_speaker_for_dialogue(chunks, i)
                chunk.character = speaker
                chunk.gender = gender

                if speaker and speaker != "Unknown Speaker":
                    if speaker not in self.characters:
                        self.characters[speaker] = CharacterProfile(name=speaker, gender=gender)
                    self.characters[speaker].line_count += 1

                    if gender != "unknown" and self.characters[speaker].gender == "unknown":
                        self.characters[speaker].gender = gender

                    if gender == "female":
                        self.active_female_speaker = speaker
                    elif gender == "male":
                        self.active_male_speaker = speaker

                    # Track co-occurrence in conversation
                    if self.last_speakers and self.last_speakers[-1] != speaker:
                        prev = self.last_speakers[-1]
                        self.characters[speaker].interacts_with.add(prev)
                        if prev in self.characters:
                            self.characters[prev].interacts_with.add(speaker)

                    if not self.last_speakers or self.last_speakers[-1] != speaker:
                        self.last_speakers.append(speaker)
                        if len(self.last_speakers) > 8:
                            self.last_speakers.pop(0)

        return chunks

    def _update_subject_context(self, text: str):
        """Scans narration for named entities and tracks recent subjects."""
        clean = re.sub(r'[\'’"]', '', text)
        words = clean.split()
        for i, raw_w in enumerate(words):
            w = re.sub(r'[^\w]', '', raw_w)
            if w.istitle() and w.lower() not in self.STOP_WORDS:
                # Check for 2-word names: "Linda Lee"
                if i + 1 < len(words):
                    w2 = re.sub(r'[^\w]', '', words[i + 1])
                    if w2.istitle() and w2.lower() not in self.STOP_WORDS:
                        full_name = f"{w} {w2}"
                    else:
                        full_name = w
                else:
                    full_name = w

                # Match against predefined character aliases or canonical names
                canonical_name = self._find_matching_predefined_name(full_name) or full_name

                if canonical_name not in self.recent_proper_names:
                    self.recent_proper_names.append(canonical_name)
                    if len(self.recent_proper_names) > 10:
                        self.recent_proper_names.pop(0)

    def _find_matching_predefined_name(self, candidate: str) -> Optional[str]:
        cand_lower = candidate.lower().strip()
        for name, profile in self.characters.items():
            if name.lower() == cand_lower:
                return name
            if any(alias.lower() == cand_lower for alias in profile.aliases):
                return name
            # Sub-match for first names (e.g. candidate "Linda" matches predefined "Linda Lee")
            if " " in name and name.split()[0].lower() == cand_lower:
                return name
        return None

    def _detect_speaker_for_dialogue(self, chunks: List[NarrativeChunk], idx: int) -> Tuple[str, str]:
        # 1. Check surrounding narration
        post_narration = chunks[idx + 1].text if idx + 1 < len(chunks) and chunks[idx + 1].chunk_type == ChunkType.NARRATION else ""
        pre_narration = chunks[idx - 1].text if idx - 1 >= 0 and chunks[idx - 1].chunk_type == ChunkType.NARRATION else ""

        # Check Post-Dialogue Speech Tag (e.g. "Case said,", "...the clerk rasped", "...she whispered")
        if post_narration:
            speaker, gender = self._extract_speech_tag(post_narration, is_post=True)
            if speaker:
                return speaker, gender

        # Check Pre-Dialogue Action Beat / Speech Tag (e.g. "Linda Lee looked at him...", "Marcus entered the room...")
        if pre_narration:
            speaker, gender = self._extract_speech_tag(pre_narration, is_post=False)
            if speaker:
                return speaker, gender

        # 2. Conversational Alternation Fallback (for rapid back-and-forth dialogue)
        if len(self.last_speakers) >= 2:
            speaker_a = self.last_speakers[-1]
            speaker_b = self.last_speakers[-2]
            if speaker_a != speaker_b:
                next_speaker = speaker_b
                gender = self.characters.get(next_speaker, CharacterProfile(name=next_speaker)).gender
                return next_speaker, gender

        # 3. Last Active Speaker Fallback
        if self.last_speakers:
            s = self.last_speakers[-1]
            return s, self.characters.get(s, CharacterProfile(name=s)).gender

        # If predefined characters exist and only one of each gender, fall back gracefully
        if len(self.characters) == 1:
            name = next(iter(self.characters.keys()))
            return name, self.characters[name].gender

        return "Unknown Speaker", "unknown"

    def _extract_speech_tag(self, text: str, is_post: bool = True) -> Tuple[Optional[str], str]:
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if not sentences:
            return None, "unknown"

        target_sentence = sentences[0] if is_post else sentences[-1]
        verb_pattern = r"\b(" + "|".join(self.SPEECH_VERBS) + r")\b"
        match = re.search(verb_pattern, target_sentence, re.IGNORECASE)

        if match:
            v_start = match.start()
            pre_verb = target_sentence[:v_start].strip()
            post_verb = target_sentence[match.end():].strip()

            candidate = pre_verb if pre_verb else post_verb
            candidate = re.sub(r'^(and|as|then|while|with)\s+', '', candidate, flags=re.I).strip()
            candidate = candidate.split(",")[0].strip()

            if candidate:
                return self._resolve_subject_string(candidate, target_sentence)

        # Pre-dialogue sentence without speech verb (e.g. "Linda Lee looked at him through the smoky violet haze of the bar")
        words = target_sentence.split()
        for i, raw_w in enumerate(words):
            w = re.sub(r'[^\w]', '', raw_w)
            if w.istitle() and w.lower() not in self.STOP_WORDS:
                if i + 1 < len(words):
                    w2 = re.sub(r'[^\w]', '', words[i + 1])
                    if w2.istitle() and w2.lower() not in self.STOP_WORDS:
                        full_name = f"{w} {w2}"
                    else:
                        full_name = w
                else:
                    full_name = w

                matched = self._find_matching_predefined_name(full_name) or full_name
                gender = self._infer_gender(matched, target_sentence)
                return matched, gender

        return None, "unknown"

    def _resolve_subject_string(self, candidate: str, full_sentence: str) -> Tuple[str, str]:
        cand_lower = candidate.lower().split()
        if not cand_lower:
            return "Unknown Speaker", "unknown"

        first_word = cand_lower[0]

        # Pronoun Resolution
        if first_word in ("she", "her", "herself"):
            name = self.active_female_speaker or self._find_recent_proper_name(exclude_male=True) or "Female Speaker"
            self.active_female_speaker = name
            return name, "female"

        if first_word in ("he", "him", "himself"):
            name = self.active_male_speaker or self._find_recent_proper_name(exclude_female=True) or "Male Speaker"
            self.active_male_speaker = name
            return name, "male"

        if first_word in ("they", "someone"):
            return "Speaker", "neutral"

        # Check against predefined characters
        clean_name = re.sub(r'[^\w\s]', '', candidate).strip()
        matched = self._find_matching_predefined_name(clean_name)

        if matched:
            gender = self.characters[matched].gender
            if gender == "unknown":
                gender = self._infer_gender(matched, full_sentence)
                self.characters[matched].gender = gender
            if gender == "male":
                self.active_male_speaker = matched
            elif gender == "female":
                self.active_female_speaker = matched
            return matched, gender

        name_title = clean_name.title()
        gender = self._infer_gender(name_title, full_sentence)

        if gender == "male":
            self.active_male_speaker = name_title
        elif gender == "female":
            self.active_female_speaker = name_title

        return name_title, gender

    def _find_recent_proper_name(self, exclude_male: bool = False, exclude_female: bool = False) -> Optional[str]:
        for name in reversed(self.recent_proper_names):
            if name in self.characters:
                char_gender = self.characters[name].gender
                if exclude_male and char_gender == "male":
                    continue
                if exclude_female and char_gender == "female":
                    continue
                return name
            return name
        return None

    def _infer_gender(self, name: str, context: str) -> str:
        # Check if already known in self.characters
        if name in self.characters and self.characters[name].gender != "unknown":
            return self.characters[name].gender

        name_lower = name.lower()
        context_lower = context.lower()

        # Check explicit female indicators
        if any(w in self.FEMALE_TITLES for w in name_lower.split()):
            return "female"
        # Common female names
        if any(fn in name_lower for fn in ["linda", "mary", "sarah", "elena", "alice", "jane", "anna", "eva", "claire", "kate", "molly"]):
            return "female"

        # Check explicit male indicators
        if any(w in self.MALE_TITLES for w in name_lower.split()):
            return "male"
        # Common male names / descriptors
        if any(mn in name_lower for mn in ["case", "john", "marcus", "david", "charlie", "bob", "alex", "peter", "clerk", "bartender", "doctor", "armitage", "wintermute", "riviera"]):
            return "male"

        if any(re.search(rf"\b{f}\b", context_lower) for f in ["she", "her", "hers"]):
            return "female"
        if any(re.search(rf"\b{m}\b", context_lower) for m in ["he", "him", "his"]):
            return "male"

        return "unknown"


class SceneAwareVoiceCaster:
    """Allocates voices to characters ensuring conversational partners never share the same voice."""

    GEMINI_POOLS = {
        "narrator": "Fenrir",
        "male": ["Puck", "Charon", "Oran", "Zephyr"],
        "female": ["Aoede", "Kore", "Leda"],
        "neutral": ["Puck", "Charon", "Aoede", "Kore"],
    }

    EDGE_POOLS = {
        "narrator": "en-US-ChristopherNeural",
        "male": ["en-US-GuyNeural", "en-US-EricNeural", "en-GB-RyanNeural", "en-US-RogerNeural"],
        "female": ["en-US-JennyNeural", "en-US-AriaNeural", "en-GB-SoniaNeural"],
        "neutral": ["en-US-GuyNeural", "en-US-JennyNeural"],
    }

    @classmethod
    def cast_characters(
        cls,
        characters: Dict[str, CharacterProfile],
        engine_type: str = "gemini",
        primary_narrator_voice: Optional[str] = None
    ) -> Dict[str, str]:
        """Graph-colored casting: assigns voices such that characters in conversation have different voices.

        Preserves any user pre-assigned voices and guarantees a single consistent narrator voice.
        """
        pools = cls.GEMINI_POOLS if engine_type.lower() == "gemini" else cls.EDGE_POOLS
        narrator_voice = primary_narrator_voice or pools["narrator"]

        voice_map: Dict[str, str] = {
            "Narrator": narrator_voice,
            "heading": narrator_voice,
            "section_break": narrator_voice,
        }

        male_pool = list(pools["male"])
        female_pool = list(pools["female"])
        neutral_pool = list(pools["neutral"])

        # 1. Lock in any explicit user-specified pre-assigned voices first
        for char in characters.values():
            if char.assigned_voice:
                voice_map[char.name] = char.assigned_voice

        # 2. Sort remaining characters by line count (major characters get assigned first)
        sorted_chars = sorted(characters.values(), key=lambda c: c.line_count, reverse=True)

        for char in sorted_chars:
            if char.name in voice_map:
                continue

            # Find voices already used by characters this character interacts with
            conflicting_voices = {
                characters[peer].assigned_voice
                for peer in char.interacts_with
                if peer in characters and characters[peer].assigned_voice
            }

            # Select appropriate pool by gender
            if char.gender == "female":
                candidate_pool = female_pool
            elif char.gender == "male":
                candidate_pool = male_pool
            else:
                candidate_pool = neutral_pool

            # Pick first voice not currently used by a conversation partner
            chosen_voice = None
            for v in candidate_pool:
                if v not in conflicting_voices:
                    chosen_voice = v
                    break

            # If all voices in candidate pool conflict, pick first available
            if not chosen_voice:
                chosen_voice = candidate_pool[0]

            voice_map[char.name] = chosen_voice
            char.assigned_voice = chosen_voice

        return voice_map
