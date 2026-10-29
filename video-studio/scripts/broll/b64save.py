"""Decode Playwright `browser_evaluate(..., filename=X.b64)` results into real files.

    python b64save.py assets/chatgpt/*.b64 assets/video_raw/*.b64

Why this exists: on 2026-09-30 every `<a download>` + `waitForEvent('download')` +
`saveAs()` in the Playwright MCP closed the whole browser ("Target page, context or
browser has been closed"). The route that works: fetch the image/video INSIDE the page,
return it as base64 from `browser_evaluate` with its `filename` parameter (the MCP writes
the result to disk), then decode here. Images keep their real format; videos are
reported with ffprobe (expect h264 1280x720, 10.0 s from Gemini).
"""
import base64, io, json, os, subprocess, sys

for f in sys.argv[1:]:
    raw = open(f, encoding="utf-8").read().strip()
    if raw.startswith('"'):
        raw = json.loads(raw)
    if raw.startswith(("PENDING", "ERR")):
        print(f, raw[:200]); continue
    data = base64.b64decode(raw)
    head = data[:12]
    if head[4:8] == b"ftyp":
        out = os.path.splitext(f)[0] + ".mp4"
        open(out, "wb").write(data)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration:stream=width,height,codec_name", "-of", "csv=p=0", out],
                           capture_output=True, text=True)
        info = p.stdout.split()
    else:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        out = os.path.splitext(f)[0] + {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(im.format, ".bin")
        open(out, "wb").write(data)
        info = [im.size, im.mode]
    os.remove(f)
    print(out, os.path.getsize(out), *info)
