"""Container Encoding, Chapter Metadata Embedding, and EBU R128 Mastering for Parlando."""

import os
import shutil
import subprocess
import tempfile
from typing import List, Optional

from parlando.core.dsp import AudioBuffer
from parlando.core.stitcher import ChapterTimepoint
from parlando.config import AudioFormat


class AudioExporter:
    """Encodes mastered AudioBuffer to M4B/MP3/WAV containers with embedded chapter tracks."""

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def export(
        self,
        audio_buffer: AudioBuffer,
        output_path: str,
        title: str = "Audiobook",
        author: str = "Unknown Author",
        chapter_timepoints: Optional[List[ChapterTimepoint]] = None,
        audio_format: Optional[AudioFormat] = None,
        normalize_loudness: bool = True,
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        ext = os.path.splitext(output_path)[1].lower()

        if audio_format is None:
            if ext == ".m4b":
                audio_format = AudioFormat.M4B
            elif ext == ".mp3":
                audio_format = AudioFormat.MP3
            elif ext == ".wav":
                audio_format = AudioFormat.WAV
            else:
                audio_format = AudioFormat.M4B

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            raw_wav_path = tf.name

        try:
            audio_buffer.to_wav_file(raw_wav_path)

            if audio_format == AudioFormat.WAV:
                shutil.copyfile(raw_wav_path, output_path)
                return output_path

            if not shutil.which("ffmpeg"):
                # Fallback to direct wav if ffmpeg not installed
                shutil.copyfile(raw_wav_path, output_path)
                return output_path

            if audio_format == AudioFormat.M4B:
                return self._export_m4b(raw_wav_path, output_path, title, author, chapter_timepoints, normalize_loudness)
            elif audio_format == AudioFormat.MP3:
                return self._export_mp3(raw_wav_path, output_path, title, author, chapter_timepoints, normalize_loudness)
            else:
                shutil.copyfile(raw_wav_path, output_path)
                return output_path
        finally:
            if os.path.exists(raw_wav_path):
                os.remove(raw_wav_path)

    def _export_m4b(
        self,
        raw_wav: str,
        output_path: str,
        title: str,
        author: str,
        timepoints: Optional[List[ChapterTimepoint]],
        normalize_loudness: bool,
    ) -> str:
        meta_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        try:
            meta_file.write(";FFMETADATA1\n")
            meta_file.write(f"title={title}\n")
            meta_file.write(f"artist={author}\n")
            meta_file.write(f"album_artist={author}\n")
            meta_file.write(f"album={title}\n")
            meta_file.write("genre=Audiobook\n")

            if timepoints:
                for tp in timepoints:
                    meta_file.write("[CHAPTER]\n")
                    meta_file.write("TIMEBASE=1/1000\n")
                    meta_file.write(f"START={tp.start_ms}\n")
                    meta_file.write(f"END={tp.end_ms}\n")
                    meta_file.write(f"title={tp.title}\n")

            meta_file.close()

            cmd = [
                "ffmpeg", "-y",
                "-i", raw_wav,
                "-i", meta_file.name,
                "-map_metadata", "1",
                "-c:a", "aac",
                "-b:a", "96k",
                "-ar", "24000",
            ]
            if normalize_loudness:
                cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])

            cmd.append(output_path)
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        except Exception:
            shutil.copyfile(raw_wav, output_path)
            return output_path
        finally:
            if os.path.exists(meta_file.name):
                os.remove(meta_file.name)

    def _export_mp3(
        self,
        raw_wav: str,
        output_path: str,
        title: str,
        author: str,
        timepoints: Optional[List[ChapterTimepoint]],
        normalize_loudness: bool,
    ) -> str:
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", raw_wav,
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                "-ar", "24000",
                "-metadata", f"title={title}",
                "-metadata", f"artist={author}",
                "-metadata", f"album={title}",
                "-metadata", "genre=Audiobook",
            ]
            if normalize_loudness:
                cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])

            cmd.append(output_path)
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path
        except Exception:
            shutil.copyfile(raw_wav, output_path)
            return output_path

    @classmethod
    def verify_file_speech(cls, filepath: str) -> dict:
        """Decodes any WAV, MP3, or M4B container and runs FFT spectral speech verification."""
        if not os.path.exists(filepath):
            return {"is_speech": False, "reason": "file_not_found"}

        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".wav":
            buf = AudioBuffer.from_wav_file(filepath)
            return buf.analyze_speech_spectrum()

        # For MP3/M4B/etc, decode with ffmpeg into temporary PCM WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tmp_wav = tf.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", filepath,
                "-ac", "1",
                "-ar", "24000",
                "-sample_fmt", "s16",
                tmp_wav
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            buf = AudioBuffer.from_wav_file(tmp_wav)
            return buf.analyze_speech_spectrum()
        except Exception as e:
            return {"is_speech": False, "reason": f"decode_error: {e}"}
        finally:
            if os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except OSError:
                    pass
