import sherpa_onnx
from pathlib import Path

model_dir = Path("project-voice/models/zipvoice-distill")
tokens = str(model_dir / "tokens.txt")
enc = str(model_dir / "encoder.int8.onnx")
dec = str(model_dir / "decoder.int8.onnx")
vocoder = str(model_dir / "vocos_24khz.onnx")
lexicon_stock = str(model_dir / "lexicon.txt")
lexicon_en = str(model_dir / "lexicon-en-us.txt")
lexicon_custom = "project-voice/experiments/lexicon/lexicon_expanded.txt"

lexicon_str = f"{lexicon_stock},{lexicon_en},{lexicon_custom}"

model_cfg = sherpa_onnx.OfflineTtsModelConfig(
    zipvoice=sherpa_onnx.OfflineTtsZipvoiceModelConfig(
        tokens=tokens,
        encoder=enc,
        decoder=dec,
        lexicon=lexicon_str,
        vocoder=vocoder,
    ),
    debug=False,
    num_threads=4,
    provider="cpu",
)

cfg = sherpa_onnx.OfflineTtsConfig(model=model_cfg)
print("Config validate:", cfg.validate())
try:
    tts = sherpa_onnx.OfflineTts(cfg)
    print("Sherpa OfflineTts loaded successfully! Sample rate:", tts.sample_rate)
except Exception as e:
    print("Error loading OfflineTts:", e)
