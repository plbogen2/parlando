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

    # Canonical 30 voices supported by Gemini Native Audiogen & VoiceLM
    ALL_30_VOICES = [
        "Puck", "Charon", "Kore", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr",
        "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
        "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
        "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
        "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
    ]

    # Bridge map for translating EdgeTTS neural voice names to Gemini names
    EDGE_TO_GEMINI_MAP = {
        "en-US-ChristopherNeural": "Fenrir",
        "en-US-GuyNeural": "Puck",
        "en-GB-RyanNeural": "Charon",
        "en-US-JennyNeural": "Aoede",
        "en-US-AriaNeural": "Kore",
        "en-GB-SoniaNeural": "Leda",
        "en-US-EricNeural": "Orus",
        "en-US-RogerNeural": "Zephyr",
        "en-US-AvaNeural": "Callirrhoe",
        "en-US-EmmaNeural": "Autonoe",
        "en-US-AndrewNeural": "Enceladus",
        "en-US-BrianNeural": "Iapetus",
        "en-GB-LibbyNeural": "Laomedeia",
        "en-US-AnaNeural": "Despina",
    }

    # Fallback map for translating Gemini names to EdgeTTS names on engine failover
    GEMINI_TO_EDGE_MAP = {
        "Fenrir": "en-US-ChristopherNeural",
        "Puck": "en-US-GuyNeural",
        "Charon": "en-GB-RyanNeural",
        "Aoede": "en-US-JennyNeural",
        "Kore": "en-US-AriaNeural",
        "Leda": "en-GB-SoniaNeural",
        "Orus": "en-US-EricNeural",
        "Oran": "en-US-EricNeural",
        "Zephyr": "en-US-RogerNeural",
        "Callirrhoe": "en-US-AvaNeural",
        "Autonoe": "en-US-EmmaNeural",
        "Enceladus": "en-US-AndrewNeural",
        "Iapetus": "en-US-BrianNeural",
        "Umbriel": "en-US-GuyNeural",
        "Algieba": "en-US-ChristopherNeural",
        "Despina": "en-US-AnaNeural",
        "Erinome": "en-US-AriaNeural",
        "Algenib": "en-US-GuyNeural",
        "Rasalgethi": "en-US-EricNeural",
        "Laomedeia": "en-GB-LibbyNeural",
        "Achernar": "en-US-RogerNeural",
        "Alnilam": "en-US-ChristopherNeural",
        "Schedar": "en-US-JennyNeural",
        "Gacrux": "en-US-GuyNeural",
        "Pulcherrima": "en-US-AriaNeural",
        "Achird": "en-US-RogerNeural",
        "Zubenelgenubi": "en-US-EricNeural",
        "Vindemiatrix": "en-US-JennyNeural",
        "Sadachbia": "en-US-AndrewNeural",
        "Sadaltager": "en-US-AriaNeural",
        "Sulafat": "en-US-JennyNeural",
    }

    def __init__(
        self,
        default_voice: str = "Fenrir",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 4,
        **kwargs,
    ):
        self.default_voice = default_voice
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or DEFAULT_GEMINI_MODEL
        self.max_retries = max_retries

    def resolve_voice(self, voice_name: Optional[str]) -> str:
        if not voice_name:
            return self.default_voice
        return self.EDGE_TO_GEMINI_MAP.get(voice_name, voice_name)

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        text = chunk.text.strip()
        if not text:
            AudioBuffer.create_silence(duration_ms=max(300, chunk.pause_after_ms)).to_wav_file(output_path)
            return output_path

        api_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            # Fallback to EdgeTTS if Gemini API key is missing
            return self._fallback_edge(chunk, output_path, "GEMINI_API_KEY not configured")

        voice = self.resolve_voice(chunk.voice or chunk.character)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"

        # Frame input text with explicit verbatim reading directive to prevent conversational replies
        tts_prompt = f"Read the following text aloud verbatim. Do not reply or add commentary:\n{text}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": tts_prompt
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

            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    pass
                last_error = f"HTTP {e.code}: {err_body or str(e)}"
                if e.code == 429:
                    # Rate limit encountered - sleep briefly or fall back if retries exhausted
                    time.sleep(0.5 * (2 ** attempt) + random.uniform(0.1, 0.3))
                elif e.code in (404, 400) and self.model == DEFAULT_GEMINI_MODEL:
                    self.model = FALLBACK_GEMINI_MODEL
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
                else:
                    time.sleep(0.3 * (2 ** attempt) + random.uniform(0.1, 0.25))

            except Exception as e:
                last_error = e
                time.sleep(0.3 * (2 ** attempt) + random.uniform(0.1, 0.25))

        # Fall back gracefully to EdgeTTS so the chunk is never silent
        return self._fallback_edge(chunk, output_path, f"Gemini synthesis failed ({last_error})")

    def _fallback_edge(self, chunk: NarrativeChunk, output_path: str, reason: str) -> str:
        """Falls back to EdgeTTS engine to guarantee non-silent speech playback."""
        print(f"[WARN] {reason}. Falling back to EdgeTTS for chunk.")
        try:
            from .edge import EdgeVoiceEngine
            resolved_gemini_voice = self.resolve_voice(chunk.voice or chunk.character)
            edge_voice = self.GEMINI_TO_EDGE_MAP.get(resolved_gemini_voice, "en-US-ChristopherNeural")
            edge_engine = EdgeVoiceEngine(default_voice=edge_voice)
            import dataclasses
            fallback_chunk = dataclasses.replace(chunk, voice=edge_voice)
            return edge_engine.synthesize_chunk(fallback_chunk, output_path)
        except Exception as fallback_err:
            print(f"[ERROR] EdgeTTS fallback also failed: {fallback_err}. Falling back to silence pad.")
            AudioBuffer.create_silence(duration_ms=max(500, chunk.pause_after_ms)).to_wav_file(output_path)
            return output_path
