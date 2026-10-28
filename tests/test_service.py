import base64
import http.client
import json
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import service


class ValidationTests(unittest.TestCase):
    def test_minimum_request_and_seed(self):
        native, seed = service.validate_request({"prompt": "A tree", "seed": 42}, "moss")
        self.assertEqual(seed, 42)
        self.assertEqual(native["size"], "768x768")
        self.assertEqual(native["n"], 1)

    def test_invalid_requests(self):
        cases = [
            ([], 400), ({"model": "unknown"}, 404), ({"model": []}, 404),
            ({"model": "z-image", "prompt": "tree"}, 409), ({"prompt": " "}, 400),
            ({"prompt": 42}, 400), ({"prompt": "x" * 16001}, 400),
            ({"prompt": "tree", "size": "513x512"}, 400),
            ({"prompt": "tree", "size": "2048x1024"}, 400),
            ({"prompt": "tree", "size": "garbage"}, 400),
            ({"prompt": "tree", "size": None}, 400),
            ({"prompt": "tree", "n": True}, 400), ({"prompt": "tree", "n": 2}, 400),
            ({"prompt": "tree", "seed": True}, 400), ({"prompt": "tree", "seed": -1}, 400),
            ({"prompt": "tree", "seed": 2**31}, 400),
            ({"prompt": "tree", "steps": 10}, 400), ({"prompt": "tree", "quality": "hd"}, 400),
            ({"prompt": "<sd_cpp_extra_args>{}</sd_cpp_extra_args>"}, 400),
            ({"prompt": "<SD_CPP_EXTRA_ARGS>"}, 400), ({"prompt": "<lora:any:1> tree"}, 400),
            ({"prompt": "tree", "response_format": "url"}, 400),
            ({"prompt": "tree", "output_format": "jpeg"}, 400),
            ({"prompt": "tree", "user": 1}, 400)]
        for body, status in cases:
            with self.subTest(body=str(body)[:80]):
                with self.assertRaises(service.APIError) as raised:
                    service.validate_request(body, "moss")
                self.assertEqual(raised.exception.status, status)

    def test_valid_rectangular_size(self):
        native, _ = service.validate_request({"prompt": "tree", "size": "512x768", "user": "client"}, "moss")
        self.assertEqual(native["size"], "512x768")
        self.assertNotIn("user", native)

    def test_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "key"
            path.write_text("secret")
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                service.private_file(path)
            path.chmod(0o600)
            service.private_file(path)


class FakeBackend:
    def __init__(self):
        self.model = "moss"
        self.proc = None
        self.cfg = {"models": {"moss": {}, "z-image": {}}}
        self.failure = None
        self.entered = threading.Event()
        self.release = threading.Event()

    def available(self):
        return True

    def generate(self, native, seed):
        self.entered.set()
        self.release.wait(4)
        return {"created": 0, "data": [{"b64_json": "test-double"}]}


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.server = service.BoundedServer(("127.0.0.1", 0), service.make_handler(self.backend, b"test-key"))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.backend.release.set()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body,
                               headers=headers if headers is not None else {"Authorization": "Bearer test-key", "Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_authentication_and_models(self):
        self.assertEqual(self.request("GET", "/v1/models", headers={})[0], 401)
        self.assertEqual(self.request("GET", "/health", headers={"Authorization": "Bearer wrong"})[0], 401)
        status, result = self.request("GET", "/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in result["data"]], ["moss", "z-image"])

    def test_browser_origin_rejected(self):
        status, _ = self.request("GET", "/health", headers={"Authorization": "Bearer test-key", "Origin": "https://example.org"})
        self.assertEqual(status, 403)

    def test_edit_and_unrelated_endpoints_absent(self):
        for path in ("/v1/images/edits", "/v1/chat/completions", "/sdcpp/v1/models/load"):
            self.assertEqual(self.request("POST", path, "{}")[0], 404)

    def test_malformed_json_and_unknown_size(self):
        self.assertEqual(self.request("POST", "/v1/images/generations", "{")[0], 400)
        self.assertEqual(self.request("POST", "/v1/images/generations", '[1,2]')[0], 400)
        status, result = self.request("POST", "/v1/images/generations", '{"prompt":"tree","size":"bad"}')
        self.assertEqual((status, result["error"]["code"]), (400, "invalid_size"))

    def test_no_generation_queue(self):
        first_result = []
        worker = threading.Thread(target=lambda: first_result.append(self.request(
            "POST", "/v1/images/generations", '{"prompt":"tree"}')))
        worker.start()
        self.assertTrue(self.backend.entered.wait(2))
        start = time.monotonic()
        status, error = self.request("POST", "/v1/images/generations", '{"prompt":"another tree"}')
        self.assertEqual((status, error["error"]["code"]), (429, "generation_busy"))
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(self.request("GET", "/health")[0], 200)
        self.backend.release.set()
        worker.join()
        self.assertEqual(first_result[0][0], 200)

    def test_http_capacity_bounded(self):
        sockets = [socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2) for _ in range(8)]
        try:
            deadline = time.monotonic() + 2
            while len(self.server.pool._threads) < 8 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(self.server.pool._threads), 8)
            status, _ = self.request("GET", "/health")
            self.assertEqual(status, 503)
        finally:
            for connection in sockets:
                connection.close()


