#!/usr/bin/env python3
"""Serve the real Studio with public example previews for documentation screenshots.

No private configuration, model weights, image library or GPU process is used.
Only GET routes and prompt composition are available. Stop with Ctrl+C.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import service
import studio_service
from catalog import MODELS
from recipes import VERSION, compose, formats

DEMO_RECIPES = (
    'lowpoly-anything', 'anima-neon', 'photo-product', 'zimage-fantasy',
    'pixel-landscape', 'moss-comic', 'lowpoly-track-overview', 'lowpoly-vehicle',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=7862)
    parser.add_argument('--allow-asset-renders',action='store_true',help='Enable local CPU GLB imports for asset UI verification; AI inference remains disabled')
    args = parser.parse_args()
    static = ROOT / 'studio/dist'
    if not (static / 'index.html').is_file():
        parser.error('Build the Studio first: npm run build --prefix studio')
    with tempfile.TemporaryDirectory(prefix='atelier-docs-') as directory:
        root = Path(directory)
        marker = root / 'public-demo-only';marker.write_text('No inference runtime.')
        cfg = dict(host='127.0.0.1', port=args.port, active_model='moss', runtime=str(marker),
                   models={name: dict(demo=str(marker)) for name in MODELS}, generation_timeout=10, load_timeout=2)
        backend = service.Backend(cfg)
        backend.stopping.set()  # The actual Studio worker exits without running inference.
        backend.failure = 'Documentation demo · public examples'
        with patch.object(studio_service, 'DATA', root), patch.object(studio_service, 'STATIC', static):
            studio = studio_service.Studio(backend, root)
            manifest = json.loads((static / 'recipe-examples/manifest.json').read_text())
            receipts = {name: dict(fingerprint=studio.fingerprint(name), modes=['text'],
                                  sizes=sorted({'1024x1024', '832x1216', '1216x832'} |
                                               {f['size'] for f in formats(name)})) for name in MODELS}
            (root / 'verification.json').write_text(json.dumps(receipts))
            for index, identifier in enumerate(DEMO_RECIPES):
                sample = manifest[identifier]
                record_id = hashlib.sha256(('documentation/' + identifier).encode()).hexdigest()[:32]
                inputs = dict(sample['inputs'], quality=sample['quality'], seed=sample['seed'])
                request = dict(compose(inputs), recipe_inputs=inputs, recipe_version=VERSION)
                with Image.open(static / 'recipe-examples' / Path(sample['url']).name) as image:
                    stream = io.BytesIO();image.save(stream, 'PNG')
                studio.write_file(record_id, stream.getvalue())
                record = dict(id=record_id, request=request, sampling=dict(steps=sample['steps'],
                              cfg=sample['cfg_scale'], sampler=sample['sampler']), seconds=sample['seconds'],
                              created=1760000000 - index, favorite=index < 2, public_example=identifier)
                studio.put('image', record)
            base = service.make_handler(backend, None)

            class ReadOnlyHandler(base):
                def dispatch(self):
                    asset_write=args.allow_asset_renders and self.command=='POST' and (self.path=='/studio/api/assets' or self.path.startswith('/studio/api/assets/') and self.path.endswith('/cancel'))
                    if self.command != 'GET' and not (self.command == 'POST' and self.path == '/studio/api/compose') and not asset_write:
                        return self.send_json(405, dict(error=dict(message='This documentation demo cannot generate or change images.')))
                    return super().dispatch()

                # Base handlers bind these aliases at class creation; bind them
                # again so every HTTP method goes through the demo's guard.
                do_GET = do_POST = do_DELETE = dispatch

            with service.BoundedServer(('127.0.0.1', args.port), ReadOnlyHandler) as server:
                print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}/studio/',
                                      mode='public documentation demo; no inference', images=len(DEMO_RECIPES))), flush=True)
                try: server.serve_forever()
                except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
