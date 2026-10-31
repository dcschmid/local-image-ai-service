# Blender reference checks — 2026-10-31

Historical report: the Anima low-poly profiles have since been retired. See [the current MOSS Low Poly workflow](moss-lowpoly.md). Measurements below describe the earlier installation.

Environment: RTX 5070 Laptop 8 GB, existing pinned CUDA runtime
`a77d3623180b2bc1886f3dd04c0aa04156a987ef`. Model weights and curated Anima adapter
strengths remain unchanged. Modeling composition version: 1.

## Automated checks

- 82 Python tests passed; the six modeling-specific tests were also rerun after
  refining the axis-view instructions. These cover all permitted asset/view
  combinations, size limits, aspect-ratio overrides, malformed/inapplicable
  settings, runtime-control rejection and original-input persistence.
- All 132 pre-existing recipe/quality combinations compiled identically to the
  captured baseline. All 44 bundled examples still match their recorded prompts
  and settings. The public kart reference matches its current starter inputs.
- Astro built all four static pages.
- Four Firefox scenarios passed against an isolated HTTP service and temporary
  archive. They covered existing low-poly examples, guided/free workflows,
  reference defaults, character/kart starters, requested views, size previews,
  restoration of saved asset/view settings and the guide links.
- Semgrep scanned 25 source files with zero findings and zero errors.
- `git diff --check` passed.

## Real GPU output

All five generations used recommended quality and seed 42. PNG decoding, requested
dimensions, saved inputs and modeling-version metadata passed validation.

| Model / composition | Size | Sampling | Seconds | Visual observation |
| --- | --- | --- | ---: | --- |
| Anima PSX · kart, three-quarter | 1216 × 832 | 35 Euler, CFG 4.5 | 76.62 | Complete orange kart, simple body panels, exposed wheels and a dark seat on a plain background. Useful main volumes for a blockout. Hidden geometry remains ambiguous. |
| Anima Low Poly Style · character, front | 832 × 1216 | 35 Euler, CFG 4.5 | 74.43 | Complete standing character, separated hands and feet, clear clothing masses. The face is very simplified and the requested single pouch became two. |
| Anima Low Poly Style · character, initial side request | 832 × 1216 | 35 Euler, CFG 4.5 | 71.19 | Produced a three-quarter pose. Jacket/pocket details differed from the front concept. The requested projection was not achieved. |
| MOSS · chest, three-quarter | 1024 × 1024 | 50 Euler, CFG 3, shift 5 | 193.49 | Complete closed chest with visible major volumes, thick bands, a latch and restrained materials. Broad shapes are easy to identify; some details remain inferred. |
| Anima Low Poly Style · character, strengthened side request | 832 × 1216 | 35 Euler, CFG 4.5 | 74.63 | Stronger head profile, but the torso remained partly rotated and costume/pose details drifted. This is still an independent concept, not an aligned side blueprint. |

The final side/back/top prompts put directional tags first and exclude competing
camera angles. Back and top outputs were validated at the request level, without
additional visual GPU samples. Building and environment options were likewise
covered by compilation/validation rather than a visual quality claim.

These checks establish working generation and readable reference compositions.
They do not establish cross-view geometric consistency. No Blender mesh was
reconstructed or measured during this change. The documented workflow uses one
approved master, a shared Blender blockout and orthographic renders of that mesh
for consistent front/side/back/top sheets.

## UI and data checks

Desktop and 390-pixel mobile screenshots were inspected for the new fields and
guide. New controls use native selects/buttons, associated labels and a named
fieldset. Keyboard Tab moved from the view select to the asset select with a
visible focus indicator; the tested mobile layouts had no horizontal overflow.
This is scoped UI verification, not a full WCAG audit or screen-reader review.
Local screenshots are under `studio/test-results/modeling-*.png`.

GPU images and job metadata live in isolated cache archives:

- `~/.cache/local-image-ai-service/blender-reference-92ltt2v9/`
- `~/.cache/local-image-ai-service/blender-reference-g528ik26/`

The generic kart concept was exported separately to the public guide with its
recorded settings. User-supplied Jax reference images were not copied into the
repository or public example library.

After installation and restart, all 40 original archive records matched their
captured JSON exactly, and all 21 original PNG filenames and SHA-256 hashes matched.
The live catalog exposed 44 recipes, five asset types, five requested reference
views and concept mode. Installed Python modules and built pages matched the
workspace. The service returned ready/idle with the previously selected
`anima-lowpoly` model; login autostart was not enabled.
