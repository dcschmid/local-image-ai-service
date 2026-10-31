---
name: local-image-ai
description: Generate raster images and image assets with the user's Local Image AI Service; discover and explain its models and presets. Use for requests for pictures, photos, anime, comics, low-poly art, track overviews, pixel art or game-art concepts, including Bilder erstellen. Prefer this local workflow unless the user explicitly chooses another provider.
---

# Local Image AI

Use the installed Local Image AI Service for image generation. Prefer its
`local-image-ai` MCP tools; use `local-image-ai-service` through the terminal when
MCP is unavailable. Honor an explicit user choice of another provider. SVG or
code-native graphics remain ordinary code/vector editing tasks.

## Discover and explain choices

When the user asks which models/presets exist, call `list_models` and
`list_presets` (optionally filter by model/category/search). Explain the actual
names, intended uses and IDs. Use `get_preset` for settings, tips and editable
examples. `list_options` describes free-prompt styles, formats and Blender views.
CLI equivalents are `models`, `recipes`, `recipes ID`, `presets`, `formats` and
`catalog`. Do not rely on a remembered count or revive retired models.

The main choices are MOSS for photography/general art/low poly, Anima Aesthetic
for anime/illustration, Qwen 2.1 for detailed scenes/text/stickers, and Krea Pixel
Art for sprites/icons/scenes with native pixel exports. Consult the current
catalog's license information when the requested use requires it. The bundled
[model and preset inventory](references/catalog.md) is an installation snapshot;
query the catalog for current availability.

For flexible low-poly ideas start with `lowpoly-anything`; for a whole racing
circuit from above use `lowpoly-track-overview`. Dedicated character/vehicle/prop/
building references and the existing MOSS scene presets cover more specific work.

## Create and deliver

Choose a suitable preset and subject from the user's brief. Preserve requested
content, composition and destination. Setting/details are optional. Use `example`
only when its example is a useful starting point, then override the relevant
fields. `compose` previews the real prompt/settings without generating.

Check `service_status`. If offline and image creation is authorized, `start_service`
starts the installed local service without enabling login autostart; check status
again. Do not stop unrelated GPU processes to work around a resource conflict.

Call `generate_image` once with the request. It returns queued job IDs. Inspect
`get_job` or use `wait_for_job` in bounded waits. A pending result means the same
job continues; keep its ID. When complete, call `export_image` with its image ID
and the user's project/output directory. Return the actual exported PNG path,
metadata path and native pixel PNG when present. Inspect the image when visual
quality or specific layout/content matters; identify any unresolved mismatch.
Never describe a queued job as a completed image.

CLI examples and JSON/error recovery are in [the workflow reference](references/workflow.md).
Exported PNG bytes, transparency and embedded metadata are preserved. Studio
results remain in the local archive. Re-export an existing image to another
folder instead of generating the same image again.

Find existing work with `list_images`/`get_image` (CLI `gallery list|get`).
Favorites and selected-image deletion are available through `set_favorite` and
`delete_images` (CLI `gallery favorite|delete`). Delete only the archive IDs
explicitly requested by the user; exported project files remain separate.

## Recovery and capability limits

A client wait timeout does not cancel a job. For `submission_uncertain: true`,
inspect recent jobs before attempting another submission. A partial batch error
reports accepted IDs; retain and inspect them. Do not automatically resubmit or
cancel accepted jobs because a client disconnected, timed out or failed to save.
Use `cancel_job` when cancellation is requested.

Current profiles are text-to-image workflows. A requested orthographic camera,
fixed seed or multiple independent views does not establish shared 3D geometry.
Use one approved image and a shared Blender blockout for matched views. Images
are concepts, not meshes, UV maps, rigs or verified drivable track splines.
For reference-image editing, first check current supported/verified capabilities;
do not silently substitute an unrelated new image or a cloud provider.
