# Atelier: Anima, MOSS, Qwen and Krea Pixel Art

Open **http://127.0.0.1:7861/studio/**. `local-image-ai-service studio` starts the service and opens the interface.

The studio includes four base model families and two trained Anima Low Poly variants: **Anima Aesthetic 1.1** for anime and illustration, **MOSS SFT** for photography, general image ideas and low poly, and **Qwen Image 2.1 Uncensored GGUF** for detailed creative scenes, typography and transparent stickers. **Krea 2 Pixel Art** adds icons, sprites, isometric buildings and landscapes with 32/64/128-pixel adapters and native PNG exports. All run locally. The interface, presets, help and validation messages are in English. The service adds no content filters or automatic content tags.

See [trained Anima Low Poly styles](anima-lowpoly.md) for the six new retro/3D recipes, [Krea Pixel Art](krea-pixel-art.md) for the four new pixel recipes and setup, and [Qwen, new styles and the example explorer](qwen21-and-examples.md) for the original 34-recipe selection, source research and Qwen’s non-commercial research license.

## Guided mode

1. Choose an image recipe. The matching model is selected automatically.
2. Fill in **What would you like to create?** This is the only required field.
3. Optionally add a setting or action and extra details.
4. Choose **Recommended** for the final image or **Draft** for experiments.
5. Click **Generate image**.

**Use example** is the quickest starting point: load a complete example and change only the subject. When a recorded example exists, its quality profile and seed are restored too. Browse and inspect example images under **Explore**. The service adds style, lighting, camera, composition, image size and technical settings. **View full prompt and settings** shows the actual composed prompt, negative prompt and settings before generation.

Recipes are deterministic and versioned. No additional language model is used. Input is passed through in its original language; the English examples follow the official model prompting guides. The original fields and complete prompt are saved with the image and can be reused.

