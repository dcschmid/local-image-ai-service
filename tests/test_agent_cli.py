"""Exercise the agent CLI against the real HTTP adapter with inference disabled."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import agent_cli
import manage
import service
import studio_service
from catalog import MODELS


class AgentCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent-cli-')
        self.root = Path(self.temp.name)
        self.key = self.root / 'key';self.key.write_text('a' * 32);self.key.chmod(0o600)
        self.cfg = dict(host='127.0.0.1', port=7861, active_model='moss', runtime='/unused',
                        models={name: {} for name in MODELS}, generation_timeout=10, load_timeout=2, api_key_file=str(self.key))
        self.backend = service.Backend(self.cfg)
        self.backend.stopping.set()  # HTTP routes run normally; no worker can touch the GPU.
        self.data_patch = patch.object(studio_service, 'DATA', self.root / 'archive');self.data_patch.start()
        self.server = service.BoundedServer(('127.0.0.1', 0), service.make_handler(self.backend, self.key.read_bytes()))
        self.cfg['port'] = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True);self.thread.start()
        self.studio = studio_service.Studio(self.backend, self.root / 'archive')

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.data_patch.stop();self.temp.cleanup()

    def cli(self, *args, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(manage, 'load_config', return_value=self.cfg), patch('sys.stdin', io.StringIO(stdin or '')), \
                patch.object(manage, 'systemctl') as control, redirect_stdout(out), redirect_stderr(err):
            code = manage.main(list(args))
        control.assert_not_called()
        return code, json.loads(out.getvalue()) if out.getvalue() else None, json.loads(err.getvalue()) if err.getvalue() else None

    def image(self, *, pixels=False):
        identifier = 'a' * 32
        def raw(size):
            image = Image.new('RGBA', size, (80, 130, 30, 180));out = io.BytesIO()
            info = PngImagePlugin.PngInfo();info.add_text('parameters', 'seed 42; original metadata')
            image.save(out, format='PNG', pnginfo=info);return out.getvalue()
        full = raw((256, 256));self.studio.write_file(identifier, full)
        request = dict(model='flux-pixel' if pixels else 'moss', seed=42, size='256x256', prompt='an angular chest')
        item = dict(id=identifier, request=request, sampling={}, seconds=1, created=time.time())
        self.studio.put('image', item)
        self.studio.put('job', dict(id=identifier, status='completed', image_id=identifier, request=request, created=0))
        return identifier, full, None

    def test_discovery_is_json_and_offline_recipe_definitions_need_no_config(self):
        for command, count in [('recipes', 72), ('presets', 17), ('formats', 7)]:
            out = io.StringIO()
            with patch.object(manage, 'load_config', side_effect=AssertionError('No configuration needed')), redirect_stdout(out):
                self.assertEqual(manage.main([command]), 0)
            self.assertEqual(len(json.loads(out.getvalue())), count)
        code, result, err = self.cli('catalog', '--model', 'moss')
        self.assertEqual(code, 0);self.assertIsNone(err)
        self.assertEqual(list(result['models']), ['moss']);self.assertEqual(len(result['recipes']), 34)
        self.assertEqual(len(result['modeling']['assets']), 5)
        self.assertEqual(result['models']['moss']['defaults']['shift'], 5)
        self.assertEqual(self.studio.listing('job'), [])

    def test_discovery_filters_and_unknown_ids(self):
        self.assertIn('lowpoly-prop', [r['id'] for r in self.cli('recipes', '--model', 'moss', '--search', 'prop')[1]])
        self.assertEqual(self.cli('recipes', 'pixel-loot')[1]['model'], 'flux-pixel')
        self.assertEqual(self.cli('presets', 'comic')[1]['id'], 'comic')
        self.assertEqual(self.cli('recipes', 'unknown')[0], 2)
        self.assertEqual(self.cli('presets', 'unknown')[0], 2)

    def test_gallery_paging_favorites_and_multi_delete_preserve_exported_copies(self):
        identifier, full, _ = self.image(pixels=True)
        second = 'b' * 32;self.studio.write_file(second, full)
        self.studio.put('image', dict(id=second, request={}, created=1))
        self.assertEqual(len(self.cli('gallery', 'list')[1]), 2)
        self.assertEqual(self.cli('gallery', 'list', '--offset', '1')[1][0]['id'], second)
        self.assertEqual(self.cli('gallery', 'list', '--offset', '-1')[0], 2)
        self.assertEqual(self.cli('gallery', 'get', identifier)[1]['id'], identifier)
        self.assertEqual(self.cli('gallery', 'favorite', identifier, 'true')[0], 0)
        self.assertEqual(len(self.cli('gallery', 'list', '--favorites')[1]), 1)
        exported = self.cli('export', identifier, '--save-dir', str(self.root / 'assets'))[1]
        deleted = self.cli('gallery', 'delete', identifier, second)
        self.assertEqual(deleted[0], 0);self.assertEqual(deleted[1]['deleted_count'], 2)
        self.assertEqual(self.cli('gallery', 'list')[1], [])
        self.assertEqual(Path(exported['exports']['image']).read_bytes(), full)

    def test_templates_store_and_edit_requests_flow_through_http(self):
        identifier, raw, _ = self.image()
        source = self.root / 'portrait.png';source.write_bytes(raw)
        code, saved, err = self.cli('templates','save','--source', identifier, '--name','my portrait')
        self.assertEqual((code, err), (0, None));self.assertEqual(saved['name'], 'my portrait')
        self.assertEqual([item['id'] for item in self.cli('templates','list')[1]], [saved['id']])
        self.assertEqual(self.cli('templates','rename', saved['id'], '--name','renamed')[1]['name'], 'renamed')
        (self.studio.root/'verification.json').write_text(json.dumps({'moss':dict(fingerprint=self.studio.fingerprint('moss'),modes=['img2img','inpaint'],sizes=[])}))
        code, output, error = self.cli('compose','--prompt','reimagine','--model','moss','--template',str(source),'--strength','0.4')
        self.assertEqual((code, error), (0, None))
        self.assertEqual(output['request']['mode'],'img2img');self.assertEqual(output['request']['strength'], 0.4)
        self.assertEqual(self.studio.get(output['request']['image_id'], 'upload')['size'], [256, 256])
        self.assertEqual(self.studio.get(saved['id'], 'template')['name'], 'renamed')
        code, deleted, _ = self.cli('templates','delete', saved['id'])
        self.assertEqual((code, deleted['deleted_ids']), (0, [saved['id']]))
        self.assertEqual(self.cli('templates','list')[1], [])
        self.assertTrue(self.studio.file(identifier).exists())

    def test_retired_profiles_are_rejected_but_historical_images_still_export(self):
        for model in ('anima-psx', 'anima-lowpoly'):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                manage.main(['render', '--model', model, '--prompt', 'a kart'])
            self.assertEqual(raised.exception.code, 2)
        identifier, raw, _ = self.image()
        metadata = self.studio.get(identifier, 'image');metadata['request']['model'] = 'anima-lowpoly'
        self.studio.put('image', metadata)
        code, exported, _ = self.cli('export', identifier, '--save-dir', str(self.root / 'history'))
        self.assertEqual(code, 0);self.assertEqual(Path(exported['exports']['image']).read_bytes(), raw)

    def test_compose_supports_all_profiles_without_queueing(self):
        for recipe, model in [('photo-product', 'moss'), ('anima-portrait', 'anima'),
                              ('pixel-loot', 'flux-pixel')]:
            code, result, err = self.cli('compose', '--recipe', recipe, '--example', '--quality', 'preview', '--seed', '42')
            self.assertEqual((code, err), (0, None));self.assertEqual(result['request']['model'], model)
            self.assertEqual(result['request']['seed'], 42)
        self.assertEqual(self.studio.listing('job'), [])

    def test_blender_and_pixel_examples_have_the_same_options_as_the_studio(self):
        code, output, _ = self.cli('compose', '--recipe', 'lowpoly-prop', '--example', '--modeling-view', 'three-quarter',
                                    '--modeling-asset', 'vehicle', '--quality', 'preview', '--aspect-ratio', '16:9', '--seed', '42')
        self.assertEqual(code, 0);self.assertIn('racing kart', output['input']['subject'])
        self.assertEqual(output['request']['modeling_version'], 2);self.assertEqual(output['request']['size'], '1024x576')
        self.assertIn('axles', output['request']['prompt'])
        code, output, _ = self.cli('compose', '--recipe', 'pixel-loot', '--example', '--quality', 'standard', '--seed', '42')
        self.assertEqual(code, 0);self.assertIn('PXART4', output['request']['prompt'])
        self.assertEqual(output['request']['model'], 'flux-pixel');self.assertEqual(output['request']['size'], '1024x1024')

    def test_free_preset_and_explicit_negative_override(self):
        code, output, _ = self.cli('compose', '--prompt', 'an angular city', '--model', 'anima', '--preset', 'manga', '--size', '512x512')
        self.assertEqual(code, 0);self.assertIn('screentone', output['request']['prompt'])
        self.assertIn('color', output['request']['negative_prompt'])
        code, output, _ = self.cli('compose', '--prompt', 'a robot', '--model', 'flux-pixel', '--preset', 'anime', '--negative-prompt', '')
        self.assertEqual(code, 0);self.assertEqual(output['request']['negative_prompt'], '')

    def test_json_stdin_is_exact_and_conflicting_flags_are_rejected(self):
        body = dict(recipe='lowpoly-prop', subject='a red toolbox', quality='preview', seed=42)
        code, output, _ = self.cli('compose', '--input', '-', stdin=json.dumps(body))
        self.assertEqual(code, 0);self.assertEqual(output['input'], body)
        self.assertEqual(self.cli('compose', '--input', '-', '--seed', '4', stdin=json.dumps(body))[0], 2)
        for value in ('[]', '{broken', 'x' * 65537):
            self.assertEqual(self.cli('compose', '--input', '-', stdin=value)[0], 2)
        self.assertEqual(self.cli('render', '--recipe', 'lowpoly-prop', '--example', '--steps', '2')[0], 2)
        self.assertEqual(self.studio.listing('job'), [])

    def test_runtime_tags_remain_rejected_before_a_job_is_submitted(self):
        code, output, error = self.cli('render', '--recipe', 'lowpoly-prop', '--subject', '<lora:untrusted:1>', '--async')
        self.assertEqual(code, 1);self.assertIsNone(output);self.assertEqual(error['error']['http_status'], 400)
        self.assertEqual(self.studio.listing('job'), [])

    def test_async_batch_pins_seeds_and_can_be_inspected_and_cancelled(self):
        code, output, err = self.cli('render', '--recipe', 'lowpoly-prop', '--example', '--quality', 'preview', '--seed', str(2**31 - 1), '--count', '2', '--async')
        self.assertEqual((code, err), (0, None));self.assertEqual([j['seed'] for j in output['jobs']], [2**31 - 1, 0])
        identifiers = [j['id'] for j in output['jobs']]
        self.assertEqual(self.cli('jobs', 'get', identifiers[0])[1]['request']['seed'], 2**31 - 1)
        self.assertEqual(len(self.cli('jobs', 'list', '--status', 'queued')[1]), 2)
        self.assertEqual(self.cli('jobs', 'cancel', identifiers[0])[1]['status'], 'cancelled')
        self.assertEqual(self.cli('jobs', 'get', identifiers[1])[1]['status'], 'queued')
        self.assertEqual(self.backend.model, 'moss')

    def test_client_timeout_does_not_cancel_or_duplicate_a_job(self):
        queued = self.cli('render', '--prompt', 'a chest', '--model', 'moss', '--size', '256x256', '--async')[1]['jobs'][0]['id']
        code, output, error = self.cli('jobs', 'wait', queued, '--timeout', '0.01')
        self.assertEqual(code, 4);self.assertIsNone(output);self.assertEqual(error['error']['job_id'], queued)
        self.assertEqual(self.studio.get(queued, 'job')['status'], 'queued');self.assertEqual(len(self.studio.listing('job')), 1)

    def test_failed_and_cancelled_jobs_have_nonzero_structured_results(self):
        for status in ('failed', 'cancelled'):
            identifier = ('b' if status == 'failed' else 'c') * 32
            self.studio.put('job', dict(id=identifier, status=status, error='test stop', created=0))
            code, output, err = self.cli('jobs', 'wait', identifier)
            self.assertEqual(code, 3);self.assertIsNone(output);self.assertEqual(err['error']['code'], 'job_' + status)

    def test_direct_record_lookup_is_independent_of_recent_job_listing(self):
        identifier, _, _ = self.image()
        for index in range(201):
            self.studio.put('job', dict(id=f'{index:032x}', status='completed', created=index + 1))
        self.assertNotIn(identifier, [j['id'] for j in self.studio.listing('job')])
        self.assertEqual(self.cli('jobs', 'get', identifier)[1]['image_id'], identifier)
        self.assertEqual(self.cli('jobs', 'get', 'd' * 32)[2]['error']['http_status'], 404)

    def test_export_preserves_alpha_metadata_and_private_files(self):
        identifier, full, _ = self.image(pixels=True)
        directory = self.root / 'exports'
        code, output, err = self.cli('export', identifier, '--save-dir', str(directory))
        self.assertEqual((code, err), (0, None))
        exports = output['exports'];self.assertEqual(Path(exports['image']).read_bytes(), full)
        self.assertEqual(json.loads(Path(exports['metadata']).read_text()), output)
        for path in directory.iterdir(): self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(len(self.studio.listing('image')), 1)
        self.assertEqual(self.cli('export', identifier, '--save-dir', str(directory))[0], 0)

    def test_completed_job_wait_exports_without_submitting_anything(self):
        identifier, full, _ = self.image()
        code, output, err = self.cli('jobs', 'wait', identifier, '--save-dir', str(self.root / 'result'))
        self.assertEqual((code, err), (0, None));self.assertEqual(output['status'], 'completed')
        self.assertEqual(Path(output['images'][0]['exports']['image']).read_bytes(), full)
        self.assertEqual(len(self.studio.listing('job')), 1)

    def test_disk_failure_rolls_back_only_this_export_and_retains_the_archive(self):
        identifier, full, _ = self.image(pixels=True)
        directory = self.root / 'exports';directory.mkdir();(directory / 'keep.txt').write_text('keep')
        with patch('os.fsync', side_effect=[None, OSError('disk full')]):
            code, _, error = self.cli('export', identifier, '--save-dir', str(directory))
        self.assertEqual(code, 1);self.assertEqual(error['error']['code'], 'export_failed')
        self.assertEqual([p.name for p in directory.iterdir()], ['keep.txt'])
        self.assertEqual(self.studio.file(identifier).read_bytes(), full)

    def test_partial_batch_failure_reports_accepted_ids_without_retry(self):
        for index in range(15): self.studio.put('job', dict(id=f'{index:032x}', status='queued', created=index))
        code, output, error = self.cli('render', '--recipe', 'lowpoly-prop', '--example', '--quality', 'preview', '--count', '2', '--async')
        self.assertEqual(code, 1);self.assertIsNone(output)
        self.assertEqual(error['error']['http_status'], 429);self.assertEqual(len(error['error']['job_ids']), 1)
        self.assertEqual(len(self.studio.listing('job')), 16)

    def test_lost_submission_response_is_reported_without_duplicate_generation(self):
        original = manage.request
        def lose_response(cfg, path, **kwargs):
            result = original(cfg, path, **kwargs)
            if path == '/studio/api/jobs' and kwargs.get('body') is not None:
                raise ConnectionResetError('The accepted response was lost')
            return result
        with patch.object(manage, 'request', side_effect=lose_response) as requests:
            code, output, error = self.cli('render', '--recipe', 'lowpoly-prop', '--example', '--quality', 'preview', '--async')
        self.assertEqual(code, 1);self.assertIsNone(output)
        self.assertTrue(error['error']['submission_uncertain']);self.assertEqual(error['error']['job_ids'], [])
        self.assertEqual(len(self.studio.listing('job')), 1);self.assertEqual(requests.call_count, 2)

    def test_async_export_and_invalid_directories_are_rejected_before_submission(self):
        target = self.root / 'file';target.write_text('keep')
        self.assertEqual(self.cli('render', '--recipe', 'lowpoly-prop', '--example', '--async', '--save-dir', str(self.root / 'out'))[0], 2)
        self.assertEqual(self.cli('render', '--recipe', 'lowpoly-prop', '--example', '--save-dir', str(target))[0], 2)
        self.assertEqual(self.studio.listing('job'), [])

    def test_authentication_errors_are_json_and_do_not_expose_credentials(self):
        self.cfg['api_key_file'] = None
        code, output, error = self.cli('compose', '--recipe', 'lowpoly-prop', '--example')
        self.assertEqual(code, 1);self.assertIsNone(output);self.assertEqual(error['error']['http_status'], 401)
        self.assertNotIn(self.key.read_text(), json.dumps(error))

    def test_parse_errors_are_json_and_status_json_has_no_systemctl_output(self):
        for args in (['jobs', 'get', '../bad'], ['render', '--recipe', 'lowpoly-prop', '--timeout', 'nan']):
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(SystemExit) as raised: manage.main(args)
            self.assertEqual(raised.exception.code, 2);self.assertEqual(json.loads(err.getvalue())['error']['code'], 'invalid_arguments')
        status, output, error = self.cli('status', '--json')
        self.assertEqual(status, 1);self.assertIsNone(error);self.assertEqual(output['active_model'], 'moss')


if __name__ == '__main__':
    unittest.main()
