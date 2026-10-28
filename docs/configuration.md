# Configuration

Active file: `~/.config/local-image-ai-service/config.json`, owned by the current user with
mode `0600`. Template: [config.example.json](../config/config.example.json).
Configuration and API keys must stay out of Git. Changes take effect after a restart.

| Field | Default / meaning |
| --- | --- |
| `active_model` | `moss`; only `moss` or `z-image` |
| `host` | Only `127.0.0.1` is accepted |
| `port` | 7861, client-facing local API |
| `backend_port` | 17861, internal loopback runtime |
| `runtime` | Absolute path to this service's `runtime/bin/sd-server` |
| `cuda_lib` | Absolute path to its own CUDA runtime libraries |
| `gpu_uuid` | GPU UUID reported by `nvidia-smi` |
| `load_timeout` | 180 seconds; allowed range 1–1800 |
| `generation_timeout` | 300 seconds; allowed range 1–1800 |
| `api_key_file` | `null` or absolute path to a private key file |
| `models` | Exactly two entries with absolute, readable file paths |
| `anatomy` | Automatic offline CPU screening; defaults listed below |

## Automatic anatomy checker

`anatomy.enabled` defaults to `true`, including when this section is omitted from older config.
It applies to every API/CLI generation. There is no per-request bypass or prompt-keyword trigger.
The installed configuration explicitly enables it. Administrative opt-out is reported as `DISABLED`.

| Anatomy field | Default / meaning |
| --- | --- |
| `enabled` | `true`; boolean |
| `runtime` | Absolute path to `~/.local/share/local-image-ai-service/anatomy/runtime/llama-mtmd-cli` |
| `model` | Absolute path to the existing `~/.local/share/local-image-ai/models/moss/Qwen3.5-9B-Q4_K_M.gguf`, never copied |
| `mmproj` | Absolute path to `~/.local/share/local-image-ai-service/anatomy/models/mmproj-Qwen3.5-9B-F16.gguf` |
| `timeout` | 180 seconds; allowed range 1–600 |
| `threads` | 8 CPU threads; allowed range 1–8 |

Missing assets prevent readiness. Invalid or failed checks withhold the image rather than pretending
it passed. Person images still require manual review because calibration found missed extra legs.
Full behavior and status meanings are in [anatomy.md](anatomy.md).

## Existing weights

Model root on this machine: `~/.local/share/local-image-ai/models/`. The installed JSON contains
expanded absolute paths. Tildes, environment variables, and relative paths are not expanded.

| Model | Role | File under model root |
| --- | --- | --- |
| moss | diffusion | `moss/MOSS-Image-SFT-Q4_K.gguf` |
| moss | llm | `moss/Qwen3.5-9B-Q4_K_M.gguf` |
| moss | vae | `moss/flux2-vae.safetensors` |
| moss | tokenizer | `moss/tokenizer_qwen3.5.json` |
| z-image | diffusion | `z-image/z_image_turbo-Q4_K.gguf` |
| z-image | llm | `z-image/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| z-image | vae | `z-image/flux1-ae.safetensors` |

Here, `llm` refers only to the image model's text encoder. No chat API is exposed. Shared encoders
can be referenced through identical absolute paths. The service never copies, modifies, or deletes them.

## Switch models

```bash
local-image-ai-service use z-image
local-image-ai-service use moss
```

`use` first checks the required files, then stops its complete systemd process group, atomically
writes private configuration, and starts again. At most one model is loaded. The command waits
for readiness. Switching cancels requests in progress. There is no HTTP model switch and no
change to `imgai` or its configuration.

Missing files detected before switching leave the current service untouched. A later load failure
results in `/ready` = 503 and requires manual repair; there is no automatic rollback or reload.

## Sampling and memory

MOSS: Euler, 20 steps, CFG 3.0. Z-Image: Euler, 8 steps, CFG 1.0. Default size: 768×768;
see [API limits](api.md). Both use `--offload-to-cpu`, `--flash-attn on`, explicit
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
The service's systemd filesystem permissions do not need to change: the CLI writes the response
in the caller's process. Existing picture and project folders remain unused by default.

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
**all four client-facing endpoints** require `Authorization: Bearer <KEY>`. The service CLI
reads and sends this key automatically, including for `generate`. Without a configured key,
no header is required and a client-supplied dummy key is ignored. Key changes require a restart.

The internal native runtime remains unauthenticated on loopback. The key protects the adapter
but is not a security boundary against other local users. A future local tunnel must forward
only the adapter port. The service itself does not accept a LAN bind address.
