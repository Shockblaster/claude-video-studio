# Film styles: a menu for cinematic, 3D and explainer reels (added 2026-11-01)

Source: lemo-opuscar by LemoLab (github.com/lemomo-ai/lemo-opuscar, code and docs MIT; demo films CC BY 4.0).
Local reference clone (read-only, never build inside it): `<VIDEO_STUDIO_HOME>/tools/lemo-opuscar/` (scripts/_paths.py opuscar_dir()).
Gallery with every demo film: https://lemomo-ai.github.io/lemo-opuscar/

**How to use it.** When a reel wants a strong look (personal brand, cinematic, 3D, a launch), pick 2-3 rows that
fit the TOPIC, show the user the gallery links, let them choose. Then read that style's
`styles/<folder>/STYLE.md` in the clone (its invariants: look, colour, type, motion, camera, sound palette, native
moves, pitfalls) and build it in OUR stack (HyperFrames + render(t), our avatar, our voice, our beat grid).
Rules carried over from opuscar (AGENTS.md "Style and story"):
- `STYLE.md` is fixed; the story is ours. Write our own treatment (3 candidate structures) BEFORE opening the
  style's `DEMO.md` or demo code. Then use the demo only to learn techniques (a brush engine, a rig, a shader, a
  mix), never its story, shots, props or timeline.
- Before delivery, compare with the demo on six points (structure, opening, signature shot, camera path, score
  shape, ending): at least four must differ.
- Their demos are CC BY 4.0: never copy a demo film's frames, characters or music into a reel. Their code (MIT) may
  be adapted with a credit line in the project's `licences.md`.
- 9:16 reels: their films are 1920x1080 at 24 fps; ours stay 1080x1920 at 30 fps. Recompose, don't crop.

Engine column: what OUR build uses (see `toolchain.md` "Engine chooser"). 3D = three.js in the demo.

## Materials & 3D (the cinematic / product look)
| Style | Folder | Engine | Good for | Native move |
|---|---|---|---|---|
| Glass Product Render | glass-product | three.js + post (DOF, GTAO, HDRI) | a product / app / service "hero" reveal | strip-light sweep over glass, caustics |
| Tilt-Shift Miniature | tilt-shift | 2D canvas + blur ramp | a city / process seen as a toy town | the miniature focus band |
| Brick Toy | brick-toy | three.js | build-it-up stories, step counts | bricks snapping together on the beat |
| Paper Pop-up Book | paper-popup | three.js | a journey, a brand story | a page fold that becomes the next scene |
| Low-poly Isometric Island | lowpoly-island | three.js | growth over time (portfolio, habit) | one tile per note, the island grows |
| Memphis Diorama | memphis-diorama | three.js | four phases in one take | the squash-and-spring that turns a season |
| Desktop Flythrough | desktop-flythrough | three.js | an app or workflow story | one object hopping across app cards |

## Information & Keynote (explainers, finance, launches)
| Style | Folder | Engine | Good for | Native move |
|---|---|---|---|---|
| Dark Tech Keynote | dark-keynote | three.js / 2D | launch films, "one feature" reels | hundreds of windows snapping into place |
| Data Storytelling | dataviz | 2D | a real dataset told by the chart itself | the chart as the character |
| Isometric Infographic | iso-infographic | three.js | a process end to end | one iso world, the camera follows the thing |
| Isometric Picture Book | isometric-picture-book | three.js | "why A beats B" with people | the order of boarding / queueing shown |
| Circuit Board | circuit-board | 2D/3D | flows (money, energy, data) | rivers becoming copper traces |
| Transit Map | transit-map | 2D/3D | growth of a network over years | the map that grows line by line |
| Sci-fi Hologram HUD | hologram-hud | three.js | spec walkthroughs | target boxes locking on parts |
| Living Screencast | living-screencast | 2D | a real app demo with a character | the mascot acting inside the UI |

## Evidence Films (every number sourced; fits our no-fabrication rule)
| Style | Folder | Good for |
|---|---|---|
| Data Physicalization | data-physical | numbers stacked as real objects (savings, returns) |
| Exploded Teardown | teardown | "what is inside" a product |
| Satellite Briefing | satellite-briefing | places, maps, before/after |
| Engineering Briefing Board | briefing-board | comparing options on one wall |
| LiDAR Survey / White Model / Microscope / Archive Light Table | lidar-survey, white-model, microscope, archive-lighttable | investigations from real data or documents |

