"""Every-frame contact sheets (the user's rule: check every frame before showing anything).
  python -I sheets.py VIDEO OUTDIR [--crop x,y,w,h] [--cols 10 --rows 6] [--width 180] [--bg magenta]
Each sheet holds cols*rows consecutive frames with the frame number and time burned in."""
import argparse
import pathlib
import subprocess

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("out")
ap.add_argument("--crop"); ap.add_argument("--cols", type=int, default=10); ap.add_argument("--rows", type=int, default=6)
ap.add_argument("--width", type=int, default=180); ap.add_argument("--start", type=float, default=0); ap.add_argument("--end", type=float, default=1e9)
a = ap.parse_args()
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS) or 30
cap.set(cv2.CAP_PROP_POS_FRAMES, int(a.start * fps))
i = int(a.start * fps); tiles = []; sheet = 0
crop = [int(v) for v in a.crop.split(",")] if a.crop else None


def flush():
    global tiles, sheet
    if not tiles:
        return
    h, w = tiles[0].shape[:2]
    while len(tiles) < a.cols * a.rows:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    rows = [np.hstack(tiles[r * a.cols:(r + 1) * a.cols]) for r in range(a.rows)]
    cv2.imwrite(str(out / f"sheet_{sheet:03d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
    sheet += 1; tiles = []


while True:
    ok, fr = cap.read()
    if not ok or i / fps > a.end:
        break
    if crop:
        x, y, w, h = crop; fr = fr[y:y + h, x:x + w]
    s = a.width / fr.shape[1]
    t = cv2.resize(fr, (a.width, int(fr.shape[0] * s)), interpolation=cv2.INTER_AREA)
    cv2.rectangle(t, (0, 0), (a.width, 18), (0, 0, 0), -1)
    cv2.putText(t, f"{i} {i / fps:.2f}", (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    tiles.append(t); i += 1
    if len(tiles) == a.cols * a.rows:
        flush()
flush()
print(f"{i} frames -> {sheet} sheets in {out}")
