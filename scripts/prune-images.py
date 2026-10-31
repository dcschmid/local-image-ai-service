#!/usr/bin/env python3
"""Keep the current recipe generation and newer images, pruning only the studio archive."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from catalog import MODELS
from recipes import VERSION
from service import Backend, load_config
from studio_service import Studio

def main():
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:
        raise SystemExit('Stop the service before pruning images.')
    studio=Studio(Backend(load_config()))
    images=studio.listing('image',1000000)
    current=[i for i in images if i['request'].get('recipe_version')==VERSION and i['request'].get('model') in MODELS]
    if not current:raise SystemExit('No current recipe images found; refusing to choose a deletion cutoff.')
    cutoff=min(i['created'] for i in current)
    removed=[]
    for image in images:
        if image['request'].get('model') not in MODELS or image['created']<cutoff:
            studio.delete_image(image['id']);removed.append(image['id'])
    with studio.db() as db:
        stale_jobs=db.execute("DELETE FROM records WHERE kind='job' AND id NOT IN (SELECT id FROM records WHERE kind='image') AND json_extract(data,'$.status') IN ('completed','failed','cancelled')").rowcount
        records=[json.loads(row[0]) for row in db.execute("SELECT data FROM records WHERE kind IN ('job','image')")]
    referenced={item['request'][key] for item in records for key in ('image_id','mask_id') if key in item.get('request',{})}
    unused_uploads=[]
    for upload in studio.listing('upload',1000000):
        if upload['id'] in referenced:continue
        identifier=upload['id'];studio.file(identifier)
        with studio.db() as db:
            db.execute("DELETE FROM records WHERE id=? AND kind='upload'",(identifier,))
            db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',(identifier,'deleting',json.dumps({'id':identifier})))
        studio.finish_deletion(identifier);unused_uploads.append(identifier)
    print(json.dumps(dict(kept=len(images)-len(removed),deleted_images=len(removed),deleted_unused_uploads=len(unused_uploads),deleted_stale_jobs=stale_jobs,cutoff=cutoff),indent=2))

if __name__=='__main__':main()
