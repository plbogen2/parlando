"""Zero-Crossing Waveform Stitcher, Silence Inserter, and Chapter Timepoint Tracker."""

import dataclasses
import os
from typing import List, Optional
from .chunker import ChunkType, NarrativeChunk
from .dsp import AudioBuffer, DEFAULT_SAMPLE_RATE


@dataclasses.dataclass
class ChapterTimepoint:
    title: str
    start_ms: int
    end_ms: int
    chapter_index: int


@dataclasses.dataclass
class StitchedAudioResult:
    master_buffer: AudioBuffer
    chapter_timepoints: List[ChapterTimepoint]
    total_chunks: int


class AudioStitcher:
    """Concatenates audio chunks with zero-crossing crossfading and exact timepoint marks."""

    def __init__(self, crossfade_ms: int = 35, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.crossfade_ms = crossfade_ms
        self.sample_rate = sample_rate

    def assemble_chunks(
        self,
        chunks: List[NarrativeChunk],
        audio_paths: List[str],
        chapter_titles: Optional[List[str]] = None,
    ) -> StitchedAudioResult:
        master = AudioBuffer(sample_rate=self.sample_rate)
        timepoints: List[ChapterTimepoint] = []

        current_chapter_idx = -1
        chapter_start_ms = 0
        current_chapter_title = "Prologue"

        for idx, (chunk, path) in enumerate(zip(chunks, audio_paths)):
            if chunk.chapter_index != current_chapter_idx or chunk.chunk_type == ChunkType.HEADING:
                if current_chapter_idx != -1:
                    timepoints.append(ChapterTimepoint(
                        title=current_chapter_title,
                        start_ms=chapter_start_ms,
                        end_ms=int(master.duration_ms),
                        chapter_index=current_chapter_idx,
                    ))

                current_chapter_idx = chunk.chapter_index
                chapter_start_ms = int(master.duration_ms)

                if chunk.chunk_type == ChunkType.HEADING:
                    current_chapter_title = chunk.text
                elif chapter_titles and current_chapter_idx < len(chapter_titles):
                    current_chapter_title = chapter_titles[current_chapter_idx]
                else:
                    current_chapter_title = f"Chapter {current_chapter_idx + 1}"

            if not os.path.exists(path) or os.path.getsize(path) < 44:
                silence = AudioBuffer.create_silence(max(300, chunk.pause_after_ms), self.sample_rate)
                master.append(silence)
                continue

            chunk_buf = AudioBuffer.from_wav_file(path)
            trimmed_buf = chunk_buf.trim_silence()

            if trimmed_buf.is_empty():
                continue

            if master.is_empty():
                master.append(trimmed_buf)
            else:
                master.crossfade_append(trimmed_buf, crossfade_ms=self.crossfade_ms)

            if chunk.pause_after_ms > 0:
                silence = AudioBuffer.create_silence(chunk.pause_after_ms, self.sample_rate)
                master.append(silence)

        if current_chapter_idx != -1:
            timepoints.append(ChapterTimepoint(
                title=current_chapter_title,
                start_ms=chapter_start_ms,
                end_ms=int(master.duration_ms),
                chapter_index=current_chapter_idx,
            ))

        return StitchedAudioResult(
            master_buffer=master,
            chapter_timepoints=timepoints,
            total_chunks=len(chunks),
        )
