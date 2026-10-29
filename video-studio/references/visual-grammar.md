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

## Pacing defaults (30 fps)

- Cuts / visual changes: every 45-90 frames.
- Text on screen: at least 0.25 s per word to be readable; captions 2-4 words per group.
- Holds after a key number: 15-30 frames.
- Transitions: 8-15 frames; shader transitions up to 20.
- Music hits: cuts on the beat (use `/sound-effects` beat grid), big moments on the
  downbeat of a bar.

## Before building, write the beat sheet

| t (s) | VO | Visual mode | Graphic | Camera | SFX | Music |
|---|---|---|---|---|---|---|

Every row must change at least one column from the previous row.
