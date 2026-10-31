#!/usr/bin/env bash
# CPU-only tooling for DoRA conversion, isolated from the running CUDA service.
set -euo pipefail
source_dir="${1:?Pass a clean stable-diffusion.cpp source directory at the pinned revision}"
revision=a77d3623180b2bc1886f3dd04c0aa04156a987ef
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$revision" ]] || { echo 'Unexpected source revision' >&2; exit 1; }
[[ -z "$(GIT_OPTIONAL_LOCKS=0 git -C "$source_dir" status --porcelain --untracked-files=no)" ]] || { echo 'Source must be clean' >&2; exit 1; }
task_root="$HOME/.cache/local-image-ai-service/krea-converter"
python3 -m venv --system-site-packages "$task_root/venv"
"$task_root/venv/bin/pip" install 'gguf==0.19.0'
cmake -S "$source_dir/ggml" -B "$task_root/ggml-build" -DBUILD_SHARED_LIBS=ON \
  -DGGML_CUDA=OFF -DGGML_OPENMP=OFF -DGGML_BUILD_TESTS=OFF -DGGML_BUILD_EXAMPLES=OFF
cmake --build "$task_root/ggml-build" --target ggml-base -j4
