import sys
sys.stdout.reconfigure(encoding="utf-8")

words_to_check = ["see", "you", "door", "car", "bird", "he", "she", "two"]
with open("project-voice/models/zipvoice-distill/lexicon-en-us.txt", encoding="utf-8") as f:
    for line in f:
        w, _, ph = line.strip().partition("||")
        w = w.strip()
        if w in words_to_check:
            print(f"{w} -> {ph.strip()}")
