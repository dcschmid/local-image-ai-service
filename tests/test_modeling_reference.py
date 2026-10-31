import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import modeling_reference
from recipes import compose, formats, recipes
from service import APIError, validate_request
from studio_service import Studio


class ModelingReferenceTests(unittest.TestCase):
    def test_existing_examples_keep_their_recorded_prompts_and_settings(self):
        path = Path(__file__).resolve().parents[1] / 'studio/public/recipe-examples/manifest.json'
        for sample in json.loads(path.read_text()).values():
            result = compose(dict(sample['inputs'], quality=sample['quality'], seed=sample['seed']))
            for key in ('prompt', 'negative_prompt', 'size', 'steps', 'cfg_scale', 'sampler', 'seed'):
                self.assertEqual(result[key], sample[key], (sample['recipe'], key))
            if sample['recipe'] in modeling_reference.RECIPE_ASSETS and 'modeling_view' not in sample['inputs']:
                self.assertEqual(result, compose(dict(sample['inputs'], quality=sample['quality'], seed=sample['seed'], modeling_view='off')))

    def test_all_supported_assets_and_views_fit_the_runtime_with_moss(self):
        for recipe in (r for r in recipes() if r['modeling_asset']):
            for asset in modeling_reference.ASSETS:
                for view in modeling_reference.VIEWS:
                    with self.subTest(recipe=recipe['id'], asset=asset, view=view):
                        result = compose(dict(recipe=recipe['id'], subject='a simple game asset', modeling_view=view, modeling_asset=asset, seed=42))
                        validate_request({k: v for k, v in result.items() if k != 'preset'}, result['model'], max_dimension=1536)
                        self.assertIn('a simple game asset', result['prompt'])
                        self.assertIn('plain light gray background', result['prompt'])
                        self.assertNotIn(recipe['scene'], result['prompt'])
                        self.assertEqual(result['size'], modeling_reference.ASSETS[asset]['size'])
                        self.assertEqual(result['model'], 'moss')
                        self.assertEqual(result['cfg_scale'], 3)

    def test_character_replaces_portrait_and_vehicle_replaces_inventory_composition(self):
        character = compose(dict(recipe='lowpoly-character', subject='an adult courier', modeling_view='front'))
        self.assertIn('neutral standing A-pose', character['prompt'])
        self.assertIn('head to soles', character['prompt'])
        self.assertNotIn('waist-up', character['prompt'])
        self.assertIn('close-up portrait', character['negative_prompt'])
        kart = compose(dict(recipe='lowpoly-prop', subject='a small racing kart', modeling_view='top', modeling_asset='vehicle', scene='a centered seat', details='orange panels'))
        self.assertIn('looking vertically down', kart['prompt'])
        self.assertIn('axles', kart['prompt'])
        self.assertIn('a centered seat', kart['prompt'])
        self.assertIn('orange panels', kart['prompt'])
        self.assertNotIn('stone plinth', kart['prompt'])

    def test_aspect_ratio_and_quality_override_reference_defaults(self):
        for model_recipe in ('lowpoly-character', 'lowpoly-character', 'lowpoly-diorama'):
            for ratio in formats():
                for quality in ('preview', 'standard', 'detail'):
                    result = compose(dict(recipe=model_recipe, subject='a game asset', modeling_view='side', quality=quality, aspect_ratio=ratio['id']))
                    self.assertEqual(result['size'], ratio['preview_size' if quality == 'preview' else 'size'])
        self.assertEqual(compose(dict(recipe='lowpoly-world', subject='a tile', modeling_view='three-quarter', quality='preview'))['steps'], 30)

    def test_inapplicable_and_malformed_settings_are_rejected(self):
        for extra in ({'modeling_view': []}, {'modeling_view': True}, {'modeling_view': 'turnaround'},
                      {'modeling_view': 'front', 'modeling_asset': {}}, {'modeling_view': 'front', 'modeling_asset': '/tmp/model'},
                      {'modeling_asset': 'vehicle'}, {'modeling_view': 'off', 'modeling_asset': 'vehicle'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                compose(dict(recipe='lowpoly-prop', subject='a kart', **extra))
        for recipe in ('anima-portrait', 'photo-product', 'qwen-world', 'pixel-character'):
            with self.assertRaises(ValueError): compose(dict(recipe=recipe, subject='a robot', modeling_view='front'))

    def test_stored_inputs_reproduce_reference_and_still_reject_runtime_controls(self):
        body = dict(recipe='lowpoly-character', subject='an adult courier', modeling_view='back', modeling_asset='character', quality='preview', seed=42)
        with tempfile.TemporaryDirectory() as root:
            studio = Studio(Mock(model='moss', cfg={'runtime': '/unused', 'models': {'moss': {}}}), root)
            prepared = studio.prepare(body)
            self.assertEqual(prepared['modeling_version'], modeling_reference.VERSION)
            self.assertEqual(prepared['recipe_inputs']['modeling_view'], 'back')
            self.assertEqual(prepared['recipe_inputs']['modeling_asset'], 'character')
            restored = compose(dict(prepared['recipe_inputs'], model=prepared['model'], seed=prepared['seed']))
            self.assertEqual(restored['prompt'], prepared['prompt'])
            self.assertEqual(restored['size'], prepared['size'])
            with self.assertRaises(APIError): studio.prepare(dict(body, details='<lora:untrusted:1>'))


if __name__ == '__main__':
    unittest.main()
