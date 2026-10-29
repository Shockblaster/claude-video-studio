#!/usr/bin/env python3
"""Turn a puppet rig (puppet_build.py) + voice + cues into a HyperFrames scene.

  python -I build_puppet_scene.py --rig rig_dir --voice vo.wav --mouth mouth.json \
      --words transcript.json --script line.txt --plan plan.json --out project_dir
      [--fonts <brand fonts folder>] [--title "..."]

plan.json (times in seconds; "at" may also be a word index from the script, e.g. "w5"):
  {"poses": [["w0","point"], ["w8","relaxed"], ...],
   "eyes":  [["w2","surprise",0.9], ["w11","think",0.8], ["w14","side",0.6]],
   "card":  {"at": "w13", "kicker": "...", "value": "...", "note": "..."}}

Captions: script words in groups of 3, timed by the transcript words matched by position.
Wrap a script word in *stars* to highlight it.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

HTML = r"""<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
<title>Puppet scene</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face { font-family: "Inter"; src: url("assets/fonts/InterVariable.woff2") format("woff2"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1080px; height: 1920px; overflow: hidden; background: #eef1f6; font-family: "Inter", sans-serif; }
#bg { position: absolute; inset: 0; background: radial-gradient(110% 70% at 50% 42%, #ffffff 0%, #eef1f6 48%, #d6dee9 100%); }
#wrap { position: absolute; left: __LEFT__px; top: __TOP__px; width: __W__px; height: __H__px; transform: scale(__S__); transform-origin: 0 0; }
#enter, #body { position: absolute; inset: 0; }
#body img { position: absolute; display: block; }
.pose { left: 0; top: 0; width: __W__px; height: __H__px; }
#desk { position: absolute; left: 0; right: 0; top: __DESK__px; bottom: 0; background: linear-gradient(180deg, #00357a 0%, #002357 100%); border-top: 6px solid #f4d049; }
#card-wrap { position: absolute; left: 90px; right: 90px; top: 196px; }
#card { background: #fff; border-radius: 34px; padding: 34px 44px; box-shadow: 0 24px 60px rgba(0,53,122,.18); border: 2px solid #e3e8f0; }
#card .k { font-size: 34px; font-weight: 650; color: #608396; }
#card .v { font-size: 96px; font-weight: 800; color: #00357a; line-height: 1.04; }
#card .n { font-size: 30px; font-weight: 600; color: #4a4848; margin-top: 6px; }
.cap { position: absolute; left: 60px; right: 60px; top: __CAPTOP__px; text-align: center; }
.cap span { display: inline-block; background: rgba(10,18,34,.86); color: #fff; font-size: 56px; font-weight: 800; padding: 10px 26px; border-radius: 18px; }
.cap b { color: #f4d049; }
.tag { position: absolute; left: 0; right: 0; top: 176px; text-align: center; color: #608396; font-size: 28px; font-weight: 650; letter-spacing: .06em; }
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__" data-width="1080" data-height="1920">
  <div id="bg"></div>
__TAG__
__CARD__
  <div id="wrap" class="clip" data-start="0" data-duration="__DUR__" data-track-index="0">
    <div id="enter"><div id="body">
__POSES__
__MOUTHS__
__EYES__
    </div></div>
  </div>
  <div id="desk"></div>
__CAPS__
  <audio id="vo" class="clip" src="assets/vo.wav" data-start="0" data-duration="__VODUR__" data-track-index="3"></audio>
</div>
<script type="application/json" id="cues">__CUES__</script>
<script>
window.__timelines = window.__timelines || {};
const D = __DUR__;
const C = JSON.parse(document.getElementById("cues").textContent);
const tl = gsap.timeline({ paused: true });

// SEEK-SAFE swaps. Renders seek frames out of order (parallel workers), so never "hide the
// whole class, then show one" at the same instant (they landed in the wrong order and the
// face floated with no body for 5 frames). Each element gets its own explicit set, only
// when its own visibility changes, from one ordered list of events per group.
function track(prefix, ids, events) {
  const at = new Map();
  for (const [t, id] of events) at.set(Math.max(0, Math.round(t * 1000) / 1000), id);
  const times = [...at.keys()].sort((a, b) => a - b);
  for (const id of ids) {
    let prev = null;
    for (const t of times) {
      const v = at.get(t) === id ? 1 : 0;
      if (v !== prev) { tl.set("#" + prefix + id, { opacity: v }, t); prev = v; }
    }
  }
}
const f = 1 / 30;

// lip-sync. REMAP swaps shapes whose generated drawing does not match the face (pursed-lip
// cells come with puffed cheeks = lines across the cheeks): E (rounded) -> C, F (OO) -> B
const REMAP = C.remap || {};
track("m-", C.ids.mouth, [[0, "X"], ...C.mouth.map(c => [c.start, REMAP[c.value] || c.value]), [C.vo + 0.05, "X"]]);

// eyes: expression events, then blinks in the gaps
const ev = [[0, "open"]], busy = [];
for (const [t, state, dur] of C.eyes) { ev.push([t, state], [t + dur, "open"]); busy.push([t - 0.3, t + dur + 0.3]); }
let seed = 11, bt = 1.1;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
while (bt < D - 0.4) {
  if (!busy.some(([a, b]) => bt > a && bt < b)) ev.push([bt, "half"], [bt + f, "closed"], [bt + 3 * f, "half"], [bt + 4 * f, "open"]);
  bt += 2.2 + rnd() * 2.0;
}
ev.sort((a, b) => a[0] - b[0]);
track("e-", C.ids.eyes, ev);

// gestures: instant pose cut hidden by a dip-and-pop (any cross-fade ghosts the old arms)
track("p-", C.ids.poses, C.poses);
let prevT = -1;
for (const [t, pose] of C.poses.slice(1)) {
  if (t < 0.7 || t - prevT < 0.5) continue;      // not during the entrance, never overlapping
  tl.fromTo("#body", { y: 0 }, { y: 10, duration: 0.07, ease: "power1.in", immediateRender: false }, t - 0.07)
    .fromTo("#body", { y: 10 }, { y: 0, duration: 0.35, ease: "back.out(2)", immediateRender: false }, t);
  prevT = t;
}

// life (explicit from-values everywhere: seek-safe in any frame order)
tl.fromTo("#enter", { y: 420 }, { y: 0, duration: 0.55, ease: "power3.out" }, 0);
tl.fromTo("#body", { scaleY: 1 }, { scaleY: 1.008, transformOrigin: "50% 100%", duration: 1.7, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.floor(D / 1.7) - 1) }, 0);
tl.fromTo("#body", { rotation: 0 }, { rotation: 0.6, transformOrigin: "50% 100%", duration: 2.6, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.floor(D / 2.6) - 1) }, 0);
// 2.5D for the 3D look: a gentle turn in depth plus a slow push-in of the whole scene
if (C.depth) {
  tl.fromTo("#body", { rotationY: 0 }, { rotationY: 3.5, transformPerspective: 2200, transformOrigin: "50% 60%", duration: 3.2, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.floor(D / 3.2) - 1) }, 0);
  tl.fromTo("#bg", { scale: 1.0 }, { scale: 1.08, duration: D, ease: "none" }, 0);
}
if (document.getElementById("card")) tl.fromTo("#card", { y: 40, scale: 0.88, opacity: 0 }, { y: 0, scale: 1, opacity: 1, transformOrigin: "50% 100%", duration: 0.5, ease: "back.out(1.5)" }, C.card);

window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("rig", "voice", "mouth", "words", "script", "plan", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--fonts", default=str(_paths.fonts_dir()))
    ap.add_argument("--title", default="", help="small label at the top ('' = none)")
    ap.add_argument("--display-height", type=int, default=950, help="head-top-to-cut height of the puppet in px")
    ap.add_argument("--top", type=int, default=590, help="frame y of the top of the head")
    ap.add_argument("--cap-top", type=int, default=468, help="caption band y: above the head, below the card, clear of hands")
    ap.add_argument("--depth", action="store_true", help="2.5D turn + push-in, for 3D-render art")
    ap.add_argument("--remap", default="", help="extra manual mouth remaps, e.g. E=C,F=B (the rig's gate is automatic)")
    a = ap.parse_args()

    rig_dir, out = pathlib.Path(a.rig), pathlib.Path(a.out)
    rig = json.loads((rig_dir / "rig.json").read_text())
    (out / "assets" / "rig").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    for f in rig_dir.glob("*.png"):
        if not f.name.startswith("debug"):
            shutil.copy(f, out / "assets" / "rig" / f.name)
    shutil.copy(pathlib.Path(a.fonts) / "InterVariable.woff2", out / "assets" / "fonts")
    # voice to social loudness here, so the mix lands near -14 LUFS without a separate pass
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.voice, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(out / "assets" / "vo.wav")], check=True)

    W, H = rig["canvas"]
    # FIT EVERY GESTURE IN FRAME: union of all pose silhouettes (the open-palm pose's hand
    # went off the left edge when the canvas was simply centred). Scale to the tighter of
    # the height budget and a 1000 px width budget, centre the union, not the canvas.
    import cv2
    import numpy as np
    union = None
    for p in rig["poses"]:
        al = cv2.imread(str(rig_dir / f"pose_{p}.png"), cv2.IMREAD_UNCHANGED)[..., 3] > 40
        union = al if union is None else (union | al)
    ys_, xs_ = np.nonzero(union)
    ux0, ux1, uy0 = int(xs_.min()), int(xs_.max()), int(ys_.min())
    body_h = rig["bottom"] - uy0
    s = min(a.display_height / body_h, 1000 / (ux1 - ux0 + 1))
    left = int((1080 - (ux1 - ux0 + 1) * s) / 2 - ux0 * s)
    a.top = int(a.top - uy0 * s)
    vo = dur(a.voice)
    D = round(vo + 0.8, 2)

    words = json.loads(pathlib.Path(a.words).read_text(encoding="utf-8"))
    words = words["words"] if isinstance(words, dict) else words
    script = pathlib.Path(a.script).read_text(encoding="utf-8").split()
    times = [(w["start"], w["end"]) for w in words]
    if len(times) != len(script):
        print(f"warning: {len(script)} script words vs {len(times)} transcript words; timing by position", file=sys.stderr)

    def at(v):
        if isinstance(v, str) and v.startswith("w"):
            return round(times[min(int(v[1:]), len(times) - 1)][0], 3)
        return float(v)

    plan = json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8"))
    poses = [[at(t), p] for t, p in plan.get("poses", [])]
    if not poses or poses[0][0] > 0:
        poses.insert(0, [0, "relaxed"])
    eyes = [[at(t), st, d] for t, st, d in plan.get("eyes", [])]

    # caption groups: up to 4 words, a group ends at sentence punctuation
    groups, cur = [], []
    for k, w in enumerate(script):
        cur.append(k)
        if len(cur) == 4 or re.search(r"[.!?,]\**$", w):
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    # no orphan one-word captions ("money.", "it are."): fold them into a neighbour
    merged = []
    for g in groups:
        if len(g) == 1 and merged and len(merged[-1]) <= 4:
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    if len(merged) > 1 and len(merged[0]) == 1:
        merged[1] = merged[0] + merged[1]; merged = merged[1:]
    groups = merged
    caps = []
    for n, g in enumerate(groups):
        t0 = times[min(g[0], len(times) - 1)][0]
        t1 = times[g[-1] + 1][0] if g[-1] + 1 < len(times) else vo
        text = re.sub(r"\*(.+?)\*", r"<b>\1</b>", " ".join(script[k] for k in g))
        caps.append(f'  <div id="cap{n}" class="clip cap" data-start="{t0:.2f}" data-duration="{max(0.3, t1 - t0):.2f}" data-track-index="2"><span>{text}</span></div>')

    card_html, card_t = "", 0
    if "card" in plan:
        c = plan["card"]; card_t = at(c["at"])
        card_html = (f'  <div id="card-wrap" class="clip" data-start="{card_t}" data-duration="{D - card_t:.2f}" data-track-index="1">'
                     f'<div id="card"><div class="k">{c["kicker"]}</div><div class="v">{c["value"]}</div><div class="n">{c["note"]}</div></div></div>')

    bx, by, bw, bh = rig["mouth"]["box"]
    ex, ey, ew, eh = rig["eyes"]["box"]
    pose_tags = "\n".join(f'      <img class="pose" id="p-{p}" src="assets/rig/pose_{p}.png" style="opacity:{1 if k == 0 else 0}">'
                          for k, p in enumerate(rig["poses"]))
    mouth_tags = "\n".join(f'      <img class="mouth" id="m-{m}" src="assets/rig/mouth_{m}.png" style="left:{bx}px;top:{by}px;width:{bw}px;height:{bh}px;opacity:{1 if m == "X" else 0}">'
                           for m in rig["mouth"]["shapes"])
    eye_tags = "\n".join(f'      <img class="eyes" id="e-{e}" src="assets/rig/eyes_{e}.png" style="left:{ex}px;top:{ey}px;width:{ew}px;height:{eh}px;opacity:{1 if e == "open" else 0}">'
                         for e in rig["eyes"]["states"])
    cues = {"mouth": json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"], "eyes": eyes, "poses": poses,
            "vo": round(vo, 3), "card": card_t, "depth": a.depth,
            # the rig's quality gate decides; --remap adds manual overrides on top
            "remap": {**rig["mouth"].get("remap", {}),
                      **(dict(kv.split("=") for kv in a.remap.split(",") if kv) if a.remap else {})},
            "ids": {"mouth": rig["mouth"]["shapes"], "eyes": rig["eyes"]["states"], "poses": rig["poses"]}}
    desk = int(a.top + rig["bottom"] * s) - 10
    html = (HTML.replace("__LEFT__", str(left)).replace("__TOP__", str(a.top)).replace("__W__", str(W)).replace("__H__", str(H))
            .replace("__S__", f"{s:.5f}").replace("__DESK__", str(desk)).replace("__CAPTOP__", str(a.cap_top))
            .replace("__DUR__", str(D)).replace("__VODUR__", f"{vo:.2f}").replace("__TAG__", f'  <div class="tag">{a.title}</div>' if a.title else "")
            .replace("__CARD__", card_html).replace("__POSES__", pose_tags).replace("__MOUTHS__", mouth_tags)
            .replace("__EYES__", eye_tags).replace("__CAPS__", "\n".join(caps)).replace("__CUES__", json.dumps(cues)))
    (out / "index.html").write_text(html, encoding="utf-8")
    # face rectangle in frame coordinates, for scripts/audit_face.py (every-frame review)
    fx0 = min(bx, ex); fy0 = min(by, ey); fx1 = max(bx + bw, ex + ew); fy1 = max(by + bh, ey + eh)
    m = 40
    (out / "audit.json").write_text(json.dumps({"face": [int(left + (fx0 - m) * s), int(a.top + (fy0 - m) * s),
                                                         int((fx1 - fx0 + 2 * m) * s), int((fy1 - fy0 + 2 * m) * s)]}))
    print(json.dumps({"ok": True, "duration": D, "captions": len(caps), "poses": poses, "eyes": eyes}))


if __name__ == "__main__":
    sys.exit(main())
