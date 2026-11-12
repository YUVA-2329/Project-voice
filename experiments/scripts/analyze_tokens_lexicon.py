import sys
sys.stdout.reconfigure(encoding="utf-8")

# Read tokens.txt
tokens = {}
with open("project-voice/models/zipvoice-distill/tokens.txt", encoding="utf-8") as f:
    for line in f:
        line = line.strip("\r\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            tokens[parts[0]] = parts[1]

print(f"Total tokens in tokens.txt: {len(tokens)}")

# Check how phones in lexicon-en-us.txt correspond to tokens.txt
unmatched_phones = {}
total_lex_lines = 0
with open("project-voice/models/zipvoice-distill/lexicon-en-us.txt", encoding="utf-8") as f:
    for line in f:
        total_lex_lines += 1
        w, _, ph = line.strip().partition("||")
        for p in ph.strip().split():
            if p not in tokens:
                unmatched_phones[p] = unmatched_phones.get(p, 0) + 1

print(f"Total lines in lexicon-en-us.txt: {total_lex_lines}")
print(f"Number of distinct phone tokens NOT in tokens.txt: {len(unmatched_phones)}")
for p, count in sorted(unmatched_phones.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"  Phone: {repr(p)} (count: {count}, chars: {[c for c in p]})")
