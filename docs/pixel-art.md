# Pixel Art in Atelier

Pixel Art offers eight guided recipes with real local examples. Open [the studio](http://127.0.0.1:7861/studio/) and select **FLUX.2-klein · Pixel Art**, or filter Explore by that model. The [English browser guide](http://127.0.0.1:7861/studio/pixel-guide/) explains the workflow.

| Recipe | Starting point |
| --- | --- |
| Tiny loot icon | One bold inventory object |
| Adventure character | One full-body game character |
| Isometric hideaway | One building on a ground tile |
| Scenic world | Foreground, focal point and distant scenery |
| Creature sprite | One complete creature in an idle pose |
| Dialogue portrait | An expressive character bust |
| Tiny vehicle | One vehicle with readable bodywork and wheels |
| Dungeon room | A complete overhead room with a few props |

Only the subject is required. Settings and extra details are optional. “Use this example” restores the actual recorded inputs and seed. All eight recipes use 1024 × 1024, twenty Euler steps and CFG 4 by default. The PXART4 LoRA produces a clean pixel grid directly; there is no separate cleanup step. All seven aspect ratios remain available.

## Model and components

The model is FLUX.2-klein-4B with the PXART4 pixel art LoRA. The components are:

- **Diffusion:** [FLUX.2-klein-4B GGUF](https://huggingface.co/leejet/FLUX.2-klein-4B-GGUF) (Q4_0, 2.46 GB)
- **Text encoder:** [Qwen3-4B GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF) (Q4_K_M, 2.50 GB)
- **VAE:** [FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) (168 MB)
- **LoRA:** [PXART4 pixel art LoRA](https://huggingface.co/adirik/pixel-art-lora-flux.2-klein-4B) (370 MB)

Total download is approximately 5.5 GB. The LoRA is applied at load time through the native runtime's `--lora-model-dir` flag; no separate preparation step is needed.

```bash
python3 scripts/install-models.py flux-pixel --download-only
local-image-ai-service stop
python3 scripts/install-models.py flux-pixel
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

Downloads are pinned by revision, size and SHA-256 in `config/models.lock.json`.

## Know the limits

The LoRA produces a clean pixel grid, but it does not guarantee tileable textures, coherent animation frames or correct anatomy. Check the actual drawing, outlines and perspective yourself. The background stays opaque; use a contrasting background and a pixel editor when preparing sprites for a game.

For a first result, start with one subject and the recipe's default settings. Keep the seed fixed and change one thing at a time.

## Licenses and primary sources

All components are Apache-2.0. The application adds no content filter.

- [FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [FLUX.2-klein-4B GGUF](https://huggingface.co/leejet/FLUX.2-klein-4B-GGUF)
- [Qwen3-4B GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
- [PXART4 pixel art LoRA](https://huggingface.co/adirik/pixel-art-lora-flux.2-klein-4B)
