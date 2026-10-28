#!/usr/bin/env bash
# Reproduce a separate official build. No writes to the old source or toolkit.
set -euo pipefail
: "${CUDA_TOOLKIT_ROOT:?Set CUDA_TOOLKIT_ROOT to an existing CUDA 13.4 toolkit}"
task_root="$HOME/.cache/local-image-ai-service/build"
source_dir="$task_root/stable-diffusion.cpp"
revision=a77d3623180b2bc1886f3dd04c0aa04156a987ef
mkdir -p "$task_root"
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --no-checkout https://github.com/leejet/stable-diffusion.cpp.git "$source_dir"
fi
git -C "$source_dir" checkout --detach "$revision"
git -C "$source_dir" submodule update --init --recursive
export CUDACXX="$CUDA_TOOLKIT_ROOT/bin/nvcc"
export PATH="$CUDA_TOOLKIT_ROOT/bin:$PATH"
export LIBRARY_PATH="$CUDA_TOOLKIT_ROOT/lib:${LIBRARY_PATH:-}"
cmake -S "$source_dir" -B "$task_root/output" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSD_CUDA=ON -DSD_BUILD_EXAMPLES=ON \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER="$CUDACXX" \
  -DCUDAToolkit_ROOT="$CUDA_TOOLKIT_ROOT" -DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler
cmake --build "$task_root/output" --target sd-server -j4
python3 "$(dirname "$0")/install-runtime.py" --rebuilt \
  --source "$source_dir" --binary "$task_root/output/bin/sd-server" --cuda-lib "$CUDA_TOOLKIT_ROOT/lib"
