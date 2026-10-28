"""Client generation, opt-in saving, and error handling without a GPU."""
import base64
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import http.server
import io
import json
from pathlib import Path
import stat
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import manage


def png_bytes():
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\x12\x34\x56" * 256) * 256)) + chunk(b"IEND", b""))


class CLIImageTests(unittest.TestCase):
    def setUp(self):
        cache = Path.home() / ".cache/local-image-ai-service"
        cache.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="cli-unit-", dir=cache)
        self.root = Path(self.temporary.name)
        self.cfg = {"host": "127.0.0.1", "port": 7861, "active_model": "moss", "generation_timeout": 300}
        self.raw = png_bytes()
        self.result = {"created": 0, "output_format": "png", "model": "moss", "seed": 42,
                       "data": [{"b64_json": base64.b64encode(self.raw).decode()}]}

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, options, response=None, expected_timeout=330):
        output = io.StringIO()
        with patch.object(manage, "load_config", return_value=self.cfg), \
                patch.object(manage, "request", return_value=response or (200, self.result)) as request, \
                patch.object(manage, "systemctl") as control, redirect_stdout(output):
            status = manage.main(["generate", "--prompt", "A red teapot", "--size", "256x256", "--seed", "42", *options])
        self.assertEqual(status, 0)
        control.assert_not_called()
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["timeout"], expected_timeout)
        return json.loads(output.getvalue()), request.call_args.kwargs["body"]

    def test_without_flag_returns_full_json_and_writes_nothing(self):
        with patch.object(manage, "default_save_dir") as default:
            result, body = self.invoke([])
        self.assertEqual(result, self.result)
        self.assertEqual(body["model"], "moss")
        self.assertNotIn("save", body)
        default.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_save_uses_separate_default_directory_and_private_png(self):
        directory = self.root / "default-images"
        with patch.object(manage, "default_save_dir", return_value=directory):
            result, _ = self.invoke(["--save"])
        path = Path(result["path"])
        self.assertEqual(path.parent, directory)
        self.assertEqual(path.read_bytes(), self.raw)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertIn("_moss_42_", path.name)
        self.assertEqual(result["size"], "256x256")
        self.assertNotIn("data", result)

    def test_custom_directory_implies_saving_and_repeated_seed_keeps_both_files(self):
        directory = self.root / "custom" / "new directory"
        first, _ = self.invoke(["--save-dir", str(directory)])
        second, _ = self.invoke(["--save-dir", str(directory)])
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(len(list(directory.glob("*.png"))), 2)
        self.assertEqual(Path(first["path"]).read_bytes(), self.raw)

    def test_default_path_is_outside_the_install_and_cache(self):
        with patch.object(Path, "home", return_value=self.root):
            self.assertEqual(manage.default_save_dir(), self.root / ".local/share/local-image-ai-service-images")

    def test_existing_file_is_rejected_before_api_call(self):
        target = self.root / "existing.txt"
        target.write_text("keep me")
        args = Namespace(model=None, prompt="tree", size="256x256", seed=42, save=False, save_dir=target)
        with patch.object(manage, "request") as request, self.assertRaisesRegex(ValueError, "not a directory"):
            manage.generate(self.cfg, args)
        request.assert_not_called()
        self.assertEqual(target.read_text(), "keep me")

    def test_api_errors_create_no_directory_and_do_not_retry(self):
        directory = self.root / "not-created"
        args = Namespace(model=None, prompt="tree", size="256x256", seed=42, save=False, save_dir=directory)
        for status in (401, 409, 429, 503):
            with self.subTest(status=status), patch.object(manage, "request", return_value=(status, {
                    "error": {"code": "test_error", "message": "Request rejected"}})) as request:
                with self.assertRaisesRegex(RuntimeError, f"HTTP {status}"):
                    manage.generate(self.cfg, args)
                self.assertEqual(request.call_count, 1)
                self.assertFalse(directory.exists())

    def test_invalid_image_response_never_creates_a_directory(self):
        directory = self.root / "not-created"
        args = Namespace(model=None, prompt="tree", size="256x256", seed=42, save=False, save_dir=directory)
        for result in (
            dict(self.result, seed=43), dict(self.result, model="z-image"),
            dict(self.result, data=[{"b64_json": "invalid!"}]),
            dict(self.result, data=[{"b64_json": base64.b64encode(b"not a PNG").decode()}]),
        ):
            with self.subTest(result=list(result)), patch.object(manage, "request", return_value=(200, result)):
                with self.assertRaisesRegex(RuntimeError, "invalid image response"):
                    manage.generate(self.cfg, args)
                self.assertFalse(directory.exists())

    def test_filename_collision_never_overwrites_the_existing_file(self):
        fixed = datetime(2026, 10, 28, tzinfo=timezone.utc)
        with patch.object(manage, "datetime") as clock, patch.object(manage.uuid, "uuid4") as unique:
            clock.now.return_value = fixed
            unique.return_value.hex = "0123456789abcdef"
            path = manage.save_image(b"original", self.root, "moss", 42)
            with self.assertRaises(FileExistsError):
                manage.save_image(b"replacement", self.root, "moss", 42)
        self.assertEqual(path.read_bytes(), b"original")

    def test_write_failure_removes_only_new_partial_file(self):
        existing = self.root / "keep.txt"
        existing.write_text("existing data")
        with patch.object(manage.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                manage.save_image(self.raw, self.root, "moss", 42)
        self.assertEqual(list(self.root.iterdir()), [existing])
        self.assertEqual(existing.read_text(), "existing data")

    def test_saving_flags_are_mutually_exclusive_and_only_apply_to_generate(self):
        for args in (["generate", "--prompt", "tree", "--save", "--save-dir", str(self.root)], ["start", "--save"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                manage.main(args)
            self.assertEqual(raised.exception.code, 2)

    def test_post_request_sends_json_and_configured_bearer_key(self):
        received = {}
        result = self.result
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received["path"] = self.path
                received["authorization"] = self.headers.get("Authorization")
                received["content_type"] = self.headers.get("Content-Type")
                received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args):
                pass
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 5
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        key = self.root / "bearer-key"
        key.write_text("unit-test-key-not-a-real-secret")
        key.chmod(0o600)
        cfg = dict(self.cfg, port=server.server_port, api_key_file=str(key))
        try:
            status, returned = manage.request(cfg, "/v1/images/generations", body={"prompt": "tree"}, timeout=3)
        finally:
            thread.join(timeout=6)
            server.server_close()
        self.assertEqual(status, 200)
        self.assertEqual(returned, self.result)
        self.assertEqual(received, {"path": "/v1/images/generations", "authorization": "Bearer " + key.read_text(),
                                    "content_type": "application/json", "body": {"prompt": "tree"}})

    def test_automatic_check_is_preserved_in_saved_result_and_extends_timeout(self):
        self.cfg["anatomy"] = {"enabled": True, "timeout": 180}
        report = {"status": "NO_OBVIOUS_ISSUE", "checked": True, "summary": "No obvious issue observed."}
        response = dict(self.result, anatomy_check=report)
        directory = self.root / "screened"
        result, _ = self.invoke(["--save-dir", str(directory)], response=(200, response), expected_timeout=510)
        self.assertEqual(result["anatomy_check"], report)
        self.assertEqual(Path(result["path"]).read_bytes(), self.raw)

    def test_missing_or_disabled_assessment_cannot_be_saved_when_enabled(self):
        self.cfg["anatomy"] = {"enabled": True, "timeout": 180}
        directory = self.root / "must-not-exist"
        for report in (None, {"status": "DISABLED", "checked": False},
                       {"status": "ISSUE_DETECTED", "checked": True}):
            response = dict(self.result)
            if report is not None:
                response["anatomy_check"] = report
            with self.subTest(report=report), self.assertRaisesRegex(RuntimeError, "no valid automatic anatomy"):
                self.invoke(["--save-dir", str(directory)], response=(200, response))
            self.assertFalse(directory.exists())

    def test_uncertain_assessment_is_visible_in_stderr_and_saved_json(self):
        self.cfg["anatomy"] = {"enabled": True, "timeout": 180}
        report = {"status": "REVIEW_REQUIRED", "checked": True, "summary": "Legs are cropped."}
        errors = io.StringIO()
        with redirect_stderr(errors):
            result, _ = self.invoke(["--save-dir", str(self.root / "review")],
                                    response=(200, dict(self.result, anatomy_check=report)), expected_timeout=510)
        self.assertIn("Anatomy review required", errors.getvalue())
        self.assertEqual(result["anatomy_check"], report)

    def test_anatomy_rejection_produces_no_saved_image(self):
        directory = self.root / "must-not-exist"
        error = {"error": {"code": "anatomy_rejected", "message": "Extra arm detected", "seed": 42,
                           "anatomy_check": {"status": "ISSUE_DETECTED", "checked": True}}}
        with redirect_stderr(io.StringIO()), self.assertRaisesRegex(RuntimeError, "anatomy_rejected"):
            self.invoke(["--save-dir", str(directory)], response=(422, error))
        self.assertFalse(directory.exists())


if __name__ == "__main__":
    unittest.main()
