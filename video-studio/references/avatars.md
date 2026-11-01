# Cartoon avatar presenters

Animated cartoon characters (caricatures of real people, WITH their OK, or invented mascots) that host and point
at the explainer. Everything runs locally and free, except the art, which comes from ChatGPT image gen in the
user's own browser (preferred over Gemini for characters; see `references/browser-ai.md`).

Two live routes:
- **A. ChatGPT pose library** (the proven route for reels): a library of 30-60 full-body poses of the SAME
  character, each with the mouth closed, plus OUR face rig patched onto every pose for blinks and lip-sync.
  `scripts/avatar_track.py` renders the placed presenter as one transparent track.
- **B. HTML/SVG drawn character**: a chibi caricature drawn in SVG and animated from code. New poses are instant;
  likeness is lower. One reviewer rejected it for a brand that wanted the pose-library look; another approved it.
  Ask which look the brand wants before building.
- Shelved: the hybrid route (an AI video clip of the character as the body + our face tracked on). AI clips have
  no green screen, so the key leaves a grey fringe and the body is soft. Never mix routes in one video without
  asking.

## Route A: the pose library (proven on real reels)

### 1. Character and poses
- **Reference**: the person's OK, 3-5 clear photos (front, three-quarter, smiling) and signature features to
  keep (hair, glasses, beard, usual outfit colours). Make 2-3 style options as single images; the user and the
  person pick one. Then a concept SHEET. To get the reference pose, ask for "the left full-body figure" and spell
  out the framing; make 2 drafts and pick the one with the mouth CLOSED (the face rig needs the X mouth).
