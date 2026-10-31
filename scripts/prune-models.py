#!/usr/bin/env python3
"""Keep curated profiles; delete only unreferenced service-owned weights."""
import json
import os
from pathlib import Path
import subprocess

KEEP={'anima','moss','qwen21','krea-pixel','anima-psx','anima-lowpoly'}

def main():
    os.umask(0o077)
    if subprocess.run(['systemctl','--user','is-active','--quiet','local-image-ai.service']).returncode==0:
        raise SystemExit('Stop the service before pruning models.')
    config=Path.home()/'.config/local-image-ai-service/config.json'
    cfg=json.loads(config.read_text())
    kept={name:files for name,files in cfg['models'].items() if name in KEEP}
    if not kept:raise SystemExit('No retained models configured; refusing to prune.')
    # Profiles share files, so retaining any profile protects all of its resolved paths.
    protected={Path(p).resolve() for files in kept.values() for p in files.values()}
    owned=(Path.home()/'.local/share/local-image-ai-service/models').resolve()
    candidates={Path(p) for name,files in cfg['models'].items() if name not in KEEP for p in files.values()}
    cfg['models']=kept
    if cfg['active_model'] not in kept:cfg['active_model']='anima' if 'anima' in kept else 'moss'
    temporary=config.with_suffix('.prune.tmp')
    with temporary.open('x') as stream:
        json.dump(cfg,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    temporary.replace(config)
    deleted=[];external=[]
    for path in sorted(candidates):
        actual=path.resolve()
        if actual in protected:continue
        if actual.is_relative_to(owned) and path.is_file() and not path.is_symlink():
            size=path.stat().st_size;path.unlink();deleted.append({'file':str(path),'bytes':size})
        elif path.exists():external.append(str(path))
    print(json.dumps({'deleted':deleted,'freed_bytes':sum(f['bytes'] for f in deleted),'external_weights_untouched':external},indent=2))

if __name__=='__main__':main()
