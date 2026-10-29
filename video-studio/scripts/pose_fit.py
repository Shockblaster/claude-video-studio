#!/usr/bin/env python3
"""FIT GATE for the poses route: generated body poses (one image each, green screen) that our
one-drawing face rig (face_rig.py) is placed on. A pose enters the library only if our head
fits it 100% - otherwise regenerate it, never patch it.

  python -I pose_fit.py --poses raw/ --face face --landmarks face_landmarks.json --ref raw/p01_rest_clasp.png \
      --out fit/ [--head-scale 1.06]

Per pose it measures (MediaPipe face + pose + hands on the cartoon):
  roll      head tilt, deg                      |roll| <= 2.5
  yaw       nose offset from the eye midpoint, in eye distances   |yaw| <= 0.07
  scale     (eye distance / shoulder width) vs the reference pose  within 5%
  clear     no hand landmark inside our placed head (+8% margin)
  colour    suit / shirt mean colour vs the reference (BGR distance)  <= 18
and writes fit/<pose>.png (our head on the keyed body, on a neutral background), fit/<pose>_neck.png
(2x close-up of the chin-collar junction for the eyeball check) and fit/report.json.
The numeric gate is necessary, not sufficient: every neck close-up still gets looked at.
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
import puppet_build as pb  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

MODELS = _paths.mediapipe_models()
L_EYE = [33, 133, 159, 145]
R_EYE = [362, 263, 386, 374]
NOSE = 1
OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
        148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]


def detectors():
    f = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "face_landmarker.task")), num_faces=1,
        min_face_detection_confidence=0.2))
    p = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "pose_landmarker_heavy.task")),
        min_pose_detection_confidence=0.2))
    h = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "hand_landmarker.task")), num_hands=2,
        min_hand_detection_confidence=0.2))
    return f, p, h


def measure(img, det):
    fd, pd, hd = det
    H, W = img.shape[:2]
    mi = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    fr = fd.detect(mi)
    if not fr.face_landmarks:
        return None
    q = fr.face_landmarks[0]
    a = np.mean([[q[k].x * W, q[k].y * H] for k in L_EYE], 0)
    b = np.mean([[q[k].x * W, q[k].y * H] for k in R_EYE], 0)
    eL, eR = (a, b) if a[0] < b[0] else (b, a)
    d = float(np.linalg.norm(eR - eL))
    nose = np.array([q[NOSE].x * W, q[NOSE].y * H])
    roll = math.degrees(math.atan2(eR[1] - eL[1], eR[0] - eL[0]))
    yaw = float((nose[0] - (eL[0] + eR[0]) / 2) / d)
    pr = pd.detect(mi)
    shw = None
    if pr.pose_landmarks:
        s = pr.pose_landmarks[0]
        shw = float(math.hypot((s[11].x - s[12].x) * W, (s[11].y - s[12].y) * H))
    hands = []
    hr = hd.detect(mi)
    for hl in hr.hand_landmarks or []:
        hands += [(p.x * W, p.y * H) for p in hl]
    oval = np.array([[q[k].x * W, q[k].y * H] for k in OVAL], np.float32)
    return {"eL": eL, "eR": eR, "d": d, "roll": roll, "yaw": yaw, "shw": shw, "hands": hands, "oval": oval}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("poses", "face", "landmarks", "ref", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--head-scale", type=float, default=1.06)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fd = pathlib.Path(a.face)
    F = json.loads((fd / "face.json").read_text()); sp = F["split"]
    LM = json.loads(pathlib.Path(a.landmarks).read_text())
    eA = [np.array([x + w / 2, y + h / 2]) for x, y, w, h in LM["eyes"]]
    dA = float(np.linalg.norm(eA[1] - eA[0]))
    ld = lambda n: cv2.imread(str(fd / n), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
    head = np.vstack([ld("upper_open.png")[:sp], ld("lower_X.png")[sp:]])
    det = detectors()

    def keyed(p):
        im = cv2.imread(str(p))
        rgba = pb.key_green(im, max_hole=600)
        return im, rgba

    ref_im, ref_rgba = keyed(a.ref)
    R = measure(ref_im, det)
    if R is None or R["shw"] is None:
        raise SystemExit("reference pose: face or shoulders not found")
    ref_ratio = R["d"] / R["shw"]

    def colours(rgba, m):
        """mean BGR of the suit and the shirt over the chest box under the chin, using only pixels
        of that kind (a fixed patch landed on a raised hand and failed good poses)"""
        c = (m["eL"] + m["eR"]) / 2; d = m["d"]
        H_, W_ = rgba.shape[:2]
        x0, x1 = int(max(0, c[0] - 3 * d)), int(min(W_, c[0] + 3 * d))
        y0, y1 = int(min(H_, c[1] + 2.8 * d)), int(min(H_, c[1] + 6 * d))
        box = rgba[y0:y1, x0:x1]
        hsv = cv2.cvtColor((np.clip(box[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
        px = box[..., :3].reshape(-1, 3); al = box[..., 3].reshape(-1)
        suit = (al > 0.9) & (hsv[:, 1] < 60) & (hsv[:, 2] > 25) & (hsv[:, 2] < 115)
        shirt = (al > 0.9) & (hsv[:, 0] > 95) & (hsv[:, 0] < 115) & (hsv[:, 2] > 180) & (hsv[:, 1] < 110)
        return {"suit": px[suit].mean(0) if suit.any() else np.zeros(3),
                "shirt": px[shirt].mean(0) if shirt.any() else np.zeros(3)}
    ref_col = colours(ref_rgba, R)

    report = {}
    for p in sorted(pathlib.Path(a.poses).glob("*.png")):
        im, rgba = keyed(p)
        m = measure(im, det)
        name = p.stem
        if m is None:
            report[name] = {"pass": False, "why": ["no face found"]}
            continue
        why = []
        if abs(m["roll"]) > 2.5: why.append(f"roll {m['roll']:.1f}")
        if abs(m["yaw"]) > 0.07: why.append(f"yaw {m['yaw']:.2f}")
        ratio = m["d"] / m["shw"] if m["shw"] else None
        if ratio is None: why.append("no shoulders")
        elif abs(ratio / ref_ratio - 1) > 0.05: why.append(f"scale {ratio / ref_ratio:.3f}")
        # place our head by the eyes (same maths as hybrid_head.py)
        s = m["d"] / dA * a.head_scale
        ang = math.atan2(m["eR"][1] - m["eL"][1], m["eR"][0] - m["eL"][0])
        c_, s_ = math.cos(ang) * s, math.sin(ang) * s
        M = np.array([[c_, -s_, 0], [s_, c_, 0]], np.float32)
        M[:, 2] = (m["eL"] + m["eR"]) / 2 - M[:, :2] @ ((eA[0] + eA[1]) / 2)
        H, W = im.shape[:2]
        hw = cv2.warpAffine(head, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)).clip(0, 1)
        hm = hw[..., 3] > 0.5
        ys, xs = np.nonzero(hm)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        mx, my = 0.08 * (x1 - x0), 0.08 * (y1 - y0)
        inside = [h for h in m["hands"] if x0 - mx <= h[0] <= x1 + mx and y0 - my <= h[1] <= y1 + my]
        if inside: why.append(f"hand in head zone ({len(inside)} pts)")
        col = colours(rgba, m)
        dc = {k: float(np.linalg.norm(col[k] - ref_col[k]) * 255) for k in col}
        if max(dc.values()) > 18: why.append("colour " + ", ".join(f"{k} {v:.0f}" for k, v in dc.items()))
        # composite on a neutral background
        bg = np.full((H, W, 3), (0.86, 0.80, 0.74), np.float32)
        body = rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4])
        comp = hw[..., :3] * hw[..., 3:4] + body * (1 - hw[..., 3:4])
        comp8 = (comp * 255).astype(np.uint8)
        cv2.imwrite(str(out / f"{name}.png"), comp8)
        cy = int(y1); cx = int((x0 + x1) / 2); r = int(0.9 * m["d"])
        neck = comp8[max(0, cy - r):cy + r, max(0, cx - 2 * r):cx + 2 * r]
        cv2.imwrite(str(out / f"{name}_neck.png"), cv2.resize(neck, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
        report[name] = {"pass": not why, "why": why, "roll": round(m["roll"], 2), "yaw": round(m["yaw"], 3),
                        "scale": round(ratio / ref_ratio, 3) if ratio else None, "colour": {k: round(v, 1) for k, v in dc.items()}}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: ("PASS" if v["pass"] else "FAIL " + "; ".join(v["why"])) for k, v in report.items()}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
