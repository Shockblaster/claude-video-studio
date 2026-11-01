#!/usr/bin/env python3
"""Prove the video toolchain still works end to end. Prints SMOKE PASS or SMOKE FAIL.

Steps: Kokoro TTS (Hindi) -> mouth cues -> avatar rig project -> hyperframes check ->
draft render -> qc_reel.py -> beat grid -> cue check; with the optional audio tools (setup/setup-audio.*):
original score -> earshot SFX mix + mux. About 2-4 minutes on a 6 GB laptop.

  python -I smoke_test.py [--workdir <VIDEO_STUDIO_HOME>/smoke] [--keep]
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _paths  # noqa: E402  (cross-platform tool / folder lookup)

HERE = pathlib.Path(__file__).resolve().parent
NPX = _paths.npx()


def step(name, cmd, cwd=None, timeout=600):
    # hyperframes tts looks for kokoro-onnx in its own default python (not found since the CLI
    # update on 2026-10-27); point it at this interpreter, which has kokoro-onnx installed
    env = dict(os.environ, HYPERFRAMES_PYTHON=os.environ.get("HYPERFRAMES_PYTHON", sys.executable))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    ok = r.returncode == 0
    print(f"[{'ok' if ok else 'FAIL'}] {name}")
    if not ok:
        print((r.stdout + r.stderr)[-1500:])
    return ok, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=str(_paths.home() / "smoke"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    wd = pathlib.Path(a.workdir)
    if wd.exists():
        # Windows can keep a handle on the last run's folder for a while (WinError 32): retry, then use a fresh folder
        import time
        for _ in range(5):
            try:
                shutil.rmtree(wd); break
            except PermissionError:
                time.sleep(3)
        else:
            wd = wd.with_name(wd.name + "_" + time.strftime("%H%M%S"))
            print(f"[note] old workdir locked, using {wd}")
    wd.mkdir(parents=True)
    proj = wd / "proj"
    ok = True

    good, _ = step("tts kokoro hindi", [NPX, "-y", "hyperframes", "tts", "नमस्ते, यह एक स्मोक टेस्ट है।",
                                        "-v", "hf_alpha", "-l", "hi", "-o", str(wd / "vo.wav"), "--json"])
    ok &= good
    good, _ = step("init portrait project", [NPX, "-y", "hyperframes", "init", str(proj), "--resolution", "portrait",
                                             "--skip-skills", "--non-interactive"])
    ok &= good
    good, _ = step("build avatar rig", [sys.executable, "-I", str(HERE / "build_avatar_proof.py"), str(wd / "vo.wav"),
                                        str(proj), "--captions", "नमस्ते,|यह एक *स्मोक* टेस्ट है।"])
    ok &= good
    good, out = step("hyperframes check", [NPX, "hyperframes", "check", "--json"], cwd=proj)
    if good:
        try:
            errors = json.loads(out).get("lint", {}).get("errorCount", 1)
            good = errors == 0
            print(f"     lint errors: {errors}")
        except json.JSONDecodeError:
            good = False
    ok &= good
    mp4 = wd / "smoke.mp4"
    good, _ = step("draft render", [NPX, "hyperframes", "render", "--quality", "draft", "--workers", "2",
                                    "--output", str(mp4)], cwd=proj)
    ok &= good
    good, out = step("qc_reel", [sys.executable, "-I", str(HERE / "qc_reel.py"), str(mp4), "--min", "1"])
    ok &= good
    # beat pipeline: grid -> cue check (no extra installs); score + earshot mix when the audio tools are set up
    cues = wd / "cues.json"
    cues.write_text(json.dumps([{"t": 0.5, "type": "pop", "lock": "beat", "role": "pop"},
                                {"t": 1.0, "type": "reveal", "lock": "anchor", "role": "hit"},
                                {"t": 1.6, "type": "move", "lock": "word", "role": "whoosh.short"}]))
    tl = wd / "timeline.json"
    good, _ = step("beat grid (fit to cues)", [sys.executable, "-I", str(HERE / "beatgrid.py"), "--fit-bpm", "100", "130",
                                               "--cues", str(cues), "--dur", "2.5", "-o", str(tl)])
    ok &= good
    good, _ = step("cue check (exit 0)", [sys.executable, "-I", str(HERE / "cuecheck.py"), "--timeline", str(tl), "--cues", str(cues)])
    ok &= good
    AP = _paths.audio_python()
    if AP != sys.executable and (_paths.opuscar_dir() / "core" / "audio" / "instruments" / "index.json").exists():
        good, _ = step("score (sampler, real instruments)", [AP, "-X", "utf8", str(HERE / "score.py"), "--timeline", str(tl),
                                                              "--cues", str(cues), "--out", str(wd / "music"), "--key", "C"])
        ok &= good
        good, _ = step("beat mix (earshot kit + mux)", [AP, "-X", "utf8", str(HERE / "beatmix.py"), "--vo", str(wd / "vo.wav"),
                                                        "--music", str(wd / "music" / "music.wav"), "--cues", str(cues),
                                                        "--timeline", str(tl), "--key", "C", "--out", str(wd / "sound"),
                                                        "--dur", "2.5", "--video", str(mp4), "--mux", str(wd / "beat.mp4")], timeout=900)
        ok &= good
    else:
        print("[skip] score + beat mix: optional audio tools not set up (setup/setup-audio.sh or .ps1)")
    if not a.keep and ok:
        shutil.rmtree(wd, ignore_errors=True)
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
