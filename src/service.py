#!/usr/bin/env python3
"""Strict, bounded image API; the separate official sd-server does all inference."""
from __future__ import annotations

import base64
import concurrent.futures
import fcntl
import hmac
import http.client
import json
import logging
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import stat
import struct
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HOME = Path.home()
CONFIG = HOME / ".config/local-image-ai-service/config.json"
WORK = HOME / ".cache/local-image-ai-service/work"
DEFAULTS = {"moss": {"steps": 50, "cfg": 3.0}}
DEFAULT_SIZE = "1024x1024"
MAX_BODY = 65536
MAX_RESPONSE = 16 * 1024 * 1024
LOG = logging.getLogger("local-image-ai")


class APIError(Exception):
    def __init__(self, status, message, code, param=None):
        super().__init__(message)
        self.status, self.code, self.param = status, code, param


def private_file(path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError(f"Expected own regular file with mode 0600: {path}")


def sampling_settings(cfg):
    settings = cfg.get("sampling", DEFAULTS["moss"])
    if not isinstance(settings, dict) or set(settings) != {"steps", "cfg"}:
        raise ValueError("sampling must contain exactly steps and cfg")
    if type(settings["steps"]) is not int or not 10 <= settings["steps"] <= 100:
        raise ValueError("sampling.steps must be an integer from 10 to 100")
    if type(settings["cfg"]) not in (int, float) or not 1 <= settings["cfg"] <= 6:
        raise ValueError("sampling.cfg must be a finite number from 1 to 6")
    return dict(settings)


def load_config(path=CONFIG):
    private_file(path)
    cfg = json.loads(path.read_text())
    if cfg["host"] != "127.0.0.1":
        raise ValueError("This service supports loopback 127.0.0.1 only")
    if cfg["active_model"] not in DEFAULTS or set(cfg["models"]) != set(DEFAULTS):
        raise ValueError("Only moss may be configured")
    sampling_settings(cfg)
    for key in ("port", "backend_port"):
        if type(cfg[key]) is not int or not 1024 <= cfg[key] <= 65535:
            raise ValueError(f"Invalid {key}")
    if cfg["port"] == cfg["backend_port"]:
        raise ValueError("Public and backend ports must differ")
    for key in ("load_timeout", "generation_timeout"):
        if type(cfg[key]) is not int or not 1 <= cfg[key] <= 1800:
            raise ValueError(f"Invalid {key}: expected 1..1800 seconds")
    for key in ("runtime", "cuda_lib"):
        if not Path(cfg[key]).is_absolute():
            raise ValueError(f"{key} must be absolute")
    if not re.fullmatch(r"GPU-[0-9a-fA-F-]+", cfg["gpu_uuid"]):
        raise ValueError("gpu_uuid must be an NVIDIA GPU UUID")
    for name, files in cfg["models"].items():
        required = {"diffusion", "llm", "vae"} | ({"tokenizer"} if name == "moss" else set())
        if set(files) != required or any(not Path(p).is_absolute() for p in files.values()):
            raise ValueError(f"Invalid model paths for {name}")
    if cfg.get("api_key_file"):
        key_path = Path(cfg["api_key_file"])
        if not key_path.is_absolute():
            raise ValueError("api_key_file must be absolute")
        private_file(key_path)
        if len(key_path.read_text().strip()) < 24:
            raise ValueError("API key must contain at least 24 characters")
    return cfg


def runtime_env(cfg):
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = cfg["cuda_lib"]
    env["CUDA_VISIBLE_DEVICES"] = cfg["gpu_uuid"]
    env["OMP_NUM_THREADS"] = "8"
    return env


def missing_files(cfg, model):
    return [p for p in cfg["models"][model].values() if not Path(p).is_file() or not os.access(p, os.R_OK)]


def gpu_check(cfg):
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=uuid,name,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=10, check=True)
    if cfg["gpu_uuid"] not in result.stdout:
        raise ValueError("Configured NVIDIA GPU is unavailable")
    backend = subprocess.run([cfg["runtime"], "--list-devices"], env=runtime_env(cfg),
                             capture_output=True, text=True, timeout=30, check=True)
    if "CUDA0\t" not in backend.stdout:
        raise ValueError("Runtime has no working CUDA0 backend; CPU fallback is forbidden")
    return result.stdout.strip(), backend.stdout.strip()


