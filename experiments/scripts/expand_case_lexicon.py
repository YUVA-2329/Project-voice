import sys
sys.stdout.reconfigure(encoding="utf-8")

lex_path = "project-voice/experiments/lexicon/lexicon_expanded.txt"
lines = open(lex_path, encoding="utf-8").read().splitlines()

expanded_dict = {}
for line in lines:
    line = line.strip()
    if not line or line.startswith("#") or "||" not in line:
        continue
    word, phones = line.split("||", 1)
    word = word.strip()
    phones = phones.strip()
    expanded_dict[word] = phones

special_cases = {
    "PyTorch": expanded_dict.get("pytorch"),
    "FastAPI": expanded_dict.get("fastapi"),
    "PostgreSQL": expanded_dict.get("postgresql"),
    "OpenAPI": expanded_dict.get("openapi"),
    "WebSocket": expanded_dict.get("websocket"),
    "WebSockets": expanded_dict.get("websockets"),
    "dBFS": expanded_dict.get("dbfs"),
    "RTF": expanded_dict.get("rtf"),
    "TTS": expanded_dict.get("tts"),
    "ASR": expanded_dict.get("asr"),
    "VRAM": expanded_dict.get("vram"),
    "GPU": expanded_dict.get("gpu"),
    "GPUs": expanded_dict.get("gpus"),
    "CPU": expanded_dict.get("cpu"),
    "CPUs": expanded_dict.get("cpus"),
    "API": expanded_dict.get("api"),
    "APIs": expanded_dict.get("apis"),
    "ONNX": expanded_dict.get("onnx"),
    "CUDA": expanded_dict.get("cuda"),
    "LLM": expanded_dict.get("llm"),
    "LLMs": expanded_dict.get("llms"),
    "VoCOS": expanded_dict.get("vocos"),
    "Vocos": expanded_dict.get("vocos"),
    "SciPy": expanded_dict.get("scipy"),
    "NumPy": expanded_dict.get("numpy"),
}

for k, v in special_cases.items():
    if v:
        expanded_dict[k] = v

with open(lex_path, "w", encoding="utf-8") as f:
    f.write("# Project Voice Domain-Specific Expanded Lexicon (with Case Coverage)\n")
    f.write("# Format: word || space-separated IPA phones (matching ZipVoice tokens.txt)\n\n")
    for w in sorted(expanded_dict.keys()):
        f.write(f"{w} || {expanded_dict[w]}\n")

print(f"Final expanded entries with special cases: {len(expanded_dict)}")
