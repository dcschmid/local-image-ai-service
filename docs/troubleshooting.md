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

`doctor` checks both models. Correct absolute paths in private JSON configuration; do not download,
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

## HTTP 409, 429, or 504

409: load the requested model with `use`, then retry.
429: wait for the current generation; there is no job queue.
504 `generation_timeout`: the GPU runtime was stopped; inspect logs and restart manually.
504 `anatomy_timeout`: only the CPU checker was stopped; the healthy GPU runtime is retained.
Client timeouts must allow generation, CPU review, and cleanup. Stop and model switching cancel active requests.

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

## Anatomy review, rejection, or checker failure

The installed service checks every image on CPU. `REVIEW_REQUIRED` is expected for detected
people: real tests showed extra legs can be missed, so no automatic anatomy approval is offered.
The CLI still saves review images when explicitly requested and prints a notice. A 422
`anatomy_rejected` response withholds an image with clearly estimated extra limbs. Inspect the
report and try another seed or prompt; there is no automatic retry or seed substitution.

503 `anatomy_unavailable`/`anatomy_failed` and 504 `anatomy_timeout` also withhold the image.
Use `doctor` and `/health.anatomy_check` to inspect readiness, busy state, and the last error.
Check the configured CPU binary, shared MOSS encoder, and separate vision projector. Rebuild with
`python3 scripts/install-anatomy.py` if necessary; do not move or redownload existing image models.
Allow at least 510 seconds in external clients. See [anatomy.md](anatomy.md) for accuracy limits.

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
