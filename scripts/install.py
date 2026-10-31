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
    for name in ("service.py", "manage.py", "agent_cli.py", "agent_integration.py", "mcp_server.py", "catalog.py", "studio_service.py", "recipes.py", "pixel_art.py", "modeling_reference.py"):
        shutil.copyfile(ROOT / "src" / name, app / name)
    shutil.copytree(ROOT / 'skills/local-image-ai', app / 'skills/local-image-ai', dirs_exist_ok=True)
    web = ROOT / "studio/dist"
    if not (web / "index.html").is_file():
        raise SystemExit("Build the studio first: npm ci --prefix studio && npm run build --prefix studio")
    shutil.copytree(web, app / "web", dirs_exist_ok=True)
    # Retired profile code and bundled examples must disappear on an upgrade too.
    (app / 'lora_adapter.py').unlink(missing_ok=True)
    for path in (app / '__pycache__').glob('lora_adapter.*.pyc'):
        path.unlink()
    for identifier in ('psx-character', 'psx-world', 'psx-prop', 'anima3d-character', 'anima3d-diorama', 'anima3d-landscape'):
        (app / 'web/recipe-examples' / (identifier + '.webp')).unlink(missing_ok=True)
    from PIL import Image  # Required for safe decoding, masks and PNG validation.
    images = HOME / ".local/share/local-image-ai-service-images/studio"
    images.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Retired checker code is not part of the installed application. Model data is retained.
    (app / "anatomy.py").unlink(missing_ok=True)
    if (app / "__pycache__").exists():
        for bytecode in (app / "__pycache__").glob("anatomy.*.pyc"):
            bytecode.unlink()
    work = HOME / ".cache/local-image-ai-service/work"
    work.mkdir(parents=True, exist_ok=True)
    config = HOME / ".config/local-image-ai-service/config.json"
    config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if config.exists():
        cfg = json.loads(config.read_text())
        updated = dict(cfg)
        updated["models"] = dict(cfg["models"])
        updated["models"] = {k:v for k,v in updated["models"].items() if k in ("moss", "anima", "qwen21", "krea-pixel")}
        if updated["active_model"] not in updated["models"]:
            updated["active_model"] = "moss" if "moss" in updated["models"] else "anima"
        updated.pop("anatomy", None)
        if cfg != updated:
            temporary = config.with_name("config.json.install")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(updated, stream, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, config)
            finally:
                temporary.unlink(missing_ok=True)
    else:
        cfg = json.loads((ROOT / "config/config.example.json").read_text())
        cfg["runtime"] = str(target / "runtime/bin/sd-server")
        cfg["cuda_lib"] = str(target / "runtime/lib")
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
