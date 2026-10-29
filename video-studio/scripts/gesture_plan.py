#!/usr/bin/env python3
"""Authored hand gestures for a cutout puppet: FEW, minimal, never a cut to a pose.

The hands rest hidden behind a desk edge at chest height. A gesture rises from behind the
desk (eased, a little overshoot), holds with a slow drift, hits a small beat on the stressed
words (wrist dip + head nod), then sinks back out of sight. Hand drawings are chosen per
gesture and only change while the hand is hidden, so no drawing swap is ever seen.

  python -I gesture_plan.py --rig rig --transcript transcript.json --gestures gestures.json \
      --duration 8.6 --out motion_gest.json [--desk 840] [--fps 30]

gestures.json: [{"type": "point", "side": "L", "at": "wrong", "beats": ["wrong"], "until": "money."},
                {"type": "open", "side": "LR", "at": "fees", "beats": ["fees", "inside"], "until": "are."}]
  "at" / "beats" / "until": a word (first match after the previous gesture) or seconds.
  types: point (index up), open (relaxed open palm), present (palm up, offering), stop (palm to camera)
Render with puppet_render.py --motion motion_gest.json (authored mode).
"""
import argparse
import json
import math
import pathlib
import sys

import numpy as np

# Poses in units of the shoulder width U, from the shoulder (elbow) and from the elbow (wrist),
# for the screen-LEFT arm; the right arm mirrors x. fdir = finger direction (screen deg).
POSES = {
    "point":   {"hand": "point_cam", "el": (-0.14, 0.63), "fa": (0.15, -0.49), "fdir": -88},
    "open":    {"hand": "palm_tilt", "el": (-0.15, 0.63), "fa": (0.07, -0.40), "fdir": -100},
    "present": {"hand": "palm_up",   "el": (-0.16, 0.63), "fa": (0.12, -0.33), "fdir": -95},
    "stop":    {"hand": "palm_cam",  "el": (-0.14, 0.63), "fa": (0.13, -0.42), "fdir": -92},
}
RISE, FALL = 0.42, 0.50          # seconds
LEAD = 0.06                      # arrive this long before the stressed word


