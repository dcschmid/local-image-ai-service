"""Optional stdio MCP bridge to the same catalog, validation and queue as the CLI."""
from __future__ import annotations

import argparse
import http.client
import json
import subprocess
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

import agent_cli
import manage
from catalog import MODELS, SAMPLERS, presets
from modeling_reference import options as modeling_options
from recipes import formats, recipes
from service import APIError

ModelID = Literal[tuple(MODELS)]
RecipeID = Literal[tuple(r['id'] for r in recipes())]
PresetID = Literal[tuple(p['id'] for p in presets())]
SamplerID = Literal[tuple(SAMPLERS)]
RecordID = Annotated[str, Field(pattern=r'^[a-f0-9]{32}$')]
Quality = Literal['preview', 'standard', 'detail']
Aspect = Literal['auto', '1:1', '16:9', '9:16', '4:3', '3:4', '3:2', '2:3']
JobStatus = Literal['queued', 'loading', 'generating', 'completed', 'failed', 'cancelled']


class ImageRequest(BaseModel):
    """Choose recipe+subject/example or a free prompt. Values share CLI validation."""
    model_config = ConfigDict(extra='forbid', strict=True)
    recipe: RecipeID | None = None
    subject: str | None = Field(default=None, max_length=2000)
    example: bool = Field(default=False, description='Use the selected recipe example; explicit fields override it.')
    prompt: str | None = Field(default=None, max_length=16000, description='Free prompt instead of recipe; supports preset and custom sampling.')
    model: ModelID | None = None
    scene: str | None = Field(default=None, max_length=2000)
    details: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=600)
    quality: Quality | None = None
    aspect_ratio: Aspect | None = None
    modeling_view: Literal['off', 'three-quarter', 'front', 'side', 'back', 'top'] | None = None
    modeling_asset: Literal['character', 'vehicle', 'prop', 'building', 'scene'] | None = None
    pixel_grid: Literal[32, 64, 128] | None = None
    pixel_colors: Literal[16, 24, 32, 64, 128] | None = None
    seed: int | None = Field(default=None, ge=0, lt=2**31)
    size: str | None = Field(default=None, pattern=r'^\d{3,4}x\d{3,4}$')
    steps: int | None = Field(default=None, ge=1, le=100)
    cfg_scale: float | None = Field(default=None, ge=1, le=12, allow_inf_nan=False)
    sampler: SamplerID | None = None
    negative_prompt: str | None = Field(default=None, max_length=16000)
    preset: PresetID | None = None

    @model_validator(mode='after')
    def choose_source(self):
        if (self.recipe is None) == (self.prompt is None):
            raise ValueError('Choose exactly one recipe or free prompt.')
        return self

    def arguments(self) -> list[str]:
        args = []
        for key, value in self.model_dump(exclude_none=True).items():
            if key == 'example':
                if value: args.append('--example')
            else:
                # Equals keeps literal user values such as "--help" from being
                # interpreted as CLI switches or corrupting the stdio protocol.
                args.append('--' + key.replace('_', '-') + '=' + str(value))
        return args


def reply(data: dict, *, error=False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(data, ensure_ascii=False))],
                          structured_content=data, is_error=error)


