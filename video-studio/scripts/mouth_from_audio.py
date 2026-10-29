#!/usr/bin/env python3
"""Cartoon mouth cues from a voice track, in Rhubarb Lip Sync's JSON format.

No speech model: it reads loudness and brightness per frame, so it works for any
language (Hindi, English, Hinglish) on a slow CPU. Output matches Rhubarb's
`-f json` shape ({"metadata":..., "mouthCues":[{"start","end","value"}]}), so an
avatar component written against it also accepts real Rhubarb output later.

Shapes used (Rhubarb's Preston Blair set):
  X rest, A closed (M/B/P), B slightly open, C open, D wide open,
  E rounded (O), F puckered (OO/W).

Usage:
  python -I mouth_from_audio.py voice.wav -o mouth.json [--fps 30] [--min-hold 2]
"""
import argparse
import json
import subprocess
import sys

import numpy as np

SR = 16000


def read_pcm(path):
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def frame_features(x, fps):
    hop = SR // fps
    n = len(x) // hop
    rms = np.zeros(n)
    centroid = np.zeros(n)
    freqs = np.fft.rfftfreq(hop * 2, 1 / SR)
    win = np.hanning(hop * 2)
    for i in range(n):
        seg = x[i * hop:i * hop + hop * 2]
        if len(seg) < hop * 2:
            seg = np.pad(seg, (0, hop * 2 - len(seg)))
        rms[i] = np.sqrt(np.mean(seg ** 2))
        mag = np.abs(np.fft.rfft(seg * win))
        centroid[i] = (freqs * mag).sum() / (mag.sum() + 1e-9)
    # light smoothing so the mouth does not flicker between frames
    k = np.array([0.25, 0.5, 0.25])
    rms = np.convolve(rms, k, mode="same")
    centroid = np.convolve(centroid, k, mode="same")
    return rms, centroid


def classify(rms, centroid):
    speech = rms[rms > 1e-4]
    if speech.size == 0:
        return ["X"] * len(rms)
    floor = np.percentile(speech, 15)
    lo, mid, hi = np.percentile(speech, [35, 60, 85])
    c_lo = np.percentile(centroid[rms > floor], 25) if (rms > floor).any() else 0
    shapes = []
    for r, c in zip(rms, centroid):
        if r <= floor:
            shapes.append("X")
        elif r < lo:
            shapes.append("A" if c > c_lo else "B")
        elif r < mid:
            shapes.append("F" if c < c_lo else "B")
        elif r < hi:
            shapes.append("E" if c < c_lo else "C")
        else:
            shapes.append("D")
    return shapes


def to_cues(shapes, fps, min_hold):
    # collapse runs, then absorb runs shorter than min_hold into the previous cue
    runs = []
    for s in shapes:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s, 1])
    merged = []
    for s, n in runs:
        if merged and n < min_hold:
            merged[-1][1] += n
        else:
            merged.append([s, n])
    cues, t = [], 0
    for s, n in merged:
        cues.append({"start": round(t / fps, 3), "end": round((t + n) / fps, 3), "value": s})
        t += n
    return cues


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--min-hold", type=int, default=2, help="minimum frames a shape is held")
    a = ap.parse_args()
    x = read_pcm(a.audio)
    rms, centroid = frame_features(x, a.fps)
    cues = to_cues(classify(rms, centroid), a.fps, a.min_hold)
    out = {"metadata": {"soundFile": a.audio, "duration": round(len(x) / SR, 3),
                        "generator": "video-studio/mouth_from_audio.py (amplitude, language-free)"},
           "mouthCues": cues}
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    counts = {}
    for c in cues:
        counts[c["value"]] = counts.get(c["value"], 0) + 1
    print(json.dumps({"ok": True, "cues": len(cues), "shapes": counts, "output": a.output}))


if __name__ == "__main__":
    sys.exit(main())
