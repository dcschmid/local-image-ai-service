# Find your way around Atelier

If you just want to make an image, open the Studio and choose an example. You can leave the sampler, step count and prompt formatting to the preset while you get a feel for the models.

[Open the Studio](http://127.0.0.1:7861/studio/) · [See example images](examples.md) · [Back to the project](../README.md)

## Start here

| Your next step | Guide |
| --- | --- |
| Set up the service for the first time | [Installation](installation.md) |
| Make your first image and find it again | [A tour of the Studio](studio.md) |
| Pick a look from real outputs | [Example gallery with commands and settings](examples.md) |
| Describe an idea more clearly | [Prompting and quality](quality.md) |
| Let Codex, Claude Code or OMP create assets | [Agent setup, MCP and the portable skill](agents-integration.md) |
| Generate from a script or terminal | [JSON CLI workflow](agent-cli.md) |
| Find out why something failed | [Troubleshooting](troubleshooting.md) |

## Models and looks

**Start with the kind of picture you want.** MOSS covers photography, low poly and several illustration styles. Anima is the anime/illustration specialist. Qwen adds detailed scenes and lettering. Krea prepares small pixel grids and native exports. Z-Image adds varied painted worlds and photography; Turbo offers eight-step photo and product studies.

| What you have in mind | Read next |
| --- | --- |
| People, products, food, interiors or natural landscapes | [MOSS photography](moss-photography.md) |
| Anime, manga, watercolor, mecha or storybook art | [Anima and the Studio workflow](studio.md#choose-a-look) |
| Animals, props, buildings, a kart or a whole track in low poly | [MOSS Low Poly](moss-lowpoly.md) |
| Matching Low Poly, Pixel and Voxel views from one model | [3D Asset Views](asset-views.md) |
| A modeler-friendly concept to build in Blender | [Blender references](blender-references.md) |
| A poster, cover, sticker or short text in the image | [Qwen and the example explorer](qwen21-and-examples.md) |
| Icons, sprites, isometric buildings or pixel landscapes | [Krea Pixel Art](krea-pixel-art.md) |
| Fast photo studies, ink wash or imaginative painted worlds | [Z-Image and the expanded presets](z-image-and-presets.md) |
| Every available preset and its ID | [Complete catalog](../skills/local-image-ai/references/catalog.md) |

The model selector links to each model's license. Qwen's configured profile uses a non-commercial research/evaluation license; Anima and Krea also have model-specific terms. The catalog keeps these differences visible.

## Connect and maintain

- [HTTP API](api.md) — requests, response formats and errors.
- [Configuration](configuration.md) — local paths, model settings and authentication.
- [systemd](systemd.md) — the user service and resource limits.
- [Open WebUI](open-webui.md) — connect a separate interface.
- [Architecture](architecture.md) — how the frontend, queue, archive and runtime fit together.
- [Runtime inspection](inspection.md) — why this build and integration were chosen.
- [Screenshots](screenshots.md) — recreate the documentation images without opening a private gallery.

## Verification and history

These reports describe checks that were actually run. Older reports may mention profiles that have since been retired; use the current catalog and guides when creating new images.

| Area | Report |
| --- | --- |
| Asset concepts, real GLB views, pixel/voxel exports | [CPU, GPU, browser and installed-service verification](asset-views-test-report.md) |
| Z-Image, Turbo, all 70 examples and the expanded catalog | [Research, GPU measurements and integration checks](z-image-and-presets.md#verification-results) |
| CLI, MCP, skill installation and all three agent clients | [Agent integration](agent-integration-test-report.md) |
| Current MOSS low-poly presets and migration | [MOSS Low Poly](moss-lowpoly-test-report.md) |
| Blender reference experiments and camera limitations | [Blender references](blender-reference-test-report.md) |
| MOSS photography | [Photography checks](moss-photography-test-report.md) |
| Qwen and its examples | [Qwen checks](qwen21-test-report.md) |
| Pixel processing and prepared adapters | [Krea checks](krea-pixel-test-report.md) |
| Original guided recipes | [Recipe checks](recipes-test-report.md) |
| Earlier Studio, CLI and runtime measurements | [Studio](studio-test-report.md) · [CLI](agent-cli-test-report.md) · [Runtime](test-report.md) |
| Retired Anima low-poly profiles | [Historical report](anima-lowpoly-test-report.md) |
