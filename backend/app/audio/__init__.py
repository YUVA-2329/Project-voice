"""Audio intelligence pipeline: probe → decode → analyse → VAD → condition → encode/validate.

Pure numpy/scipy plus ffmpeg/ffprobe subprocesses and the Silero VAD ONNX model via sherpa-onnx.
No torch anywhere in this package.
"""
