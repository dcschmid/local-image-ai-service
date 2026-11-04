"""Contracts for the shared Z-Image installation and the expanded preset catalog."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from catalog import MODELS, defaults, quality_profiles
from recipes import compose, formats, recipes
from service import APIError, load_config, validate_request
import service
from studio_service import Studio


class ZImageTests(unittest.TestCase):
    def test_variants_share_pinned_encoder_and_vae_but_have_distinct_diffusion(self):
        manifest = json.loads((ROOT / 'config/models.lock.json').read_text())
        base, turbo = (manifest[name] for name in ('z-image', 'z-image-turbo'))
        self.assertEqual(base['llm'], turbo['llm'])
        self.assertEqual(base['vae'], turbo['vae'])
        self.assertNotEqual(base['diffusion']['sha256'], turbo['diffusion']['sha256'])
        for profile in (base, turbo):
            for artifact in profile.values():
                self.assertRegex(artifact['revision'], r'^[a-f0-9]{40}$')
                self.assertRegex(artifact['sha256'], r'^[a-f0-9]{64}$')
                self.assertGreater(artifact['size'], 0)

    def test_native_launch_keeps_the_variants_distinct_from_moss_sampling(self):
        for model, steps, cfg_scale, shift in (('z-image','40','4.0','6'), ('z-image-turbo','8','1.0','3')):
            with self.subTest(model=model):
                cfg = json.loads((ROOT / 'config/config.example.json').read_text())
                cfg['active_model'] = model
                cfg['models'][model] = {key:'/models/' + model + '/' + key for key in ('diffusion','llm','vae')}
                process = Mock(pid=12345, returncode=1);process.poll.return_value = 1
                backend = service.Backend(cfg)
                with patch.object(service, 'missing_files', return_value=[]), \
                     patch.object(service, 'foreign_compute', return_value=[]), \
                     patch.object(service, 'gpu_check'), \
                     patch.object(service.socket, 'create_connection', side_effect=ConnectionRefusedError), \
                     patch.object(service.subprocess, 'Popen', return_value=process) as launch:
                    backend.start()
                args = launch.call_args.args[0]
                for flag, expected in (('--steps',steps), ('--cfg-scale',cfg_scale), ('--flow-shift',shift),
                                       ('--scheduler','discrete'), ('--sampling-method','euler')):
                    self.assertEqual(args[args.index(flag) + 1], expected)

    def test_both_variants_load_as_curated_three_component_profiles(self):
        cfg = json.loads((ROOT / 'config/config.example.json').read_text())
        cfg['gpu_uuid'] = 'GPU-1234'
        for model in ('z-image', 'z-image-turbo'):
            cfg['models'][model] = {key: '/models/' + model + '/' + key for key in ('diffusion', 'llm', 'vae')}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(cfg));path.chmod(0o600)
            self.assertEqual(set(load_config(path)['models']), {'moss', 'z-image', 'z-image-turbo'})

    def test_turbo_requires_cfg_one_and_no_negative_prompt_in_both_api_and_guided_mode(self):
        for quality in ('preview', 'standard', 'detail'):
            result = compose(dict(recipe='zimage-turbo-sign', subject='a tea shop', text='TEA', quality=quality))
            self.assertEqual((result['steps'], result['cfg_scale'], result['negative_prompt']), (8, 1, ''))
            self.assertIn("'TEA'", result['prompt'])
            validate_request({key:value for key,value in result.items() if key != 'preset'}, 'z-image-turbo', max_dimension=1536)
        for extra in ({'cfg_scale': 4}, {'negative_prompt': 'blurry'}):
            with self.assertRaises(APIError):
                validate_request(dict(prompt='a tea shop', **extra), 'z-image-turbo')
        self.assertEqual([p['steps'] for p in quality_profiles('z-image-turbo')], [8])

    def test_base_supports_negative_prompt_and_author_step_range(self):
        for quality, steps in (('preview', 28), ('standard', 40), ('detail', 50)):
            result = compose(dict(recipe='zimage-fashion', subject='an adult in a linen coat', quality=quality))
            self.assertEqual((result['steps'], result['cfg_scale']), (steps, 4))
            self.assertTrue(result['negative_prompt'])
        self.assertEqual([p['steps'] for p in quality_profiles('z-image')], [28, 40, 50])

    def test_new_model_examples_work_without_extended_size_verification_receipts(self):
        with tempfile.TemporaryDirectory() as directory, patch('service.missing_files', return_value=[]):
            backend = Mock(model='moss', cfg={'runtime':'/unused', 'models':{name:{} for name in MODELS}})
            studio = Studio(backend, directory)
            for recipe in recipes():
                if recipe['model'] not in ('z-image', 'z-image-turbo'):
                    continue
                for quality in ('preview', 'standard', 'detail'):
                    for ratio in ('auto', *(f['id'] for f in formats(recipe['model']))):
                        with self.subTest(recipe=recipe['id'], quality=quality, ratio=ratio):
                            studio.prepare(dict(recipe=recipe['id'], **recipe['example'], quality=quality, aspect_ratio=ratio))

    def test_every_guided_example_fits_all_formats_and_api_contracts(self):
        identifiers = [r['id'] for r in recipes()]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual({r['model'] for r in recipes()}, set(MODELS))
        for recipe in recipes():
            for quality in ('preview', 'standard', 'detail'):
                for format in formats():
                    with self.subTest(recipe=recipe['id'], quality=quality, ratio=format['id']):
                        result = compose(dict(recipe=recipe['id'], **recipe['example'], quality=quality, aspect_ratio=format['id']))
                        # Pixel settings are Studio postprocessing inputs, not native inference controls.
                        native = {k:v for k,v in result.items() if k != 'preset'}
                        validate_request(native, recipe['model'], max_dimension=1536)
                        self.assertEqual(result['cfg_scale'], defaults(recipe['model'])['cfg'])


if __name__ == '__main__':
    unittest.main()
