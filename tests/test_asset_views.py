"""Import trust boundaries, shared pixel palette, archives and authenticated API."""
import base64
from contextlib import redirect_stderr,redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import asset_views as assets
import manage
import service
import studio_service

DEMO=Path(__file__).resolve().parents[1]/'studio/public/asset-examples/kart.glb'


def repack(raw,change):
    size=struct.unpack_from('<I',raw,12)[0];document=json.loads(raw[20:20+size]);change(document)
    payload=json.dumps(document).encode();payload+=b' '*((-len(payload))%4);binary=raw[28+size:]
    return struct.pack('<4sII',b'glTF',2,28+len(payload)+len(binary))+struct.pack('<I4s',len(payload),b'JSON')+payload+struct.pack('<I4s',len(binary),b'BIN\0')+binary


class ImportTests(unittest.TestCase):
    def test_embedded_demo_and_malformed_headers(self):
        raw=DEMO.read_bytes();self.assertGreater(assets.validate_glb(raw)['instantiated_vertices'],900)
        for value in (b'',b'not a glb',raw[:-4],b'glTF'+b'\0'*28):
            with self.subTest(value=value[:12]),self.assertRaises(ValueError):assets.validate_glb(value)

    def test_external_references_cycles_instance_budgets_and_bad_json_types(self):
        raw=DEMO.read_bytes()
        changes=[lambda d:d['buffers'][0].update(uri='file:///etc/passwd'),
                 lambda d:d.update(asset=[]),lambda d:d.update(nodes=[None]),lambda d:d.update(meshes='bad'),
                 lambda d:d['nodes'][0].update(children=[{}]),lambda d:d['nodes'][0].update(children=[0]),
                 lambda d:d['accessors'][0].update(count=3_000_001),
                 lambda d:d['bufferViews'][0].update(byteLength=len(raw)*2),
                 lambda d:(d['meshes'][0].update(primitives=d['meshes'][0]['primitives']*16),d.update(nodes=[dict(mesh=0) for _ in range(4096)])),
                 lambda d:d.update(images=[dict(uri='https://example.com/texture.png')]),
                 lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression'])]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):assets.validate_glb(repack(raw,change))

    def test_settings_reject_paths_unknown_options_and_boolean_resolutions(self):
        for body in ({'front':'../source'},{'style':'--python'},{'pixel_grid':True},{'voxel_grid':999},{'name':'\0name'},{'path':'/etc/passwd'},[]):
            with self.subTest(body=body),self.assertRaises(ValueError):assets.settings(body)
        self.assertEqual(assets.settings({})['front'],'-Y')

    def test_shared_palette_binary_alpha_and_integrity_archive(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'model.glb').write_bytes(DEMO.read_bytes());(root/'asset-views.json').write_text(json.dumps(dict(warnings=[],cameras=[])))
            for index,view in enumerate(assets.VIEWS):
                image=Image.new('RGBA',(32,32));image.putdata([((x*8)%256,(index*38)%256,(x*17)%256,255 if x%4 else 0) for x in range(32*32)]);image.save(root/(view+'.png'))
            manifest=assets.finish(root,assets.settings(dict(style='pixel',pixel_grid=32,colors=16)),hashlib.sha256(DEMO.read_bytes()).hexdigest())
            palette=set()
            for view in assets.VIEWS:
                with Image.open(root/(view+'.native.png')) as image:
                    self.assertEqual(image.size,(32,32));self.assertEqual(set(image.getchannel('A').getdata()),{0,255});palette|={pixel[:3] for pixel in image.getdata() if pixel[3]}
                with Image.open(root/(view+'.png')) as image:self.assertEqual(image.size,(512,512))
            self.assertLessEqual(len(palette),16)
            with zipfile.ZipFile(root/'views.zip') as archive:
                self.assertIsNone(archive.testzip());self.assertEqual(set(archive.namelist()),set(manifest['files'])|{'asset-views.json'})
                for file,digest in manifest['files'].items():self.assertEqual(hashlib.sha256(archive.read(file)).hexdigest(),digest)


class AssetHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.key=self.root/'key';self.key.write_text('b'*32);self.key.chmod(0o600)
        self.cfg=dict(host='127.0.0.1',port=0,active_model='moss',runtime='/unused',models={'moss':{}},generation_timeout=10,api_key_file=str(self.key))
        self.backend=service.Backend(self.cfg);self.backend.stopping.set()
        self.data=patch.object(studio_service,'DATA',self.root/'archive');self.data.start()
        self.worker=patch.object(assets.AssetViews,'run',return_value=None);self.worker.start()
        self.blender=patch.object(assets,'blender_path',return_value='/trusted/blender');self.blender.start()
        self.server=service.BoundedServer(('127.0.0.1',0),service.make_handler(self.backend,self.key.read_bytes()))
        self.cfg['port']=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.blender.stop();self.worker.stop();self.data.stop();self.temp.cleanup()

    def call(self,path,body=None,authenticated=True):
        cfg=dict(self.cfg)
        if not authenticated:cfg.pop('api_key_file')
        return manage.request(cfg,'/studio/api/assets'+path,body=body,timeout=3)

    def test_authenticated_upload_options_errors_queue_and_cancellation(self):
        self.assertEqual(self.call('/options',authenticated=False)[0],401)
        self.assertEqual(len(self.call('/options')[1]['views']),7)
        self.assertEqual(self.call('',dict(data='not valid base64'))[0],400)
        self.assertEqual(self.call('',dict(data=base64.b64encode(repack(DEMO.read_bytes(),lambda d:d.update(asset=[]))).decode()))[0],400)
        body=dict(data=base64.b64encode(DEMO.read_bytes()).decode(),style='voxel')
        status,job=self.call('',body);self.assertEqual(status,202);self.assertEqual(job['status'],'queued')
        self.assertEqual(self.call('/'+job['id']+'/files/source.glb')[0],400)
        self.assertEqual(self.call('/'+'a'*32)[0],404)
        self.assertEqual(self.call('/'+job['id']+'/cancel',{})[1]['status'],'cancelled')
        self.assertEqual(self.call('/'+job['id'])[1]['status'],'cancelled')
        self.assertEqual(len(self.call('')[1]),1)

    def test_cli_upload_is_async_and_timeout_preserves_accepted_id(self):
        def cli(*args):
            out,err=io.StringIO(),io.StringIO()
            with patch.object(manage,'load_config',return_value=self.cfg),redirect_stdout(out),redirect_stderr(err):code=manage.main(['assets',*args])
            return code,json.loads(out.getvalue() or err.getvalue())
        code,job=cli('render','--input',str(DEMO),'--style','pixel','--front=+X','--async')
        self.assertEqual(code,0);self.assertEqual(job['front'],'+X')
        code,error=cli('wait',job['id'],'--timeout','0.01');self.assertEqual(code,4);self.assertEqual(error['error']['job_id'],job['id'])
        self.assertEqual(self.call('/'+job['id'])[1]['status'],'queued')


if __name__=='__main__':unittest.main()
