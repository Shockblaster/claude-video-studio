#!/usr/bin/env python3
"""MOTION SCORE: how our reel moves, beside the measured ranges of 71 hand-picked reference reels (2026-11-02).

  python -I motion_score.py out.mp4 [--format all|creator-edit|vox-collage|...] [--out DIR]

Runs study_motion.py (OpenCV DIS optical flow, from a friend's fork of this skill; tested there on known clips:
animated fps 29.6/14.8/10.0/7.4 for true 30/15/10/7.5, its shot detector found 87% of hand-marked cuts vs
PySceneDetect's 72%), then compares five picture measures with references/reference-ranges.json (low = p10-ish,
mid = median, high = p90-ish of that group; n = reels measured).
Trust (the fork's validation): HIGH for effective fps, hard cuts and fades; MEDIUM for camera movement.
Never a taste score: a flag means "look at it", not "it's bad". A placed avatar over a moving world reads as
camera movement only where the WORLD moves; a static avatar box lowers it.
Writes DIR/motion.json, motion_env.npz, slice_vertical.jpg (time runs left to right: read it for dead stretches).
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
MEASURES = [  # key, side that is bad, what it means
    ("camera_moving_pct", "low", "picture sits still; references drift or push most of the time"),
    ("still_half_seconds_pct", "high", "too many dead half-seconds"),
    ("hook_energy", "low", "the first 3 s move less than the rest (references hit early)"),
    ("transitions_per_10s", "low", "few picture changes"),
    ("effective_fps", "low", "animation updates on twos or threes (fine only for stepped paper styles)"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--format", default="all")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = pathlib.Path(a.out or pathlib.Path(a.video).with_suffix("").as_posix() + "_motion")
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-I", str(HERE / "study_motion.py"), a.video, str(out)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-1500:])
    m = json.loads((out / "motion.json").read_text())
    z = np.load(out / "motion_env.npz")
    fp = z["fp"]; w = max(1, int(m["fps"] / 2)); n = max(1, len(fp) // w)
    m["still_half_seconds_pct"] = round(float(np.mean([fp[i * w:(i + 1) * w].max() < .5 for i in range(n)]) * 100), 1)
    m["hook_energy"] = m.get("energy_first3s_vs_rest")
    R = json.loads((HERE.parent / "references" / "reference-ranges.json").read_text())
    rg = R.get(a.format) or R["all"]
    flags = []
    print(f"{a.video}  vs '{a.format}' references (n={next(iter(rg.values()))['n']})")
    for k, side, why in MEASURES:
        v, g = m.get(k), rg.get(k)
        if v is None or not g:
            print(f"  {k:24} n/a"); continue
        bad = (side == "low" and v < g["low"]) or (side == "high" and v > g["high"])
        flags += [k] if bad else []
        print(f"  {k:24} {v:7.2f}   refs {g['low']:.2f} / {g['mid']:.2f} / {g['high']:.2f}   {'LOOK: ' + why if bad else 'ok'}")
    print(f"  cuts {m['cuts_per_10s']}/10 s, shot median {m['shot_median_s']} s, transitions {m.get('transition_mix')}, "
          f"ease {m.get('ease_mix_pct')}, motion arc (per s) {m.get('motion_arc')}")
    m["flags"] = flags
    (out / "motion_score.json").write_text(json.dumps(m, indent=1))
    print(f"  {len(flags)} flag(s). Read {out / 'slice_vertical.jpg'}. Not a taste score.")


if __name__ == "__main__":
    main()
