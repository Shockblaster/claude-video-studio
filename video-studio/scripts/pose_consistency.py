#!/usr/bin/env python3
"""PRE-RIG consistency gate for a ChatGPT pose library (no face rig needed yet).

  python -I pose_consistency.py --poses pulled/ --ref raw/d01_rest_clasp.png --out check/ [names...]

Per pose, against the framing reference (MediaPipe face + pose + hands on the cartoon):
  roll    head tilt RELATIVE to the reference, deg          |droll| <= 2.5 (MediaPipe reads a
          constant few-degree tilt on cartoon eyes; what matters is matching the head rig)
  yaw     nose offset from the eye midpoint / eye distance |yaw| <= 0.07
  scale   body size once the eyes are aligned, vs the LIBRARY MEDIAN, within 5% on EITHER
          (a) eye distance / shoulder width (raised arms or elbows-out shift the shoulder landmarks) or
          (b) leg width at 90-97% of the frame height (a wider stance changes it). Failing both = real.
  clear   no hand landmark inside the face box (+25% margin)
  hair    IoU of the dark-hair mask around the face vs the reference, after aligning on the eyes
          (long hair framing the face must keep its shape so a face-only rig sits right) >= 0.80
  top     mean colour of the red top under the chin vs the reference (BGR distance) <= 22
Writes check/report.json, check/faces.png (eye-aligned face crops next to the reference, for the
eyeball check) and check/hands.png (every detected hand at full resolution).
Numbers are necessary, not sufficient: the sheets still get looked at.
"""
import argparse
import json
import math
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pose_fit as pf  # noqa: E402

FACE_W = 3.2     # face crop half-width, in eye distances
HAIR_BOX = (-3.2, 3.2, -3.4, 2.6)   # x0, x1, y0, y1 around the eye midpoint, in eye distances


def hair_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    # dark-brown hair: warm hue, some saturation, darkish. The blazer is near-black and unsaturated.
    return ((v < 120) & (s > 55) & ((h < 25) | (h > 165))).astype(np.uint8)


def align(img, m, mref, size):
    """similarity that maps this pose's eyes onto the reference eyes"""
    src = np.float32([m["eL"], m["eR"]]); dst = np.float32([mref["eL"], mref["eR"]])
    M, _ = cv2.estimateAffinePartial2D(src, dst)
    return cv2.warpAffine(img, M, size, flags=cv2.INTER_LINEAR, borderValue=(0, 255, 0))


def region(m, H, W, box):
    c = (m["eL"] + m["eR"]) / 2; d = m["d"]
    x0, x1, y0, y1 = box
    return (int(max(0, c[0] + x0 * d)), int(min(W, c[0] + x1 * d)), int(max(0, c[1] + y0 * d)), int(min(H, c[1] + y1 * d)))


