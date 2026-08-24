"""Audio stream assembly and crossfaded stitching pipeline."""

import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from .chunker import ChunkType, NarrativeChunk
from .config import (
    DEFAULT_SAMPLE_RATE,
    PacingConfig,
    PacingMode,
    PACING_PRESETS,
)
from .dsp import AudioBuffer
from .engine import BaseVoiceEngine


@dataclass
class ChapterTimepoint:
    """Timestamp marker for audiobook chapter index."""
    chapter_num: int
    title: str
    start_time_sec: float
    end_time_sec: float
    duration_sec: float


@dataclass
class StitchedAudioResult:
    """Output container for completed audiobook audio and chapter markers."""
    master_wav_path: str
    duration_sec: float
    total_samples: int
    sample_rate: int
    chapter_timepoints: List[ChapterTimepoint] = field(default_factory=list)


class AudioStitcher:
    """Assembles segmented neural audio chunks into a studio-grade continuous stream."""

    def __init__(
        self,
        voice_engine: BaseVoiceEngine,
        pacing_config: Optional[PacingConfig] = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ):
        self.engine = voice_engine
        self.pacing = pacing_config or PACING_PRESETS[PacingMode.NORMAL]
        self.sample_rate = sample_rate

    def assemble_chunks(
        self,
        chunks: List[NarrativeChunk],
        output_wav_path: str,
        max_workers: int = 4,
        normalize: bool = True,
        progress_callback: Optional[Callable[[int, int, NarrativeChunk], None]] = None,
    ) -> StitchedAudioResult:
        """Synthesize and stitch chunks into a single continuous track with persistent checkpoint cache."""
        if not chunks:
            buf = AudioBuffer.create_silence(1000, sample_rate=self.sample_rate)
            buf.to_wav_file(output_wav_path)
            return StitchedAudioResult(
                master_wav_path=output_wav_path,
                duration_sec=1.0,
                total_samples=self.sample_rate,
                sample_rate=self.sample_rate,
                chapter_timepoints=[],
            )

        # Use persistent cache directory next to output path
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(output_wav_path)), ".chunk_cache")
        os.makedirs(cache_dir, exist_ok=True)

        # 1. Batch synthesize all chunk WAVs concurrently
        wav_paths = self.engine.synthesize_batch(
            chunks=chunks,
            output_dir=cache_dir,
            max_workers=max_workers,
            progress_callback=progress_callback,
        )

        # 2. Sequential DSP assembly with zero-crossing crossfading
        master_buffer: Optional[AudioBuffer] = None
        chapter_timepoints: List[ChapterTimepoint] = []
        
        current_time_sec = 0.0
        current_chapter_start = 0.0
        current_chapter_title = "Chapter 1"
        current_chapter_num = 1

        for idx, (chunk, wav_path) in enumerate(zip(chunks, wav_paths)):
            if chunk.chunk_type == ChunkType.HEADING:
                if idx > 0:
                    chapter_timepoints.append(
                        ChapterTimepoint(
                            chapter_num=current_chapter_num,
                            title=current_chapter_title,
                            start_time_sec=current_chapter_start,
                            end_time_sec=current_time_sec,
                            duration_sec=current_time_sec - current_chapter_start,
                        )
                    )
                    current_chapter_num += 1
                    current_chapter_start = current_time_sec
                current_chapter_title = chunk.text

            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 44:
                chunk_buf = AudioBuffer.from_wav_file(wav_path)
            else:
                chunk_buf = AudioBuffer.create_silence(duration_ms=chunk.pause_after_ms, sample_rate=self.sample_rate)

            chunk_buf.apply_fade_in(8.0)
            chunk_buf.apply_fade_out(8.0)

            pause_buf = AudioBuffer.create_silence(
                duration_ms=chunk.pause_after_ms,
                sample_rate=self.sample_rate,
            )

            segment_buf = chunk_buf.append(pause_buf)

            if master_buffer is None:
                master_buffer = segment_buf
            else:
                master_buffer = master_buffer.crossfade_with(
                    segment_buf,
                    crossfade_ms=self.pacing.crossfade_ms,
                )

            current_time_sec = master_buffer.duration_sec

        if master_buffer:
            chapter_timepoints.append(
                ChapterTimepoint(
                    chapter_num=current_chapter_num,
                    title=current_chapter_title,
                    start_time_sec=current_chapter_start,
                    end_time_sec=master_buffer.duration_sec,
                    duration_sec=master_buffer.duration_sec - current_chapter_start,
                )
            )

        if normalize and master_buffer:
            master_buffer.normalize(target_peak_fraction=0.96)

        os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
        master_buffer.to_wav_file(output_wav_path)

        return StitchedAudioResult(
            master_wav_path=output_wav_path,
            duration_sec=master_buffer.duration_sec,
            total_samples=len(master_buffer.samples),
            sample_rate=master_buffer.sample_rate,
            chapter_timepoints=chapter_timepoints,
        )
