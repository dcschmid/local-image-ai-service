# Automatic anatomy screening

Every generated image is screened locally before the HTTP response, including images requested
directly through the API. This is always on in the installed configuration; no prompt keyword
or CLI flag is required. The existing `imgai` CLI and its workflows are not involved.

The reviewer is **Qwen3.5-9B Q4_K_M**, using the existing MOSS text-encoder file read-only plus
a separate **918 MB vision projector**. The text encoder is never copied or downloaded again.
The inference binary is a separately built, pinned `llama-mtmd-cli` from llama.cpp.
Upstream labels this CLI experimental; its pinned invocation, timeouts, and process cleanup are tested here.
CUDA, Vulkan, OpenCL, and RPC backends are disabled at build time. Each check also explicitly
uses `--device none`, `--n-gpu-layers 0`, `--no-mmproj-offload`, and `--offline`.
No chat endpoint or additional network listener is exposed.

## Important accuracy limit

**This is screening, not a guarantee of correct anatomy.** Calibration found that local models
can overlook a plainly drawn third leg or invent defects in a normal figure. Merely returning
two estimated arms and two estimated legs is not reliable enough to approve a person.

Consequently, this implementation **never automatically approves an image in which the reviewer
detects a person**. A clear estimated extra-limb count can reject it; otherwise it requires human
review. A smaller 2B model and an alternative 4B model were evaluated and were not adopted because
they missed the controls. The selected 9B profile detected the third-arm control but also missed
the actual count in the third-leg control. That failure remains documented, not counted as a
successful limb-detection test.

Person detection itself can also be wrong. Small people, crowds, overlapping bodies, portraits,
stylized anatomy, and cropped or occluded limbs need particular care. Normal disability,
prostheses, and artistic proportions are not proof of a generation defect.

## Results and image handling

| Result | HTTP behavior | Meaning |
| --- | --- | --- |
| `NOT_APPLICABLE` | 200, image returned | Reviewer reported no people; not proof that no person exists |
| `REVIEW_REQUIRED` | 200, image returned with assessment | Person detected or assessment uncertain; a human must inspect it |
| `ISSUE_DETECTED` | 422 `anatomy_rejected`, image withheld | Reviewer clearly estimated more than two arms or legs for a person |
| Checker unavailable, invalid output, or process failure | 503, image withheld | No unchecked image is returned as successfully screened |
| Checker timeout | 504 `anatomy_timeout`, image withheld | Only the owned CPU checker process is terminated |

Subjective claims such as “deformed joints” without an extra-limb count cause review, not an
automatic rejection. Observations are checked for schema consistency. Per-person counts are
not added together. There is no `PASS` or anatomy-correct status.

Successful responses add a local extension alongside the standard image fields:

```json
{
  "data": [{"b64_json": "<PNG as Base64>"}],
  "model": "moss",
  "seed": 42,
  "anatomy_check": {
    "status": "REVIEW_REQUIRED",
    "checked": true,
    "backend": "local_cpu",
    "model": "Qwen3.5-9B-Q4_K_M",
    "people_present": "yes",
    "human_review_required": true,
    "summary": "Manual anatomy review required; automated limb estimates can miss defects.",
    "people": [],
    "issues": [],
    "model_summary": "<unverified reviewer observations>",
    "limitation": "Automatic visual screening can miss defects or flag valid anatomy; it is not a correctness guarantee."
  }
}
```

The service CLI preserves this report both in full JSON output and in compact `--save` output.
It also prints a review notice to stderr for uncertain/person images. Such images are still saved
when saving was explicitly requested; saving does not imply approval. Rejected images are not saved.
The CLI refuses to save a response missing its required assessment when checking is enabled.

Rejections include `error.anatomy_check`, the model, and the actual seed, without image bytes.
There is no automatic retry or silent seed change. Choose a different seed or revise the prompt
for a new attempt. No editing or automatic repair endpoint is added.

## Resources, privacy, and lifecycle

Checks run **after GPU inference** on the CPU, with at most eight threads and one check at a time.
The generation admission slot remains occupied for the whole request. Additional generation
requests still receive 429, including while the CPU reviewer is running. Health requests remain
available; `/health.anatomy_check` reports enablement, readiness, CPU activity, and the last error.

The checker loads for each request and exits afterwards. There is no persistent second model
on the GPU. Expect tens of seconds of additional CPU latency. The default checker timeout is
180 seconds, separate from the 300-second image generation deadline. The service CLI allows
510 seconds by default; other clients should allow at least that much time.

The unit allows 20 GiB before memory pressure and caps the entire group at 28 GiB. CPU quota
remains 800%. The existing image-generation CUDA/offload settings are unchanged. Core dumps are
disabled. Service stop and timeout handling terminate only owned child processes; other GPU or
Blender work is never stopped.

Images are processed locally in temporary subdirectories of the service cache and deleted after
checking. Original prompts are not passed as reviewer instructions; image text is treated as
untrusted data. Runtime inference is offline. Setup alone fetches pinned source/projector assets
and verifies checksums. No weights or image fixtures are committed to Git.

## Setup and maintenance

Requires Git, CMake, Ninja, and a C++ compiler to build the CPU runtime. The initial checker
installation was explicitly authorized. For a fresh setup or a rebuild:

```bash
cd ~/dev/github/local-image-ai-service
python3 scripts/install-anatomy.py
# For a shared encoder at a custom absolute path instead:
# python3 scripts/install-anatomy.py --shared-model /absolute/path/Qwen3.5-9B-Q4_K_M.gguf
local-image-ai-service stop
python3 scripts/install.py
local-image-ai-service doctor
local-image-ai-service start
```

Pins, sizes, and checksums are in [anatomy.lock.json](../anatomy.lock.json). Setup checks the shared
encoder checksum without modifying it. Default settings are in [configuration.md](configuration.md).
If its path differs, set `anatomy.model` to the verified shared encoder path before restarting.
No model is fetched during a service start or generation request. `anatomy.enabled=false` is an
explicit administrative opt-out, reported as `DISABLED`, never a successful assessment.

Uninstall removes this service's CPU binary and separately installed projector. It retains the
original shared MOSS encoder and all existing image-generation models and pictures.

Sources: [original Qwen model](https://huggingface.co/Qwen/Qwen3.5-9B),
[GGUF producer and projector](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF), and
[pinned llama.cpp multimodal implementation](https://github.com/ggml-org/llama.cpp/tree/620d2225cc436ab0b001e3200e590e3b286ef9ab/tools/mtmd).

## Tests

```bash
python3 -m unittest discover -s tests -v
# Real CPU reviewer, code-drawn controls, no GPU generation:
python3 tests/anatomy_integration.py
```

The real CPU evaluation reports conservative-policy results separately from detection accuracy.
Its report explicitly records whether the third leg was counted; a missed third leg is not
described as correctly detected merely because the image requires manual review.
