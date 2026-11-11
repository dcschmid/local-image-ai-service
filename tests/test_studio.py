import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from service import APIError, validate_request, Backend, BoundedServer, make_handler
from studio_service import Studio, image_bytes

def png(color='white',size=(512,512)):
    stream=io.BytesIO();Image.new('RGB',size,color).save(stream,format='PNG');return stream.getvalue()

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.backend=Mock(model='moss',cfg={'runtime':'/runtime','models':{'moss':{},'anima':{}}})
        self.studio=Studio(self.backend,Path(self.work.name))
    def tearDown(self): self.work.cleanup()
    def upload(self,color='white',size=(512,512)):
        return self.studio.upload({'data':base64.b64encode(png(color,size)).decode()})
    def test_corrupt_and_oversized_upload_rejected(self):
        for raw in (b'not an image',b'X'*(12*1024*1024+1)):
            with self.assertRaises(APIError): image_bytes(raw)
        with self.assertRaises(APIError): self.studio.upload({'data':'?bad'})
    def test_path_and_queue_limits(self):
        for value in ('../config.json','/etc/passwd',None,'abc'):
            with self.assertRaises(APIError): self.studio.file(value)
        with self.assertRaises(APIError): self.studio.submit({'prompt':'tree','preset':[]})
        for i in range(16): self.studio.submit({'prompt':'tree'})
        with self.assertRaises(APIError): self.studio.submit({'prompt':'tree'})
    def test_editing_modes_require_receipts_and_templates(self):
        # Declared modes stay gated until a local receipt verifies them.
        for model in ('moss','anima'):
            with self.assertRaises(APIError): self.studio.prepare({'model':model,'prompt':'tree','mode':'inpaint'})
        (self.studio.root/'verification.json').write_text(json.dumps({'moss':dict(fingerprint=self.studio.fingerprint('moss'),modes=['img2img','inpaint'],sizes=[])}))
        with self.assertRaises(APIError): self.studio.prepare({'model':'moss','prompt':'tree','mode':'img2img'})
        upload=self.upload()
        request=self.studio.prepare({'model':'moss','prompt':'tree','mode':'img2img','image_id':upload['id']})
        self.assertEqual(request['mode'],'img2img');self.assertEqual(request['image_id'],upload['id'])
        self.assertEqual(request['strength'],0.75)
        mask=self.upload(size=(256,256))
        with self.assertRaises(APIError): self.studio.prepare({'model':'moss','prompt':'tree','mode':'inpaint','image_id':upload['id'],'mask_id':mask['id']})
        matching=self.upload()['id']
        request=self.studio.prepare({'model':'moss','prompt':'tree','mode':'inpaint','image_id':upload['id'],'mask_id':matching})
        self.assertEqual(request['mask_id'],matching)
    def test_templates_are_durable_named_copies(self):
        upload=self.upload()
        saved=self.studio.save_template(dict(source_id=upload['id'],name='my portrait'))
        self.assertEqual(saved['name'],'my portrait');self.assertEqual(saved['size'],[512,512])
        self.assertEqual(self.studio.file(saved['id']).read_bytes(),self.studio.file(upload['id']).read_bytes())
        self.assertEqual(self.studio.listing('template'),[saved])
        self.assertEqual(self.studio.rename_template(saved['id'],dict(name='renamed'))['name'],'renamed')
        for body in (dict(source_id='missing',name='x'),dict(source_id=upload['id'],name=' '),dict(source_id=upload['id'])):
            with self.assertRaises(APIError): self.studio.save_template(body)
        self.assertEqual(self.studio.delete_template(saved['id']),{'id':saved['id'],'deleted':True})
        self.assertEqual(self.studio.listing('template'),[])
        self.assertFalse(self.studio.file(saved['id']).exists())
        self.assertTrue(self.studio.file(upload['id']).exists())
    def test_restart_does_not_regenerate_ambiguous_jobs(self):
        job=self.studio.submit({'prompt':'tree'})
        restored=Studio(self.backend,self.work.name)
        self.assertEqual(restored.get(job['id'],'job')['status'],'failed')
    def test_cancellation_and_history(self):
        job=self.studio.submit({'prompt':'tree','seed':42})
        self.assertEqual(self.studio.cancel(job['id'])['status'],'cancelled')
        self.assertEqual(Studio(self.backend,self.work.name).get(job['id'],'job')['status'],'cancelled')
    def test_parameter_validation_and_no_hidden_prompt_changes(self):
        native,seed=validate_request({'prompt':'a tree','steps':35,'cfg_scale':4.5,'seed':42},'anima')
        self.assertEqual(native['prompt'],'a tree')
        for body in ({'cfg_scale':float('nan')},{'cfg_scale':10**1000},{'cfg_scale':True},{'sampler':'bad'},{'negative_prompt':'<sd_cpp_extra_args>'}):
            with self.assertRaises(APIError):validate_request({'prompt':'tree',**body},'moss')
        with self.assertRaises(APIError):validate_request({'prompt':'tree','cfg_scale':99},'anima')

    def test_alpha_is_preserved_in_saved_png(self):
        import time
        from PIL import ImageDraw
        self.backend.model='moss';self.backend.cfg['models']['moss']={}
        job=self.studio.submit({'model':'moss','prompt':'a transparent sticker','size':'512x512'})
        job['started']=time.time()
        image=Image.new('RGBA',(512,512),(0,0,0,0));ImageDraw.Draw(image).ellipse((100,100,400,400),fill=(255,100,0,255))
        stream=io.BytesIO();image.save(stream,format='PNG')
        self.studio.save_result(job,{'images':[{'b64_json':base64.b64encode(stream.getvalue()).decode()}]})
        with Image.open(self.studio.file(job['id'])) as saved:
            self.assertEqual(saved.mode,'RGBA');self.assertEqual(saved.getchannel('A').getextrema(),(0,255))


