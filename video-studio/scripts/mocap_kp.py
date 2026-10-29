#!/usr/bin/env python3
"""Keypoint motion capture for 2D puppets (position-based retargeting, not joint angles).

  python -I mocap_kp.py clip.mp4 --out motion_kp.json [--crop 405x720+437+0] [--fps 30] [--debug dbg.mp4]

Per output frame, for SCREEN sides L and R:
  sh, el, wr     shoulder / elbow / wrist, normalised: origin = shoulder midpoint,
                 unit = shoulder width, y down (so the puppet can be any size)
  hand: {"dir": finger direction deg (wrist -> middle knuckle, screen), "len": wrist->middle
         fingertip length (normalised), "n": palm normal [x,y,z] (MediaPipe world coords,
         sign fixed by handedness), "shape": open/point/count2/count3/fist/thumb, "seen": bool}
  head: nose (normalised), roll deg
Missing detections are filled (interpolated) and everything is smoothed (zero-phase).
"""
import argparse
import json
import math
import pathlib
import sys

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

MODELS = _paths.mediapipe_models()


def smooth(x, alpha):
    x = np.asarray(x, float)
    f = x.copy()
    for i in range(1, len(f)):
        f[i] = alpha * x[i] + (1 - alpha) * f[i - 1]
    b = f.copy()
    for i in range(len(b) - 2, -1, -1):
        b[i] = alpha * f[i] + (1 - alpha) * b[i + 1]
    return b


def fill(x):
    x = np.asarray(x, float)
    idx = np.arange(len(x)); g = ~np.isnan(x)
    if g.sum() == 0:
        return np.zeros_like(x)
    return np.interp(idx, idx[g], x[g])


def finger_ext(lm):
    lm = np.asarray(lm)
    w = lm[0]
    def ext(tip, pip):
        return np.linalg.norm(lm[tip] - w) > 1.12 * np.linalg.norm(lm[pip] - w)
    thumb = np.linalg.norm(lm[4] - lm[9]) > 0.75 * np.linalg.norm(lm[9] - w)
    return [thumb, ext(8, 6), ext(12, 10), ext(16, 14), ext(20, 18)]


