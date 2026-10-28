#!/usr/bin/env python3
"""Install this application and user unit. Never enable or start automatically."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()


def main():
    os.umask(0o077)
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "local-image-ai.service"]).returncode == 0:
        raise SystemExit("Stop local-image-ai before installing an update")
    target = HOME / ".local/share/local-image-ai-service"
    app = target / "app"
    app.mkdir(parents=True, exist_ok=True)
    for name in ("service.py", "manage.py", "anatomy.py"):
        shutil.copyfile(ROOT / "src" / name, app / name)
    work = HOME / ".cache/local-image-ai-service/work"
    work.mkdir(parents=True, exist_ok=True)
    config = HOME / ".config/local-image-ai-service/config.json"
    config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not config.exists():
        cfg = json.loads((ROOT / "config/config.example.json").read_text())
        cfg["runtime"] = str(target / "runtime/bin/sd-server")
        cfg["cuda_lib"] = str(target / "runtime/lib")
        anatomy = target / "anatomy"
        cfg["anatomy"]["runtime"] = str(anatomy / "runtime/llama-mtmd-cli")
        cfg["anatomy"]["model"] = str(HOME / ".local/share/local-image-ai/models/moss/Qwen3.5-9B-Q4_K_M.gguf")
        cfg["anatomy"]["mmproj"] = str(anatomy / "models/mmproj-Qwen3.5-9B-F16.gguf")
        gpu_lines = subprocess.check_output(["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"], text=True).splitlines()
        if len(gpu_lines) != 1:
            raise SystemExit("Expected one NVIDIA GPU; configure gpu_uuid manually")
        cfg["gpu_uuid"] = gpu_lines[0].strip()
        models = HOME / ".local/share/local-image-ai/models"
        for name, files in cfg["models"].items():
            cfg["models"][name] = {role: str(models / name / Path(path).name) for role, path in files.items()}
        config.write_text(json.dumps(cfg, indent=2) + "\n")
        config.chmod(0o600)
    unit = HOME / ".config/systemd/user/local-image-ai.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    if unit.exists() and "Standalone Local Image AI" not in unit.read_text():
        raise SystemExit("Refusing to replace an unrelated unit")
    shutil.copyfile(ROOT / "systemd/local-image-ai.service", unit)
    dropin = unit.with_name("local-image-ai.service.d") / "20-bounded-stop.conf"
    dropin.parent.mkdir(parents=True, exist_ok=True)
    if dropin.exists() and "# local-image-ai-service:" not in dropin.read_text():
        raise SystemExit("Refusing to replace an unrelated drop-in")
    shutil.copyfile(ROOT / "systemd/20-bounded-stop.conf", dropin)
    launcher = HOME / ".local/bin/local-image-ai-service"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if launcher.exists() and "local-image-ai-service/app/manage.py" not in launcher.read_text():
        raise SystemExit("Refusing to replace an unrelated launcher")
    launcher.write_text('#!/usr/bin/env bash\nexec /usr/bin/python3 "$HOME/.local/share/local-image-ai-service/app/manage.py" "$@"\n')
    launcher.chmod(0o755)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print(f"Installed {unit}; no enable or automatic start. Config: {config}")


if __name__ == "__main__":
    main()
