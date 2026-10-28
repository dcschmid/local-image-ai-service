# Test report — October 28, 2026

Test environment: Fedora Linux 44 KDE, RTX 5070 Laptop 8 GB, NVIDIA 615.78.08, CUDA 13.4,
Python 3.14.8. Tests used only the separate official `master-987-a77d362` installation.
No model rebuild or download was needed.

## Initial automated validation

`python3 -m unittest discover -s tests -v`: the initial implementation passed **14 test groups**,
including 24 invalid request variants as subtests. Coverage includes model/parameter validation,
sizes, seeds, private file permissions, correct/wrong/missing Bearer keys, browser-origin rejection,
absent editing/chat/native administration routes, malformed JSON, immediate 429, bounded HTTP workers,
missing models, and load/generation timeouts that actually terminate owned test processes.
An isolated install/uninstall test with a simulated user manager also checks file permissions,
the Fedora timeout drop-in, and preservation of unrelated model, image, and project directories.
HTTP failure and timeout tests use explicit test doubles; real inference is tested separately.

`python3 tests/integration.py` tested real models **sequentially**, without parallel GPU benchmarks.

| Required check | Result |
| --- | --- |
| Separate repository / installation | Passed; separate Git directory, private config, runtime checksums |
| Required model files | All seven readable |
| CUDA/backend check | CUDA0 with RTX 5070, no CPU fallback |
| systemd startup and API reachability | Passed |
| `/v1/models` | Both IDs, exactly one loaded model |
| MOSS generation | 200, real 512×512 PNG, actual seed 42 |
| Z-Image generation | 200, real 512×512 PNG, actual seed 42 |
| Model switching | Previous runtime PID exited before the new model became ready |
| Stop / restart | Previous adapter/runtime PIDs exited; new runtime ready |
| Stop during generation | Passed; bounded shutdown, owned runtime terminated |
| Invalid model | 404 `model_not_found` |
| Invalid size | 400 `invalid_size` |
| Other configured model | 409 `model_not_loaded` |
| Multiple images | 400 `unsupported_n` for n=2 |
| Concurrent request during real inference | Immediate 429 for both models |
| After stop | Owned PIDs gone, ports 7861/17861 closed, no owned GPU processes |
| No login autostart | Unit `static`, not enabled, no automatic restarts |

Each response was Base64-decoded, checked for PNG signature and dimensions, validated for every
PNG chunk CRC, and successfully decompressed. Nontrivial pixel data and actual seed 42 were checked.
Test images existed only in a temporary directory under `~/.cache/local-image-ai-service` and
were removed afterwards.

Final initial full run at 11:44 local time, 512×512, including inference and the API response:

| Model | Steps / CFG | Time | PNG bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| moss | 20 / 3.0 | 21.20 s | 381,072 | `7cfb5e75d1a92fd41f7222c9d6e98e7bec021863dc6c0d467bf7ea0414566cfb` |
| z-image | 8 / 1.0 | 6.98 s | 365,149 | `f6176470009000b3176896436b94dff0ede5a42ab63fca7e557fac139560843c` |

A previous complete run also passed (18.61 s / 7.88 s). MOSS was not byte-identical across
separate processes with the same seed; deterministic PNG hashes are not promised.

`systemd-analyze --user verify` passed. Semgrep `p/python` ran 151 rules over executable Python
implementations with no findings. This report does not claim visual quality assessment, a full
size/prompt benchmark, a source rebuild, or a completed Open WebUI integration.

## English documentation and CLI saving update

All nine Markdown documents were translated into English. The separate service CLI now supports
`generate`, with opt-in `--save` and `--save-dir`. The HTTP service and existing `imgai` CLI were
not changed by this update.

The expanded automated suite passed **25 test groups**. New coverage includes no-save behavior,
default/custom directories, repeated seeds with distinct filenames, private file permissions,
exclusive creation on filename collisions, partial-write cleanup, API failures without output,
invalid image responses, flag validation, and an actual HTTP JSON/Bearer request. The uninstall
test also verifies retention of the separate default image directory.

`python3 tests/cli_integration.py` passed against the already running MOSS service at 12:41 local
time. Both saving modes produced real 512×512 PNGs with validated chunk CRCs, decompressed pixels,
and actual seed 42:

