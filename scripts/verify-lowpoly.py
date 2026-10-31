#!/usr/bin/env python3
"""Verify both Anima style choices through an isolated HTTP service and archive."""
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
from catalog import MODELS


def main():
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop the service before GPU validation.')
    root=Path.home()/'.cache/local-image-ai-service/anima-lowpoly-http-20261031';root.mkdir(parents=True,exist_ok=True)
    cfg=service.load_config();cfg['active_model']='anima';backend=service.Backend(cfg)
    config=root/'config.json';config.write_text(json.dumps(cfg));report=[]
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
            for model,trigger in [('anima-psx','lowpoly, ps1, psx, 3d'),('anima-lowpoly','l0wp0ly, 3d')]:
                job=json.loads(call('POST','/studio/api/jobs',dict(model=model,prompt=trigger+', a simple wooden cabin',size='512x512',steps=2,seed=42)))
                deadline=time.monotonic()+180
                while True:
                    jobs=json.loads(call('GET','/studio/api/jobs'));current=next(j for j in jobs if j['id']==job['id'])
                    if current['status']=='completed':break
                    if current['status'] in ('failed','cancelled') or time.monotonic()>deadline:raise RuntimeError(current)
                    time.sleep(.3)
                assert backend.model==model
                gallery=json.loads(call('GET','/studio/api/gallery'));item=next(i for i in gallery if i['id']==job['id'])
                raw=call('GET','/studio/api/files/'+job['id'])
                with Image.open(io.BytesIO(raw)) as image:assert image.format=='PNG' and image.size==(512,512)
                assert item['sampling']['lora_strength']==MODELS[model]['lora_strength']
                if model=='anima-lowpoly':assert item['sampling']['adapter_revision']=='qwen-names-v1'
                (root/(model+'-queued.png')).write_bytes(raw)
                call('POST','/studio/api/gallery/delete',{'ids':[job['id']]})
                assert not (root/(job['id']+'.png')).exists()
                report.append(dict(model=model,status='passed',seconds=item['seconds'],lora_strength=item['sampling']['lora_strength']))
            result=json.loads(call('POST','/v1/images/generations',dict(model='anima-lowpoly',prompt='l0wp0ly, 3d, a cabin',size='512x512',steps=2,seed=42)))
            raw=base64.b64decode(result['data'][0]['b64_json'])
            with Image.open(io.BytesIO(raw)) as image:assert image.format=='PNG' and image.size==(512,512)
            (root/'compatibility.png').write_bytes(raw)
            assert Studio(backend,root).listing('image')==[]
            result=dict(status='passed',queued_variants=report,compatibility='512x512 PNG',archive_empty=True)
            (root/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
        finally:
            backend.stopping.set();backend.stop();server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
