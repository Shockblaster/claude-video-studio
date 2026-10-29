#!/usr/bin/env python3
"""Render the placed avatar track in FOREGROUND chunks, then join them.

Why chunks: on a small laptop, long BACKGROUND jobs get killed when memory runs low; a 12 s chunk takes
~4 min and can be redone alone. Each chunk gets a sub-plan holding ONLY the segments (poses) it shows,
because avatar_track.py loads every pose in its plan up front.

  python -I render_chunks.py --plan avatar/plan.json --poses <pose library> --face <rig>/face \
         --landmarks <rig>/face_landmarks.json --mouth avatar/mouth.json --voice vo/vo.wav \
         --out avatar --chunk 0            # one chunk per call; repeat for 1, 2, ...
  python -I render_chunks.py ... --join     # concat -> <out>/avatar.webm + <out>/preview.mp4 (magenta, with voice)

  --size 12 sets the chunk length (s). Read EVERY frame of preview.mp4 (pipeline/sheets.py) and run
  pipeline/scan_avatar.py before the reel is composited.
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
TRACK = HERE.parent / "avatar_track.py"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("plan", "poses", "face", "landmarks", "mouth", "voice", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--clips", help="hybrid clips folder (defaults to --poses)")
    ap.add_argument("--size", type=float, default=12.0)
    ap.add_argument("--chunk", type=int)
    ap.add_argument("--join", action="store_true")
    a = ap.parse_args()
    plan = json.loads(pathlib.Path(a.plan).read_text())
    n = math.ceil(plan["end"] / a.size)
    CH = [(k * a.size, min(plan["end"], (k + 1) * a.size)) for k in range(n)]
    out = pathlib.Path(a.out); cd = out / "chunks"; cd.mkdir(parents=True, exist_ok=True)
    if a.join:
        for ext in ("webm", "mp4"):
            (cd / f"list_{ext}.txt").write_text("".join(f"file 'c{k}.{ext}'\n" for k in range(n)))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(cd / f"list_{ext}.txt"),
                            "-c", "copy", str(out / f"_joined.{ext}")], check=True)
        (out / "_joined.webm").replace(out / "avatar.webm")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out / "_joined.mp4"), "-i", a.voice, "-c:v", "copy",
                        "-c:a", "aac", "-af", "apad", "-t", str(plan["end"]), str(out / "preview.mp4")], check=True)
        (out / "_joined.mp4").unlink()
        print(f"joined {n} chunks -> {out / 'avatar.webm'}, {out / 'preview.mp4'}")
        return
    if a.chunk is None or not 0 <= a.chunk < n:
        sys.exit(f"--chunk 0..{n - 1} or --join")
    t0, t1 = CH[a.chunk]
    segs = plan["segments"]; ends = [s["start"] for s in segs[1:]] + [plan["end"]]
    keep = [s for s, e in zip(segs, ends) if s["start"] < t1 and e > t0]
    sp = cd / f"plan_{a.chunk}.json"; sp.write_text(json.dumps(dict(plan, segments=keep), indent=1))
    print("chunk", a.chunk, t0, t1, "poses:", sorted({s.get("pose") or s.get("clip") for s in keep}), flush=True)
    subprocess.run([sys.executable, "-I", str(TRACK), "--plan", str(sp), "--poses", a.poses, "--clips", a.clips or a.poses,
                    "--face", a.face, "--landmarks", a.landmarks, "--mouth", a.mouth, "--voice", a.voice,
                    "--out", str(cd / f"c{a.chunk}.webm"), "--preview", str(cd / f"c{a.chunk}.mp4"), "--only", f"{t0}:{t1}"],
                   check=True)


if __name__ == "__main__":
    main()
