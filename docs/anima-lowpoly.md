# Trained Low Poly styles for Anima

The studio has two additional model choices that share the installed Anima Aesthetic 1.1 base weights. They apply the selected trained adapter automatically in guided mode, free prompt mode and the compatibility API.

| Choice | Adapter | Author/version | Additional weights |
| --- | --- | --- | --- |
| Anima · Low Poly PS1 / PSX | `LowPolyPSX_AnimaPreview2_byKonan.safetensors` | Konan, Preview2 / 2794693 | 51,721,808 bytes |
| Anima · Low Poly Style | `AnimaLowPoly.safetensors` | PrettyAIGirls, Anima / 2692813 | 264,419,968 bytes |

The user supplied the Preview2 PSX file, rather than the author's later BaseV1.0 release. The installer checks that exact version's SHA-256. It does not silently substitute a different file. Original Downloads files are retained; verified copies live in the service's own models directory. The three base components are reused, not duplicated per style.

Open the [English Low Poly guide](http://127.0.0.1:7861/studio/lowpoly-guide/) for examples and direct recipe links. Each link restores the example inputs and seed in the studio.

## Text-encoder name compatibility

The original Low Poly Style file uses Kohya text-encoder names that the pinned loader maps to a CLIP namespace. Anima uses Qwen instead. The installer makes `AnimaLowPoly-native-v1.safetensors`, renaming the 588 text-encoder entries to explicit Qwen module paths. Projection names such as `o_proj` and `gate_proj` keep their underscores. Every byte of the numerical tensor payload is copied unchanged; the original adapter and Downloads file are retained.

The conversion receipt records the original SHA-256, derived SHA-256, renamed-entry count and version. The native runtime applies 588/588 text-encoder and 840/840 diffusion entries with this file. The compatibility copy adds approximately 264 MB of storage and does not modify the base model or CUDA runtime. Gallery metadata records `adapter_revision` so examples from the earlier partial mapping cannot be reused accidentally.

## Recipes and prompting

| Variant | Recipe | Starting point |
| --- | --- | --- |
| PSX | Retro adventurer | One full-body character in a clear pose |
| PSX | Game world | Chunky architecture, a focal building and a clear route |
| PSX | Inventory prop | One object, large details and a plain background |
| Low Poly Style | Character portrait | A close view, clothing colors and one accessory |
| Low Poly Style | Miniature diorama | One structure and a few supporting props |
| Low Poly Style | Angular landscape | Foreground, middle distance and a clear horizon |

Only the subject is required. Setting and extra details are optional. Guided recipes add the trigger and composition; the selected variant applies the adapter. “Use this example” restores the recorded subject, scene, details, quality and seed. All existing aspect-ratio choices remain available.

PSX uses the author's trigger words `lowpoly, ps1, psx, low poly, 3d` and a curated strength of 0.9 within the author's 0.8–1.0 recommendation. Low Poly Style uses `l0wp0ly` with zeros and a curated strength of 0.75. Its adapter includes both text-encoder and diffusion weights.

Recommended uses the existing Anima Aesthetic profile: 35 Euler steps and CFG 4.5. Draft uses 30 steps at a smaller canvas; More detail uses 45 steps. These settings are starting points, not a guarantee for every subject. Model strength is fixed per variant and recorded in gallery metadata. Guided single-character recipes discourage duplicate figures. Free prompt mode leaves prompt composition to the user; include the appropriate trigger words yourself.

The native API receives a structured LoRA entry with the configured file's basename and the fixed strength. Its LoRA directory is confined to the service-owned model directory. The public API accepts curated model IDs; user-supplied LoRA paths and runtime-control prompt tags remain rejected.

Outputs are regular PNGs at the selected canvas size. Krea's palette/grid cleanup does not apply to these styles. Images can serve as game-art concepts; they do not provide meshes, UVs, rigs or guaranteed consistent turnaround views.

## Installing locally downloaded files

Download the exact versions linked below into `~/Downloads`, keeping their published filenames. The installer verifies size and SHA-256 before copying them. Civitai currently requires login for model downloads. The running service does not use a Civitai account or network connection for generation.

```bash
python3 scripts/install-models.py anima-psx anima-lowpoly --download-only
local-image-ai-service stop
python3 scripts/install-models.py anima-psx anima-lowpoly
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

The lockfile pins both adapter versions and all three shared base components. Pruning retains both curated variants and their shared files.

## Sources and terms

- [PS1 / PSX author page, supplied Preview2 version](https://civitai.com/models/2485743?modelVersionId=2794693)
- [Low Poly Style, Anima version](https://civitai.com/models/2204336?modelVersionId=2692813)
- [Anima Aesthetic model card](https://huggingface.co/circlestone-labs/Anima)
- [CircleStone base-model license](https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md)

Both authors permit commercial images under their published creator terms. These are creator terms, rather than an MIT-only release; the CircleStone base-model license also applies. The adapters supply a trained visual style. The service adds no content filtering or automatic safe/NSFW tags. No separate claim that these adapters are “uncensored” is made by the installer.

For GPU, browser and archive-integrity checks, see the [validation report](anima-lowpoly-test-report.md).
