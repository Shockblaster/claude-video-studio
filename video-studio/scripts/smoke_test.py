#!/usr/bin/env python3
"""Prove the video toolchain still works end to end. Prints SMOKE PASS or SMOKE FAIL.

Steps: Kokoro TTS (Hindi) -> mouth cues -> avatar rig project -> hyperframes check ->
draft render -> qc_reel.py. About 1-2 minutes on the 6 GB laptop.

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
        shutil.rmtree(wd)
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
    if not a.keep and ok:
        shutil.rmtree(wd, ignore_errors=True)
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
