# Qwen, recipe explorer and aspect ratios — October 31, 2026

## Delivered

- Three configured models: Anima Aesthetic, MOSS SFT and Qwen Image 2.1 Uncensored GGUF.
- 34 guided recipes: 13 Anima, 15 MOSS and 6 Qwen, each with a real locally generated example.
- Searchable example browser, model filters, image inspection and reproducible input/profile/seed reuse.
- Exact optional visible wording for Qwen recipes and a transparent sticker example.
- Recommended recipe format plus 1:1, 16:9, 9:16, 4:3, 3:4, 3:2 and 2:3 in guided mode. The same ratios have explicit pixel presets in free prompt mode.
- All original 17 gallery PNGs retain their SHA-256 hashes; the archive still contains 17 image and 17 job records, with no uploads or pending deletions.

## Model provenance and settings

Qwen uses the pinned supplier Q4_K_M diffusion file, official Qwen3-VL-8B Q4_K_M encoder and dedicated Qwen Image 2.1 VAE. All three downloads passed their manifest SHA-256 checks. The existing pinned CUDA runtime was retained.

Qwen uses Euler, CFG 6 and the resolution-dependent Flux schedule. It does not inherit MOSS's Shift 5. The model selector names the supplier's uncensored designation and links the non-commercial Qwen Research License; no unrestricted-commercial-use claim is made.

## Example generation

20 new native example runs completed successfully in the isolated cache. Five initial images were refined after visual review: unwanted small lettering in poster/cover/comic examples, an overly obscured action pose, and a full-size isometric world check. The final selection combines 19 matching previous outputs with 15 selected new outputs. All 34 exported examples were checked against the current compiled prompts and settings. The overview and newly generated examples were visually reviewed.

The following Qwen examples are shipped with their actual recorded profiles:

| Recipe | Profile | Size | Steps | Time |
| --- | --- | --- | ---: | ---: |
| qwen-poster | standard | 832x1216 | 40 | 176.48 s |
| qwen-sticker | standard | 1024x1024 | 40 | 177.55 s |
| qwen-portrait | preview | 576x832 | 20 | 36.75 s |
| qwen-product | preview | 768x768 | 20 | 47.60 s |
| qwen-cover | preview | 576x832 | 20 | 36.65 s |
| qwen-world | standard | 1216x832 | 40 | 168.97 s |

The transparent sticker PNG has an alpha range of 0–255 and roughly 68% non-opaque area. The WebP example preserves meaningful transparency. Nearly opaque alpha values in ordinary Qwen images do not trigger the transparent-background label. The final poster renders EXPLORE, the cover WORLDS BELOW and the product label SOL; generated wording still needs inspection for other prompts.

The new example images and jobs are stored under `~/.cache/local-image-ai-service/recipe-examples-20261031/`. Exported assets and the provenance manifest are under `studio/public/recipe-examples/`. They are separate from the user's gallery. Rebuild with `python3 scripts/build-examples.py`; changed prompts invalidate old matches.

## Format verification

30 new two-step GPU checks completed, ten previously unverified dimensions per model. Together with previously verified matching outputs, every standard and draft dimension in the seven aspect-ratio presets is covered for all three models. These runs check native execution, PNG decoding, dimensions and memory fit; two-step images are not quality examples. The example library provides the longer quality runs.

Verification receipts are bound to the exact runtime and component-file fingerprint. Large formats are added only after valid native PNG outputs are observed. Ratio choice is stored in recipe inputs and restored on image reuse. “Use this example” restores the example's own format instead of carrying an unrelated prior selection forward.

Reproduce missing size checks with `python3 scripts/verify-formats.py` while the service is stopped. Outputs remain in the isolated `format-checks-20261031` cache, outside the gallery.

## Automated checks

- **62 Python tests passed**, covering literal text validation, blocked runtime-control tags, independent Qwen scheduling, preserved PNG alpha, example reuse restrictions, exact ratios and request budgets, plus existing API, persistence and deletion behavior.
- Astro production build passed. Example images total about 2.9 MB; only a small set of cards is shown initially and previews load lazily.
- Semgrep: zero findings and zero scan errors.
- **Four Firefox tests passed** against the installed service: all 34 assets were fetched and checked as WebP, browser filters, image previews, transparent examples, seed/profile reuse, explicit Qwen wording, switching to Anima/MOSS, 1:1/16:9/2:3 selection, mobile width, the guide, legacy-model rejection and safe single/bulk deletion using disposable fixtures.
- The original twenty recipes were compared with the previous implementation at all three profiles: 60 unchanged compiled requests. The new explicit ratio control is opt-in; Recommended retains those original sizes.
- Service ready after installation, with Anima active. No new autostart behavior was enabled.

See [research, licensing, new recipes and format table](qwen21-and-examples.md).
