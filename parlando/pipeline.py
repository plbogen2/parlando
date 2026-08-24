"""Unified High-Level Audiobook Synthesis Pipeline for Parlando (DRY orchestrator for CLI and Web)."""

import dataclasses
import os
import shutil
import tempfile
import time
from typing import Callable, List, Optional

from parlando.core import (
    AudioBuffer,
    AudioStitcher,
    ChapterTimepoint,
    NarrativeChunker,
    ProsodyDirector,
    StitchedAudioResult,
)
from parlando.config import (
    AudioFormat,
    PACING_PRESETS,
    PacingConfig,
    PacingMode,
    VOICE_PROFILES,
    VoiceProfile,
)
from parlando.engines import BaseVoiceEngine, get_voice_engine
from parlando.export import AudioExporter, HTMLPlayerGenerator
from parlando.parsers import DocumentParser, ParsedDocument


@dataclasses.dataclass
class PipelineConfig:
    backend: str = "edge"
    voice: str = "en-US-ChristopherNeural"
    dialogue_voice: Optional[str] = None
    pacing_mode: PacingMode = PacingMode.NORMAL
    speed: float = 1.0
    audio_format: AudioFormat = AudioFormat.M4B
    crossfade_ms: int = 35
    audition: bool = False
    max_workers: int = 4
    cache_dir: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    generate_player: bool = True
    normalize_loudness: bool = True


@dataclasses.dataclass
class PipelineResult:
    audio_path: str
    player_path: Optional[str]
    duration_seconds: float
    total_chunks: int
    chapter_timepoints: List[ChapterTimepoint]
    render_time_seconds: float
    document: ParsedDocument


class AudiobookPipeline:
    """End-to-end synthesizer orchestrating parsing, prosody, voice engines, DSP stitching, and export."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.pacing = PACING_PRESETS.get(self.config.pacing_mode, PacingConfig())
        self.pacing.speed_multiplier = self.config.speed
        self.voice_profile = VoiceProfile(
            name="custom",
            primary_voice=self.config.voice,
            default_pacing=self.config.pacing_mode,
        )
        self.chunker = NarrativeChunker()
        self.director = ProsodyDirector(voice_profile=self.voice_profile, pacing=self.pacing)
        self.stitcher = AudioStitcher(crossfade_ms=self.config.crossfade_ms)
        self.exporter = AudioExporter()

    def run(
        self,
        input_target: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> PipelineResult:
        t_start = time.time()

        # 1. Ingest
        if os.path.exists(input_target) or input_target.startswith(("http://", "https://")):
            doc = DocumentParser.from_file_or_url(input_target)
        else:
            doc = DocumentParser.from_text(input_target)

        if self.config.audition:
            doc = doc.get_audition_excerpt(max_words=1200)

        # 2. Derive output path if omitted
        if not output_path:
            clean_title = "".join(c if c.isalnum() else "_" for c in doc.title.lower()).strip("_")
            ext = f".{self.config.audio_format.value}"
            output_path = f"{clean_title}{ext}"

        # 3. Narrative Chunking
        all_chunks = []
        for chap_idx, chap in enumerate(doc.chapters):
            chap_text = f"# {chap.title}\n\n{chap.content}" if chap.title else chap.content
            chunks = self.chunker.chunk_text(chap_text, chapter_index=chap_idx)
            for c in chunks:
                self.director.apply_to_chunk(c, dialogue_voice_override=self.config.dialogue_voice)
            all_chunks.extend(chunks)

        # 4. Neural Voice Synthesis
        cache_dir = self.config.cache_dir or os.path.join(tempfile.gettempdir(), ".parlando_chunk_cache")
        engine = get_voice_engine(
            self.config.backend,
            default_voice=self.config.voice,
            api_key=self.config.api_key,
            model=self.config.model,
        )

        def _on_chunk_progress(idx, total, chunk):
            if progress_callback:
                progress_callback(idx + 1, total, chunk.text[:40])

        audio_paths = engine.synthesize_batch(
            all_chunks,
            output_dir=cache_dir,
            max_workers=self.config.max_workers,
            progress_callback=_on_chunk_progress,
        )

        # 5. DSP Stitching
        chapter_titles = [c.title for c in doc.chapters]
        stitched = self.stitcher.assemble_chunks(all_chunks, audio_paths, chapter_titles=chapter_titles)

        # 6. Container Mastering
        final_audio_path = self.exporter.export(
            audio_buffer=stitched.master_buffer,
            output_path=output_path,
            title=doc.title,
            author=doc.author,
            chapter_timepoints=stitched.chapter_timepoints,
            audio_format=self.config.audio_format,
            normalize_loudness=self.config.normalize_loudness,
        )

        # 7. HTML5 Player
        player_path = None
        if self.config.generate_player:
            base_no_ext = os.path.splitext(output_path)[0]
            player_path = f"{base_no_ext}_player.html"
            audio_rel = os.path.basename(final_audio_path)
            HTMLPlayerGenerator.write_player_file(
                player_path,
                title=doc.title,
                author=doc.author,
                audio_filename=audio_rel,
                chapter_timepoints=stitched.chapter_timepoints,
            )

        t_end = time.time()
        return PipelineResult(
            audio_path=final_audio_path,
            player_path=player_path,
            duration_seconds=stitched.master_buffer.duration_seconds,
            total_chunks=len(all_chunks),
            chapter_timepoints=stitched.chapter_timepoints,
            render_time_seconds=t_end - t_start,
            document=doc,
        )
