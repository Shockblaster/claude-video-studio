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
- Disney's 12 principles of animation via `disney-animation-rule-skill`; timing and easing via
  `animation-principles`.
