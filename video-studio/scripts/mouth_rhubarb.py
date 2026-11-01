#!/usr/bin/env python3
"""Phoneme-accurate mouth cues with Rhubarb Lip Sync + the SCRIPT TEXT (the default for English).

Why: mouth_from_audio.py reads only loudness/brightness. It never uses G (f/v) or H (l) and often
misses the M/B/P lip closure, which the user saw as "sloppy" (2026-10-29). Rhubarb with the dialog
text (-d) aligns real phonemes. Keep mouth_from_audio.py as the fallback (Hindi, no script).

Two modes, both writing Rhubarb JSON ({"metadata":..., "mouthCues":[{start,end,value}]}):
  per-line (preferred; matches build_vo.py, whose lines are trimmed then placed at measured starts):
    python -I mouth_rhubarb.py --lines-dir vo/lines --starts vo/starts.json -o avatar/mouth.json
    (line text comes from starts.json "lines"; WAVs are lines/01.wav, 02.wav, ...)
  single file:
    python -I mouth_rhubarb.py --wav vo.wav --text script.txt -o mouth.json

Post-processing (animation practice, not Rhubarb's own):
  --lead 1      shift every shape 1 frame EARLY: a mouth that lags the sound reads as off-sync.
  --min-hold 2  merge shapes shorter than 2 frames into a neighbour (no flicker), but never drop
                an A (M/B/P closure) shorter than that: closures are what sell the sync.
  Silences longer than the gaps between lines are filled with X (rest).
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

RHUBARB = _paths.rhubarb()
TRIM_DB = 0.01            # build_vo.py trims at |x| > 0.01 and keeps 0.03 s before the first sound


def run_rhubarb(wav, text, recognizer):
    with tempfile.TemporaryDirectory() as d:
        txt = pathlib.Path(d) / "dialog.txt"; txt.write_text(text, encoding="utf-8")
        out = pathlib.Path(d) / "m.json"
        pcm = pathlib.Path(d) / "in.wav"           # Rhubarb wants 16-bit PCM; normalise whatever we got
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ac", "1", "-c:a", "pcm_s16le", str(pcm)], check=True)
        cmd = [str(RHUBARB), "-q", "-f", "json", "--extendedShapes", "GHX", "-r", recognizer, "-o", str(out)]
        if text:
            cmd += ["-d", str(txt)]
        subprocess.run(cmd + [str(pcm)], check=True)
        return json.loads(out.read_text())["mouthCues"]


def trim_offset(wav):
    import soundfile as sf
    y, sr = sf.read(str(wav), dtype="float32")
    y = y.mean(1) if y.ndim > 1 else y
    nz = np.flatnonzero(np.abs(y) > TRIM_DB)
    return max(0, nz[0] - int(0.03 * sr)) / sr if len(nz) else 0.0


def to_frames(cues, fps, total):
    n = int(np.ceil(total * fps)) + 1
    f = ["X"] * n
    for c in cues:
        a, b = int(round(c["start"] * fps)), int(round(c["end"] * fps))
        for i in range(max(0, a), min(n, b)):
            f[i] = c["value"]
    return f


def polish(f, lead, min_hold):
    if lead:
        f = f[lead:] + ["X"] * lead
    runs = []                                   # [value, length]
    for v in f:
        if runs and runs[-1][0] == v:
            runs[-1][1] += 1
        else:
            runs.append([v, 1])
    changed = True
    while changed:
        changed = False
        for i, (v, ln) in enumerate(runs):
            if ln < min_hold and v != "A" and len(runs) > 1:
                j = i - 1 if i > 0 else i + 1     # absorb into the previous run (keeps the sound's onset)
                runs[j][1] += ln; del runs[i]
                k = 0                             # re-merge equal neighbours
                while k < len(runs) - 1:
                    if runs[k][0] == runs[k + 1][0]:
                        runs[k][1] += runs[k + 1][1]; del runs[k + 1]
                    else:
                        k += 1
                changed = True
                break
    out = []
    for v, ln in runs:
        out += [v] * ln
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines-dir"); ap.add_argument("--starts")
    ap.add_argument("--wav"); ap.add_argument("--text")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--lead", type=int, default=1)
    ap.add_argument("--min-hold", type=int, default=2)
    ap.add_argument("--recognizer", default="pocketSphinx", help="pocketSphinx (English) or phonetic (other languages)")
    a = ap.parse_args()
    if not RHUBARB.exists():
        sys.exit(f"Rhubarb not found at {RHUBARB}; use mouth_phonemes.py (same arguments)")
    cues = []
    if a.lines_dir:
        S = json.loads(pathlib.Path(a.starts).read_text())
        total = S["total"]
        if "starts" not in S:                        # build_vo.py format: lines = [{i, start, dur, text}]
            S = {"starts": [x["start"] for x in S["lines"]], "lines": [x["text"] for x in S["lines"]]}
        for i, (st, text) in enumerate(zip(S["starts"], S["lines"]), 1):
            wav = pathlib.Path(a.lines_dir) / f"{i:02d}.wav"
            off = st - trim_offset(wav)              # line-file time 0 lands here in vo.wav
            for c in run_rhubarb(wav, text, a.recognizer):
                cues.append({"start": c["start"] + off, "end": c["end"] + off, "value": c["value"]})
            print(f"line {i:02d} ok", flush=True)
    else:
        text = pathlib.Path(a.text).read_text(encoding="utf-8") if a.text else ""
        cues = run_rhubarb(a.wav, text, a.recognizer)
        total = max(c["end"] for c in cues)
    frames = polish(to_frames(cues, a.fps, total), a.lead, a.min_hold)
    out, i = [], 0
    while i < len(frames):
        j = i
        while j < len(frames) and frames[j] == frames[i]:
            j += 1
        out.append({"start": round(i / a.fps, 3), "end": round(j / a.fps, 3), "value": frames[i]})
        i = j
    meta = {"soundFile": a.wav or a.lines_dir, "duration": round(total, 3), "source": "rhubarb -d (dialog text)",
            "lead_frames": a.lead, "min_hold": a.min_hold}
    pathlib.Path(a.output).write_text(json.dumps({"metadata": meta, "mouthCues": out}))
    counts = {}
    for c in out:
        counts[c["value"]] = counts.get(c["value"], 0) + 1
    print(json.dumps({"ok": True, "cues": len(out), "shapes": counts, "output": a.output}))


if __name__ == "__main__":
    main()
