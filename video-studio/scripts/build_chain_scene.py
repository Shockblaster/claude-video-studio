#!/usr/bin/env python3
"""HyperFrames scene for the v3 chain puppet (chain_rig.py body + face_rig.py face).

  python -I build_chain_scene.py --rig rig --face face --poses poses.json --voice vo.wav \
      --mouth mouth.json --words transcript.json --script script.txt --plan plan.json --out proj
      [--scale 0.95] [--top 600] [--cap-top 470] [--remap ""]

plan.json: {"gestures": [["w0","point"], ["w8","rest"], ...], "card": {...}}
Joint chain per arm: shoulder div (rotation S) > elbow div (e = forearm - S) > wrist div
(w = hand - forearm). Upper arm behind the torso, forearm + hands in a front twin chain.
Head (the one-drawing face) and neck sit behind the torso so the collar wraps the neck.
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
<title>Chain puppet</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face { font-family: "Inter"; src: url("assets/fonts/InterVariable.woff2") format("woff2"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1080px; height: 1920px; overflow: hidden; background: #eef1f6; font-family: "Inter", sans-serif; }
#bg { position: absolute; inset: 0; background: radial-gradient(110% 70% at 50% 42%, #ffffff 0%, #eef1f6 48%, #d6dee9 100%); }
#stage { position: absolute; left: __LEFT__px; top: __TOP__px; width: __SW__px; height: __SH__px; transform: scale(__S__); transform-origin: 0 0; }
.j { position: absolute; left: 0; top: 0; width: 0; height: 0; }
.j img { position: absolute; display: block; }
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
const REMAP = C.remap || {};
track("lo-", C.ids.mouth, [[0, "X"], ...C.mouth.map(c => [c.start, REMAP[c.value] || c.value]), [C.vo + 0.05, "X"]]);
const ev = [[0, "open"]];
let seed = 7, bt = 1.3;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
while (bt < D - 0.4) { ev.push([bt, "half"], [bt + f, "closed"], [bt + 3 * f, "half"], [bt + 4 * f, "open"]); bt += 2.4 + rnd() * 2.2; }
ev.sort((a, b) => a[0] - b[0]);
track("up-", C.ids.eyes, ev);

// arms: S (shoulder), e (elbow, relative), w (wrist, relative) per side; eased with overlap
const A = C.angles;
let prev = C.gestures[0][1];
const sides = ["L", "R"];
for (const s of sides) {
  tl.set(["#sh" + s, "#sh" + s + "2"], { rotation: A[prev]["S" + s] }, 0)
    .set("#el" + s, { rotation: A[prev]["e" + s] }, 0)
    .set(["#wr" + s, "#wr" + s + "b"], { rotation: A[prev]["w" + s] }, 0);
}
const handEv = { L: [[0, A[prev].hL]], R: [[0, A[prev].hR]] };
if (C.motion) {
  // MOCAP: one keyframe per video frame from real captured motion (seek-safe sets)
  const M = C.motion, dt = 1 / M.fps;
  handEv.L = []; handEv.R = [];
  let lastL = null, lastR = null;
  M.frames.forEach((r, i) => {
    const t = i * dt;
    tl.set(["#shL", "#shL2"], { rotation: r[0] }, t).set("#elL", { rotation: r[1], scaleY: r[3] }, t).set(["#wrL", "#wrLb"], { rotation: r[2] }, t)
      .set(["#shR", "#shR2"], { rotation: r[5] }, t).set("#elR", { rotation: r[6], scaleY: r[8] }, t).set(["#wrR", "#wrRb"], { rotation: r[7] }, t)
      .set("#body", { rotation: r[10], transformOrigin: "50% 100%" }, t).set("#head", { rotation: r[11] }, t);
    if (r.length > 12) {
      tl.set("#claspj", { opacity: r[12], x: r[13], y: r[14], rotation: r[15], scale: r[16] }, t);
      tl.set(["#wrL", "#wrR", "#wrLb", "#wrRb"], { opacity: 1 - r[12] }, t);
    }
    if (r[4] !== lastL) { handEv.L.push([t, r[4]]); lastL = r[4]; }
    if (r[9] !== lastR) { handEv.R.push([t, r[9]]); lastR = r[9]; }
  });
  C.gestures = [C.gestures[0]];
}
for (const [t, pose] of C.gestures.slice(1)) {
  if (pose === prev) continue;
  const p = A[pose], q = A[prev];
  const dur = 0.5, t0 = Math.max(0, t - 0.32);
  for (const s of sides) {
    tl.fromTo(["#sh" + s, "#sh" + s + "2"], { rotation: q["S" + s] }, { rotation: p["S" + s], duration: dur, ease: "power2.inOut", immediateRender: false }, t0)
      .fromTo("#el" + s, { rotation: q["e" + s] }, { rotation: p["e" + s], duration: dur, ease: "power2.inOut", immediateRender: false }, t0 + 0.04)
      .fromTo(["#wr" + s, "#wr" + s + "b"], { rotation: q["w" + s] }, { rotation: p["w" + s], duration: dur, ease: "back.out(1.2)", immediateRender: false }, t0 + 0.08);
    // FORESHORTENING: a big forearm swing in a flat drawing sweeps the hand far out sideways;
    // a real elbow bends toward the camera. Shorten the forearm along its own axis mid-swing.
    const de = Math.abs(p["e" + s] - q["e" + s]);
    if (de > 50) {
      const k = Math.max(0.5, 1 - de / 260);
      tl.fromTo("#el" + s, { scaleY: 1 }, { scaleY: k, duration: dur * 0.5, ease: "sine.out", immediateRender: false }, t0 + 0.04)
        .fromTo("#el" + s, { scaleY: k }, { scaleY: 1, duration: dur * 0.5, ease: "sine.in", immediateRender: false }, t0 + 0.04 + dur * 0.5);
    }
    if (p["h" + s] !== q["h" + s]) handEv[s].push([t0 + dur * 0.45, p["h" + s]]);
  }
  prev = pose;
}
track("hd-", C.ids.handsL, handEv.L);
track("hd-", C.ids.handsR, handEv.R);
let hv = 0;
for (const [t, r, y] of (C.motion ? [] : C.headBeats)) {
  tl.fromTo("#head", { rotation: hv }, { rotation: r, duration: 0.5, ease: "sine.inOut", immediateRender: false }, t);
  tl.fromTo("#headnod", { y: 0 }, { y: y, duration: 0.18, ease: "power1.out", yoyo: true, repeat: 1, immediateRender: false }, t);
  hv = r;
}
tl.fromTo("#body", { scaleY: 1 }, { scaleY: 1.006, transformOrigin: "50% 100%", duration: 1.7, ease: "sine.inOut", yoyo: true, repeat: Math.max(1, Math.floor(D / 1.7) - 1) }, 0);
tl.fromTo("#enter", { y: 380 }, { y: 0, duration: 0.55, ease: "power3.out" }, 0);
if (document.getElementById("card")) tl.fromTo("#card", { y: 40, scale: 0.88, opacity: 0 }, { y: 0, scale: 1, opacity: 1, transformOrigin: "50% 100%", duration: 0.5, ease: "back.out(1.5)" }, C.card);
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


def rot2(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout.strip())


def img(src, x, y, w, h, op=1, idd=None, extra=""):
    i = f' id="{idd}"' if idd else ""
    return f'<img{i} src="{src}" style="left:{x:.1f}px;top:{y:.1f}px;width:{w}px;height:{h}px;opacity:{op}{extra}">'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("rig", "face", "poses", "voice", "mouth", "words", "script", "plan", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--face-scale", type=float, default=2.0)
    ap.add_argument("--scale", type=float, default=0.95)
    ap.add_argument("--top", type=int, default=600, help="frame y of the head top")
    ap.add_argument("--cap-top", type=int, default=470)
    ap.add_argument("--remap", default="")
    ap.add_argument("--motion", help="mocap_clip.py JSON: drives the arms frame by frame instead of plan gestures")
    ap.add_argument("--motion-start", type=float, default=0.0, help="seconds into the motion to start from")
    ap.add_argument("--fonts", default=str(_paths.fonts_dir()))
    a = ap.parse_args()
    rd, fd, out = pathlib.Path(a.rig), pathlib.Path(a.face), pathlib.Path(a.out)
    rig = json.loads((rd / "rig.json").read_text())
    face = json.loads((fd / "face.json").read_text())
    poses = json.loads(pathlib.Path(a.poses).read_text())
    (out / "assets" / "p").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    for f in (rd / "pieces").glob("*.png"):
        if not f.name.startswith("_"):
            shutil.copy(f, out / "assets" / "p" / f.name)
    sp = face["split"]
    OV = 4   # lower face overlaps the upper by a few rows: no sub-pixel seam line (states are identical there)
    for f in fd.glob("upper_*.png"):
        im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED); cv2.imwrite(str(out / "assets" / "p" / ("f" + f.name)), im[:sp])
    for f in fd.glob("lower_*.png"):
        im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED); cv2.imwrite(str(out / "assets" / "p" / ("f" + f.name)), im[sp - OV:])
    shutil.copy(pathlib.Path(a.fonts) / "InterVariable.woff2", out / "assets" / "fonts")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.voice, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(out / "assets" / "vo.wav")], check=True)

    Pc, J, Hn = rig["pieces"], rig["joints"], rig["hands"]
    # angles per pose
    angles = {}
    hands_used = {"L": set(), "R": set()}
    for name, p in poses.items():
        ang = {}
        for s in ("L", "R"):
            S = p.get("S_" + s, 0.0)
            F = p.get("F_" + s, J[s]["fdir"] + S)
            fdeg = F - J[s]["fdir"]
            Hd = p.get("H_" + s, F)
            hand = p.get("hand_" + s, "rest")
            hands_used[s].add(hand)
            ang["S" + s] = round(S, 2); ang["e" + s] = round(fdeg - S, 2); ang["w" + s] = round(Hd - fdeg, 2)
            ang["h" + s] = hand
        angles[name] = ang

    def hand_tag(s, hand, front):
        if hand == "rest":
            hr = Pc["hand_" + s + "_rest"]
            axis = J[s]["hand_rest_axis"]; piv = J[s]["hand_rest_pivot"]; w, h = hr["size"]; src = f"hand_{s}_rest"
        else:
            hh = Hn[hand]; axis = hh["axis"]; piv = hh["pivot"]; w, h = hh["size"]; src = hand
        hid = f"{s}_{hand}"
        op = 1 if hand == poses[list(poses)[0]].get("hand_" + s, "rest") else 0
        return (f'<div class="j" style="transform:rotate({-axis:.3f}deg)">'
                + img(f"assets/p/{src}.png", -piv[0], -piv[1], w, h, op, f"hd-{hid}") + "</div>")

    def chain(s, front):
        sh = J[s]["shoulder"]
        ua = Pc["uarm_" + s]; fa = Pc["farm_" + s]
        parts = [f'<div id="sh{s}{"2" if front else ""}" class="j" style="left:{sh[0]:.1f}px;top:{sh[1]:.1f}px">']
        if not front:
            parts.append(img(f"assets/p/uarm_{s}.png", ua["pos"][0] - sh[0], ua["pos"][1] - sh[1], *ua["size"]))
        else:
            eu, ef, wr = J[s]["elbow_u"], J[s]["elbow_f"], J[s]["wrist"]
            parts.append(f'<div id="el{s}" class="j" style="left:{eu[0] - sh[0]:.1f}px;top:{eu[1] - sh[1]:.1f}px">')
            # rest hand BEHIND the forearm (it has no cuff), sheet hands IN FRONT (they carry a cuff)
            parts.append(f'<div id="wr{s}b" class="j" style="left:{wr[0] - ef[0]:.1f}px;top:{wr[1] - ef[1]:.1f}px">')
            if "rest" in hands_used[s]:
                parts.append(hand_tag(s, "rest", True))
            parts.append("</div>")
            parts.append(img(f"assets/p/farm_{s}.png", fa["pos"][0] - ef[0], fa["pos"][1] - ef[1], *fa["size"]))
            parts.append(f'<div id="wr{s}" class="j" style="left:{wr[0] - ef[0]:.1f}px;top:{wr[1] - ef[1]:.1f}px">')
            for hnd in sorted(hands_used[s] - {"rest"}):
                parts.append(hand_tag(s, hnd, True))
            parts.append("</div></div>")
        parts.append("</div>")
        return "\n".join(parts)

    if a.motion:   # mocap may use any hand sprite: include them all (hidden until used)
        hands_used["L"] |= {"cR_open", "cR_point", "cR_count", "cR_palm"}
        hands_used["R"] |= {"cL_open", "cL_point", "cL_thumb", "cL_palm"}
    body = [chain("L", False), chain("R", False)]
    nk = Pc["neck"]
    body.append(img("assets/p/neck.png", nk["pos"][0], nk["pos"][1], *nk["size"]))
    hd = Pc["head"]
    FW, FH = face["canvas"]
    k = 1 / a.face_scale
    pivot = [hd["pos"][0] + hd["size"][0] / 2, hd["pos"][1] + hd["bottom"][1]]
    head = [f'<div id="headnod" class="j" style="left:{pivot[0]:.1f}px;top:{pivot[1]:.1f}px"><div id="head" class="j">']
    ox, oy = hd["pos"][0] - pivot[0], hd["pos"][1] - pivot[1]
    for e in face["eyes"]:
        head.append(img(f"assets/p/fupper_{e}.png", ox, oy, int(FW * k), int(sp * k), 1 if e == "open" else 0, f"up-{e}"))
    for m in face["shapes"]:
        head.append(img(f"assets/p/flower_{m}.png", ox, oy + (sp - OV) * k, int(FW * k), round((FH - sp + OV) * k, 2), 1 if m == "X" else 0, f"lo-{m}"))
    head.append("</div></div>")
    body.append("\n".join(head))
    t = Pc["torso"]
    body.append(img("assets/p/torso.png", t["pos"][0], t["pos"][1], *t["size"]))
    body += [chain("L", True), chain("R", True)]
    if rig.get("clasp"):
        cl = rig["clasp"]; cmx = (cl["cuffL"][0] + cl["cuffR"][0]) / 2; cmy = (cl["cuffL"][1] + cl["cuffR"][1]) / 2
        body.append(f'<div id="claspj" class="j" style="opacity:0">' + img("assets/p/clasp.png", -cmx, -cmy, *cl["size"]) + '</div>')

    vo = dur(a.voice); D = round(vo + 0.8, 2)
    words = json.loads(pathlib.Path(a.words).read_text(encoding="utf-8"))
    words = words["words"] if isinstance(words, dict) else words
    times = [(w["start"], w["end"]) for w in words]
    script = pathlib.Path(a.script).read_text(encoding="utf-8").split()

    def at(v):
        if isinstance(v, str) and v.startswith("w"):
            return round(times[min(int(v[1:]), len(times) - 1)][0], 3)
        return float(v)

    plan = json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8"))
    gestures = [[at(tt), p] for tt, p in plan["gestures"]]
    if gestures[0][0] > 0:
        gestures.insert(0, [0, "rest"])
    beats, sign = [], 1
    for i, (tt, _) in enumerate(times):
        if i == 0 or re.search(r"[.!?,]\**$", script[min(i - 1, len(script) - 1)]) or i % 4 == 0:
            beats.append([round(tt, 3), sign * (1.0 + 0.5 * ((i * 7) % 3) / 2), 3 if i % 2 else 2]); sign = -sign
    beats.append([round(vo, 3), 0, 0])
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
    cxs = t["pos"][0] + t["size"][0] / 2
    left = 540 - cxs * s
    head_top = hd["pos"][1]
    top = a.top - head_top * s
    cut = t["pos"][1] + t["size"][1] - 6
    desk = int(top + cut * s)
    SW, SH = rig["sheet"]
    motion = None
    if a.motion:
        M = json.loads(pathlib.Path(a.motion).read_text())
        fps = M["fps"]; n0 = int(a.motion_start * fps)
        nfr = int(D * fps) + 1
        SHAPE = {"L": {"open": "cR_open", "point": "cR_point", "count": "cR_count", "palm": "cR_palm"},
                 "R": {"open": "cL_open", "point": "cL_point", "thumb": "cL_thumb", "palm": "cL_palm"}}
        lenmax = {s_: max(M["len" + s_]) if M.get("len" + s_) else 1 for s_ in ("L", "R")}
        fr = []
        for i in range(nfr):
            j = min(M["frames"] - 1, n0 + i)
            row = []
            for s_ in ("L", "R"):
                u, fdir, h = M["u" + s_][j], M["f" + s_][j], M["h" + s_][j]
                S = u - J[s_]["udir"]
                fdeg = fdir - J[s_]["fdir"]
                sc = max(0.55, min(1.0, M["len" + s_][j] / lenmax[s_])) if M.get("len" + s_) else 1
                shp = M["shape" + s_][j] or "open"
                hand = SHAPE[s_].get(shp, SHAPE[s_]["open"])
                if shp in ("open", "fist") or hand == SHAPE[s_]["open"]:
                    # open hand: use whichever open drawing (straight or palm-up) already points
                    # closest to the captured hand direction -> least rotation, most natural
                    cands = [SHAPE[s_]["open"], SHAPE[s_]["palm"]]
                    def dang(x):
                        return abs((x - h + 180) % 360 - 180)
                    hand = min(cands, key=lambda c: dang(Hn[c]["axis"]))
                hands_used[s_].add(hand)
                # anatomical wrist limit: the hand stays within +-60 deg of the forearm direction
                rel = (h - fdir + 180) % 360 - 180
                h = fdir + max(-60.0, min(60.0, rel))
                row += [round(S, 2), round(fdeg - S, 2), round(h - fdeg, 2), round(sc, 3), f"{s_}_{hand}"]
            # world wrist positions (sheet px) from the chain, for the two-hands-together mode
            wpos = {}
            for k_, s_ in enumerate(("L", "R")):
                S_, e_, w_, sc_ = row[k_ * 5], row[k_ * 5 + 1], row[k_ * 5 + 2], row[k_ * 5 + 3]
                Jj = J[s_]
                sh = np.array(Jj["shoulder"]); eu = sh + rot2(S_) @ (np.array(Jj["elbow_u"]) - sh)
                v = np.array(Jj["wrist"]) - np.array(Jj["elbow_f"]); v = np.array([v[0], v[1] * sc_])
                wpos[s_] = eu + rot2(S_ + e_) @ v
            clasp = [0, 0, 0, 0, 1]
            row.append(wpos)                     # temporary: resolved after all frames are known
            row += []
            tt = M["torso_tilt"][j] if M.get("torso_tilt") else 0
            ht = M["head_tilt"][j] if M.get("head_tilt") else 0
            row += [round(tt, 2), round(ht, 2)] + clasp
            fr.append(row)
        # TWO-HANDS-TOGETHER: reference distance = the closest the captured wrists ever get
        # (hands clasped at rest); the clasp drawing is scaled so its cuffs land on the wrists
        if rig.get("clasp"):
            dists = [float(np.linalg.norm(r[10]["R"] - r[10]["L"])) for r in fr]
            dref = float(np.percentile(dists, 8))
            cl = rig["clasp"]; cw = float(np.hypot(cl["cuffR"][0] - cl["cuffL"][0], cl["cuffR"][1] - cl["cuffL"][1]))
            for r, d in zip(fr, dists):
                w = r[10]
                # soft hand-over: fully clasped below 1.08 x dref, fully open above 1.30 x dref,
                # a crossfade in between (a hard swap popped the hands across one frame)
                # instant swap while the hands are still almost touching: a crossfade ghosted
                # (two pairs of hands visible for 1-2 frames), a late swap jumped
                o = 1.0 if d < 1.12 * dref else 0.0
                if o > 0:
                    mid = (w["L"] + w["R"]) / 2
                    angc = max(-20, min(20, math.degrees(math.atan2(w["R"][1] - w["L"][1], w["R"][0] - w["L"][0]))))
                    r[13:18] = [round(o, 3), round(float(mid[0]), 1), round(float(mid[1]), 1), round(angc, 2), round(max(dref, d) / cw, 3)]
        for r in fr:
            del r[10]                            # drop the temporary wrist positions
        # tilts relative to their median, damped
        import statistics
        mt = statistics.median(r[10] for r in fr); mh = statistics.median(r[11] for r in fr)
        for r in fr:
            r[10] = round(max(-3, min(3, (r[10] - mt) * 0.6)), 2); r[11] = round(max(-6, min(6, (r[11] - mh) * 0.8)), 2)
        motion = {"fps": fps, "frames": fr}
    cues = {"mouth": json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"], "vo": round(vo, 3), "card": card_t, "motion": motion,
            "gestures": gestures, "angles": angles, "headBeats": beats,
            "remap": dict(kv.split("=") for kv in a.remap.split(",") if kv) if a.remap else {},
            "ids": {"mouth": face["shapes"], "eyes": face["eyes"],
                    "handsL": [f"L_{h}" for h in sorted(hands_used["L"])], "handsR": [f"R_{h}" for h in sorted(hands_used["R"])]}}
    # gestures use hand ids with the side prefix
    for ang in cues["angles"].values():
        ang["hL"] = "L_" + ang["hL"]; ang["hR"] = "R_" + ang["hR"]
    html = (HTML.replace("__LEFT__", f"{left:.1f}").replace("__TOP__", f"{top:.1f}").replace("__SW__", str(SW)).replace("__SH__", str(SH))
            .replace("__S__", f"{s:.4f}").replace("__DESK__", str(desk)).replace("__CAPTOP__", str(a.cap_top))
            .replace("__DUR__", str(D)).replace("__VODUR__", f"{vo:.2f}").replace("__CARD__", card_html)
            .replace("__BODY__", "\n".join(body)).replace("__CAPS__", "\n".join(caps)).replace("__CUES__", json.dumps(cues)))
    (out / "index.html").write_text(html, encoding="utf-8")
    face_rect = [int(left + hd["pos"][0] * s), int(top + hd["pos"][1] * s), int(FW * k * s), int(FH * k * s)]
    (out / "audit.json").write_text(json.dumps({"face": face_rect}))
    print(json.dumps({"ok": True, "duration": D, "gestures": gestures, "desk": desk, "face_rect": face_rect}))


if __name__ == "__main__":
    sys.exit(main())