## Edit & Documentary (cut from real footage, documents, data)
Caption News (caption-news: works with the sound off, best fit for silent-autoplay feeds), Broadcast News Package
(news-package), Sports Telestrator (telestrator: freeze, draw, split screen), Visual Investigation,
Constructivist Montage (kino-montage), Time-lapse Symphony (city-symphony: a grid on the sixteenths = beat-locked
montage), Live Countdown Split-screen (countdown), 1920s Newsreel. An Edit & Documentary style gathers its
material FIRST, then writes the treatment.

## Graphic & Type
Swiss Motion Graphics (swiss-motion: every move on the beat), 60s Spy Title Sequence (spy-titles), Art Deco,
Blueprint, Pictogram Motion (beat-locked geometric pictograms), Stained Glass, ASCII / CRT Terminal (CRT pass in
`core/post/crt.js`).

## Hand-drawn & Painting / Print
Whiteboard Explainer, One-line Drawing, Chalkboard, Urban Sketch, Watercolor, Ink Wash, Impasto, Crayon Picture
Book; Risograph, Halftone Dossier, Woodcut, Copperplate Engraving, Silkscreen Travel Poster, Printed Long Take.
(Brush / stroke engines to learn from: `styles/watercolor`, `styles/ink-wash`, `styles/impasto`.)

## Cartoon, Games, Cinema & Eras, East Asian
80s Cel Anime, Mid-century Cartoon, 1930s Rubber Hose, Sci-Fi Sitcom Toon (2D character animation + lip sync:
`styles/scifi-toon`, `styles/cel-anime-80s`); 16-bit Pixel RPG, HD-2D, Microgame Frenzy (a timeline-driven score
with cue checking: `styles/microgame`), Game Show Flat (a rhythm game); 1920s Silent Film, Liminal Found Footage;
Shadow Puppetry, Ukiyo-e, Red Paper-cut, Paper-cut Lightbox.

## Where to look in their code (from their TECHNIQUE.md §12)
| Need | Look at (in the clone) |
|---|---|
| 2D character animation and lip sync | `styles/scifi-toon/`, `styles/cel-anime-80s/` |
| timeline-driven score with cue checking | `styles/microgame/`, `styles/silent-film/` |
| 3D with depth of field and real materials | `styles/brick-toy/`, `styles/paper-popup/`, `core/three/post.js` |
| brush / stroke engine | `styles/watercolor/`, `styles/ink-wash/`, `styles/impasto/` |
| CRT / VHS look | `core/post/crt.js`, `styles/ascii-crt/`, `styles/backrooms/` |
| reading-time check | `core/render/readcheck.mjs` (asks the page for `window.TEXTS(t)`) |

## Make a style your own (for a brand, e.g. the personal brand)
Their flow, adapted (full version: `MY-STYLES.md` in the clone):
1. Plan one question at a time: what it's for (platform, brand colours, logo, fonts, recurring characters); what to
   change, sorted into **safe to change** (palette, type, pace, sound, signature moves), **changes its character**
   (materials and rendering, colour logic, camera grammar) and **can't change** (the style's essence).
2. Summary: each part before / after / cost; nothing written until the user agrees.
3. One style frame with the real code, the original style's frame side by side on a local pick page.
4. A 15-30 s demo with music and SFX (our beat pipeline), checked and fixed once.
5. Keep it: write it into the brand pack as `style.md` (the brand's STYLE.md) + the demo + its source.

## Two more house styles (beta)
| Style | Good for | System |
|---|---|---|
| One-colour editorial | essays and explainers, an idea every ~2 s | one hue ground with a fine weave; true black-and-white cut-out objects with a hue-tinted shadow, 50-60% of the frame empty; condensed heavy key word built letter by letter (0.045 s) with tiny italic connectors around the object; block-dissolve between objects; 1.2%/s camera push |
| Vox / paper collage | city / brand / history stories | sticker-edged cut-outs, printed photos with paper borders, paper grounds; stepped motion at 12 drawings/s with 1-3 px jitter while the camera moves on ones; tiny serif captions, huge type only 2-3 times a film; one colour ground per section |
Material: `scripts/archive.py` (public domain / CC0) + `scripts/photo_treat.py`. Single objects read plainer than
object combinations (scale jokes).
