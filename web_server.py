"""Lightweight multi-threaded Web UI server and REST API for Audiobook Narrator."""

import base64
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
import uuid

from .chunker import NarrativeChunker
from .config import (
    AudioFormat,
    PACING_PRESETS,
    PacingMode,
    VOICE_PROFILES,
    VoiceProfile,
)
from .dsp import DEFAULT_SAMPLE_RATE
from .engine import get_voice_engine
from .exporter import AudioExporter
from .parser import DocumentParser, ParsedDocument
from .prosody import ProsodyDirector
from .stitcher import AudioStitcher


JOBS_FILE = "/tmp/audiobook_web_jobs/jobs_db.json"
JOBS: Dict[str, Dict] = {}


def _load_jobs():
    global JOBS
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for jid, job in loaded.items():
                    if job.get("state") in ["INITIALIZING", "SYNTHESIZING"]:
                        job["state"] = "ERROR"
                        job["error"] = "Synthesis interrupted by server restart."
                        job["status_text"] = "Interrupted by server restart."
                JOBS.update(loaded)
        except Exception as e:
            print(f"[WARN] Failed to load jobs database: {e}")


def _save_jobs():
    try:
        os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(JOBS, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save jobs database: {e}")


_load_jobs()


class AudiobookWebHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Audiobook Narrator Studio Web UI & API."""

    def log_message(self, format, *args):
        # Keep terminal clean, only log errors
        if args and str(args[1]).startswith(('4', '5')):
            super().log_message(format, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_web_ui()
        elif path.startswith("/api/status/"):
            job_id = path.split("/api/status/")[1].strip()
            self._handle_get_status(job_id)
        elif path.startswith("/api/audio/"):
            job_id = path.split("/api/audio/")[1].strip()
            self._handle_get_audio(job_id)
        elif path == "/api/jobs/active":
            self._handle_get_active_job()
        elif path == "/api/drive/folders":
            self._handle_get_drive_folders()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == "/api/preview":
            self._handle_preview(data)
        elif path == "/api/inspect":
            self._handle_inspect(data)
        elif path == "/api/synthesize":
            self._handle_synthesize(data)
        elif path == "/api/jobs/clear":
            self._handle_jobs_clear(data)
        elif path == "/api/drive/upload":
            self._handle_drive_upload(data)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def _serve_web_ui(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(current_dir, "web_ui.html")
        if os.path.exists(html_path):
            with open(html_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"web_ui.html not found")

    def _handle_preview(self, data: Dict):
        voice = data.get("voice", "Charon")
        text = data.get("text", "The sky above the port was the color of television, tuned to a dead channel.")
        
        try:
            engine = get_voice_engine(backend="auto", default_voice=voice)
            from .chunker import ChunkType, NarrativeChunk
            chunk = NarrativeChunk(index=0, text=text, chunk_type=ChunkType.EXPOSITION, voice_override=voice)
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                wav_path = os.path.join(tmp_dir, "preview.wav")
                engine.synthesize_chunk(chunk, wav_path)
                
                with open(wav_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                
                resp_json = {
                    "status": "OK",
                    "voice": voice,
                    "audio_b64": f"data:audio/wav;base64,{b64}",
                }
        except Exception as e:
            resp_json = {"status": "ERROR", "error": str(e)}

        self._send_json(resp_json)

    def _handle_inspect(self, data: Dict):
        try:
            url = data.get("url")
            if url:
                doc = DocumentParser.parse_target(url)
            elif data.get("file_content"):
                raw_content = data["file_content"]
                file_name = data.get("file_name", "doc.txt")
                ext = os.path.splitext(file_name)[1].lower()
                is_data_url = isinstance(raw_content, str) and raw_content.startswith("data:")
                is_binary = ext in [".pdf", ".epub"] or is_data_url

                if is_data_url:
                    try:
                        _, b64_payload = raw_content.split(",", 1)
                        byte_data = base64.b64decode(b64_payload)
                    except Exception:
                        byte_data = raw_content.encode("latin1")
                    with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False, mode="wb") as tf:
                        tf.write(byte_data)
                        temp_file = tf.name
                elif is_binary:
                    try:
                        byte_data = base64.b64decode(raw_content)
                    except Exception:
                        byte_data = raw_content.encode("latin1") if isinstance(raw_content, str) else raw_content
                    with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False, mode="wb") as tf:
                        tf.write(byte_data)
                        temp_file = tf.name
                else:
                    with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False, mode="w", encoding="utf-8") as tf:
                        tf.write(raw_content)
                        temp_file = tf.name

                doc = DocumentParser.parse_target(temp_file)
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            else:
                text = data.get("text", "")
                doc = DocumentParser.parse_text(text)

            total_words = sum(len(c.content.split()) for c in doc.chapters)
            estimated_duration_min = round(total_words / 140.0, 1)

            resp_json = {
                "status": "OK",
                "title": doc.title,
                "author": doc.author,
                "chapters_count": len(doc.chapters),
                "chapters": [{"num": c.chapter_num, "title": c.title, "words": len(c.content.split())} for c in doc.chapters],
                "total_words": total_words,
                "estimated_duration_min": estimated_duration_min,
                "sample_preview": doc.chapters[0].content[:250] if doc.chapters else "",
            }
        except Exception as e:
            resp_json = {"status": "ERROR", "error": str(e)}

        self._send_json(resp_json)

    def _handle_synthesize(self, data: Dict):
        job_id = str(uuid.uuid4())[:8]
        JOBS[job_id] = {
            "job_id": job_id,
            "state": "INITIALIZING",
            "progress_percent": 0.0,
            "completed_chunks": 0,
            "total_chunks": 0,
            "status_text": "Decomposing prose manuscript...",
            "title": data.get("title", "Audiobook"),
            "author": data.get("author", "Author"),
            "voice": data.get("voice", "Charon"),
            "audio_file": None,
            "player_file": None,
            "chapters": [],
            "gdrive_url": None,
            "error": None,
        }

        # Spawn background synthesis thread
        _save_jobs()
        t = threading.Thread(target=_run_synthesis_task, args=(job_id, data), daemon=True)
        t.start()

        self._send_json({"status": "OK", "job_id": job_id})

    def _handle_jobs_clear(self, data: Dict):
        job_id = data.get("job_id")
        if job_id and job_id in JOBS:
            JOBS.pop(job_id, None)
        else:
            JOBS.clear()
        _save_jobs()
        self._send_json({"status": "OK", "message": "Jobs cleared"})

    def _handle_get_status(self, job_id: str):
        job = JOBS.get(job_id)
        if not job:
            self._send_json({"status": "ERROR", "error": "Job not found"}, status_code=404)
            return
        self._send_json(job)

    def _handle_get_audio(self, job_id: str):
        job = JOBS.get(job_id)
        if not job or not job.get("audio_file") or not os.path.exists(job["audio_file"]):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Audio file not found or still rendering.")
            return

        file_path = job["audio_file"]
        file_size = os.path.getsize(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        content_type = "audio/mpeg" if ext == ".mp3" else "audio/mp4"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def _handle_get_drive_folders(self):
        folders = AudioExporter.get_recent_gdrive_folders()
        self._send_json({"status": "OK", "folders": folders})

    def _handle_get_active_job(self):
        # Return the most recent or active job
        if not JOBS:
            self._send_json({"status": "NONE"})
            return
        latest_job_id = list(JOBS.keys())[-1]
        self._send_json({"status": "OK", "job": JOBS[latest_job_id]})

    def _handle_drive_upload(self, data: Dict):
        job_id = data.get("job_id")
        job = JOBS.get(job_id)
        if not job or not job.get("audio_file"):
            self._send_json({"status": "ERROR", "error": "No audio file available for upload"}, status_code=400)
            return

        folder_name = data.get("folder_name") or f"{job.get('author', 'Author')} - {job.get('title', 'Audiobook')}"
        files = [job["audio_file"]]
        if job.get("player_file") and os.path.exists(job["player_file"]):
            files.append(job["player_file"])

        try:
            res = AudioExporter.upload_to_gdrive(files, folder_name=folder_name)
            self._send_json({"status": "OK", "results": res})
        except Exception as e:
            self._send_json({"status": "ERROR", "error": str(e)}, status_code=500)

    def _send_json(self, data: Dict, status_code: int = 200):
        content = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)


def _run_synthesis_task(job_id: str, data: Dict):
    job = JOBS[job_id]
    try:
        title = data.get("title") or "Audiobook"
        author = data.get("author") or "Author"
        voice = data.get("voice") or "Charon"
        profile_key = data.get("profile") or "cyberpunk_noir"
        speed = float(data.get("speed", 1.0))
        workers = int(data.get("workers", 8))
        upload_gdrive = data.get("upload_to_gdrive", True)

        # Ingest Document
        if data.get("url"):
            job["status_text"] = f"Ingesting manuscript from {data['url']}..."
            _save_jobs()
            doc = DocumentParser.parse_target(data["url"], title=title, author=author)
        elif data.get("file_content"):
            raw_content = data["file_content"]
            file_name = data.get("file_name", "doc.txt")
            ext = os.path.splitext(file_name)[1].lower()
            is_data_url = isinstance(raw_content, str) and raw_content.startswith("data:")
            is_binary = ext in [".pdf", ".epub"] or is_data_url

            if is_data_url:
                try:
                    _, b64_payload = raw_content.split(",", 1)
                    byte_data = base64.b64decode(b64_payload)
                except Exception:
                    byte_data = raw_content.encode("latin1")
                with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False, mode="wb") as tf:
                    tf.write(byte_data)
                    temp_file = tf.name
            elif is_binary:
                try:
                    byte_data = base64.b64decode(raw_content)
                except Exception:
                    byte_data = raw_content.encode("latin1") if isinstance(raw_content, str) else raw_content
                with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False, mode="wb") as tf:
                    tf.write(byte_data)
                    temp_file = tf.name
            else:
                with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False, mode="w", encoding="utf-8") as tf:
                    tf.write(raw_content)
                    temp_file = tf.name

            job["status_text"] = f"Parsing manuscript {file_name}..."
            _save_jobs()
            doc = DocumentParser.parse_target(temp_file, title=title, author=author)
            try:
                os.remove(temp_file)
            except Exception:
                pass
        else:
            text = data.get("text", "")
            if not text.strip():
                text = "No prose provided."
            job["status_text"] = "Parsing text manuscript..."
            _save_jobs()
            doc = DocumentParser.parse_text(text, title=title, author=author)

        job["title"] = doc.title
        job["author"] = doc.author
        _save_jobs()

        # Resolve Profile
        base_profile = VOICE_PROFILES.get(profile_key, VOICE_PROFILES["cyberpunk_noir"])
        pacing_config = PACING_PRESETS[base_profile.pacing_mode]
        active_profile = VoiceProfile(
            name=base_profile.name,
            voice=voice,
            description=base_profile.description,
            pacing_mode=base_profile.pacing_mode,
            speed=speed,
            pacing=pacing_config,
            system_tone=base_profile.system_tone,
            character_voices=dict(base_profile.character_voices),
        )

        # Chunk & Prosody
        job["status_text"] = "Directing prosody & atomic segmentation..."
        _save_jobs()
        chunker = NarrativeChunker(max_chunk_chars=800, pacing_config=pacing_config)
        director = ProsodyDirector(active_profile)

        all_chunks = []
        for chap in doc.chapters:
            chap_title = chap.title or f"Chapter {chap.chapter_num}"
            chap_content = chap.content.strip()
            chap_text = f"# {chap_title}\n\n{chap_content}"
            chap_chunks = chunker.chunk_text(chap_text, default_voice=voice)
            all_chunks.extend(director.process_chunks(chap_chunks))

        job["total_chunks"] = len(all_chunks)
        job["state"] = "SYNTHESIZING"
        job["status_text"] = f"Synthesizing neural waveforms (0/{len(all_chunks)})..."
        _save_jobs()

        # Synthesis
        engine = get_voice_engine(backend="auto", default_voice=voice)
        stitcher = AudioStitcher(voice_engine=engine, pacing_config=pacing_config, sample_rate=DEFAULT_SAMPLE_RATE)

        out_dir = f"/tmp/audiobook_web_jobs/{job_id}"
        os.makedirs(out_dir, exist_ok=True)
        temp_wav = os.path.join(out_dir, "master.wav")

        def progress_cb(completed: int, total: int, chunk):
            job["completed_chunks"] = completed + 1
            job["progress_percent"] = round(((completed + 1) / float(total)) * 100.0, 1)
            job["status_text"] = f"Synthesizing neural waveforms ({completed + 1}/{total})..."
            if completed % 2 == 0 or (completed + 1) == total:
                _save_jobs()

        stitched = stitcher.assemble_chunks(
            chunks=all_chunks,
            output_wav_path=temp_wav,
            max_workers=workers,
            normalize=True,
            progress_callback=progress_cb,
        )

        # Export & Master
        job["status_text"] = "Mastering broadcast container & HTML player..."
        _save_jobs()
        final_mp3 = os.path.join(out_dir, f"{doc.title.lower().replace(' ', '_')}.mp3")
        outputs = AudioExporter.export(
            stitched_result=stitched,
            output_path=final_mp3,
            output_format=AudioFormat.MP3,
            speed=speed,
            normalize_loudness=True,
            title=doc.title,
            author=doc.author,
            generate_player=True,
            embed_player_audio=True,
        )

        job["audio_file"] = final_mp3
        job["player_file"] = outputs.get("player")
        
        # Build chapter metadata for web player
        chapters_data = []
        if stitched.chapter_timepoints:
            for idx, ch in enumerate(stitched.chapter_timepoints):
                m = int(ch.start_time_sec // 60)
                s = int(ch.start_time_sec % 60)
                chapters_data.append({
                    "index": idx,
                    "title": ch.title,
                    "start_sec": ch.start_time_sec,
                    "timestamp": f"{m:02d}:{s:02d}",
                })
        job["chapters"] = chapters_data
        _save_jobs()

        # Auto-upload to Google Drive
        if upload_gdrive:
            job["status_text"] = "Uploading to Google Drive library..."
            _save_jobs()
            try:
                files_to_upload = [final_mp3]
                if outputs.get("player"):
                    files_to_upload.append(outputs["player"])
                folder_dest = data.get("gdrive_folder_path") or f"{doc.author} - {doc.title}"
                res = AudioExporter.upload_to_gdrive(
                    file_paths=files_to_upload,
                    folder_name=folder_dest,
                )
                for r in res:
                    if r.get("url"):
                        job["gdrive_url"] = r["url"]
                        break
            except Exception as e:
                print(f"[ERROR] Auto-upload to Google Drive failed: {e}")

        job["state"] = "DONE"
        job["progress_percent"] = 100.0
        job["status_text"] = "Audiobook Master Rendered Successfully!"
        _save_jobs()

    except Exception as e:
        job["state"] = "ERROR"
        job["error"] = str(e)
        job["status_text"] = f"Synthesis Fault: {e}"
        _save_jobs()


def start_web_server(port: int = 8765, host: str = "0.0.0.0"):
    """Launch multi-threaded web server."""
    server = ThreadingHTTPServer((host, port), AudiobookWebHandler)
    print(f"\n⚡ Audiobook Narrator Studio Web UI launched at http://localhost:{port}")
    print(f"⚡ Remote Cloudtop Access: http://bataille.c.googlers.com:{port}\n")
    server.serve_forever()


if __name__ == "__main__":
    start_web_server()
