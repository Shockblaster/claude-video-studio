#!/usr/bin/env python3
"""HyperFrames scene for a cutout puppet (cutout_rig.py body + face_rig.py face).

  python -I build_cutout_scene.py --rig rig_dir --face face_dir --face-offset 2,2 \
      --poses poses.json --voice vo.wav --mouth mouth.json --words transcript.json \
      --script script.txt --plan plan.json --out project_dir [--scale 1.15] [--center-x 510]

plan.json: {"gestures": [["w0","point"], ["w8","rest"], ...],      # pose names from poses.json
            "blinks": "auto", "card": {"at": "w13", "kicker": "...", "value": "...", "note": "..."}}
Arms are joint chains: shoulder div -> elbow div, tweened between poses with easing; the hand
piece swaps at the middle of each move. Upper arms render behind the torso, forearms in
front (a twin chain driven by the same tweens). Face: upper / lower states of ONE drawing.
"""
import argparse
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys

import cv2
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

HTML = r"""<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
<title>Cutout puppet</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face { font-family: "Inter"; src: url("assets/fonts/InterVariable.woff2") format("woff2"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1080px; height: 1920px; overflow: hidden; background: #eef1f6; font-family: "Inter", sans-serif; }
#bg { position: absolute; inset: 0; background: radial-gradient(110% 70% at 50% 42%, #ffffff 0%, #eef1f6 48%, #d6dee9 100%); }
#stage { position: absolute; left: __LEFT__px; top: __TOP__px; width: __SW__px; height: __SH__px; transform: scale(__S__); transform-origin: 0 0; }
.j { position: absolute; left: 0; top: 0; width: 0; height: 0; }
.j > img, .j > .p > img { position: absolute; display: block; }
.p { position: absolute; left: 0; top: 0; width: 0; height: 0; }
#desk { position: absolute; left: 0; right: 0; top: __DESK__px; bottom: 0; background: linear-gradient(180deg, #00357a 0%, #002357 100%); border-top: 6px solid #f4d049; }
#card-wrap { position: absolute; left: 90px; right: 90px; top: 196px; }
#card { background: #fff; border-radius: 34px; padding: 34px 44px; box-shadow: 0 24px 60px rgba(0,53,122,.18); border: 2px solid #e3e8f0; }
#card .k { font-size: 34px; font-weight: 650; color: #608396; }
#card .v { font-size: 96px; font-weight: 800; color: #00357a; line-height: 1.04; }
#card .n { font-size: 30px; font-weight: 600; color: #4a4848; margin-top: 6px; }
.cap { position: absolute; left: 60px; right: 60px; top: __CAPTOP__px; text-align: center; }
.cap span { display: inline-block; background: rgba(10,18,34,.86); color: #fff; font-size: 56px; font-weight: 800; padding: 10px 26px; border-radius: 18px; }
.cap b { color: #f4d049; }
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__" data-width="1080" data-height="1920">
  <div id="bg"></div>
__CARD__
  <div id="stage" class="clip" data-start="0" data-duration="__DUR__" data-track-index="0">
    <div id="enter" class="j"><div id="body" class="j">
__BODY__
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

// seek-safe visibility tracks: each element gets explicit sets only when its own state changes
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

// lip-sync on ONE drawing (lower-face states)
track("lo-", C.ids.mouth, [[0, "X"], ...C.mouth.map(c => [c.start, c.value]), [C.vo + 0.05, "X"]]);

// blinks: open -> half -> closed -> half -> open, seeded, never during a gesture peak
const ev = [[0, "open"]];
let seed = 7, bt = 1.3;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
while (bt < D - 0.4) {
  ev.push([bt, "half"], [bt + f, "closed"], [bt + 3 * f, "half"], [bt + 4 * f, "open"]);
  bt += 2.4 + rnd() * 2.2;
}
ev.sort((a, b) => a[0] - b[0]);
track("up-", C.ids.eyes, ev);

// arms: each pose = joint angles; tween between them, hand piece swaps mid-move
const A = C.angles;                // pose -> {sL, eL, sR, eR, hL, hR}
let prev = C.gestures[0][1];
tl.set(["#shL", "#shL2"], { rotation: A[prev].sL }, 0).set(["#shR", "#shR2"], { rotation: A[prev].sR }, 0)
  .set("#elL", { rotation: A[prev].eL }, 0).set("#elR", { rotation: A[prev].eR }, 0);
const handEv = { L: [[0, A[prev].hL]], R: [[0, A[prev].hR]] };
for (const [t, pose] of C.gestures.slice(1)) {
  if (pose === prev) continue;
  const p = A[pose], q = A[prev];
  const dur = 0.42, t0 = Math.max(0, t - 0.30);
  tl.fromTo(["#shL", "#shL2"], { rotation: q.sL }, { rotation: p.sL, duration: dur, ease: "power2.inOut", immediateRender: false }, t0)
    .fromTo(["#shR", "#shR2"], { rotation: q.sR }, { rotation: p.sR, duration: dur, ease: "power2.inOut", immediateRender: false }, t0)
    .fromTo("#elL", { rotation: q.eL }, { rotation: p.eL, duration: dur + 0.06, ease: "back.out(1.4)", immediateRender: false }, t0 + 0.02)
    .fromTo("#elR", { rotation: q.eR }, { rotation: p.eR, duration: dur + 0.06, ease: "back.out(1.4)", immediateRender: false }, t0 + 0.02);
  if (p.hL !== q.hL) handEv.L.push([t0 + dur * 0.3, p.hL]);
  if (p.hR !== q.hR) handEv.R.push([t0 + dur * 0.3, p.hR]);
  prev = pose;
}
track("hd-", C.ids.handsL, handEv.L);
track("hd-", C.ids.handsR, handEv.R);

// head: small nods and tilts on the beat of the speech, lagging the body a little
const beats = C.headBeats;
let hv = 0;
for (let i = 0; i < beats.length; i++) {
  const [t, r, y] = beats[i];
  tl.fromTo("#head", { rotation: hv }, { rotation: r, duration: 0.5, ease: "sine.inOut", immediateRender: false }, t);
  tl.fromTo("#headnod", { y: 0 }, { y: y, duration: 0.18, ease: "power1.out", yoyo: true, repeat: 1, immediateRender: false }, t);
  hv = r;
}
// life: breathing and sway (explicit from-values: seek-safe)
tl.fromTo("#body", { scaleY: 1 }, { scaleY: 1.006, transformOrigin: "50% 100%", duration: 1.7, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.floor(D / 1.7) - 1) }, 0);
tl.fromTo("#enter", { y: 380 }, { y: 0, duration: 0.55, ease: "power3.out" }, 0);
if (document.getElementById("card")) tl.fromTo("#card", { y: 40, scale: 0.88, opacity: 0 }, { y: 0, scale: 1, opacity: 1, transformOrigin: "50% 100%", duration: 0.5, ease: "back.out(1.5)" }, C.card);
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout.strip())


def img(src, x, y, w, h, op=1, idd=None):
    i = f' id="{idd}"' if idd else ""
    return f'<img{i} src="{src}" style="left:{x:.1f}px;top:{y:.1f}px;width:{w}px;height:{h}px;opacity:{op}">'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("rig", "face", "poses", "voice", "mouth", "words", "script", "plan", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--face-offset", default="2,2", help="face canvas origin relative to the head piece, sheet px")
    ap.add_argument("--face-scale", type=float, default=2.0)
    ap.add_argument("--scale", type=float, default=1.15)
    ap.add_argument("--center-x", type=float, default=None, help="sheet x to put at frame centre")
    ap.add_argument("--top", type=int, default=470, help="frame y of the sheet's head top")
    ap.add_argument("--cut", type=int, default=None, help="sheet y where the desk starts (default torso bottom)")
    ap.add_argument("--cap-top", type=int, default=470)
    ap.add_argument("--fonts", default=str(_paths.fonts_dir()))
    a = ap.parse_args()
    rd, fd, out = pathlib.Path(a.rig), pathlib.Path(a.face), pathlib.Path(a.out)
    rig = json.loads((rd / "rig.json").read_text())
    face = json.loads((fd / "face.json").read_text())
    poses = json.loads(pathlib.Path(a.poses).read_text())
    (out / "assets" / "p").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    for f in (rd / "pieces").glob("*.png"):
        shutil.copy(f, out / "assets" / "p" / f.name)
    # face states: crop to the two halves (upper rows [0,split), lower [split,H))
    sp = face["split"]
    for f in fd.glob("upper_*.png"):
        im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED); cv2.imwrite(str(out / "assets" / "p" / ("f" + f.name)), im[:sp])
    for f in fd.glob("lower_*.png"):
        im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED); cv2.imwrite(str(out / "assets" / "p" / ("f" + f.name)), im[sp:])
    shutil.copy(pathlib.Path(a.fonts) / "InterVariable.woff2", out / "assets" / "fonts")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.voice, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(out / "assets" / "vo.wav")], check=True)

    def size(name):
        im = cv2.imread(str(rd / "pieces" / f"{name}.png"), cv2.IMREAD_UNCHANGED)
        return im.shape[1], im.shape[0]

    T = rig["torso_pos"]; att = rig["torso_attach"]
    body = []
    angles = {}
    hands = {"L": sorted({p["hand_L"] for p in poses.values()}), "R": sorted({p["hand_R"] for p in poses.values()})}
    for name, p in poses.items():
        ang = {}
        for s in ("L", "R"):
            ua = rig["upper_" + s]
            sa = p["shoulder_" + s]
            ex, ey = ua["elbow"][0] - ua["shoulder"][0], ua["elbow"][1] - ua["shoulder"][1]
            # elbow div local rotation so the (normalised) forearm points along fdir in the world
            ang["s" + s] = sa
            ang["e" + s] = p["fdir_" + s] - sa
            ang["h" + s] = p["hand_" + s]
        angles[name] = ang

    def arm_chain(s, with_upper, with_fore, suffix):
        ua = rig["upper_" + s]
        sock = [T[0] + att["socket_" + s][0], T[1] + att["socket_" + s][1]]
        w, h = size(ua["name"])
        parts = [f'<div id="sh{s}{suffix}" class="j" style="left:{sock[0]:.1f}px;top:{sock[1]:.1f}px">']
        if with_upper:
            parts.append(img(f"assets/p/{ua['name']}.png", -ua["shoulder"][0], -ua["shoulder"][1], w, h))
        if with_fore:
            ex, ey = ua["elbow"][0] - ua["shoulder"][0], ua["elbow"][1] - ua["shoulder"][1]
            parts.append(f'<div id="el{s}" class="j" style="left:{ex:.1f}px;top:{ey:.1f}px">')
            for hn in hands[s]:
                fa = rig["forearms"][hn]
                fw, fh = size(hn)
                rest = math.degrees(math.atan2(fa["hand"][1] - fa["elbow"][1], fa["hand"][0] - fa["elbow"][0]))
                # normalise every hand piece so its elbow->hand axis lies along local +x
                parts.append(f'<div class="p" style="transform:rotate({-rest:.3f}deg)">'
                             + img(f"assets/p/{hn}.png", -fa["elbow"][0], -fa["elbow"][1], fw, fh,
                                   1 if hn == poses[list(poses)[0]]["hand_" + s] else 0, f"hd-{hn}") + '</div>')
            parts.append('</div>')
        parts.append('</div>')
        return "\n".join(parts)

    # elbow angles are relative to the world +x axis; the shoulder div adds its own rotation,
    # so the elbow div's rotation = fdir - shoulder (computed above)
    body.append(arm_chain("L", True, False, ""))
    body.append(arm_chain("R", True, False, ""))
    tw, th = size("torso")
    body.append(f'<div class="j" style="left:{T[0]}px;top:{T[1]}px">' + img("assets/p/torso.png", 0, 0, tw, th) + '</div>')
    body.append(arm_chain("L", False, True, "2"))
    body.append(arm_chain("R", False, True, "2"))
    hp = rig["head_pos"]; hpv = rig["head_pivot"]
    fx, fy = [float(v) for v in a.face_offset.split(",")]
    FW, FH = face["canvas"]
    k = 1 / a.face_scale
    head = [f'<div id="headnod" class="j" style="left:{hp[0] + hpv[0]:.1f}px;top:{hp[1] + hpv[1]:.1f}px">',
            '<div id="head" class="j">']
    ox, oy = fx - hpv[0], fy - hpv[1]
    for e in face["eyes"]:
        head.append(img(f"assets/p/fupper_{e}.png", ox, oy, int(FW * k), int(sp * k), 1 if e == "open" else 0, f"up-{e}"))
    for m in face["shapes"]:
        head.append(img(f"assets/p/flower_{m}.png", ox, oy + sp * k, int(FW * k), int((FH - sp) * k), 1 if m == "X" else 0, f"lo-{m}"))
    head.append('</div></div>')
    body.append("\n".join(head))

    vo = dur(a.voice)
    D = round(vo + 0.8, 2)
    words = json.loads(pathlib.Path(a.words).read_text(encoding="utf-8"))
    words = words["words"] if isinstance(words, dict) else words
    times = [(w["start"], w["end"]) for w in words]
    script = pathlib.Path(a.script).read_text(encoding="utf-8").split()

    def at(v):
        if isinstance(v, str) and v.startswith("w"):
            return round(times[min(int(v[1:]), len(times) - 1)][0], 3)
        return float(v)

    plan = json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8"))
    gestures = [[at(t), p] for t, p in plan["gestures"]]
    if gestures[0][0] > 0:
        gestures.insert(0, [0, "rest"])
    # head beats: a small tilt/nod at every sentence start and every ~4th word
    beats = []
    sign = 1
    for i, (t, _) in enumerate(times):
        if i == 0 or re.search(r"[.!?,]\**$", script[min(i - 1, len(script) - 1)]) or i % 4 == 0:
            beats.append([round(t, 3), sign * (1.2 + 0.6 * ((i * 7) % 3) / 2), 3 if i % 2 else 2])
            sign = -sign
    beats.append([round(vo, 3), 0, 0])

    # captions (same grouping rules as build_puppet_scene.py)
    groups, cur = [], []
    for kx, w in enumerate(script):
        cur.append(kx)
        if len(cur) == 4 or re.search(r"[.!?,]\**$", w):
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    merged = []
    for g in groups:
        if len(g) == 1 and merged and len(merged[-1]) <= 4:
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    caps = []
    for n, g in enumerate(merged):
        t0 = times[min(g[0], len(times) - 1)][0]
        t1 = times[g[-1] + 1][0] if g[-1] + 1 < len(times) else vo
        text = re.sub(r"\*(.+?)\*", r"<b>\1</b>", " ".join(script[x] for x in g))
        caps.append(f'  <div id="cap{n}" class="clip cap" data-start="{t0:.2f}" data-duration="{max(0.3, t1 - t0):.2f}" data-track-index="2"><span>{text}</span></div>')
    card_html, card_t = "", 0
    if "card" in plan:
        c = plan["card"]; card_t = at(c["at"])
        card_html = (f'  <div id="card-wrap" class="clip" data-start="{card_t}" data-duration="{D - card_t:.2f}" data-track-index="1">'
                     f'<div id="card"><div class="k">{c["kicker"]}</div><div class="v">{c["value"]}</div><div class="n">{c["note"]}</div></div></div>')

    s = a.scale
    cxs = a.center_x if a.center_x is not None else T[0] + tw / 2
    head_top = hp[1]
    left = 540 - cxs * s
    top = a.top - head_top * s
    cut = a.cut if a.cut is not None else T[1] + th - 4
    desk = int(top + cut * s)
    SW, SH = rig["sheet_size"]
    cues = {"mouth": json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"], "vo": round(vo, 3), "card": card_t,
            "gestures": gestures, "angles": angles, "headBeats": beats,
            "ids": {"mouth": face["shapes"], "eyes": face["eyes"], "handsL": hands["L"], "handsR": hands["R"]}}
    html = (HTML.replace("__LEFT__", f"{left:.1f}").replace("__TOP__", f"{top:.1f}").replace("__SW__", str(SW)).replace("__SH__", str(SH))
            .replace("__S__", f"{s:.4f}").replace("__DESK__", str(desk)).replace("__CAPTOP__", str(a.cap_top))
            .replace("__DUR__", str(D)).replace("__VODUR__", f"{vo:.2f}").replace("__CARD__", card_html)
            .replace("__BODY__", "\n".join(body)).replace("__CAPS__", "\n".join(caps)).replace("__CUES__", json.dumps(cues)))
    (out / "index.html").write_text(html, encoding="utf-8")
    face_rect = [int(left + (hp[0] + fx) * s), int(top + (hp[1] + fy) * s), int(FW * k * s), int(FH * k * s)]
    (out / "audit.json").write_text(json.dumps({"face": face_rect}))
    print(json.dumps({"ok": True, "duration": D, "gestures": gestures, "face_rect": face_rect, "desk": desk}))


if __name__ == "__main__":
    sys.exit(main())
