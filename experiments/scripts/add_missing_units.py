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

new_units = {
    "kilohertz": "kˈ ɪ l ə hˈ ɜː t s",
    "megahertz": "mˈ ɛ ɡ ə hˈ ɜː t s",
    "gigahertz": "ɡˈ ɪ ɡ ə hˈ ɜː t s",
    "terahertz": "tˈ ɛ ɹ ə hˈ ɜː t s",
    "hertz": "hˈ ɜː t s",
    "kilobytes": "kˈ ɪ l ə bˌ aɪ t s",
    "megabytes": "mˈ ɛ ɡ ə bˌ aɪ t s",
    "gigabytes": "ɡˈ ɪ ɡ ə bˌ aɪ t s",
    "terabytes": "tˈ ɛ ɹ ə bˌ aɪ t s",
    "petabytes": "pˈ ɛ t ə bˌ aɪ t s",
    "milliseconds": "mˈ ɪ l ɪ sˌ ɛ k ə n d z",
    "millisecond": "mˈ ɪ l ɪ sˌ ɛ k ə n d",
    "nanoseconds": "nˈ æ n oʊ sˌ ɛ k ə n d z",
    "microseconds": "mˈ aɪ k ɹ oʊ sˌ ɛ k ə n d z",
    "decibels": "dˈ ɛ s ɪ bˌ ɛ l z",
    "decibel": "dˈ ɛ s ɪ bˌ ɛ l",
}

for k, v in new_units.items():
    for w in [k, k.capitalize(), k.upper()]:
        expanded_dict[w] = v

with open(lex_path, "w", encoding="utf-8") as f:
    f.write("# Project Voice Domain-Specific Expanded Lexicon (with Case Coverage)\n")
    f.write("# Format: word || space-separated IPA phones (matching ZipVoice tokens.txt)\n\n")
    for w in sorted(expanded_dict.keys()):
        f.write(f"{w} || {expanded_dict[w]}\n")

print(f"Total entries now: {len(expanded_dict)}")
