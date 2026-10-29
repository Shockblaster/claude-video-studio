"""Build index.html (the HyperFrames composition) for a 16:9 screen walkthrough from timeline.json, script.json and the
captures in assets/shots (+ boxes.json saved from the capture steps).

  python -I tools/build.py

The ENGINE (top half) is generic: a browser frame showing real screenshots, eased pans/zooms to marked boxes, rings
that pop on the words that name them, a cursor that travels and clicks, left-column points that appear as they are
said, badges, sentence subtitles, and a chapter lane with the real voice waveform and a playhead.
The SCENES (bottom half) are per-video: write one block per scene id from script.json. The two below are an EXAMPLE.
Times: numbers are seconds into the scene; L(i, extra) = the start of line i; P(sid, i, "phrase") = when a phrase in
line i is said (estimated by its position in the line)."""
import html
import json
import re
import wave
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TL = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
raw = json.loads((ROOT / "assets" / "shots" / "boxes.json").read_text(encoding="utf-8"))
BOX = json.loads(raw) if isinstance(raw, str) else raw
TOTAL = TL["total"]
SCENES = {s["id"]: s for s in TL["scenes"]}
CHAPTERS = {c["id"]: (i, c["label"]) for i, c in enumerate(TL["chapters"])}
SCRIPT = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
CH_COLOR = {c["id"]: c.get("color", "#6b3f73") for c in SCRIPT["chapters"]}

W, H = 1920, 1080
FX, FY, FW, FH, BAR = 704, 160, 1120, 630, 34  # browser frame; the screen is FW x FH (16:9, like the 1600x900 captures)
XFADE = 0.45
VIEW_H = 900  # CSS px of one browser window
ZOOM = 1.22

body, tl, ids = [], [], set()


def uid(base):
    base = re.sub(r"[^a-z0-9-]", "-", base.lower())
    n, i = base, 2
    while n in ids:
        n, i = f"{base}-{i}", i + 1
    ids.add(n)
    return n


def T(sid, off):
    """Global time for an offset in a scene: a number of seconds, or ('L', line, extra)."""
    s = SCENES[sid]
    if isinstance(off, tuple):
        _, li, extra = off
        return round(s["lines"][li]["start"] + extra, 3)
    return round(s["start"] + off, 3)


def L(i, extra=0.0):
    return ("L", i, extra)


def P(sid, li, phrase, extra=0.0):
    """Scene offset where a phrase starts, by its position in the line."""
    s = SCENES[sid]
    ln = s["lines"][li]
    return round(ln["start"] - s["start"] + ln["duration"] * ln["text"].index(phrase) / len(ln["text"]) + extra, 3)


def rel(sid, off):
    return T(sid, off) - SCENES[sid]["start"]


def esc(t):
    return html.escape(t, quote=True)


def fade_in(i, t, y=18, d=0.5):
    tl.append(f'tl.fromTo("#{i}", {{opacity: 0, y: {y}}}, {{opacity: 1, y: 0, duration: {d}, ease: "power3.out"}}, {t:.3f});')


def css_w(name):
    """CSS width of a capture: full-page shots lose 15 px to the scrollbar."""
    with Image.open(ROOT / "assets" / "shots" / f"{name}.png") as im:
        return im.width / 2


def mark(name, key, dx=0):
    b = BOX[name]["marks"][key]
    assert b, f"no box {name}.{key}"
    return (b[0] + dx, b[1], b[2], b[3])


def focus(name, box, s, dy=0.0):
    """A view (css_x, css_y, scale) centring a box, clamped to the capture."""
    # Every close-up a touch closer than written: ops watch this on laptops, and 1600 px of UI in a 1120 px frame reads small.
    s = s * ZOOM if s > 1.0 else s * (1 + (ZOOM - 1) / 2)
    cw = css_w(name)
    ch = BOX[name]["height"] if BOX[name]["full"] else VIEW_H
    k = FW / cw
    win_w, win_h = FW / (k * s), FH / (k * s)
    # A box wider than the window lines up on its left edge: centring it cut the start of every line.
    x = box[0] - 24 if box[2] > win_w * 0.85 else box[0] + box[2] / 2 - win_w / 2
    y = box[1] + box[3] / 2 - win_h / 2 + dy
    return (max(0.0, min(x, cw - win_w)), max(0.0, min(y, ch - win_h)), s)


CURSOR = '<svg viewBox="0 0 24 24"><path d="M4 2.5 L4 20 L8.6 15.6 L11.6 22 L14.4 20.8 L11.5 14.6 L18 14.4 Z" fill="#1d1a24" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'


