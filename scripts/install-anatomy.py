#!/usr/bin/env python3
"""Explicit setup of the separate CPU-only vision checker, never generation weights."""
import concurrent.futures
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = Path.home() / ".local/share/local-image-ai-service/anatomy"
CACHE = Path.home() / ".cache/local-image-ai-service/anatomy-build"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_model(lock, name, expected):
    destination = BASE / "models" / expected.get("local_name", name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size == expected["bytes"] and digest(destination) == expected["sha256"]:
            print(f"Verified existing checker weight: {name}", flush=True)
            return
        raise RuntimeError(f"Existing checker file has a different checksum: {destination}")
    url = f"https://huggingface.co/{lock['repository']}/resolve/{lock['revision']}/{name}"
    temporary = destination.with_name(name + ".download")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=1024 * 1024)
        if temporary.stat().st_size != expected["bytes"] or digest(temporary) != expected["sha256"]:
            raise RuntimeError("Downloaded checker weight failed SHA-256 verification: " + name)
        temporary.replace(destination)
        print(f"Installed verified CPU checker weight: {name}", flush=True)
    finally:
        temporary.unlink(missing_ok=True)


def build_runtime(lock):
    source = CACHE / "source"
    build = CACHE / "output"
    source.mkdir(parents=True, exist_ok=True)
    if not (source / ".git").exists():
        subprocess.run(["git", "init", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "remote", "add", "origin", lock["upstream"]], check=True)
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"],
                                    env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), text=True)
    if dirty:
        raise RuntimeError("Own CPU build source has local changes; inspect it before rebuilding")
    subprocess.run(["git", "-C", str(source), "fetch", "--depth=1", "origin", lock["revision"]], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", lock["revision"]], check=True)
    subprocess.run(["cmake", "-S", str(source), "-B", str(build), "-G", "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=OFF", "-DGGML_NATIVE=ON",
                    "-DGGML_CUDA=OFF", "-DGGML_VULKAN=OFF", "-DGGML_OPENCL=OFF", "-DGGML_RPC=OFF",
                    "-DGGML_BLAS=OFF", "-DLLAMA_OPENSSL=OFF", "-DLLAMA_BUILD_SERVER=OFF",
                    "-DLLAMA_BUILD_TESTS=OFF"], check=True)
    subprocess.run(["cmake", "--build", str(build), "--target", lock["target"], "-j4"], check=True)
    runtime = BASE / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    temporary = runtime / (lock["target"] + ".install")
    try:
        shutil.copyfile(build / "bin" / lock["target"], temporary)
        temporary.chmod(0o755)
        subprocess.run([str(temporary), "--version"], check=True)
        temporary.replace(runtime / lock["target"])
    finally:
        temporary.unlink(missing_ok=True)
    shutil.copyfile(source / "LICENSE", runtime / "LICENSE.llama.cpp")
    return {"revision": lock["revision"], "binary_sha256": digest(runtime / lock["target"]),
            "cpu_only": True, "build": "Release, static, GGML_NATIVE=ON, CUDA/Vulkan/OpenCL/RPC/BLAS=OFF"}


def main():
    os.umask(0o077)
    lock = json.loads((ROOT / "anatomy.lock.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-model", type=Path, default=Path.home() / lock["model"]["shared_model"]["default_path"])
    args = parser.parse_args()
    expected = lock["model"]["shared_model"]
    if not args.shared_model.is_absolute() or not args.shared_model.is_file():
        raise SystemExit("Provide an existing absolute --shared-model path; generation weights are never downloaded")
    if args.shared_model.stat().st_size != expected["bytes"] or digest(args.shared_model) != expected["sha256"]:
        raise SystemExit("Existing shared Qwen3.5-9B encoder checksum differs from the tested model")
    BASE.mkdir(parents=True, exist_ok=True)
    setup_lock = (BASE / "setup.lock").open("a")
    fcntl.flock(setup_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print("Setting up the CPU vision checker: ~918 MB projector; shared text encoder is read in place.", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        downloads = [pool.submit(download_model, lock["model"], name, expected)
                     for name, expected in lock["model"]["files"].items()]
        runtime = pool.submit(build_runtime, lock["runtime"])
        for result in downloads:
            result.result()
        receipt = runtime.result()
    receipt["model"] = lock["model"]
    receipt["shared_model_path"] = str(args.shared_model)
    (BASE / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("CPU checker installed. Enable it in service configuration and restart the service.", flush=True)


if __name__ == "__main__":
    main()
