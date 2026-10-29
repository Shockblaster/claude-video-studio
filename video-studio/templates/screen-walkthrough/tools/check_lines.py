"""check_lines.py FILE [FILE ...] : transcribe a few voiceover lines (relative to assets/vo)."""
import sys
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
model = WhisperModel("small.en", device="cpu", compute_type="int8")
for name in sys.argv[1:]:
    segs, _ = model.transcribe(str(ROOT / "assets" / "vo" / name), beam_size=5, language="en")
    print(name, "|", " ".join(s.text for s in segs).strip())
