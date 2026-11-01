# Visual grammar and the premium look

The goal: something new to look at every 1.5-3 s, every frame looking expensive, and every
graphic carrying meaning. Decoration that does not explain anything is cut.

## Graphic type per beat

| Beat / job | Best visuals | Where it comes from |
|---|---|---|
| Hook (frame 1) | Big kinetic headline over a moving 3D or textured scene; a number mid-count; a split before/after | `/title-sequence-3d`, registry kinetic-type and title blocks, `/motion-effects` masked or elastic type |
| Explain a concept | Avatar guide pointing at a diagram; icons that assemble; flow diagram that draws itself | `references/avatars.md`, registry overlays, `/explainer-engaging` |
| Show a number | Count-up, bar to line morph, milestone particle reveal, scale stack | `/animated-chart`, `/milestone-reveal`, registry charts |
| Compare two things | Split screen, two 3D columns growing, toggle morph | registry charts + 3D blocks |
| Time / growth | 3D line or ribbon the camera flies along; timeline that scrolls | Three.js via `/hyperframes` runtimes, `/threejs-webgl` |
| Process / steps | One hero element travels station to station; numbered cards that stack | `/explainer-engaging`, `/motion-effects` spring stack |
| Real-world texture | Gemini Omni b-roll (liquid, light, city, money texture), stock footage | `references/ai-broll.md` |
| Emphasis | Punch-in zoom, light sweep, glow pulse on the key word, a freeze frame | `/hyperframes` `references/motion.md` |
| Talking-head overlay | Lower thirds, data callouts, pull quotes, motion b-roll | registry overlays, `/motion-broll` |
| Transition | Shape morph that carries across scenes, shader transitions, whip pans, match cuts | registry transitions (`@hyperframes/shader-transitions`) |

Search the registry first: `npx hyperframes catalog --json` / `/hyperframes-registry`.

## The premium look (what separates expensive from template)

Effect ideas not used yet (from the MAKINGAIDOIT Free Reel Kit, 2026-10-29). Options for the next
reel, not defaults. Each must fit the brand's look (for a light, warm, rich brand: no neon, no dark-minimal):
- **Sticker slap**: a tilted label flies in and sticks with a bounce ("ILLUSTRATIVE", "-14%").
- **Halftone dot wipe** between sections, in the brand colours.
- **Flap cards**: cards fold open like wings in 3D as they enter.
- **Orbit**: small icons circle the main object (coins around a hero coin).
- **Snap zoom**: a fast 6% punch-in on the accent word, eased back.
- **Before / after split**: a divider wipes from the old state to the new.

- **Depth**: at least three planes (background texture or 3D, midground graphic, foreground
  text or avatar). Parallax between planes on every camera move.
- **Camera**: slow continuous drift (1-3% scale or a few degrees of 3D orbit) so nothing is
  ever dead still; fast moves are eased (expo / power3 in-out), never linear.
- **3D**: Three.js scenes with real lighting (key + rim + soft ambient), shallow depth of
  field feel, reflections on floors, fog for depth. Camera moves through or around the
  subject, not just zooms. Keep scenes light on a laptop's integrated GPU (low poly, few lights,
  baked where possible) and check frames, because a WebGL bug can look fine in code.
- **Glow**: used for emphasis on one element at a time (the key number, the active node),
  as a soft bloom, never on body text. Check the brand pack: some brands ban glow.
- **Morphing**: one shape becoming the next idea (circle → coin → chart → logo) is the
  signature move that makes a film feel continuous. Use SVG path morph or GSAP
  MorphSVG-style tweens; keep point counts compatible.
- **Light**: light sweeps across text and cards, gradient shifts that follow the story's
  mood (calm to urgent to resolved).
- **Texture**: subtle grain (2-4%), noise gradients, paper or glass. Footage grades go
  through `npx hyperframes media-treatment`, never CSS filters.
