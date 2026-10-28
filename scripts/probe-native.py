#!/usr/bin/env python3
"""Probe the separately installed native API, then always stop only its own child."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from service import load_config, runtime_env, foreign_compute


def main():
    cfg = load_config()
    if foreign_compute(cfg):
        raise SystemExit("GPU occupied; refusing native probe")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", cfg["backend_port"]))
    cache = Path.home() / ".cache/local-image-ai-service"
    with tempfile.TemporaryDirectory(prefix="native-probe-", dir=cache) as work:
        args = [cfg["runtime"], "--listen-ip", "127.0.0.1", "--listen-port", str(cfg["backend_port"]),
                "--model-dir", work, "--offload-to-cpu", "--flash-attn", "on", "--steps", "12",
                "--cfg-scale", "3", "--sampling-method", "euler", "--threads", "8", "-W", "256", "-H", "256"]
        for role, flag in (("diffusion", "--diffusion-model"), ("llm", "--llm"), ("vae", "--vae"), ("tokenizer", "--tokenizer")):
            args += [flag, cfg["models"]["moss"][role]]
        log_path = cache / "native-probe.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(args, env=runtime_env(cfg), cwd=work, stdout=log, stderr=subprocess.STDOUT)
            def request(method, path, body=None):
                connection = http.client.HTTPConnection("127.0.0.1", cfg["backend_port"], timeout=180)
                try:
                    connection.request(method, path, json.dumps(body) if body is not None else None,
                                       {"Content-Type": "application/json"})
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    connection.close()
            try:
                deadline = time.monotonic() + cfg["load_timeout"]
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"Native probe exited; see {log_path}")
                    try:
                        status, models = request("GET", "/v1/models")
                        if status == 200 and models.get("data"):
                            break
                    except OSError:
                        time.sleep(0.25)
                else:
                    raise TimeoutError("Native load timeout")
                # One small real image tests the native model-name/size handling.
                status, result = request("POST", "/v1/images/generations", {
                    "model": "does-not-exist", "prompt": "A small red ceramic sphere on a white table",
                    "size": "invalid-size", "n": 1, "seed": 42, "response_format": "b64_json"})
                report = {"models_status": 200, "models": models,
                          "invalid_model_and_size_status": status,
                          "image_returned_despite_invalid_model_and_size": bool(result.get("data"))}
                report["edits_without_image_status"] = request("POST", "/v1/images/edits", {})[0]
                (cache / "native-probe.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report, indent=2))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    os.umask(0o077)
    main()
