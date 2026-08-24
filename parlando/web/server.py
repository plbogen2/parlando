"""Multi-threaded Web Studio UI server and REST API microservice for Parlando."""

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

from parlando.config import (
    AudioFormat,
    PACING_PRESETS,
    PacingConfig,
    PacingMode,
    VALID_NEURAL_VOICES,
    VOICE_PROFILES,
    VoiceProfile,
)
from parlando.core import ChunkType, NarrativeChunk, ProsodyDirector
from parlando.engines import get_voice_engine
from parlando.parsers import DocumentParser, ParsedDocument
from parlando.pipeline import AudiobookPipeline, PipelineConfig


class JobManager:
    """Thread-safe persistent job state manager for Parlando synthesis tasks."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join(tempfile.gettempdir(), "parlando_web_jobs", "jobs_db.json")
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for jid, job in loaded.items():
                        if job.get("state") in ["INITIALIZING", "SYNTHESIZING"]:
                            job["state"] = "ERROR"
                            job["error"] = "Synthesis interrupted by server restart."
                            job["status_text"] = "Interrupted by server restart."
                    self._jobs.update(loaded)
            except Exception:
                pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._jobs, f, indent=2)
        except Exception:
            pass

    def get(self, job_id: str) -> Optional[Dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def create(self, title: str, author: str) -> Dict:
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "state": "INITIALIZING",
            "progress": 0.0,
            "current_chunk": 0,
            "total_chunks": 0,
            "status_text": "Queued for synthesis...",
            "title": title or "Audiobook",
            "author": author or "Unknown",
            "created_at": time.time(),
        }
        with self._lock:
            self._jobs[job_id] = job
            self._save()
        return job

    def update(self, job_id: str, **kwargs):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)
                self._save()

    def get_active(self) -> Optional[Dict]:
        with self._lock:
            for jid, job in reversed(list(self._jobs.items())):
                if job.get("state") in ["INITIALIZING", "SYNTHESIZING"]:
                    return dict(job)
        return None

    def clear(self):
        with self._lock:
            self._jobs.clear()
            self._save()


GLOBAL_JOB_MANAGER = JobManager()
JOBS = GLOBAL_JOB_MANAGER._jobs


class AudiobookWebHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Parlando Studio Web UI & REST API."""

    def log_message(self, format, *args):
        if args and str(args[1]).startswith(('4', '5')):
            super().log_message(format, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_web_ui()
        elif path.startswith("/api/status/"):
            job_id = path.split("/api/status/")[1].strip()
            self._handle_get_status(job_id)
        elif path.startswith("/api/audio/"):
            job_id = path.split("/api/audio/")[1].strip()
            self._handle_get_audio(job_id)
        elif path == "/api/jobs/active":
            self._handle_get_active_job()
        elif path == "/api/voices":
            self._handle_get_voices()
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

        if path == "/api/synthesize":
            self._handle_synthesize(data)
        elif path == "/api/preview":
            self._handle_preview(data)
        elif path == "/api/inspect":
            self._handle_inspect(data)
        elif path == "/api/jobs/clear":
            self._handle_jobs_clear()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def _serve_web_ui(self):
        static_html_path = os.path.join(os.path.dirname(__file__), "static", "web_ui.html")
        if not os.path.exists(static_html_path):
            # Fallback to root if running in legacy flat layout
            static_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web_ui.html")

        if os.path.exists(static_html_path):
            with open(static_html_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Web UI static assets not found.")

    def _handle_get_voices(self):
        data = {
            "voices": VALID_NEURAL_VOICES,
            "profiles": list(VOICE_PROFILES.keys()),
            "pacing": [p.value for p in PacingMode],
        }
        self._send_json(200, data)

    def _handle_get_status(self, job_id: str):
        job = GLOBAL_JOB_MANAGER.get(job_id)
        if not job:
            self._send_json(404, {"error": "Job not found"})
            return
        self._send_json(200, job)

    def _handle_get_active_job(self):
        active = GLOBAL_JOB_MANAGER.get_active()
        if active:
            self._send_json(200, active)
        else:
            self._send_json(200, {"active": False})

    def _handle_jobs_clear(self):
        GLOBAL_JOB_MANAGER.clear()
        self._send_json(200, {"success": True, "message": "All job history cleared."})

    def _handle_get_audio(self, job_id: str):
        job = GLOBAL_JOB_MANAGER.get(job_id)
        if not job or not job.get("audio_path") or not os.path.exists(job["audio_path"]):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Audio file not found")
            return

        audio_path = job["audio_path"]
        ext = os.path.splitext(audio_path)[1].lower()
        mime_type = "audio/mp4" if ext == ".m4b" else ("audio/mpeg" if ext == ".mp3" else "audio/wav")

        with open(audio_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(content)

    def _handle_get_drive_folders(self):
        # Stub for drive list
        self._send_json(200, {"folders": []})

    def _handle_inspect(self, data: Dict):
        try:
            doc = self._parse_payload_doc(data)
            chapters_info = [{"title": c.title, "words": c.word_count, "index": c.chapter_index} for c in doc.chapters]
            self._send_json(200, {
                "title": doc.title,
                "author": doc.author,
                "total_words": doc.total_words,
                "total_chapters": doc.total_chapters,
                "chapters": chapters_info,
                "source_type": doc.source_type,
            })
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def _handle_preview(self, data: Dict):
        try:
            text = (data.get("text") or "").strip()
            if not text and (data.get("url") or data.get("file_path") or data.get("file_content_b64")):
                doc = self._parse_payload_doc(data)
                audition_doc = doc.get_audition_excerpt(max_words=150)
                text = audition_doc.chapters[0].content

            if not text:
                self._send_json(400, {"error": "No text provided for synthesis"})
                return

            api_key = data.get("api_key") or data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
            backend = data.get("backend")
            if not backend:
                backend = "gemini" if api_key else "edge"
            voice = data.get("voice") or ("Fenrir" if backend == "gemini" else "en-US-ChristopherNeural")
            model = data.get("model")
            pacing = PacingMode(data.get("pacing", "normal"))
            speed = float(data.get("speed", 1.0))

            # Fast-path for single-chunk narration (< 1500 chars, no chapter headings)
            if len(text) < 1500 and not text.startswith("#"):
                engine = get_voice_engine(backend, default_voice=voice, api_key=api_key, model=model)
                chunk = NarrativeChunk(
                    text=text,
                    chunk_type=ChunkType.NARRATION,
                    character=voice,
                    chunk_index=0,
                )
                pacing_cfg = PACING_PRESETS.get(pacing, PacingConfig())
                pacing_cfg.speed_multiplier = speed
                director = ProsodyDirector(
                    voice_profile=VoiceProfile(name="custom", primary_voice=voice),
                    pacing=pacing_cfg,
                )
                director.apply_to_chunk(chunk)

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    out_wav = tf.name

                try:
                    engine.synthesize_chunk(chunk, out_wav)
                    with open(out_wav, "rb") as f:
                        wav_b64 = base64.b64encode(f.read()).decode("utf-8")
                finally:
                    if os.path.exists(out_wav):
                        os.remove(out_wav)

                self._send_json(200, {
                    "audio_base64": f"data:audio/wav;base64,{wav_b64}",
                    "text_sample": text[:200],
                    "voice": voice,
                    "backend": backend,
                })
                return

            config = PipelineConfig(
                backend=backend,
                voice=voice,
                pacing_mode=pacing,
                speed=speed,
                audio_format=AudioFormat.WAV,
                audition=False,
                api_key=api_key,
                model=model,
                generate_player=False,
            )
            pipeline = AudiobookPipeline(config)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                out_wav = tf.name

            try:
                pipeline.run(text, output_path=out_wav)
                with open(out_wav, "rb") as f:
                    wav_b64 = base64.b64encode(f.read()).decode("utf-8")
            finally:
                if os.path.exists(out_wav):
                    os.remove(out_wav)

            self._send_json(200, {
                "audio_base64": f"data:audio/wav;base64,{wav_b64}",
                "text_sample": text[:200],
                "voice": voice,
                "backend": backend,
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_synthesize(self, data: Dict):
        job = GLOBAL_JOB_MANAGER.create(
            title=data.get("title", "Audiobook"),
            author=data.get("author", "Unknown"),
        )
        job_id = job["id"]

        worker_thread = threading.Thread(target=self._run_synthesis_task, args=(job_id, data), daemon=True)
        worker_thread.start()

        self._send_json(202, {"job_id": job_id, "status": "QUEUED"})

    def _run_synthesis_task(self, job_id: str, data: Dict):
        try:
            GLOBAL_JOB_MANAGER.update(
                job_id,
                state="SYNTHESIZING",
                status_text="Parsing manuscript...",
            )

            doc = self._parse_payload_doc(data)
            if data.get("title"):
                doc.title = data["title"]
            if data.get("author"):
                doc.author = data["author"]

            chapters_data = [{"title": c.title, "words": c.word_count, "index": c.chapter_index} for c in doc.chapters]
            GLOBAL_JOB_MANAGER.update(
                job_id,
                title=doc.title,
                author=doc.author,
                total_words=doc.total_words,
                total_chapters=doc.total_chapters,
                chapters=chapters_data,
            )

            api_key = data.get("api_key") or data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
            backend = data.get("backend")
            if not backend:
                backend = "gemini" if api_key else "edge"
            voice = data.get("voice") or ("Fenrir" if backend == "gemini" else "en-US-ChristopherNeural")
            model = data.get("model")
            dialogue_voice = data.get("dialogue_voice")
            pacing = PacingMode(data.get("pacing", "normal"))
            speed = float(data.get("speed", 1.0))
            fmt_str = data.get("format", "m4b").lower()
            audio_format = AudioFormat.MP3 if fmt_str == "mp3" else AudioFormat.M4B

            config = PipelineConfig(
                backend=backend,
                voice=voice,
                dialogue_voice=dialogue_voice,
                pacing_mode=pacing,
                speed=speed,
                audio_format=audio_format,
                api_key=api_key,
                model=model,
                audition=data.get("audition", False),
            )
            pipeline = AudiobookPipeline(config)

            job_out_dir = os.path.join(tempfile.gettempdir(), "parlando_web_jobs", job_id)
            os.makedirs(job_out_dir, exist_ok=True)
            clean_title = "".join(c if c.isalnum() else "_" for c in doc.title.lower()).strip("_")
            out_file = os.path.join(job_out_dir, f"{clean_title}.{audio_format.value}")

            def _progress_cb(curr, total, sample_text):
                GLOBAL_JOB_MANAGER.update(
                    job_id,
                    current_chunk=curr,
                    total_chunks=total,
                    progress=round((curr / max(1, total)) * 100, 1),
                    status_text=f"Synthesizing: {sample_text}...",
                )

            full_text = "\n\n".join(f"# {c.title}\n\n{c.content}" if c.title else c.content for c in doc.chapters)
            res = pipeline.run(full_text, output_path=out_file, progress_callback=_progress_cb)

            timepoints_data = [
                {"title": tp.title, "start_ms": tp.start_ms, "end_ms": tp.end_ms, "chapter_index": tp.chapter_index}
                for tp in res.chapter_timepoints
            ]

            GLOBAL_JOB_MANAGER.update(
                job_id,
                state="COMPLETE",
                progress=100.0,
                status_text="Render complete!",
                audio_path=res.audio_path,
                player_path=res.player_path,
                duration_seconds=res.duration_seconds,
                render_time_seconds=res.render_time_seconds,
                chapter_timepoints=timepoints_data,
            )
        except Exception as e:
            GLOBAL_JOB_MANAGER.update(
                job_id,
                state="ERROR",
                error=str(e),
                status_text=f"Failed: {e}",
            )

    def _parse_payload_doc(self, data: Dict) -> ParsedDocument:
        if data.get("url"):
            return DocumentParser.from_url(data["url"])
        elif data.get("file_path"):
            return DocumentParser.from_file_or_url(data["file_path"])
        elif data.get("file_content_b64"):
            content_bytes = base64.b64decode(data["file_content_b64"])
            filename = data.get("filename", "upload.txt")
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            with open(temp_path, "wb") as f:
                f.write(content_bytes)
            doc = DocumentParser.from_file_or_url(temp_path)
            os.remove(temp_path)
            return doc
        else:
            text = data.get("text", "")
            title = data.get("title", "Untitled Manuscript")
            author = data.get("author", "Unknown Author")
            return DocumentParser.from_text(text, title=title, author=author)

    def _send_json(self, status: int, data: Dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def start_web_studio(port: int = 8765, host: str = "0.0.0.0"):
    server = ThreadingHTTPServer((host, port), AudiobookWebHandler)
    print(f"🚀 Parlando Web Audio Studio running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Parlando studio.")
        server.server_close()
