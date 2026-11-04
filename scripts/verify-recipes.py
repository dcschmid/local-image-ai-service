#!/usr/bin/env python3
"""GPU smoke checks for every guided recipe plus full-size landscape validation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from recipes import recipes, VERSION
from catalog import MODELS
from service import Backend, load_config, WORK
from studio_service import Studio

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--only",nargs="*");parser.add_argument("--no-full",action="store_true");args=parser.parse_args()
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop the service first.')
    cfg=load_config();cfg['generation_timeout']=900
    WORK.mkdir(parents=True,exist_ok=True);(WORK/'empty-model-catalog').mkdir(exist_ok=True)
    backend=Backend(cfg);studio=Studio(backend)
    path=studio.root/'verification.json';receipts=json.loads(path.read_text()) if path.exists() else {}
    report_path=studio.root/'recipe-report.json'
    prior=json.loads(report_path.read_text()) if report_path.exists() else []
    report=[r for r in prior if r.get('request',{}).get('recipe_version')==VERSION]
    completed={(r['recipe'],r['quality']) for r in report}
    try:
        for model in MODELS:
            if args.only and not any(r['model']==model and r['id'] in args.only for r in recipes()):continue
            backend.stop();backend.model=model;backend.start()
            if not backend.available():raise RuntimeError(backend.failure)
            items=[(r,'preview') for r in recipes() if r['model']==model and (not args.only or r['id'] in args.only)]
            if not args.no_full:
                items.append((next(r for r in recipes() if r['model']==model),'standard'))
            for recipe,quality in items:
                if (recipe['id'],quality) in completed:continue
                body=dict(model=model,recipe=recipe['id'],quality=quality,seed=42,**recipe['example'])
                # One real German-input test; input remains unchanged in the prompt.
                if recipe['id']=='anima-cozy':body['subject']='eine erwachsene Buchhändlerin mit runder Brille und einer grünen Strickjacke'
                job=studio.submit(body,verification=True);job['started']=time.time();studio.put('job',job)
                try:
                    result=studio.generate(job);studio.save_result(job,result);job.update(status='completed',completed=time.time());studio.put('job',job)
                    receipt=receipts.setdefault(model,{'fingerprint':studio.fingerprint(model),'modes':['text'],'sizes':[]})
                    if job['request']['size'] not in receipt['sizes']:receipt['sizes'].append(job['request']['size'])
                    path.write_text(json.dumps(receipts,indent=2))
                    record=dict(recipe=recipe['id'],quality=quality,image_id=job['id'],seconds=round(time.time()-job['started'],2),request=job['request'])
                    report.append(record);print(json.dumps(record),flush=True)
                except Exception as exc:
                    job.update(status='failed',error=str(exc));studio.put('job',job);raise
                (studio.root/'recipe-report.json').write_text(json.dumps(report,indent=2))
    finally:backend.stop()

if __name__=='__main__':main()
