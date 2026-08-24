"""Unit tests for Parlando Web Studio HTTP handler and REST API endpoints."""

import io
import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from parlando.web.server import AudiobookWebHandler, JOBS


class WebServerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Bind to random local port for tests
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), AudiobookWebHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, path: str, data: dict) -> dict:
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_get_voices(self):
        res = self._get("/api/voices")
        self.assertIn("voices", res)
        self.assertIn("profiles", res)
        self.assertIn("pacing", res)

    def test_inspect_endpoint(self):
        payload = {
            "text": "# Chapter 1: Arrival\n\nThe sky was neon green.\n\n# Chapter 2: The Deck\n\nHe jacked in.",
            "title": "Neuromancer Preview",
            "author": "William Gibson",
        }
        res = self._post("/api/inspect", payload)
        self.assertEqual(res["title"], "Neuromancer Preview")
        self.assertEqual(res["total_chapters"], 2)
        self.assertEqual(len(res["chapters"]), 2)

    def test_jobs_clear_endpoint(self):
        res = self._post("/api/jobs/clear", {})
        self.assertTrue(res.get("success"))

    def test_preview_endpoint(self):
        # Test preview with mock engine
        payload = {
            "text": "Hello world from test suite",
            "backend": "mock",
            "voice": "mock-narrator",
        }
        res = self._post("/api/preview", payload)
        self.assertIn("audio_base64", res)
        self.assertTrue(res["audio_base64"].startswith("data:audio/wav;base64,"))
        self.assertEqual(res["backend"], "mock")

    def test_job_manager(self):
        from parlando.web.server import JobManager
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json") as tf:
            db_path = tf.name
        jm = JobManager(storage_path=db_path)
        job = jm.create(title="Test Book", author="Test Author")
        self.assertEqual(job["title"], "Test Book")
        self.assertEqual(job["state"], "INITIALIZING")
        
        jm.update(job["id"], state="COMPLETE", progress=100.0)
        fetched = jm.get(job["id"])
        self.assertEqual(fetched["state"], "COMPLETE")
        self.assertEqual(fetched["progress"], 100.0)
        
        jm.clear()
        self.assertIsNone(jm.get(job["id"]))


if __name__ == "__main__":
    unittest.main()
