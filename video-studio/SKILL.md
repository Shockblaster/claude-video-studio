---
name: video-studio
description: The entry point for making ANY video with Claude, for any brand or project - short-form Reels / Shorts / TikToks above all, plus explainers, screen walkthroughs, promos, motion graphics, 3D, talking cartoon avatar presenters, kinetic type, captions, AI b-roll, voiceover (English or Hindi), music and sound design. Knows every video tool it relies on and routes each job to the right one, holds the retention playbook (hook, re-hooks, climax, loop, shareability, eyebrow-raisers, topics), the per-video pipeline, the QC gate and the lessons, and improves itself after every video. Use whenever someone wants to make, plan, script, edit, animate, voice, score or review a video or reel, starts a new video chat, or names a brand pack (a skill called <brand>-reels). Load the brand pack too when one exists.
---

# Video Studio

The single entry point for video work. Read this file first in every video chat, then the brand pack (if any),
then `lessons-learned.md` and `lessons.md`. Everything else loads on demand. Works on macOS, Linux and Windows:
every script finds its tools through `scripts/_paths.py` (see `references/toolchain.md`).

**Standing rule: this skill gets better after every video, for its whole lifetime.** See "Self-improvement" at
the bottom. A video is not done until that step is done.

**Quality rule: each new video must beat the last finished one** in every aspect of what is on screen (look,
depth, motion, graphics, transitions, sound, polish). Before building, list what the previous video did and write
down concrete upgrades per aspect. After delivery, record the new baseline in `lessons.md`.

## Start of every video chat (2 minutes)

1. Read `lessons-learned.md` (distilled rules) and `lessons.md` (this owner's dated entries, newest first;
   they override older text in the references).
2. Find the brand pack: a skill named `<brand>-reels`, or a folder with `brand.md` + `MOTION.md`. No pack and a
   new brand: make one with `references/brand-packs.md` (template in `templates/brand-pack-template/`) before
   designing anything.
3. Check the machine (`references/machine-limits.md`). On a small laptop: one render at a time, `--workers 2`,
   close the browser after use.
4. Confirm only what is missing: topic, language, length, platform. Defaults: 9:16 1080x1920 30 fps, 20-45 s,
   the brand pack's language rule.
5. First time on this machine? Run `python -I scripts/smoke_test.py`; it must print SMOKE PASS.

## Route the job

