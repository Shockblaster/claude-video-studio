#!/usr/bin/env python3
"""Per-line TTS voice-over, assembled at MEASURED starts (concatenating lines with a fixed gap drifts).

  python -I build_vo.py --lines vo/lines.txt --out vo [--voice af_heart] [--speed 1.0] [--lang en-us]
                        [--gap 0.4] [--gaps 0.45,0.35,...] [--only 3 5]

lines.txt: one spoken line per row (blank rows ignored). Write numbers the way they must be SAID when
the TTS gets them wrong (e.g. "forty-nine lakh" instead of "49 lakh"); captions keep the real spelling.

Writes <out>/lines/NN.wav (trimmed of silence), <out>/vo.wav and <out>/starts.json
({starts, durs, total, lines}). Feed starts.json to words.py (word timings) and to
../mouth_rhubarb.py --lines-dir <out>/lines --starts <out>/starts.json (lip-sync).
TTS = Kokoro through `npx hyperframes tts` (local, Apache 2.0). Pick voice + speed BY EAR with the user
(templates/reel-project/pick.html).
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import _paths  # noqa: E402

LEAD = 0.15           # silence before the first line (s)
TRIM = 0.01           # |x| threshold for silence trimming (keep 0.03 s before, 0.08 s after the sound)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--lang", default=None, help="pass e.g. hi for Hindi voices")
    ap.add_argument("--gap", type=float, default=0.4, help="silence after each line (s)")
    ap.add_argument("--gaps", help="comma list overriding --gap per line")
    ap.add_argument("--only", type=int, nargs="*", help="re-generate only these line numbers (1-based); 0 = none")
    a = ap.parse_args()
    lines = [l.strip() for l in pathlib.Path(a.lines).read_text(encoding="utf-8").splitlines() if l.strip()]
    gaps = [float(g) for g in a.gaps.split(",")] if a.gaps else [a.gap] * len(lines)
    gaps = (gaps + [a.gap] * len(lines))[:len(lines)]
    gaps[-1] = 0.0
    out = pathlib.Path(a.out); ld = out / "lines"; ld.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HYPERFRAMES_PYTHON=os.environ.get("HYPERFRAMES_PYTHON", sys.executable))
    for i, text in enumerate(lines, 1):
        f = ld / f"{i:02d}.wav"
        if a.only is not None and i not in a.only and f.exists():
            continue
        cmd = [_paths.npx(), "hyperframes", "tts", text, "-v", a.voice, "-s", str(a.speed), "-o", str(f), "--json"]
        if a.lang:
            cmd += ["-l", a.lang]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if r.returncode != 0 or not f.exists():
            sys.exit(f"TTS failed on line {i}: {(r.stdout + r.stderr)[-800:]}")
    clips, sr = [], None
    for i in range(len(lines)):
        y, s = sf.read(ld / f"{i + 1:02d}.wav", dtype="float32")
        y = y.mean(1) if y.ndim > 1 else y
        sr = sr or s
        nz = np.flatnonzero(np.abs(y) > TRIM)
        clips.append(y[max(0, nz[0] - int(0.03 * sr)): nz[-1] + int(0.08 * sr)])
    starts, t = [], LEAD
    for y, g in zip(clips, gaps):
        starts.append(round(t, 3)); t += len(y) / sr + g
    mix = np.zeros(int(np.ceil(t * sr)) + sr, np.float32)          # +1 s of headroom (rounding)
    for y, st in zip(clips, starts):
        k = int(round(st * sr)); mix[k:k + len(y)] += y
    sf.write(out / "vo.wav", mix[:int(np.ceil(t * sr))], sr)
    json.dump({"sr": sr, "voice": a.voice, "speed": a.speed, "starts": starts,
               "durs": [round(len(y) / sr, 3) for y in clips], "total": round(t, 3), "lines": lines},
              open(out / "starts.json", "w"), indent=1)
    for i, (st, y) in enumerate(zip(starts, clips), 1):
        print(f"{i:02d}  start {st:6.2f}  dur {len(y) / sr:5.2f}  {lines[i - 1][:60]}")
    print(f"VO total {t:.2f} s -> {out / 'vo.wav'}")


if __name__ == "__main__":
    main()
