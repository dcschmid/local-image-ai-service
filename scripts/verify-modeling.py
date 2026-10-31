#!/usr/bin/env python3
"""Generate full-quality Blender concepts in an isolated archive; requires an idle, stopped service."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from modeling_reference import ASSETS, VERSION
from service import Backend, load_config, WORK
from studio_service import Studio, DATA

CASES = [
    ('lowpoly-vehicle', 'moss', 'vehicle', 'three-quarter'),
    ('lowpoly-character', 'moss', 'character', 'front'),
    ('lowpoly-character', 'moss', 'character', 'side'),
    ('lowpoly-prop', 'moss', 'prop', 'three-quarter'),
    ('lowpoly-building', 'moss', 'building', 'three-quarter'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quality', choices=('preview','standard'), default='standard')
    parser.add_argument('--views', nargs='+', choices=('three-quarter', 'front', 'side'), default=['three-quarter', 'front', 'side'])
    args = parser.parse_args()
    os.umask(0o077)
    if subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'local-image-ai.service']).returncode == 0:
        raise SystemExit('Stop the service before GPU validation; this script never changes the user service or its configuration.')
    cache = Path.home() / '.cache/local-image-ai-service'
    cache.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='blender-reference-', dir=cache))
    if (DATA / 'verification.json').is_file():
        shutil.copyfile(DATA / 'verification.json', root / 'verification.json')
    cfg = load_config()
    cfg['generation_timeout'] = 900
    backend = Backend(cfg)
    studio = Studio(backend, root)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'empty-model-catalog').mkdir(exist_ok=True)
    report = dict(root=str(root), cases=[], geometry_consistency='Not verified. Independent AI views are concepts, not projections of a shared mesh.')
    print(json.dumps(dict(event='archive', root=str(root))), flush=True)
    try:
        for recipe, model, asset, view in CASES:
            if view not in args.views:
                continue
            if backend.model != model or not backend.available():
                backend.stop()
                backend.model = model
                backend.start()
                if not backend.available():
                    raise RuntimeError(backend.failure)
            body = dict(recipe=recipe, model=model, modeling_view=view, modeling_asset=asset,
                        **ASSETS[asset]['example'], quality=args.quality, seed=42)
            job = studio.submit(body)
            job.update(started=time.time(), status='generating')
            studio.put('job', job)
            result = studio.generate(job)
            studio.save_result(job, result)
            job.update(status='completed', completed=time.time())
            studio.put('job', job)
            image = studio.get(job['id'], 'image')
            assert image['request']['modeling_version'] == VERSION
            assert image['request']['recipe_inputs']['modeling_view'] == view
            assert studio.file(job['id']).is_file()
            entry = dict(model=model, asset=asset, view=view, image_id=job['id'], size=job['request']['size'],
                         steps=job['request']['steps'], seconds=image['seconds'])
            report['cases'].append(entry)
            (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(dict(event='generated', **entry)), flush=True)
    finally:
        backend.stopping.set()
        backend.stop()
    print(json.dumps(dict(event='complete', root=str(root), cases=len(report['cases']))), flush=True)


if __name__ == '__main__':
    main()
