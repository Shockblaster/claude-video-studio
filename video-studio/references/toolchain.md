# Toolchain

Everything this skill uses, all free, with the reason each is safe to publish with. `setup/setup-mac.sh` and
`setup/setup-windows.ps1` install all of it. Update this file whenever a tool changes (version, command, breakage).

Where things live (see `scripts/_paths.py`):
- `VIDEO_STUDIO_HOME` (default `~/video-studio`) holds tools, models, smoke tests and scratch files.
- `~/.video-studio/config.json` overrides individual paths (written by the setup scripts).
- Executables are looked up on the PATH first.

## Skills this one routes to (installed by the setup scripts; see `setup/skills.txt`)

| Skills | Upstream repo | Licence |
|---|---|---|
| hyperframes, hyperframes-cli, hyperframes-registry, media-use, remotion-to-hyperframes | heygen-com/hyperframes | Apache 2.0 |
| brand-intake, motion-brief-writer, reference-to-motion, animated-chart, milestone-reveal, motion-effects, title-sequence-3d, vox-explainer, reel-export | charlie947/motion-graphics-skills | MIT |
| motion-broll, sound-effects, explainer-high-energy, explainer-engaging, object-separation | Barty-Bart/motion-graphics | MIT (SFX CC0, fonts OFL) |
| animation-principles | iart-ai/motion-design-skills | see repo |
| disney-animation-rule-skill | vibe-motion/skills | see repo |
| svg-character-animation | calesthio/openmontage (only this MIT instruction skill; the toolkit itself is AGPL + paid providers) | MIT |
| gsap-core, gsap-timeline, gsap-plugins, gsap-utils, gsap-performance, gsap-react, gsap-scrolltrigger, gsap-frameworks (official) | greensock/gsap-skills | see repo |
| humanize (writing passes for on-screen text) | any de-AI writing skill you trust; optional | |

Install or update one: `npx skills add <repo> --skill <name> -g -y -a claude-code`. List a repo's skills with
`--list`. The HyperFrames CLI itself runs from npx at its latest version.

## MCP servers (optional, add them in Claude Code)

| Server | Use for | Gotchas |
|---|---|---|
| Playwright MCP | Driving ChatGPT (still images) and Gemini (Omni video) in the user's OWN logged-in accounts; screen captures for walkthroughs | "Playwright" means this MCP browser, never a script. See `references/browser-ai.md` |
| video-analyzer | Transcripts, frames, bursts and metadata of reference reels | Local audio must be wrapped as MP4 first (ffmpeg, black video). Instagram needs `YTDLP_COOKIES_FROM_BROWSER=chrome` |
| mcp-video (Kinocut) | Editing existing footage, subtitles, QC (`sound_qa_loudness`, `video_quality_check`, `shorts_review`, `video_hook_candidates`) | Its transcription needs `pip install "kinocut[transcribe]"` |

## Local tools

