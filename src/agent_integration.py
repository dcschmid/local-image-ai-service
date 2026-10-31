"""Install and package the portable image skill and optional local MCP bridge."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid
import zipfile

NAME = 'local-image-ai'
MCP_REQUIREMENT = 'mcp==2.3.0'
START = '<!-- BEGIN LOCAL IMAGE AI SERVICE -->'
END = '<!-- END LOCAL IMAGE AI SERVICE -->'
ROUTING = START + '''
For image-generation and raster image-asset requests, use the local-image-ai skill
and the local-image-ai MCP server, or the local-image-ai-service CLI when MCP is
unavailable. Prefer this local service; use another image provider only when the
user explicitly requests it. This preference does not replace SVG/code-native
editing workflows. When asked which models or presets exist, query the service
catalog and explain the available choices using its current IDs and descriptions.
''' + END


def codex_root():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser()


def app_root():
    return Path.home() / '.local/share/local-image-ai-service'


def source_skill():
    base = Path(__file__).resolve().parent
    for candidate in (base / 'skills' / NAME, base.parent / 'skills' / NAME):
        if (candidate / 'SKILL.md').is_file(): return candidate
    raise ValueError('Packaged skill is missing; reinstall the service application.')


def inventory_markdown():
    from catalog import MODELS
    from recipes import recipes
    lines = ['# Available image models and guided presets', '',
             'Generated from the service catalog at installation/package time. Query the live catalog for current availability, settings and examples.', '',
             '## Models', '', '| ID | Model | Use | License |', '| --- | --- | --- | --- |']
    for identifier, model in MODELS.items():
        lines.append(f"| `{identifier}` | {model['name']} | {model['tip']} | {model['license']} |")
    lines.extend(['', '## Guided presets', ''])
    groups = {}
    for recipe in recipes(): groups.setdefault((recipe['model'], recipe['category']), []).append(recipe)
    for (model, category), selected in groups.items():
        lines.extend([f'### {model} / {category}', '', '| ID | Preset | Purpose |', '| --- | --- | --- |'])
        for recipe in selected:
            lines.append(f"| `{recipe['id']}` | {recipe['name']} | {recipe['description']} |")
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def skill_files():
    source = source_skill()
    files = {}
    for path in source.rglob('*'):
        if path.is_symlink(): raise ValueError('Skill packages cannot contain symlinks.')
        if path.is_file(): files[path.relative_to(source).as_posix()] = path.read_bytes()
    files['references/catalog.md'] = inventory_markdown().encode()
    return files


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally: temporary.unlink(missing_ok=True)


def install_skill(parent):
    parent = parent.expanduser().resolve();parent.mkdir(parents=True, exist_ok=True)
    target = parent / NAME
    if target.is_symlink(): raise ValueError('Refusing to replace a symlinked skill directory.')
    files = skill_files();receipt_name = '.local-image-ai-receipt.json'
    if target.exists():
        receipt_path = target / receipt_name
        if not receipt_path.is_file(): raise ValueError('Existing skill is not managed by this installer: ' + str(target))
        receipt = json.loads(receipt_path.read_text())
        actual = {p.relative_to(target).as_posix(): p for p in target.rglob('*') if p.is_file()}
        expected = receipt.get('files', {})
        if receipt.get('name') != NAME or set(actual) != set(expected) | {receipt_name} or any(p.is_symlink() for p in target.rglob('*')):
            raise ValueError('Existing skill contains unmanaged files; refusing to replace it.')
        if any(digest(actual[key].read_bytes()) != value for key, value in expected.items()):
            raise ValueError('Existing skill has local edits; preserve them before updating it.')
    staging = Path(tempfile.mkdtemp(prefix='.' + NAME + '-', dir=parent))
    backup = parent / ('.' + NAME + '-previous-' + uuid.uuid4().hex)
    try:
        for name, raw in files.items():
            path = staging / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(raw)
        (staging / receipt_name).write_text(json.dumps(dict(name=NAME, version=1,
            files={name: digest(raw) for name, raw in files.items()}), indent=2) + '\n')
        if target.exists(): target.rename(backup)
        try: staging.rename(target)
        except BaseException:
            if backup.exists(): backup.rename(target)
            raise
        if backup.exists(): shutil.rmtree(backup)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return target


def package_skill(output):
    output = output.expanduser().resolve();output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name('.' + output.name + '.' + uuid.uuid4().hex)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(skill_files().items()):
                info = zipfile.ZipInfo(NAME + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16;info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
        temporary.replace(output)
    finally: temporary.unlink(missing_ok=True)
    return dict(path=str(output), sha256=digest(output.read_bytes()))


def install_routing(root):
    path = root / 'AGENTS.md'
    if path.is_symlink(): raise ValueError('Refusing to edit a symlinked global instructions file.')
    existing = path.read_text() if path.exists() else ''
    if START in existing or END in existing:
        if existing.count(START) != 1 or existing.count(END) != 1 or existing.index(START) > existing.index(END):
            raise ValueError('Image-routing markers are ambiguous; no instructions changed.')
        first, last = existing.index(START), existing.index(END) + len(END)
        updated = existing[:first] + ROUTING + existing[last:]
    else:
        updated = existing.rstrip() + ('\n\n' if existing.strip() else '') + ROUTING + '\n'
    if updated != existing:
        backup = path.with_name('AGENTS.md.before-local-image-ai')
        if existing and not backup.exists(): atomic_text(backup, existing)
        atomic_text(path, updated)
    return path


def install_mcp_runtime():
    python = app_root() / 'mcp/venv/bin/python'
    if not python.is_file():
        python.parent.parent.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, '-m', 'venv', str(python.parent.parent)], check=True, capture_output=True)
    check = subprocess.run([str(python), '-c', "import importlib.metadata; from PIL import Image; print(importlib.metadata.version('mcp'))"], capture_output=True, text=True)
    if check.returncode or check.stdout.strip() != MCP_REQUIREMENT.split('==')[1]:
        uv = shutil.which('uv')
        command = [uv, 'pip', 'install', '--python', str(python)] if uv else [str(python), '-m', 'pip', 'install']
        result = subprocess.run([*command, MCP_REQUIREMENT, 'Pillow>=12.3.0,<13'], capture_output=True, text=True)
        if result.returncode: raise RuntimeError('Could not install optional MCP dependencies: ' + result.stderr[-1000:])
    return python


def register_codex(root):
    config = root / 'config.toml'
    if config.is_symlink(): raise ValueError('Refusing to change a symlinked Codex configuration.')
    original = config.read_text() if config.exists() else ''
    before = tomllib.loads(original)
    command = str(Path.home() / '.local/bin/local-image-ai-service')
    if not Path(command).is_file(): raise ValueError('Install the service CLI before registering MCP.')
    current = before.get('mcp_servers', {}).get(NAME)
    if current:
        if current.get('command') != command or current.get('args', []) != ['mcp']:
            raise ValueError('A different local-image-ai MCP entry already exists; no configuration changed.')
        return config
    codex = shutil.which('codex')
    if not codex: raise ValueError('Codex CLI is not available; use the documented stdio configuration.')
    backup = config.with_name('config.toml.before-local-image-ai')
    if original and not backup.exists(): atomic_text(backup, original)
    try:
        result = subprocess.run([codex, 'mcp', 'add', NAME, '--', command, 'mcp'], capture_output=True, text=True)
        if result.returncode: raise RuntimeError('Codex MCP registration failed: ' + result.stderr[-1000:])
        after = tomllib.loads(config.read_text())
        added = after.get('mcp_servers', {}).pop(NAME, None)
        if not after.get('mcp_servers') and 'mcp_servers' not in before:
            after.pop('mcp_servers', None)
        if not added or added.get('command') != command or added.get('args') != ['mcp']:
            raise RuntimeError('Unexpected Codex configuration change.')
        if after != before:
            # Some Codex versions normalize other MCP entries while adding one.
            # Keep the original text/settings and merge only our verified entry.
            merged = original.rstrip() + ('\n\n' if original.strip() else '') + (
                '[mcp_servers.local-image-ai]\ncommand = ' + json.dumps(command) + '\nargs = ["mcp"]\n')
            expected = dict(before, mcp_servers=dict(before.get('mcp_servers', {}), **{NAME: dict(command=command, args=['mcp'])}))
            if tomllib.loads(merged) != expected:
                raise RuntimeError('Cannot safely merge MCP into this configuration layout.')
            atomic_text(config, merged)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        if original: atomic_text(config, original)
        else: config.unlink(missing_ok=True)
        raise
    return config


def add_commands(commands):
    parser = commands.add_parser('agents', help='Install/package the image skill and optional local MCP integration')
    actions = parser.add_subparsers(dest='action', required=True)
    install = actions.add_parser('install')
    install.add_argument('--skills-dir', type=Path, help='Parent directory for the portable skill; default: current Codex skills directory')
    install.add_argument('--route-images', action='store_true', help='Add the local-image preference to the current Codex AGENTS.md')
    install.add_argument('--mcp', action='store_true', help='Install optional SDK dependencies and register the current Codex stdio server')
    package = actions.add_parser('package')
    package.add_argument('--output', type=Path, default=Path('build/local-image-ai.skill'))
    actions.add_parser('status')


def run(args):
    try:
        root = codex_root()
        if args.action == 'package': output = package_skill(args.output)
        elif args.action == 'status':
            path = root / 'config.toml';config = tomllib.loads(path.read_text()) if path.is_file() else {}
            output = dict(skill=str(root / 'skills' / NAME), skill_installed=(root / 'skills' / NAME / 'SKILL.md').is_file(),
                          mcp_runtime=(app_root() / 'mcp/venv/bin/python').is_file(), mcp_registered=NAME in config.get('mcp_servers', {}),
                          image_routing=(root / 'AGENTS.md').is_file() and START in (root / 'AGENTS.md').read_text())
        else:
            output = dict(skill=str(install_skill(args.skills_dir or root / 'skills')))
            if args.route_images: output['routing'] = str(install_routing(root))
            if args.mcp:
                output['mcp_python'] = str(install_mcp_runtime())
                output['mcp_config'] = str(register_codex(root))
            output['availability'] = 'The skill is available on the next turn; restart/reload the agent session to discover newly registered MCP tools.'
        print(json.dumps(output, indent=2));return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps(dict(error=dict(code='agent_install_error', message=str(exc)))), file=sys.stderr);return 1