def foreign_compute(cfg):
    result = subprocess.run(
        ["nvidia-smi", "-i", cfg["gpu_uuid"], "--query-compute-apps=pid,process_name", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True)
    processes = []
    for line in result.stdout.splitlines():
        pid, separator, name = line.partition(",")
        # KDE's compositor is reported as C+G by this driver even when no inference runs.
        if separator and pid.strip().isdigit() and name.strip() not in ("/usr/bin/kwin_wayland", "/usr/bin/Xwayland"):
            processes.append(pid.strip())
    return processes


def validate_request(body, active):
    if not isinstance(body, dict):
        raise APIError(400, "Expected a JSON object", "invalid_request_error")
    allowed = {"model", "prompt", "seed", "size", "n", "response_format", "output_format", "user"}
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise APIError(400, f"Unsupported parameters: {', '.join(unknown)}", "unsupported_parameter", unknown[0])
    model = body.get("model", active)
    if not isinstance(model, str) or model not in DEFAULTS:
        raise APIError(404, "Unknown model; only moss is supported", "model_not_found", "model")
    if model != active:
        raise APIError(409, f"Model is not loaded; run local-image-ai-service use {model}", "model_not_loaded", "model")
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
        raise APIError(400, "prompt must contain 1..16000 characters", "invalid_prompt", "prompt")
    if re.search(r"sd_cpp_extra_args|<lora:", prompt, re.IGNORECASE):
        raise APIError(400, "Runtime control tags are unsupported in prompts", "invalid_prompt", "prompt")
    size = body.get("size", DEFAULT_SIZE)
    match = re.fullmatch(r"([0-9]{3,4})x([0-9]{3,4})", size) if isinstance(size, str) else None
    if not match or any(v < 256 or v > 1024 or v % 64 for v in map(int, match.groups())):
        raise APIError(400, "size: dimensions must be multiples of 64 between 256 and 1024", "invalid_size", "size")
    if type(body.get("n", 1)) is not int or body.get("n", 1) != 1:
        raise APIError(400, "Only n=1 is supported; submit images sequentially", "unsupported_n", "n")
    if body.get("response_format", "b64_json") != "b64_json":
        raise APIError(400, "Only response_format=b64_json is supported", "unsupported_parameter", "response_format")
    if body.get("output_format", "png") != "png":
        raise APIError(400, "Only output_format=png is supported", "unsupported_parameter", "output_format")
    if "user" in body and (not isinstance(body["user"], str) or len(body["user"]) > 256):
        raise APIError(400, "user must be a string of at most 256 characters", "invalid_request_error", "user")
    seed = body.get("seed", secrets.randbelow(2**31))
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise APIError(400, "seed must be an integer in 0..2147483647", "invalid_seed", "seed")
    return {"prompt": prompt, "size": size, "n": 1, "output_format": "png"}, seed


def validate_response(payload, size):
    result = json.loads(payload)
    if not isinstance(result.get("data"), list) or len(result["data"]) != 1:
        raise ValueError("Expected exactly one backend image")
    raw = base64.b64decode(result["data"][0]["b64_json"], validate=True)
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Backend returned invalid PNG")
    if struct.unpack(">II", raw[16:24]) != tuple(map(int, size.split("x"))):
        raise ValueError("Backend image dimensions differ from request")
    return result


class Backend:
    def __init__(self, cfg):
        self.cfg, self.proc = cfg, None
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.failure = None
        self.model = cfg["active_model"]

    def stop(self):
        self.ready.clear()
        proc = self.proc
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            LOG.info("Own sd-server stopped pid=%s exit=%s", proc.pid, proc.returncode)

    def start(self):
        cfg = self.cfg
        try:
            missing = missing_files(cfg, self.model)
            if missing:
                raise ValueError("Missing model files: " + ", ".join(missing))
            if foreign_compute(cfg):
                raise ValueError("GPU is occupied by another compute process; stop it yourself before starting")
            gpu_check(cfg)
            # Probe for a listener, not a bind: the native runtime uses SO_REUSEPORT,
            # so its closed connections can prevent a plain bind during TIME_WAIT.
            try:
                with socket.create_connection(("127.0.0.1", cfg["backend_port"]), timeout=1):
                    raise ValueError("Backend port is already in use")
            except ConnectionRefusedError:
                pass
            sampling = sampling_settings(cfg)
            width, height = DEFAULT_SIZE.split("x")
            args = [cfg["runtime"], "--listen-ip", "127.0.0.1", "--listen-port", str(cfg["backend_port"]),
                    "--model-dir", str(WORK / "empty-model-catalog"), "--offload-to-cpu", "--flash-attn", "on",
                    "--backend", "cuda0", "--threads", "8", "--conditioning-cache-size", "1",
                    "-W", width, "-H", height, "--steps", str(sampling["steps"]),
                    "--cfg-scale", str(sampling["cfg"]), "--sampling-method", "euler",
                    "--scheduler", "discrete", "--flow-shift", "5", "--vae-tiling"]
            flags = {"diffusion": "--diffusion-model", "llm": "--llm", "vae": "--vae", "tokenizer": "--tokenizer"}
            for role, path in cfg["models"][self.model].items():
                args.extend([flags[role], path])
            if self.stopping.is_set():
                return
            LOG.info("Loading model=%s steps=%s cfg=%s sampler=euler scheduler=discrete flow-shift=5; offload=cpu flash-attn=on backend=cuda0",
                     self.model, sampling["steps"], sampling["cfg"])
            self.proc = subprocess.Popen(args, env=runtime_env(cfg), cwd=WORK)
            deadline = time.monotonic() + cfg["load_timeout"]
            while time.monotonic() < deadline and not self.stopping.is_set():
                if self.proc.poll() is not None:
                    raise RuntimeError(f"sd-server exited during load: {self.proc.returncode}")
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", cfg["backend_port"], timeout=1)
                    try:
                        conn.request("GET", "/v1/models")
                        response = conn.getresponse()
                        if response.status == 200 and json.loads(response.read(65536)).get("data"):
                            self.ready.set()
                            LOG.info("Ready model=%s pid=%s", self.model, self.proc.pid)
                            return
                    finally:
                        conn.close()
                except (OSError, ValueError, http.client.HTTPException):
                    pass
                self.stopping.wait(0.25)
            if not self.stopping.is_set():
                raise TimeoutError("Model load deadline exceeded")
        except Exception as error:
            self.failure = str(error)
            LOG.error("Backend load failed: %s", error)
        self.stop()

    def available(self):
        return self.ready.is_set() and self.proc is not None and self.proc.poll() is None and not self.stopping.is_set()

    def generate(self, body, seed):
        if not self.available():
            raise APIError(503, "Backend not ready; inspect /health and service logs", "backend_not_ready")
        # The official OpenAI route accepts seed only through this documented native extension.
        native = dict(body)
        native["prompt"] += "<sd_cpp_extra_args>" + json.dumps({"seed": seed}) + "</sd_cpp_extra_args>"
        conn = http.client.HTTPConnection("127.0.0.1", self.cfg["backend_port"], timeout=self.cfg["generation_timeout"])
        expired = threading.Event()
        def expire():
            expired.set()
            self.failure = "Generation timed out; backend stopped; manual restart required"
            self.stop()
        # Enforce a total wall deadline as well as individual socket-operation timeouts.
        watchdog = threading.Timer(self.cfg["generation_timeout"], expire)
        watchdog.daemon = True
        watchdog.start()
        try:
            conn.request("POST", "/v1/images/generations", json.dumps(native).encode(), {"Content-Type": "application/json"})
            response = conn.getresponse()
            payload = response.read(MAX_RESPONSE + 1)
            watchdog.cancel()
            if expired.is_set():
                raise TimeoutError("Generation wall deadline exceeded")
            if response.status != 200 or len(payload) > MAX_RESPONSE:
                raise ValueError(f"Backend HTTP {response.status} or oversized response")
            result = validate_response(payload, body["size"])
            result["model"] = self.model
            result["seed"] = seed
            return result
        except (TimeoutError, socket.timeout):
            self.failure = "Generation timed out; backend stopped; manual restart required"
            self.stop()
            raise APIError(504, self.failure, "generation_timeout") from None
        except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
            if expired.is_set():
                self.stop()
                raise APIError(504, self.failure, "generation_timeout") from None
            self.failure = "Generation failed; backend stopped; inspect journal and restart manually"
            self.stop()
            raise APIError(502, self.failure, "backend_failed") from None
        finally:
            watchdog.cancel()
            conn.close()


class BoundedServer(HTTPServer):
    request_queue_size = 8

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.slots = threading.BoundedSemaphore(8)
        self.generation = threading.Lock()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                data = b'{"error":{"message":"HTTP capacity reached","type":"rate_limit_error","code":"server_busy","param":null}}'
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "
                                + str(len(data)).encode() + b"\r\n\r\n" + data)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        self.pool.submit(self.worker, request, address)

    def worker(self, request, address):
        try:
            self.finish_request(request, address)
        except (OSError, TimeoutError):
            pass
        except Exception:
            LOG.exception("HTTP request failed")
        finally:
            self.shutdown_request(request)
            self.slots.release()

    def server_close(self):
        super().server_close()
        self.pool.shutdown(wait=True, cancel_futures=True)


