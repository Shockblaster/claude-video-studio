#!/usr/bin/env python3
"""Word timings for the whole voice-over: transcribe each line WAV separately (Whisper through
`npx hyperframes transcribe`), then shift every word by the line's start in vo.wav.

  python -I words.py --vo vo [--fix fixes.json] [--model small.en]

Needs <vo>/lines/NN.wav and <vo>/starts.json from build_vo.py. Writes <vo>/tr/NN/transcript.json and
<vo>/words.json [{line, i, text, start, end}]. fixes.json maps Whisper spellings to the script's
({"lack": "lakh", "canceling": "cancelling"}). Whisper word times can run ~0.4 s late on a word after a
pause: check the waveform before trusting one for a big visual hit.
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import _paths  # noqa: E402

TRIM = 0.01


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--fix")
    ap.add_argument("--model", default="small.en")
    a = ap.parse_args()
    vo = pathlib.Path(a.vo); S = json.loads((vo / "starts.json").read_text())
    fix = json.loads(pathlib.Path(a.fix).read_text(encoding="utf-8")) if a.fix else {}
    words = []
    for i, st in enumerate(S["starts"], 1):
        wav = vo / "lines" / f"{i:02d}.wav"
        d = vo / "tr" / f"{i:02d}"; d.mkdir(parents=True, exist_ok=True)
        tj = d / "transcript.json"
        if not tj.exists():
            (d / "line.wav").write_bytes(wav.read_bytes())
            subprocess.run([_paths.npx(), "hyperframes", "transcribe", "line.wav", "--model", a.model, "--json"],
                           cwd=d, capture_output=True, check=True)
        y, sr = sf.read(str(wav), dtype="float32")
        y = y.mean(1) if y.ndim > 1 else y
        nz = np.flatnonzero(np.abs(y) > TRIM)
        off = max(0, nz[0] - int(0.03 * sr)) / sr                  # same trim as build_vo.py
        w = json.loads(tj.read_text()); w = w if isinstance(w, list) else w["words"]
        for j, x in enumerate(w):
            words.append({"line": i, "i": j, "text": fix.get(x["text"], x["text"]),
                          "start": round(st + x["start"] - off, 3), "end": round(st + x["end"] - off, 3)})
        print(f"line {i:02d}: {len(w)} words")
    (vo / "words.json").write_text(json.dumps(words, indent=0))
    print(f"{len(words)} words -> {vo / 'words.json'}")


if __name__ == "__main__":
    main()
