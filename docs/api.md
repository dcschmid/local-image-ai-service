# HTTP API and CLI generation

Base URL: `http://127.0.0.1:7861/v1`, for the compatibility image-generation API. The [studio API](studio.md) additionally handles jobs,
editing and history. No public network exposure or CORS access. Same-origin browser access is
allowed only under `/studio/`; Open WebUI calls `/v1` from its server. Optional Bearer key: see [configuration](configuration.md).

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/v1/models` | OpenAI model list containing configured curated models, with `installed`, `loaded`, and `capabilities` |
| POST | `/v1/images/generations` | Synchronous generation of exactly one Base64 PNG |
| GET | `/health` | 200 for a live adapter; `status`, `active_model`, `backend_pid`, `error`, and `busy` |
| GET | `/ready` | 200 with a ready backend, otherwise 503 |

Chat, embeddings, video, native SDAPI and native administration are unavailable on the service port.
Image editing is exposed through validated studio jobs. MOSS is configured for text-to-image.
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
| `model` | Optional; defaults to the loaded model. Unknown model: 404; different loaded model: 409 |
| `prompt` | Required nonblank string, up to 16,000 characters |
| `seed` | Optional local extension; integer 0–2147483647, otherwise generated randomly |
| `size` | Optional, default `1024x1024`; `WIDTHxHEIGHT`, each 256–1024 and a multiple of 64; rectangles accepted |
| `n` | Optional; only integer 1. Request more images sequentially |
| `response_format` | Optional; only `b64_json` |
| `output_format` | Optional; only `png` |
| `user` | Optional string up to 256 characters; accepted as compatibility metadata, unused and not stored |

Optional local extensions: `steps` (1–100), `cfg_scale` (finite, 1–12), `sampler`
(`euler`, `euler_a`, `heun`, `dpm++2m`) and `negative_prompt` (up to 16,000 characters).
The curated profiles are `moss`, `anima`, `qwen21`, `krea-pixel`, `z-image` and `z-image-turbo`. Low-poly recipes use MOSS without a separate adapter; see [the MOSS guide](moss-lowpoly.md).
Krea Pixel Art and Z-Image Turbo require CFG 1 and an empty negative prompt. Z-Image supports ordinary CFG and negative prompting; [its guide](z-image-and-presets.md) lists the defaults for both variants.
All other parameters receive 400, including `quality`, `style`, `background`, `output_compression`, and arbitrary model paths.
Administrative `sampling` controls the MOSS defaults (50 steps, CFG 3.0). Other
profiles use their catalog defaults; request overrides take precedence without
restarting, subject to the distilled-model restrictions. See [configuration](configuration.md).
Prompts containing `sd_cpp_extra_args` or LoRA control tags are rejected. The adapter translates
the validated seed and sampling overrides into the documented native extension. Maximum request body: 64 KiB;
JSON object, `Content-Type: application/json`, exactly one `Content-Length`, no chunked requests.

Guided clients should use each model’s `formats` from `GET /studio/api/catalog`
for final and draft dimensions. Z-Image’s 3:2 and 2:3 sizes are 960×640 and
640×960. Studio jobs can also use larger dimensions that have been verified for
the exact local components; the compatibility route retains its 1024-pixel limit.

## Generate through the service CLI

For guided recipes, automatic queued model changes, Blender references, pixel
variants, job control and native PNG exports, see the [agent CLI](agent-cli.md).
The existing compatibility `generate` command below keeps its original behavior.

Additional authenticated Studio routes support direct record lookup:
`GET /studio/api/jobs/<id>` and `GET /studio/api/gallery/<id>`. IDs must contain
32 lowercase hexadecimal characters; missing or deleted records return 404.

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
exit nonzero with an English error on stderr. `use MODEL` loads a configured curated model; `use moss` also reloads its configuration.
A save failure occurs after inference; the CLI does not regenerate automatically.

The studio's guided `/studio/api/compose` and `/studio/api/jobs` routes also accept
`modeling_view` and `modeling_asset` for low-poly recipes. These are validated
recipe inputs, not compatibility API parameters. See [Blender reference options
and an example request](blender-references.md#settings-and-compatibility).

## Errors and capacity

```json
{"error":{"message":"Unknown model","type":"invalid_request_error","code":"model_not_found","param":"model"}}
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

The compatibility HTTP API creates no output URLs and saves no images. Optional CLI saving
is performed by the client. Studio jobs separately save PNGs and metadata automatically.
