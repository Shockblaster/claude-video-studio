#!/usr/bin/env python3
"""ORIGINAL SCORE FROM THE TIMELINE: music written on the reel's own beat grid, so every downbeat, accent and hit
lands on its cue by construction (0 ms). Real recorded instruments through lemo-opuscar's sampler (MIT code,
github.com/lemomo-ai/lemo-opuscar) and CC0 / CC BY sample libraries (VSCO 2 CE, VCSL, FreePats CC0; Salamander piano
CC BY 3.0 and MuldjordKit drums CC BY 4.0 need the credit line this script writes). 2026-11-01.

Run with the AUDIO venv (soxr):
  <AUDIO venv python (scripts/_paths.py audio_python())> score.py --timeline timeline.json --cues cues.json \
      --out music/ [--style pop|calm|cinematic] [--key C] [--minor] [--prog "I V vi IV"] [--seed 7]

timeline.json: from beatgrid.py (authored --bpm / --fit-bpm). cues.json: the reel's cues; the score reads:
  role hit / drop / type reveal  -> a hit on that beat (crash + kick + low octave), drums stop for the 2 beats before
  role whoosh.long / swell       -> a reverse-cymbal-style swell (sus_cymbal cresc) ending on the cue
  lock beat / anchor             -> an accent (clap + open hat) on that beat
Styles: pop (drums, bass, piano chords, marimba motif), calm (shaker, soft kick, vibraphone pads, glock motif),
cinematic (low strings, timpani, toms on hits, horn swells). Loop-friendly: the last bar resolves on the tonic.
Writes out/music.wav (48 kHz stereo), out/stems/*.wav, out/score.json (every event), out/CREDITS_music.txt.
"""
import argparse
import json
import pathlib
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402
OPUS = _paths.opuscar_dir()
sys.path.insert(0, str(OPUS))
from core.audio import sampler as S  # noqa: E402
from core.audio.sfx import SR, add  # noqa: E402

NOTES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
         "A": 9, "A#": 10, "Bb": 10, "B": 11}
