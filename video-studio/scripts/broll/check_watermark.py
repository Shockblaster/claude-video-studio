"""Prove a Gemini/Veo sparkle watermark is really gone, not just dimmed or smudged.

    python check_watermark.py RAW.mp4 CLEAN.mp4 [RAW2 CLEAN2 ...] [--sheet out.png]

Per pair, medians over ~24 frames:
  bump     luma inside the sparkle's shape minus a ring around it. Raw clips: +49..+75.
  shape    correlation of the high-passed patch with the sparkle's own outline.
           Raw: 0.37..0.84. A clean clip must be |shape| < 0.10 (catches faint ghosts/outlines).
  texture  high-frequency energy inside the mark / in the ring; 1.0 = matches its surroundings.
           Judged on this ABSOLUTE scale, not against the raw clip: the sparkle's own hard edges
           inflate the raw value (1.25 on one clip), which made a relative test flag good output.
           Smudges measured 0.10-0.38 -> FAIL below 0.40; 0.40-0.55 BORDERLINE (read the sheet);
           accepted clips measured 0.44-0.86.
Then it writes a crop sheet (raw | clean at 3 moments incl. near the loop point).
LOOK AT THE SHEET. The first scrub passed bump and shape on every clip while leaving a
visible smooth smudge on dark textured plates; only the texture ratio and the eye caught it.
"""
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from process_video import FFMPEG  # noqa: E402

# The alpha map lives in the skill's assets/. A copy of this script inside a deck's src/
# (or src/browser/) cannot see it by relative path, so try every known location.
_CANDIDATES = [os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets", "veo-watermark-alpha.png"),  # <skill>/assets
               os.path.join(os.path.dirname(HERE), "assets", "veo-watermark-alpha.png"),
               os.path.join(HERE, "veo-watermark-alpha.png"),
               os.path.join(os.path.expanduser("~"), ".claude", "skills", "video-studio", "assets",
                            "veo-watermark-alpha.png")]
ALPHA = next((c for c in _CANDIDATES if os.path.exists(c)), _CANDIDATES[-1])
a = cv2.imread(ALPHA, 0).astype(np.float32) / 255
CORE = a > 0.15
RING = (cv2.dilate(CORE.astype(np.uint8), np.ones((25, 25), np.uint8)) > 0) & \
       ~(cv2.dilate(CORE.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)
ys, xs = np.where(a > 0.01)
Y0, Y1, X0, X1 = ys.min() - 12, ys.max() + 12, xs.min() - 12, xs.max() + 12
SHAPE = a[Y0:Y1, X0:X1].ravel()
SHAPE = (SHAPE - SHAPE.mean()) / SHAPE.std()


def metrics(path):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-vf", "fps=2.4", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8)
    f = f[: (len(f) // (1280 * 720)) * 1280 * 720].reshape(-1, 720, 1280).astype(np.float32)
    bump, shape, tex = [], [], []
    for fr in f:
        bump.append(fr[CORE].mean() - fr[RING].mean())
        p = cv2.GaussianBlur(fr[Y0:Y1, X0:X1], (0, 0), 1.0)
        hp = (p - cv2.GaussianBlur(p, (0, 0), 8)).ravel()
        shape.append(np.dot(SHAPE, (hp - hp.mean()) / (hp.std() + 1e-6)) / len(SHAPE))
        h2 = fr - cv2.GaussianBlur(fr, (0, 0), 2.0)
        tex.append(h2[CORE].std() / (h2[RING].std() + 1e-3))
    return float(np.median(bump)), float(np.median(shape)), float(np.median(tex))


def crop(path, t):
    png = subprocess.run([FFMPEG, "-v", "error", "-ss", t, "-i", path, "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True).stdout
    im = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)[530:670, 1090:1250]
    return np.pad(cv2.resize(im, (240, 210), interpolation=cv2.INTER_CUBIC), ((3, 3), (3, 3), (0, 0)), constant_values=255)


def main(argv):
    sheet_path = None
    if "--sheet" in argv:
        i = argv.index("--sheet")
        sheet_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    pairs = list(zip(argv[0::2], argv[1::2]))
    bad, rows = 0, []
    print(f"{'clip':28} {'raw bump/shape/tex':>22} | {'clean bump/shape/tex':>22}")
    for raw, clean in pairs:
        rb, rs, rt = metrics(raw)
        cb, cs, ct = metrics(clean)
        ghost = abs(cs) >= 0.10 or abs(cb) >= 8
        smudge = ct < 0.40
        borderline = not smudge and ct < 0.55
        ok = not ghost and not smudge
        bad += not ok
        verdict = "FAIL  GHOST" if ghost else "FAIL  SMUDGE" if smudge else "clean (BORDERLINE texture: read the sheet)" if borderline else "clean"
        print(f"{os.path.basename(clean):28} {rb:7.1f} {rs:6.2f} {rt:6.2f}  | {cb:7.1f} {cs:6.2f} {ct:6.2f}  {verdict}")
        rows.append(np.hstack([crop(raw, "5")] + [crop(clean, t) for t in ("0.3", "4.5", "8.8")]))
    if sheet_path and rows:
        cv2.imwrite(sheet_path, np.vstack(rows))
        print("crop sheet:", sheet_path, "(columns: raw | clean 0.3 s | 4.5 s | 8.8 s)")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
