# Local Image AI Service

A local image studio with **Anima Aesthetic 1.1**, **MOSS SFT**, **Qwen Image 2.1** and **Krea Pixel Art**, using the existing
stable-diffusion.cpp CUDA runtime on the RTX 5070 Laptop 8 GB.

Open **http://127.0.0.1:7861/studio/**. The default guided workflow only needs a subject:
choose one of 44 Anima, MOSS, Qwen and pixel-art recipes, optionally add
scene/details, then generate. The service supplies composition, lighting, format and sampling.
A full prompt preview and free-prompt mode remain available.

[Guide and examples](docs/studio.md) · [Browser guide](http://127.0.0.1:7861/studio/anima-guide/)

[Trained Anima Low Poly styles](docs/anima-lowpoly.md) · [Krea Pixel Art, native PNGs and setup](docs/krea-pixel-art.md) · [Explore Qwen and the example library](docs/qwen21-and-examples.md) · [MOSS photography research](docs/moss-photography.md). Browse real examples in the studio and reuse their inputs and seeds.

Previously removed models remain outside the catalog. The archive keeps current images; individual or selected images can be deleted through the studio.
Login autostart remains disabled; inference stays local without an additional content filter.

```bash
local-image-ai-service doctor
local-image-ai-service start
local-image-ai-service studio
local-image-ai-service status
local-image-ai-service models
local-image-ai-service use moss
local-image-ai-service logs
local-image-ai-service stop
```

`start`, `restart`, and `use moss` wait for the selected model to become ready. Direct systemd commands
are also supported; `systemctl start` returns before loading finishes, so check `/ready`:

```bash
systemctl --user start local-image-ai
systemctl --user stop local-image-ai
systemctl --user restart local-image-ai
systemctl --user status local-image-ai
journalctl --user -u local-image-ai -f
```

## Generate and optionally save an image

The new service CLI calls the running image API. Start the service first:

```bash
local-image-ai-service start
local-image-ai-service generate \
  --prompt 'A red teapot on a white table' --size 512x512 --seed 42 --save
```

`--save` writes a PNG to **`~/.local/share/local-image-ai-service-images/`** and prints JSON
containing its absolute `path`, `model`, `seed`, and `size`. This separate directory survives
service uninstallation. Filenames contain a UTC timestamp, model, seed, and unique suffix.
Existing files are never overwritten. No image is saved unless a saving flag is provided.

Use `--save-dir` instead to choose a directory; this flag implies saving:

```bash
local-image-ai-service generate \
  --model moss --prompt 'A small lighthouse at sunset' --size 768x768 \
  --save-dir "$HOME/.local/share/my-image-experiments"
```

Without `--save` or `--save-dir`, the CLI prints the complete API JSON, including
`data[0].b64_json`, and creates no image files. `generate --help` lists all options.
The selected model must already be loaded; `generate` does not start or switch the service.
This CLI is independent of the existing `imgai` CLI.

MOSS quality defaults are **1024×1024, 50 Euler steps, CFG 3.0, flow shift 5**. The private
`sampling` configuration or per-request `--steps` can lower the step count for previews. Open WebUI sends an explicit
image size, so choose 1024×1024 there manually; this service does not change its settings.
See [quality settings and measured comparisons](docs/quality.md).

## HTTP API

Base URL: `http://127.0.0.1:7861/v1`. Authentication is optional on loopback.

```bash
curl --fail-with-body http://127.0.0.1:7861/v1/models
curl --fail-with-body http://127.0.0.1:7861/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"moss","prompt":"A red teapot on a white table","seed":42,"size":"512x512","n":1,"response_format":"b64_json"}'
```

Responses contain PNG bytes as Base64. The compatibility API never saves images automatically;
CLI saving happens in the client after a successful response. One generation runs at a time;
additional requests receive `429`. Requests for an unknown model return `404`; a configured model that is not loaded returns `409`.
Images are delivered directly from the selected model without an anatomy reviewer, content scoring, or a quality gate.

The runtime is a separate installation of official `sd-server master-987-a77d362`, including
its own CUDA 13.4 runtime libraries. Existing weights are read through absolute paths.
A small Python adapter adds required validation, model IDs, authentication,
and resource limits. See the [measured findings and architecture decision](docs/inspection.md).

Model weights stay outside this repository. The studio bundles generated example thumbnails and native pixel PNGs. Existing image and game
folders are not output or cleanup targets. Before using the existing `imgai` workflows, stop
this service to avoid GPU resource conflicts.

## Documentation

- [Installation, updates, and uninstallation](docs/installation.md)
- [Configuration and model paths](docs/configuration.md)
- [Quality settings, prompts, and comparisons](docs/quality.md)
- [systemd and resource management](docs/systemd.md)
- [HTTP API, CLI generation, and errors](docs/api.md)
- [Atelier studio, models and presets](docs/studio.md)
- [Open WebUI integration](docs/open-webui.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Inventory and runtime decision](docs/inspection.md)
- [Architecture and maintenance notes](docs/architecture.md)
- [Guided recipe checks](docs/recipes-test-report.md)
- [Historical studio GPU measurements](docs/studio-test-report.md)
- [Historical MOSS test report](docs/test-report.md)

## Tests

```bash
cd ~/dev/github/local-image-ai-service
python3 -m unittest discover -s tests -v
# Uses the real GPU, tests MOSS generation and lifecycle, and stops the service afterwards:
python3 tests/integration.py
# With an already running, idle service, test CLI saving without switching or stopping it:
python3 tests/cli_integration.py
```

Requires Python >=3.11 and Pillow >=12.3.0. Astro/Node is used only to build the studio. Runtime revision and reference
checksums are in [runtime.lock.json](runtime.lock.json). Installed file checksums are also
recorded in `~/.local/share/local-image-ai-service/runtime/receipt.json`.
