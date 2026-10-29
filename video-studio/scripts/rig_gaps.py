#!/usr/bin/env python3
"""Measure see-through gaps in a puppet rig: every pose with the rest mouth and open eyes on.
A gap is a pixel inside the closed silhouette with coverage under 0.9 (a light line across
the shoulders, a halo, a hole under the jaw). Prints per-pose counts and writes
gaps_<pose>.png with gaps in magenta. Target: 0 (a few edge pixels are noise).

  python -I rig_gaps.py rig_dir
"""
import json
import pathlib
import sys

import cv2
import numpy as np


def main():
    d = pathlib.Path(sys.argv[1])
    r = json.loads((d / "rig.json").read_text())
    def load(n):
        return cv2.imread(str(d / n), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
    m, e = load("mouth_X.png"), load("eyes_open.png")
    out = {}
    for p in r["poses"]:
        L = load(f"pose_{p}.png")
        a = L[..., 3].copy()
        for patch, (x, y, w, h) in ((m, r["mouth"]["box"]), (e, r["eyes"]["box"])):
            a[y:y + h, x:x + w] = 1 - (1 - a[y:y + h, x:x + w]) * (1 - patch[..., 3])
        sil = cv2.morphologyEx((a > 0.5).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
        sil = cv2.erode(sil, np.ones((7, 7), np.uint8))           # ignore the anti-aliased rim
        gaps = (sil > 0) & (a < 0.9)
        # only the head/neck/shoulder band, where the layer joins are (closing the whole
        # silhouette also flagged the background between arms and body)
        band_end = int(r.get("neck", L.shape[0]) + 0.08 * L.shape[0])
        gaps[band_end:] = False
        out[p] = int(gaps.sum())
        bg = np.full(L.shape[:2] + (3,), 128.0)
        vis = (L[..., :3] * 255 * L[..., 3:4] + bg * (1 - L[..., 3:4])).astype(np.uint8)
        vis[gaps] = (255, 0, 255)
        cv2.imwrite(str(d / f"gaps_{p}.png"), vis)
    print(json.dumps({"gaps": out, "ok": all(v < 200 for v in out.values())}))


if __name__ == "__main__":
    sys.exit(main())
