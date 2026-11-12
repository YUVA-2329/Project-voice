import sherpa_onnx
from pathlib import Path

model_dir = Path("project-voice/models/zipvoice-distill")
lexicon_str = f"{model_dir/'lexicon.txt'},{model_dir/'lexicon-en-us.txt'},project-voice/experiments/lexicon/lexicon_expanded.txt"

model_cfg = sherpa_onnx.OfflineTtsModelConfig(
    zipvoice=sherpa_onnx.OfflineTtsZipvoiceModelConfig(
        tokens=str(model_dir / "tokens.txt"),
        encoder=str(model_dir / "encoder.int8.onnx"),
        decoder=str(model_dir / "decoder.int8.onnx"),
        lexicon=lexicon_str,
        vocoder=str(model_dir / "vocos_24khz.onnx"),
    ),
    debug=True,
    num_threads=2,
    provider="cpu",
)
cfg = sherpa_onnx.OfflineTtsConfig(model=model_cfg)
tts = sherpa_onnx.OfflineTts(cfg)
print("TTS initialized with debug=True")
