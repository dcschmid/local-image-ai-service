#!/usr/bin/env python3
"""Run real agent CLI rendering/export against an isolated GPU service and archive."""
import json
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import service
import studio_service

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-mcp', action='store_true', help='Also generate through the optional MCP stdio bridge')
    args = parser.parse_args()
    os.umask(0o077)
    if subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'local-image-ai.service']).returncode == 0:
        raise SystemExit('Stop the service before isolated GPU verification.')
    cache = Path.home() / '.cache/local-image-ai-service';cache.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='agent-cli-', dir=cache))
    cfg = service.load_config();cfg.update(active_model='moss', generation_timeout=900)
    backend = service.Backend(cfg)
    config = root / 'config.json'
    wrapper = root / 'cli.py'
    # Inject only the isolated connection config into the normal CLI entrypoint.
    # No HOME override, credentials on argv, or real user config writes are needed.
    wrapper.write_text("import json,sys\nfrom pathlib import Path\nfrom unittest.mock import patch\n"
                       + 'sys.path.insert(0,' + repr(str(ROOT / 'src')) + ')\nimport manage\n'
                       + "with patch.object(manage,'load_config',side_effect=lambda: json.loads(Path(sys.argv[1]).read_text())):\n"
                       + ' raise SystemExit(manage.main(sys.argv[2:]))\n')
    mcp_wrapper = root / 'bridge.py'
    mcp_wrapper.write_text("import json,sys\nfrom pathlib import Path\nfrom unittest.mock import patch\n"
                          + 'sys.path.insert(0,' + repr(str(ROOT / 'src')) + ')\nimport manage\n'
                          + "with patch.object(manage,'load_config',side_effect=lambda: json.loads(Path(sys.argv[1]).read_text())):\n"
                          + " import mcp_server\n mcp_server.create_server().run(transport='stdio')\n")
    report = dict(root=str(root), tests=[])
    with patch('service.CONFIG', config), patch('studio_service.DATA', root / 'archive'), patch('studio_service.STATIC', ROOT / 'studio/dist'):
        key = Path(cfg['api_key_file']).read_bytes().strip() if cfg.get('api_key_file') else None
        server = service.BoundedServer(('127.0.0.1', 0), service.make_handler(backend, key))
        cfg['port'] = server.server_port;config.write_text(json.dumps(cfg))
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        def cli(*args):
            result = subprocess.run([sys.executable, str(wrapper), str(config), *args], capture_output=True, text=True, timeout=400)
            if result.returncode: raise RuntimeError(result.stderr)
            if result.stderr: raise RuntimeError('Unexpected stderr: ' + result.stderr)
            return json.loads(result.stdout)
        print(json.dumps(dict(event='archive', root=str(root))), flush=True)
        try:
            backend.start()
            if not backend.available(): raise RuntimeError(backend.failure)
            preview = cli('compose', '--recipe', 'lowpoly-vehicle', '--example', '--modeling-view', 'three-quarter',
                          '--modeling-asset', 'vehicle', '--quality', 'preview', '--aspect-ratio', '1:1', '--seed', '42')
            assert preview['request']['size'] == '768x768'
            queued = cli('render', '--recipe', 'lowpoly-vehicle', '--example', '--modeling-view', 'three-quarter',
                         '--modeling-asset', 'vehicle', '--quality', 'preview', '--aspect-ratio', '1:1', '--seed', '42', '--async')
            job_id = queued['jobs'][0]['id']
            assert cli('jobs', 'get', job_id)['id'] == job_id
            completed = cli('jobs', 'wait', job_id, '--timeout', '300', '--save-dir', str(root / 'moss-export'))
            image = completed['images'][0]
            assert image['request']['model'] == 'moss' and image['sampling']['shift'] == 5 and image['request']['modeling_version'] == 1
            assert Path(image['exports']['image']).is_file() and Path(image['exports']['metadata']).is_file()
            report['tests'].append(dict(model='moss', mode='async render/get/wait/export', size=image['request']['size'],
                                        seconds=image['seconds'], image_id=image['id']))
            print(json.dumps(dict(event='passed', **report['tests'][-1])), flush=True)
            pixel = cli('render', '--recipe', 'pixel-loot', '--example', '--seed', '43',
                        '--timeout', '300', '--save-dir', str(root / 'pixel-export'))['images'][0]
            assert pixel['request']['model'] == 'flux-pixel'
            assert 'PXART4' in pixel['request']['prompt']
            assert Path(pixel['exports']['image']).is_file() and Path(pixel['exports']['metadata']).is_file()
            assert backend.model == 'flux-pixel'
            exported = cli('export', pixel['id'], '--save-dir', str(root / 'pixel-repeat'))
            assert Path(exported['exports']['image']).read_bytes() == Path(pixel['exports']['image']).read_bytes()
            assert len(cli('jobs', 'list')) == 2
            report['tests'].append(dict(model='flux-pixel', mode='synchronous render/export/re-export', size=pixel['request']['size'],
                                        seconds=pixel['seconds'], image_id=pixel['id']))
            print(json.dumps(dict(event='passed', **report['tests'][-1])), flush=True)
            if args.with_mcp:
                async def mcp_verification():
                    from mcp import Client, StdioServerParameters
                    async with Client(StdioServerParameters(command=sys.executable, args=[str(mcp_wrapper), str(config)])) as client:
                        async def call(name, values=None):
                            result = await client.call_tool(name, values or {})
                            if result.is_error: raise RuntimeError(str(result.content))
                            return result.structured_content
                        assert (await call('list_presets'))['count'] == 70
                        composed = await call('compose', dict(params=dict(recipe='lowpoly-anything', example=True, quality='preview', seed=44)))
                        assert composed['request']['model'] == 'moss'
                        accepted = await call('generate_image', dict(params=dict(recipe='lowpoly-anything', example=True, quality='preview', seed=44)))
                        identifier = accepted['jobs'][0]['id']
                        for _ in range(30):
                            waited = await call('wait_for_job', dict(job_id=identifier, timeout=10))
                            if waited.get('status') == 'completed': break
                        else: raise RuntimeError('MCP job did not complete within 300 seconds; inspect ' + identifier)
                        exported = await call('export_image', dict(image_id=identifier, save_dir=str(root / 'mcp-export')))
                        assert Path(exported['exports']['image']).is_file()
                        assert Path(exported['exports']['metadata']).is_file()
                        return dict(model='moss', mode='MCP stdio discovery/compose/generate/wait/export', image_id=identifier,
                                    seconds=exported['seconds'], size=exported['request']['size'])
                report['tests'].append(asyncio.run(mcp_verification()))
                assert len(cli('jobs', 'list')) == 3
                print(json.dumps(dict(event='passed', **report['tests'][-1])), flush=True)
            report['status'] = 'passed'
            (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        finally:
            backend.stopping.set();backend.stop();server.shutdown();server.server_close();thread.join()
    print(json.dumps(dict(event='complete', root=str(root))), flush=True)


if __name__ == '__main__':
    main()
