#!/usr/bin/env python3
"""BEAT MIX: voice + music + professional SFX on every cue, placed the way music-led launch films place them
(2026-11-01). SFX from earshot's audited bank (MIT, github.com/Leonxlnx/earshot, its `launch` preset: per role the
level over the music bed, the offset against the cut and the minimum gap, all medians measured on professional
films); mix rules from lemo-opuscar's TECHNIQUE.md (MIT): compress the voice first, then balance by RMS.

Run with the AUDIO venv (earshot + soxr live there, not in the system Python):
  <AUDIO venv python (scripts/_paths.py audio_python())> beatmix.py \
      --vo vo.wav --music music.wav [--music-seek 0] --cues cues.json --out sound/ --dur 9.9 \
      [--kit sound/kit.json] [--preset launch] [--video silent.mp4 --mux out.mp4]

cues.json: [{"t", "type", "desc", "lock", "role", "pan"}] (beatgrid.py / cuecheck.py share it). "pan" -1..1
  follows the motion on screen (a whip to the right pans right). "role" = an earshot kit role:
  tick tock hit land land.light pop whoosh.short whoosh.long riser swell drop key click click.confirm snap bell text
  A cue without a role gets no sound. Optional per cue: "gain_db" (trim), "take" (index), "pitch" not used here.
Music handling:
  * level: the music sits --under dB under the compressed voice (RMS while speaking), +--lift dB in gaps >= 0.5 s;
  * stop-down: before every hit / drop / whoosh.long / swell cue the music dips --stop-db dB over the last 0.4 s
    and comes back on the hit (earshot measured: 53 % of strong hits in pro films follow a >= 6 dB dip);
  * no ducking under every effect (the pro films don't).
Writes out/mix.wav (48 kHz stereo), out/stems/{vo,music,sfx}.wav, out/SOUND.md (every placement + the 5 cues to
check with headphones), out/kit.lock.json (via earshot), and with --mux a video at -14 LUFS (two-pass loudnorm,
true peak -1.5 dBTP).
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np
import soundfile as sf

SR = 48000
STOP_ROLES = {"hit", "drop", "whoosh.long", "swell"}


def load(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9)


def compress(x, thr_db=-24.0, ratio=3.0, att=0.005, rel=0.12, makeup=True):
    """feed-forward RMS compressor (stereo-linked); TTS has a high peak-to-average ratio"""
    m = np.sqrt(np.mean(np.square(x), axis=1))
    a_a, a_r = np.exp(-1 / (att * SR)), np.exp(-1 / (rel * SR))
    env = np.empty_like(m)
    e = 0.0
    for i, v in enumerate(m):                              # one pass, ~0.3 s per 10 s at 48 kHz
        c = a_a if v > e else a_r
        e = c * e + (1 - c) * v
        env[i] = e
    lv = 20 * np.log10(env + 1e-9)
    over = np.maximum(0, lv - thr_db)
    g = 10 ** (-(over - over / ratio) / 20)
    y = x * g[:, None]
    if makeup:
        y *= 10 ** ((rms_db(x[m > 1e-3]) - rms_db(y[m > 1e-3])) / 20)
    return y


def speech_mask(vo, win=0.05, floor_db=-40):
    n = int(win * SR)
    k = len(vo) // n
    r = np.sqrt(np.mean(np.square(vo[:k * n]).reshape(k, n, 2), axis=(1, 2)))
    on = 20 * np.log10(r + 1e-9) > (20 * np.log10(r.max() + 1e-9) + floor_db)
    return np.repeat(on, n)[:len(vo)] if k else np.zeros(len(vo), bool), n


def smooth(g, sec=0.08):
    n = max(1, int(sec * SR))
    k = np.ones(n) / n
    return np.convolve(np.pad(g, (n, n), mode="edge"), k, mode="same")[n:-n]


def loudnorm_mux(video, mix_wav, out, target=-14.0, tp=-1.5):
    f = f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mix_wav), "-af", f, "-f", "null", "-"], capture_output=True, text=True)
    j = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    f2 = (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    # the limiter at -2 dBFS after loudnorm: AAC adds inter-sample overs (true peak -0.4 dBTP without it)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(mix_wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-af", f2 + ",aresample=48000,alimiter=limit=0.79:attack=2:release=40:level=false", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    subprocess.run(cmd, check=True)
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    i = float(m[m.rindex("I:"):].split()[1])
    pk = float(m[m.rindex("Peak:"):].split()[1])
    return i, pk


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--music")
    ap.add_argument("--music-seek", type=float, default=0.0)
    ap.add_argument("--cues", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--kit", help="kit.json (default: <out>/kit.json from --preset)")
    ap.add_argument("--preset", default="launch")
    ap.add_argument("--under", type=float, default=10.0,
                    help="music RMS under the voice RMS while speaking (dB); opuscar ~10, earshot critique tip 3-6; "
                         "14 (the old default) left a voice-led reel thin and mono (2026-11-01)")
    ap.add_argument("--lift", type=float, default=4.0, help="music lift in voice gaps >= 0.5 s (dB)")
    ap.add_argument("--stop-db", type=float, default=9.0)
    ap.add_argument("--sfx-trim", type=float, default=0.0, help="global SFX trim (dB)")
    ap.add_argument("--timeline", help="timeline.json: 'anchor' cues get their sound on the grid beat (where the music hit is)")
    ap.add_argument("--key", help="the score's key (e.g. D, or Am): tonal roles (bell, text) only use takes in that scale")
    ap.add_argument("--ambience", help="a room tone / ambience bed (opuscar's third layer); mono is decorrelated to stereo")
    ap.add_argument("--amb-under", type=float, default=26.0, help="ambience RMS under the speaking voice (dB)")
    ap.add_argument("--amb-width", type=float, default=0.15, help="ambience L/R correlation after decorrelation (0 = widest)")
    ap.add_argument("--video")
    ap.add_argument("--mux")
    a = ap.parse_args()
    from earshot.forge import kit as K                      # the audio venv

    out = pathlib.Path(a.out); (out / "stems").mkdir(parents=True, exist_ok=True)
    N = int(round(a.dur * SR))
    cues = sorted(json.loads(pathlib.Path(a.cues).read_text()), key=lambda c: c["t"])
    if a.timeline:
        beats = np.array(json.loads(pathlib.Path(a.timeline).read_text())["beats"])
        for c in cues:
            if c.get("lock") == "anchor" and len(beats):
                b = float(beats[np.argmin(np.abs(beats - c["t"]))])
                if abs(b - c["t"]) <= 0.034:
                    c["t"] = b

    # ---- voice: compress, then it is the reference level
    vo = load(a.vo)[:N]
    vo = np.pad(vo, ((0, N - len(vo)), (0, 0)))
    vo = compress(vo)
    spk, _ = speech_mask(vo)
    vo_rms = rms_db(vo[spk]) if spk.any() else -20.0

    # ---- music: level under the voice, lift in gaps, stop-downs before big hits
    music = np.zeros((N, 2), np.float32)
    if a.music:
        mu = load(a.music)
        s0 = int(a.music_seek * SR)
        mu = mu[s0:s0 + N]
        music[:len(mu)] = mu
        m_rms = rms_db(music[spk]) if spk.any() else rms_db(music)
        base = vo_rms - a.under - m_rms
        gap = ~spk
        # only gaps of >= 0.5 s lift (a breath between words does not)
        lift = np.zeros(N)
        idx = np.flatnonzero(np.diff(np.concatenate([[0], gap.astype(int), [0]])))
        for b, e in zip(idx[::2], idx[1::2]):
            if (e - b) / SR >= 0.5:
                lift[b:e] = a.lift
        g = base + smooth(lift, 0.25)
        for c in cues:
            if c.get("role") in STOP_ROLES:
                t = c["t"]
                b, e = int(max(0, t - 0.4) * SR), int(t * SR)
                if e > b:
                    ramp = np.linspace(0, 1, e - b) ** 0.7
                    g[b:e] -= a.stop_db * ramp
        music *= (10 ** (smooth(g, 0.03) / 20))[:, None].astype(np.float32)

    # ---- ambience bed: the third layer; decorrelated, it also gives a voice-led reel its stereo width
    amb = np.zeros((N, 2), np.float32)
    if a.ambience:
        y = load(a.ambience)
        reps = int(np.ceil(N / max(1, len(y))))
        y = np.concatenate([y] * reps)[:N]
        y2, _ = K.stereo_width(y.mean(1), a.amb_width)
        y2 = np.asarray(y2, np.float32).reshape(len(y), -1)[:, :2]
        amb = (y2 * 10 ** ((vo_rms - a.amb_under - rms_db(y2)) / 20)).astype(np.float32)
        f = int(0.3 * SR)
        amb[:f] *= np.linspace(0, 1, f)[:, None]; amb[-f:] *= np.linspace(1, 0, f)[:, None]
    # ---- SFX from the earshot kit
    kit_path = pathlib.Path(a.kit) if a.kit else out / "kit.json"
    if not kit_path.exists():
        K.init(a.preset, str(kit_path), force=True)
    lock = K.render(str(kit_path), str(out / "kit"))
    roles = lock["roles"]
    sfx = np.zeros((N, 2), np.float32)
    bed_ref = vo + music                                      # what the effect sits over
    used, log, rr = [], [], {}
    by_role = {}
    for c in cues:
        if c.get("role"):
            by_role.setdefault(c["role"], []).append(c)
    for role_name, cs in by_role.items():
        role = roles.get(role_name)
        if not role or not role.get("takes"):
            log.append(f"- no sound for role '{role_name}' in this kit ({len(cs)} cues skipped)")
            continue
        takes = role["takes"]
        if a.key and role_name in ("bell", "text"):
            nm = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
                  "A": 9, "A#": 10, "Bb": 10, "B": 11}
            minor = a.key.endswith("m")
            root = nm[a.key[:-1] if minor else a.key]
            scale = {(root + i) % 12 for i in ([0, 2, 3, 5, 7, 8, 10] if minor else [0, 2, 4, 5, 7, 9, 11])}
            import re as _re

            def pc(tk):
                m = _re.search(r"_([A-G][b#]?)(-?\d)\.wav$", tk["file"])
                return nm[m.group(1)] if m else None
            inkey = [tk for tk in takes if pc(tk) is None or pc(tk) in scale]
            if inkey:
                if len(inkey) < len(takes):
                    log.append(f"- {role_name}: {len(takes) - len(inkey)} takes outside {a.key} skipped")
                takes = inkey
        role = dict(role, takes=takes)
        times = K.space_run([c["t"] for c in cs], role.get("min_gap_ms"))
        for c, t in zip(cs, times):
            k = c.get("take", rr.get(role_name, 0)) % len(role["takes"])
            rr[role_name] = k + 1
            take = role["takes"][k]
            y, sr = sf.read(str(out / "kit" / take["file"]), dtype="float32", always_2d=True)
            if y.shape[1] == 1:
                y = np.repeat(y, 2, 1)
            st = K.place(take, role, t)
            try:
                bed = K.bed_level(bed_ref, t, SR) if a.music else None
            except Exception:
                bed = None
            gdb = K.gain_db(take, role, bed) + a.sfx_trim + float(c.get("gain_db", 0))
            i0 = int(round(st * SR))
            src = y[max(0, -i0):]
            i0 = max(0, i0)
            n = min(len(src), N - i0)
            if n > 0:
                pan = float(c.get("pan", 0.0))                # pan SFX with the motion (earshot critique tip)
                lr = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)], np.float32) * np.sqrt(2)
                sfx[i0:i0 + n] += src[:n] * (10 ** (gdb / 20)) * lr
            used.append({"t": round(t, 3), "role": role_name, "sound": take.get("id") or take["file"], "start": round(st, 3),
                         "gain_db": round(gdb, 1), "bed_lufs": None if bed is None else round(bed, 1), "desc": c.get("desc", "")})

    mix = vo + music + amb + sfx
    pk = np.abs(mix).max()
    if pk > 0.98:
        mix *= 0.98 / pk
    for nm, x in (("vo", vo), ("music", music), ("ambience", amb), ("sfx", sfx)):
        sf.write(out / "stems" / f"{nm}.wav", x, SR, subtype="FLOAT")
    sf.write(out / "mix.wav", mix, SR, subtype="FLOAT")

    # ---- report: every placement + the 5 cues most worth a listen
    risk = sorted(used, key=lambda u: -(abs(u["gain_db"]) * 0.1 + (u["role"] in STOP_ROLES) * 2 + (u["role"].startswith("whoosh")) * 1))[:5]
    rep = ["# SOUND.md (beatmix.py)", "", "Claude can't hear: every number below is measured. Listen to the 5 cues at the end.", "",
           f"Voice RMS while speaking {vo_rms:.1f} dBFS (compressed 3:1 at -24 dB). Music {a.under:.0f} dB under it, +{a.lift:.0f} dB in gaps, "
           f"-{a.stop_db:.0f} dB stop-down over 0.4 s before hit/drop/whoosh.long/swell.",
           f"SFX: earshot kit preset '{a.preset}' (bank {lock.get('bank')}).", "", "## Placements"]
    rep += [f"- {u['t']:.3f}s {u['role']:12} {u['sound']} start {u['start']:.3f}s, {u['gain_db']:+.1f} dB"
            + (f" (bed {u['bed_lufs']} LUFS)" if u["bed_lufs"] is not None else "") + f"  {u['desc']}" for u in used]
    rep += log + ["", "## Check these 5 with headphones"] + [f"- {u['t']:.2f}s {u['role']} ({u['desc']})" for u in sorted(risk, key=lambda u: u["t"])]
    if a.video and a.mux:
        i, p = loudnorm_mux(a.video, out / "mix.wav", a.mux)
        rep += ["", f"Muxed {a.mux}: integrated {i:.1f} LUFS, true peak {p:.1f} dBTP"]
    (out / "SOUND.md").write_text("\n".join(rep), encoding="utf-8")
    print(json.dumps({"ok": True, "placed": len(used), "skipped_roles": [l for l in log], "vo_rms": round(float(vo_rms), 1),
                      "out": str(out / "mix.wav"), "mux": a.mux}))


if __name__ == "__main__":
    sys.exit(main())
