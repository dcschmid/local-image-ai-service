#!/usr/bin/env python3
"""Verify img2img and inpaint editing on the installed GPU and record receipts.

Each model runs one img2img job and one inpaint job from a small checker
reference image. A completed, dimension-correct PNG is required before the
mode joins the local verification receipt that unlocks it in the Studio.
"""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from catalog import MODELS
from service import Backend,load_config,WORK
from studio_service import Studio,DATA

CACHE=Path.home()/'.cache/local-image-ai-service'

def checker_reference():
    stream=io.BytesIO()
    image=Image.new('RGB',(512,512),(224,228,232))
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((128,128,384,384),radius=48,fill=(52,96,150))
    draw.ellipse((216,216,296,296),fill=(232,180,90))
    image.save(stream,format='PNG')
    return stream.getvalue()

def checker_mask():
    stream=io.BytesIO()
    mask=Image.new('L',(512,512),0)
    ImageDraw.Draw(mask).rounded_rectangle((160,160,352,352),radius=40,fill=255)
    mask.save(stream,format='PNG')
    return stream.getvalue()

def recorded_modes(roots,model,fingerprint):
    modes=set()
    for root in roots:
        path=root/'history.sqlite3'
        if not path.is_file():continue
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            for row in db.execute("SELECT data FROM records WHERE kind='image'"):
                item=json.loads(row[0]);request=item.get('request',{})
                if item.get('fingerprint')!=fingerprint or request.get('model')!=model:continue
                if request.get('mode') not in ('img2img','inpaint'):continue
                file=root/(item['id']+'.png')
                if not file.is_file():continue
                with Image.open(file) as image:
                    image.load()
                    if image.format=='PNG' and image.size==tuple(map(int,request['size'].split('x'))):
                        modes.add(request['mode'])
    return modes

def store(path,receipts):
    temporary=path.with_name('verification.modes.tmp')
    with temporary.open('w') as stream:
        json.dump(receipts,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',choices=tuple(MODELS),help='Verify one model only (default: every configured model)')
    args=parser.parse_args()
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop the service before verifying editing modes.')
    cfg=load_config();cfg['generation_timeout']=900
    backend=Backend(cfg);root=CACHE/'mode-checks-20261111';studio=Studio(backend,root)
    path=DATA/'verification.json';receipts=json.loads(path.read_text()) if path.exists() else {}
    roots=[root,DATA,CACHE/'mode-checks-20261111']
    WORK.mkdir(parents=True,exist_ok=True);(WORK/'empty-model-catalog').mkdir(exist_ok=True)
    reference=studio.upload({'data':base64.b64encode(checker_reference()).decode()})
    mask=studio.upload({'data':base64.b64encode(checker_mask()).decode()})
    try:
        for model in MODELS:
            if args.model and model!=args.model:continue
            if model not in cfg['models']:continue
            fingerprint=studio.fingerprint(model)
            receipt=receipts.get(model,{})
            if receipt.get('fingerprint')!=fingerprint:receipt=dict(fingerprint=fingerprint,modes=['text'],sizes=receipt.get('sizes',[]))
            known=set(receipt.get('modes',[]))|recorded_modes(roots,model,fingerprint)
            receipt['modes']=sorted(known);receipts[model]=receipt;store(path,receipts)
            pending=[mode for mode in ('img2img','inpaint') if mode not in known]
            if not pending:
                print(json.dumps(dict(model=model,status='already verified',modes=sorted(known))),flush=True);continue
            backend.stop();backend.model=model;backend.start()
            if not backend.available():raise RuntimeError(backend.failure)
            for mode in pending:
                body=dict(model=model,mode=mode,prompt='The same central object on the same plain background, softly relit.',
                          size='512x512',steps=6,seed=42,strength=.75,image_id=reference['id'])
                if mode=='inpaint': body.update(mask_id=mask['id'],feather=4)
                job=studio.submit(body,verification=True)
                job['started']=time.time();studio.put('job',job)
                print(json.dumps(dict(event='started',model=model,mode=mode)),flush=True)
                try:
                    result=studio.generate(job);studio.save_result(job,result);job.update(status='completed',completed=time.time());studio.put('job',job)
                    known.add(mode);receipt['modes']=sorted(known);store(path,receipts)
                    print(json.dumps(dict(event='verified',model=model,mode=mode,seconds=round(time.time()-job['started'],2))),flush=True)
                except Exception as exc:
                    job.update(status='failed',error=str(exc));studio.put('job',job);raise
    finally:backend.stop()
    print('Requested editing modes verified and recorded.',flush=True)

if __name__=='__main__':main()
