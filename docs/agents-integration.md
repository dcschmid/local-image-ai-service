# Let your agent create local image assets

You can ask Codex, Claude Code or OMP for an image without remembering model IDs,
sampling settings or a long prompt template. Give it the subject, the look and
the folder where the result belongs:

> Create a low-poly wooden chest with two iron bands and a brass latch. Use the
> local image service and save the finished PNG in this project's assets folder.

The `local-image-ai` skill teaches the agent to discover the available models
and presets, preview the request, follow the job and export the finished image.
MCP provides tools for those steps; the JSON CLI is the fallback. Both use the
same worker and image archive as the Studio, with inference on your computer.

## Install the skill and MCP integration

After installing/updating the service application with `scripts/install.py`:

```bash
local-image-ai-service agents install --mcp --route-images
local-image-ai-service agents status
```

This installs `local-image-ai` into the current Codex skills directory, installs
the optional pinned MCP SDK in a separate virtual environment, and registers
`local-image-ai-service mcp` with `codex mcp add`. Existing servers and settings
are preserved. `--route-images` adds a managed preference block to the current
Codex `AGENTS.md`: image requests use the local service unless the user explicitly
selects another provider. It also directs model/preset questions to the live
catalog. SVG and code-native assets retain their existing workflows.

The skill is available on the next turn. Restart/reload the agent session to
discover a newly registered MCP server. Opening an MCP connection does not start
GPU inference or enable service login autostart. The `start_service` tool starts
the existing user service when an image task needs it; poll `service_status`
until loading finishes. Starting the service also serves the Studio.

The installer refuses to overwrite unmanaged or locally edited skills and a
different existing MCP entry with the same name. Before changing existing global
instructions/configuration it saves `AGENTS.md.before-local-image-ai` and
`config.toml.before-local-image-ai` beside those files. Repeating the installation
updates an unchanged managed skill without duplicating the preference block.
`CODEX_HOME`, when already configured, selects the current Codex directory.

For another agent that supports portable skills:

```bash
local-image-ai-service agents install --skills-dir /absolute/path/to/agent/skills
local-image-ai-service agents package --output build/local-image-ai.skill
```

The `.skill` file is a ZIP containing `local-image-ai/SKILL.md`, agent UI metadata,
a CLI workflow reference and a generated model/preset inventory. It contains no
weights, credentials or private images. Extract it into the target agent's skills
directory, or install directly from this repository's `skills/local-image-ai`
directory using that agent's normal skill installer. The same skill supports CLI
fallback when MCP is unavailable. It does not require an OpenAI API key.

For another MCP client, use its stdio server configuration with an absolute
launcher path (replace the example home directory):

```json
{
  "mcpServers": {
    "local-image-ai": {
      "command": "/home/USER/.local/bin/local-image-ai-service",
      "args": ["mcp"]
    }
  }
}
```

JSON envelope names vary by client. The transport is stdio, with no new network
listener. The bridge reads the existing private service configuration and token
file; credentials are not passed as command arguments. Base CLI/service commands
continue to work without optional MCP dependencies.

## Claude Code and OMP

The installed private frontend-ai-stack profiles also have the skill and MCP
integration. The skill lives in the private profile catalog and is linked by
`mm-profile-skills-sync` into Claude's current skills directory and OMP's native
private skills directory. The source stack's `payload/private/skills` contains
the same portable skill so a stack reinstall retains it.

```bash
mm-profile-skills-sync claude private --quiet
mm-profile-skills-sync omp private --quiet
claude mcp get local-image-ai
```

Claude's stdio server is registered through its supported user-scope command:

```bash
claude mcp add --scope user --transport stdio local-image-ai -- \
  "$HOME/.local/bin/local-image-ai-service" mcp
```

OMP registers the same command in
`~/.omp/profiles/private/agent/mcp.json`, alongside its existing servers:

```json
{
  "mcpServers": {
    "local-image-ai": {
      "type": "stdio",
      "command": "/home/USER/.local/bin/local-image-ai-service",
      "args": ["mcp"],
      "timeout": 60000
    }
  }
}
```

Merge this entry when configuring another installation; preserve existing
servers. The private profile rules prefer local image generation, and OMP's
native private `AGENTS.md` contains the same preference for direct `omp-private`
starts. OMP's model/provider settings remain YOLO-Auto only; image inference
uses this service rather than another coding agent.

