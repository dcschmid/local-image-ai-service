#!/usr/bin/env python3
"""Build real, reproducible recipe examples without adding anything to the user's gallery."""
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
from recipes import recipes,compose
from catalog import MODELS
from service import Backend,load_config,WORK
from studio_service import Studio,DATA

ROOT=Path(__file__).resolve().parents[1]
CACHE=Path.home()/'.cache/local-image-ai-service'

def candidates(roots):
    items=[]
    for root in roots:
        path=root/'history.sqlite3'
        if not path.is_file():continue
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            for row in db.execute("SELECT data FROM records WHERE kind='image'"):
                item=json.loads(row[0]);item['_root']=root
                items.append(item)
    return items

def matches(item,recipe,*,fingerprint=None):
    # A matching recipe ID alone cannot prove that the current prompt, sampling
    # and adapter revision produced this image. Check all of them before export.
    if fingerprint is not None and item.get('fingerprint')!=fingerprint:return False
    request=item.get('request',{});inputs=request.get('recipe_inputs',{})
    if inputs.get('recipe')!=recipe['id']:return False
    for key in ('subject','scene','details','text','modeling_view','modeling_asset'):
        if inputs.get(key,'')!=recipe['example'].get(key,''):return False
    body=dict(model=recipe['model'],recipe=recipe['id'],**recipe['example'],quality=inputs.get('quality','standard'),seed=request.get('seed',42))
    expected=compose(body)
    return all(request.get(key)==value for key,value in expected.items())

def export(item,recipe,target):
    target.mkdir(parents=True,exist_ok=True)
    source=item['_root']/(item['id']+'.png')
    with Image.open(source) as image:
        image.load()
        alpha='A' in image.getbands() and sum(image.getchannel('A').histogram()[:250])>image.width*image.height*.01
        if recipe.get('transparent') and not alpha:raise ValueError('Transparent example has no alpha: '+recipe['id'])
        if all(low == high for low, high in image.convert('RGBA').getextrema()):
            raise ValueError('Generated example is a uniform frame: ' + recipe['id'])
        image.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        image.save(target/(recipe['id']+'.webp'),format='WEBP',quality=88,method=6)
    request=item['request']
    entry=dict(recipe=recipe['id'],model=recipe['model'],url='/studio/recipe-examples/'+recipe['id']+'.webp',
                inputs=dict(recipe=recipe['id'],**recipe['example']),quality=request['recipe_inputs'].get('quality','standard'),
                seed=request['seed'],size=request['size'],steps=request['steps'],cfg_scale=request['cfg_scale'],sampler=request['sampler'],
                prompt=request['prompt'],negative_prompt=request.get('negative_prompt',''),seconds=item.get('seconds'),
                runtime_revision=item.get('runtime_revision'),transparent=alpha)
    return entry

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='*')
    parser.add_argument('--reuse-only',action='store_true')
    parser.add_argument('--quality',choices=('preview','standard','detail'),help='Require this profile when reusing or generating examples')
    args=parser.parse_args();os.umask(0o077)
    # New generations belong to an isolated archive; the user's archive is read-only.
    root=CACHE/'recipe-examples-20261031'
    target=ROOT/'studio/public/recipe-examples'
    cfg=load_config();cfg['generation_timeout']=900
    backend=Backend(cfg);studio=Studio(backend,root)
    sources=[root,DATA,CACHE/'moss-photography-20261031']
    items=candidates(sources)
    manifest_path=target/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest={key:value for key,value in manifest.items() if key in {r['id'] for r in recipes()}}
    pending=[]
    for recipe in recipes():
        if args.only and recipe['id'] not in args.only:continue
        required_quality=args.quality or recipe.get('example_quality')
        eligible=[item for item in items if matches(item,recipe,fingerprint=studio.fingerprint(recipe['model'])) and (not required_quality or item['request']['recipe_inputs'].get('quality','standard')==required_quality) and (item['_root']/(item['id']+'.png')).is_file()]
        if eligible:
            item=max(eligible,key=lambda i:({'preview':0,'standard':2,'detail':1}.get(i['request']['recipe_inputs'].get('quality','standard'),0),i.get('created',0)))
            manifest[recipe['id']]=export(item,recipe,target)
            print(json.dumps(dict(event='reused',recipe=recipe['id'])),flush=True)
        else:pending.append(recipe)
    target.mkdir(parents=True,exist_ok=True)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    if pending and not args.reuse_only:
        if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop the service before GPU generation. Existing examples were exported.')
        WORK.mkdir(parents=True,exist_ok=True);(WORK/'empty-model-catalog').mkdir(exist_ok=True)
        try:
            for model in MODELS:
                selected=[r for r in pending if r['model']==model]
                if not selected:continue
                backend.stop();backend.model=model;backend.start()
                if not backend.available():raise RuntimeError(backend.failure)
                for recipe in selected:
                    quality=args.quality or recipe.get('example_quality','preview')
                    body=dict(model=model,recipe=recipe['id'],**recipe['example'],quality=quality,seed=42)
                    job=studio.submit(body,verification=True);job['started']=time.time();studio.put('job',job)
                    print(json.dumps(dict(event='started',recipe=recipe['id'],quality=quality,image_id=job['id'])),flush=True)
                    try:
                        result=studio.generate(job);studio.save_result(job,result)
                        job.update(status='completed',completed=time.time());studio.put('job',job)
                        item=studio.get(job['id'],'image');item['_root']=root
                        manifest[recipe['id']]=export(item,recipe,target)
                        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
                        print(json.dumps(dict(event='completed',recipe=recipe['id'],seconds=item['seconds'],image_id=job['id'])),flush=True)
                    except Exception as exc:
                        job.update(status='failed',error=str(exc));studio.put('job',job);raise
        finally:backend.stop()
    print('Examples available: '+str(len(manifest)),flush=True)

if __name__=='__main__':main()
