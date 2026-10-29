#!/usr/bin/env python3
"""Measured QC for a rendered short-form video. Prints a JSON report and writes a
contact sheet with the platform safe zones drawn on, so the eye check is quick.

Checks:
  spec      width x height, fps, codec h264, pix_fmt yuv420p, audio present (aac)
  length    duration inside [--min, --max] seconds
  loudness  integrated LUFS and true peak (ffmpeg ebur128), target -16..-13 LUFS, TP <= -1
  opening   first frame is not black and audio is not silent in the first 0.5 s (hook check)
  sheet     N evenly spaced frames, IG/YT UI zones shaded red, at phone-ish scale

Usage:
  python -I qc_reel.py video.mp4 [--sheet out.png] [--frames 8] [--min 7 --max 90]
Exit code 0 when every hard check passes, 1 otherwise.
"""
import argparse
import json
import re
import subprocess
import sys

# UI bands on a 1080x1920 vertical, from the hyperframes skill (references/types/vertical.md):
# nothing in the top 168 px, words inside 168..1330 px, below 1330 only decoration.
# Side margin keeps text off the right-hand action rail. Ads reserve more: pass --ads.
SAFE = {"top": 168 / 1920, "bottom": (1920 - 1330) / 1920, "side": 0.06}
SAFE_ADS = {"top": 0.14, "bottom": 0.35, "side": 0.06}  # Meta Reels-ad guidance


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]).stdout
    return json.loads(out)


def loudness(path):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    tail = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    return (float(i.group(1)) if i else None, float(tp.group(1)) if tp else None)


def opening(path):
    err = run(["ffmpeg", "-hide_banner", "-t", "0.5", "-i", path,
               "-vf", "blackdetect=d=0.1:pix_th=0.02", "-af", "volumedetect", "-f", "null", "-"]).stderr
    black = "black_start:0" in err
    m = re.search(r"mean_volume:\s+(-?[\d.]+) dB", err)
    mean_db = float(m.group(1)) if m else None
    return black, mean_db


def sheet(path, out, frames, dur, w, h, safe):
    cols = 4 if frames >= 4 else frames
    rows = (frames + cols - 1) // cols
    step = dur / (frames + 1)
    t_top, t_bot, t_side = int(h * safe["top"]), int(h * safe["bottom"]), int(w * safe["side"])
    # light tint on the UI bands, a solid outline on the safe box, so the frame stays readable
    shade = (f"drawbox=x=0:y=0:w=iw:h={t_top}:color=red@0.10:t=fill,"
             f"drawbox=x=0:y=ih-{t_bot}:w=iw:h={t_bot}:color=red@0.10:t=fill,"
             f"drawbox=x={t_side}:y={t_top}:w=iw-{2 * t_side}:h=ih-{t_top + t_bot}:color=lime@0.9:t=8")
    vf = f"fps=1/{step:.3f},{shade},scale=270:-1,tile={cols}x{rows}:padding=6:color=white"
    run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{step/2:.3f}", "-i", path, "-vf", vf, "-frames:v", "1", out])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--sheet")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--min", type=float, default=7)
    ap.add_argument("--max", type=float, default=90)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--ads", action="store_true", help="use the stricter paid-ads safe zone")
    a = ap.parse_args()

    p = probe(a.video)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), {})
    au = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    num, den = (v.get("r_frame_rate", "0/1").split("/") + ["1"])[:2]
    fps = round(float(num) / float(den or 1), 2)
    dur = float(p["format"]["duration"])
    lufs, tp = loudness(a.video) if au else (None, None)
    black, mean_db = opening(a.video)

    checks = {
        "resolution": (v.get("width"), v.get("height")) == (a.width, a.height),
        "fps_30_or_60": fps in (30.0, 60.0, 29.97),
        "h264": v.get("codec_name") == "h264",
        "yuv420p": v.get("pix_fmt") == "yuv420p",
        "audio_aac": bool(au) and au.get("codec_name") == "aac",
        "length": a.min <= dur <= a.max,
        "loudness_-16_to_-13": lufs is not None and -16.5 <= lufs <= -12.5,
        "true_peak_le_-1": tp is not None and tp <= -1.0,
        "opening_not_black": not black,
        "opening_has_sound": mean_db is not None and mean_db > -45,
    }
    soft = {"opening_has_sound"}  # silent cold opens can be a choice
    report = {
        "file": a.video, "width": v.get("width"), "height": v.get("height"), "fps": fps,
        "codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
        "audio": au.get("codec_name") if au else None, "duration": round(dur, 2),
        "lufs": lufs, "true_peak": tp, "opening_mean_db": mean_db,
        "checks": checks,
        "pass": all(ok for k, ok in checks.items() if k not in soft),
    }
    if a.sheet:
        sheet(a.video, a.sheet, a.frames, dur, v.get("width", a.width), v.get("height", a.height),
              SAFE_ADS if a.ads else SAFE)
        report["sheet"] = a.sheet
    print(json.dumps(report, indent=1))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
