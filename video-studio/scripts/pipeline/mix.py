#!/usr/bin/env python3
"""Sound pass: voice + SFX + music, music start chosen so the hard cuts land on beats, music ducked
under the voice, loudness measured on the exported file. Writes two masters:
  A = voice + SFX + music      B = voice + SFX (add a platform sound in the app)

  python -I mix.py --video out/silent.mp4 --vo vo/vo.wav --dur 80 --music music/track.mp3 \
         --sfx sfx.json [--timing hf/assets/timing.js] [--sfx-dir <sound-effects skill>/sfx] \
         [--hard wait,climax,send] [--music-credit '"Track" by Artist, Source #id, Licence'] [--out out]

sfx.json:
  {"cues":   [[time, "folder/file.ogg", gain_db, semitones], ...],
   "risers": [[start, end, "riser/file.ogg", gain_db], ...],        a riser ENDS on its hit
   "dips":   [[start, end, extra_db], ...],                           e.g. music holds its breath on a key word
   "swells": [[centre, half_width, plus_db], ...]}                    climax / payoff / reveal
  A time is seconds (12.4) or a cue name from timing.js with an offset ("climax", "wait-0.07", "send+0.5").
  Semitones pitch a one-shot by resampling (e.g. a pluck that climbs a pentatonic scale as the story
  advances: 0,2,4,7,9,12...). Use one sound per cue; every visual hit gets a sound.

Defaults that held up: music -10 dB in gaps and a further -12 dB under the voice (attack 40 ms, release
300 ms), master at -14 LUFS, true peak about -1 dBTP. SFX come from the /sound-effects skill's CC0 library;
music only with a licence that allows the use (log it in licences.md).
"""
import argparse
import json
import pathlib
import re
import subprocess

import librosa
import numpy as np
import soundfile as sf
from scipy.ndimage import maximum_filter1d, uniform_filter1d

