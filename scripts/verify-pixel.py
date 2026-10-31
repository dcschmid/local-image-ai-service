#!/usr/bin/env python3
"""Exercise pixel variant switching, PNG export, deletion and compatibility API in an isolated archive."""
import base64
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import service
from studio_service import Studio


def main():
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop service before GPU validation.')
    root=Path.home()/'.cache/local-image-ai-service/krea-http-checks-20261031';root.mkdir(parents=True,exist_ok=True)
    cfg=service.load_config();cfg['active_model']='krea-pixel'
    backend=service.Backend(cfg)
    config=root/'config.json';config.write_text(json.dumps(cfg))
    with patch('studio_service.DATA',root),patch('service.CONFIG',config):
        server=service.BoundedServer(('127.0.0.1',0),service.make_handler(backend,None))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(method,path,body=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=180)
            try:
                conn.request(method,path,None if body is None else json.dumps(body),{'Content-Type':'application/json'})
                response=conn.getresponse();raw=response.read()
                if response.status not in (200,202):raise RuntimeError((response.status,raw[:300]))
                return raw
            finally:conn.close()
        try:
            backend.start()
            if not backend.available():raise RuntimeError(backend.failure)
            assert backend.pixel_grid==64
            job=json.loads(call('POST','/studio/api/jobs',dict(recipe='pixel-loot',subject='a red mushroom',seed=42)))
            deadline=time.monotonic()+180
            while True:
                jobs=json.loads(call('GET','/studio/api/jobs'));current=next(j for j in jobs if j['id']==job['id'])
                if current['status']=='completed':break
                if current['status'] in ('failed','cancelled') or time.monotonic()>deadline:raise RuntimeError(current)
                time.sleep(.5)
            assert backend.pixel_grid==32
            gallery=json.loads(call('GET','/studio/api/gallery'));item=next(i for i in gallery if i['id']==job['id'])
            route='/studio/api/files/'+job['id']
            large=call('GET',route);small=call('GET',route+'/pixels')
            with Image.open(io.BytesIO(large)) as image:
                assert image.format=='PNG' and image.size==(1024,1024)
                assert len(image.getcolors(128))<=24
            with Image.open(io.BytesIO(small)) as image:assert image.format=='PNG' and image.size==(32,32)
            assert item['pixel']['weights']=='dora-v1'
            (root/'queued-result.png').write_bytes(large);(root/'queued-native.png').write_bytes(small)
            result=json.loads(call('POST','/v1/images/generations',dict(model='krea-pixel',prompt='pixel art, a blue potion bottle on a white background',size='512x512',steps=2,seed=42)))
            raw=base64.b64decode(result['data'][0]['b64_json'])
            with Image.open(io.BytesIO(raw)) as image:
                assert image.format=='PNG' and image.size==(512,512)
                assert json.loads(image.info['AtelierPixel'])['grid']==32
            (root/'compatibility.png').write_bytes(raw)
            call('POST','/studio/api/gallery/delete',{'ids':[job['id']]})
            studio=Studio(backend,root)
            assert not studio.file(job['id']).exists() and not studio.pixel_file(job['id']).exists()
            assert studio.listing('image')==[]
            report=dict(status='passed',initial_grid=64,queued_grid=32,canvas='1024x1024',native='32x32',colors=24,
                        compatibility='512x512 PNG; current 32 variant',deleted_both_files=True,seconds=item['seconds'])
            (root/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
        finally:
            backend.stopping.set();backend.stop();server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
