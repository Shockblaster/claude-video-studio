"""Transcribe the finished voice with faster-whisper and compare it with the script, line by line."""
import difflib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from faster_whisper import WhisperModel


def load16k(path):
    """16 kHz mono float32 via ffmpeg. faster-whisper 1.2.1 decodes files with PyAV and passes
    metadata_errors=, which the installed PyAV 19 rejects (TypeError); handing it an array skips PyAV."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
model = WhisperModel("small.en", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower().replace("’", "'")).split()  # noqa: E731
worst = []
for s in tl["scenes"]:
    for ln in s["lines"]:
        segs, _ = model.transcribe(load16k(ROOT / ln["file"]), beam_size=5, language="en")
        heard = " ".join(x.text for x in segs).strip()
        r = difflib.SequenceMatcher(None, norm(ln["text"]), norm(heard)).ratio()
        worst.append((r, ln["text"], heard))
worst.sort()
print("lines", len(worst), "mean match", round(sum(r for r, *_ in worst) / len(worst), 3))
for r, said, heard in worst[:8]:
    print(f"{r:.2f} | SCRIPT: {said}\n     | HEARD:  {heard}")
