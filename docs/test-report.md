# Test report — October 29, 2026

This report covers the MOSS-only service after removal of automatic anatomy screening.
Environment: Fedora Linux 44 KDE, RTX 5070 Laptop 8 GB, NVIDIA 615.78.08, CUDA 13.4,
Python 3.14.8. Inference uses the separate official `master-987-a77d362` installation.
No existing model weights were changed, moved, copied, or downloaded during this update.

## Quality update — current settings

The later quality update passed **32 automated tests** and three sequential real MOSS comparisons
using the original heavy-metal prompt and seed 42. The current defaults are **1024×1024, 50 Euler
steps, CFG 3.0, discrete scheduler, flow shift 5**. Sampling can be configured privately and is
validated before loading; unsupported API parameters remain rejected. Native PNG metadata confirms
the actual settings. The 1024×1024 / 50-step generation completed in 190.61 seconds with a maximum
observed total GPU memory use of 4,236 MiB. Semgrep again reported zero findings.

See [the measured comparison and quality guide](quality.md). Evidence is stored in
`~/.cache/local-image-ai-service/quality-unit-tests.log`, `quality-semgrep-report.json`, and the
`quality-comparison-*` directory named by `quality-comparison-current.txt`. The running service uses
the new quality settings. Its existing API limits, direct delivery, saving flags, weights, and
loopback binding are retained. The sections below describe the earlier 20-step validation.

## Automated validation

`python3 -m unittest discover -s tests -v` passed **30 tests**, including request-validation
subtests. Coverage includes MOSS-only configuration and API discovery; rejected non-MOSS IDs;
sizes, seeds, authentication, HTTP limits, concurrency, owned-process cleanup, and timeouts.

The direct-delivery regression test supplies an image for a prompt requesting a humanoid with
three arms. Its bytes are returned unchanged, without review metadata or any extra subprocess.
Install/upgrade tests remove obsolete reviewer code and settings and non-MOSS mappings, retain
custom ports, keep configuration private, and preserve all model data. Saving tests cover both
flags, no-save behavior, unique filenames, private files, collision protection, failed-write cleanup,
and error responses without creating output. Uninstall preservation is also tested in isolation.

## Real MOSS and lifecycle validation

`python3 tests/integration.py` passed at `2026-10-29T11:03:02+0100`. Models were never benchmarked in parallel.

| Check | Result |
| --- | --- |
| Separate repository and installed runtime | Passed; independent regular files and receipt SHA-256 values |
| Required model files | All four MOSS files readable |
| CUDA/backend | CUDA0 on the RTX 5070; no CPU fallback |
| systemd startup and API | Passed; `/health` and `/ready` report readiness |
| `/v1/models` | Only `moss`, loaded |
| Person/band generation | HTTP 200, Base64 PNG, no `anatomy_check` metadata |
| Invalid or retired model ID | HTTP 404 `model_not_found`, including `z-image` |
| Invalid size / count | HTTP 400 `invalid_size` / `unsupported_n` |
| Concurrent request | Immediate HTTP 429 while the single generation runs |
| Editing route | HTTP 404; no unsupported editing API advertised |
| Stop and restart | Old owned PIDs exited; new backend became ready |
| Stop during inference | Bounded shutdown; no background generation left |
| After stop | Ports 7861/17861 closed and no remaining owned GPU process |
| Login autostart | Unit `static`, not enabled; no automatic restart |

The generated band image was decoded, checked for dimensions, validated for every PNG chunk CRC,
and successfully decompressed. Native PNG metadata confirmed seed 42. Test images were created
only in a service-specific temporary directory and removed afterwards.

| Model | Size | Steps / CFG | Time | PNG bytes | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| moss | 512×512 | 20 / 3.0 | 21.89 s | 511,781 | `67ff8aefb628277817eb14b24b1d853880e052ecf56d010b5a7bfb1bf57a12e4` |

