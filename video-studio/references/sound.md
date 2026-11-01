# Sound: beat grid, music, SFX, voice, mix

Sound is half of retention. A reel over ~15 s gets music and sound on its visible actions unless the user asked
for silence. **Every reel is beat-synced** (user goal, 2026-11-01): the music grid comes first and the edit
locks to it. Claude can't hear: every sound decision is measured, and the user gets 5 timestamps to check with
headphones.

Sources of these rules: lemo-opuscar DIRECTOR.md §6-7 and TECHNIQUE.md §3-6 (MIT,
github.com/lemomo-ai/lemo-opuscar); earshot docs/SFX.md (MIT, github.com/Leonxlnx/earshot); our own reels.

## The beat pipeline (default for every reel with music)
Audio tools run in the AUDIO venv (`setup/setup-audio.sh` or `.ps1`; path from `scripts/_paths.py audio_python()`; earshot,
soxr, librosa, torch-cpu). Grid and check tools run in the system Python with `-I`.

1. **VO first** (the voice sets the length). Word times from faster-whisper (`base.en`, 1 thread on this laptop).
2. **cues.json**: one row per moment that deserves a sound or a beat:
   `{"t", "type", "desc", "lock", "role"}`.
   - `lock`: `beat` = a visual we can move (cut, pose pop, card landing, node tick) → must sit on a beat;
     `anchor` = a spoken word that must ALSO land on a beat (the hook word, the reveal word) → the grid is fitted
     to it; `word` = tied to speech, never moved, the grid ignores it; `free`.
   - `role` = an earshot kit role (below). No role, no sound.
3. **The grid** (`scripts/beatgrid.py` → `timeline.json`):
   - original score: `--fit-bpm 90 130 --cues anchors.json --dur <vo>`: picks bpm + phase so the anchor words
     land on beats (test reel: 115.25 bpm, three anchor words within 30 ms);
   - stock track: `--music track.mp3 --cues cues.json --dur <vo>`: fits ONE uniform grid to the track (beat
     trackers miss intro beats: on Mixkit #431 librosa said 92 bpm, the fitted grid 140.03, which both halves of the
     track confirm) and picks the seek point whose beats meet the cues.
4. **Snap the edit**: `python -I scripts/cuecheck.py --timeline timeline.json --cues cues.json --snap snapped.json`
   moves every `beat` event to its nearest beat; put those times into the avatar plan (pose `start`s), the
   camera keys and the animation timings. Rule: a camera move ARRIVES on the beat (the landing is the event), a
   pop starts on it, a whoosh peak lands just after it.
5. **Music**: `$AP scripts/score.py --timeline timeline.json --cues cues.json --out music/ --style pop|calm|cinematic
   --key D` writes an original score ON the grid: hits on `hit`/`drop`/`reveal` cues (drums rest the 2 beats
   before = the stop-down), accents on beat / anchor cues, a resolving last bar for the loop, the low end set to
   -3 dB (20-120 Hz vs the rest). Real instruments (sampler below). Or a licensed track (ladder below), seeked by
   step 3.
6. **Mix**: `$AP scripts/beatmix.py --vo vo.wav --music music/music.wav --cues cues.json --timeline timeline.json
   --key D --out sound/ --dur <s> --video silent.mp4 --mux final.mp4` → earshot launch-kit SFX on every cue,
   compressed voice, music under it, stop-downs, two-pass loudnorm to -14 LUFS, `sound/SOUND.md` with every
   placement and the 5 cues to check by ear.
7. **Gate**: `cuecheck.py` exits 0 (every beat / anchor event within 1 frame), `qc_reel.py` passes, Whisper
   reads the final mix back.

## Music licence ladder (pick the first that fits, log it in `licences.md`)
1. **Original score from our own grid** (`scripts/score.py`, new default for brand reels): beat-locked by
   construction, no Content ID risk, the brand's own sound. Samples: VSCO 2 CE, VCSL, FreePats (CC0, no credit
   needed); Salamander piano (CC BY 3.0) and MuldjordKit drums (CC BY 4.0) REQUIRE the credit line the script
   writes to `CREDITS_music.txt`: paste it into the caption or `licences.md`.
2. **Platform-native library, added at upload** (Meta Sound Collection, YouTube Shorts audio) for trend-adjacent
   sounds: render with a guide track that is removed. Business accounts cannot use Instagram's trending library.
3. **Mixkit Stock Music Free License**: social posts and ads allowed, no credit; never register with Content ID.
   Picks: `~/.claude/skills/sound-effects/MUSIC.md`. Run step 3 with `--music` to seek it onto the cues.
