#!/usr/bin/env python3
"""Build Russian word lists for KWordle and insert them into kwordle/js/words.js.

accepted: Hugo0/wordle webapp/data/languages/ru/ru_5words.txt
guess:    accepted words ranked by hermitdave/FrequencyWords ru_50k, top N,
          optionally filtered with pymorphy3 (singular nominative nouns),
          minus words from tools/ru_blocklist.txt.

Usage:
  python3 tools/build_ru.py                # download sources, write words.js
  python3 tools/build_ru.py --no-morph     # skip the pymorphy3 filter
  python3 tools/build_ru.py --dry-run      # print stats only
"""

import argparse
import json
import os
import re
import sys
import urllib.request

ACCEPTED_URL = "https://raw.githubusercontent.com/Hugo0/wordle/main/webapp/data/languages/ru/ru_5words.txt"
FREQ_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/ru/ru_50k.txt"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDS_JS = os.path.join(ROOT, "kwordle", "js", "words.js")
RU_INDEX = 9
WORD_RE = re.compile(r"^[а-я]{5}$")
SKIP_GRAMMEMES = {"Name", "Surn", "Patr", "Geox", "Orgn", "Abbr", "Init", "Erro", "Dist", "Obsc"}
MIN_PARSE_SCORE = 0.1
BLOCKLIST_FILE = os.path.join(ROOT, "tools", "ru_blocklist.txt")


def read_source(path_or_url):
    if re.match(r"^https?://", path_or_url):
        with urllib.request.urlopen(path_or_url) as resp:
            return resp.read().decode("utf-8")
    with open(path_or_url, encoding="utf-8") as f:
        return f.read()


def normalize(word):
    return word.strip().lower().replace("ё", "е")


def read_blocklist(path):
    with open(path, encoding="utf-8") as f:
        return {normalize(l) for l in f if l.strip() and not l.lstrip().startswith("#")}


def build_accepted(text):
    words = set()
    for line in text.splitlines():
        w = normalize(line)
        if WORD_RE.match(w):
            words.add(w)
    return sorted(words)


def make_morph_filter():
    import pymorphy3

    morph = pymorphy3.MorphAnalyzer()

    def is_noun(parse):
        tag = parse.tag
        return (
            parse.score >= MIN_PARSE_SCORE
            and tag.POS == "NOUN"
            and "nomn" in tag.grammemes
            and "sing" in tag.grammemes
        )

    def ok(word):
        parses = morph.parse(word)
        if any(p.tag.grammemes & SKIP_GRAMMEMES for p in parses):
            return False
        return any(is_noun(p) for p in parses)

    return ok


def build_guess(freq_text, accepted, limit, morph_filter, blocklist):
    accepted_set = set(accepted)
    seen = set()
    guess = []
    for line in freq_text.splitlines():
        parts = line.split()
        if not parts:
            continue
        w = normalize(parts[0])
        if w in seen or w not in accepted_set or w in blocklist:
            continue
        seen.add(w)
        if morph_filter and not morph_filter(w):
            continue
        guess.append(w)
        if len(guess) >= limit:
            break
    return sorted(guess)


def js_array(words):
    return "  " + json.dumps(words, ensure_ascii=False, separators=(",", ":")) + ","


def set_entry(lines, var_name, entry):
    start = next(i for i, l in enumerate(lines) if l.startswith("const %s = [" % var_name))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("];"))
    count = end - start - 1
    prev = start + RU_INDEX
    if not lines[prev].rstrip().endswith(","):
        lines[prev] = lines[prev].rstrip() + ","
    if count == RU_INDEX:
        lines.insert(end, entry)
    elif count == RU_INDEX + 1:
        lines[end - 1] = entry
    else:
        sys.exit("%s has %d entries, expected %d or %d" % (var_name, count, RU_INDEX, RU_INDEX + 1))


def write_words_js(guess, accepted):
    with open(WORDS_JS, encoding="utf-8") as f:
        lines = f.read().split("\n")
    set_entry(lines, "wordList", js_array(guess))
    set_entry(lines, "accepted", js_array(accepted))
    with open(WORDS_JS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--accepted", default=ACCEPTED_URL, help="path or URL of ru_5words.txt")
    ap.add_argument("--freq", default=FREQ_URL, help="path or URL of ru_50k.txt")
    ap.add_argument("--blocklist", default=BLOCKLIST_FILE, help="words excluded from the guess list")
    ap.add_argument("--limit", type=int, default=2000, help="max size of the guess list")
    ap.add_argument("--no-morph", action="store_true", help="skip the pymorphy3 noun filter")
    ap.add_argument("--dry-run", action="store_true", help="do not modify words.js")
    args = ap.parse_args()

    accepted = build_accepted(read_source(args.accepted))

    morph_filter = None
    if not args.no_morph:
        try:
            morph_filter = make_morph_filter()
        except ImportError:
            print("pymorphy3 not installed, skipping the noun filter", file=sys.stderr)

    guess = build_guess(read_source(args.freq), accepted, args.limit, morph_filter, read_blocklist(args.blocklist))

    print("accepted: %d words, guess: %d words" % (len(accepted), len(guess)))
    if not args.dry_run:
        write_words_js(guess, accepted)
        print("updated " + os.path.relpath(WORDS_JS, ROOT))


if __name__ == "__main__":
    main()