- **Pose prompts**: one locked preamble (style, outfit, framing, scale, plain flat background, mouth closed in a
  soft neutral smile, five fingers, no text), then one line per pose. Lock long hair in every prompt ("falling in
  front of both shoulders to mid-chest with exactly the same shape"); it held at hair IoU 0.89-0.98.
- **Library**: ~30 generic gestures (count 1-5, point in 8 directions, open palms, present left/right, shrug,
  hand on chest, stop palm, arms crossed, steeple, thumbs up/down, wave, "this much", finger wag, OK sign,
  clap, fist pump, tap wrist, frame hands, ta-da, arms wide) plus props as PLAIN text-free objects (a blank white
  phone or tablet screen for compositing, a blank clipboard, a coin, a piggy bank, a calculator, a shopping bag,
  a magnifier, a gift box).
- **Gate**: `scripts/pose_consistency.py` BEFORE any face rig:
  - roll relative to the reference (MediaPipe reads a constant tilt on cartoon eyes, so absolute limits fail);
  - scale against the library median by shoulders OR leg width (raised arms move the shoulder landmarks, so
    shoulders alone false-fail);
  - hair IoU, hand near face, top colour (false-fails when hands or a prop cover the top: overrule only after
    looking).

  Every pose must fit the face rig 100% (neck, collar, scale, angle) or be regenerated. A pose that fails three
  times is dropped.

### 2. Face rig (one drawing, warped: nothing can shimmer or double)
- `scripts/face_rig.py --head head_hi.png --landmarks face_landmarks.json --out rig/face` makes every
  mouth / blink / brow state as a smooth warp of the SAME hi-res head, plus a painted mouth interior and eyelids
  (`face_paint.py`, 4x supersampled).
- Landmarks: measure with MediaPipe and READ an overlay. The automatic detector failed on a stylised face (eyes =
  catchlights, mouth = the necklace).
- Options that mattered:
  - `lip_line`: the MediaPipe inner-lip curve, for a curved smile. The +-6 px search notched the corners.
  - `lid_mode: "warp"`: slides the drawing's OWN upper lid down. A painted lid looked like a flat oval, then
    striped, then a flat bar at half.
  - `no_brows`: when brows sit on a glasses frame or ghost when moved. A still brow beats a broken one.
- **Lip seal gate**: the build prints `"lip_seal_ok"` and writes `mouth_zoom.png` (all 9 shapes at 3x). READ IT:
  - the lips meet at both corners in every shape;
  - no skin strip between the lips (fraction of skin inside the opening must be <= 0.01).

  Two bugs caused visible lip separation before the fix:
  - the jaw drop did not pin the corners;
  - the painted opening was clipped flat below a smiling lip line.

  The fix: at the lip line the drop follows the same lens profile as the opening, and the opening's box reaches
  the highest point of the lip line.
- **Short hair**: the full-head route (the whole head swapped onto each pose, our chin seated on the pose's chin,
  the pose's own neck kept with a drawn outline). The NECK must be there: an avatar without a neck was the first
  thing a reviewer saw. For a locked head, a static hand-placed back-of-collar band behind the avatar beats any
  per-frame "fill the pockets" heuristic, which flickered.
- **Long hair over the shoulders**: the full head would cover raised hands. Use the FACE-ONLY patch:
  - `face_patch.py mask --head head_hi.png --out rig/`. READ face_mask_check.png: brows inside the mask, no spike
    up the hair parting, no ear nubs.
  - Plan `"face_mode": "patch"`: each pose keeps its own hair, outfit and hands.
  - Colour gain: compare against the pose's face skin UNDER the patch core. An outer ring caught cheek shading
    and darkened every pose by 15%.
  - Fit: a similarity transform from ~32 stable MediaPipe landmarks (LMEDS).

### 3. Mouths (lip-sync)

| Id | Sound | Drawing |
|---|---|---|
| X | rest, silence | closed, relaxed smile |
| A | M, B, P | lips pressed |
| B | most consonants (K, S, T, EE) | slightly open, teeth visible |
| C | EH, AE | open |
| D | AA (wide vowels) | wide open, tongue |
| E | AO, ER | rounded open |
| F | UW, OW, W | small puckered O |
| G | F, V | top teeth on lower lip |
| H | L | open, tongue up |

- **DEFAULT (script known): Rhubarb + the script text, per line**:
  `python -I scripts/mouth_rhubarb.py --lines-dir vo/lines --starts vo/starts.json -o avatar/mouth.json`
  (or `--wav vo.wav --text script.txt`).
  - It uses all 9 shapes: G for f/v, H for l, and A for real M/B/P closures.
  - `--lead 1`: every shape starts 1 frame BEFORE its sound (a lagging mouth reads as off-sync).
  - `--min-hold 2`: no flicker, but an A closure is never dropped.
  - Reviewers called the loudness-only mouths "sloppy" and the Rhubarb + script version "so much better". On
    one reel the loudness method opened wide (D) 78 times in 74 s and never used G or H; Rhubarb opened wide
    17 times.
- **Hindi, or no Rhubarb** (e.g. Apple Silicon without Rosetta: Rhubarb 1.14 is x86_64 only on macOS):
  `scripts/mouth_phonemes.py`, same arguments as mouth_rhubarb.py plus `--lang hi`. espeak-ng phonemes of the script
  (Kokoro's own phonemizer), timed by faster-whisper word times snapped to the audio; all 9 shapes. Tested: a Hindi
  line found all 6 lip closures (m, b, ph); an English clip vs Rhubarb matched mouth openness within one step 80% of
  the time and closures 90%. Sounds inside a word are placed by weight, not heard: check A closures on M/B/P words.
  Both scripts read either starts.json format (`starts` + `lines`, or `lines: [{start, text}]`).
- Fallback: `scripts/mouth_from_audio.py` (loudness + brightness, any language, X-F only) only with no script.
- Do not judge mouth timing by Whisper word times: they can run ~0.4 s late after a pause. Check the waveform.
- Mouth QC is a 3-4x ZOOM of the lips per shape. Face contact sheets are too small to show a 3-5 px strip at the
  corners.

### 4. Placement in a reel
The avatar sits in ONE spot at ONE size for the whole reel. A pose change is hidden by a 6-frame pop (+ a sparkle),
or by a full-cover foreground sweep for route changes, never by a size change.

`scripts/avatar_track.py --plan plan.json ...` renders a single transparent WebM (VP9 + alpha) of a screen box:
- `box`: x, y, w, h. It must fit the WIDEST pose (a raised finger, a stop palm, an open palm to the side).
  A box starting at x 200 cut a present-left palm's fingers; [40, 880, 1040, 1040] fit a 60-pose library.
- `anchor`: the eye midpoint on screen. Keep the FACE left of the platform's action rail and inside the safe band.
- `d`: the locked eye distance (~94 px on 1080x1920).
- `segments`: [{start, route, pose, enter: in|pop|cut, why}], one pose per line. "why" names the line and the
  graphic it illustrates. Poses must ILLUSTRATE the line ("should not just be random"): count 1-4 on four cards,
  point at the chart, stop palm on "Wait.", steeple on the question, piggy bank on "invest every month".

Render it in FOREGROUND chunks with `scripts/pipeline/render_chunks.py` (~4 min per 12 s chunk on a small laptop).
Each chunk's plan holds only its own poses.

Before compositing:
- Read EVERY frame of the magenta `--preview` as contact sheets (`scripts/pipeline/sheets.py`) and run
  `scripts/pipeline/scan_avatar.py`. The scan checks holes vs each segment's settled frame, stray blobs and face
  jumps; it was proven by injecting fake defects.
  - Every-frame audits found what samples missed, twice: backdrop-flash frames, a pocket by the hair, and 16
    frames of shirt holes.
- Scan for body pixels in the box's outer 3 px. Any hit means widen the box. To widen a rendered track without
  re-rendering, pad the old chunks (`pad=W:H:dx:0`, transparent for VP9, magenta for the preview) and re-render
  only the clipped chunks.
- Every hand and prop stays inside the FRAME, not just the box. Drop poses that point off-screen, hang a prop
  below the frame, or cut a phone at the edge.
- Measure an avatar-free caption box over ALL avatar frames. Captions and source lines never sit under a gesture
  hand.
- Nothing busy may sit behind the avatar: only the active graphic shows. Any backdrop is soft, blurred and low
  contrast, masked to the lower part of the frame.
- A VP9-alpha track composited in Chrome can show a dotted light fringe that the magenta preview hides. Clamp rim
  pixels to the colour beside them and fill fully transparent pixels with the edge colour before encoding.

### 5. Acting
- Mood changes go through anticipation, squash, new face, settle. Never snap.
- Offset parts: head leads, arms follow, brows lag. Never move both arms or both eyes in unison.
- Eyes look at what matters (the card, the number, the other character).
- Keep the mouth visible: captions never cover the face.
- Light, rich backgrounds read better than dark ones: a navy suit on a navy background lost the arm completely.

## Route B: HTML/SVG drawn character

- Draw a cute chibi caricature in hand-written SVG inside a HyperFrames project, matched to the concept sheet:
  - outlined (#3b2a26 / #1c0d06, 4.5-5 px) with soft gradient shading;
  - what helped most: a tailored jacket (waist taper, flared hem, pocket flaps, rim light), layered wavy hair with
    shine and inner shadow, an iris rim, lid shadow and a lower lip, a soft rounded clasp of the hands;
  - what looked worse and was removed: lid creases (wrinkles), loose crown strands (antennae), lower lashes
    (whiskers), a clumpy fringe edge, finger-rectangle clasps;
  - stop adding detail once it would make animation harder.
- Rig (ids you animate):

| id | what | transform convention |
|---|---|---|
| `#char` | whole character | entrance only |
| `#body` | torso, jacket, neck | breathing scale about the base, lean |
| `#armL` / `#armR` | upper arms, pivot = shoulder (local 0,0) | `rotate(deg)`; 0 = hanging, + = clockwise |
| `#foreL` / `#foreR` | forearms, pivot = elbow | `rotate(deg) scale(1 fs)` (fs = foreshortening) |
| `.hL-<shape>` / `.hR-<shape>` | hand shapes (rest/open/one/two/three/thumb) | opacity 0/1 |
| `#clasp` | both hands clasped at the waist (rest) | opacity, crossfade 2 frames |
| `#head` | face, eyes, brows, mouths, hair cap | `translate(0 nod) rotate(tilt about the neck)` |
| `#locks` / `#hairBack` | front locks / back hair | counter-rotate `-0.6*tilt + trail` so ends hang |
| `#eyeL/#eyeR`, `#pupL/#pupR` | blink = scaleY about the eye line; glance = translate, clipped to the eye white | |
| `#brows` | brows | translate y |
| `#mX..#mH` | the 9 mouths | one at a time |

- Poses are two numbers per arm (upper, forearm), e.g. `rest [4,-67]`, `wave [-62,222]`, `present [26,100]`,
  `up [-24,206]`, `thumb [-16,204]`, `point [36,-232]`. Forearm angles past ±180 are chosen on purpose so raises
  travel UP IN FRONT of the body. Event lists give start time, pose, hand, duration.
- The 7 rules that made it smooth (from `/disney-animation-rule-skill` + `/animation-principles`):
  1. **Pure state = f(t).** `render(t)` computes everything from time, driven by one GSAP clock tween + `hf-seek`.
     Never `.to()` or relative tweens: frames render out of order, and with overlapping tweens on one property,
     seeking backward lets the earlier tween win.
  2. **Moves:**
     - spring travel (zero start velocity, one soft overshoot) with a small eased anticipation;
     - the forearm lags the upper arm by 0.07 s;
     - the hand shape swaps at 55% of the move (the passing pose).
  3. **No arm passes through "hanging"** unless foreshortened (forearm scaleY -55% at the hanging direction, elbow
     swung out 22°). A raise via the hanging pose looked like a puppet dropping its arm.
  4. **Attention is continuous.** One 0..1 "how raised" value per arm feeds the eyes (leading, -0.04 s), the head
     (0.08 s), the hair (0.14 s plus a trail) and the body lean (0.22 s). Never average an on/off signal over a few
     samples: it made the head step every other frame.
  5. **Accents:** nods and brow lifts on stressed words; gamma-shaped count bounces; wave and present sways ramped
     in and out with smoothstep.
  6. **Check:** per-frame difference plus "stutter" frames (a near-zero change between two big changes) must be 0.
     Sample frames 1/60 s apart during each move.
  7. **Render:** "smooth" also means 60 fps for avatar-heavy shots when the platform keeps it
     (`--quality looks --fps 60 --workers 2`, ~1m50s for 11.5 s).
- For a reel, make it a placed component (fixed corner spot and size, transparent background), like route A.

## Older routes (kept for reference, superseded)
- **Cutout limbs + one-drawing face** (`cutout_rig.py`, `build_cutout_scene.py`, `chain_rig.py`): a parts sheet
  (head with neck, torso without arms, upper arms, forearms with hands) on green. Joints are found automatically.
  Poses use ABSOLUTE forearm directions (`fdir`, 90 = down, -90 = up); relative bends produced backwards hands.
  Upper arms behind the torso, forearms in a twin chain in front.
  - Polish item: in a big sweep the old hand shape can pass flat across the chest for ~3 frames; time the swap
    earlier.
- **Whole-picture swaps** (`puppet_build.py`, `build_puppet_scene.py`, prompts in `templates/puppet-prompts.md`):
  three parts sheets (2x2 pose grid with WIDE gaps, a 3x3 mouth grid in Rhubarb order, a 3x2 eye grid) on chroma
  green #00FF00, keyed, aligned with SIFT + ECC, patched. Rejected: every mouth was a different drawing, so the
  jaw shimmered 10-15x a second, and arms teleported.
- **Placeholder SVG rig** (`templates/cartoon-avatar/index.html`, `build_avatar_proof.py`): a working HyperFrames
  rig with cue-driven mouths, seeded blinks, breathing, head tilts with brows following, an anticipation-point-
  overshoot-settle arm, and a card that pops on the point. Rig contract: position every part with a `transform` on
  an OUTER `<g>` and animate the inner `<g>` (never CSS-transform an element GSAP transforms).
- True rigged 3D (image-to-3D meshes, VRM) was rejected: likeness drops, no face rig for visemes, too heavy for a
  small laptop.