class BackendFailureTests(unittest.TestCase):
    def test_missing_model_never_spawns_runtime(self):
        backend = service.Backend({"active_model": "moss", "models": {"moss": {"diffusion": "/no-such-model"}}})
        backend.start()
        self.assertIn("Missing model files", backend.failure)
        self.assertIsNone(backend.proc)

    def test_load_timeout_reaps_own_process(self):
        with tempfile.TemporaryDirectory() as work:
            runtime = Path(work) / "fake-runtime"
            runtime.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(60)\n')
            runtime.chmod(0o700)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            cfg = {"active_model": "moss", "models": {"moss": {}}, "runtime": str(runtime),
                   "cuda_lib": work, "gpu_uuid": "GPU-123", "backend_port": port, "load_timeout": 1}
            backend = service.Backend(cfg)
            with patch.object(service, "gpu_check"), patch.object(service, "foreign_compute", return_value=[]), patch.object(service, "WORK", Path(work)):
                backend.start()
            self.assertIn("deadline", backend.failure)
            self.assertIsNotNone(backend.proc.poll())
            self.assertFalse(backend.available())

    def test_generation_timeout_reaps_own_process(self):
        class SlowHandler(service.BaseHTTPRequestHandler):
            def do_POST(self):
                time.sleep(2)
            def log_message(self, *args):
                pass
        server = service.HTTPServer(("127.0.0.1", 0), SlowHandler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        backend = service.Backend({"active_model": "moss", "backend_port": server.server_port, "generation_timeout": 1})
        backend.proc = process
        backend.ready.set()
        try:
            with self.assertRaises(service.APIError) as raised:
                backend.generate({"prompt": "tree", "size": "512x512"}, 42)
            self.assertEqual(raised.exception.status, 504)
            self.assertIsNotNone(process.poll())
            self.assertFalse(backend.available())
        finally:
            backend.stop()
            thread.join()
            server.server_close()


class InstallationTests(unittest.TestCase):
    def test_install_uninstall_preserves_old_models_images_and_projects(self):
        root = Path(__file__).resolve().parents[1]
        cache = Path.home() / ".cache/local-image-ai-service"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="install-test-", dir=cache) as work:
            home = Path(work)
            protected = [home / ".local/share/local-image-ai/keep.txt",
                         home / "Pictures/AI-Generated/keep.txt", home / "dev/github/riff-racers/keep.txt"]
            for path in protected:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("must remain untouched")
            original_umask = os.umask(0o077)
            def fake_run(args, **kwargs):
                return subprocess.CompletedProcess(args, 3 if "is-active" in args else 0)
            try:
                with patch.object(Path, "home", return_value=home), \
                        patch("subprocess.run", side_effect=fake_run), \
                        patch("subprocess.check_output", return_value="GPU-12345678-1234-1234-1234-123456789abc\n"):
                    runpy.run_path(str(root / "scripts/install.py"), run_name="__main__")
                    config = home / ".config/local-image-ai-service/config.json"
                    self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                    dropin = home / ".config/systemd/user/local-image-ai.service.d/20-bounded-stop.conf"
                    self.assertIn("TimeoutStopFailureMode=kill", dropin.read_text())
                    runpy.run_path(str(root / "scripts/uninstall.py"), run_name="__main__")
                self.assertFalse(config.exists())
                self.assertFalse(dropin.exists())
                self.assertFalse((home / ".local/share/local-image-ai-service").exists())
                for path in protected:
                    self.assertEqual(path.read_text(), "must remain untouched")
            finally:
                os.umask(original_umask)


if __name__ == "__main__":
    unittest.main()
