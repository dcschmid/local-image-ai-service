# MOSS photography verification — October 31, 2026

Eight new photography recipes were exercised on the installed **MOSS SFT** model. All eight draft runs and two recommended-size runs completed successfully. All ten output PNGs were opened and visually reviewed.

## Environment

- NVIDIA RTX 5070 Laptop, 8 GB VRAM; CPU offloading, flash attention and VAE tiling.
- MOSS SFT Q4_K diffusion weights, Qwen3.5-9B Q4_K_M text encoder and the existing FLUX.2 VAE.
- Runtime revision: `a77d3623180b2bc1886f3dd04c0aa04156a987ef`.
- Euler, discrete scheduler, CFG 3, flow shift 5, seed 42. These recipes do not enable SLG or adapters.
- Draft: 30 steps at a reduced size. Recommended: 50 steps at roughly one megapixel.

## Measured GPU runs

| Recipe | Profile | Size | Steps | Time |
| --- | --- | --- | ---: | ---: |
| photo-portrait | preview | 576x832 | 30 | 47.05 s |
| photo-candid | preview | 768x768 | 30 | 55.54 s |
| photo-street | preview | 832x576 | 30 | 42.20 s |
| photo-cinema | preview | 832x576 | 30 | 42.28 s |
| photo-product | preview | 768x768 | 30 | 54.59 s |
| photo-landscape | preview | 832x576 | 30 | 42.20 s |
| photo-interior | preview | 832x576 | 30 | 42.27 s |
| photo-food | preview | 768x768 | 30 | 54.73 s |
| photo-portrait | standard | 832x1216 | 50 | 176.97 s |
| photo-landscape | standard | 1216x832 | 50 | 177.63 s |

These measurements apply to this computer and these example prompts. They are not a comparison at identical size/step count, a benchmark across seeds or a guarantee for arbitrary subjects. The 60-step profile was validated through compilation tests; it was not included in these GPU runs.

## Visual findings

Natural portrait produced a single photographic portrait with visible skin texture and soft window lighting in both profiles. Candid everyday produced an informal seated subject with a mug. Street documentary retained its mechanic, bicycle and workshop setting; some small bicycle geometry remains imperfect in the draft. The cinematic example produced a single railway-platform frame with practical lamps and cool ambient light.

Product studio produced a coherent ceramic mug with a contact shadow and material highlights. The landscape examples retained the lighthouse, coastline and atmospheric depth. The interior example showed the requested reading room, side windows, oak shelving and fabric texture. Food and still life retained the toast, burrata, tomatoes and plate with visible food texture. These are observations of the fixed example seed, not a quality score.

## Application checks

- 56 Python tests passed, including photographic negative prompts, quality profiles, default settings and the existing persistence/deletion checks.
- The previous twelve Anima/Low Poly recipes produced exactly the same compiled settings as the installed prior version at all three quality levels (36 comparisons).
- Astro production build passed; Semgrep reported zero findings and zero errors.
- Two Firefox tests passed against the installed service: all 20 recipes, three recipe groups, automatic model selection, MOSS's default photography recipe, examples, photo-specific tips, prompt previews, profile changes, free prompt mode, guide, mobile width and removed-model validation.
- All 17 original gallery PNGs retain their SHA-256 hashes. The gallery still has 17 image records and 17 job records, with no uploads or pending deletions.

## Artifacts and replay

The full requests, original inputs, seeds and image IDs are in `~/.cache/local-image-ai-service/moss-photography-20261031/photo-report.json`. PNGs and an isolated SQLite history sit alongside it. No QA images were added to the user's gallery. Successful dimensions were added to the existing fingerprint-bound verification receipt so the studio can use the portrait format normally.

To replay an example through the studio API, take `request.recipe_inputs` from its report row and add `model: "moss"` and `seed: 42`, then submit it to `POST /studio/api/jobs`. A replay intentionally creates a new gallery image.

See [photography presets and source research](moss-photography.md) for upstream evidence, examples and guidance.
