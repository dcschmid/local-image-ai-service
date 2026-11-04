# Install Atelier

Atelier has three parts: a small Python service, a built Studio interface, and a separate CUDA inference runtime. The model files live outside the repository.

If it is already installed, you can skip setup and run:

```bash
local-image-ai-service studio
```

That starts the service and opens the browser. For a first installation, work through the steps below from the repository root.

## One-shot setup

`scripts/setup.sh` runs the steps below in order with dependency checks, reusing the tested per-part scripts. It stops a running service first, never enables login autostart, and ends with `doctor` and a service start:

```bash
# Runtime archive present in dist/ (produced by scripts/package-runtime.py):
scripts/setup.sh

# Also download extra model weights (service is stopped during the download):
scripts/setup.sh --models anima z-image z-image-turbo flux-pixel

# No archive and no known-good build? Build the pinned runtime from source
# (CUDA toolkit is auto-detected; pass --cuda-toolkit <dir> to override):
scripts/setup.sh --build-runtime
```

The runtime is installed in this order: `--build-runtime`, then a portable archive (`--runtime-archive <p>`, or auto-detected `dist/runtime-<revision>.tar.zst`), then a known-good build at the default paths. The archive bundles the pinned `sd-server` binary and its CUDA libraries, so a machine that has it needs no compiler or CUDA toolkit — only the NVIDIA driver. `scripts/package-runtime.py` produces the archive and a manifest from an installed, verified runtime; the installer re-verifies every file against [runtime.lock.json](../runtime.lock.json) before use. The archive is a build artifact (gitignored); distribute it however you like (a release, a model host, or `scp`) and point `--runtime-archive` at it.

Use `--no-start` to leave the service stopped, `--skip-studio` to reuse an existing `studio/dist`, and `--runtime-binary/--runtime-cuda-lib/--runtime-source` to point at a different build. The manual steps below document what the script does.

## Check what you need

The current setup is for **Linux with a systemd user manager, cgroup v2 and NVIDIA CUDA**. It has been tested on Fedora 44 KDE with an RTX 5070 Laptop, 8 GB VRAM and 64 GB RAM. CPU offloading is part of that setup; rendering time depends on the model, resolution and available memory.

You need:

- Python **3.11+** with **Pillow 12.3+** available to the Python used by the launcher.
- `nvidia-smi` working with the NVIDIA driver.
- Node/npm for building the Studio. The project pins its build-time Node package.
- The supported `stable-diffusion.cpp` build and its CUDA libraries, or the tools to build that pinned revision.
- Existing **MOSS SFT** components. The installer creates paths for them; check those paths before starting the service.

The tested runtime uses NVIDIA 615.78.08 and CUDA 13.4. It needs roughly 690 MiB for its separate runtime copies, plus disk space for whichever models you install. This guide assumes you can reuse the known working build paths shown below; adapt them to your machine.

## 1. Build the Studio

```bash
npm ci --prefix studio
npm run build --prefix studio
```

The result is a static site under `studio/dist/`. Python serves those pages alongside the API, so the installed application does not need a separate Node server.

## 2. Install the inference runtime

To reuse the existing verified build:

```bash
python3 scripts/install-runtime.py \
  --binary "$HOME/.local/share/local-image-ai/engines/sd-install/bin/sd-server" \
  --cuda-lib "$HOME/.local/share/local-image-ai/engines/cuda/lib" \
  --source "$HOME/.local/share/local-image-ai/engines/stable-diffusion.cpp"
```

The script checks the pinned revision and binary checksum, then copies the executable and required CUDA libraries into this service's own runtime directory. It does not copy model weights or change the original runtime. The NVIDIA driver and system libraries remain operating-system dependencies.

