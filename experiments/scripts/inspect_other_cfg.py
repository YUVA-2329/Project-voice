import sherpa_onnx

for name in ["matcha", "kokoro", "zipvoice"]:
    cls_name = f"OfflineTts{name.capitalize()}ModelConfig"
    cls = getattr(sherpa_onnx, cls_name, None)
    if cls:
        inst = cls()
        fields = [a for a in dir(inst) if not a.startswith("__")]
        print(f"{cls_name} fields: {fields}")