| CLI mode | Time | PNG bytes | SHA-256 |
| --- | --- | --- | --- |
| `--save-dir` | 19.99 s | 381,027 | `72e66d6db53013dc2334e52957b32291395210395c70e04047760d67f67acf04` |
| `--save` | 14.82 s | 381,796 | `02bc7203cc2e06eaa0463acb0fd4c2ea69308baa7e00d895cf7ee79683e2c118` |

The default-path test used a temporary home directory, so all test PNGs stayed inside the
service-specific temporary test folder and were removed afterwards. Invalid CLI size exited
nonzero without creating output. The existing service process/model remained ready throughout;
no stop, restart, or model switch was performed. The updated CLI module was installed atomically
because the user had started the service during this update. Semgrep again reported no findings.

## Existing file integrity

Before implementation, `scripts/audit.py` recorded **140,000 entries**, including SHA-256 file
content, modes, modification timestamps, and symlink targets. Nothing is reset automatically.
Baseline and comparison files stay in the service's own cache.

| Protected area | Baseline entries | Result |
| --- | --- | --- |
| `~/.local/bin/imgai` | 1 | Content, mode, and timestamp unchanged |
| `~/dev/local-ai/image-stack` | 363 | Unchanged, including character, kart, track, blueprint, repair, Blender code, and Git metadata |
| `~/.local/share/local-image-ai` | 12,391 | Unchanged, including all weights, shared files, previous runtime, and venv |
| Previous `imgai-api.service` | 1 | Unchanged |
| `~/Pictures/AI-Generated` | 3,543 | Unchanged; 3,126 regular files including existing images, worlds, and benchmarks |
| `~/dev/github/riff-racers` | 123,685 | Concurrent changes observed; details below |
| `~/.local/share/riff-racers` | 3 | Unchanged |
| `~/.local/share/riff_racers` | 13 | Unchanged |

The first comparison found no modified or removed baseline files and eight new scratch renders.
A later comparison found further concurrent activity: **33 added entries, 10,572 modified entries,
no removed entries**, all under `~/dev/github/riff-racers`. Rechecking modified entries found
**18 changed SHA-256 contents** and **10,554 metadata-only changes**.

The 18 content changes involved `.git/index`, two processed Rhythm-Kaur/Dance-Fusion GLBs, two
scratch-export GLBs, `rhythm-kaur-work.blend` and `.blend1`, plus Defold build artifacts and
build/version logs. Additions included scratch renders, capture logs, and directories/images under
`build/evidence/art-benchmark/rhythm-h1` and `rhythm-h2`. The full comparison is in the audit cache;
its summary is `audit/summary.json`.

The first eight added renders were:

```text
~/dev/github/riff-racers/build/scratch/rhythm-kaur/renders/
  cmp_s1_hero.png
  cmp_s1_ortho.png
  cmp_s1_top.png
  s1_back.png
  s1_front.png
  s1_hero.png
  s1_side.png
  s1_top.png
```

This implementation used no write operation on those paths. A separate Blender process had been
running since October 23. The source of the concurrent changes was not conclusively attributed.
The new systemd service has `ProtectHome=read-only` and write access only to its own cache.
No unrelated file or concurrent work was deleted, repaired, or reset.

It would be incorrect to claim that the entire Riff-Racers directory stayed unchanged throughout
the task. The verified result is that the **existing CLI, Image-AI source and workflows including
Git metadata, previous runtime/venv, all weights, and every file under `~/Pictures/AI-Generated`
remained unchanged**. Full integrity of Riff Racers, including its scratch Blender files, cannot
be asserted because of concurrent work. This task did not modify those files.

## Local evidence

```text
~/.cache/local-image-ai-service/audit/before.json
~/.cache/local-image-ai-service/audit/comparison.json
~/.cache/local-image-ai-service/audit/summary.json
~/.cache/local-image-ai-service/native-probe.json
~/.cache/local-image-ai-service/native-probe.log
~/.cache/local-image-ai-service/unit-tests.log
~/.cache/local-image-ai-service/integration-report.json
~/.cache/local-image-ai-service/integration-output.log
~/.cache/local-image-ai-service/semgrep-report.json
~/.cache/local-image-ai-service/cli-unit-tests.log
~/.cache/local-image-ai-service/cli-integration-report.json
~/.cache/local-image-ai-service/cli-integration-output.log
~/.cache/local-image-ai-service/cli-semgrep-report.json
~/.local/share/local-image-ai-service/runtime/receipt.json
```

Integrity comparison deliberately exits 1 when external changes are found and separates added,
modified, and removed entries. This is not a reason to alter unrelated work. Full manifests are
not committed to the repository.
