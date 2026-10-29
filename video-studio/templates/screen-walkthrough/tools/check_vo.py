"""Transcribe the finished voice with faster-whisper and compare it with the script, line by line."""
import difflib
import json
import re
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
model = WhisperModel("small.en", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower().replace("’", "'")).split()  # noqa: E731
worst = []
for s in tl["scenes"]:
    for ln in s["lines"]:
        segs, _ = model.transcribe(str(ROOT / ln["file"]), beam_size=5, language="en")
        heard = " ".join(x.text for x in segs).strip()
        r = difflib.SequenceMatcher(None, norm(ln["text"]), norm(heard)).ratio()
        worst.append((r, ln["text"], heard))
worst.sort()
print("lines", len(worst), "mean match", round(sum(r for r, *_ in worst) / len(worst), 3))
for r, said, heard in worst[:8]:
    print(f"{r:.2f} | SCRIPT: {said}\n     | HEARD:  {heard}")