def frame(sid, shots, url):
    """shots: dicts with name, at, views [(at, (x, y, s))], marks [(at, until, box)], clicks [(at, box)]."""
    fid = uid(f"{sid}-frame")
    inner = []
    for n, sh in enumerate(shots):
        name = sh["name"]
        k = FW / css_w(name)
        i = uid(f"{sid}-s{n}")
        extra = []
        for m, (ma, mu, (bx, by, bw, bh)) in enumerate(sh.get("marks", [])):
            r = uid(f"{i}-m{m}")
            extra.append(f'<div class="ring" id="{r}" style="left:{bx * k - 8:.1f}px;top:{by * k - 8:.1f}px;width:{bw * k + 16:.1f}px;height:{bh * k + 16:.1f}px"></div>')
            tl.append(f'tl.fromTo("#{r}", {{opacity: 0, scale: 1.1}}, {{opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2)"}}, {T(sid, ma):.3f});')
            if mu is not None:
                tl.append(f'tl.to("#{r}", {{opacity: 0, duration: 0.3}}, {T(sid, mu):.3f});')
        clicks = sh.get("clicks", [])
        if clicks:
            c = uid(f"{i}-cur")
            extra.append(f'<div class="cursor" id="{c}">{CURSOR}</div>')
            (ca, (bx, by, bw, bh)) = clicks[0]
            sx, sy = (bx + bw * 0.6) * k, (by + bh * 0.62) * k
            tl.append(f'tl.set("#{c}", {{x: {sx + 160:.1f}, y: {sy + 120:.1f}, opacity: 0}}, {T(sid, ca) - 1.2:.3f});')
            for j, (ca, (bx, by, bw, bh)) in enumerate(clicks):
                cx, cy = (bx + bw * 0.6) * k, (by + bh * 0.62) * k
                if j == 0:
                    tl.append(f'tl.to("#{c}", {{opacity: 1, duration: 0.25}}, {T(sid, ca) - 1.1:.3f});')
                tl.append(f'tl.to("#{c}", {{x: {cx:.1f}, y: {cy:.1f}, duration: 0.8, ease: "power2.inOut"}}, {T(sid, ca) - 0.85:.3f});')
                p = uid(f"{i}-clk{j}")
                extra.append(f'<div class="click" id="{p}" style="left:{cx:.1f}px;top:{cy:.1f}px"></div>')
                tl.append(f'tl.fromTo("#{p}", {{opacity: 0.9, scale: 0.4}}, {{opacity: 0, scale: 1.6, duration: 0.6, ease: "power2.out"}}, {T(sid, ca):.3f});')
                tl.append(f'tl.to("#{c}", {{scale: 0.82, duration: 0.08, yoyo: true, repeat: 1}}, {T(sid, ca) - 0.05:.3f});')
        width = css_w(name) * k
        inner.append(f'<div class="shot" id="{i}"><div class="pan" id="{i}-pan" style="width:{width:.0f}px"><img src="assets/shots/web/{name}.jpg" style="width:{width:.0f}px" alt="">{"".join(extra)}</div></div>')
        start = T(sid, sh["at"])
        if n:
            tl.append(f'tl.fromTo("#{i}", {{opacity: 0}}, {{opacity: 1, duration: 0.5, ease: "power1.out"}}, {start:.3f});')
        else:
            tl.append(f'tl.set("#{i}", {{opacity: 1}}, {start:.3f});')
        if n + 1 < len(shots):
            tl.append(f'tl.to("#{i}", {{opacity: 0, duration: 0.5}}, {T(sid, shots[n + 1]["at"]):.3f});')
        views = sh.get("views") or [(sh["at"], (0, 0, 1.0))]
        t0, (vx, vy, s) = views[0]
        tl.append(f'tl.set("#{i}-pan", {{x: {-vx * k * s:.1f}, y: {-vy * k * s:.1f}, scale: {s}, transformOrigin: "0 0"}}, {T(sid, t0):.3f});')
        for (ta, _), (tb, (vx, vy, s)) in zip(views, views[1:]):
            a, b = T(sid, ta), T(sid, tb)
            d = max(0.7, min(1.5, b - a))
            tl.append(f'tl.to("#{i}-pan", {{x: {-vx * k * s:.1f}, y: {-vy * k * s:.1f}, scale: {s}, duration: {d:.2f}, ease: "power2.inOut"}}, {b - d:.3f});')
    return f'''<div class="frame" id="{fid}" style="left:{FX}px;top:{FY}px;width:{FW}px;height:{FH + BAR}px">
  <div class="bar"><i></i><i></i><i></i><span class="url">{esc(url)}</span></div>
  <div class="screen" style="height:{FH}px">{"".join(inner)}</div>
</div>'''


