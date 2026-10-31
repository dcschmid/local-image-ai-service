# Krea 2 Pixel Art in Atelier

The fourth model adds four guided recipes and real local examples. Open [the studio](http://127.0.0.1:7861/studio/) and select **Krea 2 · Pixel Art**, or filter Explore by that model. The [English browser guide](http://127.0.0.1:7861/studio/pixel-guide/) includes the same generated examples and native PNG downloads.

| Recipe | Adapter grid at 1024 square | Palette | Starting point |
| --- | --- | --- | --- |
| Tiny loot icon | 32 × 32 | 24 | One bold inventory object |
| Adventure character | 64 × 64 | 24 | One full-body game character |
| Isometric hideaway | 64 × 64 | 32 | One building on a ground tile |
| Scenic world | 128 × 128 | 32 | Foreground, focal point and distant scenery |

Only the subject is required. Settings and extra details are optional. “Use this example” restores the actual recorded inputs and seed. All four recipes use 1024 × 1024, eight Euler steps and CFG 1 by default. The Flux schedule uses a fixed mu of 1.15 to match the official Turbo timestep implementation, with eight intervals from 1 to 0. All seven existing aspect ratios remain available. A 64 grid on 1024 × 576 exports 64 × 36 native pixels. Grid size means the pixel density relative to a 1024-pixel canvas, rather than a forced square image.

The [author’s card](https://huggingface.co/e-n-v-y/Krea-2-Pixel-Art) specifies generation at 1024 square and the trigger “pixel art”, with an explicit exception for the 64-pixel adapter. Guided prompts follow that exception even when the grid changes. The [official Krea documentation](https://github.com/krea-ai/krea-2) recommends training LoRAs on Raw and applying them to Turbo. The eight-step Turbo path fits this GPU better than Raw’s much longer guided sampling.

## Complete DoRA weights

The files include 120 sets of A, B and magnitude tensors each: 360 tensors per adapter. The pinned native runtime recognizes the A/B paths but ignores the magnitude tensors. That partial application is not used for the final presets.

The installer therefore prepares three private GGUF copies. For every adapted matrix it calculates `adapted = W + B @ A`, applies the learned per-output magnitude divided by the adapted row’s L2 norm, and quantizes it back into the original GGUF tensor type. All 360 adapter tensors must be consumed, otherwise conversion fails. This is full DoRA application followed by GGUF quantization; numerical differences from a full-precision ComfyUI workflow are expected. The original downloaded weights remain untouched.

The CUDA runtime itself stays at the existing pinned revision. Requests choose a prepared 32, 64 or 128 variant, without applying the adapter a second time. Changing the grid reloads the matching variant. The compatibility `/v1/images/generations` endpoint uses the loaded variant (64 after a fresh model load); the Studio job API supports selecting the grid and palette per job.

The conversion receipt `models/krea-pixel-dora.json` records source hashes, output hashes and algorithm version. The three prepared GGUFs add approximately 16.5 GB to the 8.5 GB downloaded components. Receipt/output hashes are checked when rerunning the installer. Install the converter separately from the application environment:

```bash
# Use a clean source checkout at the service's pinned native revision.
bash scripts/setup-pixel-converter.sh /path/to/stable-diffusion.cpp
python3 scripts/install-models.py krea-pixel --download-only
local-image-ai-service stop
python3 scripts/install-models.py krea-pixel
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

`setup-pixel-converter.sh` builds only the CPU GGML helper and installs `gguf==0.19.0` into an isolated converter environment. It does not replace the CUDA runtime. Downloads are pinned by revision, size and SHA-256 in `config/models.lock.json`.

## Pixel cleanup and downloads

Atelier quantizes the generated RGB image to 16, 24, 32, 64 or 128 colors without dithering. For each grid cell it selects the modal palette color; the cell’s center breaks ties when possible, followed by stable palette order. The native PNG is expanded with nearest-neighbor scaling for the large preview. Both contain PNG metadata describing the cleanup settings. Gallery metadata records the grid, palette, native dimensions and prepared-weight version.

This is an independent implementation inspired by the author’s [ComfyUI refiner](https://github.com/envy-ai/ComfyUI-Krea2-Pixel-Art-Refiner), without that node’s automatic grid detection or perceptual clustering. Check the drawing yourself: cleanup cannot fix anatomy, guarantee seamless tiles, produce consistent animation frames or create a transparent background. The native image is opaque RGB. Use a contrasting background and a pixel editor when preparing sprites for a game.

For a first result, start with one subject and the recipe’s default palette. Keep the seed fixed and change one thing at a time. Use 128 for a detailed scene, simplify a 32-pixel icon, and resize exported assets using nearest-neighbor.

## Licenses and primary sources

The [pixel adapters](https://huggingface.co/e-n-v-y/Krea-2-Pixel-Art) use MIT. The base weights use the [Krea 2 Community License](https://www.krea.ai/krea-2-licensing); both apply to this combination. It is not an MIT-only or unrestricted model release. The application adds no content filter. The model’s own behavior remains its own.

- [Official Turbo timestep implementation](https://github.com/krea-ai/krea-2/blob/main/sampling.py)
- [Krea official inference code and Turbo guidance](https://github.com/krea-ai/krea-2)
- [AI Toolkit DoRA implementation](https://github.com/ostris/ai-toolkit/blob/main/toolkit/models/DoRA.py)
- [Official native Krea 2 support and recommended GGUF supplier](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/docs/krea2.md)
- [Qwen3-VL 4B encoder GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF)
- [Wan 2.1 VAE](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged)

See the [GPU, browser and archive-integrity report](krea-pixel-test-report.md).
