import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from catalog import MODELS
from recipes import compose,recipes
from service import APIError,Backend
from studio_service import Studio

VARIANTS={'anima-psx':('LowPolyPSX_AnimaPreview2_byKonan.safetensors',.9),'anima-lowpoly':('AnimaLowPoly.safetensors',.75)}

class AnimaLowPolyTests(unittest.TestCase):
    def test_curated_adapter_is_applied_to_native_request_and_recorded(self):
        for model,(filename,weight) in VARIANTS.items():
            with self.subTest(model=model),tempfile.TemporaryDirectory() as root:
                backend=Backend(dict(active_model=model,runtime='/unused',models={model:{'lora':'/owned/'+filename}},generation_timeout=2))
                studio=Studio(backend,root)
                with patch('service.missing_files',return_value=[]):
                    job=studio.submit(dict(model=model,prompt='an angular cabin',size='512x512',seed=42))
                    for field in ('lora','lora_path','lora_strength'):
                        with self.assertRaises(APIError):studio.prepare(dict(model=model,prompt='a cabin',**{field:'/tmp/untrusted'}))
                with patch('studio_service.native_request',side_effect=[{'id':'native'},{'status':'completed','result':{'ok':True}}]) as native:
                    self.assertEqual(studio.generate(job),{'ok':True})
                payload=native.call_args_list[0].args[3]
                self.assertEqual(payload['lora'],[dict(path=filename,multiplier=weight)])
                self.assertEqual(payload['prompt'],'an angular cabin')
                image=Image.new('RGB',(512,512),'green');out=io.BytesIO();image.save(out,format='PNG')
                job['started']=time.time();studio.save_result(job,{'images':[{'b64_json':base64.b64encode(out.getvalue()).decode()}]})
                saved=studio.get(job['id'],'image')
                self.assertEqual(saved['sampling']['lora_strength'],weight)
                self.assertEqual(saved['components']['lora'],'/owned/'+filename)
                self.assertNotIn('pixel',saved)

    def test_compatibility_route_uses_the_same_trusted_adapter(self):
        image=Image.new('RGB',(512,512),'green');out=io.BytesIO();image.save(out,format='PNG')
        for model,(filename,weight) in VARIANTS.items():
            response=Mock(status=200);response.read.return_value=json.dumps(dict(data=[dict(b64_json=base64.b64encode(out.getvalue()).decode())])).encode()
            conn=Mock();conn.getresponse.return_value=response
            backend=Backend(dict(active_model=model,models={model:{'lora':'/owned/'+filename}},backend_port=17861,generation_timeout=2))
            with patch.object(backend,'available',return_value=True),patch('service.http.client.HTTPConnection',return_value=conn):
                result=backend.generate(dict(prompt='a cabin',size='512x512'),42)
            self.assertEqual(result['model'],model)
            request=json.loads(conn.request.call_args.args[2])
            extra=json.loads(request['prompt'].split('<sd_cpp_extra_args>')[1].split('</sd_cpp_extra_args>')[0])
            self.assertEqual(extra['lora'],[dict(path=filename,multiplier=weight)])

    def test_native_loader_confines_adapter_paths_to_its_directory(self):
        for model,(filename,_) in VARIANTS.items():
            cfg=dict(active_model=model,runtime='/unused',models={model:dict(diffusion='/base/model',llm='/base/encoder',vae='/base/vae',lora='/owned/'+filename)},cuda_lib='/cuda',gpu_uuid='GPU-1234',backend_port=17861,load_timeout=1)
            backend=Backend(cfg);process=Mock(pid=12345,returncode=1);process.poll.return_value=1
            with patch('service.missing_files',return_value=[]),patch('service.foreign_compute',return_value=[]),patch('service.gpu_check'),patch('service.socket.create_connection',side_effect=ConnectionRefusedError),patch('service.subprocess.Popen',return_value=process) as launch:
                backend.start()
            args=launch.call_args.args[0]
            self.assertEqual(args[args.index('--lora-model-dir')+1],'/owned')
            self.assertEqual(args[args.index('--diffusion-model')+1],'/base/model')
            self.assertNotIn('/owned/'+filename,args)

    def test_recipe_triggers_profiles_and_subject_only_inputs(self):
        selected=[r for r in recipes() if r['model'] in VARIANTS]
        self.assertEqual(len(selected),6)
        for recipe in selected:
            for quality,steps in [('preview',30),('standard',35),('detail',45)]:
                result=compose(dict(recipe=recipe['id'],subject='an angular wooden cabin',quality=quality,seed=42))
                self.assertEqual(result['steps'],steps);self.assertEqual(result['cfg_scale'],4.5)
                self.assertIn('an angular wooden cabin',result['prompt'])
                self.assertIn('psx' if recipe['model']=='anima-psx' else 'l0wp0ly',result['prompt'])
                self.assertNotIn('nsfw',result['negative_prompt'])
                self.assertNotIn('score_',result['prompt'])

class AdapterInstallerTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'scripts/install-models.py'
        spec=importlib.util.spec_from_file_location('adapter_installer',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def test_downloaded_file_is_verified_and_copied_without_changing_original(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as root:
            home=Path(root);repo=home/'repo';(repo/'config').mkdir(parents=True)
            config=home/'.config/local-image-ai-service/config.json';config.parent.mkdir(parents=True);config.write_text(json.dumps(dict(models={})))
            downloads=home/'Downloads';downloads.mkdir();source=downloads/'AnimaLowPoly.safetensors';header={'lora_te_layers_0_mlp_down_proj.alpha':{'dtype':'F32','shape':[],'data_offsets':[0,4]}};encoded=json.dumps(header).encode();raw=struct.pack('<Q',len(encoded))+encoded+struct.pack('<f',32.0);source.write_bytes(raw)
            entry=dict(provider='civitai',file=source.name,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),url='https://civitai.com/api/download/models/2692813')
            (repo/'config/models.lock.json').write_text(json.dumps({'anima-lowpoly':{'lora':entry}}))
            with patch.object(module,'HOME',home),patch.object(module,'ROOT',repo),patch.object(sys,'argv',['installer','anima-lowpoly','--download-only']),patch('urllib.request.urlopen') as network:
                module.main()
            destination=home/'.local/share/local-image-ai-service/models'/source.name
            self.assertEqual(destination.read_bytes(),raw);self.assertEqual(source.read_bytes(),raw)
            self.assertFalse(destination.samefile(source));network.assert_not_called()
            self.assertEqual(json.loads(config.read_text()),dict(models={}))
            destination.unlink();source.write_bytes(b'wrong weights')
            with patch.object(module,'HOME',home),patch.object(module,'ROOT',repo),patch.object(sys,'argv',['installer','anima-lowpoly','--download-only']),patch('urllib.request.urlopen') as network:
                with self.assertRaises(SystemExit):module.main()
            self.assertFalse(destination.exists());self.assertEqual(source.read_bytes(),b'wrong weights');network.assert_not_called()

class AdapterNameTests(unittest.TestCase):
    def test_text_encoder_names_preserve_projection_underscores_and_payload(self):
        from lora_adapter import tensor_name,prepare
        for module in ['mlp_down_proj','mlp_gate_proj','mlp_up_proj','self_attn_q_proj','self_attn_k_proj','self_attn_v_proj','self_attn_o_proj']:
            key='lora_te_layers_3_'+module+'.lora_down.weight'
            renamed=tensor_name(key)
            self.assertTrue(renamed.startswith('lora.text_encoders.llm.model.layers.3.'))
            self.assertIn(module.split('_')[-2]+'_proj',renamed)
            self.assertNotIn('.o.proj',renamed)
        with self.assertRaises(ValueError):tensor_name('lora_te_unknown.alpha')
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source.safetensors';target=Path(root)/'native.safetensors'
            key='lora_te_layers_3_self_attn_o_proj.lora_down.weight'
            payload=b'\x00\x00\x80\x3f'
            header={key:dict(dtype='F32',shape=[1],data_offsets=[0,4]),'__metadata__':{'author':'original'}}
            encoded=json.dumps(header).encode();raw=struct.pack('<Q',len(encoded))+encoded+payload;source.write_bytes(raw)
            digest=hashlib.sha256(raw).hexdigest();prepare(source,target,digest)
            with target.open('rb') as reader:
                length=struct.unpack('<Q',reader.read(8))[0];converted=json.loads(reader.read(length));self.assertEqual(reader.read(),payload)
            self.assertIn('lora.text_encoders.llm.model.layers.3.self_attn.o_proj.lora_down.weight',converted)
            self.assertEqual(converted['__metadata__']['author'],'original');self.assertEqual(source.read_bytes(),raw)
            original=target.read_bytes();prepare(source,target,digest);self.assertEqual(target.read_bytes(),original)
            with self.assertRaises(ValueError):prepare(source,target,'0'*64)
            self.assertEqual(target.read_bytes(),original)
