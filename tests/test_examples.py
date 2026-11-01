import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from recipes import recipes,compose
spec=importlib.util.spec_from_file_location('example_builder',Path(__file__).resolve().parents[1]/'scripts/build-examples.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class ExampleTests(unittest.TestCase):
    def test_every_bundled_recipe_has_a_current_reproducible_nonempty_example(self):
        root=Path(__file__).resolve().parents[1]/'studio/public/recipe-examples'
        manifest=json.loads((root/'manifest.json').read_text())
        current={recipe['id']:recipe for recipe in recipes()}
        self.assertEqual(set(manifest),set(current))
        for identifier,sample in manifest.items():
            with self.subTest(recipe=identifier):
                recipe=current[identifier]
                self.assertEqual(sample['model'],recipe['model'])
                self.assertEqual(sample['inputs'],dict(recipe=identifier,**recipe['example']))
                if recipe.get('example_quality'):
                    self.assertEqual(sample['quality'],recipe['example_quality'])
                expected=compose(dict(sample['inputs'],quality=sample['quality'],seed=sample['seed']))
                for key in ('prompt','negative_prompt','size','steps','cfg_scale','sampler'):
                    self.assertEqual(sample[key],expected[key],key)
                with Image.open(root/(identifier+'.webp')) as image:
                    image.load();self.assertEqual(image.format,'WEBP')
                    self.assertFalse(all(low==high for low,high in image.convert('RGB').getextrema()))
                    if sample.get('transparent'):
                        self.assertIn('A',image.getbands());self.assertLess(image.getchannel('A').getextrema()[0],250)
                if sample.get('native_url'):
                    with Image.open(root/Path(sample['native_url']).name) as native:
                        native.load();self.assertEqual(native.format,'PNG')
                        self.assertEqual(native.size,(sample['pixel']['width'],sample['pixel']['height']))

    def test_changed_weights_invalidate_cache_even_when_the_prompt_is_identical(self):
        recipe=next(r for r in recipes() if r['id']=='zimage-fantasy')
        inputs=dict(recipe=recipe['id'],**recipe['example'],quality='preview')
        item=dict(fingerprint='current-weights',request=dict(compose(dict(inputs,seed=42)),recipe_inputs=inputs))
        self.assertTrue(builder.matches(item,recipe,fingerprint='current-weights'))
        self.assertFalse(builder.matches(item,recipe,fingerprint='different-weights'))
        item.pop('fingerprint')
        self.assertFalse(builder.matches(item,recipe,fingerprint='current-weights'))

    def test_uniform_runtime_outputs_are_rejected_before_public_export(self):
        recipe=next(r for r in recipes() if r['id']=='zimage-fantasy')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'export'
            item=dict(id='a'*32,_root=root)
            for color in ('white','black'):
                Image.new('RGB',(832,576),color).save(root/(item['id']+'.png'))
                with self.assertRaisesRegex(ValueError,'uniform frame'):builder.export(item,recipe,target)
                self.assertFalse((target/(recipe['id']+'.webp')).exists())

    def test_single_color_sticker_with_a_visible_alpha_silhouette_is_not_a_blank_frame(self):
        recipe=next(r for r in recipes() if r['id']=='qwen-sticker')
        inputs=dict(recipe=recipe['id'],**recipe['example'],quality='standard')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            item=dict(id='a'*32,_root=root,request=dict(compose(dict(inputs,seed=42)),recipe_inputs=inputs))
            image=Image.new('RGBA',(128,128),(255,255,255,0))
            ImageDraw.Draw(image).ellipse((16,16,112,112),fill=(255,255,255,255))
            image.save(root/(item['id']+'.png'))
            sample=builder.export(item,recipe,root/'export')
            self.assertTrue(sample['transparent'])

    def test_moss_reference_example_matches_all_modeling_inputs(self):
        recipe=next(r for r in recipes() if r['id']=='lowpoly-prop')
        inputs=dict(recipe=recipe['id'],**recipe['example'],quality='preview')
        item=dict(request=dict(compose(dict(inputs,seed=42)),recipe_inputs=inputs),sampling={})
        self.assertTrue(builder.matches(item,recipe))
        item['request']['recipe_inputs']['modeling_view']='front'
        self.assertFalse(builder.matches(item,recipe))

    def test_custom_inputs_and_outdated_compiled_prompts_are_not_reused(self):
        recipe=next(r for r in recipes() if r['id']=='qwen-poster')
        inputs=dict(recipe=recipe['id'],**recipe['example'],quality='standard')
        request=dict(compose(dict(inputs,seed=42)),recipe_inputs=inputs)
        item={'request':request}
        self.assertTrue(builder.matches(item,recipe))
        changed=json.loads(json.dumps(item));changed['request']['recipe_inputs']['details']='a private custom scene'
        self.assertFalse(builder.matches(changed,recipe))
        changed=json.loads(json.dumps(item));changed['request']['prompt']='an older prompt version'
        self.assertFalse(builder.matches(changed,recipe))

    def test_export_distinguishes_real_transparency_from_nearly_opaque_alpha(self):
        recipe=next(r for r in recipes() if r['id']=='qwen-sticker')
        inputs=dict(recipe=recipe['id'],**recipe['example'],quality='standard')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'export'
            item=dict(id='a'*32,_root=root,request=dict(compose(dict(inputs,seed=42)),recipe_inputs=inputs))
            image=Image.new('RGBA',(1024,1024),(40,100,80,254));image.save(root/(item['id']+'.png'))
            with self.assertRaisesRegex(ValueError,'no alpha'):builder.export(item,recipe,target)
            image=Image.new('RGBA',(1024,1024),(0,0,0,0));ImageDraw.Draw(image).ellipse((100,100,900,900),fill=(255,100,0,255));image.save(root/(item['id']+'.png'))
            sample=builder.export(item,recipe,target);self.assertTrue(sample['transparent'])
            with Image.open(target/(recipe['id']+'.webp')) as result:
                self.assertIn('A',result.getbands());self.assertEqual(result.getchannel('A').getextrema(),(0,255))
