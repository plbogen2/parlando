"""Audio format conversion, playback speed manipulation, chapter metadata, and Google Drive upload."""

import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional
from .config import AudioFormat
from .player import HTMLPlayerGenerator
from .stitcher import ChapterTimepoint, StitchedAudioResult


class AudioExporterError(Exception):
    """Raised when audio conversion or tagging fails."""
    pass


class AudioExporter:
    """Encodes master WAV audio into MP3, M4B, AAC, FLAC with embedded chapter metadata and HTML players."""

    @classmethod
    def export(
        cls,
        stitched_result: StitchedAudioResult,
        output_path: str,
        output_format: AudioFormat = AudioFormat.MP3,
        speed: float = 1.0,
        normalize_loudness: bool = True,
        title: str = "Audiobook",
        author: str = "Unknown Author",
        series: Optional[str] = None,
        year: Optional[int] = None,
        generate_player: bool = True,
        embed_player_audio: bool = False,
    ) -> Dict[str, str]:
        """Process, encode master WAV into requested audio format, and generate HTML player by default."""
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)
        fmt = output_format.value.lower()

        # Build ffmpeg audio filter graph
        filters = []
        if abs(speed - 1.0) > 0.01:
            speed_clamped = max(0.5, min(2.0, speed))
            filters.append(f"atempo={speed_clamped:.3f}")

        if normalize_loudness:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        filter_arg = ["-af", ",".join(filters)] if filters else []

        # Create FFMETADATA file for chapter markers
        meta_file = cls._generate_ffmetadata(
            title=title,
            author=author,
            series=series,
            year=year,
            chapter_timepoints=stitched_result.chapter_timepoints,
            speed=speed,
        )

        outputs = {}

        try:
            cmd = ["ffmpeg", "-y", "-i", stitched_result.master_wav_path]

            if meta_file and os.path.exists(meta_file):
                cmd.extend(["-i", meta_file, "-map_metadata", "1"])

            cmd.extend(filter_arg)

            if fmt == "mp3":
                cmd.extend([
                    "-codec:a", "libmp3lame",
                    "-b:a", "192k",
                    "-id3v2_version", "3",
                    "-metadata", f"title={title}",
                    "-metadata", f"artist={author}",
                    "-metadata", f"album={title}",
                    "-metadata", f"album_artist={author}",
                ])
            elif fmt == "m4b" or fmt == "m4a":
                cmd.extend([
                    "-codec:a", "aac",
                    "-b:a", "128k",
                    "-f", "mp4",
                    "-metadata", f"title={title}",
                    "-metadata", f"artist={author}",
                    "-metadata", f"album={title}",
                ])
            elif fmt == "aac":
                cmd.extend([
                    "-codec:a", "aac",
                    "-b:a", "192k",
                    "-metadata", f"title={title}",
                    "-metadata", f"artist={author}",
                ])
            elif fmt == "flac":
                cmd.extend([
                    "-codec:a", "flac",
                    "-metadata", f"title={title}",
                    "-metadata", f"artist={author}",
                ])
            elif fmt == "wav":
                cmd.extend([
                    "-codec:a", "pcm_s16le",
                ])
            else:
                cmd.extend(["-codec:a", "libmp3lame", "-b:a", "192k"])

            cmd.append(output_path)

            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise AudioExporterError(f"FFmpeg encoding failed ({proc.returncode}): {proc.stderr}")

            outputs["audio"] = output_path

            # Generate HTML Player Console by default
            if generate_player:
                base_name = os.path.splitext(os.path.basename(output_path))[0]
                player_filename = f"{base_name}_player.html"
                player_path = os.path.join(out_dir, player_filename)
                
                HTMLPlayerGenerator.generate(
                    stitched_result=stitched_result,
                    audio_file_path=output_path,
                    output_html_path=player_path,
                    title=title,
                    author=author,
                    embed_audio=embed_player_audio,
                    voice_info="Studio Master",
                )
                outputs["player"] = player_path

                # Also create index.html in output directory for instant web server hosting
                index_path = os.path.join(out_dir, "index.html")
                shutil.copyfile(player_path, index_path)
                outputs["index"] = index_path

            return outputs
        finally:
            if meta_file and os.path.exists(meta_file):
                os.remove(meta_file)

    @classmethod
    def resolve_or_create_gdrive_path(
        cls,
        path_str: str,
        target_user: Optional[str] = None,
    ) -> str:
        """Traverse and create a nested Google Drive folder path hierarchy (e.g. 'Audiobooks/Sci Fi/Author')."""
        gdrive_bin = "/google/bin/releases/gemini-agents-gdrive/gdrive"
        if not os.path.exists(gdrive_bin):
            gdrive_bin = shutil.which("gdrive")
        if not gdrive_bin:
            raise AudioExporterError("gdrive CLI binary not found.")

        # If it looks like a direct Drive Folder ID (e.g. alphanumeric with len >= 25 without slashes)
        clean = path_str.strip()
        if len(clean) >= 25 and "/" not in clean and "\\" not in clean and " " not in clean:
            return clean

        parts = [p.strip() for p in clean.replace("\\", "/").split("/") if p.strip()]
        if not parts:
            return ""

        current_parent_id = None
        for part in parts:
            cmd = [gdrive_bin, "readonly", "search", "--name-exact", part, "--type", "folder", "--json"]
            if target_user:
                cmd.extend(["--target_user", target_user])
            res = subprocess.run(cmd, capture_output=True, text=True)
            found_id = None
            if res.returncode == 0 and res.stdout.strip():
                try:
                    import json
                    folders = json.loads(res.stdout)
                    for f in folders:
                        found_id = f.get("id")
                        break
                except Exception:
                    pass

            if found_id:
                current_parent_id = found_id
            else:
                mkdir_cmd = [gdrive_bin, "mutate", "mkdir", part]
                if current_parent_id:
                    mkdir_cmd.extend(["--parent", current_parent_id])
                if target_user:
                    mkdir_cmd.extend(["--target_user", target_user])
                m_res = subprocess.run(mkdir_cmd, capture_output=True, text=True)
                if m_res.returncode == 0:
                    for token in m_res.stdout.split():
                        if len(token) >= 20 and not token.startswith("http"):
                            current_parent_id = token
                            break
                else:
                    raise AudioExporterError(f"Failed to create Drive folder '{part}': {m_res.stderr or m_res.stdout}")

        return current_parent_id or ""

    @classmethod
    def upload_to_gdrive(
        cls,
        file_paths: List[str],
        parent_folder_id: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_name: Optional[str] = None,
        target_user: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Upload audiobooks and HTML players to Google Drive via gdrive CLI."""
        gdrive_bin = "/google/bin/releases/gemini-agents-gdrive/gdrive"
        if not os.path.exists(gdrive_bin):
            gdrive_bin = shutil.which("gdrive")

        if not gdrive_bin:
            raise AudioExporterError("gdrive CLI binary not found. Ensure gemini-agents-gdrive is available.")

        target_parent = parent_folder_id

        # 1. Resolve folder_path if provided (e.g. 'Audiobooks/Sci Fi/Charles Stross')
        if folder_path and not target_parent:
            target_parent = cls.resolve_or_create_gdrive_path(folder_path, target_user=target_user)

        # 2. If a folder_name is provided and no parent_folder_id, create or search for it
        if folder_name and not target_parent:
            target_parent = cls.resolve_or_create_gdrive_path(folder_name, target_user=target_user)

        results = []
        for fp in file_paths:
            if not os.path.exists(fp):
                continue
            upload_cmd = [gdrive_bin, "mutate", "upload", fp]
            if target_parent:
                upload_cmd.extend(["--parent", target_parent])
            if target_user:
                upload_cmd.extend(["--target_user", target_user])

            proc = subprocess.run(upload_cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                file_id = ""
                for part in proc.stdout.split():
                    if len(part) >= 20 and not part.startswith("http"):
                        file_id = part
                        break
                
                url = f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""
                results.append({
                    "file_path": fp,
                    "file_name": os.path.basename(fp),
                    "file_id": file_id,
                    "url": url,
                    "status": "UPLOADED",
                })
            else:
                results.append({
                    "file_path": fp,
                    "file_name": os.path.basename(fp),
                    "error": proc.stderr.strip() or proc.stdout.strip(),
                    "status": "FAILED",
                })

        return results

    @classmethod
    def _generate_ffmetadata(
        cls,
        title: str,
        author: str,
        series: Optional[str],
        year: Optional[int],
        chapter_timepoints: List[ChapterTimepoint],
        speed: float = 1.0,
    ) -> Optional[str]:
        """Create an FFMETADATA formatted chapter file for ffmpeg."""
        if not chapter_timepoints:
            return None

        fd, path = tempfile.mkstemp(prefix="ffmetadata_", suffix=".txt")
        lines = [
            ";FFMETADATA1",
            f"title={title}",
            f"artist={author}",
            f"album={title}",
        ]
        if series:
            lines.append(f"series={series}")
        if year:
            lines.append(f"date={year}")

        time_scale = 1.0 / speed if speed > 0 else 1.0

        for ct in chapter_timepoints:
            start_ms = int(ct.start_time_sec * 1000.0 * time_scale)
            end_ms = int(ct.end_time_sec * 1000.0 * time_scale)
            lines.extend([
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start_ms}",
                f"END={end_ms}",
                f"title={ct.title}",
            ])

        content = "\n".join(lines) + "\n"
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)

        return path
