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
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import service


class ValidationTests(unittest.TestCase):
    def test_minimum_request_and_seed(self):
        native, seed = service.validate_request({"prompt": "A tree", "seed": 42}, "moss")
        self.assertEqual(seed, 42)
        self.assertEqual(native["size"], "1024x1024")
        self.assertEqual(native["n"], 1)

    def test_invalid_requests(self):
        cases = [
            ([], 400), ({"model": "unknown"}, 404), ({"model": []}, 404),
            ({"model": "z-image", "prompt": "tree"}, 404), ({"prompt": " "}, 400),
            ({"prompt": 42}, 400), ({"prompt": "x" * 16001}, 400),
            ({"prompt": "tree", "size": "513x512"}, 400),
            ({"prompt": "tree", "size": "2048x1024"}, 400),
            ({"prompt": "tree", "size": "garbage"}, 400),
            ({"prompt": "tree", "size": None}, 400),
            ({"prompt": "tree", "n": True}, 400), ({"prompt": "tree", "n": 2}, 400),
            ({"prompt": "tree", "seed": True}, 400), ({"prompt": "tree", "seed": -1}, 400),
            ({"prompt": "tree", "seed": 2**31}, 400),
            ({"prompt": "tree", "steps": 0}, 400), ({"prompt": "tree", "quality": "hd"}, 400),
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

    def test_configuration_rejects_unknown_model(self):
        root = Path(__file__).resolve().parents[1]
        cfg = json.loads((root / "config/config.example.json").read_text())
        cfg["gpu_uuid"] = "GPU-1234"
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "config.json"
            path.write_text(json.dumps(cfg))
            path.chmod(0o600)
            self.assertEqual(set(service.load_config(path)["models"]), {"moss"})
            cfg["models"]["z-image"] = dict(cfg["models"]["moss"])
            path.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, "Only curated"):
                service.load_config(path)

    def test_sampling_defaults_and_explicit_settings(self):
        self.assertEqual(service.sampling_settings({}), {"steps": 50, "cfg": 3.0})
        self.assertEqual(service.sampling_settings({"sampling": {"steps": 30, "cfg": 4}}),
                         {"steps": 30, "cfg": 4})

    def test_invalid_sampling_is_rejected_during_config_load(self):
        root = Path(__file__).resolve().parents[1]
        cfg = json.loads((root / "config/config.example.json").read_text())
        cfg["gpu_uuid"] = "GPU-1234"
        cases = [None, [], {}, {"steps": 50}, {"steps": 50, "cfg": 3, "sampler": "random"}]
        cases += [{"steps": value, "cfg": 3} for value in (True, 9, 101, 50.5, "50")]
        cases += [{"steps": 50, "cfg": value} for value in (True, 0, 7, "3", float("nan"), float("inf"))]
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "config.json"
            for settings in cases:
                with self.subTest(settings=settings):
                    cfg["sampling"] = settings
                    path.write_text(json.dumps(cfg))
                    path.chmod(0o600)
                    with self.assertRaisesRegex(ValueError, "sampling"):
                        service.load_config(path)


