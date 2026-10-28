#!/usr/bin/env python3
"""Test CLI saving against an already running service; retain its process and model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import manage
from integration import png_check


def main():
    os.umask(0o077)
    cfg = manage.load_config()
    status, health = manage.request(cfg, "/health")
    if status != 200 or health["status"] != "ready" or health["busy"]:
        raise RuntimeError("Start an idle service before running CLI integration tests")
    cache = Path.home() / ".cache/local-image-ai-service"
    cli = Path.home() / ".local/bin/local-image-ai-service"
    app = Path.home() / ".local/share/local-image-ai-service/app/manage.py"
    report = {"date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": health["active_model"], "tests": {}}
    common = ["generate", "--prompt", "A red ceramic teapot beside a green apple on a white table, soft studio light",
              "--model", health["active_model"], "--size", "512x512", "--seed", "42"]
    with tempfile.TemporaryDirectory(prefix="cli-integration-", dir=cache) as work:
        root = Path(work)
        test_home = root / "home"
        # Only configuration is copied. Absolute model/runtime paths remain untouched.
        config = test_home / ".config/local-image-ai-service/config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps(cfg))
        config.chmod(0o600)
        variants = [
            ("save_dir", [str(cli), *common, "--save-dir", str(root / "custom")], None, root / "custom"),
            # Isolate --save's default path under the service-specific temporary test folder.
            ("save_default", [sys.executable, str(app), *common, "--save"],
             dict(os.environ, HOME=str(test_home)), test_home / ".local/share/local-image-ai-service-images"),
        ]
        for name, command, env, expected in variants:
            start = time.monotonic()
            result = subprocess.run(command, env=env, capture_output=True, text=True,
                                    timeout=cfg["generation_timeout"] + 45, check=True)
            output = json.loads(result.stdout)
            path = Path(output["path"])
            if path.parent != expected or "data" in output or output["seed"] != 42:
                raise AssertionError("Incorrect compact save response")
            if output.get("anatomy_check", {}).get("checked") is not True:
                raise AssertionError("Saved CLI response lost the automatic anatomy assessment")
            if path.stat().st_mode & 0o077:
                raise AssertionError("Image file permissions are not private")
            details = png_check(path.read_bytes(), (512, 512))
            details["seconds"] = round(time.monotonic() - start, 2)
            report["tests"][name] = details
            print(f"PASS {name}: {details}", flush=True)
        invalid = subprocess.run([str(cli), "generate", "--prompt", "tree", "--size", "513x512",
                                  "--save-dir", str(root / "invalid")], capture_output=True, text=True, timeout=10)
        if invalid.returncode == 0 or "Traceback" in invalid.stderr or (root / "invalid").exists():
            raise AssertionError("Invalid CLI size was not rejected cleanly")
        report["tests"]["invalid_size_no_output"] = "passed"
    after_status, after = manage.request(cfg, "/health")
    if after_status != 200 or after["backend_pid"] != health["backend_pid"] or after["status"] != "ready":
        raise AssertionError("The existing service process did not remain ready")
    report["result"] = "passed"
    report["service_process_retained"] = True
    report["temporary_test_images"] = "removed from service-specific temporary directory"
    (cache / "cli-integration-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
