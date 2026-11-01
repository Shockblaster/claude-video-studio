# QC gate

A video goes to the user only after this passes. Measured checks first, then eyes.

## 1. Measured
```
npx hyperframes check --json                       # 0 errors, every warning weighed
python -I scripts/qc_reel.py out.mp4 --sheet qc.png --frames 8
```
`qc_reel.py` must print `"pass": true`: 1080x1920, 30/60 fps, h264, yuv420p, AAC, length in
range, -16..-13 LUFS, true peak <= -1 dBTP, frame 0 not black. Optional extras:
mcp-video `sound_qa_loudness`, `video_quality_check`, `shorts_review`,
`video_hook_candidates`.

Pace (added 2026-10-29, from the MAKINGAIDOIT Free Reel Kit):
`python -I scripts/pace_check.py out.mp4 --mask <avatar box> --mask <caption box>`.
- Rule: something behind the avatar changes at least every second, and the first 2 s never
  sit still. Each listed stretch gets a pop, a count, a zoom or a camera move, or is confirmed
  as a deliberate hold (a disclaimer, a key number left to land).
- Example from a real 80 s reel: 17 stretches over 1 s, including the hook's first ~1.2 s and two
  2.4-2.9 s holds. Each next video should beat its predecessor's number.

Beat sync (added 2026-11-01): `python -I scripts/cuecheck.py --timeline timeline.json --cues cues.json` exits 0:
every `beat` and `anchor` event within 1 frame of a beat (test reel: 13 events, mean 4 ms, max 30 ms).
Print its table into the review notes; a reel with music and no timeline.json is not done.

Sound (opuscar TECHNIQUE.md §8 + earshot): `sound/SOUND.md` exists and lists every placement; the 5 "check with
headphones" timestamps go to the user; Whisper reads the FINAL MIX back (music and SFX must not eat a word; an
unknown name is the only allowed miss); `ffmpeg -i out.mp4 -vf blackdetect=d=0.05:pix_th=0.05 -an -f null -`
prints nothing; music low end (20-120 Hz) about -3 dB vs the rest. Optional when nothing else runs:
`earshot critique out.mp4` (scorecard vs pro launch films; evidence, not a verdict).

Reading time (opuscar DIRECTOR.md §7): text that animates in holds at least letters ÷ 15 + 1.5 s once settled;
a caption at least 1.8 s and never shorter than its spoken line + 0.6 s; a title card at least 4 s.
`npx hyperframes check` reports `line_unread`: fix every one or say why it is deliberate.

Avatar mouth: a new face rig must print `"lip_seal_ok": true`. READ its `mouth_zoom.png`: the
lips meet at both corners in all 9 shapes, with no skin strip between them.

## 2. Look (READ the images, do not just generate them)
- `qc.png` contact sheet: every word and face inside the green safe box? Nothing
  important in the tinted bands?
- Frame 0 and the first 3 s (`npx hyperframes snapshot --range 0,3 --frames 7`): hook
  visual and text there at frame 0?
- `npx hyperframes snapshot --review`: read `review-beats.jpg`, the seam strips around
  every cut and `review-phone.jpg` (360 px wide, the legibility test).
- The climax: build frames and the release frame; the number readable for 0.5 s+?
- Captions: never over a face or the avatar's mouth; key word highlighted; no orphan
  single words.
- Hindi: conjuncts and matras render correctly (Mukta or Noto Sans Devanagari loaded via
  `@font-face`); no tofu boxes.
- 3D / WebGL frames look right in the actual render (code can look fine and render wrong).
- Key actions (a pose pop, a card landing, a flip, a hand-over): a 0.2 s frame strip, enlarged.
- Expressions at their FINAL placed size, brows above all ("worried" and "angry" are one brow flip apart).
- Opuscar's frequent failures: subject too small or against the frame edge; colour on the same colour; a gag or
  reveal too fast to read; blank frames in a transition; a timed effect that loses its subject after the camera
  moves (one world-to-screen function).
- One fix round: everything the checks find is fixed together, then checked once more.
- AI b-roll: watermark gone (crop sheet read), no garbled text, no uncanny faces.
- Last frame to first frame: does the loop seam read as continuous?
- Not a slide deck (`visual-grammar.md` "Video, not slides", added 2026-10-31): the 6 structural
  checks pass (no opacity-toggled scene blocks, a visual thread > 60%, ≤ 2 text levels, not
  Ken Burns only, ≥ 2 transition kinds with ≥ 1 with depth, one special moment). Ask of each
  sheet frame: could it be a corporate slide unchanged?
- Shot sizes: the camera reaches close-ups on the element being talked about; no world edge
  shows at any shot peak; text lands after the camera arrives.
- Contrast: grey-scale 3 frames with full text; no background area as bright as the letters.
- Sizes: no text under 30 px on the 1080-wide frame (titles ≥ 100, body ≥ 44, labels ≥ 34,
  disclaimer/credits ≥ 30). Measure from the HTML, not by eye.
- Every company/product/place the VO names is on screen in its scene.
- Grainy or soft gradients: zoom the encoded MP4 frame for banding.
- Not just defects: look for clutter. Is anything busy sitting behind the presenter? Is any hand or prop
  cut at the frame or box edge? (A reviewer caught both on a real reel after the defect checks had
  passed.)

## 3. Facts and rights
- Every on-screen number and claim is in `sources.md` with a link, or labelled
  illustrative.
- Every music track, SFX pack, font, image and clip is in `licences.md`.
- Brand pack compliance items done (disclaimer slot, banned phrases).

## 4. Self-score (from `retention.md` section 9)
Score 1-5 each; anything under 4 gets fixed or explained to the user.

## 5. Phone review
The user watches the draft on a phone before the delivery render. Their notes go into
`lessons.md` in their own words.
