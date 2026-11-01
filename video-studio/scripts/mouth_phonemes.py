#!/usr/bin/env python3
"""Phoneme mouth cues WITHOUT Rhubarb: espeak-ng phonemes of the SCRIPT TEXT, timed by the word timings.

Why: Rhubarb 1.14 ships only an x86_64 macOS build, so on Apple Silicon it needs Rosetta. This script
uses only what the venv already has (espeak-ng through phonemizer + espeakng-loader, as Kokoro does;
faster-whisper only when no transcript exists). Word times come from Whisper, the order of sounds inside
a word from espeak, their lengths from per-sound weights, and the audio's loudness snaps words onto the
real speech. All 9 Rhubarb shapes (A-H, X), and it also works for Hindi (--lang hi), which Rhubarb can't.
Output is Rhubarb JSON, the same post-processing as mouth_rhubarb.py, so the avatar takes it unchanged.

  per-line (preferred; same inputs as mouth_rhubarb.py):
    python -I mouth_phonemes.py --lines-dir vo/lines --starts vo/starts.json -o avatar/mouth.json [--lang hi]
    Word times are read from vo/tr/NN/transcript.json (written by pipeline/words.py) when present,
    else faster-whisper runs here (--model, default small like words.py; downloads once into ~/.cache/huggingface).
  single file:
    python -I mouth_phonemes.py --wav vo.wav --text script.txt -o mouth.json [--transcript t.json]

Accuracy: word boundaries are as good as Whisper's (loudness-corrected); sounds inside a word are placed
by weight, not heard, so long words are a little less exact than Rhubarb. Check closures (A) on M/B/P.
"""
import argparse
import difflib
import json
import pathlib
import subprocess
import sys
import unicodedata

import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mouth_rhubarb import polish, to_frames, trim_offset  # noqa: E402  (shared post-processing)

# IPA sound -> Rhubarb shape(s) (Preston Blair set, as Rhubarb documents them):
# A closed (M B P), B clenched teeth (most consonants, EE), C open (EH AE), D wide (AA), E rounded (AO ER),
# F puckered (UW OW W), G teeth on lip (F V), H tongue up (L), X rest.
DIPHTHONGS = {"aɪ": "DB", "aʊ": "DF", "ɔɪ": "EB", "oʊ": "EF", "əʊ": "CF", "eɪ": "CB", "ɪə": "BC", "eə": "CC",
              "ʊə": "FC", "aɪə": "DBC", "aʊə": "DFC"}
AFFRICATES = {"tʃ", "dʒ", "ts", "dz"}
VOWEL = {"i": "B", "ɪ": "B", "ᵻ": "B", "y": "B", "ɨ": "B", "e": "C", "ɛ": "C", "æ": "C", "ə": "C", "ɐ": "C",
         "ʌ": "C", "a": "D", "ɑ": "D", "ɒ": "E", "ɔ": "E", "o": "E", "ɜ": "E", "ɚ": "E", "ɝ": "E", "œ": "E",
         "ø": "F", "u": "F", "ʊ": "F", "ɯ": "F", "ʉ": "F"}
CONS = {"p": "A", "b": "A", "m": "A", "ɱ": "G", "f": "G", "v": "G", "ʋ": "G", "l": "H", "ɭ": "H", "ʎ": "H",
        "w": "F", "ʍ": "F"}
CARRY = {"h", "ɦ", "ʔ"}             # breath / glottal: no shape of their own, take the next sound's
STOPS = set("ptkbdgcɟqʈɖʔ")
MODS = set("ːˑʰʲʷˠˤ̩̪̥̃ˈˌ‿-") | {"̃", "̩", "̪", "̥", "˞"}
SILENCE_DB = -40                     # frame RMS below peak - 40 dB counts as silence


def espeak(lang):
    import espeakng_loader
    from phonemizer.backend import EspeakBackend
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    EspeakWrapper.set_library(espeakng_loader.get_library_path())
    EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
    return EspeakBackend(lang, with_stress=False, preserve_punctuation=False)


def sounds(ipa):
    """IPA string -> [(shape, weight)] in order."""
    out, i = [], 0
    while i < len(ipa):
        ch = ipa[i]
        if ch in MODS or unicodedata.combining(ch) or ch.isspace():
            if ch == "ː" and out:                        # long sound: hold it longer
                out[-1] = (out[-1][0], out[-1][1] * 1.5)
            i += 1
            continue
        for n in (3, 2):
            seg = ipa[i:i + n]
            if seg in DIPHTHONGS:
                shapes = DIPHTHONGS[seg]
                out += [(s, 1.6 / len(shapes)) for s in shapes]
                i += n
                break
            if n == 2 and seg in AFFRICATES:
                out.append(("B", 0.9)); i += 2
                break
        else:
            if ch in VOWEL:
                out.append((VOWEL[ch], 1.0))
            elif ch in CARRY:
                out.append(("?", 0.4))
            elif ch in CONS:
                out.append((CONS[ch], 0.7))
            elif ch.isalpha():
                out.append(("B", 0.55 if ch in STOPS else 0.7))
            i += 1
    for k in range(len(out) - 1, -1, -1):              # h / ʔ copy the following shape (or open slightly)
        if out[k][0] == "?":
            nxt = next((s for s, _ in out[k + 1:] if s != "?"), "C")
            out[k] = (nxt, out[k][1])
    return out


