#!/usr/bin/env python3
"""Real GPU checks. Service must be stopped. Writes private studio receipts and comparison metadata."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PIL import Image, ImageDraw
from service import Backend, load_config, WORK
from studio_service import Studio
from catalog import MODELS

SCENES=[
 ('photo','A natural documentary photograph of a ceramic red teapot on a wooden table beside a window. Soft daylight, realistic material texture, neutral colors.'),
 ('portrait','A studio portrait photograph of an adult woman aged 35 with curly brown hair, wearing a green jacket. Soft key light, natural skin texture, neutral gray background.'),
 ('comic','Western comic book illustration of an adult detective walking down a rainy city street at night. Bold black ink contours, halftone shading, limited blue and orange palette.'),
 ('line','Clean line art illustration of a small hillside village, flat colors, clear silhouettes, minimal shading.'),
 ('anime','anime illustration, 1woman, adult, age 30, red coat, short brown hair, standing at a train station, sunset, clean lineart, cel shading'),
 ('background','Anime background art of a peaceful coastal town at dawn, painterly scenery, warm sunlight, atmospheric depth, no people'),
]

def main():
 os.umask(0o077)
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('models',nargs='*');p.add_argument('--matrix',action='store_true');p.add_argument('--matrix-only',action='store_true');p.add_argument('--size',default='768x768');args=p.parse_args()
 if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:raise SystemExit('Stop the service first.')
 cfg=load_config();cfg['generation_timeout']=900
 WORK.mkdir(parents=True,exist_ok=True);(WORK/'empty-model-catalog').mkdir(exist_ok=True)
 backend=Backend(cfg);studio=Studio(backend)
 receipt_path=studio.root/'verification.json'
 receipts=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
 report_path=studio.root/'gpu-report.json'
 report=json.loads(report_path.read_text()) if report_path.exists() else []
 stop=threading.Event();peak=[0]
 def monitor():
  while not stop.wait(1):
   try:peak[0]=max(peak[0],int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).splitlines()[0]))
   except (ValueError,subprocess.SubprocessError):pass
 threading.Thread(target=monitor,daemon=True).start()
 try:
  for model in args.models or list(cfg['models']):
   if model not in cfg['models']:continue
   backend.stop();backend.model=model;backend.failure=None;backend.start()
   if not backend.available():
    report.append(dict(model=model,error=backend.failure));print(model,backend.failure,flush=True);continue
   if not args.matrix_only:
    receipts[model]={'fingerprint':studio.fingerprint(model),'modes':[],'sizes':[]}
   elif 'text' not in studio.verified_modes(model):
    raise ValueError('Run verification before --matrix-only: '+model)
   def run(body,label):
    peak[0]=0;job=studio.submit(dict({'model':model,'seed':42},**body),verification=True);job['started']=time.time();studio.put('job',job)
    try:
     result=studio.generate(job);studio.save_result(job,result);job.update(status='completed',completed=time.time());studio.put('job',job)
     record=dict(model=model,label=label,id=job['id'],request=job['request'],seconds=round(time.time()-job['started'],2),peak_gpu_mib=peak[0]);report.append(record);print(json.dumps(record),flush=True);return job['id']
    except Exception as exc:
     job.update(status='failed',error=str(exc));studio.put('job',job);report.append(dict(model=model,label=label,error=str(exc)));print(model,label,exc,flush=True);return None
   smoke=None if args.matrix_only else run({'prompt':SCENES[0][1],'size':'512x512'},'smoke')
   if smoke:
    receipts[model]['modes'].append('text');receipts[model]['sizes'].append('512x512')
    for size in ['1024x1024','832x1216']:
     if run({'prompt':SCENES[4][1] if model.startswith('anima') else SCENES[0][1],'size':size},'resolution'):
      receipts[model]['sizes'].append(size)
    # Upload an existing output; all edit checks have known geometry.
    upload=studio.upload({'data':base64.b64encode(studio.file(smoke).read_bytes()).decode()})
    for mode in MODELS[model]['modes']:
     if mode=='text':continue
     body=dict(prompt='Change the red teapot to a blue teapot, keep the wooden table and composition.',size='512x512',mode=mode,image_id=upload['id'])
     if mode=='inpaint':
      mask=Image.new('RGB',(512,512),'black');ImageDraw.Draw(mask).rectangle((128,128,384,384),fill='white');out=io.BytesIO();mask.save(out,format='PNG');body['mask_id']=studio.upload({'data':base64.b64encode(out.getvalue()).decode()})['id']
     if run(body,mode):receipts[model]['modes'].append(mode)
   receipt_path.write_text(json.dumps(receipts,indent=2))
   if (args.matrix or args.matrix_only) and 'text' in receipts[model]['modes']:
    for category,prompt in SCENES:
     for seed in [42,1234,2026]:
      run(dict(prompt=prompt,size=args.size,seed=seed),category)
   (studio.root/'gpu-report.json').write_text(json.dumps(report,indent=2))
 finally:
  stop.set();backend.stop();(studio.root/'gpu-report.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
