#!/usr/bin/env python3
"""CUE CHECK: is every event that should sit on the beat actually on it? (2026-11-01; after lemo-opuscar's
cuecheck.py, MIT, github.com/lemomo-ai/lemo-opuscar: "compares every visual hit with the music cue it should land
on. Aim for 0 ms.")

  python -I cuecheck.py --timeline timeline.json --cues cues.json [--fps 30] [--tol-frames 1] [--snap snapped.json]
  python -I cuecheck.py --timeline timeline.json --plan avatar/plan.json --html hf/index.html --cues extra.json ...

Events come from cues.json and, optionally, are harvested from:
  --plan   an avatar_track plan: segment starts (pose pops; lock "beat" unless the segment says "lock": "word"),
           expression starts (lock "word": they follow the line)
  --html   a HyperFrames index.html: every element with data-start (captions are lock "word"; anything with
           data-lock="beat" is a beat cue)
Per event it prints the nearest beat, the offset in ms and frames, and whether it is on a downbeat.
lock "anchor" (a spoken word that must also sit on a beat) is gated like "beat" but never moved by --snap.
Exit 1 when a "beat" / "anchor" event is more than --tol-frames frames off (the QC gate). --snap writes the cues with every
"beat" event moved to its nearest beat (word / free events untouched), to paste back into the edit.
"""
import argparse
import json
import pathlib
import re
import sys

import numpy as np


def harvest_plan(p):
    plan = json.loads(pathlib.Path(p).read_text())
    ev = []
    for s in plan.get("segments", []):
        if s.get("enter") in ("pop", "cut", "in"):
            ev.append({"t": float(s["start"]), "type": "pose_" + s.get("enter", "cut"), "desc": s.get("pose", s.get("clip", "")),
                       "lock": s.get("lock", "beat"), "role": "pop" if s.get("enter") == "pop" else "whoosh.short", "src": "plan"})
    for e in plan.get("expressions", []):
        ev.append({"t": float(e["start"]), "type": "expression", "desc": e["expr"], "lock": e.get("lock", "word"), "src": "plan"})
    return ev


def harvest_html(p):
    s = pathlib.Path(p).read_text(encoding="utf-8")
    ev = []
    for m in re.finditer(r'<[^>]*\bid="([^"]+)"[^>]*\bdata-start="([0-9.]+)"[^>]*>', s):
        tag, el_id, t = m.group(0), m.group(1), float(m.group(2))
        if t <= 0.0001 and "cap" not in el_id:
            continue
        lock = re.search(r'data-lock="(\w+)"', tag)
        kind = "caption" if (" cg" in tag or el_id.startswith("cap")) else "clip"
        ev.append({"t": t, "type": kind, "desc": el_id, "lock": lock.group(1) if lock else ("word" if kind == "caption" else "free"),
                   "src": "html"})
    return ev


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--cues")
    ap.add_argument("--plan")
    ap.add_argument("--html")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--tol-frames", type=float, default=1.0)
    ap.add_argument("--snap")
    ap.add_argument("--json", help="write the report as JSON")
    a = ap.parse_args()
    tl = json.loads(pathlib.Path(a.timeline).read_text())
    beats, downs = np.array(tl["beats"]), np.array(tl.get("downbeats", []))
    ev = json.loads(pathlib.Path(a.cues).read_text()) if a.cues else []
    if a.plan:
        ev += harvest_plan(a.plan)
    if a.html:
        ev += harvest_html(a.html)
    ev = sorted(ev, key=lambda e: e["t"])
    fr = 1 / a.fps
    rows, fails, snapped = [], 0, []
    print(f"grid {tl['bpm']} bpm, beat {tl['beat_s'] * 1000:.0f} ms, {len(beats)} beats; tolerance {a.tol_frames:g} frame(s) = {a.tol_frames * fr * 1000:.0f} ms")
    print(f"{'t':>7} {'lock':5} {'type':12} {'beat':>7} {'off ms':>7} {'frames':>6}  {'':4} desc")
    for e in ev:
        k = int(np.argmin(np.abs(beats - e["t"]))) if len(beats) else -1
        b = float(beats[k]) if k >= 0 else float("nan")
        off = e["t"] - b
        down = bool(len(downs) and np.min(np.abs(downs - b)) < 1e-3)
        lock = e.get("lock", "free")
        bad = lock in ("beat", "anchor") and abs(off) > a.tol_frames * fr + 1e-6
        fails += bad
        flag = "FAIL" if bad else ("ok" if lock in ("beat", "anchor") else "")
        print(f"{e['t']:7.3f} {lock:5} {e.get('type', '')[:12]:12} {b:7.3f} {off * 1000:+7.0f} {off / fr:+6.1f}  {flag:4} {'DOWN ' if down else ''}{e.get('desc', '')}")
        rows.append(dict(e, beat=round(b, 4), off_ms=round(off * 1000, 1), downbeat=down, fail=bool(bad)))
        se = dict(e)
        if lock == "beat":
            se["t"] = round(b, 4)
        snapped.append(se)
    nb = sum(1 for e in ev if e.get("lock") in ("beat", "anchor"))
    offs = [abs(r["off_ms"]) for r in rows if r.get("lock") in ("beat", "anchor")]
    print(f"beat events {nb}, failing {fails}" + (f", mean |off| {np.mean(offs):.0f} ms, max {max(offs):.0f} ms" if offs else ""))
    if a.snap:
        pathlib.Path(a.snap).write_text(json.dumps(snapped, indent=1))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"fails": fails, "events": rows}, indent=1))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
