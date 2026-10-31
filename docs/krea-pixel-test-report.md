# Krea Pixel Art validation — October 31, 2026

The installed application contains four models, 38 guided recipes and 38 generated examples. MOSS, Anima Aesthetic and Qwen remain available. The 34 previous recipes compile identically for every existing quality profile.

## Automated checks

- 69 Python tests passed, including DoRA row normalization, grid/palette cleanup, PNG metadata, strict settings, variant selection and authenticated deletion of both files.
- Five Firefox scenarios passed: existing guided/free workflows, example exploration, pixel controls/native downloads, deletion/selection/comparison, and removed-model handling. The deletion test initially exposed an in-flight route response during teardown; it now waits for route completion and passed on a targeted rerun.
- Desktop and 390px mobile screenshots inspected. Pixel examples fit the guide cards; pixel controls have visible labels, keyboard operation and a visible focus ring. Dialog Escape restores focus to its opening button. This covers the new controls, not a formal whole-site WCAG audit.
- Accessibility criteria considered: combobox 1.3.1, 2.1.1, 2.4.3, 2.4.7, 2.5.8, 3.2.2, 3.3.2, 4.1.2; download links 2.4.4 and standard keyboard operation. No project-specific judgment overrides. No remaining visual checks for the new controls.
- Astro static build passed: studio, existing guide and pixel guide.
- Semgrep: 219 rules, 21 source files, zero findings and zero errors. Shell setup syntax checked with `bash -n`.

## GPU checks

RTX 5070 Laptop, 7,799 MiB reported VRAM; original pinned CUDA runtime a77d3623180b2bc1886f3dd04c0aa04156a987ef. Krea 2 Turbo Q3_K_M with each complete DoRA variant prepared into a private GGUF. Each conversion consumed 360/360 tensors; source/output hashes are recorded in the private conversion receipt.

Every final example uses 1024 × 1024, eight Euler steps, CFG 1, fixed-mu 1.15 Flux schedule and seed 42. Palette cleanup produces RGB native PNGs and nearest-neighbor previews. Example WebPs are lossless.

| Recipe | Grid | Native PNG | Palette limit | Generation and cleanup |
| --- | --- | --- | --- | --- |
| pixel-loot | 32 | 32 × 32 | 24 | 35.26 s |
| pixel-character | 64 | 64 × 64 | 24 | 40.11 s |
| pixel-isometric | 64 | 64 × 64 | 32 | 32.3 s |
| pixel-landscape | 128 | 128 × 128 | 32 | 40.04 s |

All seven standard ratios were verified at their exact dimensions: 1024×1024, 1024×576, 576×1024, 1024×768, 768×1024, 1152×768 and 768×1152. The square has full eight-step examples; the other six have two-step dimension smoke checks. These two-step checks establish runtime/dimension support, not visual quality.

An isolated HTTP archive verified a queued switch from the loaded 64 variant to 32, a complete 1024-square generation, a 32-square native PNG, the palette limit, both file routes, the compatibility API, and deletion of both image files. Its archive ended empty. Test artifacts remain outside the user's gallery.

## Installed state

The service is ready on http://127.0.0.1:7861/studio/. Autostart is not enabled; systemd reports this manual-start unit as `static`. The main archive matches the pre-change SHA-256 inventory exactly: 18 PNGs, 18 image rows and 18 job rows. Installed application sources and all four pixel WebP/native-PNG assets match the workspace.

Pixel sprites are opaque RGB. Cleanup does not guarantee coherent animation frames, tileability or correct anatomy. The adapters use MIT; the base model uses Krea 2 Community License. See [setup, sources and limitations](krea-pixel-art.md).
