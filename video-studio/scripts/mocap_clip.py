#!/usr/bin/env python3
"""Motion capture from a video (e.g. a Gemini Omni clip of the character) with MediaPipe:
per frame, the 2D arm joints (shoulder, elbow, wrist), hand direction, forearm
foreshortening and a coarse hand shape, as angles ready to drive a chain puppet.

  python -I mocap_clip.py clip.mp4 --out motion.json [--debug debug.mp4] [--fps 30]

Angles are SCREEN angles in degrees (0 = right, 90 = down), for the two SCREEN sides
L (left half of the image) and R. Smoothed (One-Euro-ish exponential) and gap-filled.
hand_shape per frame: "open", "point", "count", "fist", "thumb" or null (hand not seen).
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
# pose landmark ids
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR, L_IDX, R_IDX, L_PNK, R_PNK = 11, 12, 13, 14, 15, 16, 19, 20, 17, 18


def ang(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def unwrap(series):
    out, prev = [], None
    for v in series:
        if v is None:
            out.append(None); continue
        if prev is not None:
            while v - prev > 180: v -= 360
            while v - prev < -180: v += 360
        out.append(v); prev = v
    return out


def fill_smooth(series, alpha=0.35):
    """Linear gap fill + forward/backward exponential smoothing (zero phase)."""
    xs = np.array([np.nan if v is None else v for v in series], float)
    idx = np.arange(len(xs))
    good = ~np.isnan(xs)
    if good.sum() == 0:
        return [None] * len(xs)
    xs = np.interp(idx, idx[good], xs[good])
    f = xs.copy()
    for i in range(1, len(f)): f[i] = alpha * xs[i] + (1 - alpha) * f[i - 1]
    b = f.copy()
    for i in range(len(b) - 2, -1, -1): b[i] = alpha * f[i] + (1 - alpha) * b[i + 1]
    return [round(float(v), 2) for v in b]


def finger_states(lm):
    """Extended fingers from 21 hand landmarks (image coords): thumb, index, middle, ring, pinky."""
    def ext(tip, pip, mcp):
        w = np.array(lm[0]); t, p, m = np.array(lm[tip]), np.array(lm[pip]), np.array(lm[mcp])
        return np.linalg.norm(t - w) > np.linalg.norm(p - w) * 1.1 and np.linalg.norm(t - m) > 0.6 * np.linalg.norm(m - w)
    thumb = np.linalg.norm(np.array(lm[4]) - np.array(lm[5])) > 0.55 * np.linalg.norm(np.array(lm[5]) - np.array(lm[0]))
    return [thumb, ext(8, 6, 5), ext(12, 10, 9), ext(16, 14, 13), ext(20, 18, 17)]


def shape_of(fs):
    t, i, m, r, p = fs
    n = sum(fs[1:])
    if n == 0:
        return "thumb" if t else "fist"
    if i and not m and not r and not p:
        return "point"
    if i and m and not r and not p:
        return "count"     # two-three fingers -> counting sprite
    if i and m and r and not p:
        return "count"
    return "open"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--debug")
    ap.add_argument("--fps", type=float, default=30)
    a = ap.parse_args()
    cap = cv2.VideoCapture(a.video)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 24
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "pose_landmarker_heavy.task")),
        running_mode=vision.RunningMode.VIDEO, min_pose_detection_confidence=0.3, min_tracking_confidence=0.3))
    hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "hand_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO, num_hands=2, min_hand_detection_confidence=0.3, min_tracking_confidence=0.3))
    raw = {k: [] for k in ("uL", "fL", "hL", "lenL", "uR", "fR", "hR", "lenR", "shapeL", "shapeR", "torso_tilt", "head_tilt")}
    vw = None
    if a.debug:
        vw = cv2.VideoWriter(a.debug, cv2.VideoWriter_fourcc(*"mp4v"), src_fps, (W, H))
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        ts = int(n * 1000 / src_fps)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        pr = pose.detect_for_video(img, ts)
        hr = hands.detect_for_video(img, ts)
        P = None
        if pr.pose_landmarks:
            P = [(l.x * W, l.y * H, l.z * W, l.visibility) for l in pr.pose_landmarks[0]]
        sides = {}
        if P:
            # screen-left arm = the person's RIGHT arm for a front-facing presenter
            for scr, (sh, el, wr, ix, pk) in (("L", (R_SH, R_EL, R_WR, R_IDX, R_PNK)), ("R", (L_SH, L_EL, L_WR, L_IDX, L_PNK))):
                if P[sh][0] > P[{R_SH: L_SH, L_SH: R_SH}[sh]][0] and scr == "L":
                    pass
                vis = min(P[sh][3], P[el][3], P[wr][3])
                if vis < 0.35:
                    sides[scr] = None; continue
                hand_mid = ((P[ix][0] + P[pk][0]) / 2, (P[ix][1] + P[pk][1]) / 2)
                sides[scr] = {"u": ang(P[sh], P[el]), "f": ang(P[el], P[wr]), "h": ang(P[wr], hand_mid),
                              "len": math.hypot(P[wr][0] - P[el][0], P[wr][1] - P[el][1]) /
                                     max(1e-6, math.hypot(P[el][0] - P[sh][0], P[el][1] - P[sh][1])),
                              "wrist": (P[wr][0], P[wr][1])}
            raw["torso_tilt"].append(ang(P[R_SH], P[L_SH]))
            raw["head_tilt"].append(ang((P[8][0], P[8][1]), (P[7][0], P[7][1])))    # ear to ear
        else:
            raw["torso_tilt"].append(None); raw["head_tilt"].append(None)
        # hand shapes: assign each detected hand to the nearer pose wrist
        shape = {"L": None, "R": None}
        if hr.hand_landmarks:
            for hl in hr.hand_landmarks:
                pts = [(p.x * W, p.y * H) for p in hl]
                best, bd = None, 1e9
                for scr in ("L", "R"):
                    if sides.get(scr):
                        d = math.hypot(pts[0][0] - sides[scr]["wrist"][0], pts[0][1] - sides[scr]["wrist"][1])
                        if d < bd: best, bd = scr, d
                if best and bd < 0.12 * W:
                    shape[best] = shape_of(finger_states(pts))
        for scr in ("L", "R"):
            s = sides.get(scr)
            raw["u" + scr].append(s["u"] if s else None); raw["f" + scr].append(s["f"] if s else None)
            raw["h" + scr].append(s["h"] if s else None); raw["len" + scr].append(s["len"] if s else None)
            raw["shape" + scr].append(shape[scr])
        if vw is not None and P:
            for i in (11, 12, 13, 14, 15, 16):
                cv2.circle(frame, (int(P[i][0]), int(P[i][1])), 6, (0, 0, 255), -1)
            for a_, b_ in ((11, 13), (13, 15), (12, 14), (14, 16), (11, 12)):
                cv2.line(frame, (int(P[a_][0]), int(P[a_][1])), (int(P[b_][0]), int(P[b_][1])), (0, 255, 255), 3)
            cv2.putText(frame, f"L:{shape['L']} R:{shape['R']}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 2)
            vw.write(frame)
        n += 1
    if vw is not None:
        vw.release()
    # resample to the target fps, unwrap angles, smooth
    t_src = np.arange(n) / src_fps
    m = int(round(t_src[-1] * a.fps)) + 1 if n else 0
    t_dst = np.arange(m) / a.fps
    res = {"fps": a.fps, "frames": m, "src_fps": src_fps, "size": [W, H]}
    for k in ("uL", "fL", "hL", "uR", "fR", "hR", "torso_tilt", "head_tilt"):
        sm = fill_smooth(unwrap(raw[k]))
        if sm[0] is None:
            res[k] = None; continue
        res[k] = [round(float(v), 2) for v in np.interp(t_dst, t_src, sm)]
    for k in ("lenL", "lenR"):
        sm = fill_smooth(raw[k], 0.25)
        res[k] = None if sm[0] is None else [round(float(v), 3) for v in np.interp(t_dst, t_src, sm)]
    for k in ("shapeL", "shapeR"):
        src = raw[k]
        # majority vote over a 7-frame window, hold the last seen shape through gaps
        out, last = [], None
        for i in range(n):
            win = [s for s in src[max(0, i - 3):i + 4] if s]
            if win:
                last = max(set(win), key=win.count)
            out.append(last)
        res[k] = [out[min(n - 1, int(round(t * src_fps)))] for t in t_dst]
    seen = {k: sum(v is not None for v in raw[k]) for k in ("uL", "uR")}
    pathlib.Path(a.out).write_text(json.dumps(res))
    print(json.dumps({"ok": True, "frames_src": n, "frames_out": m, "tracked": seen,
                      "shapes": {k: {s: res[k].count(s) for s in set(res[k])} for k in ("shapeL", "shapeR")}}))


if __name__ == "__main__":
    sys.exit(main())
