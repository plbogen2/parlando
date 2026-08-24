"""Semantic Prose Segmentation, Dialogue Extraction, and Pacing Envelope Allocator."""

import dataclasses
from enum import Enum
import re
from typing import List, Optional, Tuple


class ChunkType(str, Enum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    HEADING = "heading"
    SECTION_BREAK = "section_break"


@dataclasses.dataclass
class NarrativeChunk:
    text: str
    chunk_type: ChunkType
    character: Optional[str] = None
    gender: Optional[str] = None
    pause_before_ms: int = 0
    pause_after_ms: int = 0
    chapter_index: int = 0
    chunk_index: int = 0


class NarrativeChunker:
    """Segments narrative prose manuscripts into acoustic chunks."""

    DIALOGUE_PATTERN = re.compile(
        r'(?P<pre>.*?)(?:“(?P<curly_dialogue>[^”]+)”|"(?P<straight_dialogue>[^"]+)")(?P<post>.*)',
        re.DOTALL
    )

    def __init__(self, target_chunk_words: int = 28, max_chunk_words: int = 55):
        self.target_chunk_words = target_chunk_words
        self.max_chunk_words = max_chunk_words

    def chunk_text(self, text: str, chapter_index: int = 0) -> List[NarrativeChunk]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[NarrativeChunk] = []
        chunk_idx = 0

        for para in paragraphs:
            if para.startswith("#"):
                clean_heading = re.sub(r"^#+\s*", "", para).strip()
                chunks.append(NarrativeChunk(
                    text=clean_heading,
                    chunk_type=ChunkType.HEADING,
                    pause_before_ms=600,
                    pause_after_ms=800,
                    chapter_index=chapter_index,
                    chunk_index=chunk_idx,
                ))
                chunk_idx += 1
                continue

            if para in ("*", "* * *", "---", "***", "###"):
                chunks.append(NarrativeChunk(
                    text="",
                    chunk_type=ChunkType.SECTION_BREAK,
                    pause_after_ms=1200,
                    chapter_index=chapter_index,
                    chunk_index=chunk_idx,
                ))
                chunk_idx += 1
                continue

            para_chunks = self._chunk_paragraph(para, chapter_index, chunk_idx)
            chunks.extend(para_chunks)
            chunk_idx += len(para_chunks)

        return chunks

    def _chunk_paragraph(self, paragraph: str, chapter_index: int, start_idx: int) -> List[NarrativeChunk]:
        chunks: List[NarrativeChunk] = []
        segments = self._extract_dialogue_segments(paragraph)
        curr_idx = start_idx

        for text, c_type in segments:
            text = text.strip()
            if not text:
                continue

            words = text.split()
            if len(words) <= self.max_chunk_words:
                chunks.append(NarrativeChunk(
                    text=text,
                    chunk_type=c_type,
                    pause_after_ms=450 if c_type == ChunkType.DIALOGUE else 220,
                    chapter_index=chapter_index,
                    chunk_index=curr_idx,
                ))
                curr_idx += 1
            else:
                sub_sentences = re.split(r'(?<=[.!?…])\s+(?=[A-Z"“0-9])', text)
                current_acc: List[str] = []
                current_count = 0

                for s in sub_sentences:
                    s_words = s.split()
                    if current_count + len(s_words) > self.target_chunk_words and current_acc:
                        joined = " ".join(current_acc).strip()
                        chunks.append(NarrativeChunk(
                            text=joined,
                            chunk_type=c_type,
                            pause_after_ms=220,
                            chapter_index=chapter_index,
                            chunk_index=curr_idx,
                        ))
                        curr_idx += 1
                        current_acc = [s]
                        current_count = len(s_words)
                    else:
                        current_acc.append(s)
                        current_count += len(s_words)

                if current_acc:
                    joined = " ".join(current_acc).strip()
                    chunks.append(NarrativeChunk(
                        text=joined,
                        chunk_type=c_type,
                        pause_after_ms=450 if c_type == ChunkType.DIALOGUE else 300,
                        chapter_index=chapter_index,
                        chunk_index=curr_idx,
                    ))
                    curr_idx += 1

        if chunks:
            chunks[-1].pause_after_ms = max(chunks[-1].pause_after_ms, 650)

        return chunks

    def _extract_dialogue_segments(self, text: str) -> List[Tuple[str, ChunkType]]:
        segments: List[Tuple[str, ChunkType]] = []
        pos = 0

        while pos < len(text):
            match = re.search(r'[“"][^”"]+[”"]', text[pos:])
            if not match:
                remaining = text[pos:].strip()
                if remaining:
                    segments.append((remaining, ChunkType.NARRATION))
                break

            m_start = pos + match.start()
            m_end = pos + match.end()

            if m_start > pos:
                narration = text[pos:m_start].strip()
                if narration:
                    segments.append((narration, ChunkType.NARRATION))

            dialogue = text[m_start:m_end].strip()
            clean_dialogue = re.sub(r'^[“"]|[”"]$', '', dialogue).strip()
            if clean_dialogue:
                segments.append((clean_dialogue, ChunkType.DIALOGUE))

            pos = m_end

        return segments