- **Type**: one display face + one text face from the brand pack, big sizes (headline
  90-160 px on 1080 wide), tight tracking on display, numbers in tabular figures.
  Kinetic type moves by word or line with offsets of 40-80 ms, not all at once.
- **Motion feel**: springs and overshoot for arrivals (back.out 1.2-1.6), expo for
  exits. Elements arrive from where the story says they come from.
- **Colour**: the brand palette plus one accent for emphasis. High contrast for captions.
- **Fullness**: frames should feel rich and complete. Empty, sparse, dark-minimal frames
  read as unfinished to many audiences (learned on a finance brand: the team called austere
  layouts "empty"). Fill space with meaningful graphics, not noise.

## Video, not slides (rules adapted from bang-motion, MIT, github.com/bangtutorial/bang-motion, 2026-10-31)

Models build scenes like documents (title, explainer, proof), and the result reads as an
autoplaying deck even when every element moves. These rules can be checked in the code and
in frames. Failing one means rework before the user sees it.

### Structural checks (look at the code, not the feeling)
1. **No section toggling.** Three or more scenes that are separate blocks switched on and off
   with opacity = a slide deck. Scenes change because the camera or the world moves (push,
   pull back, whip, match cut, an object that becomes the next scene).
2. **A visual thread.** One subject or one world stays on screen for more than 60% of the
   reel (the avatar alone does not count: the graphic world behind it needs its own thread).
   One picture + one sentence per scene, swapped each scene, is still a slideshow.
3. **At most two text levels per scene**: one big number or sentence + one label. Eyebrow +
   title + body = slide. A document, stamp or date block of 3 short lines or fewer counts as
   an object.
4. **Ken Burns is never the only motion.** Every second gets motion from the chosen
   background language (below) or from an element acting.
5. **Transitions vary.** At least two kinds per reel, at least one with depth (3D push,
   card turning in from depth, an object with thickness passing the lens, rack focus).
   Flat colour wipes at most twice. The same transition on every cut = template.
6. **One special moment.** The most expensive effect (3D type pan, logo build, big morph)
   is used once, maybe twice. Everywhere means nowhere.

Frame test: could this frame be a corporate slide without changes? Does the eye know where
to look within 0.2 s? With all text hidden, is the background calm but not dead?

### Shot size: the camera goes to the element
A breathing zoom of a few percent is a base layer and is nearly invisible. "Zoom in-out"
means shot size: wide → medium close-up (target fills 1/3-1/2 of the frame) → close-up
(target fills most of it) on whatever the VO is talking about now, then back out when the
composition needs the whole frame.
- Two tempos: shot changes (0.6-0.9 s, ease in-out) and a slow push while holding (sine).
- A scene may be born in close-up at a cut and pull back. Text lands AFTER the camera arrives.
- Never two shots of the same size in a row; never faster in-out than a reader can read.
- Rig: one camera object {s, fx, fy} (scale + focus point in world coordinates), applied in
  the seek-exact render; clamp the translate so the world's edge never shows, and make the
  world larger than the frame (overscan). One scale system per wrapper: stack the breathing
  inside the same function, never a second tween on the same element.
- Captions, the disclaimer and any HUD sit on a layer OUTSIDE the camera rig.
- Raster assets must be sharp at close-up scale (resolution ≥ scale x display size).

### One new element per phrase (explaining scenes)
- Each VO phrase ADDS one element; the old ones stay. A scene ends with 3-5 elements that
  explain together: subject + proof (document, screen, clipping) + scale (number or a repeat
  grid) + label/date stamp + a hand-drawn mark. Elements arrive in order: sentence → main
  object → supporting detail, never reversed.
- Scale by repetition: one icon multiplied into a grid (staggered back.out) lands harder than
  the number alone. The number still shows.
- New element = a small camera look (±200 px, 1-1.15x), not a cut.
- **Every named entity appears.** Make a list from the script of every company, product,
  place, event or person the VO names; each gets an image in its scene. Sources in order:
  free-licence photos → official press/og:image (credited) → the user's own → a generated
  image labelled illustrative for GENERIC places/objects only. Never a generated face of a
  real person. Nothing found → ask the user before using a silhouette.

