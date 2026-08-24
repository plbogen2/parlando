"""Intelligent narrative chunking and dialogue segmentation engine."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from .config import PacingConfig, PacingMode, PACING_PRESETS


class ChunkType(str, Enum):
    """Semantic type of narrative audio chunk."""
    HEADING = "heading"
    EXPOSITION = "exposition"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    SECTION_BREAK = "section_break"


@dataclass
class NarrativeChunk:
    """Atomic narrative speech block for neural synthesis."""
    index: int
    text: str
    chunk_type: ChunkType = ChunkType.EXPOSITION
    speaker: str = "narrator"
    gender_hint: Optional[str] = None
    pause_after_ms: int = 250
    voice_override: Optional[str] = None
    speed_override: Optional[float] = None
    prompt_directive: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def estimated_duration_sec(self) -> float:
        # Standard average speaking rate ~140 words per minute (~2.33 words/sec) + trailing pause
        return (self.word_count / 2.33) + (self.pause_after_ms / 1000.0)


class NarrativeChunker:
    """Splits manuscript prose into prosodically balanced speech segments."""

    def __init__(
        self,
        max_chunk_chars: int = 600,
        min_chunk_chars: int = 30,
        pacing_config: Optional[PacingConfig] = None,
    ):
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.pacing = pacing_config or PACING_PRESETS[PacingMode.NORMAL]

    def chunk_text(self, text: str, default_voice: str = "Kore") -> List[NarrativeChunk]:
        """Transform raw text into an ordered sequence of semantic narrative chunks."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[NarrativeChunk] = []
        chunk_idx = 0

        for p_idx, paragraph in enumerate(paragraphs):
            # Check if this paragraph is a section break
            if paragraph in ["* * *", "---", "***", "___", "###", "•••"]:
                chunks.append(
                    NarrativeChunk(
                        index=chunk_idx,
                        text="",
                        chunk_type=ChunkType.SECTION_BREAK,
                        pause_after_ms=self.pacing.chapter_pause_ms,
                    )
                )
                chunk_idx += 1
                continue

            # Check if this is a heading
            if paragraph.startswith("#") or paragraph.isupper() and len(paragraph) < 80:
                clean_heading = paragraph.lstrip("#").strip()
                chunks.append(
                    NarrativeChunk(
                        index=chunk_idx,
                        text=clean_heading,
                        chunk_type=ChunkType.HEADING,
                        pause_after_ms=self.pacing.paragraph_pause_ms + 200,
                        prompt_directive="Deliver clearly as an authoritative chapter or section title.",
                    )
                )
                chunk_idx += 1
                continue

            # Segment paragraph into dialogue and exposition blocks
            para_segments = self._segment_paragraph(paragraph)
            
            for seg_idx, (seg_text, seg_type, gender_hint) in enumerate(para_segments):
                if not seg_text.strip():
                    continue

                is_last_in_paragraph = (seg_idx == len(para_segments) - 1)
                
                # Determine pause duration
                if is_last_in_paragraph:
                    pause_ms = self.pacing.paragraph_pause_ms
                elif seg_type == ChunkType.DIALOGUE:
                    pause_ms = self.pacing.dialogue_pause_ms
                else:
                    pause_ms = self._calculate_punctuation_pause(seg_text)

                # Sub-chunk if excessively long
                if len(seg_text) > self.max_chunk_chars:
                    sub_sentences = self._split_long_segment(seg_text)
                    for s_idx, sub_s in enumerate(sub_sentences):
                        sub_is_last = (s_idx == len(sub_sentences) - 1)
                        sub_pause = pause_ms if sub_is_last else self.pacing.sentence_pause_ms
                        chunks.append(
                            NarrativeChunk(
                                index=chunk_idx,
                                text=sub_s,
                                chunk_type=seg_type,
                                speaker="character" if seg_type == ChunkType.DIALOGUE else "narrator",
                                gender_hint=gender_hint,
                                pause_after_ms=sub_pause,
                            )
                        )
                        chunk_idx += 1
                else:
                    chunks.append(
                        NarrativeChunk(
                            index=chunk_idx,
                            text=seg_text,
                            chunk_type=seg_type,
                            speaker="character" if seg_type == ChunkType.DIALOGUE else "narrator",
                            gender_hint=gender_hint,
                            pause_after_ms=pause_ms,
                        )
                    )
                    chunk_idx += 1

        return chunks

    def _segment_paragraph(self, text: str) -> List[tuple]:
        """Separate dialogue in quotes from narrative exposition within a paragraph."""
        # Match standard double-quoted speech: "Hello," he said.
        # Single-quote dialogue is converted to double quotes by DocumentParser during normalization.
        # Word-internal apostrophes ('s, 't, don't, can't) must remain intact within exposition/dialogue.
        segments = []
        pattern = re.compile(r'("(?:[^"\\]|\\.)*")')
        
        last_end = 0
        for match in pattern.finditer(text):
            start, end = match.span()
            # Exposition before quote
            if start > last_end:
                expo = text[last_end:start].strip()
                if expo:
                    segments.append((expo, ChunkType.EXPOSITION, None))
            
            # Quoted speech
            quote = match.group(1).strip()
            # Strip surrounding quote marks for cleaner neural prosody
            inner_quote = quote.strip('"')
            if inner_quote:
                # Basic dialogue gender heuristic
                gender_hint = self._infer_speaker_gender(text, last_end, end)
                segments.append((inner_quote, ChunkType.DIALOGUE, gender_hint))
            
            last_end = end

        # Trailing exposition after last quote
        if last_end < len(text):
            trailing = text[last_end:].strip()
            if trailing:
                segments.append((trailing, ChunkType.EXPOSITION, None))

        if not segments:
            segments.append((text.strip(), ChunkType.EXPOSITION, None))

        return segments

    def _infer_speaker_gender(self, text: str, start_idx: int, end_idx: int) -> Optional[str]:
        """Inspect surrounding context for gendered dialogue tags (e.g., 'she whispered', 'he said')."""
        window_start = max(0, start_idx - 60)
        window_end = min(len(text), end_idx + 60)
        context = text[window_start:window_end].lower()

        female_tags = ["she said", "she asked", "she whispered", "she yelled", "she replied", "muttered the girl", "said the woman", "her voice"]
        male_tags = ["he said", "he asked", "he whispered", "he yelled", "he replied", "muttered the boy", "said the man", "his voice", "case said"]

        if any(tag in context for tag in female_tags):
            return "female"
        if any(tag in context for tag in male_tags):
            return "male"
        return None

    def _calculate_punctuation_pause(self, text: str) -> int:
        """Derive natural trailing pause duration based on terminal punctuation."""
        stripped = text.strip()
        if stripped.endswith("..."):
            return self.pacing.sentence_pause_ms + 150
        elif stripped.endswith("—") or stripped.endswith("--"):
            return self.pacing.sentence_pause_ms + 100
        elif stripped.endswith("?"):
            return self.pacing.sentence_pause_ms + 40
        elif stripped.endswith("!"):
            return self.pacing.sentence_pause_ms + 20
        elif stripped.endswith(":"):
            return self.pacing.clause_pause_ms + 80
        elif stripped.endswith(";"):
            return self.pacing.clause_pause_ms + 60
        elif stripped.endswith(","):
            return self.pacing.clause_pause_ms
        else:
            return self.pacing.sentence_pause_ms

    def _split_long_segment(self, text: str) -> List[str]:
        """Break long prose at sentence boundaries or major clause delimiters."""
        # Sentence splitting pattern
        sentence_re = re.compile(r'(?<=[.!?…])\s+(?=[A-Z0-9"\'—])')
        sentences = [s.strip() for s in sentence_re.split(text) if s.strip()]

        result = []
        for s in sentences:
            if len(s) <= self.max_chunk_chars:
                result.append(s)
            else:
                # Split at clause boundaries (; — : ,)
                clauses = re.split(r'(?<=[;—:])\s+|(?<=,\sand)\s+|(?<=,\sbut)\s+', s)
                accum = ""
                for clause in clauses:
                    if len(accum) + len(clause) + 1 <= self.max_chunk_chars:
                        accum = f"{accum} {clause}".strip()
                    else:
                        if accum:
                            result.append(accum)
                        accum = clause
                if accum:
                    result.append(accum)

        return result if result else [text]
