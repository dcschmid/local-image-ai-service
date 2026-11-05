# Troubleshooting

Start with:

```bash
local-image-ai-service doctor
local-image-ai-service status
journalctl --user -u local-image-ai -n 100 --no-pager
nvidia-smi
```

## Port already in use

The previous, initially inactive `imgai-api.service` also uses port 7861 and internal port 7862.
The new service uses 7861 and internal port 17861. Both public APIs cannot bind 7861 together.
This service never terminates another process to resolve a conflict or changes the old unit.

```bash
ss -ltnp 'sport = :7861 or sport = :17861'
```

Stop the other service yourself if intended, or change the **new** service's public port and
configure its clients accordingly. Existing programs are not automatically reconfigured.

## GPU occupied or CUDA memory exhausted

At startup, other CUDA compute workloads cause model loading to be refused. The KDE compositor
is excluded. Other processes are never terminated. An `imgai` process started later can still
compete with this service. Before using the previous CLI or benchmarks:

```bash
local-image-ai-service stop
```

Restart afterwards if needed. On OOM, choose a smaller size and inspect logs; there are no automatic
retries. RAM limits do not reserve VRAM. `/health` can remain reachable while `/ready` returns 503.

## Missing files or load failure

`doctor` checks the configured model components. MOSS has four required files. Correct absolute paths in private JSON configuration; do not download,
rename, or move existing weights. MOSS requires `tokenizer_qwen3.5.json` in addition to its DiT,
encoder, and VAE. Failures appear in `/health.error` and the journal without retry loops.
After fixing the cause:

```bash
local-image-ai-service restart
```

## Missing CUDA runtime libraries

The separate runtime needs the three CUDA libraries recorded in `runtime/receipt.json`.
`cuda_lib` must point to its own absolute library directory. The previous installation is not
used as a runtime fallback. `doctor` must report CUDA0; CPU fallback is not silent.

## Wide recipe sizes fail after a runtime rebuild

Recipes wider or taller than 1024 px (for example `1216x832` and `832x1216`) are only accepted
for a model whose verification receipt matches the current runtime fingerprint, so compose can
answer `size: dimensions must be multiples of 64 between 256 and 1024`. Reinstalling the runtime
(`scripts/setup.sh`, `scripts/install-runtime.py` or a source rebuild) changes that fingerprint
and invalidates every receipt. Refresh them with one real render per model on the GPU:

```bash
local-image-ai-service stop
python3 scripts/verify-recipes.py --only lowpoly-world photo-portrait anima-portrait
python3 scripts/verify-formats.py            # optional: dropdown formats too
local-image-ai-service start
```

`verification.json` lives with the image library and survives reinstalls; the fingerprint decides.

## HTTP 404, 409, 429, or 504

404 `model_not_found`: choose an installed curated model from `local-image-ai-service models`; the five supported IDs are `moss`, `anima`, `flux-pixel`, `z-image` and `z-image-turbo`.
409 `model_not_loaded`: the compatibility API requires the selected model to be loaded with `local-image-ai-service use MODEL`. Guided CLI `render` and Studio jobs switch models automatically.
429: the synchronous compatibility API is busy; wait for its current generation. Studio and CLI `render` requests use the persistent job queue.
504: the owned runtime was stopped. Inspect logs and restart manually. Client timeouts must
allow the generation deadline plus process cleanup. Stopping the image service or changing its loaded model interrupts active requests.

## Z-Image completes with a blank white image

The initial Unsloth base GGUF completed jobs but produced uniform white frames on the tested CUDA setup. The current lockfile pins the runtime author’s compatible `z_image-Q4_0.gguf`. Stop the image service and rerun `python3 scripts/install-models.py z-image` to update its mapping, then restart. See [the measured fix and checkpoint revision](z-image-and-presets.md#z-image-setup). The public example builder rejects uniform frames; a successful runtime job alone does not prove visual quality.

## New models missing from MCP after an update

A long-running bridge retains its original model/preset schema. Reconnect or restart the MCP client so it starts the updated bridge. Until then, an old process can reject the expanded private configuration with `Only curated models may be configured`. Check the installed catalog separately with `local-image-ai-service models`.

## CLI saving or generation fails

`generate` requires a running, ready service. Use `local-image-ai-service start` first.
It does not implicitly start or switch the model. Check available options with:

```bash
local-image-ai-service generate --help
```

Choose either `--save` or `--save-dir DIRECTORY`. Without either flag, the CLI prints Base64 JSON
without writing an image. `--save-dir` creates missing directories after a valid image response.
An existing file cannot be used as the output directory. Check permissions and free disk space
when saving fails. Existing files are never overwritten; a write failure removes only its own
new partial file. No automatic retry occurs after generation or save failure.

The default output directory is `~/.local/share/local-image-ai-service-images`, outside the
installation and cache. It survives uninstall. Use an external custom directory if those images
should also survive; custom output inside the service cache remains disposable.

## systemd active but model not ready

`Type=simple` confirms only that the adapter started. Use `/ready` or the management command,
which waits for readiness. After a backend failure, the adapter stays reachable for diagnostics.
`Restart=no` is deliberate. For `start-limit-hit`, fix the cause first, then run
`systemctl --user reset-failed local-image-ai`.

## Permissions, browser requests, and authentication

Protect configuration and the optional key with `chmod 600`. Incorrect permissions prevent
startup. Browser origins are rejected; use API clients or server-side Open WebUI requests.
401 means a valid Bearer key is required. The service CLI reads its configured key automatically.

## Check integrity of existing projects

The initial installation recorded a full SHA-256 comparison; see the [test report](test-report.md).
Later comparisons may report legitimate concurrent changes. Do not reset them automatically.
The audit script writes only to the explicitly selected manifest and reads the protected roots.

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/audit.py "$HOME/.cache/local-image-ai-service/audit/before.json" --compare
```