def top_colour(img, m):
    c = (m["eL"] + m["eR"]) / 2; d = m["d"]; H, W = img.shape[:2]
    box = img[int(min(H, c[1] + 3.0 * d)):int(min(H, c[1] + 5.0 * d)), int(max(0, c[0] - 0.8 * d)):int(min(W, c[0] + 0.8 * d))]
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV).reshape(-1, 3); px = box.reshape(-1, 3)
    red = ((hsv[:, 0] < 10) | (hsv[:, 0] > 170)) & (hsv[:, 1] > 120) & (hsv[:, 2] > 80)
    return px[red].mean(0) if red.sum() > 50 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--poses", required=True); ap.add_argument("--ref", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    det = pf.detectors()
    ref = cv2.imread(a.ref); H, W = ref.shape[:2]
    R = pf.measure(ref, det)
    rr = R["d"] / R["shw"]
    x0, x1, y0, y1 = region(R, H, W, HAIR_BOX)
    ref_hair = hair_mask(ref)[y0:y1, x0:x1]
    ref_top = top_colour(ref, R)
    files = [pathlib.Path(a.poses) / (n + ".png") for n in a.names] if a.names else sorted(pathlib.Path(a.poses).glob("d*.png"))
    rep, faces, hands = {}, [], []
    fx0, fx1, fy0, fy1 = region(R, H, W, (-FACE_W, FACE_W, -3.0, 3.0))
    faces.append(("REF", ref[fy0:fy1, fx0:fx1]))
    for f in files:
        img = cv2.imread(str(f)); m = pf.measure(img, det)
        if m is None or m["shw"] is None:
            rep[f.stem] = {"pass": False, "why": ["face or shoulders not found"]}; continue
        al = align(img, m, R, (W, H))
        hair = hair_mask(al)[y0:y1, x0:x1]
        iou = float((hair & ref_hair).sum() / max(1, (hair | ref_hair).sum()))
        bx = cv2.boundingRect(m["oval"]); mx, my = bx[2] * 0.25, bx[3] * 0.25
        inside = [p for p in m["hands"] if bx[0] - mx <= p[0] <= bx[0] + bx[2] + mx and bx[1] - my <= p[1] <= bx[1] + bx[3] + my]
        tc = top_colour(img, m)
        hsv_al = cv2.cvtColor(al, cv2.COLOR_BGR2HSV)
        fg = ~((hsv_al[..., 0] > 35) & (hsv_al[..., 0] < 85) & (hsv_al[..., 1] > 120))
        legs = [int(np.ptp(np.where(fg[y])[0])) for y in range(int(H * 0.90), int(H * 0.97), 4) if fg[y].any()]
        r = {"roll": round(m["roll"] - R["roll"], 2), "ratio": (m["d"] / m["shw"]) / rr, "legs": float(np.median(legs)) if legs else None, "yaw": round(m["yaw"], 3),
             "hand_pts_near_face": len(inside), "hair_iou": round(iou, 3),
             "top_dist": None if tc is None or ref_top is None else round(float(np.linalg.norm(tc - ref_top)), 1)}
        rep[f.stem] = r
        faces.append((f.stem, al[fy0:fy1, fx0:fx1]))
        # hands at full resolution, one crop per detected hand (21 landmarks each)
        pts = np.array(m["hands"]).reshape(-1, 21, 2) if m["hands"] else []
        for k, hp in enumerate(pts):
            hx0, hy0 = hp.min(0); hx1, hy1 = hp.max(0); pad = 0.35 * max(hx1 - hx0, hy1 - hy0)
            crop = img[int(max(0, hy0 - pad)):int(min(H, hy1 + pad)), int(max(0, hx0 - pad)):int(min(W, hx1 + pad))]
            if crop.size: hands.append((f"{f.stem}#{k}", crop))
    med = float(np.median([v["ratio"] for v in rep.values() if "ratio" in v] or [1]))
    medl = float(np.median([v["legs"] for v in rep.values() if v.get("legs")] or [1]))
    for k, r in rep.items():
        if "ratio" not in r: continue
        r["scale"] = round(r.pop("ratio") / med, 3)
        lg = r.pop("legs"); r["legs"] = round(lg / medl, 3) if lg else None
        why = []
        if abs(r["roll"]) > 2.5: why.append("roll")
        if abs(r["yaw"]) > 0.07: why.append("yaw")
        if abs(r["scale"] - 1) > 0.05 and (r["legs"] is None or abs(r["legs"] - 1) > 0.05): why.append("scale")
        if r["hand_pts_near_face"]: why.append("hand near face")
        if r["hair_iou"] < 0.80: why.append("hair shape")
        if r["top_dist"] is None or r["top_dist"] > 22: why.append("top colour")
        r["pass"] = not why; r["why"] = why
    (out / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")

    def sheet(items, cell, name):
        if not items: return
        cols = 6; rows = math.ceil(len(items) / cols)
        S = np.full((rows * (cell + 24), cols * cell, 3), 255, np.uint8)
        for i, (lab, im) in enumerate(items):
            s = cell / max(im.shape[:2]); im2 = cv2.resize(im, (max(1, int(im.shape[1] * s)), max(1, int(im.shape[0] * s))))
            y, x = (i // cols) * (cell + 24), (i % cols) * cell
            S[y + 24:y + 24 + im2.shape[0], x:x + im2.shape[1]] = im2
            ok = rep.get(lab.split("#")[0], {}).get("pass", True)
            cv2.putText(S, lab[:30], (x + 3, y + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 120, 0) if ok else (0, 0, 220), 1)
        cv2.imwrite(str(out / name), S)
    sheet(faces, 260, "faces.png"); sheet(hands, 220, "hands.png")
    for k, v in rep.items():
        print(f"{k:28s} {'PASS' if v['pass'] else 'FAIL ' + ','.join(v['why'])}  " + " ".join(f"{x}={v[x]}" for x in ("roll", "yaw", "scale", "legs", "hair_iou", "top_dist") if x in v))


if __name__ == "__main__":
    main()