### Backgrounds: never flat, never still, never louder than the text
Pick ONE background motion per reel (two if the background changes between segments) and
write it in the style brief:

| # | Background motion | Feel |
|---|---|---|
| 1 | Textured ground + breathing camera + one slow tint/light shift | calm, expensive |
| 2 | Large 2-3 colour gradient drifting/rotating (8-15 s) | soft, modern |
| 3 | 2-4 floating blurred colour blobs (±60 px, 4-6 s) | friendly, light |
| 4 | Living grain / paper texture (offset from t, never random) | printed, organic |
| 5 | One light sweep per segment (not continuous) | premium |
| 6 | Large geometric or logo shapes turning 20-40 s per turn, 2 parallax layers | brand |
| 7 | Particles RISING slowly (dust, bubbles), opacity ≤ .35 in the text pocket | warm, alive |
| 8 | Grid/pattern breathing (scale/opacity 1.0-1.04, 6-10 s), no scroll | precise |
| 9 | Giant ghost text drifting behind (opacity .18-.25, one style per reel) | editorial |
| 10 | Theme photo/illustration with Ken Burns + 2-layer parallax | narrative |
| 11 | Horizontal streaks/lanes | ONLY for speed/flow topics, never two reels running |
| 12 | Palette colour fields snapping on beats/objects (0.15-0.3 s) | pop, energetic |

Surfaces (every background has ≥ 2 layers, colours from the palette, never pure black/white):
horizon glow, diagonal duotone, light mesh of blobs, spotlight + tint, layered sky bands,
texture over any of these (multiply/overlay .1-.3), grainy gradient (saturated gradient IN
shapes + fine grain over everything).
- **Text pocket contrast**: under text the background is ≤ 25% luminance (white text) or
  ≥ 80% (dark text), never busy-medium. Busy background → a soft radial pocket behind the
  text that appears with it. Test: grey-scale a frame at full title; no background area as
  bright as the letters.
- A background colour change needs a visible trigger (object covering the lens, wipe, push
  into a colour field, cut on the beat), never an unmotivated cross-fade.
- Grain: encode with `-crf 10-12 -tune grain` and check the MP4 (not the browser) for
  banding; slightly bigger grain survives re-upload better.

Object render family: one per reel (flat solid, flat + colour dots, soft clay 3D, glossy 3D,
glass/glow orb, isometric, realistic metal, neon line, flat character illustration), or two
only if the switch is the moment.

### Living type
- Sentence case, weight 500-600. All-caps heavy only for ONE emphasis scene.
- Headlines, claims and short phrases get NO full stop by default. `?` only for a real
  question. Decide punctuation once per reel.
- Emphasis: one form per reel, chosen in the style brief: none (word by word dim → full,
  size, pause, an icon beside the word), pill, underline drawing in, marker, thin box,
  colour only, strike + replacement. Not on every sentence. Different from the last reel.
- Two scenes in a row never share size AND entry direction AND position.
- Text next to an object sits beside it, not forced to the centre over it.
- Directional motion blur on every text entry/exit (SVG feGaussianBlur along the motion;
  widen the filter region to x/y -70%, w/h 240% or the blur tail clips).
- Asymmetric rhythm: in slow and firm (0.7-1.3 s, power4.out), out fast (0.35-0.55 s,
  power2.in). Symmetric feels mechanical.
- Titles clean (full white or ink + a thin shadow); glow belongs to objects, not headlines.

### Minimum text sizes (1080-wide frame, before any safe-area scale)
Titles ≥ 100 px · body/captions ≥ 44 px · labels, names, years ≥ 34 px · credits, sources
and the disclaimer ≥ 30 px at opacity ≥ .6 · handwriting notes ≥ 48 px. Nothing under 30 px.
If it does not fit, split it or cut it, never shrink it.

