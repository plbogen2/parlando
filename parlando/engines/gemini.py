"""Google Gemini Neural Voice engine adapter."""

import base64
import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.request
import wave
from typing import Optional

from parlando.config import DEFAULT_GEMINI_MODEL, FALLBACK_GEMINI_MODEL
from parlando.core.chunker import NarrativeChunk
from parlando.core.dsp import AudioBuffer
from .base import BaseVoiceEngine, VoiceEngineError


class GeminiVoiceEngine(BaseVoiceEngine):
    """Studio neural voice synthesis via Google Gemini Multimodal Audio API."""

    VOICE_MAP = {
        "en-US-ChristopherNeural": "Fenrir",
        "en-US-GuyNeural": "Puck",
        "en-GB-RyanNeural": "Charon",
        "en-US-JennyNeural": "Aoede",
        "en-US-AriaNeural": "Kore",
        "en-GB-SoniaNeural": "Leda",
        "en-US-EricNeural": "Oran",
        "en-US-RogerNeural": "Zephyr",
    }

    VALID_VOICES = {"Puck", "Charon", "Kore", "Fenrir", "Aoede", "Leda", "Oran", "Zephyr"}

    DIRECTOR_INSTRUCTION = (
        "You are a world-class audiobook narrator. Read the provided text aloud with "
        "authentic emotional depth, natural pacing, clear dialogue distinction, and rich atmospheric nuance."
    )

    def __init__(
        self,
        default_voice: str = "Fenrir",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 4,
        director_instruction: Optional[str] = None,
        **kwargs,
    ):
        self.default_voice = default_voice
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or DEFAULT_GEMINI_MODEL
        self.max_retries = max_retries
        self.director_instruction = director_instruction or self.DIRECTOR_INSTRUCTION

    def resolve_voice(self, voice_name: Optional[str]) -> str:
        if not voice_name:
            return self.default_voice
        if voice_name in self.VALID_VOICES:
            return voice_name
        return self.VOICE_MAP.get(voice_name, self.default_voice)

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        text = chunk.text.strip()
        if not text:
            AudioBuffer.create_silence(duration_ms=max(300, chunk.pause_after_ms)).to_wav_file(output_path)
            return output_path

        api_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise VoiceEngineError("GEMINI_API_KEY is not configured for Gemini voice synthesis.")

        voice = self.resolve_voice(chunk.voice or chunk.character)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": text
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice
                        }
                    }
                },
            },
        }

        if self.director_instruction:
            payload["systemInstruction"] = {
                "parts": [
                    {
                        "text": self.director_instruction
                    }
                ]
            }

        req_data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        last_error = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))

                candidates = resp_data.get("candidates") or []
                if not candidates:
                    raise VoiceEngineError(f"No candidates returned from Gemini API: {resp_data}")

                parts = candidates[0].get("content", {}).get("parts", [])
                audio_inline = None
                for p in parts:
                    if "inlineData" in p:
                        audio_inline = p["inlineData"]
                        break

                if not audio_inline or "data" not in audio_inline:
                    raise VoiceEngineError(f"No inline audio data found in Gemini response: {parts}")

                mime_type = audio_inline.get("mimeType", "").lower()
                raw_bytes = base64.b64decode(audio_inline["data"])

                if "pcm" in mime_type or "l16" in mime_type:
                    # Write 24000Hz 16-bit PCM mono to standard WAV container
                    with wave.open(output_path, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(raw_bytes)
                    return output_path
                elif "wav" in mime_type:
                    with open(output_path, "wb") as f:
                        f.write(raw_bytes)
                    return output_path
                else:
                    temp_in = output_path + ".tmp"
                    with open(temp_in, "wb") as f:
                        f.write(raw_bytes)
                    cmd = ["ffmpeg", "-y", "-i", temp_in, "-ar", "24000", "-ac", "1", output_path]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    finally:
                        if os.path.exists(temp_in):
                            os.remove(temp_in)
                    return output_path

            except Exception as e:
                last_error = e
                # If model not found or unavailable, try fallback TTS model
                if ("404" in str(e) or "not found" in str(e).lower()) and self.model == DEFAULT_GEMINI_MODEL:
                    self.model = FALLBACK_GEMINI_MODEL
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
                time.sleep(0.3 * (2 ** attempt) + random.uniform(0.1, 0.25))

        raise VoiceEngineError(f"Gemini TTS synthesis failed after {self.max_retries} attempts: {last_error}")
