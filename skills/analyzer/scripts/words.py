"""Count and show the words spoken between two times (for matching a beat's length).

usage: words.py WORKDIR START END        times in seconds or minutes:seconds, e.g. 0 11.5  or  01:07.2 01:42.0
"""
import json, os, sys

from shots import join_words


def sec(x):
    if ":" in x:
        m, s = x.split(":")
        return int(m) * 60 + float(s)
    return float(x)


wd, a, b = sys.argv[1], sec(sys.argv[2]), sec(sys.argv[3])
ws = [w["w"] for w in json.load(open(os.path.join(wd, "words.json"))) if a <= (w["s"] + w["e"]) / 2 < b]
print(f"{len(ws)} words, {b - a:.1f} s ({len(ws) / max(b - a, 0.01) * 60:.0f} per minute)")
print(join_words(ws))
