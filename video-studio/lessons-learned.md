# Lessons learned (distilled from many real videos)

These rules come from real reels, explainers and walkthroughs. Each one cost time once. Read this at the start of
every video chat. The owner's own new lessons go in `lessons.md` (dated, newest first); when one repeats, promote it
into the right reference file.

## 1. Working with the user
- **Every frame before anything is shown.** A reviewer once asked "did you look at every frame?" and the honest
  answer was no. Sampling 4-8 frames is not QC: reviewers caught double mouths, doubled brows, an overlapping jaw,
  backdrop flashes and holes that samples missed. Read a contact sheet of EVERY frame (frame number burned in),
  plus automatic per-frame scans.
- **Each new video beats the last** in every aspect behind the presenter. Write the upgrade list before building;
  record the new baseline after delivery.
- **By-ear choices belong to the user**: tricky words (render 3-5 spellings), voice, speed, music. Present them on a
  local HTML pick page (players + radio buttons + "None of these" + "Copy my picks"). Users asked for this format
  over a list of file names. Whisper read-back first, so broken options never reach them.
- **Ask before combining methods.** A reviewer wanted to SEE each avatar route on its own ("I never said to mix").
- **When a method's flaw is structural, stop patching and change the method.** Four rounds of fixing a static
  layer from the top went back and forth; removing the layer fixed it at once. "Patched" rigs were rejected as
  "still very imperfect and broken".
- **Regenerate, don't patch, rejected AI images.** Painting over a reused image flattened it, and it was called
  "very odd and bad".
