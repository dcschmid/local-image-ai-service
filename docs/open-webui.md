# Preparing for Open WebUI

Open WebUI was neither installed nor modified for this task. These settings are intended for
future manual setup; the integration itself has not been tested.

Under **Admin → Settings → Images**, select an OpenAI-compatible image generation backend:

| Setting | Value |
| --- | --- |
| Engine | OpenAI / `openai` |
| Image API base URL | `http://127.0.0.1:7861/v1` |
| Model | `moss` only |
| Size | `1024x1024` for quality; smaller sizes for faster previews |
| Count | 1 |
| API key | Configured Bearer key; if the service has none but the field is required, a dummy such as `local-unused` |
| Response format | Base64 / `b64_json` |

Keep image editing disabled. Do not send unsupported `quality`, `style`, or other parameters.
If the future Open WebUI version always sends these fields, the API will explicitly reject them;
adapt the integration for that version. This service is not an OpenAI chat backend.

The documented environment variables are:

```text
ENABLE_IMAGE_GENERATION=true
IMAGE_GENERATION_ENGINE=openai
IMAGES_OPENAI_API_BASE_URL=http://127.0.0.1:7861/v1
IMAGE_GENERATION_MODEL=moss
IMAGE_SIZE=1024x1024
IMAGES_OPENAI_API_KEY=<configured-key-or-local-unused>
```

Names were checked against the [official Open WebUI documentation](https://docs.openwebui.com/troubleshooting/image-generation/)
on October 28, 2026. Production Open WebUI validation remains outside this task.

Select `moss` in Open WebUI. Other model IDs return 404. MOSS images are delivered directly,
without an anatomy checker or hidden review metadata. Only one generation runs at a time;
additional requests receive 429.

The service now defaults to 50 steps, CFG 3.0, and 1024×1024 when size is omitted. Open WebUI
sends its own image size: its existing setting is not changed by a service update. Select
1024×1024 manually to use the tested quality resolution. Allow at least 330 seconds for the
request, matching the service's generation deadline plus cleanup. See [quality notes](quality.md)
for measured costs and a clearer four-musician prompt. No automatic prompt rewrite is performed.

The CLI `--save` and `--save-dir` flags apply only to that CLI invocation. They do not enable
server-side saving for Open WebUI or other HTTP clients.

## Container networking

Inside a normal Docker bridge container, `127.0.0.1` refers to the container itself. A host
service bound to `127.0.0.1` is normally **not** reachable through `host.docker.internal` or
`host-gateway` either: the hostname does not change the service's bind address.

For a future Linux setup using host networking (`network_mode: host`), the base URL remains
`http://127.0.0.1:7861/v1`. Host networking is also described as a Linux option in the
[official Docker guide](https://docs.docker.com/ai/model-runner/openwebui-integration/).
Alternatively, a deliberately configured local tunnel to the adapter port could be used;
that would be a separate networking decision.

No containers, tunnels, firewall rules, or LAN exposure were configured. The service accepts
only loopback. An API key alone does not make it reachable through a container gateway.
