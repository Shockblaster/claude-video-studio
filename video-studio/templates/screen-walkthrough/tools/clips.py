"""Cut one short clip per chapter from the finished guide, at the chapter edges in timeline.json, with soft fades.
  python -I tools/clips.py --name my-guide [--skip intro,rules]"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("--name", default="guide"); ap.add_argument("--skip", default="")
a = ap.parse_args()
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
full = ROOT / "renders" / f"{a.name}.mp4"
out = ROOT / "renders" / "clips"; out.mkdir(parents=True, exist_ok=True)
skip = set(x for x in a.skip.split(",") if x)
for n, ch in enumerate(c for c in tl["chapters"] if c["id"] not in skip):
    scenes = [s for s in tl["scenes"] if s["chapter"] == ch["id"]]
    if not scenes:
        continue
    st, en = max(0.0, scenes[0]["start"] - 0.3), scenes[-1]["end"] + 0.2
    d = en - st
    dst = out / f"{n + 1}-{re.sub(r'[^a-z0-9]+', '-', ch['label'].lower()).strip('-')}.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-i", str(full), "-t", f"{d:.3f}",
        "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={d - 0.5:.3f}:d=0.5",
        "-af", f"afade=t=in:st=0:d=0.3,afade=t=out:st={d - 0.5:.3f}:d=0.5",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(dst)], check=True)
    print(dst.name, f"{d:.1f} s")
