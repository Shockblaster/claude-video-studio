# Credits and licences

The files in `video-studio/` written for this skill are MIT licensed (see `LICENSE`). Everything below belongs to
its authors and keeps its own licence. The third-party skills are NOT bundled: `setup/` installs them from their
official repositories.

## Skills this one routes to
| Skills | Repository | Licence |
|---|---|---|
| hyperframes, hyperframes-cli, hyperframes-registry, media-use, remotion-to-hyperframes | https://github.com/heygen-com/hyperframes | Apache 2.0 |
| brand-intake, motion-brief-writer, reference-to-motion, animated-chart, milestone-reveal, motion-effects, title-sequence-3d, vox-explainer, reel-export | https://github.com/charlie947/motion-graphics-skills | MIT |
| motion-broll, sound-effects, explainer-high-energy, explainer-engaging, object-separation | https://github.com/Barty-Bart/motion-graphics | MIT (bundled SFX CC0, fonts OFL) |
| animation-principles | https://github.com/iart-ai/motion-design-skills | see repository |
| disney-animation-rule-skill | https://github.com/vibe-motion/skills | see repository |
| svg-character-animation | https://github.com/calesthio/openmontage | MIT (this instruction skill only) |
| gsap-* (official GSAP skills) | https://github.com/greensock/gsap-skills | see repository |

## Tools
| Tool | Source | Licence |
|---|---|---|
| HyperFrames CLI | heygen-com/hyperframes (via npx) | Apache 2.0 |
| Kokoro-82M TTS (kokoro-onnx) | hexgrad/Kokoro-82M, thewh1teagle/kokoro-onnx | Apache 2.0 / MIT |
| Rhubarb Lip Sync | https://github.com/DanielSWolf/rhubarb-lip-sync | MIT |
| MediaPipe + models | https://github.com/google-ai-edge/mediapipe | Apache 2.0 |
| Whisper (whisper.cpp via HyperFrames; faster-whisper) | ggerganov/whisper.cpp, SYSTRAN/faster-whisper | MIT |
| ffmpeg | https://ffmpeg.org | LGPL/GPL (installed separately) |
| GSAP (loaded from a CDN in templates) | https://gsap.com | GSAP standard licence (free) |
| OpenCV, NumPy, SciPy, librosa, Pillow, soundfile, matplotlib | PyPI | BSD / MIT / ISC / HPND / PSF-style |

## Bundled assets
| Asset | Licence |
|---|---|
| Inter (InterVariable.woff2) | SIL OFL 1.1, `video-studio/assets/fonts/OFL-Inter.txt` |
| Mukta, Noto Sans Devanagari | SIL OFL 1.1, licence files beside them |
| Archivo, IBM Plex Mono, Instrument Serif (screen-walkthrough template) | SIL OFL 1.1, licence files beside them |
| `veo-watermark-alpha.png` | a measured alpha map of the generator's visible mark, used only to locate it |
| Example market data in `templates/reel-project/assets/nifty.js` | NSE Nifty 50 daily closes (public market data), fetched Oct 2026, as an example; replace with your own sourced data |

## Ideas and techniques
- Pace check, hook rules and several effect ideas were adapted from the free "MAKINGAIDOIT Free Reel Kit"
  (@makingaidoit).
- The "Video, not slides" rules, shot-size camera, one-element-per-phrase, background menu, living type and minimum
  text sizes in `references/visual-grammar.md` were adapted from bang-motion by Bang Tutorial
  (https://github.com/bangtutorial/bang-motion, MIT, Copyright (c) 2026 Bang Tutorial), translated and condensed.
- Disney's 12 principles of animation via `disney-animation-rule-skill`; timing and easing via
  `animation-principles`.

## Beat sync, scores and sound effects (2026-11-01)
| Project | Repository | Licence | How it is used |
|---|---|---|---|
| lemo-opuscar (LemoLab) | https://github.com/lemomo-ai/lemo-opuscar | MIT (code, docs); CC BY 4.0 (demo films) | Directing rules adapted into `visual-grammar.md`, `qc.md`, `sound.md`; its sampler drives `scripts/score.py` from a reference clone; its 66 styles indexed in `references/film-styles.md` (names and techniques only; no demo films included) |
| earshot (Leon Lin) | https://github.com/Leonxlnx/earshot | MIT | Installed by `setup/setup-audio.*`; its SFX bank and `launch` kit drive `scripts/beatmix.py`; `earshot critique` is the optional sound judge |
| VSCO 2 CE, VCSL (Versilian Studios), FreePats, Karoryfer | via lemo-opuscar's asset release | CC0 1.0 | sampled instruments for `score.py` (downloaded, not bundled) |
| Salamander Grand Piano V3 (Alexander Holm) | via lemo-opuscar | CC BY 3.0 | credit line written to `CREDITS_music.txt` whenever the piano is used |
| MuldjordKit (Lars Muldjord), FreePats version | via lemo-opuscar | CC BY 4.0 | credit line written whenever the drum kit is used |
