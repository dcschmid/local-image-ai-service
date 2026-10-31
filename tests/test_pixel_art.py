import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, PngImagePlugin
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from pixel_art import refine, settings
from service import APIError, Backend
from studio_service import Studio
from recipes import recipes, compose


def png(image):
    out=io.BytesIO();info=PngImagePlugin.PngInfo();info.add_text('parameters','original native metadata')
    image.save(out,format='PNG',pnginfo=info);return out.getvalue()

class PixelTests(unittest.TestCase):
    def test_grid_palette_determinism_and_metadata(self):
        image=Image.new('RGB',(1024,576))
        image.putdata([(x%256,y%256,(x+y)%256) for y in range(576) for x in range(1024)])
        raw=png(image)
        large,small,meta=refine(raw,64,24)
        self.assertEqual(refine(raw,64,24),(large,small,meta))
        with Image.open(io.BytesIO(small)) as native,Image.open(io.BytesIO(large)) as enlarged:
            self.assertEqual(native.size,(64,36));self.assertEqual(enlarged.size,image.size)
            self.assertLessEqual(len(native.getcolors(128)),24)
            self.assertEqual(enlarged.tobytes(),native.resize(image.size,Image.Resampling.NEAREST).tobytes())
            self.assertEqual(enlarged.info['parameters'],'original native metadata')
            self.assertEqual(json.loads(native.info['AtelierPixel']),meta)

    def test_modal_color_precedes_center_but_center_breaks_tie(self):
        image=Image.new('RGB',(32,32),'red');draw=ImageDraw.Draw(image)
        draw.rectangle((16,0,31,31),fill='blue')
        _,small,_=refine(png(image),32,16)
        with Image.open(io.BytesIO(small)) as result:self.assertEqual(result.getpixel((0,0)),(0,0,255))
        draw.rectangle((16,0,31,14),fill='red')
        _,small,_=refine(png(image),32,16)
        with Image.open(io.BytesIO(small)) as result:self.assertEqual(result.getpixel((0,0)),(255,0,0))

    def test_strict_settings_and_matching_prepared_variant(self):
        for grid,colors in [(True,24),(16,24),(64,25),(64,False),('64',24)]:
            with self.assertRaises(ValueError):settings(grid,colors)
        with tempfile.TemporaryDirectory() as root:
            cfg={'active_model':'krea-pixel','runtime':'/unused','models':{'krea-pixel':{f'lora{g}':f'/owned/k2-pixel{g}.safetensors' for g in (32,64,128)}},'generation_timeout':2}
            backend=Backend(cfg);studio=Studio(backend,root)
            # Model files are fixtures: test validation and native request independently of downloads.
            with patch('service.missing_files',return_value=[]):
                for grid in (32,64,128):
                    backend.pixel_grid=grid
                    job=studio.submit(dict(model='krea-pixel',prompt='a crystal',pixel_grid=grid))
                    with patch('studio_service.native_request',side_effect=[{'id':'native'},{'status':'completed','result':{'ok':True}}]) as native:
                        self.assertEqual(studio.generate(job),{'ok':True})
                    payload=native.call_args_list[0].args[3]
                    self.assertNotIn('lora',payload)
                    self.assertEqual(payload['sample_params']['sample_steps'],8)
                    self.assertEqual(payload['sample_params']['scheduler'],'flux')
                    self.assertEqual(payload['sample_params']['extra_sample_args'],'base_shift=1.15,max_shift=1.15')
                    backend.pixel_grid=128 if grid==64 else 64
                    with self.assertRaisesRegex(ValueError,'loaded pixel variant'):studio.generate(job)
                for extra in ({'lora':'/tmp/arbitrary'},{'pixel_grid':'../../x'},{'pixel_colors':True}):
                    with self.assertRaises(APIError):studio.prepare(dict(model='krea-pixel',prompt='tree',**extra))

    def test_saved_native_pixels_deleted_with_gallery_image(self):
        with tempfile.TemporaryDirectory() as root:
            backend=Backend({'active_model':'krea-pixel','runtime':'/unused','models':{'krea-pixel':{}}})
            studio=Studio(backend,root)
            job=studio.submit(dict(model='krea-pixel',prompt='a crystal',size='512x512',pixel_grid=32))
            job['started']=time.time()
            studio.save_result(job,{'images':[{'b64_json':base64.b64encode(png(Image.new('RGB',(512,512),'blue'))).decode()}]})
            item=studio.get(job['id'],'image');self.assertEqual(item['pixel']['width'],16)
            with Image.open(studio.pixel_file(job['id'])) as image:self.assertEqual(image.size,(16,16))
            job['status']='completed';studio.put('job',job)
            studio.delete_image(job['id'])
            self.assertFalse(studio.pixel_file(job['id']).exists());self.assertFalse(studio.file(job['id']).exists())

    def test_presets_use_eight_steps_and_author_trigger_advice(self):
        for recipe in (r for r in recipes() if r['model']=='krea-pixel'):
            for grid in (32,64,128):
                result=compose(dict(recipe=recipe['id'],subject='a crystal',pixel_grid=grid,quality='preview'))
                self.assertEqual((result['steps'],result['cfg_scale'],result['size'],result['negative_prompt']),(8,1.,'1024x1024',''))
                self.assertEqual('pixel art' in result['prompt'],grid!=64)
        with self.assertRaises(ValueError):compose(dict(recipe='anima-portrait',subject='a mage',pixel_grid=64))

