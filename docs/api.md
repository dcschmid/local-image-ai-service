# HTTP API and CLI generation

Base URL: `http://127.0.0.1:7861/v1`, for image generation only. JSON over HTTP, no public
network exposure or CORS access. Requests containing `Origin` are rejected; Open WebUI calls
from its server. Optional Bearer key: see [configuration](configuration.md).

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/v1/models` | OpenAI model list containing only `moss`, with `installed`, `loaded`, and `capabilities` |
| POST | `/v1/images/generations` | Synchronous generation of exactly one Base64 PNG |
| GET | `/health` | 200 for a live adapter; `status`, `active_model`, `backend_pid`, `error`, and `busy` |
| GET | `/ready` | 200 with a ready backend, otherwise 503 |

Image editing, chat, embeddings, video, SDAPI, native administration, and other endpoints
are unavailable on the service port (404). MOSS is configured for text-to-image.
A native editing route does not establish model editing support.

`/v1/models` remains reachable after a load failure. `installed` checks readable files;
`loaded` means actual readiness. Only one entry can have `loaded: true`.

## Generate through HTTP

```bash
curl --fail-with-body http://127.0.0.1:7861/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"moss","prompt":"A small red teapot on a white table","size":"512x512","n":1,"seed":42,"response_format":"b64_json"}'
```

Add `Authorization: Bearer <KEY>` if a key is configured. Example response:

```json
{
  "created": 1793183935,
  "output_format": "png",
  "data": [{"b64_json": "<PNG as Base64>"}],
  "model": "moss",
  "seed": 42
}
```

Response `model` and `seed` are local extensions. Native PNG metadata records the actual seed,
which is checked by integration tests. A seed does not guarantee byte-identical images across
processes, hardware, or runtime versions.

Generated image bytes are returned unchanged. There is no anatomy review, content scoring,
automatic regeneration, or `anatomy_check` response field. Basic response-format validation
still detects corrupt responses and dimensions that differ from the request.

| Request field | Handling |
| --- | --- |
| `model` | Optional; defaults to `moss`. Only `moss` is supported; every other model returns 404 |
| `prompt` | Required nonblank string, up to 16,000 characters |
| `seed` | Optional local extension; integer 0–2147483647, otherwise generated randomly |
| `size` | Optional, default `1024x1024`; `WIDTHxHEIGHT`, each 256–1024 and a multiple of 64; rectangles accepted |
| `n` | Optional; only integer 1. Request more images sequentially |
| `response_format` | Optional; only `b64_json` |
| `output_format` | Optional; only `png` |
| `user` | Optional string up to 256 characters; accepted as compatibility metadata, unused and not stored |

All other parameters receive 400, including `quality`, `style`, `steps`, `cfg_scale`,
`negative_prompt`, `background`, `output_compression`, and arbitrary model paths.
Sampling is configured administratively for this service (default: 50 steps, CFG 3.0);
unsupported per-request features are not silently simulated. See [configuration](configuration.md).
Prompts containing `sd_cpp_extra_args` or LoRA control tags are rejected. The adapter translates
only the validated seed into the documented native extension. Maximum request body: 64 KiB;
JSON object, `Content-Type: application/json`, exactly one `Content-Length`, no chunked requests.

## Generate through the service CLI

```bash
# Complete API JSON on stdout, no saved image:
local-image-ai-service generate --prompt 'A red teapot' --size 512x512 --seed 42

# Save in ~/.local/share/local-image-ai-service-images:
local-image-ai-service generate --prompt 'A red teapot' --size 512x512 --seed 42 --save

# Save in an explicitly selected directory instead:
local-image-ai-service generate --model moss --prompt 'A mountain lake' \
  --size 768x768 --save-dir "$HOME/.local/share/my-image-experiments"
```

`--prompt` is required. `--model` defaults to the configured model, `--size` to `1024x1024`,
and `--seed` to a server-generated random seed. The flags `--save` and `--save-dir DIRECTORY`
are mutually exclusive; `--save-dir` implies saving. The directory is created only after a
successful, validated image response. PNG format, dimensions, model, and seed are checked.

A saved request prints compact JSON instead of the full Base64 response:

```json
{
  "model": "moss",
  "seed": 42,
  "size": "512x512",
  "path": "/home/USER/.local/share/local-image-ai-service-images/<timestamp>_moss_42_<unique>.png"
}
```

Files use UTC timestamp/model/seed/unique filenames, exclusive creation, and mode `0600`.
Existing files are never overwritten; failed writes remove only the newly created partial file.
The default directory is retained by uninstall. No saving flag is sent to the HTTP API and no
service-wide storage setting is changed. The CLI reads the configured API key automatically.

Start the service first. `generate` neither starts the service nor switches models, and performs
no automatic retries. Invalid local parameters, HTTP errors, connection failures, and save failures
exit nonzero with an English error on stderr. Only `moss` is supported; `use moss` reloads its configuration.
A save failure occurs after inference; the CLI does not regenerate automatically.

## Errors and capacity

```json
{"error":{"message":"Unknown model; only moss is supported","type":"invalid_request_error","code":"model_not_found","param":"model"}}
```

| HTTP | Code / meaning |
| --- | --- |
| 400 | `invalid_size`, `invalid_seed`, `invalid_prompt`, `unsupported_parameter`, `unsupported_n`, or malformed JSON |
| 401 | `invalid_api_key` |
| 403 | `origin_not_allowed` |
| 404 | `model_not_found` or `not_found` |
| 408 / 413 / 415 | HTTP read deadline, body limit, or incorrect Content-Type |
| 429 | `generation_busy`, `Retry-After: 5`; there is no generation queue |
| 502 | `backend_failed`; runtime stopped, manual restart required |
| 503 | `backend_not_ready`, `/ready` unavailable, or `server_busy` when HTTP workers are full |
| 504 | `generation_timeout`; owned runtime stopped, no background generation remains |

The default total generation deadline is 300 seconds; process cleanup can take up to another
13 seconds. Use a client timeout of at least 330 seconds; the service CLI adds this margin.
An early client disconnect does not guarantee cancellation: a started generation can continue
until its service deadline, occupying the single generation slot. Errors do not trigger automatic
retries or model reloads.

The HTTP service creates no output URLs and saves no images. PNG bytes and responses stay in
memory. Optional CLI saving is performed by the client after receiving them.
