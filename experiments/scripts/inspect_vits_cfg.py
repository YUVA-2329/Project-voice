import sherpa_onnx

vits_cfg = sherpa_onnx.OfflineTtsVitsModelConfig()
print("OfflineTtsVitsModelConfig fields:")
for attr in dir(vits_cfg):
    if not attr.startswith("__"):
        print(f"  {attr}")
