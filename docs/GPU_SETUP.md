# GPU setup

Nothing in PROJECT VOICE requires a GPU. The worker detects CUDA at runtime and uses it when
`PV_ENGINE_DEVICE=auto` (default) or `cuda`; otherwise everything runs on the CPU with ONNX
Runtime / PyTorch CPU kernels. **The build environment for this repository has no GPU, so the
CUDA paths below are implemented and unit-tested with fake engines but have not been executed on
real hardware here.**

## Requirements

| Component | Version | Notes |
|---|---|---|
| NVIDIA driver | ≥ 525 (CUDA 12.x capable) | `nvidia-smi` must work inside the container (`--gpus all` / compose `deploy.resources.reservations.devices`) |
| CUDA runtime | 12.x | provided by the PyTorch and onnxruntime-gpu wheels; no system toolkit needed |
| PyTorch | 2.x cu12x wheel | `pip install torch --index-url https://download.pytorch.org/whl/cu124` (pick the cu12x tag matching the driver); used by F5-TTS / IndicF5 |
| onnxruntime-gpu | 1.17+ (CUDA 12) | sherpa-onnx (ZipVoice, Whisper, Silero) runs on `provider="cuda"` only when the GPU build of sherpa-onnx is installed: `pip install sherpa-onnx --index-url https://k2-fsa.github.io/sherpa/onnx/cuda.html` (see the sherpa-onnx docs for the exact wheel for your CUDA/cuDNN) |
| cuDNN | 9 for CUDA 12 wheels | bundled with the wheels above |

`Dockerfile.worker.cuda` is the production image for GPU hosts; the CPU worker image works
everywhere.

## How the engine uses the GPU

* `hardware_snapshot()` reports `cuda_available`, GPU name and VRAM (`torch.cuda.mem_get_info`).
  It only imports torch when an NVIDIA driver is visible (`/proc/driver/nvidia/version`,
  `/dev/nvidia*` or `nvidia-smi` on PATH), so the API process stays light on CPU hosts.
* `EngineManager` loads an engine on `cuda` only if the engine declares `supports_cuda` and
  the memory guard sees `resource_requirements().vram_mb + 128 MB` free. Otherwise it loads on
  the CPU (when `PV_ENGINE_ALLOW_CPU_FALLBACK=true`) or refuses with a clear reason.
* CUDA OOM during inference → unload → `torch.cuda.empty_cache()` → retry once on CPU (if
  allowed) → the job records `cpu_fallback: true`. CUDA load failures (missing provider, OOM)
  fall back the same way.
* ZipVoice under sherpa-onnx uses ONNX Runtime's CUDA execution provider; F5-TTS loads in fp16 on
  CUDA (the package picks fp16 for compute capability ≥ 7) and fp32 on CPU.

## Sizing guidance

| Engine | VRAM (approx.) | RAM on CPU (approx.) | Notes |
|---|---|---|---|
| ZipVoice distilled (int8 or fp32 ONNX) | ~1 GB | 1.2 GB (int8) / 2.2 GB (fp32 loaded too) | 123 M parameters + Vocos; measured 0.8 GB RSS during CPU inference here |
| F5-TTS Base (OpenF5 / v1 Base) | ~2 GB fp16 incl. activations for 30 s | ~4.5 GB fp32 | 336 M parameters |
| F5-TTS Small (Hindi) | ~1.2 GB | ~2.5 GB | |
| IndicF5 | ~2.2 GB | ~4.5 GB | F5-TTS Base sized |
| Whisper base int8 (sherpa-onnx) | CPU is fine | 0.3 GB | ASR only |

**4 GB VRAM card (e.g. GTX 1650 / T4-class slice):** keep `PV_ENGINE_MAX_RESIDENT_MODELS=1`
(the default). ZipVoice (~1 GB) and one F5-family model (~2 GB fp16) each fit on their own, but
not together with headroom; the manager evicts the previous engine before loading the next, so
switching engines costs a reload (ZipVoice int8 loads in ~2.5 s on CPU here; F5 Base takes
longer). Leave `PV_ENGINE_ALLOW_CPU_FALLBACK=true` so a long paragraph that overflows VRAM
finishes on the CPU instead of failing.

**8 GB+ VRAM:** `PV_ENGINE_MAX_RESIDENT_MODELS=2` lets ZipVoice and one F5-family engine stay
resident; still one inference at a time per worker (the inference lock). Run one worker per GPU.

**CPU only (this environment, 2 cores):** ZipVoice fast tier runs at RTF ≈ 0.5–0.65 for English
(faster than real time), balanced ≈ 1.1, high (fp32) ≈ 1.7 — see `docs/AI_ENGINE.md` §8. Set
`PV_ENGINE_NUM_THREADS` to the physical core count.

## Checking

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
python -c "import onnxruntime as ort; print(ort.get_available_providers())"   # expect CUDAExecutionProvider
curl -s -b cookies http://localhost:8000/api/v1/system/hardware | jq
```

`/system/hardware` returns `device`, `cuda_available`, `gpu: {name, vram_total_mb, vram_used_mb}`,
`cpu_cores`, `ram_total_mb`, `ram_used_mb`, `disk_free_mb`, `torch_version`,
`onnxruntime_version` — all measured.
