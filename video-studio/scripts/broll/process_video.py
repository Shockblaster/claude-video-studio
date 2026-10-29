"""Turn a raw AI-generated clip (Gemini / Veo) into a deck-ready background loop.

    python process_video.py raw.mp4 out.mp4            # scrub + loop + poster
    python process_video.py raw.mp4 out.mp4 --no-scrub # clip has no watermark
    python process_video.py raw.mp4 out.mp4 --crop     # crop the mark out (scrub left a ghost)
    python process_video.py --dir assets/video_raw assets/video

Per clip:
1. Remove the Gemini/Veo sparkle watermark (scrub_mark.py). Only valid for
   1280x720 clips from that generator: the mark is static and in a fixed place.
2. Seamless loop: crossfade the last XF seconds into the first. Output is L-XF
   seconds long and its last frame flows into its first.
3. Strip audio (decks play muted), H.264 yuv420p, CRF 20, +faststart.
   10 s of 720p lands at 2-4 MB.
4. Write <out>_poster.png = the processed clip's first frame. Use it as the
   movie's poster so a paused or failed video shows exactly where the loop starts.

Raw files are never modified. Needs ffmpeg/ffprobe on PATH (or FFMPEG_BIN env).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
XF = 1.0


def _bin(name):
    found = shutil.which(name)
    if found:
        return found
    d = os.environ.get("FFMPEG_BIN")
    if d and os.path.exists(os.path.join(d, name + ".exe")):
        return os.path.join(d, name + ".exe")
    # winget's default install location on this machine family
    base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(base):
        for root, _dirs, files in os.walk(base):
            if name + ".exe" in files:
                return os.path.join(root, name + ".exe")
    sys.exit(f"{name} not found: install ffmpeg or set FFMPEG_BIN")


FFMPEG, FFPROBE = _bin("ffmpeg"), _bin("ffprobe")


def duration(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=duration", "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def process(src, dst, scrub=True, crop=False, center=False):
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    clean = dst[:-4] + "._clean.mp4"
    if crop:
        # The sparkle's bounding box is x 1135-1192, y 575-624 (from the alpha map). A
        # 1120x630 window from the left edge excludes it with a 15 px margin for the codec's
        # ringing, so nothing needs repairing. Used when the scrub leaves a ghost: a nearly
        # static background under the mark (a floor stripe that never moves) defeats the
        # per-clip alpha estimate, because the background term no longer averages out.
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src, "-vf",
                        # --crop-center keeps the frame centred (symmetric plates): the mark
                        # starts at row 575, so a 1000x562 window from the top clears it.
                        ("crop=1000:562:140:0" if center else "crop=1120:630:0:45")
                        + ",scale=1280:720:flags=lanczos", "-an", "-c:v", "libx264",
                        "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", clean], check=True)
    elif scrub:
        import scrub_mark
        scrub_mark.scrub_file(FFMPEG, src, clean)
    else:
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src, "-an", "-c:v", "libx264", "-crf", "14",
                        "-preset", "veryfast", "-pix_fmt", "yuv420p", clean], check=True)
    L = duration(clean)
    subprocess.run([
        FFMPEG, "-y", "-v", "error", "-i", clean, "-filter_complex",
        f"[0:v]split[a][b];[a]trim=start={XF},setpts=PTS-STARTPTS[main];"
        f"[b]trim=0:{XF},setpts=PTS-STARTPTS[head];"
        f"[main][head]xfade=transition=fade:duration={XF}:offset={L - 2 * XF:.3f},format=yuv420p[out]",
        "-map", "[out]", "-an", "-c:v", "libx264", "-crf", "20", "-preset", "slow",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst], check=True)
    poster = dst[:-4] + "_poster.png"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", dst, "-frames:v", "1", poster], check=True)
    os.remove(clean)
    print(f"{os.path.basename(dst)}: {duration(dst):.2f}s  {os.path.getsize(dst) / 1e6:.1f} MB  poster {os.path.basename(poster)}")
    return dst, poster


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    scrub = "--no-scrub" not in sys.argv
    crop = "--crop" in sys.argv or "--crop-center" in sys.argv
    center = "--crop-center" in sys.argv
    if "--dir" in sys.argv:
        raw, out = args
        for f in sorted(os.listdir(raw)):
            if f.endswith(".mp4"):
                process(os.path.join(raw, f), os.path.join(out, f), scrub)
    elif len(args) == 2:
        process(args[0], args[1], scrub, crop, center)
    else:
        sys.exit(__doc__)
