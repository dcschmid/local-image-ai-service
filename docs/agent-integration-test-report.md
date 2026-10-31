# Agent CLI, MCP and skill verification — 2026-10-31

The current installation exposes four models, 44 guided recipes, ten free-prompt
styles, seven aspect ratios and the Blender asset/view options through the CLI.
The optional stdio MCP server provides 17 tools and a live catalog resource.
See [the integration guide](agents-integration.md) and
[complete inventory](../skills/local-image-ai/references/catalog.md).

## Automated checks

- The Python suite ran 114 tests: 113 passed; one optional NumPy weight-converter
  test was skipped in the isolated MCP environment. MCP tests themselves ran.
- Seven MCP scenarios exercised real authenticated HTTP routes with inference
  disabled, including a subprocess stdio client negotiating `2025-11-25`.
- Discovery covered all four model IDs, all recipes, low-poly filtering, full
  examples, style/format options and the catalog resource. Compose covered MOSS,
  Anima, Qwen and Krea without queuing work.
- Queue checks covered asynchronous batches, seed wraparound, bounded waits
  that leave pending jobs running, explicit cancellation, invalid parameters and
  unknown records. Literal `--help` prompt values remained ordinary user data.
- Export preserved PNG alpha/text metadata and native pixel bytes. Library
  tests covered paging, favorites, single/multiple deletion, and retention of
  already exported project files.
- Seven installer scenarios checked deterministic packages, complete recipe
  inventory, managed updates, preservation of local edits/unmanaged files,
  symlink refusal, instruction backups, idempotency and configuration rollback.
  Codex normalization of unrelated MCP entries is corrected by merging only the
  verified new server entry into the original configuration.
- Semgrep scanned all 27 application/script source files, including the new
  CLI/MCP/installer modules: zero findings and zero errors.
- Both repository and installed skills passed the skill-creator validator.

## Real GPU workflows

`scripts/verify-agent-cli.py --with-mcp` used a separate private configuration,
HTTP listener, archive and exports. It reused the configured runtime and weights
without modifying the user configuration. No HOME override or credentials on
command arguments were used.

| Model | Workflow | Output | Generation seconds |
| --- | --- | --- | ---: |
| MOSS | CLI compose → async render → get → wait/export | 768 × 768 Blender kart concept PNG and JSON, 30 steps, shift 5 | 61.61 |
| Krea Pixel Art | CLI synchronous render → native export → repeat export | 1024 × 1024 preview, 32 × 32 native PNG and JSON, prepared 32-grid DoRA | 37.79 |
| MOSS | MCP stdio discovery → compose → generate → wait → export | 768 × 768 Low Poly Anything fox scene PNG and JSON, 30 steps | 63.11 |

All three workflows passed. The worker switched MOSS → Krea's 32-grid profile →
MOSS. The repeated pixel export matched the first PNG byte-for-byte. The archive
contained exactly three generated jobs. Visual inspection found a readable
orange/blue kart, a coarse native-grid red mushroom icon and a faceted fox scene.
This verifies the workflow; it is not a model-quality benchmark or proof of
matched geometry between independent views.

Artifacts and `report.json` are under
`~/.cache/local-image-ai-service/agent-cli-09ix57k4/`.

## Installed integration and user data

The installed launcher passed a real stdio MCP client check: 17 tools, four
installed models, 44 guided presets, nine MOSS low-poly presets, ten styles,
seven ratios, the catalog resource, a track-overview compose request and library
listing. The local service remained ready and idle on MOSS.

The portable skill is installed in the current Codex skills directory; its
generated model/preset inventory matches the current catalog. A deterministic
`.skill` ZIP is available through `agents package`. Codex reports the
`local-image-ai` server enabled with the installed stdio launcher. The managed
local-image preference is present in the current Codex `AGENTS.md`.

After installation, all other Codex configuration values matched the backup
exactly and the original profile instructions remained intact. The private
service configuration hash, all 42 original archive records, and names/SHA-256
hashes of all 22 original PNG files matched the captured baseline. The normal
service was restored ready and idle on MOSS. Login autostart was not changed.

## Claude Code and OMP private profiles

The follow-up installation registered the stdio server in Claude's user scope
and OMP's native private MCP file. The portable skill was added to the source
and installed stack's private skill catalog, then linked through
`mm-profile-skills-sync` for both clients. Private profile rules prefer local
images; OMP also has native private context instructions.

- Claude's own `mcp get local-image-ai` reported **Connected**.
- An actual OMP private RPC startup, without sending a model prompt, exposed all
  17 MCP tools and `skill:local-image-ai`. Its selected provider/model remained
  `yolo-auto/qwen3.8-27b`; local image instructions were present. It exited cleanly
  with no stderr. A temporary verification overlay exposed tools directly
  instead of mounting them through OMP's device interface; no persisted setting
  changed.
- Switching Claude's managed skill links to Working removed the image skill.
  Its generated strict MCP configuration excluded the image server. Private
  links were restored afterward. OMP Working contains neither the skill nor the
  MCP entry.
- Existing OMP MCP entries, both OMP provider/model configurations and Working
  rules matched their captured baseline. Credentials were not copied or edited.
- `verify-profiles.sh` passed. The baseline had already reported missing OMP
  private skill links; the normal private skill sync restored those links.
- `mm-skill-audit --profile both --client all --strict` passed with zero problems;
  project-memory doctors passed for both profiles, and the runtime doctor passed.

Details are in [the client installation guide](agents-integration.md#claude-code-and-omp).