| Tool | macOS | Windows | Notes |
|---|---|---|---|
| ffmpeg / ffprobe | `brew install ffmpeg` | `winget install Gyan.FFmpeg` | Everything uses it |
| Node 20+ | `brew install node` | `winget install OpenJS.NodeJS.LTS` | HyperFrames CLI via npx |
| Python 3.10-3.12 | `brew install python@3.12` | `winget install Python.Python.3.12` | `pip install -r setup/requirements.txt` |
| HyperFrames CLI | `npx hyperframes` | same | `npx hyperframes doctor`. Headless Chrome is cached in `~/.cache/hyperframes/chrome` |
| Kokoro TTS (Apache 2.0) | `npx hyperframes tts "<text>" -v af_heart -o out.wav` | same | 54 voices incl. Hindi (`hf_alpha hf_beta hm_omega hm_psi`, pass `-l hi`). Needs `kokoro-onnx` + `soundfile` in the Python that `HYPERFRAMES_PYTHON` points at |
| Whisper (word timings) | `npx hyperframes transcribe file --model small.en` | same | Builds whisper.cpp on first use. Hindi: `--model small --language hi` |
| faster-whisper | pip | pip | Line-by-line voice read-back checks (templates/screen-walkthrough/tools/check_vo.py) |
| Rhubarb Lip Sync 1.14 (MIT) | release zip `Rhubarb-Lip-Sync-1.14.0-macOS.zip` | `...-Windows.zip` | From github.com/DanielSWolf/rhubarb-lip-sync. DEFAULT lip-sync via `scripts/mouth_rhubarb.py`: per line, `-d` script text, `--extendedShapes GHX`, 1-frame lead, ~10 s per line. Wants 16-bit PCM WAV (the script converts). macOS: clear quarantine with `xattr -dr com.apple.quarantine <folder>` |
| MediaPipe models | `face_landmarker.task`, `pose_landmarker_heavy.task`, `hand_landmarker.task` | same | Downloaded by setup into `<home>/tools/mediapipe` (Google's storage URLs in the setup scripts) |
| Fonts | bundled in `assets/fonts` | same | Inter, Mukta, Noto Sans Devanagari (OFL). Point `VIDEO_STUDIO_FONTS` at a brand's own fonts |
| Pace check | `python -I scripts/pace_check.py reel.mp4 --mask <avatar box> --mask <caption box>` | same | Lists still stretches over 1 s and still frames in the first 2 s. ~1 min for 80 s |
| edge-tts (optional) | `pip install edge-tts` | same | Microsoft neural voices incl. Indian English. GREY licence (unofficial use of a consumer read-aloud service): only if the user accepts the risk |
| Parakeet ASR (optional) | `npx hyperframes models install parakeet` | same | English/European only |
| **Beat + sound pipeline (2026-11-01)** | `scripts/beatgrid.py`, `cuecheck.py` (system Python `-I`); `score.py`, `beatmix.py` (AUDIO venv) | See `sound.md` "The beat pipeline". Grid fit on a 97 s track ~20 s; score 10 s ~11 s; mix + mux ~2 min first run (kit render), cached after |
| AUDIO venv | `<VIDEO_STUDIO_HOME>/tools/earshot/.venv` (setup/setup-audio.*) | Python 3.12 + earshot 0.4.0 (editable), torch 2.15 CPU, librosa 1.0, soxr. Always run with `-X utf8` (cp1252 console) |
| earshot 0.4.0 (MIT) | `<VIDEO_STUDIO_HOME>/tools/earshot` (clone @591fa3e) | `sfx list/render/check`, `kit init/render/check/audition`, `measure`: no models. `critique/timeline/sheet/describe/match`: CLAP + AST models (1.1 GB, `.cache/hf` in the tool folder; `doctor --fetch`). MCP server exists (`pip install -e .[mcp]`), not registered |
| lemo-opuscar (MIT code, CC BY demos) | `<VIDEO_STUDIO_HOME>/tools/lemo-opuscar` (clone @bebbbe1, reference only: never build inside it) | Sampler + pluck + sfx (`core/audio`), three.js post (`core/three/post.js`), CRT pass, readcheck, 66 styles (`references/film-styles.md`). Sample libraries in `core/audio/instruments/` (1.28 GB): vsco2ce, vcsl, freepats (CC0), salamander (CC BY 3.0). Fetch more: `python -X utf8 -I <fetch logic from tools/fetch.sh>` (the .sh needs a POSIX python3 path; on Windows run its Python block, see lessons 2026-11-01). Karoryfer (erhu, jazz bass, alto sax) not fetched |

## Engine chooser: which tool makes which kind of video (2026-11-01)

Compare before every new kind of video; the user plans 3D and cinematic work. Times measured on this laptop.

| Need | Best engine here | Quality ceiling | Render cost (a 6 GB laptop) | Licence |
|---|---|---|---|---|
| Reels: kinetic type, cards, charts, one-take worlds, avatar compositing | **HyperFrames** (HTML + GSAP render(t)) | high; seek-exact; registry blocks | 10 s 1080x1920 draft ≈ 1.5 min (`--workers 2`) | Apache 2.0 |
| 3D shots inside a reel (product hero, diorama, isometric world, title) | **three.js inside HyperFrames** (`/title-sequence-3d`, `/threejs-webgl`) + opuscar's `core/three/post.js` ideas: physical DOF, GTAO, bloom, colour grade, 2x supersample, a Poly Haven HDRI at low intensity + soft area lights | near "rendered" look with post; hardware WebGL via ANGLE/D3D11 | heavy: budget 2-4x a 2D reel; render 2x then downsample only for hero shots | MIT / CC0 assets |
| Full cinematic film in one named style (66 styles) | **opuscar's method in our stack**: their `STYLE.md` + techniques, our HyperFrames render, our beat grid | their gallery is the bar (`references/film-styles.md`) | as above | MIT code; demos CC BY (never copy) |
| Real-looking b-roll (people, places, nature) | **Gemini Omni via Playwright** (`ai-broll.md`) | photoreal, 8 s clips, watermark scrub | ~4 clips/day, user presses Send | platform terms; AI label when it looks real |
| Still plates, character art, poses | **ChatGPT image gen via Playwright** | best character consistency we have | 60 s between sends | user's account |
| Rigged true 3D characters | not here (Blender rendering too heavy; VRM only after 2D is proven) | n/a | n/a | n/a |
| Editing existing footage | mcp-video (Kinocut) | n/a | fast | MIT |
| Music | `scripts/score.py` (original, beat-locked) > platform library > Mixkit (seeked by `beatgrid.py`) | real sampled instruments | 10 s ≈ 11 s | CC0 / CC BY credit lines |
| SFX | earshot bank via `beatmix.py` | pro-measured placement | seconds | MIT |
Rule: pick the cheapest engine that reaches the look; one 3D hero shot inside a 2D reel beats a whole 3D reel
that renders for an hour. Every new engine or style gets a row here and a line in `lessons.md`.

## Machine limits (measure YOUR machine and write the numbers here)

The skill was built on a 6 GB RAM laptop with an integrated GPU. What worked there and still helps on bigger machines:

- Render with `--workers 2`. Each worker is a Chrome (~256 MB). Budget ~5-6 min per 30 s reel at draft quality,
  more with heavy Three.js. An 80 s one-take reel took ~10-11 min (draft) and ~23 min (delivery).
- Run ONE heavy job at a time: render, avatar track or browser session. Close the Playwright browser after use.
- Long renders run as FOREGROUND chunks (`--only` / segmented capture with `HF_SEGMENTED_CAPTURE=true --resume`).
  When RAM ran low, long background jobs were killed and a 45 min render was lost.
- `export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` before numpy-heavy scripts when memory is tight.
- Give avatar_track.py a plan holding only the poses in the range: it loads every pose up front
  (`scripts/pipeline/render_chunks.py` does this).
- If memory still fails, ask the user what to close. Never kill a process you did not start.
- No local Blender rendering and no local music or voice-clone models on a small laptop. Use a free cloud GPU
  (e.g. Colab) if needed.
- See `references/machine-limits.md` for the full checklist.

## Licence traps (why some free things are banned)

- MusicGen weights: CC-BY-NC. It is media-use's local music fallback; do NOT install its deps, so media-use skips
  generated music instead of using it.
- XTTS-v2 (CPML), F5-TTS weights, Fish Speech: non-commercial. No free commercial voice cloning exists, so brand
  voices are stock TTS voices, not clones of real people.
- Remotion: free only for individuals and companies up to 3 people.
- Mixkit music: allowed on social and ads, but never register it with Content ID.
- Instagram's trending music library: personal accounts only. Business accounts get Meta Sound Collection.
- Brand fonts (e.g. ITF FFL fonts): embedding in rendered video is usually fine, sharing the font files is not.
