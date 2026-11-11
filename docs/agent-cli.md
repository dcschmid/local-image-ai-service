# CLI workflow for AI agents

For MCP tools, an installable skill, and the local image-generation preference,
see [agent integration](agents-integration.md). The
[model/preset inventory](../skills/local-image-ai/references/catalog.md) lists
the available choices; query discovery below for current settings.

The archive is also available as JSON: `gallery list [--offset N] [--favorites]`,
`gallery get IMAGE_ID`, `gallery favorite IMAGE_ID true|false`, and
`gallery delete IMAGE_ID [IMAGE_ID ...]` (up to 500 selected IDs). Each page
contains up to 60 images. Deleting archive records leaves exported copies intact.

Named templates are durable reference pictures shared by every model:
`templates list`, `templates save --source IMAGE_ID --name 'my portrait'`,
`templates rename IMAGE_ID --name NAME`, `templates delete TEMPLATE_ID ...`
(up to 200). `render`/`compose` accept `--template FILE` (uploaded first),
`--template-id ID`, `--mask FILE` and `--strength 0..1`; with any of these the
request becomes `mode img2img` (or `inpaint` with a mask), which requires the
model's editing verification receipt like the Studio does.

Use `local-image-ai-service render` for the same guided recipes, queued model
switches and image archive as the Studio. Successful agent commands write one
JSON document to stdout. Errors write one JSON document to stderr and exit
nonzero. Credentials are read from the private service configuration; never put
API keys into prompts or command arguments.

## Discover the installed models and recipes

```bash
local-image-ai-service models
local-image-ai-service catalog --model moss
local-image-ai-service recipes --model moss --search photo
local-image-ai-service recipes lowpoly-prop
local-image-ai-service presets
local-image-ai-service presets comic
local-image-ai-service formats
local-image-ai-service status --json
```

`catalog` contains model IDs, licenses, sources, defaults, guided recipe
definitions/examples, free-prompt styles, aspect ratios and Blender asset/view
options. `models` includes configuration and readable-file status. These discovery
commands do not start the service or switch a model. `configured_model` describes
the configuration; use `status --json` to check live readiness.

`recipes`, `presets` and `formats` work without a running service or configuration.
Recipe IDs are the 82 guided presets used in the web UI. `presets` lists the seventeen
optional styles for free prompts. Model `free_prompt_quality_profiles` and guided
`preview`/`standard`/`detail` qualities are identified separately in the catalog.

| Model ID | Intended use |
| --- | --- |
| `moss` | Photography, illustration and low-poly concepts. |
| `anima` | Anima Aesthetic anime and illustration. |
| `z-image` | Creative illustration and photography with CFG and negative-prompt control. |
| `z-image-turbo` | Eight-step photographic studies and short lettering at CFG 1. |
| `flux-pixel` | FLUX.2-klein Pixel Art with the PXART4 LoRA. |

## Preview before generating

The service must be running for `compose`, `render`, job commands and exports.
Start it explicitly with `local-image-ai-service start` when required.
`compose` validates the request through the Studio API and returns both the input
and complete prepared request. It queues no job, generates no image and switches
no model. Local installation/capability/size verification still applies.

```bash
local-image-ai-service compose --recipe lowpoly-vehicle --example \
  --modeling-view three-quarter --modeling-asset vehicle \
  --quality standard --seed 42
```

`--example` fills the recipe's example fields. Explicit fields then override them.
With a supported Blender view, it uses the selected asset's modeling starter
instead: for example, `vehicle` supplies the kart rather than the inventory chest.
Omitting `--example` leaves only your explicit input and the recipe's defaults.
Only `--subject` is required for a guided recipe without an example.

## Generate and export

```bash
# Anime character
local-image-ai-service render --recipe anima-portrait \
  --subject 'an adult explorer with short silver hair and a red jacket' \
  --seed 42 --save-dir ./artifacts/anime

# Any low-poly motif
local-image-ai-service render --recipe lowpoly-anything \
  --subject 'a fox exploring a crystal cave' --save-dir ./artifacts/lowpoly

# Complete circuit overview
local-image-ai-service render --recipe lowpoly-track-overview --example \
  --seed 42 --save-dir ./artifacts/track

# Realistic product image
local-image-ai-service render --recipe photo-product \
  --subject 'an amber glass bottle with a brushed brass cap' \
  --aspect-ratio 4:3 --save-dir ./artifacts/photo

# Blender modeling reference using a complete kart starter
local-image-ai-service render --recipe lowpoly-vehicle --example \
  --modeling-view three-quarter --modeling-asset vehicle \
  --seed 42 --save-dir ./artifacts/kart

# Pixel art with the PXART4 LoRA
local-image-ai-service render --recipe pixel-loot \
  --subject 'a red mushroom with white spots' \
  --seed 42 --save-dir ./artifacts/pixel

# Z-Image Turbo storefront with literal wording
local-image-ai-service render --recipe zimage-turbo-sign \
  --subject 'a tiny corner flower shop with one dark green painted sign' --text 'PETAL' \
  --aspect-ratio 16:9 --save-dir ./artifacts/sign

# Free prompt with a style preset and explicit sampling
local-image-ai-service render --model moss --prompt 'a lighthouse above a quiet harbor' \
  --preset comic --size 1024x1024 --steps 50 --seed 42 --save-dir ./artifacts/comic
```

