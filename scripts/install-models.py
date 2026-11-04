#!/usr/bin/env python3
"""Install pinned, SHA-256 checked studio models. Existing weights are read, never changed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    manifest = json.loads((ROOT / 'config/models.lock.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('models', nargs='*', default=['anima'], choices=sorted(manifest))
    parser.add_argument('--download-only', action='store_true', help='Verify downloads without changing the service configuration')
    args = parser.parse_args()
    os.umask(0o077)
    config = HOME / '.config/local-image-ai-service/config.json'
    cfg = json.loads(config.read_text())
    installed = {}
    target = HOME / '.local/share/local-image-ai-service/models'
    old = HOME / '.local/share/local-image-ai/models'
    # Reuse identical components across profiles by checksum, including the Anima base.
    shared = {}
    for model in args.models:
        files = {}
        for role, item in manifest[model].items():
            key = item['sha256']
            path = shared.get(key)
            if path is None:
                candidates = list(old.glob('*/' + Path(item['file']).name))
                if role == 'vae':
                    candidates += list(old.glob('*/flux*-*.safetensors'))
                path = next((p for p in candidates if p.is_file() and p.stat().st_size == item['size'] and digest(p) == key), None)
            if path is None:
                path = target / Path(item['file']).name
                if not path.exists() or digest(path) != key:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    partial = path.with_suffix(path.suffix + '.partial')
                    url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['file']}"
                    print(f'Download {model}/{role}: {item["size"] / 1e9:.2f} GB', flush=True)
                    with urllib.request.urlopen(url, timeout=120) as source, partial.open('wb') as destination:
                        shutil.copyfileobj(source, destination, 4 * 1024 * 1024)
                    if digest(partial) != key:
                        partial.unlink()
                        raise ValueError('Checksum mismatch: ' + str(path))
                    partial.replace(path)
            shared[key] = path
            files[role] = str(path)
        installed[model] = files
        print(f'Verified {model}', flush=True)
    if args.download_only:
        return
    # Do not race a live service changing its config.
    import subprocess
    if subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'local-image-ai.service']).returncode == 0:
        raise SystemExit('Downloads verified. Stop service and rerun to update config safely.')
    cfg = json.loads(config.read_text())
    cfg['models'].update(installed)
    backup = config.with_suffix('.pre-studio.json')
    if not backup.exists():
        shutil.copyfile(config, backup)
    temporary = config.with_suffix('.models.tmp')
    with temporary.open('w') as stream:
        json.dump(cfg, stream, indent=2)
    temporary.replace(config)
    print('Model configuration updated; no service started.')

if __name__ == '__main__':
    main()
