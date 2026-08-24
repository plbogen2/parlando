"""OpenAI Audio TTS Voice synthesis."""

import os
import subprocess
from typing import Optional

from parlando.core.chunker import NarrativeChunk
from parlando.core.dsp import AudioBuffer
from .base import BaseVoiceEngine, VoiceEngineError


class OpenAIVoiceEngine(BaseVoiceEngine):
    """OpenAI TTS voice engine (requires OPENAI_API_KEY)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "tts-1-hd", default_voice: str = "onyx", **kwargs):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.default_voice = default_voice

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        try:
            import openai
        except ImportError:
            raise VoiceEngineError("openai package is not installed. Install via `pip install openai`.")

        client = openai.OpenAI(api_key=self.api_key)
        voice = chunk.character if chunk.character in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] else self.default_voice

        mp3_temp = output_path.replace(".wav", ".mp3")
        try:
            response = client.audio.speech.create(
                model=self.model,
                voice=voice,
                input=chunk.text,
            )
            response.stream_to_file(mp3_temp)
            cmd = ["ffmpeg", "-y", "-i", mp3_temp, "-ar", "24000", "-ac", "1", output_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(mp3_temp):
                os.remove(mp3_temp)
            return output_path
        except Exception as e:
            raise VoiceEngineError(f"OpenAI TTS synthesis error: {e}")
