#!/usr/bin/env python3
"""BEAT GRID: the one timeline every beat-synced reel is built on (2026-11-01; method from lemo-opuscar's
"one timeline drives everything", MIT, github.com/lemomo-ai/lemo-opuscar).

Three modes, all writing the same timeline.json:

  1. a music track (stock / Mixkit / your own):
     python -I beatgrid.py --music track.mp3 -o timeline.json [--bpm-range 70 180] [--meter 4]
     Detects tempo from the onset envelope, then FITS ONE UNIFORM GRID over the whole track (beat trackers
     miss beats in quiet intros; a fitted grid does not), finds the downbeat from the low band (kick).

  2. an authored grid, for an original score (scripts/score.py writes music FROM this grid):
     python -I beatgrid.py --bpm 112 --dur 10 [--offset 0.2] -o timeline.json

  3. fit the music to the edit: the voice is locked, so move the MUSIC, not the words.
     python -I beatgrid.py --music track.mp3 --cues cues.json --dur 9.9 -o timeline.json
        -> picks the start point in the track (seek) whose beats land closest to the cues marked "beat"
     python -I beatgrid.py --fit-bpm 90 130 --cues cues.json --dur 9.9 -o timeline.json
        -> for an original score: picks bpm + phase so the "beat" cues fall on beats

timeline.json: {bpm, beat_s, offset (first beat, reel time), meter, beats[], downbeats[], dur, source, seek}
cues.json (shared with /sound-effects sound_pass.py): [{"t": 1.6, "type": "scene_cut", "desc": "...",
  "lock": "beat" | "word" | "free", "role": "<earshot kit role, e.g. pop, hit, whoosh.short>"}]
  lock "beat": a visual event we can move (cut, pop, card landing): it must sit on a beat (cuecheck.py).
  lock "word": tied to a spoken word: it stays; SFX land on it; the grid ignores it.
  lock "anchor": a spoken word that should ALSO land on a beat (the hook word, the reveal word): it stays, and the
               grid (bpm / phase / music seek) is fitted to it together with the "beat" cues.
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np
from scipy.signal import stft

SR = 22050
HOP = 256


def load(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def onset_env(y, lo_hz=None, hi_hz=None):
    f, t, Z = stft(y, SR, nperseg=1024, noverlap=1024 - HOP, boundary=None)
    M = np.log1p(100 * np.abs(Z))
    if lo_hz is not None or hi_hz is not None:
        sel = (f >= (lo_hz or 0)) & (f <= (hi_hz or SR))
        M = M[sel]
    flux = np.maximum(0, np.diff(M, axis=1)).sum(0)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")       # local mean removed: transients only
    return np.maximum(flux, 0) / (flux.max() + 1e-9)


def tempo(env, lo=70, hi=180):
    fps = SR / HOP
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    best, bb = None, -1
    for bpm in np.arange(lo, hi + 0.01, 0.25):
        lag = 60 / bpm * fps
        # comb over 1, 2, 4 beats; a weak prior around 115 bpm breaks double/half ties
        s = sum(np.interp(k * lag, np.arange(len(ac)), ac) for k in (1, 2, 4)) * np.exp(-0.5 * (np.log2(bpm / 115) / 0.9) ** 2)
        if s > bb:
            best, bb = bpm, s
    return best


def fit_grid(env, bpm, dur):
    """One uniform grid over the whole track: refine bpm (+-1 %) and phase by the comb sum."""
    fps = SR / HOP
    tt = np.arange(len(env)) / fps
    best = (-1, bpm, 0.0)
    for b in np.linspace(bpm * 0.99, bpm * 1.01, 41):
        p = 60 / b
        for ph in np.arange(0, p, 0.005):
            g = np.arange(ph, dur, p)
            s = np.interp(g, tt, env).sum() / max(1, len(g))
            if s > best[0]:
                best = (s, b, ph)
    return best[1], best[2]


def downbeat(y, bpm, off, dur, meter):
    low = onset_env(y, hi_hz=160)
    fps = SR / HOP
    tt = np.arange(len(low)) / fps
    p = 60 / bpm
    sc = [np.interp(np.arange(off + k * p, dur, meter * p), tt, low).sum() for k in range(meter)]
    return int(np.argmax(sc))


def grid(bpm, off, dur, meter, db=0, start=0.0):
    p = 60 / bpm
    first = off + np.ceil((start - off) / p - 1e-9) * p if start > off else off
    beats = np.arange(first, dur + 1e-9, p)
    idx = np.round((beats - off) / p).astype(int)
    downs = beats[(idx - db) % meter == 0]
    return beats, downs


def cue_score(cues, beats, tol):
    ts = [c["t"] for c in cues if c.get("lock") in ("beat", "anchor")]
    if not ts or not len(beats):
        return 0.0, []
    d = [float(np.min(np.abs(beats - t))) for t in ts]
    return float(np.mean([np.exp(-0.5 * (x / tol) ** 2) for x in d])), d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--music")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--fit-bpm", type=float, nargs=2, metavar=("LO", "HI"))
    ap.add_argument("--bpm-range", type=float, nargs=2, default=(70, 180))
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--dur", type=float, help="reel length (s); default: the track's length")
    ap.add_argument("--meter", type=int, default=4)
    ap.add_argument("--cues", help="cues.json: fit the music / bpm to the 'beat' cues")
    ap.add_argument("--tol", type=float, default=0.033, help="alignment tolerance for fitting (s), default 1 frame")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    cues = json.loads(pathlib.Path(a.cues).read_text()) if a.cues else []
    out = {"meter": a.meter}

    if a.music:
        y = load(a.music)
        tdur = len(y) / SR
        env = onset_env(y)
        b0 = tempo(env, *a.bpm_range)
        bpm, off = fit_grid(env, b0, tdur)
        db = downbeat(y, bpm, off, tdur, a.meter)
        dur = a.dur or tdur
        seek = 0.0
        if cues:
            # move the music under the edit: try every seek point on a 10 ms step, keep the one whose beats
            # (in reel time) sit closest to the 'beat' cues; ties go to a downbeat at a cue
            best = (-1, 0.0)
            p = 60 / bpm
            for s in np.arange(0, max(0.0, tdur - dur) + 1e-9, 0.01):
                beats_r = np.arange(off, tdur, p) - s
                sc, _ = cue_score(cues, beats_r[(beats_r > -0.01) & (beats_r < dur + 0.01)], a.tol)
                if sc > best[0] + 1e-6:
                    best = (sc, s)
            seek = round(float(best[1]), 3)
        p = 60 / bpm
        all_beats = np.arange(off, tdur, p) - seek
        k0 = int(np.argmax(all_beats > -1e-6))
        beats = all_beats[k0:]
        beats = beats[beats <= dur + 1e-9]
        idx = np.arange(k0, k0 + len(beats))
        downs = beats[(idx - db) % a.meter == 0]
        out.update(source=str(a.music), track_dur=round(tdur, 3), detected_bpm=round(b0, 2), seek=seek)
    else:
        if not a.dur:
            sys.exit("--dur is needed without --music")
        dur = a.dur
        if a.fit_bpm:
            best = (-1, None, None)
            for b in np.arange(a.fit_bpm[0], a.fit_bpm[1] + 1e-9, 0.25):
                p = 60 / b
                for ph in np.arange(0, p, 0.005):
                    bt = np.arange(ph, dur + p, p)
                    sc, _ = cue_score(cues, bt, a.tol)
                    if sc > best[0] + 1e-6:
                        best = (sc, b, ph)
            bpm, off = float(best[1]), float(best[2])
        elif a.bpm:
            bpm, off = a.bpm, a.offset
        else:
            sys.exit("give --music, --bpm or --fit-bpm")
        db = 0
        beats, downs = grid(bpm, off, dur, a.meter, db)
        if cues:
            # the downbeat goes on the strongest 'beat' cue (the reveal / first cut) when one sits on a beat
            strong = [c["t"] for c in cues if c.get("lock") in ("beat", "anchor") and c.get("type") in ("reveal", "scene_cut", "hit")]
            if strong:
                k = int(np.argmin(np.abs(beats - strong[0])))
                db = k % a.meter
                downs = beats[(np.arange(len(beats)) - db) % a.meter == 0]
        out.update(source="authored")
    sc, d = cue_score(cues, beats, a.tol) if cues else (None, [])
    out.update(bpm=round(float(bpm), 3), beat_s=round(60 / float(bpm), 5), offset=round(float(beats[0]), 4) if len(beats) else 0.0,
               dur=round(float(dur), 3), beats=[round(float(x), 4) for x in beats],
               downbeats=[round(float(x), 4) for x in downs],
               fit={"beat_cues": len(d), "mean_off_ms": round(1000 * float(np.mean(d)), 1) if d else None,
                    "max_off_ms": round(1000 * float(np.max(d)), 1) if d else None})
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("beats", "downbeats")}))


if __name__ == "__main__":
    main()
