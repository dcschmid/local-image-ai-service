#!/usr/bin/env python3
"""Management for this service only; never imports or calls imgai."""
import argparse
import base64
from datetime import datetime, timezone
import fcntl
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from service import (APIError, CONFIG, DEFAULTS, MAX_RESPONSE, WORK, gpu_check, load_config,
                     missing_files, private_file, runtime_env, validate_request, validate_response)

UNIT = "local-image-ai.service"


def systemctl(*args, check=True):
    return subprocess.run(["systemctl", "--user", *args, UNIT], check=check)


def atomic_config(cfg):
    temporary = CONFIG.with_name("config.json.new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(cfg, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, CONFIG)
    finally:
        temporary.unlink(missing_ok=True)


def request(cfg, path, *, body=None, timeout=2):
    connection = http.client.HTTPConnection(cfg["host"], cfg["port"], timeout=timeout)
    headers = {}
    if cfg.get("api_key_file"):
        key_path = Path(cfg["api_key_file"])
        private_file(key_path)
        headers["Authorization"] = "Bearer " + key_path.read_text().strip()
    try:
        payload = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        connection.request("POST" if body is not None else "GET", path, body=payload, headers=headers)
        response = connection.getresponse()
        limit = MAX_RESPONSE if body is not None else 65536
        data = response.read(limit + 1)
        if len(data) > limit:
            raise RuntimeError("API response exceeds the size limit")
        return response.status, json.loads(data)
    finally:
        connection.close()


def default_save_dir():
    # Kept outside the installation/cache trees so uninstall retains generated images.
    return Path.home() / ".local/share/local-image-ai-service-images"


def save_image(raw, directory, model, seed):
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{timestamp}_{model}_{seed}_{uuid.uuid4().hex[:12]}.png"
    # Exclusive creation also rejects pre-existing symlinks; never overwrite a file.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def generate(cfg, args):
    model = args.model or cfg["active_model"]
    body = {"model": model, "prompt": args.prompt, "size": args.size, "n": 1, "response_format": "b64_json"}
    if args.seed is not None:
        body["seed"] = args.seed
    validate_request(body, cfg["active_model"])
    directory = None
    if args.save or args.save_dir is not None:
        directory = (args.save_dir if args.save_dir is not None else default_save_dir()).expanduser().resolve()
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"Save directory is not a directory: {directory}")
    status, result = request(cfg, "/v1/images/generations", body=body, timeout=cfg["generation_timeout"] + 30)
    if not isinstance(result, dict):
        raise RuntimeError("API returned an invalid image response")
    if status != 200:
        error = result.get("error", {})
        if isinstance(error, dict):
            raise RuntimeError(f"HTTP {status} [{error.get('code', 'api_error')}]: {error.get('message', 'Generation failed')}")
        raise RuntimeError(f"HTTP {status}: Generation failed")
    try:
        validate_response(json.dumps(result).encode(), args.size)
        seed = result["seed"]
        if result["model"] != model or type(seed) is not int or not 0 <= seed < 2**31:
            raise ValueError("Unexpected model or seed")
        if args.seed is not None and seed != args.seed:
            raise ValueError("Seed differs from request")
        raw = base64.b64decode(result["data"][0]["b64_json"], validate=True)
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f"API returned an invalid image response: {error}") from None
    if directory is not None:
        path = save_image(raw, directory, model, seed)
        return {"model": model, "seed": seed, "size": args.size, "path": str(path)}
    return result


def wait_ready(cfg):
    deadline = time.monotonic() + cfg["load_timeout"] + 40
    while time.monotonic() < deadline:
        try:
            status, health = request(cfg, "/health")
            if status == 200 and health["active_model"] == cfg["active_model"]:
                if health["error"]:
                    raise RuntimeError(health["error"])
                if health["status"] == "ready":
                    print(f"Ready: {cfg['active_model']} at http://{cfg['host']}:{cfg['port']}/v1")
                    return
        except (OSError, http.client.HTTPException):
            pass
        if systemctl("is-active", "--quiet", check=False).returncode:
            raise RuntimeError("Service exited; inspect local-image-ai-service logs")
        time.sleep(0.5)
    raise TimeoutError("Readiness deadline exceeded; inspect logs (no automatic restart)")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="local-image-ai-service", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "status", "models", "logs", "start", "stop", "restart"):
        commands.add_parser(name)
    switch = commands.add_parser("use", help="Stop this service, select a model, and start it again")
    switch.add_argument("model", choices=sorted(DEFAULTS))
    generation = commands.add_parser("generate", help="Generate one image through the running service API")
    generation.add_argument("--prompt", required=True, help="Image prompt")
    generation.add_argument("--model", choices=sorted(DEFAULTS), help="Must match the loaded model; default: configured model")
    generation.add_argument("--size", default="768x768", help="WIDTHxHEIGHT; multiples of 64, each 256..1024 (default: 768x768)")
    generation.add_argument("--seed", type=int, help="Integer 0..2147483647; omitted means random")
    saving = generation.add_mutually_exclusive_group()
    saving.add_argument("--save", action="store_true", help="Save PNG in ~/.local/share/local-image-ai-service-images")
    saving.add_argument("--save-dir", type=Path, help="Save PNG in this directory instead (implies saving)")
    args = parser.parse_args(argv)
    cfg = load_config()
    if args.command == "generate":
        print(json.dumps(generate(cfg, args), indent=2))
        return 0
    if args.command == "logs":
        os.execvp("journalctl", ["journalctl", "--user", "-u", UNIT, "-f"])
    if args.command == "status":
        result = systemctl("status", "--no-pager", check=False)
        try:
            print(json.dumps(request(cfg, "/health")[1], indent=2))
        except OSError:
            print("API is offline")
        return result.returncode
    if args.command == "models":
        print(json.dumps({"configured_model": cfg["active_model"], "models": {
            name: {"missing": missing_files(cfg, name), "defaults": defaults}
            for name, defaults in DEFAULTS.items()}}, indent=2))
        return 0
    if args.command == "doctor":
        for name in DEFAULTS:
            missing = missing_files(cfg, name)
            if missing:
                raise ValueError(f"Missing files for {name}: {missing}")
        gpu, backend = gpu_check(cfg)
        version = subprocess.run([cfg["runtime"], "--version"], env=runtime_env(cfg),
                                 capture_output=True, text=True, timeout=10, check=True)
        print(json.dumps({"config": str(CONFIG), "work": str(WORK), "models": "all required files readable",
                          "gpu": gpu, "backend": backend, "runtime": version.stdout.strip()}, indent=2))
        return 0
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with (CONFIG.parent / "management.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cfg = load_config()
        if args.command == "use":
            if missing_files(cfg, args.model):
                raise ValueError("Requested model is missing files; current service remains untouched")
            # systemctl stop waits for the entire service cgroup; then config and start.
            systemctl("stop")
            cfg["active_model"] = args.model
            atomic_config(cfg)
            systemctl("start")
            wait_ready(cfg)
        elif args.command in ("start", "restart"):
            systemctl(args.command)
            wait_ready(cfg)
        elif args.command == "stop":
            systemctl("stop")
    return 0


if __name__ == "__main__":
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except (APIError, OSError, ValueError, RuntimeError, TimeoutError, http.client.HTTPException, subprocess.SubprocessError) as error:
        print(f"local-image-ai-service: {error}", file=sys.stderr)
        raise SystemExit(1)
