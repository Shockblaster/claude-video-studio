# Video Studio: a Claude Code skill for making videos

A complete, free, local video-making system for [Claude Code](https://claude.com/claude-code), on macOS and Windows.
Ask Claude for a reel, explainer, screen walkthrough or talking cartoon presenter, and this skill handles every
step:
- routes the job to the right tool;
- runs the pipeline (brief, sources, hook, script, voice, beat sheet, build, render, sound);
- checks every frame before you see anything;
- learns from every video it makes.

It was built and battle-tested on real client reels (finance explainers with a talking cartoon presenter,
one-take camera worlds, real-data charts) and screen walkthroughs, on a 6 GB laptop.

## What you can make
- **Short-form reels** (9:16, Instagram / YouTube Shorts / TikTok), with hooks, re-hooks, a climax and a loop
  ending from a retention playbook.
- **Talking cartoon presenters**:
  - a ChatGPT-generated pose library of your character, with a face rig, blinks and phoneme-accurate lip-sync
    (Rhubarb + the script), placed in a fixed corner;
  - or an SVG character animated from code.
- **One-take explainer worlds**: the camera travels between story cards as a hero object hops along the
  narration.
- **Data charts** from real sources, count-ups, stamps, morphs, 3D openers (via the routed HyperFrames and
  motion skills).
- **16:9 screen walkthroughs** of a web app: real screenshots, rings, cursor, zooms, chapter lane, voice.
- **Voice-over** with free local TTS (Kokoro), word timings, captions and a measured -14 LUFS mix.
- **Hindi lip-sync without Rhubarb** (`mouth_phonemes.py`, espeak phonemes + word timings, all 9 mouth shapes), and
  a voice-first mix that keeps music and effects under every spoken word.
- **Checks before anyone sees it**: how the reel moves against 71 measured reference reels (`motion_score.py`),
  every spoken or on-screen number traced to `sources.md` (`number_check.py`), and free public-domain / CC0 images
  with a licence record for each (`archive.py`).
- **Beat-synced reels**: one beat grid fitted to the key spoken words, every cut and pop snapped onto it and
  gated to within one frame, an original score written on that grid with real CC0 / CC BY instruments, and
  professional sound effects placed the way launch films place them ([earshot](https://github.com/Leonxlnx/earshot),
  optional install).
- **Cinematic and 3D looks** from a menu of 66 named film styles ([lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar))
  and an engine chooser (HyperFrames, three.js with depth of field, AI b-roll).
- Optional AI b-roll and art through your own ChatGPT / Gemini accounts (no API keys).

Everything renders locally with [HyperFrames](https://github.com/heygen-com/hyperframes) (HTML + GSAP/Three.js,
frame-exact). No paid services are required.

## Install

You need Claude Code, git, and about 3 GB of disk.

**macOS** (Homebrew needed):
```bash
cd video-studio-share
bash setup/setup-mac.sh
```

**Windows** (PowerShell; winget needed, which ships with Windows 10/11):
```powershell
cd video-studio-share
powershell -ExecutionPolicy Bypass -File setup\setup-windows.ps1
```

The setup script:
1. installs ffmpeg, Node and Python if missing;
2. creates a Python venv in `~/video-studio/venv`;
3. downloads Rhubarb Lip Sync and the MediaPipe models;
4. copies the skill into `~/.claude/skills/video-studio`, backing up any existing copy;
5. installs the ~30 third-party skills it routes to, from their official repos;
6. writes `~/.video-studio/config.json` and runs a smoke test that must print `SMOKE PASS`.

Set `VIDEO_STUDIO_HOME` before running it to use another folder. Pass `--no-skills` / `-NoSkills` to skip the
third-party skills.

**Optional: beat sync and pro sound** (about 3 GB more: earshot with CPU torch, the lemo-opuscar sampler and
1.3 GB of CC0 / CC BY instrument samples):
```bash
sh setup/setup-audio.sh                      # macOS / Linux; add --with-models for earshot's 1.1 GB listening models
powershell -ExecutionPolicy Bypass -File setup\setup-audio.ps1   # Windows; -WithModels likewise
```

Optional MCP servers, added in Claude Code, unlock more:
- the **Playwright MCP**: generate art and AI clips in your own logged-in ChatGPT/Gemini, and capture app
  screens;
- **video-analyzer**: study reference reels;
- **mcp-video**: edit existing footage.

## First video
In Claude Code, say for example:

> /video-studio Make a 40 s reel for my tea shop: "Why your green tea tastes bitter". Light, warm look.

Claude will:
1. ask only for what is missing;
2. set up a brand pack for your brand (see `video-studio/templates/brand-pack-example/` for a filled-in
   fictional one);
3. write `sources.md` before any number appears;
4. offer three hooks;
5. let you pick tricky pronunciations, voice speed and music by ear on a local pick page;
6. build, render a draft, and check every frame;
7. show it to you, and only then render the final.

## What is in the folder
```
README.md, CREDITS.md, LICENSE
setup/                      setup-mac.sh, setup-windows.ps1, requirements.txt, skills.txt
video-studio/               the skill (copied into ~/.claude/skills/ by setup)
  SKILL.md                  entry point: routing table, pipeline, hard rules, self-improvement loop
  lessons-learned.md        distilled rules from many real videos
  lessons.md                your own lessons (empty, grows with every video)
  references/               toolchain, retention, visual grammar, sound, voice, avatars, browser AI, AI b-roll,
                            platform specs, QC, brand packs, machine limits
  scripts/                  QC, pace check, avatar track, face rig + lip seal, lip-sync (Rhubarb), pose gate,
                            pipeline/ (voice, word timings, captions, mix, sheets, chunked avatar render, avatar
                            scan), broll/ (AI clip clean-up + watermark check), browser/ (ChatGPT/Gemini helpers)
  templates/                reel-project (one-take world + avatar), screen-walkthrough, brand-pack-template,
                            brand-pack-example (fictional), cartoon-avatar, puppet prompts
  assets/                   OFL fonts (Inter, Mukta, Noto Sans Devanagari), the Veo watermark alpha map
```

## Principles baked in
- Never fabricate data, quotes, testimonials or results. Every on-screen number traces to a source;
  illustrative maths is labelled.
- Real people appear as avatars only with their consent, as clear cartoon caricatures. Stock voices are never
  passed off as the person's voice. Photo-real AI footage gets the platform's AI label.
- Music only with a licence that allows the use. No non-commercial models (MusicGen, voice clones).
- Every frame is checked before anyone sees the video. Each new video must beat the last one.

## Tested
- **Windows 11:** set up and smoke-tested, including the voice, lip-sync, face rig, caption, mix and walkthrough
  pipelines.
- **macOS:** the setup uses only standard Homebrew/pip steps and the scripts are cross-platform, but it was not
  run on a Mac before release. If something breaks there, the fix usually belongs in `scripts/_paths.py` or
  `setup/setup-mac.sh`.

## Licence
Our own files are MIT (see `LICENSE`). The third-party skills, tools, fonts and sounds keep their own licences
(see `CREDITS.md`).
