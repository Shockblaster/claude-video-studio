# Voice (Hindi, English, Hinglish)

## Options (all free; licence matters because videos are commercial)

| Engine | Languages | Licence | Where it runs | Notes |
|---|---|---|---|---|
| Kokoro-82M (`npx hyperframes tts`) | EN (US/GB), HI, + others | Apache 2.0 | Local CPU, seconds per line | Installed. HI voices: `hf_alpha`, `hf_beta` (female), `hm_omega`, `hm_psi` (male); pass `-l hi`. No Indian-English accent voice |
| AI4Bharat Indic Parler-TTS | HI, Indian EN, other Indic | Check the model card before use | Colab (slow on this CPU) | Describe the speaker in words (age, pace, tone) |
| Gemini TTS (AI Studio free tier) | HI, Indian EN, many | Gemini API terms (free tier may be used for training) | Cloud, needs the user's AI Studio key | Very natural, style control by prompt; rate-limited |
| edge-tts (Microsoft neural voices) | `hi-IN-SwaraNeural`, `hi-IN-MadhurNeural`, `en-IN-NeerjaNeural`, `en-IN-PrabhatNeural` | Unofficial use of a consumer service: grey area for commercial use | Cloud, no key | Only if the user accepts the risk |
| Human recording | any | owned | phone | Most trust for advice-style content |

No free model allows commercial voice CLONING (XTTS, F5, Fish are non-commercial), so
brand characters get a consistent stock voice, not a clone of a real person.

## Results of a real bake-off (a finance brand, Indian audience; the user's verdicts)
- Kokoro: English `af_heart` (female, American accent) GOOD, picked. Every other Kokoro English
  voice "bad". Kokoro Hindi all to be retried. Kokoro Hinglish (romanised) "fully broken".
- en-IN edge-tts voices skip Devanagari words entirely (a Hinglish line came out half
  length). Use hi-IN voices for Hinglish: they read Devanagari Hindi and Latin English words
  both correctly (verified by transcribing back: "invest", "habit", "Simple, right").
- Indian-accent English candidates: edge-tts en-IN Neerja / Prabhat; Gemini TTS (needs AI
  Studio key); Indic Parler-TTS (Apache 2.0, gated on Hugging Face: needs an HF token,
  heavy on a laptop CPU).

## Rules learned
- Kokoro Hindi reads Latin acronyms badly ("SIP" came out as "इन इस आईपी"). In Hindi
  scripts write acronyms the way they are said: एस-आई-पी, ई-एम-आई, पी-पी-एफ. Numbers as
  words when the reading is ambiguous (₹2,00,000 → "दो लाख रुपये").
- NEVER write Hinglish romanised. Hindi words in Devanagari, English words in Latin, and a
  Hindi (hi-IN) voice reads it. Romanised Hinglish broke completely in Kokoro.
- Always transcribe the TTS output back (video-analyzer `get_transcript` on an MP4 wrap)
  and compare with the script: wrong words show up immediately.
- Speed 0.95-1.1. Faster for hooks, slower for the climax line.

## Kokoro voice blending (option for NEW voices; from the MAKINGAIDOIT kit, 2026-10-29)
kokoro-onnx can mix voice styles, which gives more options than the 54 stock voices:
```python
from kokoro_onnx import Kokoro
k = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
v = 0.6 * k.get_voice_style("af_heart") + 0.4 * k.get_voice_style("af_nicole")
audio, sr = k.create(text, voice=v, speed=1.0, lang="en-us")
```
Use it in a voice bake-off (the user picks by ear), never on an approved voice: keep an approved
voice exactly as it was. Speed 0.95 sounds calmer and 1.1 punchier.

## By-ear picks
- Every tricky word (names, "lakh", acronyms) gets 3-4 spellings rendered and the USER picks by ear.
  Present them on a local HTML pick page: a player and a radio button per option, a "None of these"
  text box, and "Copy my picks". Users found this far easier than a list of file names. Template:
  `templates/reel-project/pick.html`. The same page works
  for voice speed and music.
- Kokoro af_heart: write lakh numbers in words ("forty-nine lakh"); "SIP" as written is fine.
- Whisper read-back first, to drop broken options before the user hears them.

## Voice bake-off (once per brand, per language)
1. Same 2-3 test lines (a hook, an explanation, a number-heavy line) through every
   candidate voice. Files named `<lang>_<engine>_<voice>.wav` in the brand's
   `voice-bakeoff/` folder.
2. The user picks by ear. Record the pick, settings (voice id, speed, lang) and licence in
   the brand pack's `brand.md` under "Voices".
3. Re-run when a new engine appears in `toolchain.md`.

Kokoro command:
`npx hyperframes tts "<text>" -v hm_omega -l hi -s 1.0 -o assets/vo/line01.wav --json`
(a `.txt` path works as input for long scripts).

## Captions from the script, not from ASR
We write the script, so caption text comes from it. Timing comes from word timestamps
(`npx hyperframes transcribe`, needs whisper.cpp, see `toolchain.md`) or, until that is
installed, from the per-line TTS durations (generate one file per line and sum).