Choose an aspect ratio in guided mode: Recommended, 1:1, 16:9, 9:16, 4:3, 3:4, 3:2 or 2:3. Output shows the actual dimensions. See [the format table](qwen21-and-examples.md#aspect-ratios).

## Recipes

**Anima Aesthetic:** cinematic character portrait, wide anime film scene, fantasy hero, cyberpunk/neon night, landscape, cozy slice of life, manga, watercolor and chibi.

**MOSS photography:** natural portrait, candid everyday, street documentary, cinematic still, product studio, landscape and travel, architecture and interior, food and still life. Each recipe includes a complete example and a specific tip. See [photography settings, examples and research](moss-photography.md).

**MOSS Low Poly:** floating diorama, 1990s game scene and geometric landscape/game world. These recipes add visible polygon faces, flat shading, simple materials, clear silhouettes and suitable perspectives. They produce PNG images, not 3D models.

| Profile | Anima Aesthetic | MOSS |
| --- | --- | --- |
| Draft | 30 steps, reduced size where possible | Photography: 30 steps; Low Poly: 20 steps; reduced size where possible |
| Recommended | 35 steps, CFG 4.5, Euler | 50 steps, CFG 3, Euler, Shift 5 |
| More detail | 45 steps | 60 steps |

Depending on the recipe, the recommended size is 832×1216, 1216×832 or 1024×1024. Anima Aesthetic uses neither positive nor negative `score_*` tags. More steps do not guarantee a better composition. Sizes are verified on the local GPU; new large formats become available only after successful verification.

The guide is also available **inside the studio at `/studio/anima-guide/`**.

## Free prompt mode

**Free prompt · custom settings** exposes the style suffix, size, sampler, steps, CFG and negative prompt. Existing free prompt API and CLI requests still work. All three selected models are used for text-to-image generation here; reference and mask editing are unavailable with this selection.

A fixed seed helps compare results within the same model. Reusing a recipe image restores its original fields. Any historical images from other models remain viewable, but their removed model configurations cannot be loaded.

## Deleting images

In the image library, use **Delete** to remove an individual image, or select several images with the checkboxes. **Select all displayed** selects the images already loaded; **Clear selection** resets the checkboxes. **Delete selected** removes the entire selection after one confirmation. Select exactly two images to compare them.

Deletion removes the PNG, its library settings and the associated completed job. Related entries in local GPU test reports are also removed. Active jobs cannot be deleted as images. An invalid selection is rejected before anything is removed. If a file operation fails, deletion remains pending and is completed on the next service start. Deleted images stay removed after a reload or restart.

## Technical interfaces

- `GET /studio/api/catalog`: six model choices, example metadata, free prompt style presets and complete `recipes` with example values.
- `POST /studio/api/compose`: validate recipe inputs and return the complete settings without generating an image.
- `DELETE /studio/api/gallery/{id}`: permanently delete an individual image.
- `POST /studio/api/gallery/delete`: `{ "ids": ["...", "..."] }`, delete up to 500 images together; the entire selection is validated first.
- `POST /studio/api/jobs`: create a job from the same recipe inputs, or supply a free `prompt` and custom settings.

```json
{
  "model": "anima",
  "recipe": "anima-portrait",
  "subject": "an adult mage with red hair and a green cloak",
  "quality": "standard"
}
```

Optional: `scene`, `details`, `seed`, `aspect_ratio`; Qwen recipes also accept `text`. The `subject`, `scene` and `details` fields are limited to 2000 characters each. Custom `steps`, `size` or `prompt` values are not allowed in guided mode; use free prompt mode instead. `quality` is `preview`, `standard` or `detail`. The compiled prompt, original fields and recipe version are saved.

The existing `/v1/images/generations` endpoint remains a synchronous API call with an unchanged prompt. It uses no recipe and does not save automatically. Recipes are used only when an explicit `recipe` is supplied in studio requests.

## Data and model maintenance

Images, inputs, SQLite history and GPU reports remain under `~/.local/share/local-image-ai-service-images/studio/`. New images stay saved until you explicitly delete them. Each new file receives its own ID and does not overwrite another file.

The additional model installation contains Anima Aesthetic and Qwen Image 2.1 with their required components. With the service stopped, `scripts/prune-models.py` removes all other models from the configuration and deletes their unused weights only inside its own download directory. Shared external weights used by other programs are preserved. Files needed by MOSS, Anima, Qwen or Krea Pixel Art are retained.

```bash
npm ci --prefix studio
npm run build --prefix studio
local-image-ai-service stop
python3 scripts/prune-models.py
python3 scripts/install.py
local-image-ai-service start
```

For a new Anima installation, run `python3 scripts/install-models.py anima` with the service stopped. Pinned revisions and checksums are in `config/models.lock.json`. Runtime requirements: Python 3.11+, Pillow 12.3+ and the existing separate CUDA runtime; Astro/Node is needed only for the build.

## Sources and rights

- [Anima model card](https://huggingface.co/circlestone-labs/Anima): Aesthetic-specific tags, natural language, sampling and permitted commercial image use.
- [Official ComfyUI guide](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/anima/anima.mdx): architecture and workflow; some examples refer to Anima Base rather than Aesthetic.
- [MOSS user guide](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md): image descriptions and sampling. MOSS uses Apache 2.0.
- [Low-poly scenes by a Blender artist](https://github.com/emrelab/blender-projects): diorama, architecture and small game world examples as style inspiration. No assets are downloaded or included.

The built-in image recipes are custom, editable recipes. They are not official presets or additional LoRAs. Anima permits commercially used generated images, but requires a separate license for paid model hosting. Model licenses do not replace rights relating to depicted trademarks or characters.

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 scripts/verify-recipes.py  # real GPU; the service must be stopped
npx --prefix studio playwright test --config studio/playwright.config.js
```

`verify-recipes.py` generates examples of every recipe in the draft profile and one large landscape image each with Anima and MOSS. Its report is saved alongside the images in `recipe-report.json`. See the [current recipe checks](recipes-test-report.md). [Earlier GPU measurements](studio-test-report.md) remain available as a historical comparison.

## Cleanup on October 31, 2026

17 current recipe images and newer custom results were retained. 100 older test/comparison images, eight unused reference uploads and six stale jobs were removed. The cleanup affected only the studio library.

Deletion verification: 54 Python tests passed, the Astro build succeeded and Semgrep reported no findings. Two Firefox tests covered the existing interface and the full deletion flow: cancel, delete one image from the detail view, compare two images, select more than two, clear the selection, delete all displayed images and reload. Only temporary test copies were used; all 17 retained images remained intact.
