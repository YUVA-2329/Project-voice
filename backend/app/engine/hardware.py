"""Hardware snapshot for ``GET /system/hardware``.

Importing this module is cheap: torch is only imported when an NVIDIA driver is present on the
host (otherwise CUDA cannot be available and the import would only cost ~1 s and ~300 MB in the
API process).  Every value is measured, never assumed.
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import psutil

from app.engine.config import EngineSettings, get_engine_settings


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def onnxruntime_version() -> str | None:
    for dist in ("onnxruntime-gpu", "onnxruntime"):
        version = _package_version(dist)
        if version:
            return version
    return None


def nvidia_driver_present() -> bool:
    """True when the host exposes an NVIDIA kernel driver (cheap filesystem/PATH checks)."""
    if Path("/proc/driver/nvidia/version").exists():
        return True
    if any(Path("/dev").glob("nvidia[0-9]*")):
        return True
    return shutil.which("nvidia-smi") is not None


def cuda_available() -> bool:
    """Real CUDA availability via torch, probed only when a driver exists and torch is installed."""
    if not nvidia_driver_present() or _package_version("torch") is None:
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def gpu_info() -> dict[str, Any] | None:
    if not cuda_available():
        return None
    import torch

    try:
        index = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(index)
        free_b, total_b = torch.cuda.mem_get_info(index)
        return {
            "name": str(props.name),
            "vram_total_mb": int(total_b // (1024 * 1024)),
            "vram_used_mb": int((total_b - free_b) // (1024 * 1024)),
        }
    except Exception:
        return None


def resolve_device(settings: EngineSettings | None = None) -> str:
    """The device the worker will use: ``cuda`` only if requested/auto *and* really available."""
    settings = settings or get_engine_settings()
    if settings.ENGINE_DEVICE == "cpu":
        return "cpu"
    if settings.ENGINE_DEVICE == "cuda":
        return "cuda" if cuda_available() else "cpu"
    return "cuda" if cuda_available() else "cpu"


def disk_free_mb(path: Path) -> int:
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        return int(shutil.disk_usage(probe).free // (1024 * 1024))
    except OSError:
        return 0


def hardware_snapshot(settings: EngineSettings | None = None) -> dict[str, Any]:
    """Exactly the ``/system/hardware`` payload from API_DOCUMENTATION.md."""
    settings = settings or get_engine_settings()
    vm = psutil.virtual_memory()
    cuda = cuda_available()
    return {
        "device": resolve_device(settings),
        "cuda_available": cuda,
        "gpu": gpu_info() if cuda else None,
        "cpu_cores": int(os.cpu_count() or psutil.cpu_count(logical=True) or 1),
        "ram_total_mb": int(vm.total // (1024 * 1024)),
        "ram_used_mb": int((vm.total - vm.available) // (1024 * 1024)),
        "disk_free_mb": disk_free_mb(settings.MODELS_DIR),
        "torch_version": _package_version("torch"),
        "onnxruntime_version": onnxruntime_version(),
    }


def free_ram_mb() -> int:
    avail = psutil.virtual_memory().available
    if sys.platform.startswith("win"):
        avail += psutil.swap_memory().free
    return int(avail // (1024 * 1024))


def free_vram_mb() -> int | None:
    if not cuda_available():
        return None
    import torch

    try:
        free_b, _total = torch.cuda.mem_get_info()
        return int(free_b // (1024 * 1024))
    except Exception:
        return None
