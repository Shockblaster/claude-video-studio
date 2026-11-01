#!/usr/bin/env python3
"""NUMBER CHECK: every number a viewer hears or reads must trace to sources.md (2026-11-02; the facts rule of a
friend's fork's plan check, as its own gate. Our hard rule: never fabricate data).

  python -I number_check.py --sources sources.md [--script vo/script.txt] [--html hf/index.html] [--allow 0-10]

Numbers are pulled from the script (spoken), from the visible text of the HyperFrames page (tags, scripts and
styles stripped), and compared with every number written in sources.md. "1,20,000" and "120000" are the same;
"7.5%" matches "7.5". Small counts (0-10 by default, "step 3") are allowed. A line in the script or page can opt
out with the word "illustrative" in it (it must then be labelled illustrative on screen).
Exit 1 when any number is missing from sources.md.
"""
import argparse
import html as H
import pathlib
import re
import sys

NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
         "thousand": 1000, "lakh": 100000, "crore": 10000000, "million": 10 ** 6, "billion": 10 ** 9}


def norm(s):
    s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return s
    return str(int(v)) if v == int(v) else repr(v)


def visible_text(page):
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)
    page = re.sub(r"(?s)<!--.*?-->", " ", page)
    return H.unescape(re.sub(r"<[^>]+>", "\n", page))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--script", action="append", default=[])
    ap.add_argument("--html", action="append", default=[])
    ap.add_argument("--allow", default="0-10", help="range of small numbers that need no source")
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.allow.split("-"))
    known = {norm(n) for n in NUM.findall(pathlib.Path(a.sources).read_text(encoding="utf-8"))}
    lines = []
    for p in a.script:
        lines += [("spoken", p, ln) for ln in pathlib.Path(p).read_text(encoding="utf-8").splitlines()]
    for p in a.html:
        lines += [("on screen", p, ln) for ln in visible_text(pathlib.Path(p).read_text(encoding="utf-8")).splitlines()]
    missing, checked = [], 0
    for kind, p, ln in lines:
        if not ln.strip() or "illustrative" in ln.lower():
            continue
        for n in NUM.findall(ln):
            v = norm(n)
            try:
                if lo <= float(v) <= hi:
                    continue
            except ValueError:
                pass
            checked += 1
            if v not in known:
                missing.append(f"{kind:9} {n:>12}  ({pathlib.Path(p).name}): {ln.strip()[:90]}")
        bare = NUM.sub(" ", re.sub(r"\d[\d,.]*\s*(lakh|crore|million|billion|thousand|hundred)", " ", ln.lower()))
        spelled = [w for w in re.findall(r"[a-z]+", bare) if w in WORDS and WORDS[w] > hi]
        if spelled:
            print(f"note  {kind}: spelled-out amount {spelled} in: {ln.strip()[:90]}  (check it against sources.md by eye)")
    for m in missing:
        print("NO SOURCE " + m)
    print(f"{'NUMBERS PASS' if not missing else 'NUMBERS FAIL'}: {checked} numbers checked, {len(missing)} without a source in {a.sources}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
