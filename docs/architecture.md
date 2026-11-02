# Architecture and maintenance notes

Atelier consists of a static Astro frontend, a Python HTTP service and a separate
`stable-diffusion.cpp` process. The Python service owns validation, model selection,
queued jobs and the image archive. The native process owns inference. Only one job
or compatibility request uses the GPU at a time.

## Request flow

`src/agent_cli.py` adds JSON discovery plus `compose`, queued `render`, job
inspection/cancellation and validated PNG exports to the management CLI. It uses
the same Studio HTTP validation/worker as the browser. Direct job/image lookups
support agents independently of recent-list pagination. Client wait deadlines
leave server work intact; accepted or uncertain submissions are not retried.

`src/mcp_server.py` wraps the same CLI execution functions in a stdio MCP server:
22 typed tools cover discovery, preview, asynchronous generation, jobs, exports
and library management. A catalog resource exposes the current definitions.
Individual MCP waits are bounded; pending jobs continue on the service worker.
The bridge uses a separately installed optional SDK and opens no network port.

`src/agent_integration.py` installs and packages the portable skill, regenerates
its model/preset reference, and optionally registers Codex's MCP server and local
image preference. Managed receipts detect local skill edits; global instructions
and unrelated MCP settings are preserved. Claude Code and OMP use the same skill
and launcher through their private profile configuration. See
[agent installation and client setup](agents-integration.md).

The studio loads its catalog from `/studio/api/catalog`. Guided requests contain
a recipe and the user's subject, scene and optional details. `src/recipes.py`
compiles these deterministically into a prompt and sampling settings; it does not
call a language model. The prompt preview uses the same compiler as generation.

For low-poly Blender references, `src/modeling_reference.py` replaces the original
composition with an asset-specific single view. Its separate version is recorded
with the saved request. Omitting these options keeps existing recipes unchanged;
the catalog supplies the permitted asset/view choices and starter briefs. This
path requests readable concepts and does not assert geometric consistency between
independent generations. See [the Blender workflow](blender-references.md).

`Studio.prepare()` routes compiled recipes through the common request validator
used for free prompts. The service checks installed components, capabilities,
sampling limits and image dimensions before placing a job in SQLite. Dimensions
above the normal 1024-pixel limit require a local verification receipt for that
size and the current runtime/component fingerprint. The total pixel limit still
applies. Optional editing controls remain unavailable until their mode has a
matching local verification receipt.

The studio worker claims the server's generation lock before switching a model
or generating an image. The synchronous `/v1/images/generations` compatibility
API shares that lock and returns a busy response when it cannot acquire it.
Studio jobs persist their images automatically; the compatibility API returns
image bytes, with optional saving handled by the CLI client.

## Model profiles and adapters

`src/catalog.py` defines the six selectable profiles and their capabilities,
licenses and sampling defaults. `config/models.lock.json` pins downloaded
components by source revision, size and checksum. Actual model files live outside
the repository. `scripts/install-models.py` prepares the files and updates the
private configuration while the service is stopped.

| Profile | Components and special handling |
| --- | --- |
| MOSS SFT | Diffusion model, text encoder, VAE and tokenizer; photography, illustration and low-poly recipes. |
| Anima Aesthetic | Shared Anima diffusion model, text encoder and VAE; anime and illustration recipes. |
| Qwen Image 2.1 | Dedicated diffusion model, encoder and VAE; its non-commercial research license is displayed in the UI. |
| Z-Image / Turbo | Separate diffusion weights with one shared Qwen3 4B encoder and FLUX VAE; normal CFG/negative prompting versus eight-step distilled sampling. |
| Krea Pixel Art | Krea Turbo components with separately prepared 32, 64 and 128-grid DoRA variants, followed by deterministic pixel cleanup. |

MOSS handles all low-poly compositions through visible prompts and sampling
presets. The retired Anima PSX/Low Poly Style profiles and their separate adapter
loader are removed. Their historical images remain readable/exportable, and the
shared Anima Aesthetic base components remain available.

Krea's DoRA adapters need a different preparation path. The pinned native runtime
does not apply their learned magnitudes directly. `scripts/prepare-pixel-models.py`
merges each complete adapter into its own quantized diffusion copy using the CPU
conversion helper. At runtime the selected grid loads that prepared copy; it
must not apply the adapter a second time. The original base remains unchanged.
See the [pixel-art setup guide](krea-pixel-art.md) for dependencies and disk usage.

## Recipes and public examples

