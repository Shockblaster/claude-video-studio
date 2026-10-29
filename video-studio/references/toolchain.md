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