| Need | Use | Notes |
|---|---|---|
| Author / render any video | `/hyperframes` (+ `/hyperframes-cli`) | Default renderer. HTML + GSAP/Three.js, seek-exact, Apache 2.0. Read its `references/types/vertical.md` for reels |
| Ready-made blocks: transitions, captions, charts, 3D, camera moves, overlays | `/hyperframes-registry` | Search the registry BEFORE hand-building any named effect |
| Voice, music, SFX, transcripts, cutouts, grades | `/media-use` | Free local paths only (Kokoro, Openverse). Never its MusicGen fallback for published work, see `references/sound.md` |
| Brand system (brand.md + MOTION.md) | `/brand-intake` | Feeds every charlie947 skill below |
| Turn an idea into a precise build brief | `/motion-brief-writer` | Never invents a figure |
| Copy the moves of a reel you admire | `/reference-to-motion` (+ video-analyzer MCP for frames) | |
| Animated chart / count-up / before-after | `/animated-chart`, `/milestone-reveal` | Values stay exactly as given |
| Premium effects (chart morph, masked type, particles, glass focus, perspective shift, flowing paths) | `/motion-effects` | 16 effects, seek-exact |
| Cinematic 3D opener / hook | `/title-sequence-3d` | Three.js camera through a lit scene |
| Documentary explainer look | `/vox-explainer` | Torn paper, halftone, condensed type |
| One-take story explainer (camera follows a hero element) | `/explainer-engaging`, or `templates/reel-project/` (a proven 80 s one-take world with a talking avatar) | |
| Hype / teaser, beat-locked kinetic type | `/explainer-high-energy` | |
| Motion b-roll over a talking head | `/motion-broll` | One morphing shape, timed to words |
| Beat-synced reel: grid, cue check, original score, pro SFX mix | `scripts/beatgrid.py`, `cuecheck.py`, `score.py`, `beatmix.py` (`references/sound.md`) | DEFAULT for every reel with music. Score = real CC0/CC BY instruments via lemo-opuscar's sampler; SFX = earshot's audited bank placed by its launch preset. Optional install: `setup/setup-audio.*` |
| Sound pass with the bundled CC0 kit / a finished edit | `/sound-effects` + `scripts/pipeline/mix.py` | Older route, still fine |
| A named film style (66: glass product, tilt-shift, paper pop-up, spy titles, dark keynote...), cinematic or 3D | `references/film-styles.md` + `toolchain.md` "Engine chooser" | Styles and techniques from lemo-opuscar (MIT); their demo films are CC BY, never copied |
| Cut a subject out of footage | `/object-separation` | SAM 2 local; pick the smallest model on a small machine |
| Make a 16:9 into a clean 9:16 upload | `/reel-export` | |
| Port Remotion / Lottie / Three.js / AE work | `/remotion-to-hyperframes` | |
| Screen walkthrough / how-to guide for a web app (16:9) | `templates/screen-walkthrough/` (README there) | Real screenshots + rings + cursor + Kokoro VO + chapter lane. Tall pages: capture in slices; Whisper-check every line |
| Edit existing footage (trim, crop, speed, merge, subtitles, QC) | mcp-video (Kinocut) MCP | `video_*`, `sound_qa_loudness`, `shorts_review`, `video_hook_candidates` |
| Study a reference reel (frames, transcript, timing) | video-analyzer MCP | Instagram needs `YTDLP_COOKIES_FROM_BROWSER=chrome` |
| Cartoon avatar presenter that talks | `references/avatars.md` | Two live routes: ChatGPT pose library (`scripts/avatar_track.py`) or an HTML/SVG drawn character animated by GSAP. The hybrid route (AI video body + our face) is shelved |
| Make character / avatar motion feel alive (acting, anticipation, overlap, weight) | `/disney-animation-rule-skill` (block event poses, pick the few principles that fix it) + `/animation-principles` (concrete durations, curves, springs, stagger) | Read both before animating any avatar gesture |
| Animate an SVG character rig (pivots, timelines, acting beats) | `/svg-character-animation` + `/gsap-core` + `/gsap-timeline` | Deterministic: one pure `render(t)` driven by a GSAP clock tween; never `.to()` or overlapping tweens on one property (frames render out of order) |
| AI-generated cinematic b-roll (optional garnish) | `references/ai-broll.md` + `references/browser-ai.md` | Gemini Omni via the Playwright MCP, the user presses Send, ~4 clips/day |
| Still art plates, character sheets, pose libraries | ChatGPT image gen via the Playwright MCP (`references/browser-ai.md`) | One tab, new chat per prompt, sends >= 60 s apart |
| Copy an audience will read (script, caption, hook text) | a de-AI writing skill (e.g. `/humanize`), one light pass for short text | |

Not used on purpose (do not add without asking): Remotion skills (company licence above 3 employees), the
OpenMontage toolchain (AGPL + paid providers; only its MIT `svg-character-animation` instruction skill),
paid inference wrappers, Blender (too heavy for a small laptop), MusicGen (CC-BY-NC), the lemo-opuscar plugin
itself (its rules, sampler and style index are used from a reference clone; the plugin would compete with this
skill), earshot's Gemini critique (uploads audio) and its forge search (needs licensed reference recordings).

## The pipeline (every video)

1. **Brief**: topic, audience, one-line promise, platform, language, length. Every number that will appear on
   screen gets a source in `sources.md` before scripting. No source, no number (illustrative values are labelled
   "illustrative" on screen).
2. **Benchmark + hook + structure**: name 1-2 reference works that set the bar for THIS topic and look (what to
   learn / what not to take). Pick a hook archetype, fill the retention grid (`references/retention.md`), write
   three hook options and three candidate structures; choose by the rubric. A strong look (cinematic, 3D, a brand
   style): choose from `references/film-styles.md` and the engine from `toolchain.md` "Engine chooser".
