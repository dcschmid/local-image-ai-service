# Local Image AI Service

A standalone local image inference service for **MOSS-Image SFT** and **Z-Image Turbo**.
MOSS is the default. The service does not import or invoke `imgai` and contains no game,
Blender, character, vehicle, or track workflow code.

Installed and tested on Fedora 44 / RTX 5070 Laptop 8 GB on October 28, 2026.
Login autostart is not enabled. No remote repository was created.

```bash
local-image-ai-service doctor
local-image-ai-service start
local-image-ai-service status
local-image-ai-service models
local-image-ai-service use z-image
local-image-ai-service use moss
local-image-ai-service logs
local-image-ai-service stop
```

`start`, `restart`, and `use` wait for the selected model to become ready. Direct systemd commands
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

## HTTP API

Base URL: `http://127.0.0.1:7861/v1`. Authentication is optional on loopback.

```bash
curl --fail-with-body http://127.0.0.1:7861/v1/models
curl --fail-with-body http://127.0.0.1:7861/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"moss","prompt":"A red teapot on a white table","seed":42,"size":"512x512","n":1,"response_format":"b64_json"}'
```

Responses contain PNG bytes as Base64. The HTTP service never retains generated images;
CLI saving happens in the client after a successful response. One generation runs at a time;
additional requests receive `429`. Requesting the other configured model returns `409` until
it has been selected with `use`. There is no automatic HTTP model switching.

Every image now receives an automatic, offline CPU anatomy check before the response.
The reviewer reuses the existing Qwen3.5-9B encoder read-only, with a separate vision projector.
Clear estimated extra limbs return `422 anatomy_rejected`; images with detected people otherwise
remain **`REVIEW_REQUIRED`**. Tests showed missed extra legs, so no person is automatically certified
as anatomically correct. CLI saving preserves the report in its JSON output and shows a review notice.
See [anatomy screening, accuracy limits, and setup](docs/anatomy.md).

The runtime is a separate installation of official `sd-server master-987-a77d362`, including
its own CUDA 13.4 runtime libraries. Existing weights are read through absolute paths.
A small Python standard-library adapter adds required validation, model IDs, authentication,
and resource limits. See the [measured findings and architecture decision](docs/inspection.md).

This repository contains no models, images, or other binary assets. Existing image and game
folders are not output or cleanup targets. Before using the existing `imgai` workflows, stop
this service to avoid GPU resource conflicts.

## Documentation

- [Installation, updates, and uninstallation](docs/installation.md)
- [Configuration and model paths](docs/configuration.md)
- [systemd and resource management](docs/systemd.md)
- [HTTP API, CLI generation, and errors](docs/api.md)
- [Automatic anatomy screening and its limits](docs/anatomy.md)
- [Future Open WebUI integration](docs/open-webui.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Inventory and runtime decision](docs/inspection.md)
- [Test report](docs/test-report.md)

## Tests

```bash
cd ~/dev/github/local-image-ai-service
python3 -m unittest discover -s tests -v
# Uses the real GPU, tests both models sequentially, and stops the service afterwards:
python3 tests/integration.py
# With an already running, idle service, test CLI saving without switching or stopping it:
python3 tests/cli_integration.py
# Real CPU control images; detection limitations are reported separately:
python3 tests/anatomy_integration.py
```

Requires Python >=3.11, with no additional Python packages. Runtime revision and reference
checksums are in [runtime.lock.json](runtime.lock.json). Installed file checksums are also
recorded in `~/.local/share/local-image-ai-service/runtime/receipt.json`.
