#!/usr/bin/env python3
"""Every-frame face audit for avatar videos. Sampling a few frames MISSED double mouths and
double brows that the user saw at once; this tiles EVERY frame so nothing hides.

  python -I audit_face.py video.mp4 --rect x,y,w,h | --audit proj/audit.json  --out dir
         [--from 0 --to end] [--per-sheet 30] [--scale 1.0]

Writes dir/sheet_000.png ... each with N consecutive frames (frame number + time printed on
each tile) at full resolution of the face crop. READ every sheet. Look for: two mouths at
once, brows doubled or cut by the patch edge, a patch edge line, eyes that do not fully
close on a blink, a ghost of the previous pose, flicker of the wrong patch for one frame.
"""
import argparse
import json
import pathlib
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--rect")
    ap.add_argument("--audit")
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="t0", type=float, default=0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--per-sheet", type=int, default=30)
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    x, y, w, h = (json.loads(pathlib.Path(a.audit).read_text())["face"] if a.audit
                  else [int(v) for v in a.rect.split(",")])
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video],
                               capture_output=True, text=True).stdout.strip())
    t1 = a.t1 if a.t1 is not None else dur
    cols = 6
    rows = (a.per_sheet + cols - 1) // cols
    tw = int(w * a.scale)
    vf = (f"trim=start={a.t0}:end={t1},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale={tw}:-1,"
          f"drawtext=text='f%{{eif\\:n+{int(a.t0 * 30)}\\:d}} %{{eif\\:(n+{int(a.t0 * 30)})*1000/30\\:d}}ms':"
          f"x=6:y=6:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.6,"
          f"tile={cols}x{rows}:padding=4:color=white")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.video, "-vf", vf, "-fps_mode", "passthrough",
                    str(out / "sheet_%03d.png")], check=True)
    sheets = sorted(out.glob("sheet_*.png"))
    print(json.dumps({"ok": True, "sheets": len(sheets), "rect": [x, y, w, h], "out": str(out)}))


if __name__ == "__main__":
    sys.exit(main())