Use a fresh Claude/OMP session after installation. The skill command is
`/local-image-ai` in Claude and `/skill:local-image-ai` in OMP; automatic discovery
also uses the skill description. Models and presets are available through the
same discovery tools as in Codex.

The private Claude and OMP skill copies have been refreshed for the current
82-preset catalog and [GLB asset workflow](asset-views.md). Their shared private
catalog and the stack's source payload contain the same managed skill as Codex,
including pixel/voxel exports and the five model-view tools. Verification found
22 MCP tools, a connected Claude registration and a working OMP discovery call.
Installed-profile and strict skill audits passed; see the
[refresh verification](asset-views-test-report.md#private-client-skill-refresh).

Working profiles keep their existing configuration. Claude Working uses its
scoped strict MCP configuration and swaps out private skill links at launch;
OMP Working has its own native MCP and skills directories. Neither Working
profile receives this private image integration.

Without the stack's profile manager, use `agents install --skills-dir` with
Claude's `~/.claude/skills` or the chosen OMP profile's native `agent/skills`
directory, then register the stdio entry in that client's configuration.

Client references: [Claude skills](https://code.claude.com/docs/en/skills),
[Claude MCP](https://code.claude.com/docs/en/mcp),
[OMP MCP configuration](https://github.com/can1357/oh-my-pi/blob/main/docs/mcp-config.md),
[OMP skills](https://github.com/can1357/oh-my-pi/blob/main/docs/skills.md).

## Discover and explain models and presets

The full current inventory is in
[the skill's model and preset reference](../skills/local-image-ai/references/catalog.md).
The installed/package copy is regenerated from the catalog at installation time;
agents should query live discovery before choosing IDs or reporting availability.

| Model ID | Best starting point | Guided presets |
| --- | --- | ---: |
| `moss` | Realistic photos, comic/craft illustrations, low-poly concepts and Blender references | 34: 9 photo, 7 craft/comic, 12 low-poly, 6 voxel |
| `anima` | Anime, manga, character art, print styles and illustrated backgrounds | 17 |
| `qwen21` | Detailed scenes, text, product/packaging concepts and transparent stickers | 10 |
| `krea-pixel` | Native pixel icons, characters, creatures, vehicles, rooms, landscapes and concept sheets | 11 |
| `z-image` | Fantasy paintings, ink wash, vintage science fiction, fashion and botanical art | 5 |
| `z-image-turbo` | Eight-step photo, cinema, product, lettering and food studies | 5 |

There are also 17 free-prompt styles and 7 aspect ratios. Discovery includes
model licenses and installation status; Qwen's configured profile has a
non-commercial research/evaluation license. Describe the installed profiles
accurately when agents explain the choices.

Each model’s `formats` lists its actual final and draft sizes; Z-Image’s 3:2 and
2:3 formats differ from the common defaults. After adding profiles, reconnect
long-running MCP clients so the bridge reloads its model and preset argument
schema. See [the expanded catalog’s sources and GPU checks](z-image-and-presets.md).

CLI discovery:

```bash
local-image-ai-service models
local-image-ai-service recipes --model moss --search low
local-image-ai-service recipes lowpoly-track-overview
local-image-ai-service presets
local-image-ai-service formats
local-image-ai-service catalog
```

`recipes` are guided templates with subject/scene/details inputs and prepared
settings. `presets` are style suffixes for free prompts. MCP `list_presets`
lists the guided recipes; `list_options` lists the free-prompt styles and sizes.
The Studio example library remains available under `/studio/`.

## MCP tools and resource

| Tool | Purpose |
| --- | --- |
| `list_models` | IDs, capabilities, licenses, defaults and installed status |
| `list_presets` | Guided recipes, filtered by model, category or search |
| `get_preset` | Full recipe, settings, tips, sources and editable example inputs |
| `list_options` | Free styles, aspect ratios, samplers, Blender assets/views |
| `service_status`, `start_service` | Observe readiness or start the existing user unit |
| `compose` | Validate and preview a request without queuing a job |
| `generate_image` | Queue 1–8 images and return job IDs immediately |
| `list_jobs`, `get_job`, `wait_for_job` | Follow progress; individual waits last at most 30 seconds |
| `cancel_job` | Cancel the specified job when requested |
| `export_image` | Export PNG, JSON metadata and native pixel companion |
| `list_images`, `get_image` | Find archived images and inspect their metadata |
| `set_favorite` | Set/clear an image's favorite flag |
| `list_asset_views`, `get_asset_views` | Inspect Blender options and CPU model render progress |
| `render_asset_views` | Queue seven shared-scale views from one local GLB |
| `export_asset_views`, `cancel_asset_views` | Export the model/view ZIP or cancel the specified CPU render |
| `delete_images` | Delete 1–500 explicitly selected archive IDs |

The `local-image-ai://catalog` resource exposes the full current catalog.
Tools include read-only/destructive annotations and typed input schemas. Outputs
contain JSON text and structured results, including structured tool errors.
The bridge uses Python MCP SDK 2.3.0 and also negotiates the legacy
`2025-11-25` protocol, which is covered by a real stdio client test.

Example MCP flow:

1. `list_presets({"model":"moss","category":"lowpoly"})` and
   `get_preset({"preset_id":"lowpoly-anything"})`.
2. `compose({"params":{"recipe":"lowpoly-anything","subject":"an orange fox beside a pond","quality":"preview","seed":42}})`.
3. `generate_image` with the same `params`; record the returned job ID.
4. `wait_for_job({"job_id":"RETURNED_ID","timeout":10})`, repeating until
   completed. A `pending` result means the job is still running.
5. `export_image({"image_id":"COMPLETED_IMAGE_ID","save_dir":"/absolute/project/assets"})`.

Choose `lowpoly-track-overview` for a full racing-circuit overview, or
`lowpoly-vehicle` with `modeling_asset=vehicle` and
`modeling_view=three-quarter` for a simpler kart reference. Separate generated
views are concept references; consistent geometry requires a shared Blender
blockout and orthographic renders. See [Blender references](blender-references.md).

Requests support the same recipe inputs, quality, ratios, seeds, pixel grid and
palette, Blender views and free-prompt sampling controls as the CLI. The running
service remains the authority for supported settings and verified resolutions.
Unsupported reference editing is reported; agents should not silently change
provider or promise identical multi-view geometry.

## CLI lifecycle and library operations

See [the complete JSON CLI workflow](agent-cli.md) for rendering, exact JSON
input, batch seeds and export details. Success goes to JSON stdout, errors to
JSON stderr. Images remain archived after client disconnection or export errors.

```bash
local-image-ai-service render --recipe lowpoly-track-overview --example --quality preview --seed 42 --async
local-image-ai-service jobs get JOB_ID
local-image-ai-service jobs wait JOB_ID --timeout 30 --save-dir ./assets
local-image-ai-service export IMAGE_ID --save-dir ./assets
local-image-ai-service gallery list --offset 0
local-image-ai-service gallery get IMAGE_ID
local-image-ai-service gallery favorite IMAGE_ID true
local-image-ai-service gallery list --favorites
local-image-ai-service gallery delete IMAGE_ID ANOTHER_IMAGE_ID
```

Each library page contains up to 60 images. Deletion removes selected archive
images and native companions; already exported project files remain intact.
Cancellation and deletion operate only on the explicitly supplied IDs.

A client wait timeout does not cancel a server job. Inspect/reuse accepted IDs
after a timeout, disconnect, uncertain submission, or partially accepted batch.
Do not automatically submit again: the first request may already be rendering.
Retry export from the completed image instead of generating another copy.

## Verification and upstream documentation

See [the measured CLI/MCP and installation report](agent-integration-test-report.md).

Run the standard tests with the optional runtime to include MCP scenarios:

```bash
~/.local/share/local-image-ai-service/mcp/venv/bin/python -m unittest discover -s tests
```

The tests use isolated archives and authenticated HTTP routes without GPU work.
Real GPU CLI/MCP checks are available through
`scripts/verify-agent-cli.py --with-mcp` while the main service is stopped; this
creates a separate private archive and leaves the normal image library alone.
Run it with the optional MCP Python environment.

Upstream references: [official Python MCP SDK](https://py.sdk.modelcontextprotocol.io/servers/tools/),
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
[Codex agent instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
