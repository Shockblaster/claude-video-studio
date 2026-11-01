#!/usr/bin/env python3
"""Word timings for the whole voice-over: transcribe each line WAV separately with Whisper, then shift
every word by the line's start in vo.wav.

  python -I words.py --vo vo [--fix fixes.json] [--model small.en] [--language hi] [--engine faster-whisper]

--engine faster-whisper (default): the venv's faster-whisper, nothing else to install (model downloads once
into ~/.cache/huggingface). --engine hyperframes: `npx hyperframes transcribe`, which needs whisper.cpp from
Homebrew or a cmake build. Hindi: --model small --language hi.

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


def faster_whisper_words(wav, model, language):
    from faster_whisper import WhisperModel
    from mouth_phonemes import load16k        # array input: faster-whisper 1.2.1 + PyAV 19 fail on file paths
    global _WM
    if "_WM" not in globals():
        _WM = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = _WM.transcribe(load16k(wav), language=language, word_timestamps=True,
                             condition_on_previous_text=False, beam_size=5)
    return [{"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
            for s in segs for w in s.words if w.word.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--fix")
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--language", help="e.g. hi; default: en for *.en models, else auto-detect")
    ap.add_argument("--engine", choices=["faster-whisper", "hyperframes"], default="faster-whisper")
    a = ap.parse_args()
    lang = a.language or ("en" if a.model.endswith(".en") else None)
    vo = pathlib.Path(a.vo); S = json.loads((vo / "starts.json").read_text())
    fix = json.loads(pathlib.Path(a.fix).read_text(encoding="utf-8")) if a.fix else {}
    words = []
    for i, st in enumerate(S["starts"], 1):
        wav = vo / "lines" / f"{i:02d}.wav"
        d = vo / "tr" / f"{i:02d}"; d.mkdir(parents=True, exist_ok=True)
        tj = d / "transcript.json"
        if not tj.exists() and a.engine == "faster-whisper":
            tj.write_text(json.dumps(faster_whisper_words(wav, a.model, lang)))
        elif not tj.exists():
            (d / "line.wav").write_bytes(wav.read_bytes())
            cmd = [_paths.npx(), "hyperframes", "transcribe", "line.wav", "--model", a.model, "--json"]
            subprocess.run(cmd + (["--language", lang] if lang else []), cwd=d, capture_output=True, check=True)
        y, sr = sf.read(str(wav), dtype="float32")
        y = y.mean(1) if y.ndim > 1 else y
        nz = np.flatnonzero(np.abs(y) > TRIM)
        off = max(0, nz[0] - int(0.03 * sr)) / sr                  # same trim as build_vo.py
        w = json.loads(tj.read_text(encoding="utf-8")); w = w if isinstance(w, list) else w["words"]
        for j, x in enumerate(w):
            words.append({"line": i, "i": j, "text": fix.get(x["text"], x["text"]),
                          "start": round(st + x["start"] - off, 3), "end": round(st + x["end"] - off, 3)})
        print(f"line {i:02d}: {len(w)} words")
    (vo / "words.json").write_text(json.dumps(words, indent=0))
    print(f"{len(words)} words -> {vo / 'words.json'}")


if __name__ == "__main__":
    main()
