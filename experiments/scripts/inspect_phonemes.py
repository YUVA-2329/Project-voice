import sys
sys.stdout.reconfigure(encoding="utf-8")

words_to_check = ["see", "bird", "car", "door", "he", "she"]
with open("project-voice/models/zipvoice-distill/lexicon-en-us.txt", encoding="utf-8") as f:
    for line in f:
        w, _, ph = line.strip().partition("||")
        w = w.strip()
        if w in words_to_check:
            tokens_in_line = ph.strip().split()
            print(f"{w} -> tokens: {tokens_in_line}")
            for t in tokens_in_line:
                print(f"   token: {repr(t)} codepoints: {[hex(ord(c)) for c in t]}")
