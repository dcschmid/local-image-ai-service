# Historical studio verification — October 30, 2026

The seven-model comparison below predates the reduction to Anima Aesthetic and MOSS. Current guided recipes are documented in [the studio guide](studio.md); new GPU examples and timings are recorded in `recipe-report.json` alongside the local images.

Implemented and installed locally on Fedora 44, RTX 5070 Laptop (8151 MiB), with the existing pinned stable-diffusion.cpp `a77d362` CUDA runtime.

## Automated checks

- 42 Python tests passed: validation, lifecycle, legacy CLI/API, migration, bounded capacity, studio origin/authentication, uploads, masks, persistence, cancellation, favorites and pagination.
- Astro production build passed.
- Installed systemd service integration passed: actual MOSS output/seed, concurrent-request 429, unloaded-model 409, checksums, readiness, clean restart, bounded stop during inference, and no remaining owned GPU process or listener after stop. Login autostart remains disabled.
- **3 Firefox tests passed against the installed service:** presets, archive reuse, comparison, mobile layout, real saved generation, queued cancellation, and active GPU cancellation followed by successful next-job execution. No browser page errors were observed in the UI regression test.
- Semgrep Python/JavaScript rules: no findings or scan errors.

## GPU model checks

All listed models successfully generated 512×512, 1024×1024 and 832×1216 PNGs. Larger sizes are enabled only for the matching local runtime/component fingerprints.

| Model | 1024×1024 time | Sampled total GPU memory | Other verified modes |
| --- | ---: | ---: | --- |
| moss | 183.76 s | 4239 MiB | — |
| z-turbo | 18.17 s | 4719 MiB | — |
| z-base | 100.41 s | 4705 MiB | — |
| klein | 8.01 s | 3775 MiB | reference |
| animagine | 25.30 s | 5863 MiB | img2img, inpaint |
| anima | 59.68 s | 4565 MiB | — |
| anima-turbo | 11.69 s | 4565 MiB | — |

Each model uses its documented default steps and CFG, so these timings are **not** equal-settings quality comparisons. They include generation, decode and polling; model-loading time is excluded. VRAM samples include desktop use and are observations, not hard limits. Downloads and other lightweight checks overlapped some runs.

FLUX klein uses the publisher-declared uncensored text encoder; the diffusion weights are unchanged. Tests used non-explicit prompts and do not establish universal uncensored behavior. Anima/Animagine content-rating tags are available without a service-added prefix or negative prompt.

A pixel comparison of the real GPU inpainting output found zero RGB difference outside the selected mask and nonzero change inside it.

Native PNG metadata separately confirmed that the legacy CLI request used its exact prompt, seed 42 and a per-request 10-step override. The image remained in the ordinary CLI output directory.

## Controlled comparison

All **54 comparison generations completed successfully** (18 per model). There were **78 successful GPU checks in total**, including model resolution and editing checks.

The final comparison uses six fixed motifs (photograph, studio portrait, western comic, line art, anime character, anime background), seeds 42/1234/2026 and 768×768. Z-Image Turbo, FLUX klein and Anima Turbo each use their documented few-step defaults. This explores stylistic suitability and seed variation; it is not a universal ranking. The original MOSS guide also retains its controlled 20/50-step comparison.

Source prompts, exact settings, PNGs and machine-readable timings are retained under `~/.local/share/local-image-ai-service-images/studio/`. `gpu-report.json` and `verification.json` contain the measured evidence. The studio archive allows full-resolution visual comparisons. No automatic anatomy or aesthetics gate was added.

Qwen 2512 is an optional pinned download, not locally benchmarked. Qwen 2.1 and NoobAI 1.1 were excluded from the installed selection due to the commercial-use restrictions described in the [studio guide](studio.md).
