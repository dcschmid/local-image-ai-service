import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from recipes import recipes, compose, formats, VERSION
from studio_service import Studio
from service import APIError, validate_request

class RecipeTests(unittest.TestCase):
    def test_general_lowpoly_keeps_subject_choice_and_track_overview_has_its_own_framing(self):
        for subject in ('a fox', 'an alien spacecraft', 'a crystal cave', 'a racing circuit'):
            result=compose(dict(recipe='lowpoly-anything',subject=subject,quality='preview',seed=42))
            self.assertEqual((result['model'],result['steps'],result['cfg_scale']),('moss',30,3.))
            self.assertIn(subject,result['prompt'])
            self.assertNotIn('A-pose',result['prompt']);self.assertNotIn('chassis level',result['prompt'])
        overview=compose(dict(recipe='lowpoly-track-overview',subject='an alpine kart circuit',quality='standard',aspect_ratio='16:9'))
        self.assertEqual((overview['size'],overview['steps']),('1024x576',50))
        self.assertIn('complete closed driving loop',overview['prompt'])
        self.assertIn('directly overhead',overview['prompt'])
        self.assertIn('disconnected road segments',overview['negative_prompt'])

    def test_all_lowpoly_recipes_use_moss_and_retired_recipes_are_unavailable(self):
        selected=[recipe for recipe in recipes() if recipe['category']=='lowpoly']
        self.assertEqual(len(selected),9)
        self.assertTrue(all(recipe['model']=='moss' for recipe in selected))
        for recipe_id in ('lowpoly-character','lowpoly-vehicle','lowpoly-prop','lowpoly-building'):
            recipe=next(recipe for recipe in selected if recipe['id']==recipe_id)
            prepared=compose(dict(recipe=recipe_id,**recipe['example'],quality='standard'))
            self.assertEqual((prepared['steps'],prepared['cfg_scale'],prepared['sampler']),(50,3.,'euler'))
            self.assertNotIn('l0wp0ly',prepared['prompt']);self.assertNotIn('<lora:',prepared['prompt'])
        for recipe_id in ('psx-prop','anima3d-character'):
            with self.assertRaises(ValueError):compose(dict(recipe=recipe_id,subject='a kart'))

    def test_all_examples_compose_with_expected_model_settings(self):
        for r in recipes():
            with self.subTest(recipe=r['id']):
                body=dict(model=r['model'],recipe=r['id'],**r['example'])
                result=compose(body)
                self.assertIn(r['example']['subject'],result['prompt'])
                self.assertEqual(result['size'],r['size'])
                self.assertEqual(result['cfg_scale'],{'anima':4.5,'moss':3,'qwen21':6,'krea-pixel':1}[r['model']])
                self.assertNotIn('score_',result['prompt']+result['negative_prompt'])
                self.assertNotIn('safe,',result['prompt'])
    def test_only_subject_required_and_preview_keeps_orientation(self):
        result=compose({'recipe':'anima-portrait','subject':'Eine Magierin mit roten Haaren','quality':'preview'})
        self.assertIn('Eine Magierin mit roten Haaren',result['prompt'])
        self.assertIn('city overlook',result['prompt'])
        self.assertEqual(result['size'],'576x832')
        self.assertEqual(result['steps'],30)
    def test_lowpoly_uses_moss_and_geometric_style(self):
        result=compose({'recipe':'lowpoly-diorama','subject':'a small lighthouse'})
        self.assertEqual(result['model'],'moss');self.assertEqual(result['steps'],50)
        self.assertIn('flat shading',result['prompt']);self.assertIn('isometric',result['prompt'])
    def test_photography_does_not_inherit_lowpoly_exclusions(self):
        for recipe in (r for r in recipes() if r['category']=='photo'):
            with self.subTest(recipe=recipe['id']):
                result=compose({'recipe':recipe['id'],'subject':'a test subject'})
                self.assertEqual(result['model'],'moss')
                self.assertIn(recipe['scene'],result['prompt'])
                self.assertNotIn('photorealistic textures',result['negative_prompt'])
                self.assertNotIn('glossy plastic',result['negative_prompt'])
                self.assertNotIn('flat shading',result['prompt'])
                self.assertNotIn('nsfw',result['negative_prompt'])
                self.assertIn('3d render',result['negative_prompt'])
        self.assertIn('photorealistic textures',compose({'recipe':'lowpoly-diorama','subject':'a cabin'})['negative_prompt'])
    def test_photography_quality_profiles_and_portrait_orientation(self):
        for quality,steps,size in [('preview',30,'576x832'),('standard',50,'832x1216'),('detail',60,'832x1216')]:
            with self.subTest(quality=quality):
                result=compose({'recipe':'photo-portrait','subject':'an adult baker','quality':quality,'seed':42})
                self.assertEqual((result['steps'],result['size'],result['cfg_scale'],result['sampler'],result['seed']),(steps,size,3.,'euler',42))
        self.assertEqual(compose({'recipe':'lowpoly-diorama','subject':'a cabin','quality':'preview'})['steps'],20)
    def test_qwen_literal_wording_transparency_and_sampling(self):
        result=compose({'recipe':'qwen-poster','subject':'a desert landscape','text':'HELLO WORLD','seed':42})
        self.assertIn('HELLO WORLD',result['prompt'])
        self.assertEqual((result['model'],result['steps'],result['cfg_scale']),('qwen21',40,6))
        transparent=compose({'recipe':'qwen-sticker','subject':'an orange robot'})
        self.assertTrue(transparent['prompt'].startswith('This is an RGBA image with transparency.'))
        self.assertIn('background is transparent',transparent['prompt'])
        self.assertNotIn('photorealistic textures',transparent['negative_prompt'])
        for body in ({'recipe':'anima-portrait','subject':'a mage','text':'TITLE'},{'recipe':'qwen-poster','subject':'a valley','text':'x'*601}):
            with self.assertRaises(ValueError):compose(body)
        with tempfile.TemporaryDirectory() as root:
            studio=Studio(Mock(model='qwen21',cfg={'runtime':'/unused','models':{'qwen21':{}}}),root)
            with self.assertRaises(APIError) as raised:
                studio.prepare({'recipe':'qwen-sticker','subject':'a robot','text':'<sd_cpp_extra_args>'})
            self.assertEqual(raised.exception.code,'invalid_prompt')
    def test_all_aspect_ratio_profiles_are_exact_and_fit_runtime_budget(self):
        for recipe_id in ('anima-portrait','photo-portrait','qwen-poster','lowpoly-character','lowpoly-building'):
            for format in formats():
                for quality in ('preview','standard','detail'):
                    with self.subTest(recipe=recipe_id,ratio=format['id'],quality=quality):
                        result=compose(dict(recipe=recipe_id,subject='a ceramic vase',aspect_ratio=format['id'],quality=quality))
                        width,height=map(int,result['size'].split('x'));x,y=map(int,format['id'].split(':'))
                        self.assertEqual(width*y,height*x)
                        validate_request({k:v for k,v in result.items() if k!='preset'},result['model'],max_dimension=1536)
        for ratio in ('10:1',[],None):
            with self.assertRaises(ValueError):compose(dict(recipe='qwen-poster',subject='a vase',aspect_ratio=ratio))
    def test_invalid_fields_and_conflicting_overrides_rejected(self):
        for extra in ({'subject':''},{'subject':[]},{'scene':{}},{'details':'x'*2001},{'quality':[]},{'steps':99},{'model':'moss'},{'recipe':'unknown'}):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):compose(dict({'recipe':'anima-portrait','subject':'a knight'},**extra))
    def test_service_stores_original_inputs_and_compiled_prompt(self):
        with tempfile.TemporaryDirectory() as root:
            backend=Mock(model='anima',cfg={'runtime':'/unused','models':{'anima':{},'moss':{}}})
            studio=Studio(backend,root)
            body={'recipe':'anima-portrait','subject':'an adult mage','quality':'preview','seed':42}
            result=studio.prepare(body)
            self.assertEqual(result['recipe_inputs']['subject'],'an adult mage')
            self.assertEqual(result['recipe_version'],VERSION)
            self.assertEqual(result['seed'],42)
            self.assertEqual(result['prompt'],compose(body)['prompt'])
            with self.assertRaises(APIError):studio.prepare(dict(body,subject='<sd_cpp_extra_args>'))