If those build paths do not exist, use [the source-build option below](#build-the-pinned-runtime-from-source). The exact pin is recorded in [runtime.lock.json](../runtime.lock.json).

## 3. Install the application and check its paths

If this is an update, stop the existing instance with `local-image-ai-service stop` first. For a first installation, run:

```bash
python3 scripts/install.py
local-image-ai-service doctor
```

The installer creates the launcher, application files, user unit and a private configuration at:

```text
~/.config/local-image-ai-service/config.json
```

Make sure the MOSS `diffusion`, `llm`, `vae` and `tokenizer` paths point to your actual files. The [configuration guide](configuration.md) explains the fields, and [the example configuration](../config/config.example.json) shows their layout. `doctor` checks the configured model files and runtime before you try a render.

Keep `~/.local/bin` on your `PATH`. The application installer does not start the service or enable login autostart. During an upgrade it keeps supported model mappings and removes retired profiles; it does not delete shared model files.

## 4. Add the other models you want

With the service stopped, the model installer can download and verify the pinned Anima, Qwen and Z-Image components:

```bash
python3 scripts/install-models.py anima
python3 scripts/install-models.py z-image z-image-turbo
```

These downloads are optional and explicit. MOSS continues to use your existing components. For FLUX.2-klein Pixel Art, run `python3 scripts/install-models.py flux-pixel`. Model files are large, so check available disk space first.

The two Z-Image profiles share an encoder and VAE and require about 10.54 GB in total. The pinned base model uses the runtime author’s compatible Q4_0 file; see [Z-Image setup and GPU checks](z-image-and-presets.md) for settings and the blank-output issue found with the initial checkpoint.

The catalog explains the model licenses. Qwen's configured release uses a non-commercial research/evaluation license; it is not an unrestricted commercial model.

## 5. Start creating

```bash
local-image-ai-service studio
```

Once loading finishes, open **[Atelier](http://127.0.0.1:7861/studio/)** and try an example from **Explore**. [The Studio tour](studio.md) walks through your first image.

To check or stop the service later:

```bash
local-image-ai-service status
local-image-ai-service stop
```

For terminal generation, use [the CLI walkthrough](agent-cli.md). To let Codex, Claude Code or OMP create assets, follow [the agent setup](agents-integration.md).

## Update the application

From the repository root, after reviewing the changes:

```bash
local-image-ai-service stop
python3 -m unittest discover -s tests -v
npm ci --prefix studio
npm run build --prefix studio
python3 scripts/install.py
local-image-ai-service start
```

The image archive and existing configuration stay outside the application directory. Reinstall/update the managed skill if its instructions changed, following [the client setup guide](agents-integration.md).

The runtime has a separate pin and verification process. Application updates do not silently rebuild it, download models or enable autostart.

## Build the pinned runtime from source

This is the alternative when you are not copying a known working build. It needs Git, CMake, Ninja, C/C++ compilers and an existing CUDA 13.4 toolkit:

```bash
CUDA_TOOLKIT_ROOT="$HOME/.local/share/local-image-ai/engines/cuda" \
  bash scripts/build-runtime.sh
```

The toolkit is read-only input. Downloads and build output stay under `~/.cache/local-image-ai-service/build`; the previous source directory is not modified. Continue with application installation and `doctor` afterward. Compiler differences can change binary hashes even when the source revision is the same.

## Where your images go

Studio images and metadata are saved automatically under:

```text
~/.local/share/local-image-ai-service-images/studio/
```

CLI `render --save-dir ./assets` also exports the result into your project. The compatibility `generate` command saves only when you pass `--save` or `--save-dir`; without those flags it returns API JSON containing the image bytes. See [CLI generation](agent-cli.md) for the difference.

Choose a project directory outside the application/configuration/cache trees when you want exported assets to survive service removal.

## Remove the service

```bash
python3 scripts/uninstall.py
```

This removes the user unit, launcher, application/runtime, configuration and the service's own cache. It retains the repository, shared external model files, the previous `local-image-ai` installation and the separate generated-image directory. Downloads and prepared weights inside `~/.local/share/local-image-ai-service/models/` are part of the removed service data tree; move any copies you want to keep out of that tree first. `~/Pictures/AI-Generated` and game projects are not cleanup targets. Save audit logs elsewhere first if you need them, because the service cache is removed.

Agent registrations and portable skills are separate. Remove a registration through the corresponding client if you no longer want it advertised after uninstalling the service; the [agent guide](agents-integration.md) lists where each client stores it.

[Back to the Studio tour](studio.md) · [Troubleshooting](troubleshooting.md) · [All documentation](README.md)
