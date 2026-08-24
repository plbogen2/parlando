"""Google Gemini / Cloud TTS engine adapter."""

import os
import subprocess
from typing import Optional

from parlando.core.chunker import NarrativeChunk
from .base import BaseVoiceEngine, VoiceEngineError


class GeminiVoiceEngine(BaseVoiceEngine):
    """Adapter for Google Cloud / Gemini TTS synthesis."""

    def __init__(self, default_voice: str = "Fenrir"):
        self.default_voice = default_voice

    def synthesize_chunk(self, chunk: NarrativeChunk, output_path: str) -> str:
        # Check for local beyond or gemini CLI if present, or fallback
        generate_bin = "/google/bin/releases/gemini-agents-generate/generate"
        voice = chunk.character or self.default_voice

        if os.path.exists(generate_bin):
            cmd = [generate_bin, "--type=audio", f"--prompt={chunk.text}", f"--output_file={output_path}", f"--voice={voice}"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        
        raise VoiceEngineError("Google Gemini voice backend requires internal environment or Cloud API credentials.")