`render` waits by default. The Studio worker loads the matching model and trusted
adapter/grid variant while serializing GPU use with other Studio and compatibility
requests. It archives each result and its settings. No service restart or browser
is needed for an ordinary queued model change. Generation itself is not retried.

Without `--save-dir`, the JSON result contains image metadata and authenticated
relative file URLs, and the image remains in the Studio archive. With the flag,
each completed image is exported to a unique private PNG and JSON sidecar. The paths are under
`images[i].exports.image` and `.metadata`.

Exports preserve the archived PNG bytes, alpha and embedded text metadata. Both
pixel variants are decoded and dimension-checked before writing. Files use mode
`0600` and exclusive creation; existing files are never overwritten. A failed
export rolls back its own newly created files and retains the server's archive.
The sidecar includes original request fields, sampling, provenance and export paths.

## JSON input and reproducible requests

`compose` and `render` accept `--input FILE` or `--input -` for stdin. The input is
an exact Studio request object, limited to 64 KiB; request flags cannot be mixed
with it. `render` output options such as count, async, timeout and save directory
remain available. The JSON `preset` field is metadata; use a complete free prompt
in exact API input, or use CLI `--prompt ... --preset ...` to compose a style.

```json
{
  "recipe": "lowpoly-character",
  "subject": "an adult forest courier with a green jacket and brown boots",
  "modeling_view": "front",
  "modeling_asset": "character",
  "quality": "standard",
  "aspect_ratio": "2:3",
  "seed": 42
}
```

```bash
local-image-ai-service compose --input request.json > preview.json
# Replay the original input, rather than sending the prepared record's internal fields:
jq '.input' preview.json | local-image-ai-service render --input - --save-dir ./artifacts
```

Guided sampling is controlled through `--quality` and `--aspect-ratio`; `--steps`,
`--cfg-scale`, `--sampler`, `--negative-prompt`, `--size` and `--preset` belong to
free prompts. Asset view options are available
with the supported low-poly, pixel and voxel recipes. MOSS supplies the low-poly appearance without an additional style adapter.
Agents cannot pass arbitrary adapter paths or runtime control tags.

AI references are single-view concepts or proposed concept sheets. Independently generated views can
change geometry or details. See [the shared-blockout workflow](blender-references.md).
A seed does not establish geometric or cross-hardware identity.

## Asynchronous work, batches and recovery

```bash
local-image-ai-service render --recipe lowpoly-vehicle --example --quality preview \
  --seed 42 --count 2 --async > queued.json

local-image-ai-service jobs list --status queued
local-image-ai-service jobs get JOB_ID
local-image-ai-service jobs wait JOB_ID --timeout 600 --save-dir ./artifacts
local-image-ai-service jobs cancel JOB_ID
local-image-ai-service export IMAGE_ID --save-dir ./artifacts
```

Replace `JOB_ID`/`IMAGE_ID` with the returned 32-character lowercase hexadecimal
ID. Normally an image and its job share an ID. Direct lookup also works when a
job has left the recent 200-job listing. `jobs wait` and `export` do not generate
another image. `export` defaults to the service's separate image output directory
when no save directory is supplied.

`--count` accepts 1–8. The resolved preview seed is pinned before submission;
subsequent jobs increment it modulo 2³¹. The server queue holds 16 pending jobs.
Submission is sequential: if a batch partially fits, the JSON error reports the
already accepted `job_ids`. Inspect those jobs before submitting more work.

`--async` returns accepted IDs immediately and cannot be combined with
`--save-dir`; export later through `jobs wait` or `export`. Waiting defaults to
the configured load timeout plus generation timeout plus 40 seconds, multiplied
by the batch count for `render`. `--timeout` overrides the client wait budget.
A wait timeout or client disconnect does not cancel server work.

| Exit | Meaning |
| --- | --- |
| 0 | Discovery/compose success, accepted asynchronous jobs, completed rendering, export or successful cancel request. |
| 1 | API, configuration, transport, validation or export failure. Inspect the JSON error and optional HTTP status. |
| 2 | Invalid CLI arguments, input JSON or incompatible flag combinations. |
| 3 | A waited job failed or was cancelled. |
| 4 | Client wait deadline expired; the job continues independently. |

Errors include `error.code` and `error.message`; known `job_id`, `job_ids`,
`image_id` and `http_status` are added where relevant. If a submission response is
lost, `submission_uncertain: true` means the server may have accepted it. No POST
is retried automatically. Inspect the recent jobs before resubmitting.

The existing `generate --prompt ...` compatibility command retains its previous
behavior: the requested model must already be loaded, no automatic archive/model
switch occurs, and saving is opt-in. Use `render` for the complete Studio workflow.

See [the CLI verification report](agent-cli-test-report.md) for isolated HTTP
coverage, real GPU rendering/export checks and user-data preservation.

