# Screen walkthrough template (16:9 how-to guide for a web app)

A narrated walkthrough built from REAL screenshots of the app: a browser frame that pans and zooms to the part
being talked about, rings that pop on the words that name them, a cursor that travels and clicks, left-column
points that appear as they are said, sentence subtitles, and a chapter lane showing the real voice waveform with a
playhead. Optional: one short clip per chapter. Proven on a ~4.5 min ops guide (16 scenes, ~60 captures).

## Folder
```
script.json          voice, speed, brand, url, chip, "say" respellings, chapters (id, label, color), scenes (id, chapter, title, lines)
capture/lib.js       helpers prepended to every capture step (shot(), rect(), boxes)
capture/wrap.py      wrap.py STEP --base http://127.0.0.1:3000  ->  capture/run/STEP.js for the Playwright MCP
capture/steps/       one JS file per scene: navigate, act, shot('name', {mark: () => locator})
tools/tts.py         one Kokoro WAV per line + timeline.json (exact starts)
tools/mix_vo.py      every line at its start in assets/vo-full.wav
tools/check_vo.py    transcribe the whole voice with faster-whisper and list the worst-matching lines
tools/check_lines.py transcribe a few lines (for testing respellings)
tools/prep.py        light JPEG copies of the captures for the video
tools/music.py       a synthesised soft lo-fi bed (no samples, no licence question)
tools/build.py       ENGINE (generic) + SCENES (one block per scene: edit these) -> index.html
tools/mux.py         voice + ducked music to -16 LUFS onto the silent render
tools/clips.py       one clip per chapter with soft fades
tools/style.css      the look; swap the palette for the product's own
fonts.css + assets/fonts/   Archivo, IBM Plex Mono, Instrument Serif (OFL, licences included)
```

## Steps
1. **Script**: copy `script.example.json` to `script.json`. Short spoken lines, one idea each. Respell what the
   TTS says wrong in `say` (captions keep the real text). Pick the voice and speed by ear with the user.
2. **Captures** (the app running locally, logged in inside the Playwright MCP browser):
   - per scene: `python -I capture/wrap.py s02 --base http://127.0.0.1:3000`, then pass `capture/run/s02.js` to the
     MCP's run-code tool;
   - after the last step, save `window.__boxes` with the MCP's evaluate tool to `assets/shots/boxes.json`;
   - captures are 1600x900 CSS at device scale 2. A full-page capture taller than 16,384 device px repeats the
     top of the page, so capture tall pages in slices and stitch.
   - Use made-up test data and say so on screen (the `chip`).
3. `python -I tools/prep.py`
4. **Voice**: `HYPERFRAMES_PYTHON` must point at a Python with `kokoro-onnx` and `soundfile`. Then:
   - `python -I -X utf8 tools/tts.py` (add `--force` to redo all lines);
   - `python -I tools/mix_vo.py`, then `python -I tools/check_vo.py`, and fix any line that reads back wrong;
   - `python -I tools/music.py`.
5. **Build**: write one scene block per scene in `tools/build.py`, then `python -I tools/build.py`.
6. **Check**:
   - `npx hyperframes check --json` (the lane's small muted labels raise 2 contrast warnings; darken
     `--muted` if you want them gone);
   - `npx hyperframes snapshot --at <s>,<s> --timeout 60000`, and read every snapshot.
7. **Render**:
   - `npx hyperframes render -o renders/video-silent.mp4 --fps 30 --workers 1`;
   - `python -I tools/mux.py --name my-guide`;
   - optionally `python -I tools/clips.py --name my-guide --skip intro`.

## Rules that came from real reviews
- Whisper-check every line before building. One bad respelling ruins a sentence.
- A ring appears exactly on the word that names the thing, never before it.
- Zoom a touch closer than feels necessary: viewers watch on laptops, and 1600 px of UI in a 1120 px frame
  reads small.
- A box wider than the window lines up on its left edge (centring cut off the start of every line).
- The capture tab can close on its own when memory is low; the browser context keeps the login.
