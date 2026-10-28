#!/usr/bin/env python3
"""Remove only this service, its launcher, config, runtime and cache."""
from pathlib import Path
import shutil
import subprocess

home = Path.home()
unit = home / ".config/systemd/user/local-image-ai.service"
if unit.exists() and "Standalone Local Image AI" not in unit.read_text():
    raise SystemExit("Refusing to remove an unrelated unit")
subprocess.run(["systemctl", "--user", "stop", "local-image-ai.service"], check=True)
unit.unlink(missing_ok=True)
dropin_dir = unit.with_name("local-image-ai.service.d")
dropin = dropin_dir / "20-bounded-stop.conf"
if dropin.exists():
    if "# local-image-ai-service:" not in dropin.read_text():
        raise SystemExit("Refusing to remove an unrelated drop-in")
    dropin.unlink()
if dropin_dir.exists() and not any(dropin_dir.iterdir()):
    dropin_dir.rmdir()
launcher = home / ".local/bin/local-image-ai-service"
if launcher.exists():
    if "local-image-ai-service/app/manage.py" not in launcher.read_text():
        raise SystemExit("Refusing to remove an unrelated launcher")
    launcher.unlink()
for relative in (".local/share/local-image-ai-service", ".cache/local-image-ai-service", ".config/local-image-ai-service"):
    target = home / relative
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
print("Service removed. Existing models, images, projects and this repository are retained.")
