# AI b-roll with Gemini Omni (optional garnish)

Generated clips are a creative extra, never the backbone. A video must still work if every
AI clip is removed. Quota is scarce (about 4 usable clips a day per account) and a clip can
be refused or come out wrong, so never block a deadline on one.

## When it earns its place
- Real-world texture a code graphic cannot fake: liquid gold pouring, rain on a city at
  night, light through a window, a slow push over coins or paper, smoke, water, fire.
- Mood plates behind kinetic type or a chart (blurred, graded, darkened).
- Not for: people's faces (likeness and trust problems), readable text or numbers (they
  garble), chained physics like dominoes (failed twice), brand logos.

## The flow
Full recipe with every trap: `references/browser-ai.md`. In short:

1. Make the still plate first (ChatGPT image gen via the Playwright MCP),
   in the brand's art direction. Image-to-video on a plate gives far more control than
   text-only.
2. Playwright MCP to `gemini.google.com/u/N/videos` (the user says which N). Click
   "File upload", then `browser_file_upload` the plate.
3. Type the motion prompt (camera locked or one slow move, no text, no faces). **Stop.
   The user presses Send.** They reply "done" / "next".
4. Save in-page: `browser_evaluate` that fetches `video.currentSrc` and returns base64 to a
   file, then `python -I scripts/broll/b64save.py key.b64`.
   Never trigger a download event (it closed the MCP browser once).
5. Clips arrive 1280x720, 24 fps, about 10 s, with audio, with a sparkle watermark at
   bottom right (about x 1135-1193, y 575-624).

## Making a 16:9 clip work in a 9:16 reel
- **Centre 9:16 crop** (405x720 from x=437) misses the watermark entirely, then scales to
  1080x1920. It is soft (2.7x upscale): use it for backgrounds under grain, blur or a
  dark grade, not as a hero shot.
  `ffmpeg -i raw.mp4 -vf "crop=405:720:437:0,scale=1080:1920:flags=lanczos,fps=30" -an clip.mp4`
- **Framed card**: keep it 16:9 inside a rounded card in the middle band, over a blurred
  copy of itself. Scrub the watermark first with
  `python -I scripts/broll/process_video.py raw.mp4 out.mp4 --crop`
  and check with `scripts/broll/check_watermark.py ... --sheet crops.png` (READ the sheet).
- At first use, check whether Omni offers a portrait option. If it does, log it in
  `lessons.md` and prefer it.
- Retime to 30 fps and strip its audio (`-an`). Our own music and SFX go on top.

## Disclosure
Photo-real AI footage gets the platform's AI label (Instagram "AI info", YouTube altered
or synthetic content toggle) when it could be mistaken for real events. Abstract textures
and plates usually do not need it, but the brand pack's compliance notes win.
