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
    def test_lowpoly_example_requires_the_complete_text_encoder_mapping(self):
        recipe=next(r for r in recipes() if r['id']=='anima3d-diorama')
        inputs=dict(recipe=recipe['id'],**recipe['example'],quality='standard')
        item=dict(request=dict(compose(dict(inputs,seed=42)),recipe_inputs=inputs),sampling={'lora_strength':.75})
        self.assertFalse(builder.matches(item,recipe))
        item['sampling']['adapter_revision']='qwen-names-v1'
        self.assertTrue(builder.matches(item,recipe))
        item['sampling']['lora_strength']=.9
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
