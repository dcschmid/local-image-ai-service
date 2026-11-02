"""Local studio: bounded jobs, validated uploads, private persistent history and static UI."""
from __future__ import annotations
from contextlib import contextmanager
import base64
import hashlib
import http.client
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid
from urllib.parse import urlsplit, parse_qs
import warnings

from PIL import Image, ImageFilter, ImageOps, PngImagePlugin
from catalog import MODELS, SAMPLERS, defaults, presets, quality_profiles
from recipes import compose, recipes, formats, VERSION as RECIPE_VERSION
import pixel_art
import modeling_reference

DATA = Path.home() / '.local/share/local-image-ai-service-images/studio'
STATIC = Path(__file__).resolve().parent / 'web'
if not STATIC.exists():
    STATIC = Path(__file__).resolve().parents[1] / 'studio/dist'
MAX_UPLOAD = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 16_000_000

def error(status, message, code='studio_error'):
    from service import APIError
    raise APIError(status, message, code)

def image_bytes(raw):
    if len(raw) > MAX_UPLOAD:
        error(413, 'Image is too large (maximum 12 MiB).')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 16_000_000:
                    raise ValueError()
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError()
                image.load()
                out = io.BytesIO()
                canonical = ImageOps.exif_transpose(image).convert('RGB')
                canonical.save(out, format='PNG')
                return out.getvalue(), canonical.size
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        error(400, 'Invalid image. Use PNG, JPEG or WebP up to 16 megapixels.')

def native_request(backend, method, route, payload=None):
    from service import MAX_RESPONSE
    conn = http.client.HTTPConnection('127.0.0.1', backend.cfg['backend_port'], timeout=15)
    try:
        conn.request(method, route, None if payload is None else json.dumps(payload), {'Content-Type':'application/json'})
        response = conn.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Backend response is too large')
        result = json.loads(raw)
        if response.status not in (200, 202):
            raise ValueError('Backend HTTP ' + str(response.status) + ': ' + str(result.get('error', 'Error'))[:300])
        return result
    finally:
        conn.close()

