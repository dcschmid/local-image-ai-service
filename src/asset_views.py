"""Private GLB imports and deterministic views from one shared static model."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import struct
import subprocess
import threading
import time
import uuid
import warnings
import zipfile

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

MAX_GLB = 32 * 1024 * 1024
MAX_BODY = 45 * 1024 * 1024
VIEWS = {'front':'Front', 'left':'Left', 'right':'Right', 'back':'Back',
         'top':'Top', 'bottom':'Bottom', 'three-quarter':'Three-quarter'}
STYLES = {'model':'Original materials', 'lowpoly':'Flat shading',
          'pixel':'Pixel Art', 'voxel':'Voxel Art'}
FRONTS = ('-Y', '+Y', '-X', '+X')


def blender_path():
    candidate = shutil.which('blender') or str(Path.home()/'.local/bin/blender')
    return candidate if Path(candidate).is_file() and os.access(candidate, os.X_OK) else None


def validate_glb(raw):
    """Accept self-contained glTF 2 only; no external URIs, scripts or archives."""
    if not 20 <= len(raw) <= MAX_GLB or raw[:4] != b'glTF':
        raise ValueError('Choose a binary GLB file, at most 32 MiB.')
    version, length = struct.unpack_from('<II', raw, 4)
    if version != 2 or length != len(raw):
        raise ValueError('The GLB header is invalid; export glTF 2.0 Binary from Blender.')
    offset=12;chunks=[]
    while offset < len(raw):
        if offset+8 > len(raw):raise ValueError('Invalid GLB chunk.')
        size,kind=struct.unpack_from('<II',raw,offset);offset+=8
        if size%4 or offset+size > len(raw):raise ValueError('Invalid GLB chunk length.')
        chunks.append((kind,raw[offset:offset+size]));offset+=size
    if len(chunks)!=2 or [c[0] for c in chunks]!=[0x4E4F534A,0x004E4942]:
        raise ValueError('Use one JSON chunk and one embedded binary buffer.')
    try:document=json.loads(chunks[0][1].decode('utf-8').rstrip(' \0'))
    except (ValueError,UnicodeError,RecursionError):raise ValueError('Invalid GLB JSON.') from None
    if not isinstance(document,dict) or not isinstance(document.get('asset'),dict) or document['asset'].get('version')!='2.0':
        raise ValueError('Only glTF 2.0 assets are supported.')
    def walk(value,depth=0):
        if depth>48:raise ValueError('GLB nesting is too deep.')
        if isinstance(value,dict):
            if 'uri' in value:raise ValueError('External and data URIs are not supported; embed all data in the GLB buffer.')
            for item in value.values():walk(item,depth+1)
        elif isinstance(value,list):
            for item in value:walk(item,depth+1)
        elif isinstance(value,float) and not math.isfinite(value):raise ValueError('GLB numbers must be finite.')
    walk(document)
    def objects(owner,key,limit):
        value=owner.get(key,[])
        if not isinstance(value,list) or len(value)>limit or any(not isinstance(item,dict) for item in value):
            raise ValueError('Invalid or excessive GLB '+key+'.')
        return value
    for key,limit in [('buffers',1),('bufferViews',16384),('nodes',4096),('accessors',8192),('meshes',1024),('images',128),('materials',1024),('scenes',32),('skins',256),('animations',256)]:
        objects(document,key,limit)
    buffers=document.get('buffers',[])
    if len(buffers)!=1 or type(buffers[0].get('byteLength')) is not int or not 0 < buffers[0]['byteLength'] <= len(chunks[1][1]):
        raise ValueError('GLB must contain one valid embedded buffer.')
    views=document.get('bufferViews',[])
    for view in views:
        start,size=view.get('byteOffset',0),view.get('byteLength')
        if view.get('buffer',0)!=0 or type(start) is not int or type(size) is not int or start<0 or size<0 or start+size>buffers[0]['byteLength']:
            raise ValueError('GLB buffer view is out of bounds.')
    nodes=document.get('nodes',[])
    if not isinstance(nodes,list) or len(nodes)>4096:raise ValueError('The asset contains too many nodes.')
    def visit(index,ancestors):
        if type(index) is not int or not 0 <= index < len(nodes) or index in ancestors or len(ancestors)>64:
            raise ValueError('Invalid or cyclic GLB node hierarchy.')
        for child in nodes[index].get('children',[]):visit(child,ancestors|{index})
    # Every node may have at most one parent; this also bounds traversal work.
    for node in nodes:
        if not isinstance(node.get('children',[]),list) or any(type(child) is not int for child in node.get('children',[])):
            raise ValueError('Invalid GLB children.')
    children=[child for node in nodes for child in node.get('children',[])]
    if len(children)!=len(set(children)):raise ValueError('GLB nodes must have a single parent.')
    for index in range(len(nodes)):visit(index,set())
    accessors=document.get('accessors',[])
    if len(accessors)>8192:raise ValueError('The asset contains too many accessors.')
    elements=0
    for accessor in accessors:
        count=accessor.get('count')
        if type(count) is not int or not 0 <= count <= 3_000_000:raise ValueError('GLB accessor exceeds the geometry limit.')
        kind=accessor.get('type');component=accessor.get('componentType')
        if not isinstance(kind,str) or kind not in ('SCALAR','VEC2','VEC3','VEC4','MAT2','MAT3','MAT4') or type(component) is not int or component not in (5120,5121,5122,5123,5125,5126):
            raise ValueError('Invalid GLB accessor type.')
        width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT2':4,'MAT3':9,'MAT4':16}[kind]
        elements+=count*width
        if elements>32_000_000:raise ValueError('The asset contains too much decoded accessor data.')
        if 'bufferView' in accessor:
            index=accessor['bufferView'];offset=accessor.get('byteOffset',0)
            if type(index) is not int or not 0<=index<len(views) or type(offset) is not int or offset<0:raise ValueError('Invalid GLB accessor buffer.')
            size={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}[component]*width
            if kind.startswith('MAT'):
                side=int(kind[-1]);column=side*{5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}[component];size=side*((column+3)//4*4)
            stride=views[index].get('byteStride',size)
            if type(stride) is not int or stride<size or offset+max(0,count-1)*stride+(size if count else 0)>views[index]['byteLength']:
                raise ValueError('GLB accessor data is out of bounds.')
    meshes=document.get('meshes',[])
    primitives=[primitive for mesh in meshes for primitive in objects(mesh,'primitives',1024)]
    if not primitives or len(primitives)>1024:raise ValueError('Choose a mesh asset with at most 1024 primitives.')
    vertices=0
    for primitive in primitives:
        if not isinstance(primitive.get('attributes'),dict):raise ValueError('Invalid GLB attributes.')
        index=primitive.get('attributes',{}).get('POSITION')
        if type(index) is not int or not 0 <= index < len(accessors):raise ValueError('A mesh is missing valid positions.')
        vertices+=accessors[index]['count']
    if vertices>1_000_000:raise ValueError('Choose an asset with at most one million declared vertices.')
    instantiated=0
    for node in nodes:
        if 'mesh' in node:
            index=node['mesh']
            if type(index) is not int or not 0<=index<len(meshes):raise ValueError('Invalid GLB mesh instance.')
            instantiated+=sum(accessors[p['attributes']['POSITION']]['count'] for p in meshes[index]['primitives'])
    if not instantiated or instantiated>1_000_000:raise ValueError('Choose an asset with 1–1,000,000 vertices including instances.')
    for scene in document.get('scenes',[]):
        roots=scene.get('nodes',[])
        if not isinstance(roots,list) or any(type(index) is not int or not 0<=index<len(nodes) or index in children for index in roots) or len(roots)!=len(set(roots)):
            raise ValueError('Invalid GLB scene roots.')
    total_pixels=0
    for image in document.get('images',[]):
        index=image.get('bufferView')
        if type(index) is not int or not 0 <= index < len(views) or image.get('mimeType') not in ('image/png','image/jpeg'):
            raise ValueError('Use embedded PNG or JPEG textures; KTX/Draco extensions are not supported here.')
        view=views[index];start=view.get('byteOffset',0)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(chunks[1][1][start:start+view['byteLength']])) as texture:
                    if texture.format not in ('PNG','JPEG') or max(texture.size)>4096:raise ValueError()
                    total_pixels+=texture.width*texture.height
        except (OSError,ValueError,Image.DecompressionBombWarning,Image.DecompressionBombError):
            raise ValueError('A texture is invalid or larger than 4096×4096 pixels.') from None
    if total_pixels>64_000_000:raise ValueError('The asset has more than 64 million texture pixels.')
    extensions=document.get('extensionsRequired',[])
    if not isinstance(extensions,list) or len(extensions)>64 or any(not isinstance(value,str) for value in extensions):raise ValueError('Invalid GLB extension list.')
    if any(extension in extensions for extension in ('KHR_draco_mesh_compression','EXT_meshopt_compression')):
        raise ValueError('Export an uncompressed GLB; Draco/meshopt compression is not supported here.')
    return {'vertices':vertices,'instantiated_vertices':instantiated,'primitives':len(primitives),'texture_pixels':total_pixels}


def settings(body):
    allowed={'data','name','style','front','pixel_grid','colors','voxel_grid'}
    if not isinstance(body,dict) or set(body)-allowed:raise ValueError('Unknown asset import settings.')
    result={key:body.get(key,default) for key,default in dict(style='model',front='-Y',pixel_grid=128,colors=32,voxel_grid=24).items()}
    if not isinstance(result['style'],str) or result['style'] not in STYLES:raise ValueError('Choose an asset rendering style.')
    if not isinstance(result['front'],str) or result['front'] not in FRONTS:raise ValueError('Choose the model’s front axis in Blender coordinates.')
    for key,choices in [('pixel_grid',(32,64,128)),('colors',(16,24,32,64,128)),('voxel_grid',(16,24,32,48,64))]:
        if type(result[key]) is not int or result[key] not in choices:raise ValueError('Choose a supported '+key.replace('_',' ')+'.')
    name=body.get('name','Imported asset')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80 or any(ord(c)<32 for c in name):raise ValueError('Asset name must contain 1–80 printable characters.')
    result['name']=name.strip()
    return result


def pixel_frames(directory,colors):
    """One palette and binary alpha across every direction; no per-view palette drift."""
    frames=[]
    for view in VIEWS:
        with Image.open(directory/(view+'.png')) as source:frames.append(source.convert('RGBA'))
    # Invisible colors do not influence the shared palette.
    opaque=[pixel[:3] for frame in frames for pixel in frame.getdata() if pixel[3]>=128]
    if not opaque:raise ValueError('The rendered asset is empty.')
    palette_source=Image.new('RGB',(len(opaque),1));palette_source.putdata(opaque)
    palette=palette_source.quantize(colors=colors,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    for view,frame in zip(VIEWS,frames):
        alpha=frame.getchannel('A').point(lambda value:255 if value>=128 else 0)
        rgb=frame.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE).convert('RGBA');rgb.putalpha(alpha)
        info=PngImagePlugin.PngInfo();info.add_text('AtelierAssetView',json.dumps({'view':view,'shared_palette':True,'colors':colors,'source':'one shared 3D model'}))
        rgb.save(directory/(view+'.native.png'),pnginfo=info)
        rgb.resize((512,512),Image.Resampling.NEAREST).save(directory/(view+'.png'),pnginfo=info)


def finish(directory,options,source_hash):
    if sum(path.stat().st_size for path in directory.iterdir() if path.is_file())>100*1024*1024:
        raise ValueError('The rendered asset exceeds 100 MiB; simplify its geometry or lower the voxel resolution.')
    manifest=json.loads((directory/'asset-views.json').read_text())
    if options['style']=='pixel':pixel_frames(directory,options['colors'])
    try:font=ImageFont.truetype('DejaVuSans.ttf',19);small=ImageFont.truetype('DejaVuSans.ttf',14)
    except OSError:font=ImageFont.load_default(size=19);small=ImageFont.load_default(size=14)
    sheet=Image.new('RGB',(1536,930),'#f5f4f0');draw=ImageDraw.Draw(sheet)
    draw.text((20,14),options['name']+' · '+STYLES[options['style']],fill='#20242b',font=font)
    draw.text((20,44),'One shared model · orthographic cameras · front '+options['front']+' · source geometry requires review',fill='#505761',font=small)
    empty=[]
    for index,(view,label) in enumerate(VIEWS.items()):
        x=(index%4)*384;y=84+(index//4)*390
        draw.text((x+12,y),label,fill='#20242b',font=font)
        with Image.open(directory/(view+'.png')) as image:
            image.load()
            if image.size!=(512,512):raise ValueError('A rendered view has incorrect dimensions.')
            if image.convert('RGBA').getchannel('A').getbbox() is None:empty.append(view)
            image=image.convert('RGBA').resize((350,350),Image.Resampling.NEAREST if options['style']=='pixel' else Image.Resampling.LANCZOS)
            sheet.paste(image,(x+7,y+30),image)
    if len(empty)==len(VIEWS):raise ValueError('The rendered asset is empty.')
    manifest['empty_projections']=empty
    if empty:manifest.setdefault('warnings',[]).append('Empty projections (possibly edge-on flat geometry): '+', '.join(empty))
    draw.text((20,885),'The views describe model.glb. Voxel conversion and pixel export approximate the source at the chosen resolution.',fill='#505761',font=small)
    sheet.save(directory/'sheet.png')
    manifest.update(source_sha256=source_hash,rendered_model_sha256=hashlib.sha256((directory/'model.glb').read_bytes()).hexdigest(),
                    style=options['style'],front=options['front'],pixel_grid=options['pixel_grid'] if options['style']=='pixel' else None,
                    colors=options['colors'],consistency='All cameras render the same static model.glb; source correctness is not certified.')
    manifest['files']={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ['model.glb','sheet.png',*[v+'.png' for v in VIEWS],*([v+'.native.png' for v in VIEWS] if options['style']=='pixel' else [])]}
    (directory/'asset-views.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(directory/'views.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in [*manifest['files'],'asset-views.json']:archive.write(directory/name,name)
    return manifest


class AssetViews:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=threading.RLock();self.pending=queue.Queue(maxsize=3);self.processes={}
        for path in self.root.glob('*/job.json'):
            try:
                job=json.loads(path.read_text())
                if job['status'] in ('queued','rendering'):
                    job.update(status='failed',error='The service stopped; this render was not restarted.');self.put(job)
            except (OSError,ValueError,KeyError):pass
        threading.Thread(target=self.run,name='asset-views',daemon=True).start()

    def options(self):
        return dict(available=bool(blender_path()),styles=[dict(id=k,name=v) for k,v in STYLES.items()],
                    views=[dict(id=k,name=v) for k,v in VIEWS.items()],fronts=list(FRONTS),max_bytes=MAX_GLB)

    def folder(self,identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid asset ID.')
        return self.root/identifier

    def put(self,job):
        path=self.folder(job['id'])/'job.json';temporary=path.with_suffix('.tmp')
        with self.lock:
            temporary.write_text(json.dumps(job,indent=2)+'\n');temporary.replace(path)
        return job

    def get(self,identifier):
        with self.lock:job=json.loads((self.folder(identifier)/'job.json').read_text())
        if job['status']=='completed':
            prefix='/studio/api/assets/'+identifier+'/files/'
            job['sheet']=prefix+'sheet.png';job['bundle']=prefix+'views.zip';job['manifest']=prefix+'asset-views.json';job['model']=prefix+'model.glb'
            job['views']=[dict(id=view,name=label,url=prefix+view+'.png',native_url=prefix+view+'.native.png' if job['style']=='pixel' else None) for view,label in VIEWS.items()]
        return job

    def listing(self):
        jobs=[]
        for path in self.root.glob('*/job.json'):
            try:jobs.append(self.get(path.parent.name))
            except (OSError,ValueError,KeyError):pass
        return sorted(jobs,key=lambda job:job['created'],reverse=True)[:20]

    def submit(self,body):
        options=settings(body)
        if not blender_path():raise ValueError('Blender is required for model views; install it locally before importing.')
        value=body.get('data')
        if not isinstance(value,str) or len(value)>MAX_GLB*4//3+4:raise ValueError('Choose a GLB file of at most 32 MiB.')
        try:raw=base64.b64decode(value,validate=True)
        except ValueError:raise ValueError('Invalid GLB upload encoding.') from None
        summary=validate_glb(raw)
        with self.lock:
            if self.pending.full():raise ValueError('The asset render queue is full; wait for an existing render.')
            identifier=uuid.uuid4().hex;folder=self.folder(identifier);folder.mkdir(mode=0o700)
            descriptor=os.open(folder/'source.glb',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(raw)
            job=dict(id=identifier,status='queued',created=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),summary=summary,progress=0,**options)
            self.put(job);self.pending.put(identifier)
        return job

    def cancel(self,identifier):
        with self.lock:
            job=self.get(identifier)
            if job['status'] in ('queued','rendering'):
                job.update(status='cancelled');self.put(job)
                process=self.processes.get(identifier)
                if process and process.poll() is None:
                    try:os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
            return job

    def file(self,identifier,name):
        job=self.get(identifier)
        allowed={'sheet.png','views.zip','asset-views.json','model.glb',*[v+'.png' for v in VIEWS]}
        if job['style']=='pixel':allowed|={v+'.native.png' for v in VIEWS}
        if job['status']!='completed' or name not in allowed:raise ValueError('This asset output is not available.')
        return self.folder(identifier)/'output'/name

    def run(self):
        while True:
            identifier=self.pending.get();process=None
            try:
                with self.lock:
                    job=self.get(identifier)
                    if job['status']=='cancelled':continue
                    job.update(status='rendering',started=time.time());self.put(job)
                folder=self.folder(identifier);output=folder/'output';output.mkdir()
                (folder/'settings.json').write_text(json.dumps({k:job[k] for k in ('style','front','pixel_grid','colors','voxel_grid')}))
                command=[blender_path(),'--background','--factory-startup','--disable-autoexec','--offline-mode','--threads','4','--python-exit-code','1',
                         '--python',str(Path(__file__).with_name('render_asset.py')),'--',str(folder/'source.glb'),str(folder/'settings.json'),str(output)]
                with (folder/'render.log').open('wb') as log:
                    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                                             env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',
                                                      XDG_CACHE_HOME=str(folder/'cache'),BLENDER_USER_CONFIG=str(folder/'config')))
                    with self.lock:self.processes[identifier]=process
                    deadline=time.monotonic()+300
                    while process.poll() is None:
                        if time.monotonic()>deadline:
                            os.killpg(process.pid,signal.SIGTERM);raise ValueError('The model render exceeded five minutes; simplify the asset or lower its voxel resolution.')
                        try:
                            progress=json.loads((output/'progress.json').read_text())
                            with self.lock:
                                current=self.get(identifier)
                                if current['status']!='cancelled':
                                    current.update(progress=progress['completed']/len(VIEWS),current_view=progress['view']);self.put(current)
                        except (OSError,ValueError,KeyError):pass
                        time.sleep(.3)
                with self.lock:
                    current=self.get(identifier)
                    if current['status']=='cancelled':continue
                    if process.returncode:raise ValueError('Blender could not render this asset. Check its geometry and export an embedded, uncompressed GLB.')
                finish(output,job,job['source_sha256'])
                with self.lock:
                    current=self.get(identifier)
                    if current['status']!='cancelled':current.update(status='completed',progress=1,seconds=round(time.time()-job['started'],2));self.put(current)
            except Exception as error:
                with self.lock:
                    job=self.get(identifier)
                    if job['status']!='cancelled':job.update(status='failed',error=str(error)[:500]);self.put(job)
            finally:
                if process and process.poll() is None:
                    try:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                    except ProcessLookupError:pass
                with self.lock:self.processes.pop(identifier,None)
                self.pending.task_done()
