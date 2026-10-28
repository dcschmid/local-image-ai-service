#!/usr/bin/env python3
"""Sequential real GPU/lifecycle tests. Leaves this service stopped, default MOSS."""
import base64
import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from service import CONFIG, load_config, missing_files, foreign_compute

CLI = str(Path.home() / ".local/bin/local-image-ai-service")
CACHE = Path.home() / ".cache/local-image-ai-service"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def request(cfg, method, path, body=None):
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key_file"):
        headers["Authorization"] = "Bearer " + Path(cfg["api_key_file"]).read_text().strip()
    conn = http.client.HTTPConnection(cfg["host"], cfg["port"], timeout=cfg["generation_timeout"] + 20)
    try:
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def run(*args):
    subprocess.run([CLI, *args], check=True)


def png_check(raw, expected_size):
    check(raw[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature")
    check(struct.unpack(">II", raw[16:24]) == expected_size, "PNG dimensions")
    position, compressed, metadata = 8, bytearray(), {}
    while position < len(raw):
        size = struct.unpack(">I", raw[position:position + 4])[0]
        name = raw[position + 4:position + 8]
        data = raw[position + 8:position + 8 + size]
        crc = struct.unpack(">I", raw[position + 8 + size:position + 12 + size])[0]
        check(zlib.crc32(name + data) == crc, "PNG chunk CRC")
        if name == b"IDAT":
            compressed.extend(data)
        if name == b"tEXt":
            key, _, value = data.partition(b"\0")
            metadata[key.decode("latin1")] = value.decode("latin1")
        position += 12 + size
    decoded = zlib.decompress(compressed)
    check(len(decoded) > expected_size[0] * expected_size[1], "Decoded pixel data")
    check(len(set(decoded)) > 32, "Nontrivial image content")
    check("Seed: 42" in json.dumps(metadata), "Actual native seed metadata must be 42")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "png_crc_and_decode": "passed", "actual_seed": 42}


def stopped(cfg, pids):
    for pid in pids:
        check(not Path(f"/proc/{pid}").exists(), f"Process {pid} remains after stop")
    for port in (cfg["port"], cfg["backend_port"]):
        probe = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            try:
                probe.connect()
            except OSError:
                pass
            else:
                raise AssertionError(f"Port {port} still open")
        finally:
            probe.close()
    check(not foreign_compute(cfg), "Unexpected GPU compute process after stopping")


def main():
    os.umask(0o077)
    cfg = load_config()
    report = {"date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tests": {}, "images": {}}
    tests = report["tests"]
    check((Path(__file__).resolve().parents[1] / ".git").is_dir(), "Separate Git repository")
    check(CONFIG.stat().st_mode & 0o077 == 0, "Config is private")
    receipt = json.loads((Path(cfg["runtime"]).parents[1] / "receipt.json").read_text())
    for relative, checksum in receipt["files"].items():
        path = Path(cfg["runtime"]).parents[1] / relative
        check(not path.is_symlink(), "Runtime must be a separate install")
        with path.open("rb") as stream:
            check(hashlib.file_digest(stream, "sha256").hexdigest() == checksum, "Runtime checksum")
    tests["repository_install_runtime_checksums"] = "passed"
    check(all(not missing_files(cfg, name) for name in ("moss", "z-image")), "All model files")
    tests["all_model_files"] = "passed"
    run("doctor")
    tests["cuda_backend"] = "passed"
    temporary = tempfile.TemporaryDirectory(prefix="integration-", dir=CACHE)
    try:
        run("use", "moss")
        tests["systemd_start_api_reachability"] = "passed"
        for model in ("moss", "z-image"):
            if model == "z-image":
                old_pid = request(cfg, "GET", "/health")[1]["backend_pid"]
                run("use", model)
                check(not Path(f"/proc/{old_pid}").exists(), "Previous model process must exit")
                tests["controlled_model_switch"] = "passed"
            status, models = request(cfg, "GET", "/v1/models")
            check(status == 200 and {m["id"] for m in models["data"]} == {"moss", "z-image"}, "Models response")
            check([m["id"] for m in models["data"] if m["loaded"]] == [model], "Exactly one loaded model")
            tests["models_response"] = "passed"
            check(request(cfg, "GET", "/ready")[0] == 200, "Ready endpoint")
            for body, expected, code in (
                ({"model": "invalid", "prompt": "tree"}, 404, "model_not_found"),
                ({"model": model, "prompt": "tree", "size": "513x512"}, 400, "invalid_size"),
                ({"model": "z-image" if model == "moss" else "moss", "prompt": "tree"}, 409, "model_not_loaded"),
                ({"model": model, "prompt": "tree", "n": 2}, 400, "unsupported_n")):
                status, error = request(cfg, "POST", "/v1/images/generations", body)
                check(status == expected and error["error"]["code"] == code, f"Error handling {code}")
                tests[code] = "passed"
            check(request(cfg, "POST", "/v1/images/edits", {})[0] == 404, "No edits endpoint")
            body = {"model": model, "prompt": "A red ceramic teapot beside a green apple on a white table, soft studio light",
                    "size": "512x512", "n": 1, "seed": 42, "response_format": "b64_json"}
            start = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                generation = pool.submit(request, cfg, "POST", "/v1/images/generations", body)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if request(cfg, "GET", "/health")[1]["busy"]:
                        break
                    time.sleep(0.02)
                else:
                    raise AssertionError("Generation did not enter busy state")
                status, error = request(cfg, "POST", "/v1/images/generations", body)
                check(status == 429 and error["error"]["code"] == "generation_busy", "Reject parallel GPU generation")
                tests["real_concurrent_request_429"] = "passed"
                status, result = generation.result()
            check(status == 200, f"{model} generation failed: {result if status != 200 else status}")
            raw = base64.b64decode(result["data"][0]["b64_json"], validate=True)
            report["images"][model] = png_check(raw, (512, 512))
            report["images"][model]["seconds"] = round(time.monotonic() - start, 2)
            (Path(temporary.name) / f"{model}.png").write_bytes(raw)
            tests[f"real_generation_{model}"] = "passed"
            print(f"PASS real generation {model}: {report['images'][model]}", flush=True)
        backend_pid = request(cfg, "GET", "/health")[1]["backend_pid"]
        main_pid = subprocess.check_output(["systemctl", "--user", "show", "-p", "MainPID", "--value", "local-image-ai"], text=True).strip()
        run("stop")
        stopped(cfg, [backend_pid, int(main_pid)])
        tests["stop_no_gpu_process_or_listener"] = "passed"
        run("use", "moss")
        before_pid = request(cfg, "GET", "/health")[1]["backend_pid"]
        run("restart")
        after_pid = request(cfg, "GET", "/health")[1]["backend_pid"]
        check(before_pid != after_pid and not Path(f"/proc/{before_pid}").exists(), "Clean restart")
        tests["restart"] = "passed"
        # Stop during inference must also reap the model, without waiting for all sampling steps.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            active = pool.submit(request, cfg, "POST", "/v1/images/generations", {
                "model": "moss", "prompt": "A blue ceramic sphere", "size": "512x512", "seed": 42})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if request(cfg, "GET", "/health")[1]["busy"]:
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("Active stop test failed to start inference")
            start = time.monotonic()
            run("stop")
            check(time.monotonic() - start < 22, "Bounded shutdown while generating")
            try:
                status, _ = active.result()
                check(status in (502, 503), "Stopped generation should fail explicitly")
            except (OSError, http.client.HTTPException):
                pass  # systemd may close the connection as the service exits.
        tests["stop_during_generation"] = "passed"
        stopped(cfg, [after_pid])
        check(subprocess.check_output(["systemctl", "--user", "is-enabled", "local-image-ai"], text=True).strip() == "static",
              "Unit must not be enabled")
        tests["not_enabled_at_login"] = "passed"
        report["result"] = "passed"
    finally:
        subprocess.run([CLI, "stop"], check=False)
        temporary.cleanup()
        report["temporary_test_images"] = "removed from service-specific temporary directory"
        (CACHE / "integration-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
