import sys
sys.stdout.reconfigure(encoding="utf-8")

tokens = set()
with open("project-voice/models/zipvoice-distill/tokens.txt", encoding="utf-8") as f:
    for line in f:
        line = line.strip("\r\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            tokens.add(parts[0])

print(f"Loaded {len(tokens)} tokens from tokens.txt")

missing = {}
entries_count = 0
with open("project-voice/experiments/lexicon/lexicon_expanded.txt", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "||" not in line:
            continue
        entries_count += 1
        word, phones = line.split("||", 1)
        word = word.strip()
        phone_tokens = phones.strip().split()
        bad = [p for p in phone_tokens if p not in tokens]
        if bad:
            missing[word] = bad

print(f"Total valid entries in lexicon_expanded: {entries_count}")
print(f"Entries with missing tokens: {len(missing)}")
if missing:
    for k, v in list(missing.items())[:15]:
        print(f"  {k} -> missing: {v}")
else:
    print("ALL entries in lexicon_expanded match tokens.txt perfectly!")
