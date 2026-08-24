"""Abstract base class for all Parlando speech synthesis engines."""

import abc
import concurrent.futures
import os
from typing import List, Optional

from parlando.core.chunker import ChunkType, NarrativeChunk
from parlando.core.dsp import AudioBuffer


class VoiceEngineError(Exception):
    """Raised when audio synthesis fails after all retries."""
    pass


class BaseVoiceEngine(abc.ABC):
    """Abstract interface for audio synthesis engines."""

    @abc.abstractmethod
    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        """Synthesize audio for a single chunk to the destination WAV file."""
        pass

    def synthesize_batch(
        self,
        chunks: List[NarrativeChunk],
        output_dir: str,
        max_workers: int = 4,
        progress_callback: Optional[callable] = None,
    ) -> List[str]:
        """Synthesize multiple chunks concurrently in a worker pool with caching."""
        os.makedirs(output_dir, exist_ok=True)
        results = [None] * len(chunks)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {}
            for idx, chunk in enumerate(chunks):
                chunk_path = os.path.join(output_dir, f"chunk_{idx:05d}.wav")

                if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 44:
                    results[idx] = chunk_path
                    if progress_callback:
                        progress_callback(idx, len(chunks), chunk)
                    continue

                if chunk.chunk_type == ChunkType.SECTION_BREAK or not chunk.text.strip():
                    AudioBuffer.create_silence(duration_ms=chunk.pause_after_ms).to_wav_file(chunk_path)
                    results[idx] = chunk_path
                    if progress_callback:
                        progress_callback(idx, len(chunks), chunk)
                    continue

                future = executor.submit(self.synthesize_chunk, chunk, chunk_path)
                future_to_idx[future] = (idx, chunk_path, chunk)

            for future in concurrent.futures.as_completed(future_to_idx):
                idx, chunk_path, chunk = future_to_idx[future]
                try:
                    future.result()
                    results[idx] = chunk_path
                    if progress_callback:
                        progress_callback(idx, len(chunks), chunk)
                except Exception as e:
                    print(f"\n[WARN] Chunk {idx} synthesis failed ({e}). Falling back to clean silence pad.")
                    AudioBuffer.create_silence(duration_ms=max(500, chunk.pause_after_ms)).to_wav_file(chunk_path)
                    results[idx] = chunk_path
                    if progress_callback:
                        progress_callback(idx, len(chunks), chunk)

        return results