def shape_of(fs):
    t, i, m, r, p = fs
    n = i + m + r + p
    if n == 0:
        return "thumb" if t else "fist"
    if i and not (m or r or p):
        return "point"
    if i and m and not (r or p):
        return "count2"
    if i and m and r and not p:
        return "count3"
    return "open"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop", default=None)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--debug")
    a = ap.parse_args()
    cap = cv2.VideoCapture(a.video)
    sfps = cap.get(cv2.CAP_PROP_FPS) or 24
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if a.crop:
            cw, ch, cx, cy = [int(v) for v in a.crop.replace("x", " ").replace("+", " ").split()]
            fr = fr[cy:cy + ch, cx:cx + cw]
        frames.append(fr)
    H, W = frames[0].shape[:2]
    pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "pose_landmarker_heavy.task")),
        running_mode=vision.RunningMode.VIDEO, min_pose_detection_confidence=0.3, min_tracking_confidence=0.3))
    hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "hand_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO, num_hands=2, min_hand_detection_confidence=0.25, min_tracking_confidence=0.25))
    keys = ["shLx", "shLy", "shRx", "shRy", "elLx", "elLy", "elRx", "elRy", "wrLx", "wrLy", "wrRx", "wrRy", "noseX", "noseY", "roll",
            "hdirL", "hdirR", "hlenL", "hlenR", "nLx", "nLy", "nLz", "nRx", "nRy", "nRz"]
    raw = {k: [] for k in keys}
    shapes = {"L": [], "R": []}
    vw = cv2.VideoWriter(a.debug, cv2.VideoWriter_fourcc(*"mp4v"), sfps, (W, H)) if a.debug else None
    for i, fr in enumerate(frames):
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        ts = int(i * 1000 / sfps)
        pr = pose.detect_for_video(img, ts)
        hr = hands.detect_for_video(img, ts)
        P = [(l.x * W, l.y * H) for l in pr.pose_landmarks[0]] if pr.pose_landmarks else None
        if P:
            # screen-left = person's right side (ids 12/14/16)
            sL, sR = np.array(P[12]), np.array(P[11])
            if sL[0] > sR[0]:
                sL, sR = sR, sL
            mid = (sL + sR) / 2; u = np.linalg.norm(sR - sL)
            nrm = lambda p: (np.array(p) - mid) / u
            eL, eR, wL, wR = P[14], P[13], P[16], P[15]
            if P[14][0] > P[13][0] and P[16][0] > P[15][0]:
                eL, eR, wL, wR = P[13], P[14], P[15], P[16]
            vals = {"sh": (nrm(sL), nrm(sR)), "el": (nrm(eL), nrm(eR)), "wr": (nrm(wL), nrm(wR))}
            for k, (l_, r_) in vals.items():
                raw[k + "Lx"].append(l_[0]); raw[k + "Ly"].append(l_[1]); raw[k + "Rx"].append(r_[0]); raw[k + "Ry"].append(r_[1])
            nz = nrm(P[0]); raw["noseX"].append(nz[0]); raw["noseY"].append(nz[1])
            raw["roll"].append(math.degrees(math.atan2(P[7][1] - P[8][1], P[7][0] - P[8][0])) if P[7][0] > P[8][0]
                               else math.degrees(math.atan2(P[8][1] - P[7][1], P[8][0] - P[7][0])))
        else:
            mid, u = None, None
            for k in keys[:15]:
                raw[k].append(np.nan)
        got = {"L": None, "R": None}
        if hr.hand_landmarks and P:
            for hl, hw, hd in zip(hr.hand_landmarks, hr.hand_world_landmarks, hr.handedness):
                pts = np.array([(p.x * W, p.y * H) for p in hl])
                wpt = np.array([(p.x, p.y, p.z) for p in hw])
                side = "L" if np.linalg.norm(pts[0] - np.array(wL)) < np.linalg.norm(pts[0] - np.array(wR)) else "R"
                n = np.cross(wpt[5] - wpt[0], wpt[17] - wpt[0])
                if hd[0].category_name == "Left":       # mirror-consistent normal for both hands
                    n = -n
                n = n / (np.linalg.norm(n) + 1e-9)
                d = pts[9] - pts[0]
                got[side] = {"dir": math.degrees(math.atan2(d[1], d[0])),
                             "len": np.linalg.norm(pts[12] - pts[0]) / u, "n": n, "shape": shape_of(finger_ext(pts))}
        for s in ("L", "R"):
            g = got[s]
            raw["hdir" + s].append(g["dir"] if g else np.nan)
            raw["hlen" + s].append(g["len"] if g else np.nan)
            for c, v in zip("xyz", g["n"] if g else (np.nan,) * 3):
                raw["n" + s + c].append(v)
            shapes[s].append(g["shape"] if g else None)
        if vw is not None:
            if P:
                for p in (12, 11, 14, 13, 16, 15):
                    cv2.circle(fr, (int(P[p][0]), int(P[p][1])), 4, (0, 0, 255), -1)
            for s, g in got.items():
                if g:
                    cv2.putText(fr, f"{s}:{g['shape']} n=({g['n'][0]:.1f},{g['n'][1]:.1f},{g['n'][2]:.1f})",
                                (8, 24 if s == "L" else 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
            vw.write(fr)
    if vw is not None:
        vw.release()
    n_src = len(frames)
    t_src = np.arange(n_src) / sfps
    n_out = int(round(t_src[-1] * a.fps)) + 1
    t_dst = np.arange(n_out) / a.fps
    out = {"fps": a.fps, "frames": n_out}
    for k in keys:
        x = fill(raw[k])
        if k.startswith("hdir") or k == "roll":
            x = np.degrees(np.unwrap(np.radians(x)))
        x = smooth(x, 0.5 if k.startswith(("wr", "hdir", "n")) else 0.4)
        out[k] = [round(float(v), 4) for v in np.interp(t_dst, t_src, x)]
    for s in ("L", "R"):
        last, res = "open", []
        for i in range(n_src):
            win = [v for v in shapes[s][max(0, i - 3):i + 4] if v]
            if win:
                last = max(set(win), key=win.count)
            res.append(last)
        out["shape" + s] = [res[min(n_src - 1, int(round(t * sfps)))] for t in t_dst]
        out["seen" + s] = [shapes[s][min(n_src - 1, int(round(t * sfps)))] is not None for t in t_dst]
    pathlib.Path(a.out).write_text(json.dumps(out))
    print(json.dumps({"ok": True, "frames": n_out, "hands_seen": {s: sum(out["seen" + s]) for s in "LR"},
                      "shapes": {s: {k: out["shape" + s].count(k) for k in set(out["shape" + s])} for s in "LR"}}))


if __name__ == "__main__":
    sys.exit(main())