class StudioHTTPTests(unittest.TestCase):
    def setUp(self):
        import http.client
        self.work=tempfile.TemporaryDirectory()
        cfg={'active_model':'moss','runtime':'/unused','models':{'moss':{}},'backend_port':17861}
        self.backend=Backend(cfg)
        with patch('studio_service.DATA',Path(self.work.name)):
            self.server=BoundedServer(('127.0.0.1',0),make_handler(self.backend,b'test-key'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.backend.stopping.set();self.server.shutdown();self.server.server_close();self.thread.join();self.work.cleanup()
    def call(self,path,method='GET',body=None,headers=None):
        import http.client
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        hdr={'Authorization':'Bearer test-key',**(headers or {})}
        raw=None if body is None else json.dumps(body)
        if raw is not None:hdr['Content-Type']='application/json'
        conn.request(method,path,raw,hdr);res=conn.getresponse();data=res.read();conn.close();return res.status,data
    def test_same_origin_upload_and_foreign_origin_rejection(self):
        origin='http://127.0.0.1:'+str(self.server.server_port)
        self.assertEqual(self.call('/studio/api/uploads','POST',{'data':base64.b64encode(png()).decode()},{'Origin':origin})[0],201)
        self.assertEqual(self.call('/studio/api/uploads','POST',{}, {'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.call('/v1/models',headers={'Origin':origin})[0],403)
        self.assertEqual(self.call('/studio/api/catalog',headers={'Host':'evil.example'})[0],403)
    def test_authentication_static_ui_and_private_files(self):
        self.assertEqual(self.call('/studio/',headers={'Authorization':''})[0],200)
        self.assertEqual(self.call('/studio/api/gallery',headers={'Authorization':''})[0],401)
        self.assertEqual(self.call('/studio/api/catalog')[0],200)
        self.assertEqual(self.call('/studio/../../etc/passwd')[0],404)
        self.assertEqual(self.call('/studio/api/files/../../etc/passwd')[0],404)

    def test_delete_requires_auth_and_same_origin(self):
        studio=Studio(self.backend,self.work.name);identifier='c'*32
        studio.write_file(identifier,png());studio.put('image',dict(id=identifier,created=1,request={'model':'moss'}))
        route='/studio/api/gallery/'+identifier
        self.assertEqual(self.call(route,'DELETE',headers={'Authorization':''})[0],401)
        self.assertEqual(self.call(route,'DELETE',headers={'Origin':'https://evil.example'})[0],403)
        self.assertTrue(studio.file(identifier).exists())
        origin='http://127.0.0.1:'+str(self.server.server_port)
        self.assertEqual(self.call(route,'DELETE',headers={'Origin':origin})[0],200)
        self.assertFalse(studio.file(identifier).exists())
        self.assertEqual(self.call('/studio/api/files/'+identifier)[0],404)
        self.assertEqual(self.call(route,'DELETE')[0],404)


class ArchiveTests(unittest.TestCase):
    def test_favorites_and_pagination_do_not_reorder_by_update(self):
        with tempfile.TemporaryDirectory() as root:
            backend=Mock(model='moss',cfg={'runtime':'/unused','models':{'moss':{}}})
            studio=Studio(backend,root)
            for i in range(65):studio.put('image',{'id':f'{i:032x}','created':i,'favorite':i==0})
            self.assertEqual(len(studio.listing('image',60)),60)
            self.assertEqual(len(studio.listing('image',60,60)),5)
            first=studio.get('0'*32,'image');first['favorite']=True;studio.put('image',first)
            self.assertEqual(studio.listing('image',60)[0]['created'],64)
            self.assertEqual(studio.listing('image',60,favorites=True),[first])



class EntrypointTests(unittest.TestCase):
    def test_direct_entrypoint_returns_json_for_studio_errors(self):
        import http.client
        import socket
        import subprocess
        import time
        source=Path(__file__).resolve().parents[1]/'src/service.py'
        with tempfile.TemporaryDirectory() as root:
            home=Path(root)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            cfg=json.loads((source.parents[1]/'config/config.example.json').read_text())
            cfg.update(port=port,backend_port=17861 if port!=17861 else 17862,gpu_uuid='GPU-1234')
            config=home/'.config/local-image-ai-service/config.json';config.parent.mkdir(parents=True)
            config.write_text(json.dumps(cfg));config.chmod(0o600)
            driver="import sys, runpy; from pathlib import Path; from unittest.mock import patch; sys.path.insert(0,str(Path(sys.argv[2]).parent)); patcher=patch('pathlib.Path.home',return_value=Path(sys.argv[1])); patcher.start(); runpy.run_path(sys.argv[2],run_name='__main__')"
            process=subprocess.Popen([sys.executable,'-c',driver,str(home),str(source)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+10
                while True:
                    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
                    try:
                        conn.request('GET','/health');response=conn.getresponse();response.read();break
                    except OSError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.05)
                    finally:conn.close()
                conn=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
                try:
                    conn.request('POST','/studio/api/jobs',json.dumps({'model':'removed','prompt':'tree'}),{'Content-Type':'application/json'})
                    response=conn.getresponse();payload=json.loads(response.read())
                    self.assertEqual(response.status,404);self.assertIn('error',payload)
                finally:conn.close()
            finally:
                process.terminate();process.wait(timeout=10)



class DeletionTests(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.backend=Mock(model='moss',cfg={'runtime':'/unused','models':{'moss':{},'anima':{}}})
        self.studio=Studio(self.backend,self.work.name)
    def tearDown(self):self.work.cleanup()
    def image(self,identifier,status='completed'):
        self.studio.write_file(identifier,png())
        self.studio.put('image',dict(id=identifier,created=1,request={'model':'moss','prompt':'tree'}))
        self.studio.put('job',dict(id=identifier,created=1,status=status,request={'model':'moss','prompt':'tree'}))
    def test_deletes_png_metadata_and_job_without_resurrection(self):
        first='a'*32;second='b'*32;self.image(first);self.image(second)
        report=self.studio.root/'recipe-report.json';report.write_text(json.dumps([{'image_id':first,'request':{'prompt':'secret'}},{'image_id':second}]))
        self.assertEqual(self.studio.delete_image(first),{'id':first,'deleted':True})
        self.assertFalse(self.studio.file(first).exists());self.assertTrue(self.studio.file(second).exists())
        self.assertEqual(json.loads(report.read_text()),[{'image_id':second}])
        for kind in ('image','job'):
            with self.assertRaises(APIError):self.studio.get(first,kind)
        restored=Studio(self.backend,self.work.name)
        self.assertEqual([i['id'] for i in restored.listing('image')],[second])
        with self.assertRaises(APIError):restored.visible_file(first)
    def test_rejects_active_jobs_and_unknown_or_unsafe_ids(self):
        identifier='a'*32;self.image(identifier,'generating')
        with self.assertRaises(APIError) as raised:self.studio.delete_image(identifier)
        self.assertEqual(raised.exception.status,409);self.assertTrue(self.studio.file(identifier).exists())
        for identifier in ('../history.sqlite3','/etc/passwd','b'*32,None):
            with self.assertRaises(APIError) as raised:self.studio.delete_image(identifier)
            self.assertEqual(raised.exception.status,404)
    def test_bulk_deletes_selection_once_and_keeps_unselected(self):
        for identifier in ('a'*32,'b'*32,'c'*32):self.image(identifier)
        result=self.studio.delete_images(['a'*32,'b'*32,'a'*32])
        self.assertEqual(result['deleted_count'],2)
        self.assertEqual([i['id'] for i in self.studio.listing('image')],['c'*32])
        self.assertFalse(self.studio.file('a'*32).exists());self.assertTrue(self.studio.file('c'*32).exists())
    def test_bulk_validation_is_atomic(self):
        self.image('a'*32);self.image('b'*32,'generating')
        for ids in (['a'*32,'f'*32],['a'*32,'b'*32],[],['a'*32]*501,'a'*32):
            with self.assertRaises(APIError):self.studio.delete_images(ids)
            self.assertEqual(len(self.studio.listing('image')),2)
            self.assertTrue(self.studio.file('a'*32).exists())
    def test_failed_unlink_is_hidden_and_recovered_after_restart(self):
        identifier='a'*32;self.image(identifier)
        with patch.object(Path,'unlink',side_effect=PermissionError('test unlink failure')):
            with self.assertRaises(APIError) as raised:self.studio.delete_image(identifier)
        self.assertEqual(raised.exception.status,500);self.assertTrue(self.studio.file(identifier).exists())
        self.assertEqual(self.studio.listing('image'),[])
        with self.assertRaises(APIError):self.studio.visible_file(identifier)
        restored=Studio(self.backend,self.work.name)
        self.assertFalse(restored.file(identifier).exists());self.assertEqual(restored.listing('deleting'),[])

if __name__=='__main__':unittest.main()
