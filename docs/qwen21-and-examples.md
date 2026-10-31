# Qwen Image 2.1 and the recipe explorer

Research checked October 31, 2026. The studio now includes **Anima Aesthetic, MOSS SFT and Qwen Image 2.1 Uncensored GGUF**, with **34 guided recipes** and locally generated example images.

## Qwen model choice

The [supplier's model card](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized) describes its release as quantized original upstream weights without a built-in content checker. “Uncensored” is the supplier's designation; the card does not establish a separately trained uncensoring fine-tune. The service adds no content filtering or rating tags.

The installed diffusion file is `qwen-image-2.1-UC-Q4_K_M.gguf`. It uses the official Qwen3-VL-8B Q4_K_M text encoder and the dedicated Qwen Image 2.1 VAE. The [runtime's guide](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/docs/qwen_image_2.1.md) specifies this encoder family and warns that older Qwen/Wan VAEs are not interchangeable with the 2.1 VAE. These are text-to-image recipes; image editing would additionally require a vision projector and separate verification.

Every component is pinned to a Hugging Face revision with a SHA-256 checksum in `config/models.lock.json`. The three files total about 10.3 GB on disk. CPU offloading allows the text encoder and diffusion model to run in sequence on this 8 GB GPU.

## License

Qwen Image 2.1 uses the [Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE). Its model-use grant is restricted to non-commercial research and evaluation; commercial use requires a separate license. The studio displays this restriction in the model selector's note and license link. It is not labeled Apache-2.0 or unrestricted commercial software.

## Qwen recipes

| Recipe | Starting point | Useful detail |
| --- | --- | --- |
| Graphic travel poster | A bold subject and a short headline | Put exact wording in Visible text |
| Transparent sticker | A compact character or object | Keep the whole silhouette within the image |
| Editorial portrait | One person in a specific setting | Add expression, clothing and visible material texture |
| Product campaign | A product, surface and light source | Short label text is optional |
| Illustrated book cover | One focal scene and an optional title | Keep title and visual details in separate fields |
| Isometric world | A small place with a few important structures | Use consistent scale and materials |

Only Subject is required. Visible text is optional and limited to 600 characters; it is passed through in its original language. Short titles are easier to evaluate than blocks of text. Generated lettering still needs visual checking.

The [official model example](https://huggingface.co/Qwen/Qwen-Image-2.1) uses 40 steps. The local runtime example uses CFG 6 and Euler. Our Qwen profiles use **20 / 40 / 50 steps** for Draft / Recommended / More detail, **CFG 6**, Euler and the model's resolution-dependent **Flux schedule**. They do not inherit MOSS's fixed Shift 5. Sizes remain within the locally verified roughly one-megapixel budget; the upstream 2048px examples are not enabled on this GPU without verification.

Transparent stickers use the upstream RGBA prompting format. The raw PNG preserves the generated alpha channel. The explorer shows a checkerboard behind meaningful transparent areas; it is a display background, not part of the downloaded image. Tiny alpha deviations in otherwise opaque images do not label them transparent.

## New Anima and MOSS ideas

Anima adds **Retro anime**, **Mecha**, **Storybook gouache** and **Dynamic action**. These follow the [Aesthetic-specific prompting guidance](https://huggingface.co/circlestone-labs/Anima): descriptive captions or tags, ordinary spaces in tags, and no `score_*` tags. The recipes use their existing 35-step, CFG 4.5 Euler baseline. No new Anima weights or style LoRAs are required.

MOSS adds **Handmade clay**, **Layered paper cut**, **Bold comic illustration** and **Macro nature photography**. Following the [MOSS prompt guidance](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md) and [official caption enhancer](https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md), their custom briefs specify visible subjects, materials, camera, lighting and composition. Craft recipes have their own style instructions; they do not inherit the Low Poly exclusions against smooth geometry and photographic textures.

The existing twenty recipes keep exactly the same compiled prompts and settings. This includes all three Low Poly recipes and all eight earlier MOSS photography recipes. The new styles are custom Atelier recipes, not official downloadable preset packs or quality guarantees.

## Aspect ratios

Guided mode offers **Recommended**, **1:1**, **16:9**, **9:16**, **4:3**, **3:4**, **3:2** and **2:3**. Recommended retains the recipe’s original composition and size. Explicit ratios override only the canvas; the subject and style remain yours. Output shows the actual pixel dimensions before generation, even with an empty subject field.

| Ratio | Recommended / More detail | Draft |
| --- | --- | --- |
| 1:1 | 1024×1024 | 768×768 |
| 16:9 | 1024×576 | 1024×576 |
| 9:16 | 576×1024 | 576×1024 |
| 4:3 | 1024×768 | 768×576 |
| 3:4 | 768×1024 | 576×768 |
| 3:2 | 1152×768 | 768×512 |
| 2:3 | 768×1152 | 512×768 |

Draft reduces the canvas where possible and always uses its lower step count. For exact 16:9 and 9:16, Draft retains the same pixel size. All sizes respect the local pixel budget. Free prompt mode exposes the same seven ratios through Image size. The chosen ratio is saved with the original recipe inputs and restored when reusing an image. Using a recorded example restores that example’s ratio as well.

## Exploring and reproducing examples

Open **Explore** in the studio. Filter by model or search for a look. Each card shows the actual example's quality profile, size and step count. Open its image to inspect the complete prompt, negative prompt and original inputs.

**Use this example** restores its recipe, subject, setting, details, visible text when present, quality profile and seed. Change one field to explore a variation. Selecting a recipe alone keeps your current subject; the example button explicitly fills the example values.

Example images are separate from the user's image library. They are generated locally, exported as WebP previews and bundled under `studio/public/recipe-examples/`. Their manifest records actual settings and provenance. Existing results are reused only when their inputs and compiled requests match the current recipe exactly; custom user prompts are not repurposed as example assets. New outputs are written to an isolated cache directory.

To rebuild examples, stop the service and run:

```bash
python3 scripts/build-examples.py
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

`--reuse-only` exports matching existing examples without starting inference. `--only qwen-poster` regenerates or reuses a particular recipe. A changed prompt invalidates the previous example match.

## Installation

```bash
python3 scripts/install-models.py qwen21 --download-only
local-image-ai-service stop
python3 scripts/install-models.py qwen21
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

The first command downloads and verifies weights without modifying a running service's configuration. Model cleanup and installation retain all three selected models. Generated user images are preserved.

[Local GPU, format and browser verification](qwen21-test-report.md).