def ease_out_back(x, k=1.25):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def bump(x):
    """0 -> 1 -> 0 over x in [0, 1], fast attack, soft release."""
    if x <= 0 or x >= 1:
        return 0.0
    return math.sin(math.pi * x ** 0.6)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rig", required=True)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--gestures", required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--desk", type=float, default=None, help="desk line, rig-sheet px (default: just above the rest elbows)")
    ap.add_argument("--fps", type=float, default=30)
    a = ap.parse_args()
    rig = json.loads((pathlib.Path(a.rig) / "rig.json").read_text())
    J = rig["joints"]
    sh = {s: np.array(J[s]["shoulder"], float) for s in "LR"}
    el_rest = {s: np.array(J[s]["elbow_u"], float) for s in "LR"}
    U = float(np.linalg.norm(sh["R"] - sh["L"]))
    cx = (sh["L"][0] + sh["R"][0]) / 2
    desk = a.desk if a.desk is not None else float(min(el_rest["L"][1], el_rest["R"][1]) - 12)
    words = json.loads(pathlib.Path(a.transcript).read_text())
    n = int(round(a.duration * a.fps)) + 1
    t = np.arange(n) / a.fps

    cursor = [0.0]

    def when(v, after=None):
        if isinstance(v, (int, float)):
            return float(v)
        lo = cursor[0] if after is None else after
        for w in words:
            if w["start"] >= lo - 1e-6 and w["text"].strip().lower().strip(".,!?") == v.lower().strip(".,!?"):
                return float(w["start"])
        raise SystemExit(f"word not found after {lo:.2f}s: {v}")

    def word_end(v, after):
        if isinstance(v, (int, float)):
            return float(v)
        for w in words:
            if w["start"] >= after - 1e-6 and w["text"].strip().lower().strip(".,!?") == v.lower().strip(".,!?"):
                return float(w["end"])
        raise SystemExit(f"word not found after {after:.2f}s: {v}")

    # per side: progress p(t) in [0, 1+overshoot], the pose, beats
    prog = {s: np.zeros(n) for s in "LR"}
    pose_of = {s: [None] * n for s in "LR"}
    beat = {s: np.zeros(n) for s in "LR"}
    nod = np.zeros(n)
    roll = np.zeros(n)
    last_hand = {s: POSES["open"]["hand"] for s in "LR"}
    for g in json.loads(pathlib.Path(a.gestures).read_text()):
        P = POSES[g["type"]]
        t_at = when(g["at"])
        t0 = t_at - LEAD - RISE
        t_end = word_end(g["until"], t_at)
        t1 = t_end + 0.05
        cursor[0] = t_at
        bts = [when(b, t_at - 0.01) for b in g.get("beats", [])]
        for s in g["side"]:
            for i, ti in enumerate(t):
                if t0 <= ti < t0 + RISE:
                    p = ease_out_back((ti - t0) / RISE)
                elif t0 + RISE <= ti <= t1:
                    p = 1.0
                elif t1 < ti < t1 + FALL:
                    p = 1 - ease_in_out((ti - t1) / FALL)
                else:
                    continue
                prog[s][i] = p
                pose_of[s][i] = P
            for b in bts:
                beat[s] += np.array([bump((ti - b + 0.04) / 0.30) for ti in t])
        for b in bts:
            nod += np.array([bump((ti - b + 0.02) / 0.34) for ti in t])
        side_sign = {"L": -1, "R": 1, "LR": 0, "RL": 0}[g["side"]]
        roll += side_sign * 1.6 * np.array([prog[g["side"][0]][i] for i in range(n)])

    out = {"space": "sheet", "fps": a.fps, "frames": n, "desk": desk, "roll": [], "nod": [], "breath": []}
    for k in ("elLx", "elLy", "elRx", "elRy", "wrLx", "wrLy", "wrRx", "wrRy", "hdirL", "hdirR", "handL", "handR"):
        out[k] = []
    for s in "LR":
        mx = -1 if s == "L" else 1        # mirror x for the screen-right arm
        prev_fdir = None
        for i, ti in enumerate(t):
            p = prog[s][i]
            P = pose_of[s][i]
            if P is None:                 # resting: keep the last hand drawing, hidden
                P = POSES["open"] if last_hand[s] is None else next((q for q in POSES.values() if q["hand"] == last_hand[s]), POSES["open"])
            last_hand[s] = P["hand"]
            pe = np.clip(p, 0, 1)
            el_pose = sh[s] + np.array([P["el"][0] if s == "L" else -P["el"][0], P["el"][1]]) * U
            el = el_rest[s] + (el_pose - el_rest[s]) * pe
            # forearm: a signed length along a direction that starts straight up. While the
            # length is negative the forearm points DOWN behind the desk; it passes through zero
            # vertically under the desk line, so it never sweeps sideways in view.
            fa = np.array([P["fa"][0] if s == "L" else -P["fa"][0], P["fa"][1]]) * U
            L_pose = float(np.linalg.norm(fa)); th_pose = math.atan2(fa[1], fa[0])
            L_hide = -0.46 * U
            ln = L_hide + (L_pose - L_hide) * p              # overshoot carries through the length
            tilt = min(max((p - 0.55) / 0.45, 0.0), 1.0)
            th = -math.pi / 2 + (th_pose + math.pi / 2) * ease_in_out(tilt) if p > 0.55 else -math.pi / 2
            wr = el + ln * np.array([math.cos(th), math.sin(th)])
            # hold: slow drift + beat (wrist dips toward the elbow)
            drift = np.array([3.0 * math.sin(2 * math.pi * 0.55 * ti + (0 if s == "L" else 1.7)),
                              2.5 * math.sin(2 * math.pi * 0.42 * ti + 0.6)]) * pe
            wr = wr + drift + beat[s][i] * 0.05 * U * np.array([0.25 * mx * -1, 1.0])
            # finger direction trails the forearm a little (overlapping action)
            fdir_t = math.degrees(th) + (P["fdir"] + 90 if s == "L" else -(P["fdir"] + 90)) * tilt
            fdir = fdir_t if prev_fdir is None else prev_fdir + 0.45 * (fdir_t - prev_fdir)
            prev_fdir = fdir
            out[f"el{s}x"].append(round(float(el[0]), 2)); out[f"el{s}y"].append(round(float(el[1]), 2))
            out[f"wr{s}x"].append(round(float(wr[0]), 2)); out[f"wr{s}y"].append(round(float(wr[1]), 2))
            out[f"hdir{s}"].append(round(float(fdir), 2)); out[f"hand{s}"].append(P["hand"])
    for i, ti in enumerate(t):
        out["nod"].append(round(float(6.0 * nod[i]), 2))
        out["roll"].append(round(float(roll[i]), 2))
        out["breath"].append(round(float(-2.0 * math.sin(2 * math.pi * 0.22 * ti)), 2))
    # the same Rhubarb / blink machinery reads these; keep the mocap keys it expects
    for k in ("shLx", "shLy", "shRx", "shRy"):
        out[k] = [0.0] * n
    pathlib.Path(a.out).write_text(json.dumps(out))
    vis = {s: round(float(np.mean(prog[s] > 0)), 2) for s in "LR"}
    print(json.dumps({"ok": True, "frames": n, "desk": desk, "hands_up_fraction": vis}))


if __name__ == "__main__":
    sys.exit(main())
