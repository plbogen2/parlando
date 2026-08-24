"""Multi-backend voice synthesis engine supporting Edge-TTS, Gemini API, OpenAI, and local DSP."""

import abc
import asyncio
import concurrent.futures
import json
import math
import os
import random
import subprocess
import time
import urllib.request
from typing import List, Optional
from .chunker import ChunkType, NarrativeChunk
from .config import (
    DEFAULT_SAMPLE_RATE,
    VALID_NEURAL_VOICES,
)
from .dsp import AudioBuffer


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

                # Reuse cached chunk if already synthesized and valid
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


class EdgeTTSVoiceEngine(BaseVoiceEngine):
    """Free, studio-quality Microsoft Neural Voice synthesis via edge-tts (no API key required)."""

    VOICE_MAP = {
        "Fenrir": "en-US-ChristopherNeural",
        "Puck": "en-US-GuyNeural",
        "Charon": "en-GB-RyanNeural",
        "Aoede": "en-US-JennyNeural",
        "Kore": "en-US-AriaNeural",
        "Leda": "en-GB-SoniaNeural",
        "Oran": "en-US-EricNeural",
        "Zephyr": "en-US-RogerNeural",
    }

    def __init__(self, default_voice: str = "en-US-ChristopherNeural", max_retries: int = 4):
        self.default_voice = default_voice
        self.max_retries = max_retries

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        """Call edge-tts or subprocess edge-playback to generate standard audio."""
        if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
            return output_path

        text = chunk.text.strip()
        if not text:
            AudioBuffer.create_silence(duration_ms=chunk.pause_after_ms).to_wav_file(output_path)
            return output_path

        voice = chunk.voice_override or self.default_voice
        voice = self.VOICE_MAP.get(voice, voice)

        # Check if edge-tts library is installed or use CLI
        try:
            import edge_tts
            async def _run():
                communicate = edge_tts.Communicate(text, voice)
                # edge-tts outputs MP3 by default; convert or write
                temp_mp3 = output_path + ".mp3"
                await communicate.save(temp_mp3)
                # Convert temp MP3 to WAV via ffmpeg
                subprocess.run(["ffmpeg", "-y", "-i", temp_mp3, output_path], capture_output=True)
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)

            asyncio.run(_run())
            if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
                return output_path
        except ImportError:
            # Fallback to edge-tts CLI if present
            temp_mp3 = output_path + ".mp3"
            cmd = ["edge-tts", "--voice", voice, "--text", text, "--write-media", temp_mp3]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0 and os.path.exists(temp_mp3):
                subprocess.run(["ffmpeg", "-y", "-i", temp_mp3, output_path], capture_output=True)
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
                    return output_path

        raise VoiceEngineError("Edge-TTS unavailable. Install via `pip install edge-tts`.")


