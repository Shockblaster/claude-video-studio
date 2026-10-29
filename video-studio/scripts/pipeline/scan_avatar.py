"""Automatic every-frame scan of the avatar preview (magenta background). Each segment is compared
with its own settled frame (10 frames after the change), so the pose's real arm-to-body gaps are
not flagged; only what CHANGES inside a segment is:
  1. new holes: enclosed magenta (> 40 px) that the settled frame does not have (shirt/collar pockets)
  2. stray blobs: non-magenta specks off the main body (> 25 px), outside the preview's corner label
  3. face jumps: mean face-crop change between consecutive frames above 9 (eyes/mouth alone stay below)
Run: python -I scan_avatar.py ../avatar/preview.mp4 ../avatar/plan.json"""
import json
import sys

import cv2
import numpy as np

video, plan = sys.argv[1], json.load(open(sys.argv[2]))
FPS = 30
starts = [int(round(s["start"] * FPS)) for s in plan["segments"]]
SETTLE = 10
AX, AY = plan["anchor"]; bx, by = plan["box"][:2]
fx, fy = AX - bx, AY - by


def holes(mag):
    m8 = mag.astype(np.uint8); H, W = m8.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats(m8, 4)
    out = np.zeros_like(m8)
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if a > 40 and x > 0 and y > 0 and x + w < W and y + h < H:
            out[lab == k] = 1
    return out


cap = cv2.VideoCapture(video)
frames_mag, faces = [], []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    b, g, r = [fr[..., c].astype(int) for c in range(3)]
    frames_mag.append(np.packbits((r > 190) & (b > 190) & (g < 90)))
    faces.append(cv2.cvtColor(fr[fy - 110:fy + 150, fx - 110:fx + 110], cv2.COLOR_BGR2GRAY))
    shape = fr.shape[:2]
N = len(faces)
unpack = lambda p: np.unpackbits(p)[:shape[0] * shape[1]].reshape(shape).astype(bool)
flags = []
seg_of = np.searchsorted(starts, np.arange(N), side="right") - 1
ref = {}
for i in range(N):
    s = seg_of[i]; u = i - starts[s]
    if u < SETTLE:
        continue
    mag = unpack(frames_mag[i])
    h = holes(mag)
    if s not in ref:
        ref[s] = cv2.dilate(h, np.ones((9, 9), np.uint8))
    new = h & (1 - ref[s])
    na = int(new.sum())
    if na > 40:
        ys, xs = np.nonzero(new)
        flags.append((i, "new_hole", (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()), na)))
    body = (~mag).astype(np.uint8)
    body[-40:, :400] = 0                                  # the preview's frame label
    n, lab, st, _ = cv2.connectedComponentsWithStats(body, 8)
    if n > 2:
        main = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
        stray = [tuple(int(v) for v in st[k]) for k in range(1, n) if k != main and st[k, cv2.CC_STAT_AREA] > 25]
        if stray:
            flags.append((i, "stray", stray[:3]))
    if u >= SETTLE + 1:
        d = float(np.mean(np.abs(faces[i].astype(np.float32) - faces[i - 1].astype(np.float32))))
        if d > 9:
            flags.append((i, "face_jump", round(d, 1)))
print(f"{N} frames scanned, {len(starts)} segments, {len(flags)} flags")
for f in flags[:120]:
    print(f"frame {f[0]:5d} t={f[0] / FPS:6.2f}  {f[1]}  {f[2]}")
