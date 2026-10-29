#!/usr/bin/env python3
"""FACE-ONLY patch for avatars with long hair (poses route). The pose keeps its own hair, outfit,
hands and jewellery; only the skin region of the face (forehead to upper neck, with eyes, brows,
nose and mouth) comes from the one-drawing face rig, so mouths and blinks never touch the hair.
First used for a long-haired presenter. A short-haired presenter can keep the full-head route in pose_reel.

  python -I face_patch.py mask --head head_hi.png --out rig/        -> face_mask.png, head_lm.npy,
                                                                       face_mask_check.png (READ it)
Library use (avatar_track.py, plan "face_mode": "patch"):
  prep = prepare_patch_pose(pose_bgr, det, head_lm, mask, states_X)  -> dict for the renderer

Mask = shrunk face oval (always patched, incl. dark brows/eyes) + brow hulls, plus skin-only rim,
forehead up to the hairline and upper neck; opened (drops the hair-parting skin and ear nubs) and
eroded a little inside the hairline (skin-to-skin seams vanish; hair-on-hair seams show).
Fit = similarity from ~32 stable MediaPipe landmarks (LMEDS). Colour = per-channel gain from the
pose's OWN face skin under the patch core (an outside ring caught cheek-edge shading).
"""
import argparse
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mediapipe as mp  # noqa: E402
import pose_fit as pf  # noqa: E402
import puppet_build as pb  # noqa: E402

OVAL = pf.OVAL
STABLE = [33, 133, 362, 263, 1, 4, 5, 195, 168, 6, 61, 291, 13, 14, 152, 10, 234, 454, 93, 323,
          132, 361, 58, 288, 172, 397, 70, 300, 105, 334, 55, 285]
BROWS = ([70, 63, 105, 66, 107, 55, 65, 52, 53, 46], [300, 293, 334, 296, 336, 285, 295, 282, 283, 276])


def face_landmarks(img, det):
    H, W = img.shape[:2]
    r = det[0].detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks:
        return None
    return np.array([[p.x * W, p.y * H] for p in r.face_landmarks[0]], np.float32)


def build_mask(head, det):
    H, W = head.shape[:2]
    P = face_landmarks(head, det)
    d = float(np.linalg.norm(P[[362, 263]].mean(0) - P[[33, 133]].mean(0)))
    hsv = cv2.cvtColor(head, cv2.COLOR_BGR2HSV)
    cheeks = np.vstack([hsv[int(P[i][1]) - 6:int(P[i][1]) + 6, int(P[i][0]) - 6:int(P[i][0]) + 6].reshape(-1, 3)
                        for i in (50, 280, 101, 330)])
    m_h, m_s, m_v = np.median(cheeks, 0)
    h, s, v = [hsv[..., k].astype(int) for k in range(3)]
    skin = (np.abs(h - m_h) <= 12) & (np.abs(s - m_s) <= 70) & (v > m_v * 0.45)
    c = P[OVAL].mean(0)
    region = np.zeros((H, W), np.uint8)
    cv2.fillPoly(region, [(c + (P[OVAL] - c) * 1.12).astype(np.int32)], 1)
    chin, jl, jr = P[152], P[172], P[397]
    neck = np.array([jl, jr, [jr[0] - 0.15 * d, chin[1] + 0.55 * d], [jl[0] + 0.15 * d, chin[1] + 0.55 * d]], np.int32)
    cv2.fillPoly(region, [neck], 1)
    fx0, fx1 = int(min(P[103][0], P[54][0])), int(max(P[332][0], P[284][0]))
    cv2.rectangle(region, (fx0, int(P[10][1] - 0.9 * d)), (fx1, int(P[105][1])), 1, -1)
    core = np.zeros((H, W), np.uint8)
    cv2.fillPoly(core, [(c + (P[OVAL] - c) * 0.86).astype(np.int32)], 1)
    for br in BROWS:
        cv2.fillPoly(core, [cv2.convexHull(P[br].astype(np.int32))], 1)
    core = cv2.dilate(core, np.ones((7, 7), np.uint8))
    m = ((core > 0) | (skin & (region > 0))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    m = (lab == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    m = cv2.erode(m, np.ones((9, 9), np.uint8))
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), 3.0), P


def _skin(img8):
    hv = cv2.cvtColor(img8, cv2.COLOR_BGR2HSV)
    return (hv[..., 1] > 40) & (hv[..., 2] > 140) & (hv[..., 0] < 25)


def prepare_patch_pose(pose, det, head_lm, mask, state_x):
    """Key the pose, fit the rig head onto its face. Returns rgba (body, pose px), Mh (head canvas ->
    pose px), d / mid (pose eye distance / midpoint, as pose_fit.measure), gain (BGR), mask."""
    P = face_landmarks(pose, det)
    if P is None:
        raise SystemExit("face not found on pose")
    Mh, _ = cv2.estimateAffinePartial2D(head_lm[STABLE], P[STABLE], method=cv2.LMEDS)
    m = pf.measure(pose, det)
    H, W = pose.shape[:2]
    st = cv2.warpAffine(state_x, Mh, (W, H), flags=cv2.INTER_AREA)
    mk = cv2.warpAffine(mask, Mh, (W, H), flags=cv2.INTER_LINEAR)
    core = cv2.erode((mk > 0.95).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    both = core & _skin(pose) & _skin((np.clip(st[..., :3], 0, 1) * 255).astype(np.uint8)) & (st[..., 3] > 0.9)
    gain = np.ones(3, np.float32)
    if both.sum() > 200:
        gain = np.clip(np.median(pose.astype(np.float32)[both] / 255, 0) / np.maximum(np.median(st[..., :3][both], 0), 1e-3), 0.8, 1.2)
    rgba = pb.key_green(pose, max_hole=600)
    return {"rgba": rgba, "Mh": Mh.astype(np.float64), "d": m["d"], "mid": (m["eL"] + m["eR"]) / 2,
            "gain": gain.astype(np.float32), "over": np.zeros_like(rgba)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["mask"])
    ap.add_argument("--head", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    head = cv2.imread(a.head)
    soft, P = build_mask(head, pf.detectors())
    cv2.imwrite(str(out / "face_mask.png"), (soft * 255).astype(np.uint8))
    np.save(out / "head_lm.npy", P)
    vis = head.copy(); vis[soft < 0.5] = (vis[soft < 0.5] * 0.35).astype(np.uint8)
    cv2.imwrite(str(out / "face_mask_check.png"), cv2.resize(vis, None, fx=0.5, fy=0.5))
    print("mask ok, coverage", round(float(soft.mean()), 3))


if __name__ == "__main__":
    main()
