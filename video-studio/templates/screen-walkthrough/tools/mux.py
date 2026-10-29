"""Mix voice + ducked music to -16 LUFS, then add it to the silent render (works on macOS, Linux, Windows).
  python -I tools/mux.py [--name my-guide]   ->  renders/<name>.mp4"""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("--name", default="guide"); a = ap.parse_args()
fc = ("[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,"
      "asplit=2[vo][key];[1:a]aresample=48000,volume=0.22[m];[m][key]sidechaincompress=threshold=0.015:ratio=6:attack=30:release=500[md];"
      "[vo][md]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=11[out]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ROOT / "assets/vo-full.wav"), "-i", str(ROOT / "assets/music.wav"),
                "-filter_complex", fc, "-map", "[out]", "-ar", "48000", "-c:a", "pcm_s16le", str(ROOT / "assets/mix.wav")], check=True)
dst = ROOT / "renders" / f"{a.name}.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ROOT / "renders/video-silent.mp4"), "-i", str(ROOT / "assets/mix.wav"),
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart",
                str(dst)], check=True)
print(dst)