class PreparedWeightTests(unittest.TestCase):
    def test_dora_preserves_learned_row_magnitudes(self):
        import importlib.util
        if importlib.util.find_spec('numpy') is None:self.skipTest('Optional converter dependency is not installed')
        import numpy as np
        spec=importlib.util.spec_from_file_location('pixel_converter',Path(__file__).resolve().parents[1]/'scripts/prepare-pixel-models.py')
        converter=importlib.util.module_from_spec(spec);spec.loader.exec_module(converter)
        weight=np.array([[3,0],[0,4]],dtype=np.float32)
        down=np.array([[0,4],[3,0]],dtype=np.float32)
        merged=converter.merge_dora(weight,down,np.eye(2,dtype=np.float32),np.array([10,2.5],dtype=np.float32))
        np.testing.assert_allclose(merged,[[6,8],[1.5,2]])
        np.testing.assert_allclose(np.linalg.norm(merged,axis=1),[10,2.5])
        with self.assertRaises(ValueError):converter.merge_dora(weight*0,down*0,np.eye(2),np.ones(2))

    def test_native_loader_selects_only_the_prepared_grid_variant(self):
        import socket
        from unittest.mock import Mock
        roles={role:'/owned/'+role for role in ('diffusion','llm','vae','lora32','lora64','lora128','pixel32','pixel64','pixel128')}
        cfg=dict(active_model='krea-pixel',runtime='/unused',models={'krea-pixel':roles},cuda_lib='/cuda',gpu_uuid='GPU-1234',backend_port=17861,load_timeout=1)
        for grid in (32,64,128):
            backend=Backend(cfg);backend.pixel_grid=grid
            process=Mock(pid=12345,returncode=1);process.poll.return_value=1
            with patch('service.missing_files',return_value=[]),patch('service.foreign_compute',return_value=[]),patch('service.gpu_check'),patch('service.socket.create_connection',side_effect=ConnectionRefusedError),patch('service.subprocess.Popen',return_value=process) as launch:
                backend.start()
            arguments=launch.call_args.args[0]
            self.assertEqual(arguments[arguments.index('--diffusion-model')+1],roles['pixel'+str(grid)])
            self.assertNotIn('--lora-model-dir',arguments)
            self.assertNotIn(roles['diffusion'],arguments)
            for value in (32,64,128):self.assertNotIn(roles['lora'+str(value)],arguments)
