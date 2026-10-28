#!/usr/bin/env python3
"""Separately install an official sd-server and its CUDA runtime libraries (no models)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

REVISION = "a77d3623180b2bc1886f3dd04c0aa04156a987ef"
# Audited official source build, master-987-a77d362, CUDA 13.4, SM 120.
EXPECTED_BINARY_SHA256 = "d438b31a7a0794f25646320ff86b04449ac17058855b3620f861711df31c6e43"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--cuda-lib", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--rebuilt", action="store_true", help="Allow a locally reproduced binary with a different hash")
    args = parser.parse_args()
    active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", "local-image-ai.service"])
    if active.returncode == 0:
        raise SystemExit("Stop local-image-ai before replacing its runtime")
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(args.source), "status", "--porcelain", "--untracked-files=no"],
                                    env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), text=True)
    if revision != REVISION or dirty:
        raise SystemExit("Expected clean official source at pinned revision " + REVISION)
    binary_hash = digest(args.binary)
    if not args.rebuilt and binary_hash != EXPECTED_BINARY_SHA256:
        raise SystemExit("Unrecognized installed binary; use a reproduced official build")
    target = Path.home() / ".local/share/local-image-ai-service/runtime"
    target.mkdir(parents=True, exist_ok=True)
    files = {"bin/sd-server": args.binary}
    for name in ("libcudart.so.13", "libcublas.so.13", "libcublasLt.so.13"):
        files["lib/" + name] = (args.cuda_lib / name).resolve(strict=True)
    receipt = {"upstream": "https://github.com/leejet/stable-diffusion.cpp", "revision": revision,
               "installation": "separate copies, no symlinks to the old installation", "files": {}}
    for name, source in files.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if name.startswith("bin/") else 0o644)
        checksum = digest(destination)
        if checksum != digest(source):
            raise RuntimeError("Copy verification failed: " + name)
        receipt["files"][name] = checksum
    shutil.copyfile(args.source / "LICENSE", target / "LICENSE.stable-diffusion.cpp")
    env = dict(os.environ, LD_LIBRARY_PATH=str(target / "lib"))
    receipt["version"] = subprocess.check_output([str(target / "bin/sd-server"), "--version"], env=env, text=True).strip()
    (target / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