class OpenAIVoiceEngine(BaseVoiceEngine):
    """OpenAI neural speech synthesis backend (alloy, echo, fable, onyx, nova, shimmer)."""

    VOICE_MAP = {
        "Fenrir": "onyx",
        "Puck": "fable",
        "Charon": "echo",
        "Aoede": "nova",
        "Kore": "alloy",
        "Leda": "shimmer",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "tts-1-hd", default_voice: str = "onyx"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.default_voice = default_voice

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        """Call OpenAI TTS REST API."""
        if not self.api_key:
            raise VoiceEngineError("OPENAI_API_KEY environment variable not set.")

        text = chunk.text.strip()
        voice = chunk.voice_override or self.default_voice
        voice = self.VOICE_MAP.get(voice, voice)

        req_data = json.dumps({
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": "wav",
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=req_data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            wav_bytes = resp.read()

        with open(output_path, "wb") as f:
            f.write(wav_bytes)

        return output_path


class GeminiVoiceEngine(BaseVoiceEngine):
    """High-fidelity neural voice synthesis via Gemini /generate binary or Public API."""

    def __init__(
        self,
        binary_path: str = "/google/bin/releases/gemini-agents-generate/generate",
        default_voice: str = "Kore",
        max_retries: int = 5,
        base_backoff_sec: float = 2.0,
    ):
        self.binary_path = binary_path
        self.default_voice = default_voice
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        """Call Gemini TTS with resilient exponential backoff and jitter."""
        if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
            return output_path

        text = chunk.text.strip()
        if not text:
            AudioBuffer.create_silence(duration_ms=chunk.pause_after_ms).to_wav_file(output_path)
            return output_path

        # Clean trailing comma/quotes that can cause empty returns on edge models
        cleaned_text = text.rstrip(",;:- ")
        if not cleaned_text.endswith((".", "!", "?", '"')):
            cleaned_text += "."

        voice = chunk.voice_override or self.default_voice
        if voice not in VALID_NEURAL_VOICES:
            voice = self.default_voice

        if os.path.exists(self.binary_path):
            cmd = [
                self.binary_path,
                f"-output={output_path}",
                "tts",
                f"-voice={voice}",
                cleaned_text,
            ]

            last_error = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=50,
                    )

                    if proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 44:
                        return output_path

                    stderr = proc.stderr or ""
                    stdout = proc.stdout or ""
                    last_error = stderr.strip() or stdout.strip() or f"Exit code {proc.returncode}"

                except subprocess.TimeoutExpired:
                    last_error = "Process timed out after 50 seconds"
                except Exception as e:
                    last_error = str(e)

                if attempt < self.max_retries:
                    backoff = (self.base_backoff_sec * (1.5 ** (attempt - 1))) + random.uniform(0.5, 2.5)
                    time.sleep(backoff)

            raise VoiceEngineError(f"Gemini TTS failed after {self.max_retries} attempts: {last_error}")
        else:
            raise VoiceEngineError(f"Gemini binary not found at {self.binary_path}. Use --backend=edge or --backend=openai.")


class MockVoiceEngine(BaseVoiceEngine):
    """Deterministic, fast mock engine generating synthetic speech bursts for testing and offline builds."""

    def __init__(self, sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.sample_rate = sample_rate

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        """Generate a synthetic tone/speech burst matching the estimated duration."""
        if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
            return output_path

        text = chunk.text.strip()
        duration_sec = max(0.2, len(text.split()) / 3.0)
        num_frames = int(duration_sec * self.sample_rate)

        import array
        samples = array.array("h")
        freq = 160.0 if chunk.gender_hint == "female" else 110.0
        
        for f in range(num_frames):
            t = f / float(self.sample_rate)
            env = min(1.0, f / 500.0) * min(1.0, (num_frames - f) / 500.0)
            val = (
                math.sin(2.0 * math.pi * freq * t) * 0.6 +
                math.sin(2.0 * math.pi * (freq * 2) * t) * 0.3 +
                math.sin(2.0 * math.pi * (freq * 3) * t) * 0.1
            )
            sample_val = int(val * 16000 * env)
            samples.append(sample_val)

        buf = AudioBuffer(samples=samples, sample_rate=self.sample_rate, channels=1)
        buf.to_wav_file(output_path)
        return output_path


def get_voice_engine(
    backend: str = "auto",
    default_voice: str = "Fenrir",
) -> BaseVoiceEngine:
    """Factory helper resolving the best voice engine backend."""
    b = backend.lower()
    if b == "mock":
        return MockVoiceEngine()
    elif b == "edge":
        return EdgeTTSVoiceEngine(default_voice=default_voice)
    elif b == "openai":
        return OpenAIVoiceEngine(default_voice=default_voice)
    elif b == "gemini" or b == "gemini_cli":
        return GeminiVoiceEngine(default_voice=default_voice)
    else:
        # Auto detection
        if os.path.exists("/google/bin/releases/gemini-agents-generate/generate"):
            return GeminiVoiceEngine(default_voice=default_voice)
        try:
            import edge_tts
            return EdgeTTSVoiceEngine(default_voice=default_voice)
        except ImportError:
            pass
        return MockVoiceEngine()
