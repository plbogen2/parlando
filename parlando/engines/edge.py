"""Microsoft Neural Voice synthesis via edge-tts."""

import asyncio
import os
import random
import time
from typing import Optional

from parlando.core.chunker import NarrativeChunk
from parlando.core.dsp import AudioBuffer
from .base import BaseVoiceEngine, VoiceEngineError


class EdgeTTSVoiceEngine(BaseVoiceEngine):
    """Free, studio-quality Microsoft Neural Voice synthesis via edge-tts."""

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

    def __init__(self, default_voice: str = "en-US-ChristopherNeural", max_retries: int = 4, **kwargs):
        self.default_voice = default_voice
        self.max_retries = max_retries

    def resolve_voice(self, voice_name: Optional[str]) -> str:
        if not voice_name:
            return self.default_voice
        return self.VOICE_MAP.get(voice_name, voice_name)

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        try:
            import edge_tts
        except ImportError:
            raise VoiceEngineError("edge-tts package is not installed. Install via `pip install edge-tts`.")

        text = chunk.text.strip()
        if not text:
            AudioBuffer.create_silence(duration_ms=max(300, chunk.pause_after_ms)).to_wav_file(output_path)
            return output_path

        voice = self.resolve_voice(chunk.voice or chunk.character)

        rate_str = chunk.ssml_rate or "+0%"
        pitch_str = chunk.ssml_pitch or "+0Hz"

        mp3_temp = output_path.replace(".wav", ".mp3")
        last_error = None

        for attempt in range(self.max_retries):
            try:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate_str, pitch=pitch_str)
                    loop.run_until_complete(communicate.save(mp3_temp))
                finally:
                    loop.close()

                if os.path.exists(mp3_temp) and os.path.getsize(mp3_temp) > 0:
                    import subprocess
                    cmd = ["ffmpeg", "-y", "-i", mp3_temp, "-ar", "24000", "-ac", "1", output_path]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    finally:
                        if os.path.exists(mp3_temp):
                            os.remove(mp3_temp)
                    return output_path
            except Exception as e:
                last_error = e
                time.sleep(0.3 * (2 ** attempt) + random.uniform(0.1, 0.3))

        if os.path.exists(mp3_temp):
            try:
                os.remove(mp3_temp)
            except Exception:
                pass

        raise VoiceEngineError(f"Failed to synthesize chunk after {self.max_retries} attempts: {last_error}")