def make_handler(backend, api_key):
    class Handler(BaseHTTPRequestHandler):
        server_version = "local-image-ai-service/0.1"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, fmt, *args):
            # No URLs, prompts, request bodies or Authorization values in adapter logs.
            LOG.info("HTTP method=%s status=%s", self.command, args[1] if len(args) > 1 else "-")

        def send_json(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if status == 429:
                self.send_header("Retry-After", "5")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (OSError, TimeoutError):
                pass

        def send_error(self, code, message=None, explain=None):
            self.send_json(code, {"error": {"message": message or "Invalid HTTP request", "type": "invalid_request_error",
                                           "code": "http_error", "param": None}})

        def authorize(self):
            if api_key and not hmac.compare_digest(self.headers.get("Authorization", "").encode(), b"Bearer " + api_key):
                raise APIError(401, "Valid Bearer API key required", "invalid_api_key")

        def dispatch(self):
            try:
                self.authorize()
                if self.headers.get("Origin"):
                    raise APIError(403, "Browser origins are not accepted", "origin_not_allowed")
                if self.command == "GET":
                    if self.path == "/health":
                        return self.send_json(200, {"status": "ready" if backend.available() else "unavailable",
                            "active_model": backend.model, "backend_pid": backend.proc.pid if backend.proc else None,
                            "error": backend.failure, "busy": self.server.generation.locked()})
                    if self.path == "/ready":
                        return self.send_json(200 if backend.available() else 503, {"ready": backend.available()})
                    if self.path == "/v1/models":
                        return self.send_json(200, {"object": "list", "data": [
                            {"id": name, "object": "model", "owned_by": "local", "created": 0,
                             "installed": not missing_files(backend.cfg, name),
                             "loaded": backend.available() and name == backend.model,
                             "capabilities": ["images.generations"]} for name in DEFAULTS]})
                if self.command != "POST" or self.path != "/v1/images/generations":
                    raise APIError(404, "Unknown endpoint", "not_found")
                if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                    raise APIError(400, "Exactly one Content-Length required; chunked bodies unsupported", "invalid_request_error")
                try:
                    length = int(self.headers["Content-Length"])
                except ValueError:
                    raise APIError(400, "Invalid Content-Length", "invalid_request_error") from None
                if length < 1 or length > MAX_BODY:
                    raise APIError(413, "Body must contain 1..65536 bytes", "request_too_large")
                if self.headers.get_content_type() != "application/json":
                    raise APIError(415, "Content-Type must be application/json", "invalid_request_error")
                # Reject excess generations immediately, with no generation waiting queue.
                if not self.server.generation.acquire(blocking=False):
                    raise APIError(429, "One generation is already running; retry later", "generation_busy")
                try:
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise APIError(400, "Incomplete body", "invalid_request_error")
                    try:
                        body = json.loads(raw)
                    except (ValueError, UnicodeError, RecursionError):
                        raise APIError(400, "Invalid JSON", "invalid_request_error") from None
                    native, seed = validate_request(body, backend.model)
                    result = backend.generate(native, seed)
                finally:
                    self.server.generation.release()
                return self.send_json(200, result)
            except APIError as error:
                self.send_json(error.status, {"error": {"message": str(error),
                    "type": "rate_limit_error" if error.status == 429 else "invalid_request_error" if error.status < 500 else "server_error",
                    "code": error.code, "param": error.param}})
            except (TimeoutError, OSError):
                self.send_json(408, {"error": {"message": "HTTP read deadline exceeded", "type": "invalid_request_error",
                                              "code": "request_timeout", "param": None}})

        do_GET = dispatch
        do_POST = dispatch
        do_OPTIONS = dispatch
        do_DELETE = dispatch
        do_PUT = dispatch

    return Handler


def serve():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    os.umask(0o077)
    cfg = load_config()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "empty-model-catalog").mkdir(exist_ok=True)
    with (WORK / "service.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        backend = Backend(cfg)
        key = Path(cfg["api_key_file"]).read_text().strip().encode() if cfg.get("api_key_file") else None
        server = BoundedServer((cfg["host"], cfg["port"]), make_handler(backend, key))
        def shutdown(signum, frame):
            backend.stopping.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        loader = threading.Thread(target=backend.start, name="model-loader")
        loader.start()
        LOG.info("API listening on http://%s:%s model=%s", cfg["host"], cfg["port"], backend.model)
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            backend.stopping.set()
            loader.join(timeout=12)
            backend.stop()
            server.server_close()


if __name__ == "__main__":
    serve()