The 82 recipes include composition, lighting, negative prompts, aspect ratios and
model-specific sampling. Original guided inputs, the compiled request, recipe
version, selected seed, component paths and sampling metadata are saved with each
image. Additive recipes keep the existing recipe version; changes to existing
recipe semantics need a version review. A saved seed helps comparisons but does
not guarantee identical output across different hardware, weights or runtimes.

`scripts/build-examples.py` generates examples in a separate cache archive. It
can read existing candidates without modifying the user's gallery, and reuses
them only when their inputs, compiled settings and required adapter revision
match. The bundled manifest records the actual example inputs and seed, which
the frontend restores through “Use this example”. Public WebP examples and native pixel PNGs are committed under `studio/public/recipe-examples/`.

## Private image lifecycle

The studio stores private data in
`~/.local/share/local-image-ai-service-images/studio/`. SQLite records use
`(id, kind)` as the primary key so a job and its completed image can share an ID.
Image filenames use validated opaque IDs. Private file routes require a visible
archive or upload record; knowing a filename alone does not grant access.

Generated PNGs are fully decoded and checked before saving. Ordinary text
generation preserves the original PNG bytes, including transparency and text
metadata. Pixel cleanup quantizes the palette without dithering and assigns one
color per square cell. It saves both a native small PNG and a nearest-neighbor
enlarged PNG. Both files are flushed before committing gallery visibility.

Deletion validates the whole selection before changing it. A transaction hides
the image and its job and records a deletion tombstone. File cleanup then removes
both PNG variants and associated report entries. If cleanup is interrupted, the
tombstone lets startup retry it while the image remains inaccessible. The browser
revokes both cached blob URLs and clears detail, result and comparison views.
Jobs interrupted by a service restart become failed rather than generating again.

## Filesystem boundaries and deployment

| Location | Purpose |
| --- | --- |
| Repository `src/`, `studio/`, `scripts/`, `docs/` | Source, curated public examples, setup tools and documentation. |
| `~/.config/local-image-ai-service/config.json` | Private machine configuration and model paths. |
| `~/.local/share/local-image-ai-service/app/` | Installed Python sources and the built studio under `web/`. |
| `~/.local/share/local-image-ai-service/runtime/` | Pinned native executable, CUDA libraries and runtime receipt. |
| `~/.local/share/local-image-ai-service/mcp/venv/` | Optional isolated Python MCP SDK environment. |
| Repository `skills/local-image-ai/` | Portable agent instructions and catalog/workflow references; packaged by `agents package`. |
| `~/.local/share/local-image-ai-service-images/` | User-owned generated images and the studio archive; retained on uninstall. |
| `~/.cache/local-image-ai-service/` | Runtime work files and isolated verification/example archives. |

Astro builds static pages; Python serves the resulting assets and API on loopback.
There is no separate frontend server in the installed application. API routes use
the service's optional bearer authentication and same-origin checks; the static
shell itself contains no private gallery data. Authentication tokens remain in
browser memory and are attached to API/image requests, including blob downloads.

Build the frontend before running `scripts/install.py`, and stop the user service
before installing application or model updates. The installer does not enable
login autostart. It operates on this application's files and its own subprocess;
existing model sources and unrelated image/game directories are not cleanup
targets. See [installation](installation.md) and [configuration](configuration.md)
for commands and supported paths.

The [Blender reference check report](blender-reference-test-report.md) records
single-view generation results and the observed limits of AI camera consistency.

## Verification

Run `python3 -m unittest discover -s tests -v` for request, recipe, archive,
adapter and pixel-processing checks, and `npm run build --prefix studio` for the
static application. Browser scenarios use Firefox through
`studio/playwright.config.js`. Semgrep is the security validation lane.

The `scripts/verify-*.py` tools perform explicit GPU checks with their documented
service lifecycle requirements. Prefer their isolated archives for new model QA;
do not generate disposable checks into the user's gallery. Existing measurements
and limitations are recorded in the model-specific test reports, including
[historical Anima Low Poly](anima-lowpoly-test-report.md) and
[Krea Pixel Art](krea-pixel-test-report.md). The current [Z-Image and expanded-preset report](z-image-and-presets.md#verification-results) includes the compatible checkpoint, all 70 examples, native format checks and CLI/MCP measurements.

## CPU model views

`asset_views.py` validates embedded GLB uploads and maintains an independent persistent CPU queue. `render_asset.py` runs in a separate factory-startup Blender process, bakes one static model and renders seven shared-scale orthographic cameras. Pixel postprocessing uses one cross-view palette; voxel conversion creates one shared cubic surface mesh before rendering. Authenticated API routes, the Astro asset page, CLI `assets` commands and five MCP tools share this workflow. See [formats, bounds and verification](asset-views.md).