class DirectGenerationTests(unittest.TestCase):
    def test_backend_restart_accepts_a_port_with_recently_closed_connections(self):
        root = Path(__file__).resolve().parents[1]
        cfg = json.loads((root / "config/config.example.json").read_text())
        cfg["sampling"] = {"steps": 30, "cfg": 4}
        with socket.socket() as listener:
            # Match cpp-httplib's Linux listener options in the pinned native runtime.
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            cfg["backend_port"] = listener.getsockname()[1]
            with socket.create_connection(listener.getsockname()) as client:
                connection, _ = listener.accept()
                connection.shutdown(socket.SHUT_WR)
                self.assertEqual(client.recv(1), b"")
            connection.close()
        # Prove this is an actual TIME_WAIT regression, rather than an unused free port.
        with socket.socket() as probe:
            with self.assertRaises(OSError):
                probe.bind(("127.0.0.1", cfg["backend_port"]))
        backend = service.Backend(cfg)
        process = Mock(pid=12345, returncode=1)
        process.poll.return_value = 1
        with patch.object(service, "missing_files", return_value=[]), \
                patch.object(service, "foreign_compute", return_value=[]), \
                patch.object(service, "gpu_check"), \
                patch.object(service.subprocess, "Popen", return_value=process) as launch:
            backend.start()
        launch.assert_called_once()
        arguments = launch.call_args.args[0]
        for option, expected in (("--steps", "30"), ("--cfg-scale", "4"), ("--scheduler", "discrete"), ("--flow-shift", "5")):
            self.assertEqual(arguments[arguments.index(option) + 1], expected)
        self.assertEqual(backend.failure, "sd-server exited during load: 1")

    def test_backend_start_refuses_an_existing_listener(self):
        root = Path(__file__).resolve().parents[1]
        cfg = json.loads((root / "config/config.example.json").read_text())
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            cfg["backend_port"] = listener.getsockname()[1]
            backend = service.Backend(cfg)
            with patch.object(service, "missing_files", return_value=[]), \
                    patch.object(service, "foreign_compute", return_value=[]), \
                    patch.object(service, "gpu_check"), \
                    patch.object(service.subprocess, "Popen") as launch:
                backend.start()
            launch.assert_not_called()
            self.assertEqual(backend.failure, "Backend port is already in use")

    def test_image_bytes_are_returned_without_a_reviewer_or_extra_process(self):
        from test_cli import png_bytes
        raw = png_bytes()
        encoded = base64.b64encode(raw).decode()
        payload = {"created": 0, "output_format": "png", "data": [{"b64_json": encoded}]}
        response = Mock(status=200)
        response.read.return_value = json.dumps(payload).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        backend = service.Backend({"active_model": "moss", "backend_port": 17861, "generation_timeout": 10})
        with patch.object(backend, "available", return_value=True), \
                patch.object(service.http.client, "HTTPConnection", return_value=connection), \
                patch.object(service.subprocess, "Popen") as process:
            result = backend.generate({"prompt": "A humanoid with three arms", "size": "256x256"}, 42)
        self.assertEqual(base64.b64decode(result["data"][0]["b64_json"]), raw)
        self.assertNotIn("anatomy_check", result)
        self.assertEqual(result["model"], "moss")
        process.assert_not_called()


class FakeBackend:
    def __init__(self):
        self.model = "moss"
        self.proc = None
        self.cfg = {"models": {"moss": {}}}
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
        self.assertEqual([row["id"] for row in result["data"]], ["moss"])

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
    def test_upgrade_removes_retired_config_and_code_but_preserves_model_files(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            home = Path(work)
            config = home / ".config/local-image-ai-service/config.json"
            config.parent.mkdir(parents=True)
            cfg = json.loads((root / "config/config.example.json").read_text())
            cfg.update(active_model="z-image", port=17888, anatomy={"enabled": True})
            cfg["models"]["z-image"] = dict(cfg["models"]["moss"])
            config.write_text(json.dumps(cfg))
            config.chmod(0o600)
            retired = home / ".local/share/local-image-ai-service/app/anatomy.py"
            retired.parent.mkdir(parents=True)
            retired.write_text("retired checker")
            preserved = [home / ".local/share/local-image-ai/models/z-image/keep.gguf",
                         home / ".local/share/local-image-ai-service/anatomy/models/keep.gguf"]
            for path in preserved:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"keep model data")
            original_umask = os.umask(0o077)
            try:
                with patch.object(Path, "home", return_value=home), \
                        patch("subprocess.run", side_effect=lambda command, **kwargs:
                              subprocess.CompletedProcess(command, 3 if "is-active" in command else 0)):
                    runpy.run_path(str(root / "scripts/install.py"), run_name="__main__")
            finally:
                os.umask(original_umask)
            migrated = json.loads(config.read_text())
            self.assertEqual(migrated["active_model"], "moss")
            self.assertEqual(set(migrated["models"]), {"moss"})
            self.assertNotIn("anatomy", migrated)
            self.assertEqual(migrated["port"], 17888)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertFalse(retired.exists())
            for path in preserved:
                self.assertEqual(path.read_bytes(), b"keep model data")

    def test_install_uninstall_preserves_old_models_images_and_projects(self):
        root = Path(__file__).resolve().parents[1]
        cache = Path.home() / ".cache/local-image-ai-service"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="install-test-", dir=cache) as work:
            home = Path(work)
            protected = [home / ".local/share/local-image-ai/keep.txt",
                         home / "Pictures/AI-Generated/keep.txt", home / "dev/github/riff-racers/keep.txt",
                         home / ".local/share/local-image-ai-service-images/keep.txt"]
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
