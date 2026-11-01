# Z-Image and the expanded preset catalog

Research checked on 2026-11-01. The catalog now has six model profiles, 70 guided
presets and 16 editable free-prompt styles. The original 44 guided presets keep
their existing prompts and sampling settings. The additional 26 are our curated
templates, informed by the authors' guides; they are not official preset packs.

## Z-Image setup

| Profile | Steps | CFG | Negative prompt | Best starting points |
| --- | ---: | ---: | --- | --- |
| `z-image` | 28 draft / 40 recommended / 50 comparison | 4 | Supported | Painted worlds, ink, retro science fiction, fashion, botanical art |
| `z-image-turbo` | 8 | 1 | Unsupported | Everyday photographs, cinematic night, products, storefront lettering, food |

The [Z-Image authors](https://huggingface.co/Tongyi-MAI/Z-Image) recommend 28–50
steps and CFG 3–5. The [Turbo model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
describes eight-step distillation and English/Chinese lettering. Both checkpoints
use Apache-2.0. The [pinned runtime's Z-Image guide](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/docs/z_image.md)
supports both variants with a Qwen3 4B encoder and a FLUX VAE. This integration
uses Euler, discrete scheduling and the existing CUDA/offload path. The official
scheduler configurations specify [shift 6 for Z-Image](https://huggingface.co/Tongyi-MAI/Z-Image/blob/main/scheduler/scheduler_config.json)
and [shift 3 for Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/blob/main/scheduler/scheduler_config.json);
the two profiles preserve that difference explicitly.

The two profiles share their encoder and VAE, while keeping separate diffusion
weights. [models.lock.json](../config/models.lock.json) pins every component to a
repository revision, byte size and SHA-256. The current pinned components require
about 10.54 GB. No extra Python inference framework is needed.

The native GPU check caught blank white output from the initial Unsloth
`z-image-Q4_K_M.gguf`, despite a successful job status. The configured base
checkpoint is now the runtime author's [Z-Image Q4_0](https://huggingface.co/leejet/Z-Image-GGUF),
pinned at `96a6f157468e1372d47a7c96e32f2016bad12c3d`. The same fantasy request
then produced a visible painted scene. The symptom is also described in
[upstream issue 1488](https://github.com/leejet/stable-diffusion.cpp/issues/1488).
The example builder rejects uniform frames and requires a matching component
fingerprint before reusing cached images. Failed diagnostic images stay in the
isolated cache and are excluded from the public examples.

When the service is idle and the GPU is available:

```bash
local-image-ai-service stop
python3 scripts/install-models.py z-image z-image-turbo
local-image-ai-service start
local-image-ai-service render --recipe zimage-turbo-product \
  --example --quality preview --seed 42 --save-dir ./artifacts
```

Z-Image's recipe sizes stay within the 1024-pixel per-dimension API limit. Its
3:2 and 2:3 recommended formats use 960×640 and 640×960. The model catalog exposes
these sizes under each model's `formats`. Turbo's draft uses a smaller image
with the same eight steps; more steps are not presented as a quality upgrade.
Reference-image editing remains outside these text-to-image profiles.

## Review of all existing models

| Model | Guidance checked | Changes and additions |
| --- | --- | --- |
| MOSS SFT | [Official model card](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT), [MOSS user guide](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md) | Keep the locally established 50 steps, CFG 3, Euler and shift 5. Add risograph, embroidery, needle felt and stained glass. These prompt-driven material studies need no new adapters. |
| Anima Aesthetic 1.1 | [Author's settings and Aesthetic prompting section](https://huggingface.co/circlestone-labs/Anima) | Keep 35 steps, CFG 4.5, Euler and no score tags. Add woodblock print, chalk pastel, dark fantasy and solarpunk scenery. Explicit medium, framing and palette cues keep these distinct from the existing anime looks. |
| Qwen Image 2.1 | [Official model card](https://huggingface.co/Qwen/Qwen-Image-2.1) | Keep 40 steps and the existing transparent-image wording. Add a three-stage illustrated explainer, exploded product concept, packaging and neon lettering. The current research-license notice still applies. |
| Krea Pixel Art | [LoRA author's card](https://huggingface.co/e-n-v-y/Krea-2-Pixel-Art), [Krea prompting guide](https://github.com/krea-ai/krea-2/blob/main/docs/prompting.md) | Keep eight steps, 1024-square inference and native-grid cleanup. Preserve the author's advice to omit the pixel-art trigger at 64 pixels. Add creature, dialogue portrait, vehicle and overhead room concepts. |

These sources establish model capabilities and prompting guidance. The new
looks are a curation decision; the sources do not certify that every generated
image will match the intended medium. Inspect lettering, anatomy, connected
parts and room layouts before using them. Generated product studies are not CAD,
and pixel concepts do not provide matched animation frames or seamless tilesets.

The six extra free-prompt styles are `risograph`, `embroidery`, `woodblock`,
`ink-wash`, `retro-scifi` and `pastel`. Guided recipes additionally prepare
composition, examples and model settings. See the [complete inventory](../skills/local-image-ai/references/catalog.md)
for all IDs, purposes and model assignments.

The existing 44 public images were also inspected together as a visual overview.
The established photography, anime, low-poly, clay, paper and pixel looks already
cover distinct uses. The additions focus on missing materials, print media,
painted environments and practical game/product concepts rather than replacing
those established examples.

## Verification results

All 70 presets now have real public examples. All 26 additions were generated
locally and visually reviewed, including the four new native pixel PNGs. The
builder reused 33 original examples with matching component fingerprints and
regenerated 11 older examples whose stored fingerprints differed. These images
live in the separate verification cache; the private user gallery stays separate.

The original 44 presets still produce **1,056 identical compiled requests** when
compared with the previous implementation across three qualities and eight
format choices. Recipe version 4 records refinements to the three new Qwen text
recipes. Their examples now use Recommended quality: the `GROW` heading is
visible and the neon facade retains more shadow detail. The `BLOOM` main label
is readable, but Qwen still invents fine print below it despite the negative
prompt; inspect lettering and punctuation before using a result. Anima's pastel
example has a strong pastel palette, with a smoother finish than traditional chalk.

The final automated checks cover the full Python/MCP suite (**125 tests, one
optional NumPy-dependent converter check skipped**), the Astro production build,
eight Firefox browser checks and Semgrep (**219 rules, no findings**). An artifact
contract checks every public image, original inputs, composed prompt, sampling,
required example quality and native pixel dimensions. It also rejects uniform
frames while preserving valid single-color alpha silhouettes.

Both Z-Image variants completed native CUDA generation. In addition to the
preview series, two Recommended-quality requests exercised an isolated HTTP
service, the real CLI, and a newly started MCP stdio process:

| Recipe | Path checked | Size | Steps / CFG / shift | Seconds |
| --- | --- | --- | --- | ---: |
| `zimage-fantasy` | HTTP queue, CLI render and PNG/metadata export | 1024x768 | 40 / 4 / 6 | 103.67 |
| `zimage-turbo-sign` | Fresh MCP stdio discovery/compose/generate/wait/export and automatic model switch | 1024x768 | 8 / 1 / 3 | 18.59 |

The integration cases used seed 42. To repeat their image inputs through the
normal installed CLI:

```bash
local-image-ai-service render --recipe zimage-fantasy --example \
  --quality standard --seed 42 --save-dir ./artifacts/z-image
local-image-ai-service render --recipe zimage-turbo-sign --example \
  --quality standard --seed 42 --save-dir ./artifacts/z-image-turbo
```

For the MCP case, start a fresh bridge and call `generate_image` with
`{"params":{"recipe":"zimage-turbo-sign","example":true,"quality":"standard","seed":42}}`.
Keep the returned job ID, inspect `get_job` or `wait_for_job`, then call
`export_image` with that completed image ID and your output directory. The
recorded integration test used an isolated archive; these normal CLI/MCP runs
follow the regular Studio history workflow.

The exported PNG bytes matched the archived originals. Fresh MCP discovery
returned all six profiles and 70 presets, and the worker automatically switched
from Z-Image to Turbo. Existing long-running MCP clients need to reconnect to
load the expanded argument schema.

The finished application and portable skill are installed locally. The regular
Studio is ready with MOSS loaded, six installed profiles, 70 public examples and
16 free-prompt styles. All 70 presets also passed a Recommended-quality compose
request through the installed HTTP service. The private image gallery is unchanged.

`scripts/verify-formats.py` now accepts both variants and checks their model-specific
sizes. All seven final and draft aspect-ratio choices passed native dimension
checks, with receipts tied to the current component files. These quick two-step
checks establish output dimensions; the full recipe examples establish the
observed image results, rather than a quality guarantee for every format and seed.

### Measured examples for the 26 additions

Times are local RTX 5070 Laptop measurements with the pinned CUDA runtime and CPU
offloading. They describe these fixed-seed examples, not general performance.

| Preset | Quality | Canvas | Steps | Seconds |
| --- | --- | --- | ---: | ---: |
| `moss-risograph` | preview | 576x832 | 20 | 27.97 |
| `moss-embroidery` | preview | 768x768 | 20 | 37.05 |
| `moss-felt` | preview | 768x768 | 20 | 37.07 |
| `moss-stained-glass` | preview | 576x832 | 20 | 28.28 |
| `anima-woodblock` | preview | 576x832 | 30 | 20.06 |
| `anima-pastel` | preview | 768x768 | 30 | 25.47 |
| `anima-dark-fantasy` | preview | 576x832 | 30 | 20.01 |
| `anima-solarpunk` | preview | 832x576 | 30 | 20.03 |
| `qwen-infographic` | standard | 832x1216 | 40 | 174.51 |
| `qwen-exploded` | preview | 768x768 | 20 | 47.24 |
| `qwen-packaging` | standard | 1024x1024 | 40 | 177.77 |
| `qwen-neon-sign` | standard | 1216x832 | 40 | 169.81 |
| `pixel-creature` | preview | 1024x1024 | 8 | 36.20 |
| `pixel-portrait` | preview | 1024x1024 | 8 | 32.35 |
| `pixel-vehicle` | preview | 1024x1024 | 8 | 32.28 |
| `pixel-dungeon` | preview | 1024x1024 | 8 | 36.67 |
| `zimage-fantasy` | standard | 1024x768 | 40 | 103.67 |
| `zimage-ink` | preview | 576x832 | 28 | 41.76 |
| `zimage-retro-scifi` | preview | 576x832 | 28 | 38.95 |
| `zimage-fashion` | preview | 576x832 | 28 | 39.64 |
| `zimage-botanical` | preview | 576x832 | 28 | 38.55 |
| `zimage-turbo-photo` | preview | 768x768 | 8 | 12.32 |
| `zimage-turbo-cinema` | preview | 832x576 | 8 | 7.34 |
| `zimage-turbo-product` | preview | 768x768 | 8 | 9.50 |
| `zimage-turbo-sign` | standard | 1024x768 | 8 | 18.59 |
| `zimage-turbo-food` | preview | 768x768 | 8 | 9.51 |

## Rebuild the examples

When the service is idle and the GPU is available:

```bash
local-image-ai-service stop
python3 scripts/build-examples.py
python3 scripts/verify-formats.py --model z-image
python3 scripts/verify-formats.py --model z-image-turbo
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

The builder reuses examples only when their recorded inputs, sampling request
and component fingerprint match. Missing ones are generated in an isolated cache
archive; the manifest is written incrementally. No verification images are added
to the user's gallery. Inspect an accepted job before any retry after an uncertain
submission or a timeout.
