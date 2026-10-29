#!/usr/bin/env python3
"""HYBRID avatar: the BODY (arms, hands, posture) from an AI video of the character
(Gemini Omni), the HEAD from the one-drawing face rig (face_rig.py) - sharp, lip-synced
to our voice, blinking - tracked onto the video's head every frame.

  python -I hybrid_head.py --clip omni.mp4 --face face_dir --landmarks face_landmarks.json \
      --mouth mouth.json --voice vo.wav --out hybrid.mp4 [--crop 405x720+437+0] [--size 1080x1920]
      [--head-scale 1.06] [--start 0] [--debug]

Tracking: MediaPipe FaceLandmarker on the video -> eye centres per frame (smoothed), giving
position, scale (eye distance) and roll. The A face is placed so its eye centres land on
the video's. Mouth state from Rhubarb cues, blinks seeded. No lip-sync model needed.
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from face_heal import heal, trim_below_jaw, ears_from_source, load_ear_source  # noqa: E402
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

MODELS = _paths.mediapipe_models()
L_EYE = [33, 133, 159, 145]     # MediaPipe face mesh: one eye's corners + lids
R_EYE = [362, 263, 386, 374]


def smooth(a, alpha=0.4):
    a = np.array(a, float)
    f = a.copy()
    for i in range(1, len(f)):
        f[i] = alpha * a[i] + (1 - alpha) * f[i - 1]
    b = f.copy()
    for i in range(len(b) - 2, -1, -1):
        b[i] = alpha * f[i] + (1 - alpha) * b[i + 1]
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("clip", "face", "landmarks", "mouth", "voice", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--crop", default="405x720+437+0")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--head-scale", type=float, default=1.06)
    ap.add_argument("--head-dy", type=float, default=0.0, help="extra vertical offset, in eye-distances")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    cw, ch, cx, cy = [int(v) for v in a.crop.replace("x", " ").replace("+", " ").split()]
    OW, OH = [int(v) for v in a.size.split("x")]
    fd = pathlib.Path(a.face)
    F = json.loads((fd / "face.json").read_text())
    sp = F["split"]
    LM = json.loads(pathlib.Path(a.landmarks).read_text())
    eA = [np.array([x + w / 2, y + h / 2]) for x, y, w, h in LM["eyes"]]       # A face eye centres
    dA = float(np.linalg.norm(eA[1] - eA[0]))
    load = lambda n: heal(cv2.imread(str(fd / n), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0)
    ears = load_ear_source(a.landmarks, F["canvas"][::-1])
    fix = (lambda im: ears_from_source(im, ears, LM["jaw"])) if ears is not None else (lambda im: im)
    upper = {e: fix(load(f"upper_{e}.png")) for e in F["eyes"]}
    lower = {m: trim_below_jaw(fix(load(f"lower_{m}.png")), int(LM["lip_y"]) + 25) for m in F["shapes"]}

    # 1) read and crop the clip, track the face
    cap = cv2.VideoCapture(a.clip)
    sfps = cap.get(cv2.CAP_PROP_FPS) or 24
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr[cy:cy + ch, cx:cx + cw])
    det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "face_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO, num_faces=1,
        min_face_detection_confidence=0.3, min_tracking_confidence=0.3))
    eL, eR = [], []
    for i, fr in enumerate(frames):
        r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)),
                                 int(i * 1000 / sfps))
        if r.face_landmarks:
            p = r.face_landmarks[0]
            # screen-left eye of the image = the person's right eye
            a_ = np.mean([[p[k].x * cw, p[k].y * ch] for k in L_EYE], 0)
            b_ = np.mean([[p[k].x * cw, p[k].y * ch] for k in R_EYE], 0)
            l_, r_ = (a_, b_) if a_[0] < b_[0] else (b_, a_)
            eL.append(l_); eR.append(r_)
        else:
            eL.append(None); eR.append(None)
    good = [i for i, v in enumerate(eL) if v is not None]
    if not good:
        raise SystemExit("no face tracked")
    idx = np.arange(len(frames))
    tr = {}
    for nm, arr in (("lx", [v[0] if v is not None else np.nan for v in eL]), ("ly", [v[1] if v is not None else np.nan for v in eL]),
                    ("rx", [v[0] if v is not None else np.nan for v in eR]), ("ry", [v[1] if v is not None else np.nan for v in eR])):
        arr = np.array(arr, float); g = ~np.isnan(arr)
        tr[nm] = smooth(np.interp(idx, idx[g], arr[g]), 0.45)
    sx, sy = OW / cw, OH / ch

    # 2) cues
    cues = json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"]
    vo_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice],
                                  capture_output=True, text=True).stdout.strip())
    n_out = int((min(len(frames) / sfps - a.start, vo_len + 0.6)) * a.fps)
    blinks = []
    rng = np.random.default_rng(7); t = 1.2
    while t < n_out / a.fps:
        blinks.append(t); t += 2.4 + rng.random() * 2.2

    def mouth_at(t):
        m = "X"
        for c in cues:
            if c["start"] <= t:
                m = c["value"]
        return m if t <= vo_len + 0.05 else "X"

    def eyes_at(t):
        for b in blinks:
            d = (t - b) * a.fps
            if 0 <= d < 1: return "half"
            if 1 <= d < 3: return "closed"
            if 3 <= d < 4: return "half"
        return "open"

    # 3) compose
    tmp = str(pathlib.Path(a.out).with_suffix(".silent.mp4"))
    proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}",
                             "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-crf", "15", "-preset", "medium",
                             "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for k in range(n_out):
        t = k / a.fps
        si = min(len(frames) - 1, int((t + a.start) * sfps))
        bg = cv2.resize(frames[si], (OW, OH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32) / 255.0
        L = np.array([tr["lx"][si] * sx, tr["ly"][si] * sy]); R = np.array([tr["rx"][si] * sx, tr["ry"][si] * sy])
        dV = float(np.linalg.norm(R - L))
        s = dV / dA * a.head_scale
        ang = math.atan2(R[1] - L[1], R[0] - L[0])
        midA = (eA[0] + eA[1]) / 2
        midV = (L + R) / 2 + np.array([-math.sin(ang), math.cos(ang)]) * a.head_dy * dV
        c, si_ = math.cos(ang) * s, math.sin(ang) * s
        M = np.array([[c, -si_, 0], [si_, c, 0]], np.float32)
        M[:, 2] = midV - M[:, :2] @ midA
        head = np.vstack([upper[eyes_at(t)][:sp], lower[mouth_at(t)][sp:]])
        w = cv2.warpAffine(head, M, (OW, OH), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)).clip(0, 1)
        al = w[..., 3:4]
        out = w[..., :3] * al + bg * (1 - al)
        if a.debug:
            for p in (L, R):
                cv2.circle(out, (int(p[0]), int(p[1])), 6, (1, 0, 1), -1)
        proc.stdin.write((out * 255).astype(np.uint8).tobytes())
    proc.stdin.close(); proc.wait()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-i", a.voice, "-af", "loudnorm=I=-14:TP=-1.5",
                    "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-shortest", a.out], check=True)
    pathlib.Path(tmp).unlink(missing_ok=True)
    print(json.dumps({"ok": True, "frames": n_out, "tracked": len(good), "of": len(frames), "out": a.out}))


if __name__ == "__main__":
    sys.exit(main())