DEG = {"I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11}


def chord_of(sym, key, minor):
    """roman numeral -> (root midi class, intervals). Upper case = major, lower = minor; diatonic in the key."""
    up = sym.upper().rstrip("7")
    scale = [0, 2, 3, 5, 7, 8, 10] if minor else [0, 2, 4, 5, 7, 9, 11]
    idx = ["I", "II", "III", "IV", "V", "VI", "VII"].index(up)
    root = (key + scale[idx]) % 12
    q = [0, 3, 7] if sym[0].islower() else [0, 4, 7]
    if sym.endswith("7"):
        q = q + [10]
    return root, q


def voicing(root, q, lo=60):
    """close voicing in the octave from lo, nearest to middle C"""
    ps = sorted(((root + i) % 12) + lo for i in q)
    return [p if p < lo + 12 else p - 12 for p in ps]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--cues")
    ap.add_argument("--out", required=True)
    ap.add_argument("--style", default="pop", choices=["pop", "calm", "cinematic"])
    ap.add_argument("--key", default="C")
    ap.add_argument("--minor", action="store_true")
    ap.add_argument("--prog", default=None, help='roman numerals per bar, e.g. "I V vi IV" (default by style)')
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--low-target", type=float, default=-3.0,
                    help="20-120 Hz energy relative to everything above, dB (lemo-opuscar TECHNIQUE.md: about -3; synthetic and "
                         "sampled scores drift bass-heavy, which wastes phone-speaker headroom)")
    a = ap.parse_args()
    S.seed(a.seed)
    rng = np.random.default_rng(a.seed)
    tl = json.loads(pathlib.Path(a.timeline).read_text())
    cues = json.loads(pathlib.Path(a.cues).read_text()) if a.cues else []
    beats = np.array(tl["beats"])
    B = tl["beat_s"]
    meter = tl.get("meter", 4)
    dur = tl["dur"]
    downs = np.array(tl["downbeats"]) if tl.get("downbeats") else beats[::meter]
    # bar index of every beat, beat-in-bar position (0 = downbeat); beats before the first downbeat are a pickup
    pos = np.array([int(round((b - downs[0]) / B)) % meter for b in beats])
    bar = np.array([int(np.floor((b - downs[0]) / (meter * B) + 1e-6)) for b in beats])
    key = NOTES[a.key]
    prog = (a.prog or {"pop": "I V vi IV", "calm": "I vi IV V", "cinematic": "i VI III VII" if a.minor else "vi IV I V"}[a.style]).split()
    minor = a.minor

    def near(t):
        return int(np.argmin(np.abs(beats - t)))

    hits = sorted({near(c["t"]) for c in cues if c.get("role") in ("hit", "drop") or c.get("type") == "reveal"})
    swells = sorted({near(c["t"]) for c in cues if c.get("role") in ("whoosh.long", "swell")})
    accents = sorted({near(c["t"]) for c in cues if c.get("lock") in ("beat", "anchor")} - set(hits))
    quiet = set()                                    # drums rest the 2 beats before a hit (the stop-down)
    for h in hits:
        quiet |= {h - 1, h - 2}

    N = int(round((dur + 2.5) * SR))
    STEMS = ["drums", "bass", "keys", "motif", "hits"]
    bus = {k: np.zeros((N, 2), np.float32) for k in STEMS}
    subbus = np.zeros((N, 2), np.float32)        # hit subs: added AFTER the low-end balance (it would flatten them)
    used = set()
    ev = []

    def put(stem, t, inst, pitch, d, vel, pan=0.0, gain=1.0, kind="note"):
        if t < 0 or t > dur + 0.05:
            return
        used.add(inst)
        x = S.hit(inst, pitch, vel, d) if kind == "hit" else S.note(inst, pitch, d, vel)
        add(bus[stem], x, t, gain, pan)
        ev.append({"t": round(float(t), 4), "stem": stem, "inst": inst, "pitch": pitch if isinstance(pitch, (str, type(None))) else int(pitch),
                   "dur": round(float(d or 0), 3), "vel": round(float(vel), 2)})

    nb = len(beats)
    last_down = int(np.flatnonzero(pos == 0)[-1]) if (pos == 0).any() else nb - 1
    for i, t in enumerate(beats):
        p, br = pos[i], bar[i]
        sym = prog[br % len(prog)] if br >= 0 else prog[-1]
        if i >= last_down:
            sym = "i" if minor else "I"                  # the last bar resolves home (loop-friendly)
        root, q = chord_of(sym, key, minor)
        v = rng.uniform(0.9, 1.0)
        intro = br < 0 or (br == 0 and a.style != "calm" and not hits[:1] == [i])
        # ---------------- drums / pulse
        if i not in quiet:
            if a.style == "pop":
                if p in (0, 2) and not (br < 0):
                    put("drums", t, "drum_kit", "kick_drum_left", None, 0.85 * v, 0, 0.9, "hit")
                if p in (1, 3) and br >= 0:
                    put("drums", t, "drum_kit", "snare_1", None, 0.62 * v, 0.05, 0.7, "hit")
                for k in (0, 0.5):
                    put("drums", t + k * B, "hihat", "closed", None, (0.42 if k == 0 else 0.3) * v, 0.45, 0.5, "hit")
                if p == 2 and rng.random() < 0.35 and br >= 0:
                    put("drums", t + 0.5 * B, "drum_kit", "kick_drum_left", None, 0.55, 0, 0.7, "hit")
            elif a.style == "calm":
                if p == 0:
                    put("drums", t, "kick", None, None, 0.45 * v, 0, 0.6, "hit")
                put("drums", t + 0.5 * B, "shaker", "down", None, 0.35 * v, 0.45, 0.45, "hit")
            else:
                if p == 0:
                    put("drums", t, "timpani", "drum1", None, 0.5 * v, 0, 0.6, "hit")
        # ---------------- bass (roots; pop: on 1 and the and of 2; calm/cinematic: whole bar)
        bass_root = 36 + root if 36 + root <= 47 else 24 + root
        if a.style == "pop":
            if p == 0:
                put("bass", t, "electric_bass", bass_root, 1.4 * B, 0.75, -0.05)
            if p == 1:
                put("bass", t + 0.5 * B, "electric_bass", bass_root, 0.45 * B, 0.6, -0.05)
            if p == 2:
                put("bass", t, "electric_bass", bass_root + 12 if rng.random() < .3 else bass_root, 0.9 * B, 0.65, -0.05)
        elif p == 0:
            put("bass", t, "cellos" if a.style == "cinematic" else "electric_bass", bass_root + (12 if a.style == "cinematic" else 0),
                meter * B * 0.98, 0.55, -0.1)
        # ---------------- harmony
        if p == 0:
            vc = voicing(root, q, 60)
            inst = {"pop": "piano", "calm": "vibraphone", "cinematic": "violins"}[a.style]
            for j, n in enumerate(vc):
                put("keys", t + j * 0.012, inst, n, meter * B * 0.95, 0.42 if a.style != "cinematic" else 0.35, -0.55 + 0.55 * j, 0.6)
        # ---------------- motif: an arpeggio on chord tones (pop 8ths on marimba, calm quarters on glock)
        if br >= 0 or a.style == "calm":
            tones = sorted(((root + x) % 12) + 72 for x in q)
            if a.style == "pop":
                for k, off in enumerate((0, 0.5)):
                    n = tones[(2 * p + k) % len(tones)] + (12 if (2 * p + k) % 7 == 6 else 0)
                    put("motif", t + off * B, "marimba", n, 0.45 * B, 0.38 if k else 0.48, 0.5 if k else -0.35, 0.55)
            elif a.style == "calm" and p in (0, 2):
                put("motif", t, "glockenspiel", tones[(p // 2 + br) % len(tones)] + 12, B, 0.3, 0.5 if br % 2 else -0.5, 0.4)
        # ---------------- accents and hits
        if i in accents:
            put("hits", t, "claps", "group", None, 0.5, 0.1, 0.5, "hit")
            put("hits", t, "hihat", "open", None, 0.4, 0.3, 0.45, "hit")
        if i in hits:
            put("hits", t, "sus_cymbal", "hit", None, 0.75, 0.15, 0.7, "hit")
            put("hits", t, "drum_kit" if a.style == "pop" else "gran_cassa", "kick_drum_left" if a.style == "pop" else "hit",
                None, 0.95, 0, 1.0, "hit")
            put("hits", t, "piano" if a.style != "cinematic" else "cellos", 36 + root, 2.5 * B, 0.7, -0.1, 0.8)
            if a.style == "cinematic":
                put("hits", t, "toms", "low_mallet", None, 0.8, 0, 0.8, "hit")
    # sub layer under hits: a sine at the chord root two octaves down (~37-62 Hz), pitch dropping a little,
    # 0.9 s exp decay with 2nd/3rd harmonics so it still speaks on phone speakers (opuscar TECHNIQUE.md §5)
    sub_beats = [(h, 0.55, 0.32) for h in hits]
    if a.style in ("pop", "cinematic"):          # an 808-style sub on every bar's downbeat, softer and shorter
        sub_beats += [(i, 0.32, 0.22) for i in range(nb) if pos[i] == 0 and bar[i] >= 0 and i not in hits and i not in quiet]
    for h, amp, tau in sub_beats:
        t = float(beats[h])
        sym = prog[bar[h] % len(prog)] if bar[h] >= 0 else prog[-1]
        r0, _ = chord_of(sym, key, minor)
        f0 = 440 * 2 ** (((24 + r0) - 69) / 12)
        while f0 < 36:
            f0 *= 2
        n = int(1.1 * SR); tt = np.arange(n) / SR
        f = f0 * (1.12 - 0.12 * np.exp(-tt / 0.08))
        ph = 2 * np.pi * np.cumsum(f) / SR
        sub = (np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)) * np.exp(-tt / tau) * np.minimum(1, tt / 0.004)
        add(subbus, (amp * sub).astype(np.float32), t, 1.0, 0.0)
        ev.append({"t": round(t, 4), "stem": "hits", "inst": "sub_sine", "pitch": round(f0, 1), "dur": 1.1, "vel": amp})
    for s in swells:
        t = beats[s]
        put("hits", max(0.0, t - 2 * B), "sus_cymbal", "cresc", 2 * B, 0.6, -0.15, 0.6, "hit")

    # ---------------- final: ring out on the tonic, light room, gentle bus balance
    mix = np.zeros((N, 2), np.float32)
    gains = {"drums": 1.0, "bass": 0.9, "keys": 0.75, "motif": 0.6, "hits": 0.9}
    out = pathlib.Path(a.out); (out / "stems").mkdir(parents=True, exist_ok=True)
    for k in STEMS:
        y = S.room(bus[k], size=0.45 if k != "drums" else 0.22, mix=0.24 if k in ("keys", "motif") else (0.16 if k != "drums" else 0.08),
                   seed_=STEMS.index(k) + 3)
        bus[k] = y * gains[k]
        mix += bus[k]
    # ---------------- low-end balance: zero-phase complementary split at 120 Hz, low band set to --low-target
    from scipy.signal import butter, sosfiltfilt, welch
    sos = butter(2, 120, "low", fs=SR, output="sos")

    def low_rest(x):
        f, P = welch(x.mean(1), SR, nperseg=8192)
        return 10 * np.log10(P[(f >= 20) & (f < 120)].sum() / (P[f >= 120].sum() + 1e-20) + 1e-20)
    lr0 = low_rest(mix)
    low = sosfiltfilt(sos, mix, axis=0).astype(np.float32)
    g_low = 10 ** ((a.low_target - lr0) / 20)
    for _ in range(3):                                    # the split is not band-exact: converge in a few steps
        test = mix - low + low * g_low
        g_low *= 10 ** ((a.low_target - low_rest(test)) / 20)
    mix = mix - low + low * g_low
    for k in STEMS:                                       # stems keep summing to the mix
        lk = sosfiltfilt(sos, bus[k], axis=0).astype(np.float32)
        bus[k] = bus[k] - lk + lk * g_low
    low_after = low_rest(mix)
    # width: mid/side, side x1.6 above 200 Hz (the low end stays mono); a mono voice will sit over this
    hp_sos = butter(2, 200, "high", fs=SR, output="sos")
    mid, side = (mix[:, 0] + mix[:, 1]) / 2, (mix[:, 0] - mix[:, 1]) / 2
    side = side + 0.6 * sosfiltfilt(hp_sos, side)
    mix = np.stack([mid + side, mid - side], 1).astype(np.float32)
    bus["hits"] = bus["hits"] + subbus
    mix = mix + subbus
    n_end = int(round(dur * SR))
    fade = int(0.06 * SR)
    mix = mix[:n_end]
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    for k in STEMS:
        sf.write(out / "stems" / f"{k}.wav", bus[k][:n_end], SR, subtype="FLOAT")
    sf.write(out / "music.wav", mix, SR, subtype="FLOAT")
    cred = S.credits(sorted(used))
    (out / "CREDITS_music.txt").write_text("Original score (scripts/score.py, video-studio), sampler by lemo-opuscar (MIT).\n" + "\n".join(cred) + "\n",
                                          encoding="utf-8")
    (out / "score.json").write_text(json.dumps({"bpm": tl["bpm"], "key": a.key + (" minor" if minor else " major"), "style": a.style,
                                                "prog": prog, "hits": [round(float(beats[h]), 4) for h in hits],
                                                "accents": [round(float(beats[h]), 4) for h in accents],
                                                "instruments": sorted(used), "events": ev}, indent=1))
    print(json.dumps({"ok": True, "low_end_db": [round(float(lr0), 1), round(float(low_after), 1)], "bpm": tl["bpm"], "bars": int(bar.max()) + 1, "events": len(ev), "hits": len(hits),
                      "accents": len(accents), "instruments": sorted(used), "credits_required": [c for c in cred if "CC BY" in c]}))


if __name__ == "__main__":
    main()
