#!/usr/bin/env bash
# One-shot fresh installation for local-image-ai-service.
#
# Runs the documented steps in order, reusing the tested per-part scripts:
#   1. dependency checks
#   2. build the Studio (npm)
#   3. install the inference runtime (copy a known build, or build from source)
#   4. install the application + user unit (scripts/install.py)
#   5. fill the private config (gpu_uuid, runtime paths, MOSS model paths)
#   6. doctor
#   7. install optional model weights (scripts/install-models.py) and start
#
# It never enables login autostart. Stop the service first if it is running.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVICE="local-image-ai.service"
RUNTIME_DIR="$HOME/.local/share/local-image-ai-service/runtime"
CONFIG="$HOME/.config/local-image-ai-service/config.json"
OLD_MODELS="$HOME/.local/share/local-image-ai/models"

# Known-good runtime build (see docs/installation.md). Override with --runtime-*.
RUNTIME_BINARY="$HOME/.local/share/local-image-ai/engines/sd-install/bin/sd-server"
RUNTIME_CUDA_LIB="$HOME/.local/share/local-image-ai/engines/cuda/lib"
RUNTIME_SOURCE="$HOME/.local/share/local-image-ai/engines/stable-diffusion.cpp"
# Portable runtime archive (see scripts/package-runtime.py). Empty = auto-detect in dist/.
RUNTIME_ARCHIVE=""

MODELS=""            # space-separated model ids to install (default: none)
BUILD_RUNTIME=0      # 1 = build the pinned runtime from source
CUDA_TOOLKIT=""      # CUDA 13.4 toolkit root (auto-detected when --build-runtime)
SKIP_STUDIO=0
NO_START=0

usage() {
  cat <<'EOF'
Usage: scripts/setup.sh [options]

Options:
  --models <ids...>     Model weights to download (anima z-image z-image-turbo flux-pixel).
                        Default: none (MOSS is reused from the existing installation).
  --runtime-archive <p> Install the runtime from a portable archive produced by
                        scripts/package-runtime.py. Default: auto-detect
                        dist/runtime-<revision>.tar.zst.
  --build-runtime       Build the pinned stable-diffusion.cpp runtime from source
                        (needs a CUDA 13.4 toolkit; auto-detected if not given).
  --cuda-toolkit <dir>  CUDA 13.4 toolkit root (default: auto-detected).
  --runtime-binary <p>  sd-server binary to copy (known-good build fallback).
  --runtime-cuda-lib <p> CUDA library dir to copy (known-good build fallback).
  --runtime-source <p>  stable-diffusion.cpp source at the pinned revision.
  --skip-studio         Skip the Studio build (use an existing studio/dist).
  --no-start            Do not start the service at the end.
  -h, --help            Show this help.

Runtime install order: --build-runtime, then --runtime-archive / dist/ archive,
then a known-good build at the default paths.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --models) shift; MODELS="$*"; break ;;
    --build-runtime) BUILD_RUNTIME=1; shift ;;
    --cuda-toolkit) CUDA_TOOLKIT="$2"; shift 2 ;;
    --runtime-archive) RUNTIME_ARCHIVE="$2"; shift 2 ;;
    --runtime-binary) RUNTIME_BINARY="$2"; shift 2 ;;
    --runtime-cuda-lib) RUNTIME_CUDA_LIB="$2"; shift 2 ;;
    --runtime-source) RUNTIME_SOURCE="$2"; shift 2 ;;
    --skip-studio) SKIP_STUDIO=1; shift ;;
    --no-start) NO_START=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

step() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mSetup failed: %s\033[0m\n' "$*" >&2; exit 1; }

# --- 1. Dependencies -------------------------------------------------------
step "1/7 Checking dependencies"
need() { command -v "$1" >/dev/null 2>&1 || fail "missing required tool: $1"; }
need python3
need npm
need git
need systemctl

python3 - <<'PY' || fail "Python must be 3.11+ with Pillow 12.3+"
import sys
assert sys.version_info >= (3, 11), f"Python {sys.version} < 3.11"
import PIL
ver = tuple(int(x) for x in PIL.__version__.split('.')[:2])
assert ver >= (12, 3), f"Pillow {PIL.__version__} < 12.3"
print(f"  python {sys.version.split()[0]}, Pillow {PIL.__version__}")
PY

if ! nvidia-smi >/dev/null 2>&1; then
  fail "nvidia-smi not working; the NVIDIA driver must be installed"
fi
GPU_UUID="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -1 | tr -d '[:space:]')"
[[ "$GPU_UUID" =~ ^GPU-[0-9a-fA-F-]+$ ]] || fail "could not read a valid NVIDIA GPU UUID"
echo "  GPU: $GPU_UUID"

if [[ "$BUILD_RUNTIME" -eq 1 ]]; then
  if [[ -z "$CUDA_TOOLKIT" ]]; then
    for cand in /usr/local/cuda /usr/local/cuda-13.4 /usr/local/cuda-13* \
                "$HOME/.local/share/local-image-ai/engines/cuda" /opt/cuda*; do
      [[ -x "$cand/bin/nvcc" ]] && { CUDA_TOOLKIT="$cand"; break; }
    done
  fi
  [[ -n "$CUDA_TOOLKIT" && -x "$CUDA_TOOLKIT/bin/nvcc" ]] || \
    fail "no CUDA 13.4 toolkit found; pass --cuda-toolkit <dir> or drop --build-runtime"
  need cmake
  need ninja
  echo "  CUDA toolkit: $CUDA_TOOLKIT"
fi

# Stop a running service so the installers can replace files safely.
if systemctl --user is-active --quiet "$SERVICE"; then
  echo "  stopping running service"
  systemctl --user stop "$SERVICE"
fi

# --- 2. Studio -------------------------------------------------------------
if [[ "$SKIP_STUDIO" -eq 1 ]]; then
  step "2/7 Studio (skipped)"
  [[ -f studio/dist/index.html ]] || fail "studio/dist/index.html missing; build it or drop --skip-studio"
else
  step "2/7 Building the Studio"
  npm ci --prefix studio
  npm run build --prefix studio
  [[ -f studio/dist/index.html ]] || fail "studio build did not produce studio/dist/index.html"
fi

# --- 3. Runtime -------------------------------------------------------------
step "3/7 Installing the inference runtime"
if [[ "$BUILD_RUNTIME" -eq 1 ]]; then
  CUDA_TOOLKIT_ROOT="$CUDA_TOOLKIT" bash scripts/build-runtime.sh
elif [[ -z "$RUNTIME_ARCHIVE" ]]; then
  # Auto-detect the portable archive in dist/ (see scripts/package-runtime.py).
  for cand in "$ROOT"/dist/runtime-*.tar.zst; do
    [[ -f "$cand" ]] && { RUNTIME_ARCHIVE="$cand"; break; }
  done
fi
if [[ -n "$RUNTIME_ARCHIVE" ]]; then
  [[ -f "$RUNTIME_ARCHIVE" ]] || fail "runtime archive not found: $RUNTIME_ARCHIVE"
  python3 - "$RUNTIME_ARCHIVE" "$RUNTIME_DIR" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path
archive, runtime_dir = Path(sys.argv[1]), Path(sys.argv[2])
# The manifest sits next to the archive; the repo root is the current directory.
manifest_path = archive.with_name(archive.name.replace(".tar.zst", ".manifest.json"))
if not manifest_path.is_file():
    raise SystemExit(f"missing manifest next to archive: {manifest_path}")
manifest = json.loads(manifest_path.read_text())
def digest(p):
    with p.open("rb") as s:
        return hashlib.file_digest(s, "sha256").hexdigest()
if digest(archive) != manifest["archive_sha256"]:
    raise SystemExit("archive checksum does not match its manifest")
runtime_dir.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, "r:zst") as tar:
    for member in tar.getmembers():
        if not member.isfile():
            continue
        dest = runtime_dir / member.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tar.extractfile(member) as src, dest.open("wb") as out:
            out.write(src.read())
        dest.chmod(0o755 if member.name.startswith("bin/") else 0o644)
# Verify every file against the repo pin (runtime.lock.json).
lock = json.loads(Path("runtime.lock.json").read_text())
for rel, want in lock["installed_reference_sha256"].items():
    got = digest(runtime_dir / rel)
    if got != want:
        raise SystemExit(f"runtime file does not match the pin: {rel}")
