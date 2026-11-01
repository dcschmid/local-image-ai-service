"""Exercise the optional MCP SDK against the real authenticated HTTP adapter."""
import asyncio
import contextlib
from functools import wraps
import io
import json
from pathlib import Path
import selectors
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import test_agent_cli as fixtures
try:
    from mcp import Client
    import mcp_server
except ImportError:
    Client = None


def client_session(test):
    @wraps(test)
    async def run(self):
        async with Client(self.server) as self.client:
            await test(self)
    return run


@unittest.skipIf(Client is None, 'Optional MCP dependencies are not installed in this Python environment')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = fixtures.AgentCLITests('runTest');self.fixture.setUp()
        self.server = mcp_server.create_server(load_config=lambda: self.fixture.cfg)

    async def asyncTearDown(self):
        await asyncio.to_thread(self.fixture.tearDown)

    async def call(self, name, arguments=None):
        result = await self.client.call_tool(name, arguments or {})
        return result, result.structured_content

    @client_session
    async def test_discovery_has_live_ids_annotations_filters_and_examples(self):
        listing = await self.client.list_tools()
        tools = {tool.name: tool for tool in listing.tools}
        self.assertEqual(len(tools), 17)
        self.assertTrue(tools['compose'].annotations.read_only_hint)
        self.assertFalse(tools['generate_image'].annotations.read_only_hint)
        self.assertTrue(tools['cancel_job'].annotations.destructive_hint)
        _, models = await self.call('list_models')
        self.assertEqual(set(models['models']), {'moss', 'anima', 'qwen21', 'krea-pixel', 'z-image', 'z-image-turbo'})
        _, all_presets = await self.call('list_presets');self.assertEqual(all_presets['count'], 70)
        _, lowpoly = await self.call('list_presets', dict(model='moss', category='lowpoly'))
        self.assertEqual(lowpoly['count'], 9)
        self.assertIn('lowpoly-track-overview', [p['id'] for p in lowpoly['presets']])
        _, preset = await self.call('get_preset', dict(preset_id='lowpoly-anything'))
        self.assertEqual(preset['example_request']['recipe'], 'lowpoly-anything')
        resources = await self.client.list_resources()
        self.assertIn('local-image-ai://catalog', [str(r.uri) for r in resources.resources])
        self.assertEqual(self.fixture.studio.listing('job'), [])

    @client_session
    async def test_compose_all_models_and_literal_switch_values_without_protocol_output(self):
        for recipe, model in [('photo-product', 'moss'), ('anima-portrait', 'anima'), ('qwen-poster', 'qwen21'), ('pixel-loot', 'krea-pixel')]:
            result, data = await self.call('compose', dict(params=dict(recipe=recipe, example=True, quality='preview', seed=42)))
            self.assertFalse(result.is_error, data)
            self.assertEqual(data['request']['model'], model)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result, data = await self.call('compose', dict(params=dict(prompt='--help', model='moss', size='256x256')))
        self.assertFalse(result.is_error, data);self.assertEqual(data['request']['prompt'], '--help')
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(self.fixture.studio.listing('job'), [])

    @client_session
    async def test_async_batch_wait_timeout_and_explicit_cancellation(self):
        result, batch = await self.call('generate_image', dict(params=dict(recipe='lowpoly-anything', subject='a fox', seed=2**31-1), count=2))
        self.assertFalse(result.is_error, batch)
        self.assertEqual([j['seed'] for j in batch['jobs']], [2**31-1, 0])
        identifier = batch['jobs'][0]['id']
        result, pending = await self.call('wait_for_job', dict(job_id=identifier, timeout=1))
        self.assertFalse(result.is_error, pending);self.assertEqual(pending['status'], 'pending')
        self.assertEqual(self.fixture.studio.get(identifier, 'job')['status'], 'queued')
        self.assertEqual(len(self.fixture.studio.listing('job')), 2)
        _, cancelled = await self.call('cancel_job', dict(job_id=identifier))
        self.assertEqual(cancelled['status'], 'cancelled')
        _, jobs = await self.call('list_jobs', dict(status='queued'));self.assertEqual(len(jobs['jobs']), 1)

    @client_session
    async def test_export_keeps_png_alpha_metadata_and_native_pixel_bytes(self):
        identifier, full, native = self.fixture.image(pixels=True)
        result, data = await self.call('export_image', dict(image_id=identifier, save_dir=str(self.fixture.root / 'project-assets')))
        self.assertFalse(result.is_error, data)
        self.assertEqual(Path(data['exports']['image']).read_bytes(), full)
        self.assertEqual(Path(data['exports']['native_pixels']).read_bytes(), native)
        self.assertTrue(Path(data['exports']['metadata']).is_file())

    @client_session
    async def test_invalid_inputs_never_queue_and_missing_records_are_tool_errors(self):
        for params in (dict(recipe='anima-psx'), dict(prompt='a fox', model='cloud'), dict(recipe='lowpoly-anything', example=True, steps=2),
                       dict(recipe='lowpoly-anything', subject='<lora:foreign:1>'), dict(prompt='a fox', steps=0)):
            result, _ = await self.call('generate_image', dict(params=params))
            self.assertTrue(result.is_error)
        result, data = await self.call('get_job', dict(job_id='f'*32))
        self.assertTrue(result.is_error);self.assertIn('error', data)
        self.assertEqual(self.fixture.studio.listing('job'), [])

    @client_session
    async def test_library_favorites_and_explicit_deletion_leave_exported_files_intact(self):
        identifier, full, _ = self.fixture.image(pixels=True)
        _, before = await self.call('list_images');self.assertEqual(len(before['images']), 1)
        result, _ = await self.call('set_favorite', dict(image_id=identifier, favorite=True));self.assertFalse(result.is_error)
        _, favorites = await self.call('list_images', dict(favorites=True));self.assertEqual(len(favorites['images']), 1)
        _, exported = await self.call('export_image', dict(image_id=identifier, save_dir=str(self.fixture.root / 'exports')))
        result, deleted = await self.call('delete_images', dict(image_ids=[identifier]))
        self.assertFalse(result.is_error, deleted);self.assertEqual(deleted['deleted_count'], 1)
        _, after = await self.call('list_images');self.assertEqual(after['images'], [])
        self.assertEqual(Path(exported['exports']['image']).read_bytes(), full)