3. **Script**: spoken lines with beat timestamps. Hindi: Devanagari, acronyms spelled phonetically for TTS
   (`references/voice.md`). One light de-AI pass on on-screen text.
4. **Voice**: record or TTS (`scripts/pipeline/build_vo.py`: per line, placed at measured starts). Tricky words,
   voice speed and music are picked BY EAR by the user on a pick page (`templates/reel-project/pick.html`).
   Measure the real duration: the VO length sets the edit, not the other way round.
5. **Beat grid + beat sheet** (`references/sound.md` "The beat pipeline"): `cues.json` (every cut, pop, landing
   and key word with its lock and SFX role), `scripts/beatgrid.py` (grid fitted to the anchor words, or a stock
   track seeked onto the cues), `scripts/cuecheck.py --snap` (every movable event onto a beat). Then the beat
   sheet, plus a sound design table (ambience, foley, music state per section), one row per 1.5-3 s: time, VO words, visual mode, graphic, SFX, music event, avatar pose (one
   pose per line, chosen to illustrate the line). Pick visuals from `references/visual-grammar.md`; change visual
   mode every 5-7 s at least (re-hook). With it, write the one-line-each STYLE BRIEF (`visual-grammar.md` "The style
   brief") and plan shot sizes, one new element per phrase, and the entity list (everything the VO names gets an image).
6. **Build**: HyperFrames project (start from `templates/reel-project/` or the brand pack's starter). Registry
   blocks first, then the specialist skills above, hand-built last. Word timings: `scripts/pipeline/words.py`;
   named cues + captions: `scripts/pipeline/build_timing.py`. Avatar mouth cues: `scripts/mouth_rhubarb.py`
   (Rhubarb + the script text, all 9 shapes; `mouth_from_audio.py` only for no-script or Hindi). A new face rig
   must pass its lip-seal gate (`references/avatars.md`). Avatar track: `scripts/pipeline/render_chunks.py`.
7. **Draft render**: `npx hyperframes check --json`, fix all errors, then
   `npx hyperframes render --quality draft --workers 2` (long reels: segmented capture, foreground).
8. **QC gate** (`references/qc.md`): `python -I scripts/qc_reel.py out.mp4 --sheet qc.png`,
   `python -I scripts/pace_check.py out.mp4 --mask <avatar box>`, READ EVERY FRAME as contact sheets
   (`scripts/pipeline/sheets.py`) plus the automatic avatar scan (`scripts/pipeline/scan_avatar.py`), watch the
   first 3 s and the climax frame by frame, self-score. Nothing goes to the user before this passes.
9. **Sound**: `scripts/score.py` (original score on the grid) + `scripts/beatmix.py` (earshot SFX on every cue,
   stop-downs, ambience, -14 LUFS mux); `scripts/cuecheck.py` must exit 0; Whisper on the final mix. Older route:
   `scripts/pipeline/mix.py`. Optional judge (run alone): `earshot critique out.mp4`.
10. **User review on a phone**, then the delivery render (`--quality delivery`) and a final QC run. Hand over: MP4
    (with and without music), cover frame, caption text, music credit line, `sources.md`, `licences.md`.
11. **Self-improvement** (below).

## Hard rules

- Never fabricate data, quotes, testimonials or results. Every on-screen claim traces to `sources.md`.
  Illustrative visuals are labelled.
- No em dashes in on-screen text or captions (they read as machine-written).
- Music must have a licence that allows the use (see `references/sound.md`) and is logged in the project's
  `licences.md`. Business accounts cannot use Instagram's trending library.
- Text and faces stay inside the safe box (`references/platform-specs.md`). Every hand and prop stays inside the
  frame.
- Real people as avatars only with their OK; cartoon caricatures, never deceptive photo-real fakes. Stock TTS
  voices are never presented as the person's real voice. AI footage that looks real gets the platform's AI label.
- The brand pack's compliance notes are followed; regulated brands keep a disclaimer slot that their compliance
  team fills, and its wording goes on screen VERBATIM (never rewritten or "fixed").
- Never kill a running render, server or app you did not start without asking.

## References (load on demand)

| File | What is in it |
|---|---|
| `references/toolchain.md` | Every tool: what it is, Mac + Windows install, commands, licences, licence traps |
| `references/machine-limits.md` | Running heavy video work on a small laptop |
| `references/retention.md` | Hook, retention grid, re-hooks, open loops, climax, loop endings, shareability, eyebrow-raisers, topic engine, scoring rubrics |
| `references/visual-grammar.md` | Which graphic for which beat; the premium look; video-not-slides checks, shot sizes, one element per phrase, background menu, living type, minimum text sizes, style brief; pacing; effect ideas |
| `references/sound.md` | The beat pipeline (grid, cues, score, mix), music licence ladder, pro SFX roles, sound design rules, mix targets |
| `references/film-styles.md` | 66 named film styles (lemo-opuscar) by category, engine and use, "make a style your own" |
| `references/voice.md` | TTS options and how to pick; Hindi/Hinglish rules; voice bake-off; by-ear pick pages; Kokoro blending |
| `references/avatars.md` | Cartoon avatar pipeline: pose library, face rig, mouths (Rhubarb + lip seal), placement, gestures, QC |
| `references/browser-ai.md` | ChatGPT image gen + Gemini Omni through the Playwright MCP: queue, rate limits, saving, QA |
| `references/ai-broll.md` | Gemini Omni clips: when, prompts, user-sends flow, saving, watermark scrub, vertical framing |
| `references/platform-specs.md` | IG Reels / YT Shorts / TikTok specs, safe zones, covers, captions, export |
| `references/qc.md` | The QC gate checklist and the self-score rubric |
| `references/brand-packs.md` | How to make a brand pack for a new brand or project |
| `lessons-learned.md` | Distilled rules from many real videos, by topic. Read at start |
| `lessons.md` | This owner's dated lessons (newest first). Read at start, append after every video |

Scripts (run Python helpers with `python -I`):
- `scripts/qc_reel.py` (measured QC + safe-zone contact sheet), `scripts/pace_check.py` (still stretches)
- `scripts/avatar_track.py` (placed corner avatar, one transparent track), `scripts/face_rig.py` +
  `face_paint.py` + `face_patch.py` (face rig, lip seal, long-hair patch), `scripts/pose_consistency.py`
  (pose library gate)
- `scripts/mouth_rhubarb.py` (DEFAULT lip-sync), `scripts/mouth_from_audio.py` (language-free fallback)
- `scripts/pipeline/`: `build_vo.py`, `words.py`, `build_timing.py`, `mix.py`, `sheets.py`, `render_chunks.py`,
  `scan_avatar.py`
- `scripts/smoke_test.py` (proves the toolchain works; must print SMOKE PASS)
- Older avatar routes kept for reference: `puppet_*`, `cutout_*`, `chain_*`, `build_*_scene.py`, `mocap_*`,
  `hybrid_head.py`, `pose_reel.py`, `gesture_plan.py`

## Self-improvement (standing rule, every video)

Before calling any video done:

1. Append a dated entry to `lessons.md`: what worked, what failed, what the user changed or rejected (their
   words), render times, any tool quirk, and the new quality baseline. Be specific enough that a future chat
   avoids the mistake without context.
2. Promote anything that will recur into the right reference file (or a script), and remove text it makes wrong.
   A lesson that appears twice in `lessons.md` must be promoted.
3. When the user reports how a posted video performed (views, watch %, sends, saves, follows), log it in the
   brand pack's `performance.md` and re-rank that pack's hook and topic lists by real results. Real numbers beat
   every heuristic here.
4. Tool changed (new version, new skill, broken command)? Update `references/toolchain.md` and the routing table.
5. Run `python -I scripts/smoke_test.py` and confirm SMOKE PASS.
6. Tell the user in 1-2 lines what the skill learned.

Back up before large rewrites to a folder OUTSIDE `~/.claude/skills/` (e.g. `~/.claude/skills-archive/<date>-video-studio/`):
a copy inside the skills folder registers as a second skill.
