import sherpa_onnx

print("sherpa_onnx version:", sherpa_onnx.__version__)
model_cfg = sherpa_onnx.OfflineTtsModelConfig()
print("OfflineTtsModelConfig attributes:")
for attr in dir(model_cfg):
    if not attr.startswith("__"):
        print(f"  {attr}")
