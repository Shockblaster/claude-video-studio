"""Synthesise a soft lo-fi bed (keys, sub bass, brushed drums) as assets/music.wav. No samples, no licences."""
import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parent.parent
SR = 44100
total = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))["total"]
rng = np.random.default_rng(7)

BPM = 82
beat = 60 / BPM
bar = beat * 4
n = int((total + 1) * SR)
out = np.zeros((n, 2), dtype=np.float64)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def place(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= n:
        return
    sig = sig[: n - i] * gain
    out[i:i + len(sig), 0] += sig * (1 - max(0, pan))
    out[i:i + len(sig), 1] += sig * (1 + min(0, pan))


def keys(m, dur):
    """Soft electric-piano-ish tone: a few sine partials with a gentle tine and slow decay."""
    t = np.arange(int(dur * SR)) / SR
    f = midi(m)
    env = (1 - np.exp(-t * 60)) * np.exp(-t * 0.55)
    tone = np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 2.5) + 0.08 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 6)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)
    return tone * env * trem


def bass(m, dur):
    t = np.arange(int(dur * SR)) / SR
    env = (1 - np.exp(-t * 80)) * np.exp(-t * 0.9)
    return np.sin(2 * np.pi * midi(m) * t) * env


def kick():
    t = np.arange(int(0.35 * SR)) / SR
    f = 52 + 70 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


def hat(dur=0.06):
    s = rng.standard_normal(int(dur * SR))
    s = sosfilt(butter(4, 7000, "hp", fs=SR, output="sos"), s)
    return s * np.exp(-np.arange(len(s)) / SR * 70)


def snare():
    t = np.arange(int(0.25 * SR)) / SR
    s = sosfilt(butter(2, [1500, 6000], "bp", fs=SR, output="sos"), rng.standard_normal(len(t)))
    return (s * 0.8 + 0.3 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 18)


# Am9 - Fmaj7 - Cmaj7 - G6, two bars each (warm, unhurried).
chords = [(45, [57, 60, 64, 67, 71]), (41, [57, 60, 64, 65]), (48, [55, 59, 64, 67]), (43, [55, 59, 62, 64])]
K, H, S = kick(), hat(), snare()
t, i = 0.0, 0
while t < total + 1:
    root, notes = chords[i % len(chords)]
    for b in range(2):
        t0 = t + b * bar
        for j, m in enumerate(notes):  # gently strummed
            place(keys(m, bar * 1.6), t0 + j * 0.018, pan=(j - len(notes) / 2) * 0.12, gain=0.11)
        place(bass(root - 12 + 12, bar), t0, gain=0.28)
        place(bass(root - 12 + 12 + 7, beat * 1.5), t0 + beat * 2.5, gain=0.16)
        for q in range(4):
            if q in (0, 2):
                place(K, t0 + q * beat, gain=0.42)
            if q in (1, 3):
                place(S, t0 + q * beat, gain=0.11, pan=0.1)
            for e in range(2):  # swung eighths
                place(H, t0 + q * beat + e * beat * 0.58, pan=-0.3, gain=0.05 if e else 0.07)
    t += 2 * bar
    i += 1

# Warmth: low-pass the whole mix, add faint tape hiss, fade in and out.
out = sosfilt(butter(2, 5200, "lp", fs=SR, output="sos"), out, axis=0)
out += rng.standard_normal(out.shape) * 0.0015
fade_in, fade_out = int(2.5 * SR), int(5 * SR)
env = np.ones(n)
env[:fade_in] = np.linspace(0, 1, fade_in)
end = int(total * SR)
env[end - fade_out:end] = np.linspace(1, 0, fade_out)
env[end:] = 0
out *= env[:, None]
out = out[:end] / (np.abs(out).max() + 1e-9) * 0.8

with wave.open(str(ROOT / "assets" / "music.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((out * 32767).astype(np.int16).tobytes())
print("music", round(len(out) / SR, 1), "s")