SR = 48000


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True); ap.add_argument("--vo", required=True)
    ap.add_argument("--dur", type=float, required=True); ap.add_argument("--music")
    ap.add_argument("--sfx", required=True); ap.add_argument("--timing")
    ap.add_argument("--sfx-dir", default=str(pathlib.Path.home() / ".claude/skills/sound-effects/sfx"))
    ap.add_argument("--hard", default="", help="comma list of cue names / times that should land on beats")
    ap.add_argument("--music-credit", default="(music credit)")
    ap.add_argument("--target", type=float, default=-14.0, help="integrated LUFS")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    OUT = pathlib.Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
    T = json.loads(re.search(r"window.__T = (\{.*\});", pathlib.Path(a.timing).read_text(), re.S).group(1))["w"] if a.timing else {}

    def tm(x):
        if isinstance(x, (int, float)):
            return float(x)
        m = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*([+-]\s*[\d.]+)?\s*", str(x))
        if not m or m.group(1) not in T:
            raise SystemExit(f"unknown time / cue: {x!r}")
        return T[m.group(1)] + (float(m.group(2).replace(" ", "")) if m.group(2) else 0.0)

    spec = json.loads(pathlib.Path(a.sfx).read_text())
    n = int(a.dur * SR)
    SFX = pathlib.Path(a.sfx_dir)

    def load(path):
        y, _ = librosa.load(str(path), sr=SR, mono=False)
        y = np.atleast_2d(y)
        return (np.vstack([y, y]) if y.shape[0] == 1 else y).T

    def shift(y, st):
        if not st:
            return y
        idx = np.arange(0, len(y) - 1, 2 ** (st / 12))
        return np.stack([np.interp(idx, np.arange(len(y)), y[:, c]) for c in range(2)], 1).astype(np.float32)

    def place(buf, y, t, gain_db):
        i = max(0, int(round(t * SR))); y = y * 10 ** (gain_db / 20)
        m = min(len(y), len(buf) - i)
        if m > 0:
            buf[i:i + m] += y[:m]

    sfx = np.zeros((n, 2), np.float32); used = set(); cache = {}
    for c in spec.get("cues", []):
        t, f, g = c[0], c[1], c[2]; st = c[3] if len(c) > 3 else 0
        if f not in cache:
            cache[f] = load(SFX / f)
        place(sfx, shift(cache[f], st), tm(t), g); used.add(f)
    for t0, t1, f, g in spec.get("risers", []):
        y = load(SFX / f); t0, t1 = tm(t0), tm(t1); need = int((t1 - t0) * SR)
        y = y[-need:] if len(y) > need else y
        place(sfx, y, t1 - len(y) / SR, g); used.add(f)
    vo = load(a.vo); voice = np.zeros((n, 2), np.float32); voice[:min(n, len(vo))] = vo[:n]

    def lufs(path):
        o = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        return float(re.findall(r"I:\s+([-\d.]+) LUFS", o)[-1]), float(re.findall(r"Peak:\s+([-\d.]+) dBFS", o)[-1])

    def master(parts, name):
        raw = OUT / f"{name}_raw.wav"; sf.write(str(raw), sum(parts).astype(np.float32), SR, subtype="FLOAT")
        I, _ = lufs(raw)
        mp4 = OUT / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.video, "-i", str(raw), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-af", f"volume={a.target - I:.2f}dB,alimiter=limit=0.84:level=false", "-c:a", "aac", "-b:a", "256k",
                        "-ar", "48000", "-shortest", str(mp4)], check=True)
        return (mp4,) + lufs(mp4)

    rep = ["# SOUND.md", ""]
    parts_a = [voice, sfx]
    if a.music:
        y_m = load(a.music); mono = y_m.mean(1)
        tempo, bf = librosa.beat.beat_track(y=mono, sr=SR)
        beats = librosa.frames_to_time(bf, sr=SR)
        period = float(np.median(np.diff(beats)))
        k = np.round((beats - beats[0]) / period)
        period, phase = np.polyfit(k, beats, 1)             # librosa drops beats in breaks: fit one uniform grid
        beats = phase + period * np.arange(0, int(len(mono) / SR / period) + 2)
        hard = [tm(x) for x in a.hard.split(",") if x.strip()]
        best = (0.0, 0.0)
        if hard:
            best = None
            for s0 in np.arange(0.0, max(0.005, len(mono) / SR - a.dur), 0.005):   # every start that fits the reel
                e = float(np.mean([np.min(np.abs((beats - s0) - h)) for h in hard]))
                if best is None or e < best[0]:
                    best = (e, s0)
        mstart = float(best[1])
        music = y_m[int(mstart * SR):int(mstart * SR) + n]
        music = np.vstack([music, np.zeros((n - len(music), 2), np.float32)]) if len(music) < n else music
        env = uniform_filter1d(np.abs(voice.mean(1)), int(0.05 * SR))
        act = maximum_filter1d((env > 10 ** (-42 / 20)).astype(np.float32), int(0.30 * SR))
        act = uniform_filter1d(act, int(0.08 * SR))
        gain_db = -10 - 12 * act
        tt = np.arange(n) / SR
        for t0, t1, d in spec.get("dips", []):
            gain_db = np.where((tt > tm(t0)) & (tt < tm(t1)), gain_db + d, gain_db)
        for c, w, d in spec.get("swells", []):
            gain_db = gain_db + d * np.clip(1 - np.abs(tt - tm(c)) / w, 0, 1)
        fade = np.clip(tt / 0.25, 0, 1) * np.clip((a.dur - tt) / 1.0, 0, 1)
        parts_a = [voice, sfx, music * (10 ** (gain_db / 20) * fade)[:, None]]
        resid = ", ".join(f"{h:.2f}s={float(np.min(np.abs((beats - mstart) - h))) * 1000:.0f}ms" for h in hard)
        rep += [f"Music: {a.music_credit}. Starts {mstart:.3f} s into the track.",
                f"Tempo {float(np.atleast_1d(tempo)[0]):.1f} BPM (beat {period:.3f} s). Cut-to-beat error: {resid or 'n/a'}"]
    A = master(parts_a, "master_A_music" if a.music else "master")
    rep.append(f"Master {'A (music)' if a.music else ''}: {A[1]:.1f} LUFS integrated, true peak {A[2]:.1f} dBFS -> {A[0].name}")
    if a.music:
        B = master([voice, sfx], "master_B_no_music")
        rep.append(f"Master B (no music): {B[1]:.1f} LUFS, true peak {B[2]:.1f} dBFS -> {B[0].name}")
    rep += ["", "SFX used (from the sound-effects library; check its LICENSES.md):"] + [f"- {u}" for u in sorted(used)]
    (OUT / "SOUND.md").write_text("\n".join(rep), encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
