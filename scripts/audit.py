#!/usr/bin/env python3
"""Read-only SHA-256 inventory; manifests belong in the service cache, never Git."""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path


def inventory(roots):
    records = {}
    for root in roots:
        root = Path(root).expanduser().absolute()
        if not root.exists():
            raise FileNotFoundError(root)
        paths = [root]
        if root.is_dir():
            for parent, dirs, files in os.walk(root, followlinks=False):
                paths.extend(Path(parent) / name for name in dirs + files)
        for path in sorted(set(paths)):
            info = path.lstat()
            record = {"mode": stat.S_IMODE(info.st_mode), "kind": stat.S_IFMT(info.st_mode)}
            if path.is_symlink():
                record["target"] = os.readlink(path)
            elif path.is_file():
                record.update(size=info.st_size, mtime_ns=info.st_mtime_ns)
                with path.open("rb") as stream:
                    record["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
                if path.stat().st_mtime_ns != info.st_mtime_ns:
                    raise RuntimeError(f"File changed during audit: {path}")
            records[str(path)] = record
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("roots", nargs="*")
    args = parser.parse_args()
    if args.compare:
        before = json.loads(args.manifest.read_text())
        after = inventory(before["roots"])
        changes = [p for p in sorted(before["files"].keys() | after.keys())
                   if before["files"].get(p) != after.get(p)]
        added = sorted(after.keys() - before["files"].keys())
        removed = sorted(before["files"].keys() - after.keys())
        modified = [p for p in changes if p in before["files"] and p in after]
        print(json.dumps({"baseline_entries": len(before["files"]), "checked": len(after),
                          "added": added, "modified": modified, "removed": removed,
                          "changed": changes}, indent=2))
        raise SystemExit(bool(changes))
    if not args.roots:
        parser.error("Provide explicit protected roots")
    if args.manifest.exists():
        parser.error("Refusing to overwrite baseline")
    records = inventory(args.roots)
    args.manifest.write_text(json.dumps({"roots": args.roots, "files": records}, sort_keys=True))
    args.manifest.chmod(0o600)
    print(f"Recorded {len(records)} entries in {args.manifest}")


if __name__ == "__main__":
    main()
