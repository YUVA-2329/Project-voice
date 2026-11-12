import sys
sys.stdout.reconfigure(encoding="utf-8")

tokens = {}
with open("project-voice/models/zipvoice-distill/tokens.txt", encoding="utf-8") as f:
    for line in f:
        line = line.strip("\r\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            tokens[parts[0]] = parts[1]

for k in sorted(tokens.keys()):
    if any(c in k for c in ["ː", ":", "ˈ", "ˌ", "ɔ", "ɑ", "ɜ", "i", "u"]):
        print(f"Token: {repr(k)} -> ID: {tokens[k]}")