class Studio:
    """Own queued jobs and private archive metadata independently of the native runtime."""

    def __init__(self, backend, root=None):
        self.backend = backend
        self.root = Path(root) if root else DATA
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.root / 'history.sqlite3'
        self.lock = threading.RLock()
        self.generation = None
        self.worker = None
        self.native_id = None
        self.active_id = None
        self.asset_views = None
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (id, kind))')
            if len([r for r in db.execute('PRAGMA table_info(records)') if r[5]]) == 1:
                db.execute('ALTER TABLE records RENAME TO legacy_records')
                db.execute('CREATE TABLE records (id TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (id, kind))')
                db.execute('INSERT INTO records SELECT * FROM legacy_records')
                db.execute('DROP TABLE legacy_records')
                for row in db.execute("SELECT data FROM records WHERE kind='job'").fetchall():
                    job = json.loads(row[0])
                    if job.get('status') == 'completed' and self.file(job['id']).is_file():
                        item = dict(id=job['id'], request=job['request'], created=job.get('completed',time.time()),
                                    seconds=round(job.get('completed',0)-job.get('started',0),2), favorite=False,
                                    license=MODELS.get(job['request']['model'],{}).get('license','Historical model'))
                        db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',(item['id'],'image',json.dumps(item)))
            # Never resume ambiguous work after a crash and accidentally regenerate images.
            for row in db.execute("SELECT id, data FROM records WHERE kind='job'").fetchall():
                job = json.loads(row[1])
                if job['status'] in ('queued','loading','generating'):
                    job.update(status='failed', error='The service stopped. The job was not restarted.')
                    db.execute("UPDATE records SET data=? WHERE id=? AND kind='job'", (json.dumps(job), row[0]))

        # Complete committed deletions after an interrupted unlink. Image metadata is
        # already hidden, and the file route checks archive membership as well.
        for item in self.listing('deleting',1000000):
            try: self.finish_deletion(item['id'])
            except OSError: pass

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def put(self, kind, item):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (item['id'], kind, json.dumps(item)))
        return item

    def get(self, identifier, kind):
        if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
            error(404, 'Record not found.')
        with self.db() as db:
            row = db.execute('SELECT data FROM records WHERE id=? AND kind=?', (identifier,kind)).fetchone()
        if row is None:
            error(404, 'Record not found.')
        return json.loads(row[0])

    def listing(self, kind, limit=200, offset=0, favorites=False):
        with self.db() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM records WHERE kind=? AND (?=0 OR json_extract(data, '$.favorite')=1) ORDER BY CAST(json_extract(data, '$.created') AS REAL) DESC, id DESC LIMIT ? OFFSET ?", (kind,int(favorites),limit,offset))]

    def file(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
            error(404, 'Image not found.')
        return self.root / (identifier + '.png')

    def pixel_file(self, identifier):
        return self.file(identifier).with_name(identifier + '.pixels.png')

    def write_file(self, identifier, raw, *, pixel=False):
        path = self.pixel_file(identifier) if pixel else self.file(identifier)
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    def finish_deletion(self, identifier):
        self.file(identifier).unlink(missing_ok=True)
        self.pixel_file(identifier).unlink(missing_ok=True)
        # QA reports can contain a second copy of the same image's settings.
        for name in ('recipe-report.json','gpu-report.json'):
            path=self.root/name
            if not path.exists():continue
            try:
                rows=json.loads(path.read_text())
                if not isinstance(rows,list):raise ValueError('Expected report list')
            except ValueError as exc:
                raise OSError('Image report could not be read: '+name) from exc
            remaining=[r for r in rows if not isinstance(r,dict) or r.get('image_id',r.get('id'))!=identifier]
            if len(remaining)==len(rows):continue
            temporary=path.with_name('.'+name+'.'+uuid.uuid4().hex+'.tmp')
            try:
                with temporary.open('x') as stream:
                    json.dump(remaining,stream,indent=2);stream.flush();os.fsync(stream.fileno())
                temporary.replace(path)
            finally:temporary.unlink(missing_ok=True)
        with self.db() as db:
            db.execute("DELETE FROM records WHERE id=? AND kind='deleting'",(identifier,))

    def delete_images(self, identifiers):
        if not isinstance(identifiers,list) or not 1<=len(identifiers)<=500:
            error(400,'Select 1 to 500 images to delete.')
        for identifier in identifiers:self.file(identifier)
        identifiers=list(dict.fromkeys(identifiers))
        with self.lock:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                # Validate the whole selection before hiding or removing any item.
                for identifier in identifiers:
                    image=db.execute("SELECT 1 FROM records WHERE id=? AND kind='image'",(identifier,)).fetchone()
                    pending=db.execute("SELECT 1 FROM records WHERE id=? AND kind='deleting'",(identifier,)).fetchone()
                    if image is None and pending is None:error(404,'A selected image was not found.')
                    job=db.execute("SELECT data FROM records WHERE id=? AND kind='job'",(identifier,)).fetchone()
                    if job and json.loads(job[0])['status'] in ('queued','loading','generating'):
                        error(409,'An active job cannot be deleted as an image.')
                for identifier in identifiers:
                    db.execute("DELETE FROM records WHERE id=? AND kind IN ('image','job')",(identifier,))
                    db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',(identifier,'deleting',json.dumps({'id':identifier})))
            failed=[]
            for identifier in identifiers:
                try:self.finish_deletion(identifier)
                except OSError:failed.append(identifier)
            if failed:error(500,'The images have been removed from the library; some files could not be deleted yet. The service will retry on its next start.','image_delete_failed')
        return {'deleted_ids':identifiers,'deleted_count':len(identifiers)}

    def delete_image(self, identifier):
        self.delete_images([identifier])
        return {'id':identifier,'deleted':True}

    def visible_file(self, identifier):
        path=self.file(identifier)
        with self.db() as db:
            found=db.execute("SELECT 1 FROM records WHERE id=? AND kind IN ('image','upload')",(identifier,)).fetchone()
        if not found: error(404,'Image not found.')
        return path

    def fingerprint(self, model):
        # Receipts are tied to runtime and the exact local component files.
        paths = [self.backend.cfg['runtime'], *self.backend.cfg['models'].get(model, {}).values()]
        try:
            return hashlib.sha256(json.dumps([(p, Path(p).stat().st_size, Path(p).stat().st_mtime_ns) for p in paths]).encode()).hexdigest()
        except OSError:
            return ''

    def verified_modes(self, model):
        try:
            receipt = json.loads((self.root / 'verification.json').read_text()).get(model, {})
            return receipt.get('modes', []) if receipt.get('fingerprint') == self.fingerprint(model) else []
        except (OSError, ValueError):
            return []

    def verified_sizes(self,model):
        try:
            receipt=json.loads((self.root/'verification.json').read_text()).get(model,{})
            return receipt.get('sizes',[]) if receipt.get('fingerprint')==self.fingerprint(model) else []
        except (OSError,ValueError):return []

    def catalog(self):
        from service import missing_files
        return [dict(id=name, **model, installed=not missing_files(self.backend.cfg,name),
                     loaded=self.backend.available() and self.backend.model == name,
                     verified_modes=self.verified_modes(name), sizes=self.verified_sizes(name), formats=formats(name), defaults=defaults(name), quality=quality_profiles(name)) for name,model in MODELS.items()]

    def examples(self):
        try:
            data=json.loads((STATIC/'recipe-examples/manifest.json').read_text())
            return {recipe['id']:data[recipe['id']] for recipe in recipes() if recipe['id'] in data}
        except (OSError,ValueError):
            return {}

    def upload(self, body):
        try:
            raw = base64.b64decode(body['data'], validate=True)
        except (KeyError, ValueError, TypeError):
            error(400, 'Image data is missing or invalid.')
        raw, size = image_bytes(raw)
        identifier = uuid.uuid4().hex
        self.write_file(identifier, raw)
        return self.put('upload', dict(id=identifier, size=list(size), created=time.time()))

    def prepare(self, body, verification=False):
        from service import validate_request
        if not isinstance(body, dict):
            error(400, 'Expected a JSON object.')
        if 'recipe' in body:
            try: resolved=compose(body)
            except ValueError as exc: error(400,str(exc))
            # Guided requests use the same validation path as free prompts.
            # Store original inputs separately for editable, reproducible reuse.
            prepared=self.prepare(resolved,verification)
            prepared['recipe_inputs']={k:v for k,v in body.items() if k not in ('model','seed')}
            prepared['recipe_version']=RECIPE_VERSION
            if body.get('modeling_view','off')!='off':
                prepared['modeling_version']=modeling_reference.VERSION
            return prepared
        allowed = {'model','prompt','size','seed','steps','cfg_scale','sampler','negative_prompt','mode','image_id','mask_id','strength','feather','preset','pixel_grid','pixel_colors'}
        if set(body) - allowed:
            error(400, 'Unknown job settings: ' + ', '.join(sorted(set(body)-allowed)))
        model = body.get('model', self.backend.model)
        if not isinstance(model,str) or model not in MODELS:
            error(404, 'Unknown model.')
        from service import missing_files
        if missing_files(self.backend.cfg, model):
            error(409, 'Model is not installed.')
        mode = body.get('mode','text')
        if mode not in MODELS[model]['modes']:
            error(400, 'This model does not support the selected mode.')
        if mode != 'text' and not verification and mode not in self.verified_modes(model):
            error(409, 'This editing mode has not been verified locally yet.')
        settings = defaults(model)
        request = {k:v for k,v in body.items() if k in {'model','prompt','size','seed','steps','cfg_scale','sampler','negative_prompt'}}
        request.setdefault('steps', settings['steps'])
        request.setdefault('cfg_scale', settings['cfg'])
        request.setdefault('sampler', settings['sampler'])
        size = request.get('size','1024x1024')
        max_dimension = 1024
        if verification:
            max_dimension = 1536
        else:
            try:
                receipt = json.loads((self.root / 'verification.json').read_text()).get(model,{})
                # A larger dimension needs a receipt for these exact local files;
                # the common validator still enforces the total pixel budget.
                if receipt.get('fingerprint') == self.fingerprint(model) and size in receipt.get('sizes',[]):
                    max_dimension = 1536
            except (OSError,ValueError): pass
        native, seed = validate_request(request, model, max_dimension=max_dimension)
        request.update(model=model,seed=seed,size=native['size'],mode=mode)
        if model=='krea-pixel':
            try: grid,colors=pixel_art.settings(body.get('pixel_grid',64),body.get('pixel_colors',24))
            except ValueError as exc: error(400,str(exc))
            if any(d % (1024//grid) for d in map(int,request['size'].split('x'))):
                error(400,'The canvas must align with the selected pixel grid.')
            request.update(pixel_grid=grid,pixel_colors=colors)
        elif 'pixel_grid' in body or 'pixel_colors' in body:
            error(400,'Pixel settings are available with Krea Pixel Art.')
        for key, default, maximum in [('strength',.65,1),('feather',8,32)]:
            value = body.get(key,default)
            if type(value) not in (int,float) or not 0 <= value <= maximum:
                error(400, 'Invalid value: ' + key)
            request[key] = value
        request['preset'] = body.get('preset','none')
        if not isinstance(request['preset'],str) or request['preset'] not in {p['id'] for p in presets()}:
            error(400, 'Unknown preset.')
        if mode != 'text':
            image = self.get(body.get('image_id'), 'upload')
            request['image_id'] = image['id']
            if mode == 'inpaint':
                mask = self.get(body.get('mask_id'), 'upload')
                if mask['size'] != image['size']:
                    error(400, 'The mask and reference must have the same dimensions.')
                with Image.open(self.file(mask['id'])) as m:
                    if m.convert('L').getextrema()[1] == 0:
                        error(400, 'The mask is empty. Mark the area to edit in white.')
                request['mask_id'] = mask['id']
        return request

    def submit(self, body, verification=False):
        request = self.prepare(body,verification)
        with self.lock:
            jobs = self.listing('job')
            if sum(j['status'] in ('queued','loading','generating') for j in jobs) >= 16:
                error(429, 'Queue is full (16 jobs).')
            return self.put('job', dict(id=uuid.uuid4().hex, status='queued', created=time.time(), request=request, error=None, progress=None))

    def cancel(self, identifier):
        with self.lock:
            job = self.get(identifier,'job')
            if job['status'] in ('completed','failed','cancelled'):
                return job
            job['status'] = 'cancelled'
            self.put('job',job)
            if self.active_id == identifier and self.native_id:
                try:
                    native_request(self.backend,'POST','/sdcpp/v1/jobs/'+self.native_id+'/cancel',{})
                except (OSError,ValueError,http.client.HTTPException):
                    # Worker enforces cancellation by stopping only its own runtime.
                    self.backend.stop()
            return job

    def switch(self, model, pixel_grid=64):
        from service import missing_files
        if model not in MODELS or missing_files(self.backend.cfg,model):
            error(409, 'Model is not installed.')
        if self.backend.model == model and self.backend.available() and (model!='krea-pixel' or self.backend.pixel_grid==pixel_grid):
            return
        self.backend.stop()
        self.backend.failure = None
        self.backend.model = model
        self.backend.pixel_grid = pixel_grid
        self.backend.start()
        if not self.backend.available():
            error(503, self.backend.failure or 'The model could not be loaded.')
        # Persist selection so CLI and subsequent restarts use the same model.
        from service import CONFIG
        self.backend.cfg['active_model'] = model
        if CONFIG.exists():
            temporary = CONFIG.with_suffix('.studio.tmp')
            with temporary.open('w') as stream:
                json.dump(self.backend.cfg,stream,indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(CONFIG)

    def run(self):
        from service import APIError
        while not self.backend.stopping.wait(.2):
            # Startup loader owns the runtime until ready or failed.
            if not self.backend.ready.is_set() and self.backend.failure is None:
                continue
            queued = [j for j in reversed(self.listing('job')) if j['status']=='queued']
            # Share GPU ownership with the compatibility API for the entire job,
            # including model switches and result persistence.
            if not queued or not self.generation.acquire(blocking=False):
                continue
            job = queued[0]
            try:
                with self.lock:
                    job = self.get(job['id'],'job')
                    if job['status'] != 'queued':
                        continue
                    self.active_id = job['id']
                    job.update(status='loading',started=time.time())
                    self.put('job',job)
                self.switch(job['request']['model'],job['request'].get('pixel_grid',64))
                if self.get(job['id'],'job')['status']=='cancelled':
                    continue
                result = self.generate(job)
                with self.lock:
                    if self.get(job['id'],'job')['status']=='cancelled':
                        continue
                    self.save_result(job,result)
                    job.update(status='completed', completed=time.time(), progress=1)
                    self.put('job',job)
            except Exception as exc:
                if self.native_id:
                    self.backend.failure = 'Runtime stopped after a job error: ' + str(exc)[:200]
                    self.backend.stop()
                with self.lock:
                    if self.get(job['id'],'job')['status'] != 'cancelled':
                        job.update(status='failed',error=str(exc)[:500],completed=time.time())
                        self.put('job',job)
            finally:
                self.native_id = self.active_id = None
                self.generation.release()

    def encoded(self, identifier):
        return base64.b64encode(self.file(identifier).read_bytes()).decode()

    def generate(self,job):
        from service import APIError
        req = job['request']
        width,height = map(int,req['size'].split('x'))
        settings = defaults(req['model'])
        sample = dict(sample_steps=req['steps'],sample_method=req['sampler'],scheduler=settings['scheduler'],guidance={'txt_cfg':req['cfg_scale']})
        if MODELS[req['model']].get('extra_sample_args'):
            sample['extra_sample_args']=MODELS[req['model']]['extra_sample_args']
        if settings['shift'] is not None:
            sample['flow_shift'] = settings['shift']
        payload = dict(prompt=req['prompt'],negative_prompt=req.get('negative_prompt',''),width=width,height=height,seed=req['seed'],
                       batch_count=1,sample_params=sample,output_format='png',embed_image_metadata=True,
                       vae_tiling_params={'enabled':True},preview='proj',preview_interval=1)
        if req['model']=='krea-pixel' and self.backend.pixel_grid!=req['pixel_grid']:
            raise ValueError('The loaded pixel variant does not match the requested grid.')
        if req['mode']=='reference':
            payload['ref_images'] = [self.encoded(req['image_id'])]
        elif req['mode'] in ('img2img','inpaint'):
            payload.update(init_image=self.encoded(req['image_id']),strength=req['strength'])
            if req['mode']=='inpaint':
                payload['mask_image'] = self.encoded(req['mask_id'])
        submitted = native_request(self.backend,'POST','/sdcpp/v1/img_gen',payload)
        self.native_id = submitted['id']
        deadline = time.monotonic() + self.backend.cfg['generation_timeout']
        job['status']='generating'
        with self.lock:
            if self.get(job['id'],'job')['status']!='cancelled':
                self.put('job',job)
        while not self.backend.stopping.wait(.35):
            if time.monotonic() > deadline:
                self.backend.failure = 'Time limit exceeded. The runtime was stopped.'
                self.backend.stop()
                raise TimeoutError(self.backend.failure)
            current = native_request(self.backend,'GET','/sdcpp/v1/jobs/'+self.native_id)
            if self.get(job['id'],'job')['status']=='cancelled':
                native_request(self.backend,'POST','/sdcpp/v1/jobs/'+self.native_id+'/cancel',{})
                cancel_deadline = time.monotonic()+10
                while current['status'] not in ('completed','failed','cancelled') and time.monotonic()<cancel_deadline:
                    time.sleep(.2)
                    current = native_request(self.backend,'GET','/sdcpp/v1/jobs/'+self.native_id)
                if current['status'] not in ('completed','failed','cancelled'):
                    self.backend.failure = 'Job cancelled: the runtime was stopped.'
                    self.backend.stop()
                return None
            if current['status']=='completed':
                return current['result']
            if current['status'] in ('failed','cancelled'):
                raise RuntimeError(str(current.get('error') or 'Job cancelled'))
            preview = current.get('preview') or {}
            job['progress'] = min(.99,preview.get('step',0)/max(1,preview.get('total_steps',1)))
            with self.lock:
                if self.get(job['id'],'job')['status']!='cancelled':
                    self.put('job',job)
        self.backend.stop()
        raise RuntimeError('The service stopped.')

    def save_result(self,job,result):
        req = job['request']
        images = result.get('images') or result.get('data')
        raw = base64.b64decode(images[0]['b64_json'],validate=True)
        # Fully decode before committing a result. Keep original PNG bytes for
        # text generation so native alpha and metadata survive unchanged.
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format!='PNG' or image.size != tuple(map(int,req['size'].split('x'))):
                raise ValueError('The backend returned incorrect image dimensions or format.')
            if req['mode']=='inpaint':
                with Image.open(self.file(req['image_id'])) as source:
                    original = source.convert('RGB').resize(image.size,Image.Resampling.LANCZOS)
                with Image.open(self.file(req['mask_id'])) as source:
                    mask = source.convert('L').resize(image.size,Image.Resampling.NEAREST)
                if req['feather']:
                    # Feather inward: original pixels outside the selected mask stay identical.
                    softened = mask.filter(ImageFilter.GaussianBlur(req['feather']))
                    from PIL import ImageChops
                    mask = ImageChops.multiply(mask,softened)
                merged = Image.composite(image.convert('RGB'),original,mask)
                out = io.BytesIO()
                info = PngImagePlugin.PngInfo()
                for key,value in image.info.items():
                    if isinstance(value,str): info.add_text(key,value)
                merged.save(out,format='PNG',pnginfo=info)
                raw = out.getvalue()
        identifier = job['id']
        pixel = None
        if req['model']=='krea-pixel':
            raw,small,pixel=pixel_art.refine(raw,req['pixel_grid'],req['pixel_colors'])
            pixel['weights']='dora-v1'
            self.write_file(identifier,small,pixel=True)
        self.write_file(identifier,raw)
        sampling = dict(defaults(req['model']), steps=req['steps'], cfg=req['cfg_scale'], sampler=req['sampler'])
        if MODELS[req['model']].get('extra_sample_args'):
            sampling['extra_sample_args']=MODELS[req['model']]['extra_sample_args']
        receipt_path = Path(self.backend.cfg['runtime']).parent.parent / 'receipt.json'
        try: runtime_receipt = json.loads(receipt_path.read_text())
        except (OSError,ValueError): runtime_receipt = {}
        metadata = dict(id=identifier,request=req,sampling=sampling,runtime_revision=runtime_receipt.get('revision'),
                        components=self.backend.cfg['models'].get(req['model'],{}),created=time.time(),seconds=round(time.time()-job['started'],2),favorite=False,
                        runtime=self.backend.cfg['runtime'],fingerprint=self.fingerprint(req['model']),license=MODELS[req['model']]['license'])
        if pixel: metadata['pixel']=pixel
        # SQLite commits gallery visibility only after PNG is durable.
        self.put('image',metadata)
        job['image_id']=identifier

    def read_body(self,h,limit=20*1024*1024):
        if h.headers.get('Transfer-Encoding') or len(h.headers.get_all('Content-Length',[]))!=1:
            error(400,'Exactly one Content-Length header is required.')
        try: length=int(h.headers['Content-Length'])
        except ValueError: error(400,'Invalid length.')
        if not 1<=length<=limit: error(413,'Request is too large.')
        if h.headers.get_content_type()!='application/json': error(415,'Expected JSON.')
        try:
            raw=h.rfile.read(length)
            if len(raw)!=length: raise ValueError()
            body=json.loads(raw)
            if not isinstance(body,dict): raise ValueError()
            return body
        except (ValueError,RecursionError): error(400,'Invalid JSON.')

    def send_file(self,h,path,content_type=None):
        if not path.is_file(): error(404,'File not found.')
        raw=path.read_bytes()
        h.send_response(200)
        h.send_header('Content-Type',content_type or mimetypes.guess_type(path)[0] or 'application/octet-stream')
        h.send_header('Content-Length',str(len(raw)))
        h.send_header('X-Content-Type-Options','nosniff')
        h.send_header('Cache-Control','no-store')
        h.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        h.end_headers()
        h.wfile.write(raw)

    def dispatch(self,h,api_key):
        route=urlsplit(h.path).path
        if h.command=='GET' and not route.startswith('/studio/api/'):
            relative=route.removeprefix('/studio').lstrip('/') or 'index.html'
            path=(STATIC / relative).resolve()
            if not path.is_relative_to(STATIC.resolve()): error(404,'File not found.')
            if path.is_dir(): path=path/'index.html'
            return self.send_file(h,path)
        h.authorize()
        if route=='/studio/api/assets' or route.startswith('/studio/api/assets/'):
            from asset_views import AssetViews,MAX_BODY as ASSET_MAX_BODY
            with self.lock:
                if self.asset_views is None:self.asset_views=AssetViews(self.root/'asset-views')
            assets=self.asset_views
            try:
                if h.command=='GET' and route=='/studio/api/assets/options':return h.send_json(200,assets.options())
                if h.command=='GET' and route=='/studio/api/assets':return h.send_json(200,assets.listing())
                if h.command=='POST' and route=='/studio/api/assets':return h.send_json(202,assets.submit(self.read_body(h,ASSET_MAX_BODY)))
                match=re.fullmatch('/studio/api/assets/([a-f0-9]{32})/files/([^/]+)',route)
                if h.command=='GET' and match:return self.send_file(h,assets.file(*match.groups()))
                match=re.fullmatch('/studio/api/assets/([a-f0-9]{32})',route)
                if h.command=='GET' and match:return h.send_json(200,assets.get(match[1]))
                match=re.fullmatch('/studio/api/assets/([a-f0-9]{32})/cancel',route)
                if h.command=='POST' and match:
                    self.read_body(h);return h.send_json(200,assets.cancel(match[1]))
            except FileNotFoundError:error(404,'Asset render not found.')
            except ValueError as exc:error(400,str(exc))
            error(404,'Unknown asset endpoint.')
        with self.lock:
            if self.worker is None:
                self.generation=h.server.generation
                self.worker=threading.Thread(target=self.run,name='studio-worker',daemon=True)
                self.worker.start()
        if h.command=='GET':
            if route=='/studio/api/status': return h.send_json(200,dict(ready=self.backend.available(),model=self.backend.model,error=self.backend.failure))
            if route=='/studio/api/catalog': return h.send_json(200,dict(models=self.catalog(),presets=presets(),samplers=SAMPLERS,recipes=recipes(),formats=formats(),examples=self.examples(),modeling=modeling_reference.options()))
            if route=='/studio/api/jobs': return h.send_json(200,self.listing('job'))
            match=re.fullmatch('/studio/api/jobs/([a-f0-9]{32})',route)
            if match: return h.send_json(200,self.get(match[1],'job'))
            match=re.fullmatch('/studio/api/gallery/([a-f0-9]{32})',route)
            if match: return h.send_json(200,self.get(match[1],'image'))
            if route=='/studio/api/gallery':
                try:
                    offset=int(parse_qs(urlsplit(h.path).query).get('offset',['0'])[0])
                    if not 0 <= offset <= 1000000: raise ValueError()
                except ValueError: error(400,'Invalid library offset.')
                favorites=parse_qs(urlsplit(h.path).query).get('favorites',['0'])[0]=='1'
                return h.send_json(200,self.listing('image',60,offset,favorites))
            match=re.fullmatch('/studio/api/files/([a-f0-9]{32})/pixels',route)
            if match:
                self.get(match[1],'image')
                return self.send_file(h,self.pixel_file(match[1]),'image/png')
            if route.startswith('/studio/api/files/'):
                return self.send_file(h,self.visible_file(route.split('/')[-1]),'image/png')
        if h.command=='DELETE':
            match=re.fullmatch('/studio/api/gallery/([a-f0-9]{32})',route)
            if match: return h.send_json(200,self.delete_image(match[1]))
        if h.command=='POST':
            body=self.read_body(h)
            if route=='/studio/api/uploads': return h.send_json(201,self.upload(body))
            if route=='/studio/api/gallery/delete': return h.send_json(200,self.delete_images(body.get('ids')))
            if route=='/studio/api/jobs': return h.send_json(202,self.submit(body))
            if route=='/studio/api/compose': return h.send_json(200,self.prepare(body))
            match=re.fullmatch('/studio/api/jobs/([a-f0-9]{32})/cancel',route)
            if match: return h.send_json(200,self.cancel(match[1]))
            match=re.fullmatch('/studio/api/gallery/([a-f0-9]{32})/favorite',route)
            if match:
                if type(body.get('favorite')) is not bool: error(400,'favorite must be a boolean.')
                item=self.get(match[1],'image');item['favorite']=body['favorite']
                return h.send_json(200,self.put('image',item))
            if route=='/studio/api/models/load':
                model=body.get('model')
                if not isinstance(model,str) or model not in MODELS: error(404,'Unknown model.')
                grid=64
                if model=='krea-pixel':
                    try: grid,_=pixel_art.settings(body.get('pixel_grid',64))
                    except ValueError as exc:error(400,str(exc))
                elif 'pixel_grid' in body:error(400,'Pixel settings are available with Krea Pixel Art.')
                from service import missing_files
                if missing_files(self.backend.cfg,model): error(409,'Model is not installed.')
                if not self.generation.acquire(blocking=False): error(409,'GPU is busy. You can switch models when the job finishes.')
                def load():
                    try: self.switch(model,grid)
                    except Exception as exc: self.backend.failure=str(exc)
                    finally: self.generation.release()
                threading.Thread(target=load,name='studio-model-loader',daemon=True).start()
                return h.send_json(202,{'status':'loading','model':model})
        error(404,'Unknown studio endpoint.')
