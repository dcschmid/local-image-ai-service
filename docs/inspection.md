# Inventory and architecture decision — October 28, 2026

## Existing installation: read-only inspection

- CLI: `~/.local/bin/imgai`, a 188-byte shell launcher for its existing virtual environment.
- Source project: `~/dev/local-ai/image-stack`.
- Inference binaries: `~/.local/share/local-image-ai/engines/sd-install/bin/{sd-cli,sd-server}`.
- Version: `master-987-a77d362`, full revision `a77d3623180b2bc1886f3dd04c0aa04156a987ef`.
- The official stable-diffusion.cpp source tree was clean at that revision.
- Rootless CUDA toolkit: `~/.local/share/local-image-ai/engines/cuda`, version 13.4.92.
- Build: Release, `SD_CUDA=ON`, `CMAKE_CUDA_ARCHITECTURES=120`, CUDA flag `-allow-unsupported-compiler`.
- GPU: RTX 5070 **Laptop** GPU, 8151 MiB reported by the driver, compute capability 12.0; NVIDIA 615.78.08.
- Reference parameters from the existing `registry.py`, `build-engine.sh`, and recorded benchmarks:
  CPU offload, Flash Attention, Euler; MOSS 20 steps / CFG 3.
- All four required MOSS files exist; roles and names are in [configuration.md](configuration.md).
- `sd-server --list-devices` reports CUDA0. Without the correct library path, `libcudart.so.13` is missing.
- The old `imgai-api.service` existed and was inactive, also using 7861. It was not changed.

The old Image-AI and Riff-Racers repositories already contained uncommitted changes. They were
neither cleaned nor committed. The audit therefore records actual file content, modes, modification
timestamps, symlink targets, and existing Git metadata rather than relying only on `git diff`.

## Native API verification

Sources: the official [OpenAI route implementation at the pinned revision](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/examples/server/routes_openai.cpp)
and its [API documentation](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/examples/server/api.md).

Source inspection found generation, editing, and model routes. A controlled real MOSS run using
the separately installed binary confirmed:

| Check | Result |
| --- | --- |
| `GET /v1/models` | 200; only ID `sd-cpp-local` |
| Generation with `model=does-not-exist` and `size=invalid-size` | **200 and an image**; model ID ignored, invalid size fell back to CLI defaults |
| `POST /v1/images/edits` without an image | 400; a route exists, but this does not establish supported model editing |

Native generation supports prompts, count, size, and Base64 output. At this pin, seed must be
passed through `<sd_cpp_extra_args>`; a top-level `seed` is not read. Native `/v1/models` does
not expose the required model IDs, and unknown top-level fields are not strictly rejected.
Native `/sdcpp/v1/models/*` management exists but is neither exposed nor used by this application.

## Why an adapter is necessary

Native model IDs, validation, and resource/parameter rules do not meet the required behavior.
A standalone Python standard-library adapter therefore handles HTTP validation, model metadata,
optional authentication, nonwaiting generation admission, process readiness and termination,
and timeouts. It uses no FastAPI, third-party packages, or modules from the previous project.
The official binary performs all inference.

Only MOSS is supported as of October 29, 2026. Reloading MOSS stops and starts this service's unit,
keeping process ownership and the 8 GB GPU constraint straightforward. An HTTP request cannot
load arbitrary models or access native administration, video, WebUI, or file-path APIs.

## Separate runtime

The known official build was separately installed with SHA-256 verification under
`~/.local/share/local-image-ai-service/runtime`. CUDA libraries are also separate regular files,
not links to the old project. A pinned independent build script is included. The previous source
and virtual environment are not runtime dependencies. Only existing weights are read at their
configured absolute paths.

No previous programs were switched to the new API. No Open WebUI, firewall, Blender, Defold,
or other project configuration was changed by this implementation.

## Optional CLI saving

The later `generate` command is a client of the existing image API. Its `--save` and `--save-dir`
flags decode and write the response only for that invocation. They add no server-side storage
or inference dependency. Default output is outside both the old picture folders and the new
installation/cache trees and is retained by uninstall.