Fast startup after stopping an active generation initially exposed a port-probe defect: a plain
bind treated native `SO_REUSEPORT` connections in `TIME_WAIT` as an occupied listener. Startup
now probes for an actual TCP listener. Regression tests reproduce the native socket options,
allow recently closed connections, and still reject a genuinely occupied port. The final live run
also successfully started the service immediately after the active-stop test.

## CLI saving validation

`python3 tests/cli_integration.py` passed at `2026-10-29T11:03:39+0100` against the running MOSS service.
Both modes returned real 512×512 PNGs with valid CRCs, decompressed pixels, actual seed 42,
and private file permissions:

| CLI mode | Time | PNG bytes | SHA-256 |
| --- | --- | --- | --- |
| `--save-dir` | 20.19 s | 380,067 | `ea74981c866bbd517b339132e87ab670dc066a27ed692d5fded7eeded144e1b7` |
| `--save` | 14.96 s | 378,446 | `42151b2064af402f83457818f97f4f16b6ea289b81afc994ec3daca72c235cf7` |

The default-save test used a temporary home. All test images stayed inside the service's cache
and were removed afterwards. Invalid CLI size exited nonzero without creating output. The same
backend PID remained ready throughout both save tests. The final service was left running MOSS.

## Security and installation

Semgrep `p/python`: 151 rules over seven implementation files, **zero findings**.
`systemd-analyze --user verify` passed. Installed `service.py` and `manage.py` match the repository.
No reviewer Python module or bytecode remains in the installed application. Old reviewer data and
all existing weights are retained, but the reviewer is no longer loaded or executed.

The API remains loopback-only. `KillMode=control-group`, bounded termination, private configuration,
read-only access to home, and write access only to the service cache remain in place. Removal of
the CPU reviewer restores the generation-only RAM limits: 16 GiB high / 24 GiB maximum.

## Protected files and observed unrelated activity

The read-only SHA-256/mode/mtime comparison against the original October 28 audit confirms:

| Protected area | Entries | Current comparison |
| --- | --- | --- |
| `~/.local/bin/imgai` | 1 | Unchanged |
| `~/dev/local-ai/image-stack` | 363 | Unchanged, including workflow code and Git metadata |
| `~/.local/share/local-image-ai/models` | 10 | Unchanged, including all seven MOSS and Z-Image files |

The original audit also covered picture and game directories. Current picture contents differ
from that older snapshot: 249 added entries, 733 removed entries, and 16 modified entries under
`~/Pictures/AI-Generated`. Examples concern existing cathedral Blender/workflow projects. The
historical Riff-Racers comparison had already recorded concurrent project activity. These paths
were not write or cleanup targets of this implementation, and nothing was reset or repaired.
Consequently, this report does not claim that those entire directories stayed unchanged since
October 28. The API process cannot write there under its systemd filesystem restrictions.

## Scope and limitations

Only `moss` is supported by this service; other installed model weights remain available to their
original workflows. The earlier lifecycle run used Euler / 20 steps / CFG 3.0; the quality update above uses 50 steps. Images are delivered without
anatomy assessment, filtering, or automatic regeneration. These tests verify generation and
service behavior; they do not assess artistic quality or anatomical accuracy. No full resolution
benchmark or Open WebUI configuration change was performed. Documentation remains in English.

## Local evidence

```text
~/.cache/local-image-ai-service/moss-only-unit-tests.log
~/.cache/local-image-ai-service/moss-only-validation.log
~/.cache/local-image-ai-service/moss-only-integration-output.log
~/.cache/local-image-ai-service/integration-report.json
~/.cache/local-image-ai-service/moss-only-cli-integration-output.log
~/.cache/local-image-ai-service/cli-integration-report.json
~/.cache/local-image-ai-service/moss-only-semgrep-report.json
~/.cache/local-image-ai-service/moss-only-protected-integrity.json
~/.cache/local-image-ai-service/audit/before.json
~/.local/share/local-image-ai-service/runtime/receipt.json
```

Full manifests, local configuration, credentials, test PNGs, and binaries are not committed.