def left(sid, items):
    """The scene's chapter, title and what to do, each point appearing as it is said. items: (at, html)."""
    s = SCENES[sid]
    num, label = CHAPTERS[s["chapter"]]
    tid = uid(f"{sid}-title")
    fade_in(tid, T(sid, 0.05), y=24, d=0.6)
    out = []
    for n, (at, text) in enumerate(items):
        i = uid(f"{sid}-pt{n}")
        out.append(f'<li id="{i}"><b></b><span>{text}</span></li>')
        tl.append(f'tl.fromTo("#{i}", {{opacity: 0, x: -18}}, {{opacity: 1, x: 0, duration: 0.45, ease: "power2.out"}}, {T(sid, at):.3f});')
    return f'''<div class="left">
  <div class="kicker">{esc(label)}</div>
  <h2 id="{tid}">{esc(s["title"])}</h2>
  <ul class="points">{"".join(out)}</ul>
</div>'''


def badge(sid, at, until, inner, x, y, w, cls="badge"):
    i = uid(f"{sid}-badge")
    tl.append(f'tl.fromTo("#{i}", {{opacity: 0, y: 16}}, {{opacity: 1, y: 0, duration: 0.5, ease: "power3.out"}}, {T(sid, at):.3f});')
    if until is not None:
        tl.append(f'tl.to("#{i}", {{opacity: 0, duration: 0.35}}, {T(sid, until):.3f});')
    return f'<div class="{cls}" id="{i}" style="left:{x}px;top:{y}px;width:{w}px">{inner}</div>'


def btn(t, ghost=False):
    return f'<span class="btn{" ghost" if ghost else ""}">{esc(t)}</span>'


def dur(sid):
    s = SCENES[sid]
    return s["end"] - s["start"]


URL = SCRIPT.get("url", "app.example.com")
BRAND = SCRIPT.get("brand", "YOUR PRODUCT")
B = lambda name, key, dx=0: mark(name, key, dx)  # noqa: E731
scene_html = {}

# ---------------- EXAMPLE SCENES: replace with one block per scene in script.json ----------------
# s01: a hero title card.
sid = "s01"
hero = uid("s01-hero")
tl.append(f'tl.fromTo("#{hero}", {{opacity: 0, y: 30}}, {{opacity: 1, y: 0, duration: 0.8, ease: "power3.out"}}, 0.15);')
scene_html[sid] = f'''<div class="hero" id="{hero}"><div class="logo"><i></i>{esc(BRAND)}</div><h1>{esc(SCENES[sid]["title"])}</h1><p class="serif">a short guide</p></div>'''

# s02: the list (ring the list, then the New note button with a click), then the editor (ring title, then Save).
sid = "s02"
N, E = "02-notes", "03-editor"
t_new, t_edit = P(sid, 1, "New note"), rel(sid, L(2, 0))
scene_html[sid] = left(sid, [(0.3, "Every note, newest first"), (t_new, f"Start with {btn('New note')}"), (t_edit, f"Title, then {btn('Save')}")]) + frame(sid, [
    {"name": N, "at": 0, "views": [(0, focus(N, B(N, "list"), 1.0)), (t_new, focus(N, B(N, "newBtn"), 1.3))],
     "marks": [(0.4, t_new, B(N, "list")), (t_new, None, B(N, "newBtn"))], "clicks": [(t_new + 0.6, B(N, "newBtn"))]},
    {"name": E, "at": t_edit, "views": [(t_edit, focus(E, B(E, "title"), 1.2))],
     "marks": [(t_edit + 0.3, None, B(E, "title")), (P(sid, 2, "Save"), None, B(E, "save"))], "clicks": [(P(sid, 2, "Save", 0.4), B(E, "save"))]},
], URL + "/notes")
# --------------------------------------------------------------------------------------------------

# ---------- assemble ----------
order = [s["id"] for s in TL["scenes"]]
for n, sid in enumerate(order):
    s = SCENES[sid]
    start = s["start"] if n else 0.0
    end = (s["end"] + XFADE) if n + 1 < len(order) else TOTAL
    cid = f"scene-{sid}"
    ids.add(cid)
    if n:
        tl.append(f'tl.fromTo("#{cid}", {{opacity: 0}}, {{opacity: 1, duration: {XFADE}, ease: "power1.out"}}, {start:.3f});')
    body.append(f'<section id="{cid}" class="clip scene" data-start="{start:.3f}" data-duration="{end - start:.3f}" data-track-index="{1 + n % 2}">{scene_html[sid]}</section>')

