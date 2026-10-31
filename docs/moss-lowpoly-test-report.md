# MOSS Low Poly migration checks — 2026-10-31

The service now retains four profiles: MOSS, Anima Aesthetic, Qwen 2.1 and Krea
Pixel Art. The two Anima low-poly profiles and their six recipes are removed.
Four MOSS asset-reference recipes replace those workflows, giving 42 recipes in
total and seven MOSS Low Poly choices at that migration stage. The subsequent
general/track addition below brings the current catalog to 44 recipes and nine
MOSS Low Poly choices.

## Verification

- 98 Python tests passed, including removal/rejection of retired profile IDs,
  export of historical images, safe pruning of unreferenced owned weights,
  MOSS reference composition and CLI/queue/export behavior.
- All 38 retained recipes compiled identically across their three quality
  profiles: 114 unchanged combinations.
- All 42 bundled example records matched their current compiled prompts,
  dimensions, steps, CFG and sampler. Modeling-reference tests were rerun after
  the four new real examples were exported.
- Astro built the four static pages.
- Seven Firefox scenarios passed: example browsing, all MOSS low-poly presets,
  Blender controls/starters, reference reuse, pixel art, guided/free mode and
  retained access to historical images. These checks created no GPU jobs in the
  user's archive. Desktop/mobile screenshots of the updated controls and guide
  were inspected; the tested mobile layouts had no horizontal overflow.
- Semgrep scanned 25 source files with zero findings and zero errors.
- The installed CLI catalog exposed exactly four profiles and 42 recipes, and
  composed all four MOSS asset examples successfully.
- `git diff --check` passed.

## Actual MOSS examples

All four examples use Draft: 30 Euler steps, CFG 3, flow shift 5 and seed 42.
They were generated in the separate example cache, inspected, and exported to
the public example library. Recommended keeps the existing 50-step defaults and
larger canvas; this table measures the new Draft examples.

| Recipe | Dimensions | Seconds | Observation |
| --- | --- | ---: | --- |
| `lowpoly-character` | 576 × 832 | 49.00 | Complete figure, readable face, simple jacket/trousers/boots, one belt pouch and separated arms in a neutral pose. |
| `lowpoly-vehicle` | 832 × 576 | 44.39 | Orange/blue kart with large panels, a simple seat, visible frame and wheel attachments. Occluded geometry remains a modeling decision. |
| `lowpoly-prop` | 768 × 768 | 56.84 | A complete chest with broad wood/metal color regions and a clear latch. The generated lid is curved despite the flat-lid wording. |
| `lowpoly-building` | 768 × 768 | 57.77 | A simple cream workshop with a terracotta roof and clear door/window volumes. Roof and opening placement remain an interpretation of the brief. |

The images are useful design references, without establishing exact projections
or matched cross-view geometry. The shared Blender-blockout workflow remains the
documented path to consistent front/side/back/top sheets. The kart guide image
and its recorded-settings JSON now contain the actual MOSS result.

## Removal and preservation

Pruning removed three unreferenced service-owned safetensors files: the two
downloaded adapter copies and the derived text-encoder-compatible copy. This
freed **580,574,248 bytes**, plus the small conversion receipt. The installer also
removed retired adapter code/bytecode and the six obsolete public examples.
The model lockfile and installers no longer offer the retired profiles.

After installation and restart:

- All 42 original gallery records matched their captured JSON exactly.
- All 22 original PNG filenames and SHA-256 hashes matched.
- Original Downloads files matched their captured hashes.
- Every retained model component remained present at its original path.
- Configuration changed only by dropping the two profiles and selecting MOSS.
- The service was ready and idle with MOSS loaded. Login autostart was unchanged.

Generation artifacts remain under
`~/.cache/local-image-ai-service/recipe-examples-20261031/`. The private archive
was not used for the new example generations. Historical images from removed
profiles remain viewable/exportable; their generation settings cannot reload
the retired models.

## General motifs and track overview follow-up

`lowpoly-anything` adds an unrestricted motif/camera composition;
`lowpoly-track-overview` requests an entire closed circuit from overhead. Both
use MOSS, with Draft at 30 Euler steps, CFG 3 and flow shift 5. Recommended remains
50 steps and More detail 60. All 126 previous recipe/quality combinations were
unchanged after adding the two definitions.

| Recipe | Draft dimensions | Seed | Seconds | Visual observation |
| --- | --- | ---: | ---: | --- |
| `lowpoly-anything` | 768 × 768 | 42 | 60.11 | An angular orange fox in a wooded pond scene, with a readable subject and broad color regions. |
| `lowpoly-track-overview` | 832 × 576 | 42 | 44.27 | A complete overhead closed circuit with clear boundaries and sparse surroundings. The loop became oval/rounded-rectangular rather than the requested kidney shape. |

Both real examples were exported to the public library and added to the guide.
The circuit is a concept image: a route spline, exact geometry and driveability
were not validated. The guide explains this distinction.

99 Python tests and eight Firefox scenarios passed. The latter covered both new
presets, free motif entry, hidden asset-type controls, the overhead composition,
aspect/quality controls and the existing Studio workflows. Astro built all four
pages; Semgrep reported zero findings/errors. The installed CLI composed both
recipes successfully. All 44 example records matched their current compiled
requests. The original 42 gallery records, 22 PNG hashes and private configuration
were unchanged; example generations stayed in the separate cache.
