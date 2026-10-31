"""JSON-first discovery, queued rendering and artifact export for local AI agents."""
import argparse
import http.client
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import time

from PIL import Image
from catalog import MODELS, SAMPLERS, defaults, presets, quality_profiles
from modeling_reference import ASSETS, VIEWS, options as modeling_options
from recipes import formats, recipes
from service import APIError, MAX_RESPONSE, missing_files, sampling_settings

COMMANDS = {'catalog', 'models', 'recipes', 'presets', 'formats', 'compose', 'render', 'jobs', 'export', 'gallery'}
JSON_LIMIT = 2 * 1024 * 1024
INPUT_LIMIT = 65536


class CommandError(Exception):
    def __init__(self, message, code='cli_error', exit_code=1, **details):
        super().__init__(message)
        self.code, self.exit_code, self.details = code, exit_code, details


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps(dict(error=dict(code='invalid_arguments', message=message))), file=sys.stderr)
        self.exit(2)


def identifier(value):
    if not re.fullmatch('[a-f0-9]{32}', value):
        raise argparse.ArgumentTypeError('Use a 32-character lowercase hexadecimal record ID.')
    return value


def positive_seconds(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('Timeout must be a finite positive number of seconds.')
    return result


def request_arguments(parser):
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--recipe', choices=[r['id'] for r in recipes()], help='Guided preset ID; discover with recipes')
    source.add_argument('--prompt', help='Free prompt; optional --preset adds a curated style')
    source.add_argument('--input', type=Path, help='Exact Studio request JSON file, or - for stdin; no input flag overrides')
    parser.add_argument('--model', choices=sorted(MODELS))
    parser.add_argument('--subject')
    parser.add_argument('--scene')
    parser.add_argument('--details')
    parser.add_argument('--text', help='Exact visible wording for Qwen recipes')
    parser.add_argument('--example', action='store_true', help='Start with the recipe example, then apply explicit inputs')
    parser.add_argument('--quality', choices=('preview', 'standard', 'detail'))
    parser.add_argument('--aspect-ratio', choices=['auto', *[f['id'] for f in formats()]])
    parser.add_argument('--modeling-view', choices=['off', *VIEWS])
    parser.add_argument('--modeling-asset', choices=list(ASSETS))
    parser.add_argument('--pixel-grid', type=int, choices=(32, 64, 128))
    parser.add_argument('--pixel-colors', type=int, choices=(16, 24, 32, 64, 128))
    parser.add_argument('--seed', type=int)
    parser.add_argument('--size', help='Free prompt only: WIDTHxHEIGHT, subject to local verification')
    parser.add_argument('--steps', type=int)
    parser.add_argument('--cfg-scale', type=float)
    parser.add_argument('--sampler', choices=SAMPLERS)
    parser.add_argument('--negative-prompt')
    parser.add_argument('--preset', choices=[p['id'] for p in presets()], help='Free prompt style ID')


def add_commands(commands):
    for name in ('catalog', 'models', 'recipes'):
        parser = commands.add_parser(name, help='JSON model/recipe discovery; no generation')
        parser.add_argument('--model', choices=sorted(MODELS))
        if name == 'recipes':
            parser.add_argument('id', nargs='?')
            parser.add_argument('--search', default='')
    parser = commands.add_parser('presets', help='List or inspect free-prompt style presets as JSON')
    parser.add_argument('id', nargs='?')
    commands.add_parser('formats', help='List guided aspect ratios and dimensions as JSON')
    request_arguments(commands.add_parser('compose', help='Validate and preview the exact Studio request without generating'))
    parser = commands.add_parser('render', help='Queue guided/free images, switch models through the Studio worker, and optionally export')
    request_arguments(parser)
    parser.add_argument('--count', type=int, choices=range(1, 9), default=1)
    parser.add_argument('--async', dest='asynchronous', action='store_true', help='Return accepted job IDs immediately')
    parser.add_argument('--timeout', type=positive_seconds, help='Total client wait budget; a timeout does not cancel jobs')
    parser.add_argument('--save-dir', type=Path, help='Export completed PNGs, native pixels and JSON metadata to this directory')
    parser = commands.add_parser('jobs', help='Inspect, wait for or cancel Studio jobs as JSON')
    actions = parser.add_subparsers(dest='action', required=True)
    listing = actions.add_parser('list')
    listing.add_argument('--status', choices=('queued', 'loading', 'generating', 'completed', 'failed', 'cancelled'))
    for name in ('get', 'wait', 'cancel'):
        action = actions.add_parser(name)
        action.add_argument('id', type=identifier)
        if name == 'wait':
            action.add_argument('--timeout', type=positive_seconds)
            action.add_argument('--save-dir', type=Path)
    parser = commands.add_parser('export', help='Export an existing image without generating again')
    parser.add_argument('id', type=identifier, help='Completed image ID (normally the same as its job ID)')
    parser.add_argument('--save-dir', type=Path, help='Defaults to ~/.local/share/local-image-ai-service-images')
    parser = commands.add_parser('gallery', help='List, inspect, favorite or delete archived images as JSON')
    actions = parser.add_subparsers(dest='action', required=True)
    listing = actions.add_parser('list')
    listing.add_argument('--offset', type=int, default=0, help='Offset into the library; each page contains up to 60 images')
    listing.add_argument('--favorites', action='store_true')
    actions.add_parser('get').add_argument('id', type=identifier)
    favorite = actions.add_parser('favorite')
    favorite.add_argument('id', type=identifier)
    favorite.add_argument('value', choices=('true', 'false'))
    actions.add_parser('delete').add_argument('ids', type=identifier, nargs='+', help='Delete 1–500 specified images and their native companions')


def build_request(args, cfg):
    keys = ('model', 'subject', 'scene', 'details', 'text', 'quality', 'aspect_ratio', 'modeling_view',
            'modeling_asset', 'pixel_grid', 'pixel_colors', 'seed', 'size', 'steps', 'cfg_scale', 'sampler', 'negative_prompt', 'preset')
    values = {key: getattr(args, key) for key in keys if getattr(args, key) is not None}
    if args.input is not None:
        if values or args.example:
            raise CommandError('--input cannot be combined with request overrides.', 'invalid_arguments', 2)
        if str(args.input) == '-':
            raw = sys.stdin.read(INPUT_LIMIT + 1).encode('utf-8')
        else:
            with args.input.expanduser().open('rb') as stream:
                raw = stream.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            raise CommandError('Input JSON exceeds 64 KiB.', 'invalid_input', 2)
        try: body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise CommandError('Input must contain valid UTF-8 JSON.', 'invalid_input', 2) from None
        if not isinstance(body, dict):
            raise CommandError('Input must be a JSON object.', 'invalid_input', 2)
        return body
    if args.recipe:
        forbidden = {'size', 'steps', 'cfg_scale', 'sampler', 'negative_prompt', 'preset'} & values.keys()
        if forbidden:
            raise CommandError('Guided presets use quality/aspect ratio; custom sampling requires --prompt: ' + ', '.join(sorted(forbidden)), 'invalid_arguments', 2)
        recipe = next(r for r in recipes() if r['id'] == args.recipe)
        body = dict(recipe=args.recipe)
        if args.example:
            reference = recipe['modeling_asset'] and args.modeling_view not in (None, 'off')
            body.update(ASSETS[args.modeling_asset or recipe['modeling_asset']]['example'] if reference else recipe['example'])
        body.update(values)
        if args.modeling_view == 'off' and args.modeling_asset is None:
            body.pop('modeling_asset', None)
        return body
    forbidden = {'subject', 'scene', 'details', 'text', 'quality', 'aspect_ratio', 'modeling_view', 'modeling_asset'} & values.keys()
    if forbidden or args.example:
        raise CommandError('Guided inputs and --example require --recipe.', 'invalid_arguments', 2)
    body = dict(prompt=args.prompt, **values)
    if args.preset is not None:
        preset = next(p for p in presets() if p['id'] == args.preset)
        body['prompt'] = ', '.join(part for part in (args.prompt.strip(), preset['suffix']) if part)
        model = MODELS[body.get('model', cfg['active_model'])]
        body.setdefault('negative_prompt', preset['negative'] if model['negative'] else '')
    return body


def export_directory(value):
    directory = value.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise CommandError('Save directory is not a directory: ' + str(directory), 'invalid_directory', 2)
    return directory


def checked_png(raw, size):
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'PNG' or image.size != size or image.width * image.height > 1100000:
            raise CommandError('Exported image format or dimensions differ from its metadata.', 'invalid_image')
        image.load()


class Client:
    def __init__(self, cfg, request, save_image):
        self.cfg, self.request, self.save_image = cfg, request, save_image

    def call(self, path, body=None, *, raw=False, timeout=10):
        try:
            status, result = self.request(self.cfg, '/studio/api/' + path, body=body, timeout=timeout,
                                          raw=raw, limit=MAX_RESPONSE if raw else JSON_LIMIT)
        except (OSError, ValueError, RuntimeError, http.client.HTTPException) as exc:
            raise CommandError(str(exc), 'transport_error', submission_uncertain=path == 'jobs' and body is not None) from None
        if status >= 400:
            if raw:
                try: result = json.loads(result)
                except (ValueError, UnicodeError): result = {}
            error = result.get('error', {}) if isinstance(result, dict) else {}
            if not isinstance(error, dict): error = {}
            raise CommandError(error.get('message', 'API request failed.'), error.get('code', 'api_error'), http_status=status)
        return result

    def job(self, job_id, timeout=10):
        job = self.call('jobs/' + identifier(job_id), timeout=timeout)
        if not isinstance(job, dict) or job.get('id') != job_id or job.get('status') not in ('queued', 'loading', 'generating', 'completed', 'failed', 'cancelled'):
            raise CommandError('API returned an invalid job record.', 'invalid_response')
        return job

    def wait(self, job_id, deadline):
        while True:
            remaining = deadline - time.monotonic()
            expired = CommandError('Client wait timed out. The job was not cancelled; inspect it before resubmitting.', 'wait_timeout', 4, job_id=job_id)
            if remaining <= 0: raise expired
            try: job = self.job(job_id, timeout=min(10, remaining))
            except CommandError:
                if time.monotonic() >= deadline: raise expired from None
                raise
            if job['status'] == 'completed': return job
            if job['status'] in ('failed', 'cancelled'):
                raise CommandError(job.get('error') or 'Job ' + job['status'], 'job_' + job['status'], 3, job_id=job_id, status=job['status'])
            time.sleep(min(.5, max(0, deadline - time.monotonic())))

    def image(self, image_id, directory=None):
        metadata = self.call('gallery/' + identifier(image_id))
        if not isinstance(metadata, dict) or metadata.get('id') != image_id:
            raise CommandError('API returned invalid image metadata.', 'invalid_response')
        output = dict(metadata, urls=dict(image='/studio/api/files/' + image_id))
        pixel = metadata.get('pixel')
        if pixel: output['urls']['native_pixels'] = '/studio/api/files/' + image_id + '/pixels'
        if directory is None: return output
        request = metadata['request']
        model, seed = request['model'], request['seed']
        if not isinstance(model, str) or not re.fullmatch('[a-z0-9_-]{1,80}', model) or type(seed) is not int or not 0 <= seed < 2**31:
            raise CommandError('Invalid export filename metadata.', 'invalid_response')
        size = tuple(map(int, request['size'].split('x')))
        raw = self.call('files/' + image_id, raw=True)
        checked_png(raw, size)
        small = None
        if pixel:
            small = self.call('files/' + image_id + '/pixels', raw=True)
            checked_png(small, (pixel['width'], pixel['height']))
        # Validate both variants before writing. Roll back only files created by
        # this export; the server's archived image remains available for retry.
        written = []
        try:
            path = self.save_image(raw, directory, model, seed);written.append(path)
            output['exports'] = dict(image=str(path))
            if small is not None:
                native = self.save_image(small, directory, model + '-pixels', seed);written.append(native)
                output['exports']['native_pixels'] = str(native)
            sidecar = path.with_suffix('.json')
            descriptor = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            written.append(sidecar)
            output['exports']['metadata'] = str(sidecar)
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(output, stream, indent=2, ensure_ascii=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        except BaseException:
            for path in written: path.unlink(missing_ok=True)
            raise
        return output


def discovery(args, load_config):
    selection = [r for r in recipes() if not getattr(args, 'model', None) or r['model'] == args.model]
    if args.command == 'recipes':
        if args.id:
            item = next((r for r in selection if r['id'] == args.id), None)
            if item is None: raise CommandError('Unknown recipe or model filter mismatch.', 'recipe_not_found', 2)
            return item
        return [r for r in selection if args.search.lower() in (r['name'] + ' ' + r['description'] + ' ' + r['id']).lower()]
    if args.command == 'presets':
        if not args.id: return presets()
        item = next((p for p in presets() if p['id'] == args.id), None)
        if item is None: raise CommandError('Unknown style preset.', 'preset_not_found', 2)
        return item
    if args.command == 'formats': return formats()
    cfg = load_config()
    models = {name: dict(model, defaults=defaults(name), free_prompt_quality_profiles=quality_profiles(name),
                        guided_qualities=['preview', 'standard', 'detail'],
                        configured=name in cfg['models'], installed=not missing_files(cfg, name),
                        missing=missing_files(cfg, name), recipes=[r['id'] for r in selection if r['model'] == name])
              for name, model in MODELS.items() if not args.model or args.model == name}
    output = dict(schema_version=1, configured_model=cfg['active_model'], models=models)
    if args.command == 'models':
        output['sampling'] = sampling_settings(cfg) if cfg['active_model'] == 'moss' else defaults(cfg['active_model'])
    else:
        output.update(recipes=selection, presets=presets(), formats=formats(), modeling=modeling_options(), samplers=SAMPLERS,
                      workflow=['compose', 'render', 'jobs get|wait|cancel', 'export'],
                      notes=['Discovery is local; configured_model is not a readiness claim. Use status --json.',
                             'compose/render use the running Studio API and its validation.',
                             'render archives results and switches models through the serial Studio worker.',
                             'Independent Blender reference views are concepts, not geometrically matched blueprints.'])
    return output


def execute(args, load_config, request, save_image, default_save_dir):
    if args.command in ('catalog', 'models', 'recipes', 'presets', 'formats'):
        return discovery(args, load_config)
    cfg = load_config()
    client = Client(cfg, request, save_image)
    if args.command == 'gallery':
        if args.action == 'list':
            if not 0 <= args.offset <= 1000000:
                raise CommandError('Library offset must be between 0 and 1000000.', 'invalid_arguments', 2)
            return client.call(f'gallery?offset={args.offset}&favorites={int(args.favorites)}')
        if args.action == 'get': return client.call('gallery/' + args.id)
        if args.action == 'favorite': return client.call('gallery/' + args.id + '/favorite', dict(favorite=args.value == 'true'))
        if len(args.ids) > 500:
            raise CommandError('Delete at most 500 images per request.', 'invalid_arguments', 2)
        return client.call('gallery/delete', dict(ids=args.ids))
    directory = export_directory(args.save_dir) if getattr(args, 'save_dir', None) is not None else None
    if args.command == 'export':
        try: return client.image(args.id, directory or export_directory(default_save_dir()))
        except OSError as exc:
            raise CommandError(str(exc), 'export_failed', image_id=args.id,
                               note='The archived image is retained; retry export without generating again.') from None
    timeout = getattr(args, 'timeout', None) or (cfg.get('load_timeout', 120) + cfg['generation_timeout'] + 40)
    if args.command == 'jobs':
        if args.action == 'list':
            jobs = client.call('jobs')
            return [j for j in jobs if not args.status or j['status'] == args.status]
        if args.action == 'get': return client.job(args.id)
        if args.action == 'cancel': return client.call('jobs/' + args.id + '/cancel', {})
        job = client.wait(args.id, time.monotonic() + timeout)
        return dict(status='completed', jobs=[dict(id=job['id'], status=job['status'])], images=[client.image(job['image_id'], directory)])
    body = build_request(args, cfg)
    if args.command == 'render' and args.asynchronous and directory is not None:
        raise CommandError('--async cannot export before completion; use jobs wait --save-dir or export later.', 'invalid_arguments', 2)
    prepared = client.call('compose', body)
    if args.command == 'compose': return dict(schema_version=1, input=body, request=prepared)
    jobs = []
    try:
        # Pin the preview's resolved seed before submitting; never resubmit a POST
        # after an uncertain transport failure, which could duplicate GPU work.
        seed = prepared['seed']
        for index in range(args.count):
            jobs.append(client.call('jobs', dict(body, seed=(seed + index) % 2**31)))
        summaries = [dict(id=j['id'], status=j['status'], model=j['request']['model'], seed=j['request']['seed']) for j in jobs]
        if args.asynchronous: return dict(status='queued', jobs=summaries)
        deadline = time.monotonic() + (args.timeout or timeout * args.count)
        images = []
        for job in jobs:
            completed = client.wait(job['id'], deadline)
            images.append(client.image(completed['image_id'], directory))
        return dict(status='completed', jobs=[dict(j, status='completed') for j in summaries], images=images)
    except CommandError as exc:
        exc.details['job_ids'] = [j['id'] for j in jobs]
        raise
    except (KeyError, TypeError, ValueError, argparse.ArgumentTypeError) as exc:
        raise CommandError('Invalid job or image response: ' + str(exc), 'invalid_response',
                           job_ids=[j['id'] for j in jobs if isinstance(j, dict) and 'id' in j],
                           submission_uncertain=True) from None
    except OSError as exc:
        raise CommandError(str(exc), 'export_failed', job_ids=[j['id'] for j in jobs],
                           note='Completed images remain archived. Inspect jobs and use export instead of generating again.') from None


def run(args, **dependencies):
    try:
        output = execute(args, **dependencies)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0
    except CommandError as exc:
        print(json.dumps(dict(error=dict(code=exc.code, message=str(exc), **exc.details)), ensure_ascii=False), file=sys.stderr)
        return exc.exit_code
    except (APIError, OSError, ValueError, KeyError, TypeError, RuntimeError, http.client.HTTPException) as exc:
        print(json.dumps(dict(error=dict(code='cli_error', message=str(exc))), ensure_ascii=False), file=sys.stderr)
        return 1