# ---------- subtitles ----------
subs = []
for s in TL["scenes"]:
    for ln in s["lines"]:
        chunks = []
        for sen in re.split(r"(?<=[.!?:])\s+", ln["text"]):
            words = sen.split()
            while len(words) > 14:
                cut = 12
                for j in range(7, 14):
                    if words[j - 1].endswith(","):
                        cut = j
                chunks.append(" ".join(words[:cut]))
                words = words[cut:]
            if words:
                chunks.append(" ".join(words))
        total_chars = sum(len(c) for c in chunks)
        t = ln["start"]
        for c in chunks:
            d = ln["duration"] * len(c) / total_chars
            subs.append((t, d, c))
            t += d
sub_html = []
for n, (t, d, c) in enumerate(subs):
    i = f"sub{n}"
    ids.add(i)
    sub_html.append(f'<div id="{i}" class="clip sub" data-start="{t:.3f}" data-duration="{d - 0.02:.3f}" data-track-index="{30 + n % 2}"><span>{esc(c)}</span></div>')

# ---------- chapter lane with the real voiceover waveform ----------
LX, LW = 96, 1728
with wave.open(str(ROOT / "assets" / "vo-full.wav")) as w:
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
env = np.array([np.sqrt(np.mean(c ** 2)) if len(c) else 0 for c in np.array_split(a, LW // 4)])
env = env / (env.max() + 1e-9)
bars = "".join(f'<rect x="{j * 4}" y="{16 - max(1, v * 14):.1f}" width="2" height="{max(2, v * 28):.1f}" rx="1"/>' for j, v in enumerate(env))
runs = []
for s in TL["scenes"]:
    if runs and runs[-1][0] == s["chapter"]:
        runs[-1][2] = s["end"]
    else:
        runs.append([s["chapter"], s["start"], s["end"]])
runs[0][1], runs[-1][2] = 0, TOTAL
regions = []
for ch, a0, a1 in runs:
    x0, x1 = a0 / TOTAL * LW, a1 / TOTAL * LW
    label = f"<span>{esc(CHAPTERS[ch][1])}</span>" if x1 - x0 > 110 else ""
    regions.append(f'<div class="region" style="left:{x0:.1f}px;width:{x1 - x0 - 3:.1f}px;--c:{CH_COLOR[ch]}">{label}</div>')
tl.append(f'tl.fromTo("#playhead", {{x: 0}}, {{x: {LW}, duration: {TOTAL}, ease: "none"}}, 0);')
tl.append(f'tl.fromTo("#lit", {{x: {-LW}}}, {{x: 0, duration: {TOTAL}, ease: "none"}}, 0);')
tl.append(f'tl.fromTo("#lit-inner", {{x: {LW}}}, {{x: 0, duration: {TOTAL}, ease: "none"}}, 0);')
hud = f'''
<div id="hud" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="40">
  <div class="brand"><i></i><span>{esc(BRAND)}</span></div>
  <div class="testchip"><b></b>{esc(SCRIPT.get("chip", "Made-up test data"))}</div>
  <div class="lane">
    {"".join(regions)}
    <svg class="wave" width="{LW}" height="32" viewBox="0 0 {LW} 32"><g fill="#b9aec0" opacity="0.55">{bars}</g></svg>
    <div class="litwrap"><div id="lit"><div id="lit-inner"><svg width="{LW}" height="32" viewBox="0 0 {LW} 32"><g fill="#6b3f73">{bars}</g></svg></div></div></div>
    <div id="playhead"><i></i></div>
  </div>
</div>'''
ids.update({"hud", "playhead", "lit", "lit-inner"})

css = (ROOT / "tools" / "style.css").read_text(encoding="utf-8")
fonts = (ROOT / "fonts.css").read_text(encoding="utf-8")
page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={W}, height={H}">
<title>{esc(BRAND)}: guide</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{fonts}
{css}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-width="{W}" data-height="{H}" data-duration="{TOTAL}" data-fps="30">
<div id="bg" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0"><div class="grid"></div><div class="glow"></div></div>
{chr(10).join(body)}
{chr(10).join(sub_html)}
{hud}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(tl)}
window.__timelines["main"] = tl;
</script>
</body>
</html>
'''
(ROOT / "index.html").write_text(page, encoding="utf-8")
print("scenes", len(order), "subs", len(subs), "tweens", len(tl), "total", TOTAL)
