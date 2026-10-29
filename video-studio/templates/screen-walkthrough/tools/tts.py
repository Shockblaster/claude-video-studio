"""Generate one voice-over WAV per script line (Kokoro, local) and write timeline.json with exact timings.
  python -I tools/tts.py [--force]
script.json: {"voice", "speed", "say": {word: how TTS should say it}, "chapters": [...], "scenes": [{id, chapter, title, lines}]}
`say` respellings fix TTS pronunciation ("PDF": "P D F", "AI": "A.I."); captions keep the real text."""
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
script = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
out = ROOT / "assets" / "vo"
out.mkdir(parents=True, exist_ok=True)
NPX = shutil.which("npx.cmd" if sys.platform == "win32" else "npx") or "npx"
ENV = dict(os.environ, HYPERFRAMES_PYTHON=os.environ.get("HYPERFRAMES_PYTHON", sys.executable))

LINE_GAP = 0.35   # pause between lines in a scene
SCENE_GAP = 0.9   # pause between scenes
LEAD_IN = 1.6     # title card before the first word
TAIL = 4.0        # end card after the last word
speed = str(script.get("speed", 1.0))


def spoken(text):
    for k, v in script.get("say", {}).items():
        text = re.sub(rf"\b{re.escape(k)}\b", v, text)
    return text


def length(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


t = LEAD_IN
scenes = []
for s in script["scenes"]:
    start = t
    lines = []
    for i, text in enumerate(s["lines"]):
        wav = out / f"{s['id']}-{i + 1}.wav"
        if not wav.exists() or "--force" in sys.argv:
            for attempt in range(3):          # a line can fail once at random and pass on the rerun
                r = subprocess.run([NPX, "hyperframes", "tts", spoken(text), "-v", script["voice"], "-s", speed, "-o", str(wav)],
                                   cwd=ROOT, capture_output=True, env=ENV)
                if r.returncode == 0 and wav.exists():
                    break
            else:
                raise SystemExit(f"TTS failed for {wav.name}: {r.stdout[-300:]!r} {r.stderr[-300:]!r}")
        d = length(wav)
        lines.append({"text": text, "file": f"assets/vo/{wav.name}", "start": round(t, 3), "duration": round(d, 3)})
        t += d + LINE_GAP
    t += SCENE_GAP - LINE_GAP
    scenes.append({**{k: s[k] for k in ("id", "chapter", "title")}, "start": round(start, 3), "end": round(t, 3), "lines": lines})
    print(s["id"], round(t - start, 1), "s", flush=True)

total = round(t + TAIL - SCENE_GAP, 3)
(ROOT / "timeline.json").write_text(json.dumps({"total": total, "chapters": script["chapters"], "scenes": scenes}, indent=1), encoding="utf-8")
print("total", total)
