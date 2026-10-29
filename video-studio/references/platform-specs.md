# Platform specs and export

## Master format
1080x1920, 30 fps (60 only for very fast motion), H.264 High, yuv420p, bt709, AAC 48 kHz
stereo, 128-256 kbps. `/reel-export` turns a 16:9 or 4:5 into a clean 9:16 upload and
runs an ffprobe check. `qc_reel.py` checks all of this plus loudness.

## Safe zones on 1080x1920 (from `/hyperframes` references/types/vertical.md)
- Top 0-168 px: status and search bar. Nothing important.
- 168-1330 px: every word, face and key graphic.
- Below 1330 px: caption, handle and buttons cover it. Texture or decoration only.
- Right edge: the action rail (like, comment, share) sits over the lower right. Keep text
  ~65 px+ off the right edge, more in the lower half.
- Paid ads reserve more (Meta Reels ads: about 14% top, 35% bottom, 6% sides). Use
  `qc_reel.py --ads` for those.

## Per platform
| | Instagram Reels | YouTube Shorts | TikTok |
|---|---|---|---|
| Length used for explainers | 20-45 s (up to 90 s keeps Reels behaviour) | up to 3 min allowed; 20-45 s still best for explainers | 20-60 s |
| Cover | Pick a frame or upload a 1080x1920 cover; the grid crops it to 3:4 centre | Pick a frame | Pick a frame, add a title |
| Music | Business account: Meta Sound Collection only | Shorts audio library | Commercial Music Library for business accounts |
| AI label | "AI info" for realistic AI | Altered or synthetic content toggle | AI-generated content label |
| Captions | Burn in (most watch muted) | Burn in; auto-captions optional | Burn in |

Re-check these against each platform's current help pages every few months and update
this table plus `lessons.md`.

## Deliverables per video
`final.mp4`, `cover.png` (1080x1920, hook text inside the 3:4 centre crop), `caption.txt`
(post caption + hashtags + music credit line), `sources.md`, `licences.md`.