@unittest.skipIf(Client is None, 'Optional MCP dependencies are not installed in this Python environment')
class MCPStdioTests(unittest.TestCase):
    def test_legacy_client_negotiates_and_calls_discovery_without_stdout_noise(self):
        process = subprocess.Popen([sys.executable, str(Path(mcp_server.__file__))], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        selector = selectors.DefaultSelector();selector.register(process.stdout, selectors.EVENT_READ)
        def send(method, params=None, identifier=None):
            message = dict(jsonrpc='2.0', method=method)
            if params is not None: message['params'] = params
            if identifier is not None: message['id'] = identifier
            process.stdin.write(json.dumps(message) + '\n');process.stdin.flush()
            if identifier is None: return None
            self.assertTrue(selector.select(15), 'No stdio protocol response')
            response = json.loads(process.stdout.readline())
            self.assertNotIn('error', response);self.assertEqual(response['id'], identifier)
            return response['result']
        try:
            initialized = send('initialize', dict(protocolVersion='2025-11-25', capabilities={},
                                                 clientInfo=dict(name='local-image-test', version='1')), 1)
            self.assertEqual(initialized['protocolVersion'], '2025-11-25')
            send('notifications/initialized')
            self.assertEqual(len(send('tools/list', {}, 2)['tools']), 17)
            result = send('tools/call', dict(name='list_presets', arguments=dict(model='moss', category='lowpoly')), 3)
            self.assertFalse(result.get('isError'))
            self.assertEqual(json.loads(result['content'][0]['text'])['count'], 9)
        finally:
            selector.close();process.stdin.close()
            try: process.wait(5)
            except subprocess.TimeoutExpired: process.kill();process.wait(5)
            stderr = process.stderr.read();process.stdout.close();process.stderr.close()
        self.assertEqual(stderr, '')


if __name__ == '__main__': unittest.main()
