"""check_lines.py FILE [FILE ...] : transcribe a few voiceover lines (relative to assets/vo)."""
import subprocess
import sys
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
model = WhisperModel("small.en", device="cpu", compute_type="int8")
for name in sys.argv[1:]:
    segs, _ = model.transcribe(load16k(ROOT / "assets" / "vo" / name), beam_size=5, language="en")
    print(name, "|", " ".join(s.text for s in segs).strip())
