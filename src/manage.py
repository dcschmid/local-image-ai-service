#!/usr/bin/env python3
"""Management for this service only; never imports or calls imgai."""
import argparse
import fcntl
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from service import CONFIG, DEFAULTS, WORK, gpu_check, load_config, missing_files, private_file, runtime_env

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


def request(cfg, path):
    connection = http.client.HTTPConnection(cfg["host"], cfg["port"], timeout=2)
    headers = {}
    if cfg.get("api_key_file"):
        key_path = Path(cfg["api_key_file"])
        private_file(key_path)
        headers["Authorization"] = "Bearer " + key_path.read_text().strip()
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read(65536))
    finally:
        connection.close()


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "status", "models", "use", "logs", "start", "stop", "restart"])
    parser.add_argument("model", nargs="?", choices=sorted(DEFAULTS))
    args = parser.parse_args()
    cfg = load_config()
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
    if args.command == "use" and args.model is None:
        parser.error("use requires moss or z-image")
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
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        print(f"local-image-ai-service: {error}", file=sys.stderr)
        raise SystemExit(1)
