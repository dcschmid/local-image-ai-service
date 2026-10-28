#!/usr/bin/env python3
"""Real person screening and shutdown during CPU review; leaves MOSS running."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import manage
from integration import png_check


def command(*args):
    subprocess.run([str(Path.home() / ".local/bin/local-image-ai-service"), *args], check=True)


def cpu_pids():
    group = subprocess.check_output(["systemctl", "--user", "show", "local-image-ai", "-p", "ControlGroup", "--value"], text=True).strip()
    if not group:
        return []
    path = Path("/sys/fs/cgroup") / group.lstrip("/") / "cgroup.procs"
    if not path.exists():
        return []
    return [int(pid) for pid in path.read_text().split() if Path(f"/proc/{pid}/comm").exists()
            and Path(f"/proc/{pid}/comm").read_text().strip() == "llama-mtmd-cli"]


def main():
    cfg = manage.load_config()
    cli = str(Path.home() / ".local/bin/local-image-ai-service")
    cache = Path.home() / ".cache/local-image-ai-service"
    report = {"date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tests": {}}
    # A deliberate test start; clear the unit's manual start limit after the preceding lifecycle suite.
    # An unloaded inactive unit has no counters and can reject reset-failed harmlessly.
    subprocess.run(["systemctl", "--user", "reset-failed", "local-image-ai"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    command("use", "moss")
    with tempfile.TemporaryDirectory(prefix="anatomy-api-", dir=cache) as work:
        args = [cli, "generate", "--prompt", "Studio head-and-shoulders portrait of one adult person with short dark hair, wearing a plain blue shirt, facing camera, neutral gray background, no text, photorealistic",
                "--size", "512x512", "--seed", "42", "--save-dir", work]
        result = subprocess.run(args, capture_output=True, text=True, timeout=cfg["generation_timeout"] + cfg["anatomy"]["timeout"] + 45, check=True)
        saved = json.loads(result.stdout)
        assessment = saved["anatomy_check"]
        if assessment["status"] != "REVIEW_REQUIRED" or not assessment["checked"]:
            raise AssertionError("A real portrait was not explicitly routed to human review")
        if assessment["people_present"] != "yes" or "Anatomy review required" not in result.stderr:
            raise AssertionError("Person detection or CLI review notice is missing")
        report["person_image"] = png_check(Path(saved["path"]).read_bytes(), (512, 512))
        report["person_image"]["anatomy_check"] = assessment
        report["tests"]["real_person_cli_save_and_review"] = "passed"
        status, health = manage.request(cfg, "/health")
        if status != 200 or cpu_pids():
            raise AssertionError("Checker process remains after a completed assessment")
        report["tests"]["no_cpu_process_after_check"] = "passed"
        with tempfile.TemporaryFile(dir=work) as stdout, tempfile.TemporaryFile(dir=work) as stderr:
            proc = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            try:
                deadline = time.monotonic() + cfg["generation_timeout"] + 30
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise AssertionError("Second request exited before CPU shutdown test")
                    _, state = manage.request(cfg, "/health")
                    pids = cpu_pids()
                    if state["anatomy_check"]["busy"] and pids:
                        break
                    time.sleep(0.1)
                else:
                    raise TimeoutError("CPU review never started")
                gpu_pids = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"], text=True).split()
                if set(map(str, pids)) & set(gpu_pids):
                    raise AssertionError("CPU checker unexpectedly created a GPU context")
                report["tests"]["real_checker_uses_no_gpu_context"] = "passed"
                start = time.monotonic()
                command("stop")
                elapsed = time.monotonic() - start
                proc.wait(timeout=25)
                if elapsed > 22 or proc.returncode == 0:
                    raise AssertionError("CPU-stage shutdown did not cancel the active request cleanly")
                if any(Path(f"/proc/{pid}").exists() for pid in [*pids, health["backend_pid"]]):
                    raise AssertionError("Owned CPU/GPU child remains after stop")
                report["tests"]["stop_during_real_cpu_review"] = "passed"
                report["stop_seconds"] = round(elapsed, 2)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
    command("start")
    report["tests"]["service_restored_running_moss"] = "passed"
    report["temporary_test_images"] = "removed from service-specific temporary directory"
    report["result"] = "passed"
    (cache / "anatomy-api-integration-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
