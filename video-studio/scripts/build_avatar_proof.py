#!/usr/bin/env python3
"""Build a HyperFrames project from templates/cartoon-avatar: voice + mouth cues + captions.

  python -I build_avatar_proof.py VOICE.wav OUT_DIR --captions "line one|line two|line three"
         [--cues mouth.json] [--fonts <VIDEO_STUDIO_HOME>/assets/fonts]

Without --cues it runs mouth_from_audio.py on the voice. Captions are spread across the
voice by character count (approximate; replace with word timestamps when whisper.cpp is
installed). Wrap a word in *stars* to highlight it.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "templates" / "cartoon-avatar" / "index.html"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def captions_html(lines, vo_dur):
    total = sum(len(l) for l in lines) or 1
    t, rows = 0.0, []
    for i, line in enumerate(lines):
        d = vo_dur * len(line) / total
        text = re.sub(r"\*(.+?)\*", r"<b>\1</b>", line)
        rows.append(f'      <div id="cap{i + 1}" class="clip cap" data-start="{t:.2f}" data-duration="{d:.2f}" '
                    f'data-track-index="2"><span>{text}</span></div>')
        t += d
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("voice")
    ap.add_argument("out")
    ap.add_argument("--captions", required=True, help="caption groups separated by |")
    ap.add_argument("--cues")
    ap.add_argument("--fonts", default=str(_paths.fonts_dir()))
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    (out / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy(a.voice, out / "assets" / "vo.wav")
    for f in ("Mukta-SemiBold.ttf", "Mukta-ExtraBold.ttf"):
        shutil.copy(pathlib.Path(a.fonts) / f, out / "assets" / "fonts" / f)

    cues_path = a.cues or str(out / "mouth.json")
    if not a.cues:
        subprocess.run([sys.executable, "-I", str(HERE / "mouth_from_audio.py"), a.voice, "-o", cues_path], check=True)
    cues = json.loads(pathlib.Path(cues_path).read_text(encoding="utf-8"))

    vo = duration(a.voice)
    total = round(vo + 0.6, 2)
    html = TEMPLATE.read_text(encoding="utf-8")
    html = (html.replace("{{DURATION}}", str(total))
                .replace("{{VO_DURATION}}", f"{vo:.2f}")
                .replace("{{CARD_DURATION}}", f"{total - 2.0:.2f}")
                .replace("{{CAPTIONS}}", captions_html(a.captions.split("|"), vo))
                .replace("{{CUES_JSON}}", json.dumps(cues, ensure_ascii=False)))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({"ok": True, "project": str(out), "duration": total, "cues": len(cues["mouthCues"])}))


if __name__ == "__main__":
    sys.exit(main())
