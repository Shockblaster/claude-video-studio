"""Lay every voiceover line at its timeline position in one WAV (assets/vo-full.wav)."""
import json
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
SR = 24000
buf = np.zeros(int(tl["total"] * SR) + SR, dtype=np.float32)
for s in tl["scenes"]:
    for line in s["lines"]:
        with wave.open(str(ROOT / line["file"])) as w:
            assert w.getframerate() == SR and w.getnchannels() == 1, (line["file"], w.getframerate())
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        i = int(line["start"] * SR)
        buf[i:i + len(a)] += a
buf = buf[: int(tl["total"] * SR)]
with wave.open(str(ROOT / "assets" / "vo-full.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
print("peak", float(np.abs(buf).max()), "seconds", len(buf) / SR)