def create_server(**overrides) -> MCPServer:
    dependencies = dict(load_config=manage.load_config, request=manage.request,
                        save_image=manage.save_image, default_save_dir=manage.default_save_dir)
    dependencies.update(overrides)
    server = MCPServer('local-image-ai', version='1.0.0', log_level='WARNING', instructions=(
        'Use Local Image AI Service for local image creation. Discover models/presets before choosing IDs. '
        'Compose to preview, generate_image to queue, get_job/wait_for_job to inspect, then export_image '
        'to the requested project directory. Generation is asynchronous and changes models through the shared '
        'Studio worker. Never resubmit after an uncertain submission or wait timeout without inspecting jobs. '
        'Use service_status before starting an offline service. Reference views are concepts, not matched 3D geometry.'))
    read = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
    write = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

    def execute(argv):
        args = manage.build_parser().parse_args(argv)
        return agent_cli.execute(args, **dependencies)

    def guarded(action):
        try: return reply(action())
        except agent_cli.CommandError as exc:
            return reply(dict(error=dict(code=exc.code, message=str(exc), **exc.details)), error=True)
        except SystemExit:
            return reply(dict(error=dict(code='invalid_arguments', message='Request flags are incompatible. Consult the preset and compose schema.')), error=True)
        except (APIError, OSError, ValueError, KeyError, TypeError, RuntimeError, argparse.ArgumentTypeError, http.client.HTTPException, subprocess.SubprocessError) as exc:
            return reply(dict(error=dict(code='local_service_error', message=str(exc))), error=True)

    @server.tool(annotations=read, structured_output=False)
    def list_models() -> CallToolResult:
        """List current model IDs, names, capabilities, licenses, defaults and local installation status. No generation."""
        return guarded(lambda: execute(['models']))

    @server.tool(annotations=read, structured_output=False)
    def list_presets(model: ModelID | None = None, category: str | None = None, search: str = '') -> CallToolResult:
        """List guided presets with IDs and names, optionally filtered by model/category/search. Use get_preset for full inputs."""
        def listing():
            selected = [r for r in recipes() if (model is None or r['model'] == model) and
                        (category is None or r['category'] == category) and
                        search.casefold() in (r['id'] + ' ' + r['name'] + ' ' + r['description']).casefold()]
            return dict(count=len(selected), presets=[{key: r[key] for key in
                ('id', 'name', 'model', 'category', 'description', 'size', 'steps', 'cfg_scale', 'modeling_asset')} for r in selected])
        return guarded(listing)

    @server.tool(annotations=read, structured_output=False)
    def get_preset(preset_id: RecipeID) -> CallToolResult:
        """Get a guided preset's complete settings, tips, source and editable example request. Does not generate."""
        def detail():
            recipe = execute(['recipes', preset_id])
            return dict(preset=recipe, example_request=dict(recipe=preset_id, **recipe['example'],
                        quality=recipe.get('example_quality', 'standard'), seed=42))
        return guarded(detail)

    @server.tool(annotations=read, structured_output=False)
    def list_options() -> CallToolResult:
        """List free-prompt style presets, aspect ratios, samplers and Blender asset/view choices."""
        return guarded(lambda: dict(styles=presets(), formats=formats(), samplers=SAMPLERS, modeling=modeling_options()))

    @server.tool(annotations=read, structured_output=False)
    def service_status() -> CallToolResult:
        """Read live readiness, loaded model and GPU busy state without starting or switching anything."""
        def status():
            cfg = dependencies['load_config']()
            status, data = dependencies['request'](cfg, '/health')
            return dict(http_status=status, **data)
        return guarded(status)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False), structured_output=False)
    def start_service() -> CallToolResult:
        """Start the installed user service when image creation is requested and it is offline. Never enables login autostart."""
        def start():
            cfg = dependencies['load_config']()
            subprocess.run(['systemctl', '--user', 'start', manage.UNIT], check=True, capture_output=True, timeout=30)
            return dict(status='starting', model=cfg['active_model'], next_action='service_status')
        return guarded(start)

    @server.tool(annotations=read, structured_output=False)
    def compose(params: ImageRequest) -> CallToolResult:
        """Validate and preview exact prompts/settings through the running local service. Queues no job."""
        return guarded(lambda: execute(['compose', *params.arguments()]))

    @server.tool(annotations=write, structured_output=False)
    def generate_image(params: ImageRequest, count: Annotated[int, Field(ge=1, le=8)] = 1) -> CallToolResult:
        """Queue images locally and return job IDs immediately. Poll get_job or wait_for_job, then export_image. Do not retry uncertain submissions."""
        return guarded(lambda: execute(['render', *params.arguments(), '--count', str(count), '--async']))

    @server.tool(annotations=read, structured_output=False)
    def list_jobs(status: JobStatus | None = None) -> CallToolResult:
        """Inspect recent jobs; use before resubmitting after a lost response or disconnect."""
        return guarded(lambda: dict(jobs=execute(['jobs', 'list', *(['--status', status] if status else [])])))

    @server.tool(annotations=read, structured_output=False)
    def get_job(job_id: RecordID) -> CallToolResult:
        """Inspect one job, including progress/status, error, original request and completed image ID."""
        return guarded(lambda: execute(['jobs', 'get', job_id]))

    @server.tool(annotations=read, structured_output=False)
    def wait_for_job(job_id: RecordID, timeout: Annotated[float, Field(ge=1, le=30)] = 10) -> CallToolResult:
        """Wait up to 30 seconds. Return pending normally when the wait expires; the server job continues."""
        def wait():
            try: return execute(['jobs', 'wait', job_id, '--timeout', str(timeout)])
            except agent_cli.CommandError as exc:
                if exc.code != 'wait_timeout': raise
                return dict(status='pending', job=execute(['jobs', 'get', job_id]), next_action='get_job or wait_for_job; do not generate again')
        return guarded(wait)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False), structured_output=False)
    def cancel_job(job_id: RecordID) -> CallToolResult:
        """Cancel the specified job when cancellation is requested. Ordinary client wait timeouts do not require cancellation."""
        return guarded(lambda: execute(['jobs', 'cancel', job_id]))

    @server.tool(annotations=write, structured_output=False)
    def export_image(image_id: RecordID, save_dir: Annotated[str, Field(min_length=1)]) -> CallToolResult:
        """Export a completed PNG, native pixel companion if present, and metadata to a local directory. No new generation."""
        return guarded(lambda: execute(['export', image_id, '--save-dir=' + save_dir]))

    @server.tool(annotations=read, structured_output=False)
    def list_images(offset: Annotated[int, Field(ge=0, le=1000000)] = 0, favorites: bool = False) -> CallToolResult:
        """List up to 60 archived images per page, including prompts and IDs. Export selected IDs without regenerating."""
        return guarded(lambda: dict(images=execute(['gallery', 'list', '--offset', str(offset), *(['--favorites'] if favorites else [])])))

    @server.tool(annotations=read, structured_output=False)
    def get_image(image_id: RecordID) -> CallToolResult:
        """Read an existing image's full prompt, settings and metadata without exporting or generating."""
        return guarded(lambda: execute(['gallery', 'get', image_id]))

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False), structured_output=False)
    def set_favorite(image_id: RecordID, favorite: bool) -> CallToolResult:
        """Set or clear a library favorite for the specified image."""
        return guarded(lambda: execute(['gallery', 'favorite', image_id, str(favorite).lower()]))

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False), structured_output=False)
    def delete_images(image_ids: Annotated[list[RecordID], Field(min_length=1, max_length=500)]) -> CallToolResult:
        """Delete only explicitly requested archived image IDs and native companions. Local exported copies remain available."""
        return guarded(lambda: execute(['gallery', 'delete', *image_ids]))

    @server.resource('local-image-ai://catalog')
    def catalog_resource() -> str:
        """Current local model capabilities, recipe definitions and settings; no generation."""
        return json.dumps(execute(['catalog']), ensure_ascii=False)

    return server


if __name__ == '__main__':
    create_server().run(transport='stdio')