### Props must look alive
A ±10 px sway over 2 s reads as still. Minimum: ±22-28 px over 1.3-1.8 s (sine yoyo) + ±1.5°
turn + slow scale 1 → 1.06 across the scene + a few px of x drift, with different phase and
duration per object so nothing moves in unison.

### Traps
| Symptom | Cause | Fix |
|---|---|---|
| Element flashes for a frame before its entry | initial state set by a later tween, or a more specific CSS selector overrides `opacity:0` | initial `opacity:0` in CSS on the animated pieces themselves |
| Counter box jitters in width | proportional digits | `font-variant-numeric: tabular-nums` + `min-width` |
| Split text breaks or measures wrong | split before the font loaded | wait for `document.fonts.ready` |
| A flat 3D ornament becomes a white line | full Y rotation of a flat object | sine wobble, never a full turn |
| Text looks dull | stacked glows eat the contrast | drop the title glow |
| Scrub/seek frames differ between runs | random or accumulated state in the render | everything a pure function of t |

## The style brief (write before building; show with the beat sheet)
One line each: background motion (# above) · surface · object render family · emphasis form ·
signature motion (one repeated move that is the reel's identity, e.g. a drawing line, a card
flip, a word roll) · transitions (which cuts get which, ≥ 1 with depth) · the special moment.
Brand colours and fonts come from the brand pack and stay fixed. Each reel must differ from
the previous reel of the same brand in at least TWO of: background motion, signature motion,
emphasis form, transition set, special moment (each video beats the last).

## Directing rules from lemo-opuscar (MIT, github.com/lemomo-ai/lemo-opuscar, DIRECTOR.md, adopted 2026-11-01)
A film is judged in this order: **sound, rhythm, camera, directing** (performance, staging, emotional arc). Good
frames are only the start.
- **Benchmark first**: 1-2 reference works for this topic and look; write what to learn (composition, pacing,
  camera grammar, colour logic, score structure) and what NOT to take (characters, designs, melodies, shots,
  logos, fonts). It lifts quality more than any rule here.
- **Story**: one subject, one goal, one turn; hook in the first 3 s; an ending that echoes the opening (and
  loops); **one native move** at the emotional peak, a moment only this medium can do (a fold that becomes a
  transition, ink that blooms into the next scene); cut the extras.
- **Treatment before building**: three candidate structures and the choice; logline; shot list with framing,
  angle, move, duration and WHY; second-by-second beat sheet; cue map (tempo, bar grid, which beat every cut,
  action and caption lands on); sound design table.
- **Rhythm**: the music grid comes first; vary the pace (one clear acceleration or deceleration, one breath); one
  action, one sound, one cut, but not a cut on every beat; pace for the viewer, not the clock.
- **Camera**: at least four different camera moves and real framing changes per reel (push, pull, pan, parallax,
  focus pull, frame within a frame); one signature shot; transitions made from the medium, one consistent grammar;
  at key moments the subject fills a third of the frame height or more.
- **Performance**: anticipation, action, follow-through; blend poses with easing, never switch inside an `if`
  (one-frame comic pops excepted); check every expression at final size, eyebrows first.
- **Not the demo / not the last reel**: compare structure, opening, signature shot, camera path, score shape,
  ending with the reference and with the previous reel; at least four of six differ.

## Pacing defaults (30 fps)

- Cuts / visual changes: every 45-90 frames.
- Text on screen: at least 0.25 s per word to be readable; captions 2-4 words per group.
- Holds after a key number: 15-30 frames.
- Transitions: 8-15 frames; shader transitions up to 20.
- Music hits: cuts on the beat (`scripts/beatgrid.py` + `cuecheck.py`, `sound.md`), big moments on the
  downbeat of a bar; a camera move ARRIVES on the beat.

## Before building, write the beat sheet

| t (s) | VO | Visual mode | Graphic | Camera | SFX | Music |
|---|---|---|---|---|---|---|

Every row must change at least one column from the previous row.