def norm(w):
    return "".join(c for c in unicodedata.normalize("NFC", w).lower() if unicodedata.category(c)[0] in "LMN")


def load16k(path):
    """16 kHz mono float32 via ffmpeg. faster-whisper 1.2.1 decodes files with PyAV and passes
    metadata_errors=, which the installed PyAV 19 rejects (TypeError); handing it an array skips PyAV."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def whisper_words(wav, lang, model):
    from faster_whisper import WhisperModel
    global _WM
    if "_WM" not in globals():
        _WM = WhisperModel(model, device="cpu", compute_type="int8")
    # no initial_prompt: feeding the script back in makes Whisper repeat it (fake words past the audio)
    segs, _ = _WM.transcribe(load16k(wav), language=lang[:2], word_timestamps=True,
                             condition_on_previous_text=False, vad_filter=False, beam_size=5)
    return [{"text": w.word.strip(), "start": w.start, "end": w.end} for s in segs for w in s.words]


def align(script_words, weights, heard):
    """Give every script word a (start, end) from the heard words; unmatched words share the gap by weight."""
    n = len(script_words)
    t = [None] * n
    a = [norm(w) for w in script_words]
    b = [norm(w["text"]) for w in heard]
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                t[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif op == "replace":                           # e.g. "49" heard for "forty-nine": share the span
            s, e = heard[j1]["start"], heard[j2 - 1]["end"]
            tot, span = sum(weights[i1:i2]) or 1, e - s
            for k in range(i1, i2):
                d = span * weights[k] / tot
                t[k] = (s, s + d); s += d
    k = 0                                                # words nobody heard: fill between neighbours
    while k < n:
        if t[k] is not None:
            k += 1
            continue
        j = k
        while j < n and t[j] is None:
            j += 1
        s = t[k - 1][1] if k > 0 else (heard[0]["start"] if heard else 0.0)
        e = t[j][0] if j < n else (heard[-1]["end"] if heard else s + 0.3 * (j - k))
        if e <= s:
            e = s + 0.08 * (j - k)
        tot, span = sum(weights[k:j]) or 1, e - s
        for m in range(k, j):
            d = span * weights[m] / tot
            t[m] = (s, s + d); s += d
        k = j
    return t


def voiced_mask(wav, hop=0.01):
    y, sr = sf.read(str(wav), dtype="float32")
    y = y.mean(1) if y.ndim > 1 else y
    h = int(sr * hop)
    n = max(1, len(y) // h)
    rms = np.sqrt(np.mean(y[:n * h].reshape(n, h) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-12))
    return db > SILENCE_DB, hop


def snap(times, voiced, hop):
    """Pull word edges onto the speech: a start sitting in silence moves to the first voiced frame, a start
    Whisper put late (mid-sound, typical after a pause) moves back to that sound's onset, a long silent
    tail is cut, and short gaps between words are bridged (speech has no rests inside a phrase)."""
    out = []
    n = len(voiced)
    prev_end = 0.0
    for s, e in times:
        a, b = int(s / hop), max(int(s / hop) + 1, int(np.ceil(e / hop)))
        a, b = min(a, n - 1), min(b, n)
        seg = np.flatnonzero(voiced[a:b])
        if len(seg):
            s2 = (a + seg[0]) * hop
            e2 = min(e, (a + seg[-1] + 1) * hop + 0.03)
            if e2 - s2 >= 0.04:
                s, e = s2, e2
        k = int(round(s / hop))
        if 0 < k < n and voiced[k]:
            j = k
            while j > 0 and voiced[j - 1] and (j - 1) * hop >= prev_end and k - j < 50:
                j -= 1
            if j > 0 and not voiced[j - 1] and j * hop >= prev_end:   # a real onset after silence, not the last word
                s = j * hop
        out.append([s, e])
        prev_end = e
    for k in range(len(out) - 1):
        out[k][1] = min(out[k][1], out[k + 1][0])
        if 0 < out[k + 1][0] - out[k][1] < 0.12:
            out[k][1] = out[k + 1][0]
    return out


def line_cues(wav, text, backend, lang, model, transcript):
    words = text.split()
    ipa = backend.phonemize(words, strip=True) if words else []
    snd = [sounds(p) for p in ipa]
    weights = [sum(w for _, w in s) or 0.5 for s in snd]
    heard = transcript if transcript is not None else whisper_words(wav, lang, model)
    voiced, hop = voiced_mask(wav)
    cues = []
    for (s, e), ss in zip(snap(align(words, weights, heard), voiced, hop), snd):
        parts = speech_parts(s, e, voiced, hop)
        tot, span = sum(w for _, w in ss) or 1, sum(b - a for a, b in parts)
        pos = 0.0                                       # position in speaking time, mapped back onto the clock
        for shape, w in ss:
            d = span * w / tot
            for a, b in clock_spans(parts, pos, pos + d):
                cues.append({"start": a, "end": b, "value": shape})
            pos += d
    return cues


PAUSE = 0.12      # silence this long inside a word is a pause ("I. P. O."); stop closures (p, b, t) are shorter


def speech_parts(s, e, voiced, hop):
    """[s, e] minus the pauses inside it, as a list of (start, end) speaking intervals."""
    a, b = int(s / hop), min(len(voiced), int(np.ceil(e / hop)))
    parts, cur, run = [], s, 0
    for k in range(a, b):
        if not voiced[k]:
            run += 1
            continue
        if run * hop >= PAUSE and k - run > a:            # a real pause ended here: close the part before it
            parts.append((cur, (k - run) * hop)); cur = k * hop
        run = 0
    parts.append((cur, e))
    return [(x, y) for x, y in parts if y - x > 1e-3] or [(s, e)]


def clock_spans(parts, p0, p1):
    """Speaking-time [p0, p1) -> clock intervals across the parts."""
    out, acc = [], 0.0
    for a, b in parts:
        n = b - a
        lo, hi = max(p0, acc), min(p1, acc + n)
        if hi > lo:
            out.append((a + lo - acc, a + hi - acc))
        acc += n
    return out


def load_transcript(p):
    if not p or not pathlib.Path(p).exists():
        return None
    w = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    return w if isinstance(w, list) else w["words"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines-dir"); ap.add_argument("--starts")
    ap.add_argument("--wav"); ap.add_argument("--text"); ap.add_argument("--transcript")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--lang", default="en-us", help="espeak voice: en-us, en-gb, hi, ...")
    ap.add_argument("--model", default="small", help="faster-whisper model when no transcript exists")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--lead", type=int, default=1)
    ap.add_argument("--min-hold", type=int, default=2)
    a = ap.parse_args()
    if a.model == "small" and a.lang.startswith("en"):
        a.model = "small.en"
    backend = espeak(a.lang)
    cues = []
    if a.lines_dir:
        S = json.loads(pathlib.Path(a.starts).read_text(encoding="utf-8"))
        total = S["total"]
        tr = pathlib.Path(a.lines_dir).parent / "tr"
        if "starts" not in S:                            # build_vo.py format: lines = [{i, start, dur, text}]
            S = {"starts": [x["start"] for x in S["lines"]], "lines": [x["text"] for x in S["lines"]]}
        for i, (st, text) in enumerate(zip(S["starts"], S["lines"]), 1):
            wav = pathlib.Path(a.lines_dir) / f"{i:02d}.wav"
            off = st - trim_offset(wav)                  # line-file time 0 lands here in vo.wav
            t = load_transcript(tr / f"{i:02d}" / "transcript.json")
            for c in line_cues(wav, text, backend, a.lang, a.model, t):
                cues.append({"start": c["start"] + off, "end": c["end"] + off, "value": c["value"]})
            print(f"line {i:02d} ok ({'transcript' if t is not None else 'whisper'})", flush=True)
    else:
        text = pathlib.Path(a.text).read_text(encoding="utf-8")
        cues = line_cues(a.wav, " ".join(text.split()), backend, a.lang, a.model, load_transcript(a.transcript))
        total = sf.info(str(a.wav)).duration
    frames = polish(to_frames(cues, a.fps, total), a.lead, a.min_hold)
    out, i = [], 0
    while i < len(frames):
        j = i
        while j < len(frames) and frames[j] == frames[i]:
            j += 1
        out.append({"start": round(i / a.fps, 3), "end": round(j / a.fps, 3), "value": frames[i]})
        i = j
    meta = {"soundFile": a.wav or a.lines_dir, "duration": round(total, 3),
            "source": f"espeak phonemes ({a.lang}) + word timings", "lead_frames": a.lead, "min_hold": a.min_hold}
    pathlib.Path(a.output).write_text(json.dumps({"metadata": meta, "mouthCues": out}))
    counts = {}
    for c in out:
        counts[c["value"]] = counts.get(c["value"], 0) + 1
    print(json.dumps({"ok": True, "cues": len(out), "shapes": counts, "output": a.output}))


if __name__ == "__main__":
    main()
