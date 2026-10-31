# Agent CLI checks — 2026-10-31

For the current four-model CLI, MCP and skill checks, see
[the agent integration report](agent-integration-test-report.md).

Historical report: the Anima low-poly profiles have since been retired. See [the current MOSS Low Poly workflow](moss-lowpoly.md). Measurements below describe the earlier installation.

The CLI now exposes all six curated profiles, 44 guided recipes, ten free-prompt
styles, seven aspect ratios and the Blender asset/view options. Agent commands
use JSON stdout for success and JSON stderr for errors. The existing compatibility
`generate` command retains its generation/storage behavior.

## Automated verification

- 102 Python tests passed, including 20 agent CLI scenarios against the real
  HTTP adapter with inference disabled and an isolated temporary archive.
- Discovery and preview covered all six profiles, free styles, Blender starters,
  Krea grid/palette settings, JSON stdin and conflicting input rejection.
- Job checks covered asynchronous batches, seed wraparound, direct lookup beyond
  the recent listing, cancellation, failures, timeouts that retain queued work,
  partial queue acceptance and a deliberately lost accepted-submission response.
  No failed or uncertain submission was automatically retried.
- Export checks covered byte-preserved PNG alpha/text metadata, native pixel
  companions, private permissions, repeat exports, corrupt image rejection and
  rollback after a simulated metadata-write failure. Archived files were retained.
- Authentication errors, argument errors and machine-readable health checks were
  verified without systemctl output or credentials in the JSON response.
- Semgrep scanned 27 source files with zero findings and zero errors.
- `git diff --check` passed.

## Real GPU CLI workflow

`scripts/verify-agent-cli.py` started an isolated HTTP service with a separate
configuration, archive and exports. CLI subprocesses used the normal parser and
HTTP client with that isolated configuration. Existing model/runtime paths were
read unchanged. No HOME override or credentials on command arguments were used.

| Model | Workflow | Output | Generation seconds |
| --- | --- | --- | ---: |
| Anima PSX | Compose Blender kart → async render → get job → wait/export | 768 × 768 PNG and JSON metadata, adapter strength 0.9, modeling version 1 | 35.98 |
| Krea Pixel Art | Synchronous render → native export → repeat export | 1024 × 1024 PNG, 32 × 32 native PNG and JSON metadata, prepared DoRA 32-grid weights | 37.30 |

The worker switched from the initial Anima Low Poly Style model to PSX and then
to Krea's prepared 32-grid variant. The repeated pixel export matched the first
PNG byte-for-byte and left the archive at exactly two generated jobs. Artifacts
and `report.json` are under
`~/.cache/local-image-ai-service/agent-cli-22o27n09/`.

## Installation and user data

The installed launcher passed `models`, filtered `catalog`/`recipes`, `presets`,
`formats`, `status --json` and a Blender `compose` request. Installed management,
agent CLI and Studio API modules matched the workspace bytes.

After restart, the private configuration matched its captured text exactly.
All 40 original archive records and the SHA-256 hashes/names of all 21 original
PNGs matched the baseline. The service was ready and idle on the original
`anima-lowpoly` selection; the installed compose check did not switch it.
Login autostart remained unchanged.
