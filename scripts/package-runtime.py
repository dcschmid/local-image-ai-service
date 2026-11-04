#!/usr/bin/env python3
"""Package the installed, verified runtime into a portable archive.

The archive bundles the pinned sd-server binary and its CUDA runtime libraries
so a fresh machine can install the runtime without a compiler or CUDA toolkit.
File checksums are verified against runtime.lock.json before packaging.

Output (under dist/):
  runtime-<revision>.tar.zst        the portable archive
  runtime-<revision>.manifest.json  checksums, size, version, revision
"""
import argparse
import hashlib
import json
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path.home() / ".local/share/local-image-ai-service/runtime"
# Fixed mtime so the archive is byte-for-byte reproducible for a given runtime.
FIXED_MTIME = 1700000000


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=RUNTIME,
                        help="Installed runtime directory (default: the service runtime)")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist",
                        help="Where to write the archive (default: dist/)")
    args = parser.parse_args()

    lock = json.loads((ROOT / "runtime.lock.json").read_text())
    expected = lock["installed_reference_sha256"]
    revision = lock["revision"]

    # Verify the installed runtime against the repo pin before packaging it.
    for rel, want in expected.items():
        path = args.runtime_dir / rel
        if not path.is_file():
            raise SystemExit(f"Missing runtime file: {path}")
        got = digest(path)
        if got != want:
            raise SystemExit(f"Runtime file does not match the pin: {rel}\n  expected {want}\n  got      {got}")
    print(f"Verified {len(expected)} runtime files against runtime.lock.json")

    version = (args.runtime_dir / "bin/sd-server")
    env = dict(os.environ, LD_LIBRARY_PATH=str(args.runtime_dir / "lib"))
    import subprocess
    version_out = subprocess.check_output([str(version), "--version"], env=env, text=True).strip()

    members = sorted(expected) + ["LICENSE.stable-diffusion.cpp"]
    archive = args.out_dir / f"runtime-{revision}.tar.zst"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:zst") as tar:
        for rel in members:
            path = args.runtime_dir / rel
            ti = tarfile.TarInfo(name=rel)
            ti.size = path.stat().st_size
            ti.mode = 0o755 if rel.startswith("bin/") else 0o644
            ti.mtime = FIXED_MTIME
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            with path.open("rb") as fh:
                tar.addfile(ti, fh)

    manifest = {
        "upstream": lock["upstream"],
        "revision": revision,
        "version": version_out,
        "cuda_toolkit": lock.get("cuda_toolkit"),
        "cuda_architecture": lock.get("cuda_architecture"),
        "archive": archive.name,
        "archive_sha256": digest(archive),
        "archive_size": archive.stat().st_size,
        "files": {rel: digest(args.runtime_dir / rel) for rel in expected},
    }
    manifest_path = args.out_dir / f"runtime-{revision}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Archive:   {archive} ({archive.stat().st_size / 1e6:.1f} MB)")
    print(f"Manifest:  {manifest_path}")
    print(f"sha256:    {manifest['archive_sha256']}")
    print(f"version:   {version_out}")


if __name__ == "__main__":
    main()