4. **YouTube Audio Library / Pixabay Music**: check each track's licence line; log the URL.
5. **ACE-Step 1.5 (MIT) on Colab**: for a genre the sampler can't do (vocals, EDM drops).
6. **Never**: MusicGen output (CC-BY-NC), commercial songs, "royalty-free" without a readable licence, Instagram
   trending audio on a business account.

## SFX: professional, placed like pro launch films
- **Default: earshot's bank** (252 audited sounds made in code, MIT; installed by
  `setup/setup-audio.*` into `<VIDEO_STUDIO_HOME>/tools/earshot`, no models needed for `sfx`/`kit`). `beatmix.py` builds a kit from the
  `launch` preset: per role its level over the music bed, its offset against the cut and its minimum gap, all
  medians measured on professional launch films:

  | role | sound | over bed | vs the cut | use for |
  |---|---|---|---|---|
  | whoosh.short / .long | whoosh_fast/crisp, whoosh_big/thump | 9 / 8.5 dB | peak +37 / +3 ms | camera whips, scene moves |
  | pop | ui_pop/soft | 8.5 dB | +4 ms | pose pops, cards arriving |
  | hit / drop | cut_hit/punch, cut_hit/kick | 7.5 / 7 dB | 0 | the reveal, the climax |
  | riser / swell | riser/dark, reverse_swell/dark | 8 / 9.5 dB | -23 / +42 ms | once a reel, into the section change |
  | tick, tock, click, snap | pro_hover_tick, knock/wood, floss_lid, shutter/dslr | 3-8 dB | -40..+9 ms | small UI beats |
  | bell / text | mallet/glock, mallet/pluck (pentatonic) | 7.5 / 4 dB | -20 / 0 ms | counts, steps, a rising motif |
- **The stop-down, not ducking**: before a hit, drop, long whoosh or swell the music dips 6-12 dB over 0.3-0.5 s
  and comes back on the hit (53 % of strong hits in pro films follow such a dip); nothing ducks under every
  effect.
- **Restraint**: one gesture at a time; riser / swell about once a reel; runs keep their gap with one accent at
  the end. Not every tiny motion gets a sound.
- Tonal SFX (bell, text) must be in the score's key: pass `--key`.
- Other sources when the bank lacks a sound: the bundled CC0 kit `~/.claude/skills/sound-effects/sfx/` and
  Openverse CC0 (`/media-use`); `earshot sfx render <id> --dur --apex --pitch` aims a single bank sound at a moment.
- **Not a sound library**: realsfx.com is a UK practical-effects company (rain, fire, explosions on set), no
  downloads, no licence (checked 2026-11-01).

## Sound design rules (opuscar DIRECTOR.md §6, adopted)
- Every visible action that matters has a sound, matched to its material (paper, wood, glass, metal).
- Three layers: ambience, foley (tied to actions), music. Duck music under dialogue and key foley.
- At least two real near-silences before the turn or the peak; the first sound after it is one of the most
  important in the reel.
- Sound as a transition at least twice: bring the next scene's sound in early (J-cut) or let the last one run over
  the cut (L-cut).
- No generic "piano and strings": score in the instruments of the style.
- Write a **sound design table** in the beat sheet: per section the ambience bed, the main foley, the music state.

## Voice processing
- Compress the TTS first (beatmix: 3:1 at -24 dB, RMS-linked), THEN balance by RMS: music about 14 dB under the
  speaking voice (opuscar says ~10 dB; on phone speakers 12-16 keeps every word clear), +4 dB in gaps >= 0.5 s.
- Names Kokoro gets wrong: force phonemes (`k.create(ipa, is_phonemes=True)`, a per-person lexicon). Every line read back by Whisper; the FINAL MIX too.

## Mix targets (measure on the exported MP4, never guess)
- Integrated **-16 to -13 LUFS** (beatmix masters to -14), true peak **<= -1 dBTP**.
- Low end: 20-120 Hz about -3 dB relative to everything above (score.py sets it; measure a stock track too).
- `python -I scripts/qc_reel.py out.mp4`; mcp-video `sound_qa_loudness`; `ffmpeg -af ebur128`.

## Optional: earshot listening (heavy, run alone)
`earshot critique final.mp4`, `earshot timeline final.mp4 --cues cues.json`, `earshot sheet final.mp4 -o s.png`
load two models (CLAP + AudioSet tagger, 1.1 GB, cached in the tool folder). Only with the Playwright browser and
renders closed; read the scorecard as evidence, never as "it sounds good" (earshot's own Goodhart warning).
