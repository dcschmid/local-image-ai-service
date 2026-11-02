# CLI fallback and recovery

All discovery/compose/render/job/export commands return JSON. Success goes to
stdout; failures go to stderr with a nonzero exit code. The CLI reads its private
configuration and bearer key itself. Do not pass credentials on command lines.

```bash
local-image-ai-service status --json
local-image-ai-service models
local-image-ai-service recipes --model moss --search lowpoly
local-image-ai-service recipes lowpoly-track-overview
local-image-ai-service presets
local-image-ai-service formats
```

When the service is offline, `local-image-ai-service start` starts it explicitly.
Use `render` for the complete Studio workflow; it queues work, switches models
through the serial worker and archives results. `generate --prompt` is the older
synchronous compatibility command and requires an already loaded matching model.

```bash
local-image-ai-service compose --recipe lowpoly-anything \
  --subject 'a fox exploring a crystal cave' --seed 42

local-image-ai-service render --recipe lowpoly-track-overview --example \
  --quality preview --seed 42 --async

local-image-ai-service jobs get JOB_ID
local-image-ai-service jobs wait JOB_ID --timeout 30 --save-dir ./artifacts
local-image-ai-service export IMAGE_ID --save-dir ./artifacts
```

Use actual returned IDs, not the placeholder strings. Asynchronous generation
cannot export immediately; use `jobs wait --save-dir` or `export` on completion.
For a single blocking command, omit `--async` and supply `--save-dir` to `render`.

Other useful starts:

```bash
local-image-ai-service render --recipe anima-portrait \
  --subject 'an adult explorer with short silver hair and a red coat' --save-dir ./artifacts

local-image-ai-service render --recipe photo-product \
  --subject 'an amber perfume bottle with a brass cap' --save-dir ./artifacts

local-image-ai-service render --recipe pixel-loot \
  --subject 'a red mushroom with white spots' --pixel-grid 32 --pixel-colors 24 --save-dir ./artifacts

local-image-ai-service render --recipe qwen-poster \
  --subject 'a tiny spacecraft above a desert canyon' --text 'EXPLORE' --save-dir ./artifacts
```

Discover IDs rather than inventing them. Guided mode uses quality
`preview`/`standard`/`detail`, aspect ratios and optional Blender or pixel options.
Free prompts use `--prompt`, optional `--preset`, size and sampling overrides.
`--input FILE` or `--input -` accepts an exact Studio JSON request without mixing
request flags. The `compose` result contains `.input` for replay and `.request`
for inspection; internal prepared fields are not accepted as raw request input.

`--count` accepts 1–8 and increments the resolved seed modulo 2^31. Export paths
are in `images[i].exports.image`, `.metadata` and optional `.native_pixels`.
Exports use unique private files and preserve the archived bytes. Do not infer
filenames or assume the enlarged pixel preview is the native sprite.

Exit 2 means invalid input/arguments; exit 3 means a waited job failed/cancelled;
exit 4 means the client wait expired. Exit 1 covers transport/API/config/export
failures. Read the JSON error, including `job_id`, accepted `job_ids`, `image_id`,
`http_status` and `submission_uncertain` when present. Inspect existing jobs and
retry only an export when the image already exists. Native generation is not
retried automatically.

## Library

```bash
local-image-ai-service gallery list --offset 0
local-image-ai-service gallery list --favorites
local-image-ai-service gallery get IMAGE_ID
local-image-ai-service gallery favorite IMAGE_ID true
local-image-ai-service gallery delete IMAGE_ID ANOTHER_IMAGE_ID
```

Pages contain up to 60 images. Multi-delete accepts 1–500 explicit IDs and removes
their archive PNG/native companions. It leaves exported project copies intact.
Use deletion only for the images the user requested to remove.

## Model views from a GLB

For actual matching cameras use `assets options`, then:

```bash
local-image-ai-service assets render --input ./kart.glb --style pixel --front=-Y --pixel-grid 64 --colors 24 --async
local-image-ai-service assets get JOB_ID
local-image-ai-service assets export JOB_ID --save-dir ./artifacts
```

`assets list` recovers recent imports. `assets wait JOB_ID --timeout 30` retains
an accepted ID on timeout. `assets cancel JOB_ID` stops only that own CPU job.
ZIP exports contain seven transparent views, a sheet, the rendered static GLB,
camera/hash metadata and native grid PNGs for Pixel Art. Do not extract arbitrary
archive paths from an untrusted server. The service's exports use fixed filenames.

Styles are `model`, `lowpoly`, `pixel`, `voxel`; front axes use Blender Z-up
coordinates, default −Y. Voxel resolution is 16/24/32/48/64 cubes along the longest
dimension. It produces a shared surface approximation, not a solid volume or a
reconstruction from an image. Native pixel grids are 32/64/128 with one palette
across all views. Self-contained uncompressed GLB files are limited to 32 MiB,
with embedded PNG/JPEG textures. Blender runs separately on CPU.
