# Sound: music, SFX, voice, mix

Sound is half of retention. A film over ~15 s gets music and sound on its visible
actions unless the user asked for silence.

## Music licence ladder (pick the first that fits, log it in `licences.md`)

1. **Platform-native library, added at upload**: Meta Sound Collection on Instagram
   business accounts, YouTube's Shorts audio. Render the video with the music muted (or a
   guide track that is removed), so the platform's licence covers it. Best for
   trend-adjacent sounds. Business accounts cannot use Instagram's general trending
   library.
2. **Mixkit Stock Music Free License**: social posts and ads allowed, no credit required.
   Never register it with Content ID. Curated picks and the download URL pattern:
   `~/.claude/skills/sound-effects/MUSIC.md`.
3. **YouTube Audio Library / Pixabay Music**: check the track's own licence line each
   time (some need a credit, some sit in Content ID). Log the exact track URL.
4. **Original tracks (the brand's sonic identity)**: ACE-Step 1.5 (MIT) on free Google
   Colab GPU. Generate a few on-brand beds once, keep them in the brand pack's assets, and
   reuse them, so the sound becomes recognisable.
5. **Never**: MusicGen output (CC-BY-NC), commercial songs, "royalty-free" tracks without a
   readable licence, Instagram trending audio on a business account.

## SFX
- Bundled CC0 library: `~/.claude/skills/sound-effects/sfx/` (whoosh, click, pop, riser,
  impact, tick, ding, glitch, ambience). `/sound-effects` builds a cue list from the
  timeline and places one real sound per cue. Openverse (via `/media-use`) for more CC0.
- One sound per visual event that matters: whoosh on a move, tick or pop on an element
  landing, riser into the climax, impact on the reveal. Not on every tiny motion.
- Keep SFX 6-12 dB under the voice. Low-end hits sit under the music, not over it.

## Voice processing
- High-pass ~80 Hz, gentle compression, de-ess, normalise. TTS needs less processing than
  a phone recording; a phone recording needs noise reduction first.
- The VO's measured length sets the timeline. Leave 0.2-0.4 s breaths between ideas.

## Mix targets (measure, never guess)
- Final integrated loudness **-16 to -13 LUFS**, true peak **<= -1 dBTP**
  (`/sound-effects` targets -16 LUFS with TP below -4: both pass).
- Music under voice: duck 12-20 dB while the voice speaks, swell back in the gaps and on
  the climax.
- Measure on the exported MP4: `python -I scripts/qc_reel.py out.mp4`, or mcp-video
  `sound_qa_loudness`.

## Beat sync
- Cuts on beats, the climax on a downbeat, the loop point on a bar line.
  `/sound-effects` checks the music's beat grid against the kick drums;
  `npx hyperframes beats` (see `/hyperframes-cli` `references/beats.md`) for
  beat-driven compositions.
