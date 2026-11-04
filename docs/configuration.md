# Configuration

Active file: `~/.config/local-image-ai-service/config.json`, owned by the current user with
mode `0600`. Template: [config.example.json](../config/config.example.json).
Configuration and API keys must stay out of Git. Changes take effect after a restart.

| Field | Default / meaning |
| --- | --- |
| `active_model` | `moss` initially; `moss`, `anima`, `flux-pixel`, `z-image` or `z-image-turbo` |
| `host` | Only `127.0.0.1` is accepted |
| `port` | 7861, client-facing local API |
| `backend_port` | 17861, internal loopback runtime |
| `runtime` | Absolute path to this service's `runtime/bin/sd-server` |
| `cuda_lib` | Absolute path to its own CUDA runtime libraries |
| `gpu_uuid` | GPU UUID reported by `nvidia-smi` |
| `load_timeout` | 180 seconds; allowed range 1–1800 |
| `generation_timeout` | 300 seconds; allowed range 1–1800 |
| `api_key_file` | `null` or absolute path to a private key file |
| `sampling` | Optional MOSS defaults with `steps` and `cfg`; defaults to 50 and 3.0 |
| `models` | Curated model entries with absolute component paths; see [studio guide](studio.md) |

## Existing weights

Model root on this machine: `~/.local/share/local-image-ai/models/`. The installed JSON contains
expanded absolute paths. Tildes, environment variables, and relative paths are not expanded.

| Model | Role | File under model root |
| --- | --- | --- |
| moss | diffusion | `moss/MOSS-Image-SFT-Q4_K.gguf` |
| moss | llm | `moss/Qwen3.5-9B-Q4_K_M.gguf` |
| moss | vae | `moss/flux2-vae.safetensors` |
| moss | tokenizer | `moss/tokenizer_qwen3.5.json` |

Here, `llm` refers only to the image model's text encoder. No chat API is exposed. Shared encoders
can be referenced through identical absolute paths. The service never copies, modifies, or deletes them.

## Reload MOSS

```bash
local-image-ai-service use moss
```

`use moss` checks the four required files, stops this service, records the MOSS selection, and
starts it again. It remains available as a reload command. Anima Aesthetic can also be selected with `use anima`. The command
waits for readiness; reloading cancels requests in progress. The existing `imgai` CLI is unchanged.

Missing files detected before reloading leave the current service untouched. A later load failure
results in `/ready` = 503 and requires manual repair; there is no automatic rollback or reload.

## Sampling and memory

MOSS quality defaults: Euler, 50 steps, CFG 3.0, discrete scheduler, flow shift 5.
Default size: 1024×1024. The native MOSS implementation applies negative-branch layer skipping
at layer 22. These settings follow the [official SFT model card](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT)
and the [pinned runtime documentation](https://github.com/leejet/stable-diffusion.cpp/blob/a77d3623180b2bc1886f3dd04c0aa04156a987ef/docs/moss_image.md).

Optional private configuration:

```json
"sampling": {"steps": 50, "cfg": 3.0}
```

Both keys are required when the object is present. `steps` must be an integer from 10 to 100;
`cfg` must be a finite number from 1 to 6. The recommended CFG is 3.0 for detailed prompts.
Missing `sampling` uses the quality defaults; null, unknown keys, and invalid values are rejected.
Changes require a restart. `doctor` and `models` print configured sampling values. For a faster
preview, 20 steps can be configured explicitly, or a smaller `size` can be requested. High step
counts may require increasing the generation timeout; only tested combinations are described in
the [quality guide](quality.md). Per-request `steps`, `cfg_scale`, `sampler`, and `negative_prompt` are supported; see the API and studio guide.

See [API limits](api.md). The runtime uses `--offload-to-cpu`, `--flash-attn on`, explicit
`--backend cuda0`, VAE tiling, eight CPU threads, and one conditioning-cache entry.
These limits apply only to this service.

CUDA libraries come exclusively from its own runtime. `CUDA_VISIBLE_DEVICES` selects the GPU;
an unavailable CUDA backend causes an error rather than CPU fallback. There is no hard VRAM
partition: other GPU workloads started later can still cause OOM.

## CLI image saving

Saving is a per-call client option, not a service configuration setting:

- `generate --save`: save in `~/.local/share/local-image-ai-service-images`.
- `generate --save-dir DIRECTORY`: save in the selected directory, creating it when needed.
- Neither flag: return API JSON only, without writing an image.

The default image directory is outside the application and cache and is not removed by uninstall.
The CLI writes in the caller's process. The studio writes to its own subdirectory, permitted
by the service unit. Existing picture and project folders remain unused by default.

## Optional Bearer key

Create a private key file without printing its value:

```bash
python3 - <<'PY'
from pathlib import Path
import os, secrets
os.umask(0o077)
p = Path.home() / '.config/local-image-ai-service/bearer-key'
with p.open('x') as stream:
    stream.write(secrets.token_urlsafe(32) + '\n')
p.chmod(0o600)
PY
```

Set `api_key_file` in JSON to its absolute path, then restart. The key must contain at least
24 characters, be owned by the current user, and have mode `0600`. Once configured,
the compatibility, health/readiness and Studio API routes require `Authorization: Bearer <KEY>`. The service CLI
reads and sends this key automatically, including for `generate`. Without a configured key,
no header is required and a client-supplied dummy key is ignored. Key changes require a restart.

The internal native runtime remains unauthenticated on loopback. The key protects the adapter
but is not a security boundary against other local users. A future local tunnel must forward
only the adapter port. The service itself does not accept a LAN bind address.

## Z-Image profiles

Both Z-Image profiles use three roles: `diffusion`, `llm` and `vae`. Their Qwen3 4B text encoder and FLUX VAE share the same local files; their diffusion weights differ. Install the pinned components with `python3 scripts/install-models.py z-image z-image-turbo` while the service is stopped. See [Z-Image setup and research](z-image-and-presets.md).

Z-Image defaults to 40 steps, CFG 4, Euler, discrete scheduling and flow shift 6. Turbo uses eight steps, CFG 1 and flow shift 3, with no negative prompt. The `sampling` configuration still controls only MOSS.