- **Never kill a process you did not start without asking** (renders, servers, the user's apps). When memory runs
  out, show what is using it and let the user choose what to close.
- **Long work keeps going.** When the user has said to finish, do not stop and wait for permission after a tool
  hiccup; fix it and continue.

## 2. Script, facts and compliance
- Every on-screen number has a row in `sources.md` with a link and date, checked at the PRIMARY source (the
  regulator, the exchange, the industry body), not only a news article. Re-read live numbers (an index level) on
  the posting day; say which numbers will need refreshing when new monthly data lands.
- Illustrative maths is labelled "ILLUSTRATIVE" on screen ("Not a prediction" where it projects). Past-performance
  charts carry "Past performance does not guarantee future returns."
- Compliance / disclaimer text goes on screen VERBATIM, first line bold if the brand asks. Never humanise or "fix"
  its grammar. Snapshot the end card before rendering: the first layout ran under the presenter's hair.
- Changing only an end card of an approved video: edit the scene, re-render, PSNR-compare with the approved master
  (only the changed frames should differ), then put the approved audio back with `-map 0:v -map 1:a -c copy`.
- Hooks: write three, score them, keep the runner-up for an A/B repost. A hook number is sourced like any other.

## 3. Voice
- Kokoro `af_heart` was the best free English female voice in a 25+ voice bake-off; most other Kokoro English voices
  were rejected. Kokoro romanised Hinglish was "fully broken". edge-tts Indian voices silently SKIP Devanagari
  (half-length output): check durations, not just "ok".
- Pronunciation: Devanagari inside English TTS was garbled; respell instead ("Dhanteras" -> "Dhuntayrus", picked by
  ear from 4-5 options). Write numbers that read badly in words ("forty-nine lakh"). "A I" was heard as "the eye";
  "A.I." works. Kokoro Hindi mangles Latin acronyms ("SIP"): spell them phonetically in Devanagari.
- Build the voice PER LINE and place each line at its MEASURED start in a numpy mix. Concatenating with a fixed
  gap drifted ~1 s from the planned sums. Transcribe each line separately for word timings.
- Whisper word times can run ~0.4 s late after a pause. Check a big visual hit against the waveform.
- `npx hyperframes tts` needs `HYPERFRAMES_PYTHON` pointing at a Python with kokoro-onnx; a line can fail at random
  once, so retry before giving up. Loudnorm the voice (a -17 LUFS voice failed QC).

## 4. Avatar presenters (see `references/avatars.md` for the full pipeline)
- **Routes**: the ChatGPT pose library + our face rig won on real reels. The HTML/SVG drawn route works and is
  instant to pose, but one brand rejected it for the pose-library look. The hybrid (AI video body + our face) was
  rejected: no green screen means a grey fringe and a soft body. Whole-picture swap rigs shimmer (every mouth a
  different drawing) and arms teleport.
- **Pose library**:
  - Generate every pose against ONE framing reference ("same head size, same shoulder width").
  - Gate every pose BEFORE any face rig (roll relative to the reference, scale by shoulders OR legs vs the library
    median, hair IoU, hands near the face, outfit colour). Colour checks must sample only outfit-coloured pixels: a
    fixed patch landed on a raised hand and failed 9 good poses.
  - A pose that fails three times is dropped; never use a pose that fails.
  - Ask for the reference figure from the concept sheet with the MOUTH CLOSED.
  - Lock long hair's shape in every prompt.
  - Props are plain and text-free.
- **Poses must illustrate the line** ("should not just be random"): count on cards, point at the chart, stop palm on
  the warning, steeple on the question. Write a "why" per segment. One pose per line; every change on a pop or a
  sweep; size and place never change.
- **Every hand and prop inside the FRAME**: drop poses that point off-screen, hang a bag below the frame, or cut a
  phone at the edge, even if they are in the library.
- **The box must fit the widest pose**: a 704 px box cut a raised finger; a box starting at x 200 cut an open palm.
  Scan the outer 3 px of the box on every frame before compositing.
- **Neck and collar**: an avatar without a neck was the first thing a reviewer noticed. Seat our chin on the pose's
  own chin and keep the pose's neck. For a locked head, ONE hand-placed back-of-collar band behind the avatar beat a
  per-frame "fill the pockets" pass, which flickered as the mouth changed.
- **Long hair**: patch only the face skin (face_patch), so each pose keeps its own hair and hands. Add the brows to
  the mask core explicitly: a brow tip touching the mask edge escaped hole-filling and showed a ghost brow.
- **Face rig**: automatic landmarks fail on stylised faces (eyes = catchlights, mouth = a necklace). Measure with
  MediaPipe and READ an overlay. Painted eyelids looked flat; slide the drawing's own lid down. Brow moves left ghost
  brows: a still brow beats a broken one.
- **Mouths**: Rhubarb + the script text, per line, 1-frame lead, 2-frame hold that never drops an A closure.
  Loudness-only cues were called "sloppy". The lips must meet at the corners (lip-seal gate, 3x mouth zoom sheet);
  a fault there showed as "the lower lip separated from the upper lip". Face contact sheets are too small for mouth
  QC.
- **Hands (older drawn routes)**: real presenters show palms to camera or cupped hands in front of the belly, not
  side-view palms at the sides. Arms placed by joint ANGLES hung wrong; arms placed by normalised POSITIONS (from a
  motion clip) looked natural. Hanging arms need their own drawings. Clamp a pointing hand's rotation to ±12°. Hands
  together = a separate clasp drawing; a crossfade of two hand pairs ghosted.
- **Debug on MAGENTA at 3-8x, using the renderer's own code path**: a light background hid the holes, and a separate
  diagnostic script hid the real bug.
- **Image tech that worked**: SIFT + ratio test + ECC for aligning flat cartoon art (ORB failed across a 1.8x scale
  gap); geodesic growth from head + spine seeds for splitting figures (watershed leaked); a feathered rounded
  rectangle for patches (an oval faded the eyes). Lanczos warps ring on black outlines: clamp after the warp and
  divide by max(alpha, 0.02). A VP9-alpha track can show a dotted fringe in Chrome that a magenta preview hides:
  clamp rim colours and fill transparent pixels with the edge colour before encoding.
- **Seek-safe animation**: renders seek out of order. Never `.to()` or relative tweens; never two tweens on one
  property; give each element its own explicit sets. "Hide the class, then show one" at the same instant floated the
  face without a body for 5 frames.

## 5. The look behind the presenter
- **One-take world** beat scene cuts: station cards on one canvas, a hero object hopping card to card on the spoken
  words, a camera that eases between framings and never cuts, a pull-out reveal of the whole journey at the end and
  a dive back to card 1 for the loop (`templates/reel-project/`).
- **Nothing busy behind the presenter**: neighbouring cards at 30% opacity were called clutter ("why is there stuff
  behind her"). Only the framed card shows; any backdrop is soft, blurred, low contrast, masked to the lower part of
  the frame, with a slow drift that loops. One quiet AI backdrop was enough.
- **Real data charts** (exchange daily closes fetched in the browser; records came newest first, so sort them) beat
  illustrative shapes. The hero can ride the line as it is spoken.
- Light, warm, rich frames won; sparse dark-minimal frames were rejected as "empty" (repeatedly, by one brand).
- 3D: a white RoomEnvironment turned gold into cream; use the scene's own plate as the reflection map. A non-metal red
  reads as RED next to gold; a salmon metal read as gold. A camera dive must end inside a lit face, not over a dark
  top face. A rotating 3D ring of cards looked cluttered; a 2D-driven coverflow is cleaner and seek-safe.
- Badges go ON the object (the bar's face), never over a data label. Source and caption text never sit under a
  gesture hand.
- Pace: nothing behind the presenter should sit still for over ~1 s, and the first 2 s must move
  (`scripts/pace_check.py`). One real reel's hook sat nearly still for 1.2 s; beat that.
- An inline `//` comment added mid-line in minified JS ate the rest of the line, and the whole scene vanished. Put
  comments on their own line, and snapshot after every edit.

## 6. Captions
- Measure an avatar-free caption box over ALL avatar frames. Captions never cover the mouth.
- Groups follow the sentence: split at punctuation and pauses, 2-4 words, a number stays with its unit, a lone
  trailing word folds back, a lone word that OPENS a sentence goes forward ("One, your goal has changed."), break
  BEFORE a word that would overflow. A one-word complete sentence ("Wait.") may stand alone. Key word in the accent
  colour. Captions keep the real spelling even when the TTS got a respelling.

## 7. Sound
- Music only with a licence that allows the use; business accounts cannot use the platform's trending library (the
  real trending songs are usually copyrighted film music). Log the licence and credit.
- librosa misses beats in intros: fit ONE uniform beat grid and pick the music start that lands the hard cuts on
  beats (search every start that fits the reel; a narrow search window crashed once).
- Duck the music under the voice (~-22 dB under speech, ~-10 dB in gaps), dip it on a key word, swell it on the
  climax and the reveal. Master to -14 LUFS, true peak about -1 dBTP; deliver with and without music.
- Every visual hit gets a sound. A hero object's landings can be the lead instrument (a pluck climbing a pentatonic
  scale as the story advances).

## 8. Rendering and the machine
- Background jobs get killed when RAM runs low: a 45-min render was lost. Run long renders as FOREGROUND chunks
  (avatar `--only` chunks ~12 s; HyperFrames segmented capture with `--resume`), one heavy job at a time.
- avatar_track loads every pose in its plan: give each chunk a plan with only its poses. `OPENBLAS_NUM_THREADS=1`
  when memory is tight. Keep video frames JPEG-compressed in RAM. Cache per-clip eye tracking (it was 5 of every 8
  minutes).
- HyperFrames `check` timed out on 21,000 px PNGs: feed the video light JPEG copies.
- Timings on a 6 GB laptop: an 80 s one-take reel ~10-11 min draft, ~23 min delivery; an avatar chunk ~4 min per
  12 s; a 4.5 min 1080p walkthrough ~23 min at `--workers 1`.
- On Windows, inline Python in shell commands mangled backslash paths (`\a`, `\t`, `\U`); use forward slashes, raw
  strings or a file editor.

## 9. Browser AI (details in `references/browser-ai.md`)
- ChatGPT: one tab, a new chat per image, sends at least 60 s apart (~55 fast sends triggered "too many requests").
  Read real chat ids from the sidebar. Clear the composer and verify its text before Enter, or an old draft gets
  spliced in. Record the chat id in every pulled file: a pull once grabbed the wrong chat.
- Gemini Omni: the user presses Send; retry a failure in place ("Try again"); stay on the tab until saved; scope the
  saved `<video>` to the last answer. Abstract textures animate; chained physics and some subjects fail.
- Save by in-page fetch to base64, never a download event (it closed the browser).
- Lip-sync and likeness work on a real person runs only in the user's OWN accounts, never a public service.

## 10. Screen walkthroughs (template in `templates/screen-walkthrough/`)
- Capture through the Playwright MCP; each run-code call is a fresh sandbox, so keep helpers in a library file
  prepended to each step. A 2x context gives sharp zooms.
- Full-page shots over 16,384 device px repeat the top of the page: capture tall pages in slices and stitch.
  Full-page shots are ~15 px narrower (scrollbar); measure boxes in the same state the image was taken.
- 1600 px of UI in a 1120 px frame reads small: zoom close-ups ~1.22x, and align a box wider than the window LEFT.
- Whisper-check every voice line before building.

## Beat sync and professional sound (2026-11-01)
- One beat grid drives everything. Mark every cue as `beat` (can move: snap it), `anchor` (a spoken word that must
  also land on a beat: fit the grid to these) or `word` (never moves). A test reel: 14 events, mean 3 ms off.
- Beat trackers misread intros (librosa said 92 bpm on a 140 bpm track); fit one uniform grid over the whole track.
- Write the score ON the grid (hits, rests before them, a resolving last bar) and the sync is exact by construction.
- Judge the mix with measurements, not taste: earshot's critique against 7 pro launch films first flagged a thin sub
  and a mono image. Fixes that got it to 18/18: subs added after the low-end balance, mid/side width on the music,
  music ~10 dB (not 14) under the voice, a decorrelated room-tone layer, a limiter after loudnorm (AAC overs).
- Windows: `python -I` ignores PYTHONIOENCODING; use `-X utf8`.

