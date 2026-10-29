#!/usr/bin/env python3
"""Word timings -> named cue times for the scenes (timing.js) + timed caption groups (cap.html).

  python -I build_timing.py --words vo/words.json --cues cues.json --hf hf --end 80
         [--key key_words.txt] [--fixtxt fixtxt.json] [--box 48,894,542] [--font Inter]
         [--font-file InterVariable.woff2] [--pill "rgba(10,18,34,.86)"] [--accent "#f4d049"] [--size 52]

cues.json  {"hook": [1, 0], "number": [1, 4], ...}: cue name -> [line, word index] (1-based line,
           0-based word, as in words.json). Scenes read window.__T.w.<name> (seconds) so nothing is
           hard-timed; a re-recorded voice re-times every scene by re-running this script.
key words  one per row; shown in the accent colour inside captions (numbers, the turn, the payoff).
fixtxt     {"4.14": "At a"}: caption text for a word ("line.i") where Whisper misheard or dropped one.
--box      x,y,width of the caption box. MEASURE it on every avatar frame so captions never sit on the
           avatar (the pose with the widest arm decides it).

Caption rules that held up on real reels: groups follow the sentence (split at punctuation and pauses
over 0.35 s); long clauses are cut into balanced 2-4 word groups; a number stays with its unit ("49
lakh"); a lone trailing word folds back; a lone word that OPENS a sentence goes forward ("One, your goal
has changed."); max ~30 characters (2 lines at 52 px in a ~540 px box).
"""
import argparse
import json
import pathlib
import re


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", required=True); ap.add_argument("--cues", required=True)
    ap.add_argument("--hf", required=True, help="HyperFrames project folder")
    ap.add_argument("--end", type=float, required=True, help="reel length (s)")
    ap.add_argument("--key"); ap.add_argument("--fixtxt")
    ap.add_argument("--box", default="48,894,542"); ap.add_argument("--size", type=int, default=52)
    ap.add_argument("--font", default="Inter"); ap.add_argument("--font-file", default="InterVariable.woff2")
    ap.add_argument("--pill", default="rgba(10,18,34,.86)"); ap.add_argument("--accent", default="#f4d049")
    ap.add_argument("--maxc", type=int, default=30); ap.add_argument("--maxw", type=int, default=4)
    a = ap.parse_args()
    W = json.loads(pathlib.Path(a.words).read_text())
    cues = json.loads(pathlib.Path(a.cues).read_text())
    at = lambda line, i: next(w for w in W if w["line"] == line and w["i"] == i)
    T = {k: at(*v)["start"] for k, v in cues.items()}
    vo_end = max(w["end"] for w in W)
    T["voEnd"] = round(vo_end, 3)
    hf = pathlib.Path(a.hf)
    (hf / "assets").mkdir(parents=True, exist_ok=True); (hf / "compositions").mkdir(parents=True, exist_ok=True)
    (hf / "assets" / "timing.js").write_text("window.__T = " + json.dumps({"w": T}) + ";\n")

    KEY = set(l.strip() for l in pathlib.Path(a.key).read_text(encoding="utf-8").splitlines() if l.strip()) if a.key else set()
    FIX = {tuple(int(x) for x in k.split(".")): v for k, v in json.loads(pathlib.Path(a.fixtxt).read_text()).items()} if a.fixtxt else {}
    words = [dict(w, text=FIX.get((w["line"], w["i"]), w["text"])) for w in W]
    MAXC, MAXW = a.maxc, a.maxw
    txt = lambda g: " ".join(x["text"] for x in g)
    clauses, cur = [], []
    for k, w in enumerate(words):
        nxt = words[k + 1] if k + 1 < len(words) else None
        cur.append(w)
        gap = (nxt["start"] - w["end"]) if nxt else 9
        if re.search(r"[.,?!]$", w["text"]) or gap > 0.35 or not nxt or nxt["line"] != w["line"]:
            clauses.append(cur); cur = []
    groups = []
    for c in clauses:
        if (len(c) <= MAXW and len(txt(c)) <= MAXC) or (len(c) == MAXW + 1 and len(txt(c)) <= MAXC - 4):
            groups.append(c); continue
        k = -(-len(c) // MAXW)
        while True:                                     # balanced cut points, nudged off number|unit pairs
            size = len(c) / k
            cuts = [round(size * j) for j in range(1, k)]
            cuts = [ct + 1 if re.fullmatch(r"[\d,%]+", c[ct - 1]["text"]) else ct for ct in cuts]
            parts = [c[x:y] for x, y in zip([0] + cuts, cuts + [len(c)]) if c[x:y]]
            if all(len(txt(p)) <= MAXC for p in parts) or k > len(c):
                break
            k += 1
        groups += parts
    fixed, carry = [], None
    for n, g in enumerate(groups):
        if carry:
            g, carry = carry + g, None
        prev = fixed[-1] if fixed else None
        nxt = groups[n + 1] if n + 1 < len(groups) else None
        opens = prev is None or re.search(r"[.?!]$", prev[-1]["text"])
        whole = opens and re.search(r"[.?!]$", g[0]["text"])             # a one-word sentence ("Wait.") stands alone
        lone = len(g) == 1 and not whole
        if lone and opens and nxt and nxt[0]["line"] == g[0]["line"] and len(nxt) <= MAXW and len(txt(g + nxt)) <= MAXC:
            carry = g
        elif prev and lone and not opens and g[0]["line"] == prev[-1]["line"] and len(prev) <= MAXW and len(txt(prev + g)) <= MAXC:
            fixed[-1] = prev + g
        else:
            fixed.append(g)
    groups = fixed

    def html(g):
        return " ".join(f"<em>{x['text']}</em>" if x["text"] in KEY or x["text"].rstrip(".,?!") in KEY else x["text"] for x in g)

    rows = []
    for n, g in enumerate(groups):
        st = g[0]["start"] - 0.05
        nxt_st = groups[n + 1][0]["start"] - 0.05 if n + 1 < len(groups) else None
        en = g[-1]["end"] + 0.25
        if nxt_st is not None and nxt_st - g[-1]["end"] < 0.6:
            en = min(max(en, g[-1]["end"]), nxt_st)
        en = min(en, vo_end + 0.3)
        rows.append((st, en - st, html(g)))
    bx, by, bw = [int(v) for v in a.box.split(",")]
    cap = ['<template>', '  <style>',
           f'    @font-face {{ font-family: "{a.font}"; src: url("assets/fonts/{a.font_file}") format("woff2"); font-weight: 100 900; }}',
           f'    #root {{ position: absolute; inset: 0; font-family: "{a.font}", sans-serif; pointer-events: none; }}',
           f'    .cg {{ position: absolute; left: {bx}px; top: {by}px; width: {bw}px; }}',
           f'    .cg span {{ display: inline; padding: 5px 16px 9px; line-height: 1.4; border-radius: 16px; background: {a.pill};',
           f'      color: #fff; font-size: {a.size}px; font-weight: 800; letter-spacing: -0.02em; -webkit-box-decoration-break: clone; box-decoration-break: clone; }}',
           f'    .cg em {{ font-style: normal; color: {a.accent}; }}',
           '  </style>', '  <div id="root" data-composition-id="cap" data-width="1080" data-height="1920">']
    for n, (st, d, h) in enumerate(rows):
        cap.append(f'    <div id="cap-{n}" class="clip cg" data-start="{st:.2f}" data-duration="{d:.2f}" data-track-index="1"><span>{h}</span></div>')
    cap += ['  </div>', '  <script>',
            '    (function () { const tl = gsap.timeline({ paused: true }); tl.to({}, { duration: ' + f"{a.end}" + ' }, 0); window.__timelines["cap"] = tl; })();',
            '  </script>', '</template>', '']
    (hf / "compositions" / "cap.html").write_text("\n".join(cap), encoding="utf-8")
    print(len(T), "cues;", len(rows), "caption groups")
    for st, d, h in rows:
        print(f"{st:6.2f} {d:4.2f}  {re.sub('<[^>]+>', '', h)}")


if __name__ == "__main__":
    main()
