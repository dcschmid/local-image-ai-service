# Installation and maintenance

## Requirements

Python >=3.11, a systemd user manager with cgroup v2, and NVIDIA drivers with working `nvidia-smi`.
Tested on Fedora 44 KDE, Python 3.14.8, NVIDIA 615.78.08, CUDA 13.4, RTX 5070 Laptop / SM 120,
and 64 GB RAM. No root installation or system Python packages are required.

Model weights must already exist. Installation scripts do not download models. The separate
runtime requires approximately 690 MiB of additional disk space.

## Separately install the existing official build

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/install-runtime.py \
  --binary "$HOME/.local/share/local-image-ai/engines/sd-install/bin/sd-server" \
  --cuda-lib "$HOME/.local/share/local-image-ai/engines/cuda/lib" \
  --source "$HOME/.local/share/local-image-ai/engines/stable-diffusion.cpp"
python3 scripts/install.py
local-image-ai-service doctor
local-image-ai-service start
```

The first script checks the pinned source revision and known binary checksum. It installs
separate copies of the official binary, `libcudart.so.13`, `libcublas.so.13`, and `libcublasLt.so.13`.
It copies **no model weights**. All copies are verified with SHA-256. At runtime, neither the
previous project's source, binary, Python environment, nor CUDA installation path is required.
System libraries and the NVIDIA driver remain operating-system dependencies.

`install.py` installs the application, a separate launcher, the user unit, and its bounded-stop
drop-in. On first installation, it creates configuration with local absolute paths and the GPU UUID.
Existing paths, port, and authentication settings are retained. An upgrade removes retired review
settings and non-MOSS model mappings from this service configuration, without deleting model files.
It removes obsolete reviewer application code. Previously downloaded reviewer data is retained but
is no longer loaded or executed; MOSS's existing text encoder remains required for generation.
It neither starts nor enables the service. Ensure `~/.local/bin`
is on `PATH`.

## Reproduce a separate source build

Alternatively, build from the official repository at the exact pinned revision and submodules:

```bash
cd ~/dev/github/local-image-ai-service
local-image-ai-service stop
CUDA_TOOLKIT_ROOT="$HOME/.local/share/local-image-ai/engines/cuda" \
  bash scripts/build-runtime.sh
python3 scripts/install.py
local-image-ai-service doctor
local-image-ai-service start
```

Requires Git, CMake, Ninja, C/C++ compilers, and an existing CUDA 13.4 toolkit. The toolkit is
read-only input. Downloads and build output stay under `~/.cache/local-image-ai-service/build`;
the previous stable-diffusion.cpp source directory is not used. Build configuration is reproducible;
bit-identical binaries across different compilers are not guaranteed. This is a maintenance path;
the initial installation used and tested a separate copy of the known working official build.

## Update the application

```bash
cd ~/dev/github/local-image-ai-service
local-image-ai-service stop
python3 -m unittest discover -s tests -v
python3 scripts/install.py
local-image-ai-service start
```

Runtime upgrades require a deliberate change to the pinned revision and build verification,
followed by a build, Doctor, and integration tests. There is no automatic `git pull` on a running
runtime. `build-runtime.sh` rebuilds the current pin. There are no automatic updates, model downloads,
or restart loops.

## Save CLI-generated images

```bash
local-image-ai-service generate --prompt 'A red ceramic teapot' --save
local-image-ai-service generate --prompt 'A small lighthouse' \
  --save-dir "$HOME/.local/share/my-image-experiments"
```

The default `--save` directory, `~/.local/share/local-image-ai-service-images`, is separate from
the application and cache and survives updates and uninstallation. Choose a custom directory outside
the installation, configuration, and cache trees if those outputs should also survive uninstallation.
No saving flag changes the HTTP API or the existing `imgai` installation.

## Uninstall

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/uninstall.py
```

Removes only this user unit and its own drop-in, this launcher, and these three directories:

- `~/.local/share/local-image-ai-service`
- `~/.config/local-image-ai-service`
- `~/.cache/local-image-ai-service`, including its own test and audit logs

The repository, previous `local-image-ai` installation, models, existing images, game projects,
and the default CLI image directory `~/.local/share/local-image-ai-service-images` are retained.
Back up audit logs before uninstalling if needed. Neither `~/.local/share/local-image-ai` nor
`~/Pictures/AI-Generated` is removed.
