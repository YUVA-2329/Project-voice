"""PROJECT VOICE AI engine package.

Standalone: nothing in here imports ``app.core``, ``app.db`` or ``app.api``.  The heavy
dependencies (torch, onnxruntime via sherpa-onnx) are imported lazily inside the adapters, so
importing ``app.engine.types`` or ``app.engine.hardware`` from the API process is cheap.
"""