class PruneTests(unittest.TestCase):
    def test_removes_only_unused_owned_weights(self):
        import contextlib
        import io
        import json
        import os
        import runpy
        import subprocess
        from unittest.mock import patch
        script=Path(__file__).resolve().parents[1]/'scripts/prune-models.py'
        with tempfile.TemporaryDirectory() as root:
            home=Path(root);owned=home/'.local/share/local-image-ai-service/models';owned.mkdir(parents=True)
            unused=owned/'unused.gguf';shared=owned/'shared.safetensors';psx=owned/'psx.safetensors';lowpoly=owned/'lowpoly.safetensors';external=home/'other-app/model.gguf';external.parent.mkdir()
            for path in (unused,shared,external,psx,lowpoly):path.write_bytes(b'keep-or-remove')
            config=home/'.config/local-image-ai-service/config.json';config.parent.mkdir(parents=True)
            config.write_text(json.dumps({'active_model':'removed','models':{'moss':{'vae':str(shared)},'anima':{'vae':str(shared)},'qwen21':{'vae':str(shared)},'krea-pixel':{'pixel64':str(shared)},'anima-psx':{'lora':str(psx)},'anima-lowpoly':{'lora':str(lowpoly)},'removed':{'diffusion':str(unused),'vae':str(shared),'llm':str(external)}}}))
            old_mask=os.umask(0o077)
            try:
                with patch.object(Path,'home',return_value=home),patch('subprocess.run',return_value=subprocess.CompletedProcess([],3)),contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(script),run_name='__main__')
            finally:os.umask(old_mask)
            self.assertFalse(unused.exists());self.assertTrue(shared.exists());self.assertTrue(external.exists());self.assertFalse(psx.exists());self.assertFalse(lowpoly.exists())
            cfg=json.loads(config.read_text());self.assertEqual(set(cfg['models']),{'anima','moss','qwen21','krea-pixel'});self.assertEqual(cfg['active_model'],'moss')
