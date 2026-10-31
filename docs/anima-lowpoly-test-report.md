# Anima Low Poly validation — October 31, 2026

Historical report: the Anima low-poly profiles have since been retired. See [the current MOSS Low Poly workflow](moss-lowpoly.md). Measurements below describe the earlier installation.

Both user-selected Anima adapters are installed as curated model choices, sharing the existing Anima Aesthetic 1.1 diffusion model, Qwen3 0.6B encoder and Qwen Image VAE. The installed studio has six choices, 44 recipes and 44 real examples. The previous 38 recipes compile identically across all three existing quality profiles.

## Weight and loader checks

- The user-supplied PSX Preview2 file matches SHA-256 `3f0fc4a628262a85728426e0f0d14c882c2a36e46d2798b555fb95ae5f00dd03`.
- Low Poly Style matches SHA-256 `ec50a198575a8ac3ffb51fb0ab91b6e3ac4d98b28f872ec6a88e15c9451263c7`.
- Original Downloads files remain unchanged. Service-owned adapter copies were verified before configuration changed.
- PSX: the native loader applies 840/840 tensors.
- Low Poly Style: the original names caused the native loader to ignore all 588 encoder entries. The compatibility copy renames those entries into explicit Qwen module paths while preserving every numerical payload byte. The final runtime applies 588/588 encoder and 840/840 diffusion entries.
- Both Studio and compatibility API requests apply a fixed curated adapter with a relative basename. Arbitrary adapter path/strength fields remain rejected by the public API.
- The CUDA runtime stays at pinned revision `a77d3623180b2bc1886f3dd04c0aa04156a987ef`.

## Final GPU examples

RTX 5070 Laptop with 7,799 MiB VRAM, CUDA backend, CPU offload and flash attention. All final examples use 35 Euler steps, CFG 4.5 and seed 42. The character recipes use explicit framing and discourage duplicate figures; no universal subject-quality guarantee is implied.

| Recipe | Variant | Canvas | LoRA strength | Generation and save |
| --- | --- | --- | --- | --- |
| psx-character | anima-psx | 832x1216 | 0.9 | 76.54 s |
| psx-world | anima-psx | 1216x832 | 0.9 | 73.99 s |
| psx-prop | anima-psx | 1024x1024 | 0.9 | 76.82 s |
| anima3d-character | anima-lowpoly | 832x1216 | 0.75 | 74.41 s |
| anima3d-diorama | anima-lowpoly | 1024x1024 | 0.75 | 74.11 s |
| anima3d-landscape | anima-lowpoly | 1216x832 | 0.75 | 71.39 s |

All 44 example records were recompiled from their recorded inputs and matched their current prompt, negative prompt, size, steps, CFG and sampler. Cache reuse rejects Low Poly Style images from the earlier incomplete encoder mapping.

Each new variant has all seven standard aspect-ratio sizes verified at exact dimensions: 1024×1024, 1024×576, 576×1024, 1024×768, 768×1024, 1152×768 and 768×1152. The square size has full-quality example generations; the other six sizes have two-step dimension checks per variant. Full examples also cover the automatic 832×1216 and 1216×832 recipe formats. Two-step checks establish execution/dimension support, not final visual quality.

An isolated HTTP archive exercised queued switches from Anima to PSX and Low Poly Style, generated both styles, fetched PNGs and verified stored strengths/revision, deleted the test images, and exercised `/v1/images/generations` with Low Poly Style. Its gallery ended empty. GPU QA artifacts stay outside the user's archive.

## Automated and browser checks

- 76 Python tests passed, including payload/metadata checks, compatibility requests, path confinement, exact payload preservation during key conversion, local download import, refusal of wrong checksums, cache-revision handling and pruning protection for both variants.
- Six Firefox scenarios passed: deletion/selection/comparison; all-model example exploration; the two trained styles and guide links; Krea pixel controls/downloads; existing guided/free workflows and mobile layout; removed-model handling.
- New guide links restore the actual example subject, setting, details, quality and seed. Both style choices remain usable in free prompt mode; pixel-cleanup controls stay hidden for them.
- Desktop and 390px mobile screenshots inspected. Images fit their cards, labels and long license text wrap, links/fields are reachable by keyboard, and the focused setting field has a visible focus ring. Existing native selects/dialogs retain their standard keyboard behavior. This is scoped UI verification, not a formal WCAG audit.
- Accessibility considerations: existing combobox labels/names (1.3.1, 3.3.2, 4.1.2), keyboard/focus behavior (2.1.1, 2.4.3, 2.4.7), and meaningful recipe-link context (2.4.4). No remaining visual checks for the added guide/choices.
- Astro build passed for four static pages.
- Semgrep ran 219 rules on 23 source files: zero findings and zero errors. `git diff --check` passed.

## Installed state and integrity

The service is ready at http://127.0.0.1:7861/studio/, with the user's prior `krea-pixel` selection restored. All six choices are installed. Installed source files and six new example assets match the workspace. Existing model choices remain available, and autostart was not enabled.

The complete pre-change archive inventory matches exactly: 19 image rows, 19 job rows and 20 PNG files (including native pixel exports), with matching SHA-256 values and unchanged stored records. Original Downloads files also retain their pinned hashes.

See [versions, sources, setup and limitations](anima-lowpoly.md).
