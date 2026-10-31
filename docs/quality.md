# MOSS quality settings and comparison

This page documents the existing MOSS-Image SFT weights. Other models and presets are covered in the [studio guide](studio.md). Quality tuning changes sampling and
resolution; it adds no image reviewer, automatic rejection, prompt rewriting, or regeneration.

## Recommended starting point

| Setting | Quality default | Notes |
| --- | --- | --- |
| Resolution | 1024×1024 | About one megapixel; smaller explicit sizes remain available |
| Steps | 50 | Configurable in private JSON; previous service default was 20 |
| CFG | 3.0 | Already matched the model's recommended starting point |
| Sampler | Euler | Kept unchanged |
| Scheduler / shift | Discrete / 5 | Explicitly selected; previously selected by native defaults |
| Negative-branch skipping | Layer 22 | Applied internally by the native MOSS implementation |
| Negative prompt | Empty | No hidden negative prompt is injected |

Sources checked on October 29, 2026: the [official SFT model card](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT),
[OpenMOSS user guide](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md), and
[pinned stable-diffusion.cpp MOSS documentation](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/docs/moss_image.md).
The guide recommends approximately 1–2 million pixels and at least 50 steps. This service keeps
its existing maximum of 1024 per dimension for the 8 GB GPU. Larger resolutions, other samplers,
negative prompts, and higher-precision weights have not been evaluated in this update.

## Use the settings

```bash
local-image-ai-service models
local-image-ai-service generate --model moss \
  --prompt 'A small lighthouse at sunset, stylized low-poly 3D game artwork' \
  --size 1024x1024 --seed 42 --save
```

The HTTP API and CLI use 1024×1024 when size is omitted. Open WebUI sends an explicit size;
select **1024×1024** in its image settings manually. Updating this service does not change
Open WebUI. Use a client timeout of at least 330 seconds with the default service deadline.

To trade quality for speed, edit only this service's private configuration:

```json
"sampling": {"steps": 20, "cfg": 3.0}
```

Then reload the service when it is idle:

```bash
local-image-ai-service restart
local-image-ai-service doctor
```

Set `steps` back to 50 for the quality default. A 512×512 or 768×768 request also provides a
faster preview. Administrative sampling provides defaults until the next restart. Per-request `steps` and
`cfg_scale` now override them; the generic `quality` API field remains unsupported.
See [configuration](configuration.md) for validation bounds and memory settings.

## Describe a four-person band clearly

The original prompt requests four members and several instruments without assigning positions
or roles. A more explicit alternative is:

```text
A powerful heavy metal band performing live on a stage, rendered as polished late-1990s
low-poly 3D video game artwork. Exactly four adult musicians: three standing across the
front of the stage and one drummer seated behind them. On the left, a bassist holding
one bass guitar. In the center, a vocalist playing one rhythm guitar at a microphone.
On the right, a lead guitarist holding one electric guitar. At the rear center, the
drummer sits at one clearly visible drum kit. Keep each musician's silhouette distinct,
with space between their bodies and instruments. Show their full bodies on the stage.
Energetic but readable playing poses. Large amplifiers, speakers, colored spotlights,
smoke, and cheering crowd silhouettes at the bottom. Chunky polygon geometry, flat
shading, simple materials, strong depth, a slightly low camera angle, and colorful gritty
concert lighting. Consistent stylized low-poly characters throughout the scene.
```

This is an optional prompt example for the caller. The service always uses the submitted prompt
without adding these instructions. Exact person counts, hands, anatomy, and visual quality remain
properties of the generated image; higher resolution or more steps cannot guarantee them.

## Comparison method

The local comparison uses the user's original heavy-metal prompt, seed 42, CFG 3, Euler,
and the same model files. It first compares 512×512 and 1024×1024 at 20 steps, then compares
20 and 50 steps at 1024×1024. Each generation runs sequentially through the service API.

Images and native PNG metadata stay under a separate temporary test directory inside
`~/.cache/local-image-ai-service/quality-comparison-*`; no existing pictures or benchmark
folders are used. `quality-comparison-current.txt` in that cache identifies the latest directory.
GPU memory is sampled once per second and includes desktop use; recorded maxima are observations,
not a guaranteed upper bound. One prompt and seed do not establish a universal quality ranking.
Changing image size also changes the noise grid and composition even when the seed is the same.

## Measured results — October 29, 2026

| Size | Steps | End-to-end time | Maximum observed total GPU memory |
| --- | --- | --- | --- |
| 512x512 | 20 | 15.67 s | 3,716 MiB |
| 1024x1024 | 20 | 76.95 s | 4,236 MiB |
| 1024x1024 | 50 | 190.61 s | 4,236 MiB |

In this visual comparison, 1024×1024 produced clearer instrument shapes and more legible
character detail than 512×512. Increasing to 50 steps refined details further, with a smaller
visible change and approximately 2.5 times the 20-step duration at the same resolution.
The 50-step run completed within the unchanged 300-second service deadline.

Actual steps, CFG, Euler sampling, seed, and dimensions were verified in each PNG's native
metadata. The explicit flow shift is 5 in the new run; the previous automatic default was
already 5. No model files, offload settings, or precision settings changed. All images were
returned without review. `comparison.html` and `report.json` in the latest comparison directory
provide full-resolution images, the original prompt, timings, and native metadata.

The example prompt assigning four explicit roles above has not been separately benchmarked.
It is a composition suggestion, not a measured claim that it fixes person count or anatomy.

## Prompt fidelity and a real 16:9 request

A later concert example confirmed another distinction: the image was generated at 1024×1024
and 50 steps even though its prompt requested 16:9. The actual output dimensions come from
the API `size` field or Open WebUI's explicit image-size setting. Writing an aspect ratio in
the prompt does not replace those dimensions. Within this service's current bounds,
**1024×576** is an exact supported 16:9 size. It contains fewer pixels than 1024×1024.

Read-only inspection of the native PNG metadata also confirmed that Open WebUI's enabled
Image Prompt Generation had reformulated the submitted concert description. The requested
female guitarist was still present in that reformulation, so its omission from the picture
cannot be attributed to a deleted instruction. To evaluate an exact prompt, call the service
CLI directly, or manually disable Image Prompt Generation in Open WebUI. No Open WebUI setting
was changed by this diagnosis or test.

The revised scene assigns three separate front-stage positions to the vocalist, female lead
guitarist, and bassist, with the drummer behind them on a low riser. The vocalist holds a
microphone and has an empty other hand. Speaker cabinets and trusses are behind the band; a
few audience silhouettes appear only along the lower edge. This resolves the competing
viewpoints of a photo-pit camera and a large audience behind the stage.

A direct service trial at 1024×576, seed 223972791, 50 steps, and CFG 3.0 completed in
**93.62 seconds**. Native metadata verified the exact unmodified prompt, seed, dimensions,
steps, and CFG. Visual inspection found a clearer role assignment and a more coherent stage.
This example changes both the prompt and aspect ratio and is not a controlled attribution
of improvement to one parameter. It is not an anatomy approval. Sampling, weights, and the
running service configuration were retained.

The exact tested prompt, PNG, and report are in the service-cache directory identified by
`~/.cache/local-image-ai-service/prompt-quality-current.txt` (`prompt.txt` and `report.json`).
All test output remains outside existing picture, project, and benchmark directories.