print(f"  installed {len(lock['installed_reference_sha256'])} runtime files from {archive.name}")
PY
else
  [[ -x "$RUNTIME_BINARY" ]] || fail "no runtime source: pass --runtime-archive, --build-runtime, or a known-good build at the default paths"
  [[ -d "$RUNTIME_CUDA_LIB" ]] || fail "CUDA lib dir not found: $RUNTIME_CUDA_LIB"
  [[ -d "$RUNTIME_SOURCE/.git" ]] || fail "runtime source not a git checkout: $RUNTIME_SOURCE"
  python3 scripts/install-runtime.py \
    --binary "$RUNTIME_BINARY" \
    --cuda-lib "$RUNTIME_CUDA_LIB" \
    --source "$RUNTIME_SOURCE"
fi
[[ -x "$RUNTIME_DIR/bin/sd-server" ]] || fail "runtime not installed at $RUNTIME_DIR/bin/sd-server"
echo "  runtime: $("$RUNTIME_DIR/bin/sd-server" --version 2>/dev/null || echo installed)"

# --- 4. Application ---------------------------------------------------------
step "4/7 Installing the application"
python3 scripts/install.py

# --- 5. Configuration -------------------------------------------------------
step "5/7 Filling the private configuration"
python3 - "$GPU_UUID" "$RUNTIME_DIR" "$OLD_MODELS" <<'PY'
import json, os, sys
from pathlib import Path

gpu_uuid, runtime_dir, old_models = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
config = Path.home() / ".config/local-image-ai-service/config.json"
cfg = json.loads(config.read_text())

# Runtime paths point at the service's own runtime directory.
cfg["runtime"] = str(runtime_dir / "bin/sd-server")
cfg["cuda_lib"] = str(runtime_dir / "lib")
cfg["gpu_uuid"] = gpu_uuid

# MOSS is reused from the existing installation. Fill any missing role by
# matching the known file names under the old models/moss directory.
moss = cfg["models"].setdefault("moss", {})
moss_dir = old_models / "moss"
def find(pred):
    if not moss_dir.is_dir():
        return None
    for p in sorted(moss_dir.iterdir()):
        if p.is_file() and pred(p.name):
            return str(p)
    return None
fill = {
    "diffusion": lambda n: n.startswith("MOSS"),
    "llm": lambda n: n.startswith("Qwen"),
    "vae": lambda n: n.endswith(".safetensors"),
    "tokenizer": lambda n: n.endswith(".json"),
}
changed = []
for role, pred in fill.items():
    if not moss.get(role) or not Path(moss[role]).is_file():
        found = find(pred)
        if found:
            moss[role] = found
            changed.append(role)

tmp = config.with_suffix(".json.new")
tmp.write_text(json.dumps(cfg, indent=2) + "\n")
os.replace(tmp, config)
config.chmod(0o600)
print(f"  gpu_uuid: {gpu_uuid}")
print(f"  runtime:  {cfg['runtime']}")
if changed:
    print(f"  MOSS paths filled from {moss_dir}: {', '.join(changed)}")
else:
    print("  MOSS paths: already set")
missing = [r for r in ("diffusion", "llm", "vae", "tokenizer") if not moss.get(r) or not Path(moss[r]).is_file()]
if missing:
    print(f"  WARNING: MOSS missing {missing}; set them in {config} before rendering")
PY

# --- 6. Doctor ---------------------------------------------------------------
step "6/7 Running doctor"
local-image-ai-service doctor

# --- 7. Models + start -------------------------------------------------------
step "7/7 Models and start"
if [[ -n "$MODELS" ]]; then
  # shellcheck disable=SC2086
  python3 scripts/install-models.py $MODELS
else
  echo "  no extra models requested (MOSS reused from the existing installation)"
fi

if [[ "$NO_START" -eq 1 ]]; then
  echo "  --no-start: service left stopped"
else
  systemctl --user start "$SERVICE"
  sleep 2
  systemctl --user is-active --quiet "$SERVICE" || fail "service did not start; check: local-image-ai-service logs"
  echo "  service: active"
fi

printf '\n\033[1;32mSetup complete.\033[0m\n'
echo "  Studio:  local-image-ai-service studio"
echo "  Status:  local-image-ai-service status"
echo "  Models:  local-image-ai-service use <model>"
