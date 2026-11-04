#!/usr/bin/env python3
"""Verify recipe aspect-ratio dimensions on the installed GPU without adding gallery images."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from recipes import formats
from catalog import MODELS
from service import Backend,load_config,WORK
from studio_service import Studio,DATA

CACHE=Path.home()/'.cache/local-image-ai-service'

def recorded_sizes(roots,model,fingerprint):
    sizes=set()
    for root in roots:
        path=root/'history.sqlite3'
        if not path.is_file():continue
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            for row in db.execute("SELECT data FROM records WHERE kind='image'"):
                item=json.loads(row[0]);request=item.get('request',{})
                if item.get('fingerprint')!=fingerprint or request.get('model')!=model:continue
                file=root/(item['id']+'.png')
                if not file.is_file():continue
                with Image.open(file) as image:
                    image.load()
                    if image.format=='PNG' and image.size==tuple(map(int,request['size'].split('x'))):sizes.add(request['size'])
    return sizes

def store(path,receipts):
    temporary=path.with_name('verification.formats.tmp')
    with temporary.open('x') as stream:
        json.dump(receipts,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',choices=tuple(MODELS))
    parser.add_argument('--standard-only',action='store_true',help='Verify the seven final-output aspect-ratio sizes')
    args=parser.parse_args()
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop the service before verifying dimensions.')
    cfg=load_config();cfg['generation_timeout']=900
    backend=Backend(cfg);root=CACHE/'format-checks-20261031';studio=Studio(backend,root)
    path=DATA/'verification.json';receipts=json.loads(path.read_text()) if path.exists() else {}
    roots=[root,DATA,CACHE/'recipe-examples-20261031',CACHE/'moss-photography-20261031']
    WORK.mkdir(parents=True,exist_ok=True);(WORK/'empty-model-catalog').mkdir(exist_ok=True)
    try:
        for model in MODELS:
            if args.model and model!=args.model:continue
            if model not in cfg['models']:continue
            desired={f[key] for f in formats(model) for key in (('size',) if args.standard_only else ('size','preview_size'))}
            fingerprint=studio.fingerprint(model)
            receipt=receipts.get(model,{})
            if receipt.get('fingerprint')!=fingerprint:receipt=dict(fingerprint=fingerprint,modes=['text'],sizes=[])
            known=set(receipt.get('sizes',[]))|recorded_sizes(roots,model,fingerprint)
            receipt['sizes']=sorted(known);receipts[model]=receipt;store(path,receipts)
            pending=sorted(desired-known)
            if not pending:
                print(json.dumps(dict(model=model,status='already verified',sizes=sorted(desired))),flush=True);continue
            backend.stop();backend.model=model;backend.start()
            if not backend.available():raise RuntimeError(backend.failure)
            for size in pending:
                job=studio.submit(dict(model=model,prompt='A simple blue ceramic vase on a pale wooden table, soft studio light, one complete object.',size=size,steps=2,seed=42),verification=True)
                job['started']=time.time();studio.put('job',job)
                print(json.dumps(dict(event='started',model=model,size=size)),flush=True)
                try:
                    result=studio.generate(job);studio.save_result(job,result);job.update(status='completed',completed=time.time());studio.put('job',job)
                    known.add(size);receipt['sizes']=sorted(known);store(path,receipts)
                    print(json.dumps(dict(event='verified',model=model,size=size,seconds=round(time.time()-job['started'],2))),flush=True)
                except Exception as exc:
                    job.update(status='failed',error=str(exc));studio.put('job',job);raise
    finally:backend.stop()
    print('All requested standard aspect-ratio dimensions verified.' if args.standard_only else 'All standard and draft aspect-ratio dimensions verified.',flush=True)

if __name__=='__main__':main()
