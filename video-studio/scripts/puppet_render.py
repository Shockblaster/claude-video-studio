#!/usr/bin/env python3
"""Render a 2D cutout puppet driven by KEYPOINT motion capture (mocap_kp.py), in Python.

Arms: placed where the captured shoulders / elbows / wrists are (normalised by shoulder
width, per-segment length ratios), so the silhouette and foreshortening match real motion.
Hands: a HAND BANK of drawings (one sheet, mirrored for the other hand); per frame the
drawing whose palm facing best matches the captured palm normal (and finger shape) is
chosen, held for a minimum time (no flicker), rotated to the captured finger direction,
at a constant cartoon size. Face: the one-drawing face rig (face_rig.py), lip-synced to the
voice with Rhubarb cues, blinking, rolling with the captured head roll.

  python -I puppet_render.py --rig rig --face face --landmarks face_landmarks.json \
      --handbank handbank.png --bank bank.json --motion motion_kp.json \
      --mouth mouth.json --voice vo.wav --out out.mp4 [--size 1080x1920] [--scale 0.95] [--top 600]

AUTHORED mode: a motion file with "space": "sheet" (from gesture_plan.py) gives elbow /
wrist positions in rig-sheet pixels plus explicit per-frame hand drawings (handL/handR),
finger directions (hdirL/hdirR), head nod/roll, breathing and a desk line. The hands rest
hidden behind the desk; drawings change only while hidden, so no visible pose cuts.

bank.json: {"cells": {"<component id>": {"name": "palm", "shape": "open|point|count2|count3|fist|thumb",
            "n": [x,y,z]}}, ...}  n = palm normal of the drawing as drawn (screen-left hand;
            x right, y down, z toward the viewer is NEGATIVE), e.g. palm to camera = [0,0,-1].
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import puppet_build as pb  # noqa: E402
import chain_rig as cr  # noqa: E402


def load(p):
    return cv2.imread(str(p), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0


def over(dst, src, M):
    w = cv2.warpAffine(src, M, (dst.shape[1], dst.shape[0]), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    w = np.clip(w, 0, 1)
    a = w[..., 3:4]
    dst[..., :3] = w[..., :3] * a + dst[..., :3] * (1 - a)
    dst[..., 3:4] = a + dst[..., 3:4] * (1 - a)


def seg_affine(p_rest0, p_rest1, p0, p1, min_scale=0.5):
    """Map a piece's rest segment (its own px) onto a target segment: rotate, stretch along
    the axis only (foreshortening), keep the width."""
    a = np.array(p_rest1, float) - p_rest0; La = np.linalg.norm(a) + 1e-9; a /= La
    b = np.array(p1, float) - p0; Lb = np.linalg.norm(b) + 1e-9; b /= Lb
    s = max(min_scale, Lb / La)
    pa, pb_ = np.array([-a[1], a[0]]), np.array([-b[1], b[0]])
    Lin = s * np.outer(b, a) + np.outer(pb_, pa)
    t = np.array(p0, float) - Lin @ np.array(p_rest0, float)
    return np.hstack([Lin, t[:, None]]).astype(np.float32)


def rot_affine(piv, deg, at, scale=1.0, flip=False):
    t = math.radians(deg)
    R = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]]) * scale
    if flip:
        R = R @ np.diag([-1.0, 1.0])
    T = np.array(at, float) - R @ np.array(piv, float)
    return np.hstack([R, T[:, None]]).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("rig", "face", "landmarks", "handbank", "bank", "motion", "mouth", "voice", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--scale", type=float, default=0.95)
    ap.add_argument("--top", type=int, default=600)
    ap.add_argument("--hand-scale", type=float, default=1.0)
    ap.add_argument("--hold", type=int, default=6, help="min frames a hand drawing is held")
    ap.add_argument("--hangbank", help="sheet of hanging hands, cuff at TOP, fingers down")
    ap.add_argument("--hang", default="1:hang_side,2:hang_back,6:hang_bent,4:hang_open,5:hang_fist,3:hang_palm")
    a = ap.parse_args()
    OW, OH = [int(v) for v in a.size.split("x")]
    rd = pathlib.Path(a.rig)
    rig = json.loads((rd / "rig.json").read_text())
    Pc, J = rig["pieces"], rig["joints"]
    pc = {n: load(rd / "pieces" / f"{n}.png") for n in ("torso", "neck", "uarm_L", "uarm_R", "farm_L", "farm_R")}
    # ELBOW: the upper-arm drawing ends in a rounded cap below the elbow joint; with the
    # forearm swung toward the camera that cap poked out beside it (a "puffy elbow").
    # Fade the upper arm out just past the joint so the forearm's own top makes the elbow.
    for s_ in ("L", "R"):
        u = pc["uarm_" + s_].copy()
        ey = J[s_]["elbow_u"][1] - Pc["uarm_" + s_]["pos"][1]
        hw = cr.ends(u)["bot_hw"]
        rows = np.arange(u.shape[0], dtype=np.float32)[:, None]
        # clean cut (2 px edge) a little past the joint: a long fade left a fuzzy grey smear
        u[..., 3] *= np.clip(1 - (rows - (ey + 0.30 * hw)) / 2.0, 0, 1)
        pc["uarm_" + s_] = u
    # ONE CUFF: cut each forearm at the top of its shirt cuff; the hand drawing (cuff + sleeve
    # stub) supplies the only cuff (two cuffs showed at every wrist)
    fend = {}
    for s_ in ("L", "R"):
        f = pc["farm_" + s_]
        hsv = cv2.cvtColor((np.clip(f[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        cuffm = (hsv[..., 0] > 90) & (hsv[..., 0] < 125) & (hsv[..., 1] > 25) & (hsv[..., 2] > 140) & (f[..., 3] > 0.5)
        rows = np.nonzero(cuffm.sum(1) > 6)[0]
        al_rows = np.nonzero((f[..., 3] > 0.5).any(1))[0]
        cut = int(rows.min()) if len(rows) else int(al_rows.max())
        f = f.copy(); f[cut:] = 0
        pc["farm_" + s_] = f
        cols = np.nonzero(f[cut - 3, :, 3] > 0.5)[0]
        fend[s_] = {"pt": [float((cols.min() + cols.max()) / 2), float(cut - 2)], "w": float(cols.max() - cols.min())}
    clasp = load(rd / "pieces" / "clasp.png") if (rd / "pieces" / "clasp.png").exists() else None

    # hand bank
    bank = json.loads(pathlib.Path(a.bank).read_text())
    HB = pb.key_green(cv2.imread(a.handbank))
    lab, st = cr.comps(HB)
    hands = {}
    fa_e = cr.ends(pc["farm_L"])
    cuff_w = 2 * fa_e["bot_hw"]
    for cid, meta in bank["cells"].items():
        h, _ = cr.cut(HB, lab, st, int(cid))
        e = cr.ends(h)
        piv = np.array([e["bottom"][0], e["bottom"][1] - 0.12 * e["bot_hw"]])     # sleeve-stub bottom
        hsv = cv2.cvtColor((np.clip(h[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        sk = (hsv[..., 0] < 25) & (hsv[..., 1] > 50) & (h[..., 3] > 0.5)
        ys, xs = np.nonzero(sk)
        d = np.hypot(xs - piv[0], ys - piv[1]); far = d > np.percentile(d, 80)
        axis = math.degrees(math.atan2(ys[far].mean() - piv[1], xs[far].mean() - piv[0]))
        k = (fend["L"]["w"] + fend["R"]["w"]) / 2 * 1.0 / (2 * e["bot_hw"]) * a.hand_scale  # stub width = sleeve width
        nn = np.array(meta["n"], float)
        hands[meta["name"]] = {"img": h, "piv": piv, "axis": axis, "k": k, "shape": meta["shape"], "n": nn}
        # mirrored variant (reads as the same hand turned the other way: e.g. a cupped palm
        # facing the body's centre instead of away from it)
        hm = cv2.flip(h, 1)
        hands[meta["name"] + "~m"] = {"img": hm, "piv": np.array([h.shape[1] - 1 - piv[0], piv[1]]),
                                      "axis": 180 - axis, "k": k, "shape": meta["shape"], "n": nn * np.array([-1, 1, 1])}

    if a.hangbank:
        HG = pb.key_green(cv2.imread(a.hangbank))
        hl, hs = cr.comps(HG)
        for item in a.hang.split(","):
            cid, name = item.split(":")
            h, _ = cr.cut(HG, hl, hs, int(cid))
            e = cr.ends(h)
            piv = np.array([e["top"][0], e["top"][1] + 0.12 * e["top_hw"]])   # cuff at the TOP
            hsv = cv2.cvtColor((np.clip(h[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
            sk = (hsv[..., 0] < 25) & (hsv[..., 1] > 50) & (h[..., 3] > 0.5)
            ys, xs = np.nonzero(sk)
            d = np.hypot(xs - piv[0], ys - piv[1]); far = d > np.percentile(d, 80)
            axis = math.degrees(math.atan2(ys[far].mean() - piv[1], xs[far].mean() - piv[0]))
            k = (fend["L"]["w"] + fend["R"]["w"]) / 2 / (2 * e["top_hw"]) * a.hand_scale
            ln = float(np.max(d)) * k
            hands[name] = {"img": h, "piv": piv, "axis": axis, "k": k, "shape": "hang", "n": np.zeros(3), "len": ln}
            hm = cv2.flip(h, 1)
            hands[name + "~m"] = {"img": hm, "piv": np.array([h.shape[1] - 1 - piv[0], piv[1]]), "axis": 180 - axis,
                                  "k": k, "shape": "hang", "n": np.zeros(3), "len": ln}
    # face
    fd = pathlib.Path(a.face)
    F = json.loads((fd / "face.json").read_text()); sp = F["split"]
    upper = {e: load(fd / f"upper_{e}.png") for e in F["eyes"]}
    lower = {m: load(fd / f"lower_{m}.png") for m in F["shapes"]}
    hd = Pc["head"]; fk = 0.5          # face canvas is 2x the sheet head
    head_piv = np.array([hd["pos"][0] + hd["size"][0] / 2, hd["pos"][1] + hd["bottom"][1]])

    M = json.loads(pathlib.Path(a.motion).read_text())
    n = M["frames"]
    # retarget scales: puppet shoulder width vs normalised 1.0; per-segment length ratios
    shL, shR = np.array(J["L"]["shoulder"]), np.array(J["R"]["shoulder"])
    U = np.linalg.norm(shR - shL)
    def p95(vals):
        return float(np.percentile(vals, 95))
    authored = M.get("space") == "sheet"
    seg = {}
    for s in (() if authored else ("L", "R")):
        up = [math.hypot(M[f"el{s}x"][i] - M[f"sh{s}x"][i], M[f"el{s}y"][i] - M[f"sh{s}y"][i]) for i in range(n)]
        fo = [math.hypot(M[f"wr{s}x"][i] - M[f"el{s}x"][i], M[f"wr{s}y"][i] - M[f"el{s}y"][i]) for i in range(n)]
        Lu = np.linalg.norm(np.array(J[s]["elbow_u"]) - J[s]["shoulder"])
        Lf = np.linalg.norm(np.array(J[s]["wrist"]) - J[s]["elbow_f"])
        seg[s] = (Lu / (p95(up) * U), Lf / (p95(fo) * U))

    # hand choice per frame, with hysteresis
    def choose(s, i, cur):
        shape = M["shape" + s][i]
        nv = np.array([M[f"n{s}x"][i], M[f"n{s}y"][i], M[f"n{s}z"][i]])
        if s == "R":
            nv = nv * np.array([-1, 1, 1])                    # compare in the drawn (screen-left) frame
        hd_ = (M["hdir" + s][i] + 360) % 360
        if 25 < hd_ < 155 and shape in ("open", "thumb", "fist"):
            return ("hang_side" if "hang_side" in hands else "back"), 1.0   # arm hanging: relaxed hand
        fam = {"point": ["point_cam", "point_side"], "count2": ["count2"], "count3": ["count3"], "fist": ["fist"]}
        base = fam.get(shape) or [k for k, v in hands.items() if v["shape"] == "open" and not k.endswith("~m")]
        names = base + [b + "~m" for b in base]
        best = max(names, key=lambda k: float(hands[k]["n"] @ nv))
        return best, float(hands[best]["n"] @ nv)

    chosen = {"L": list(M.get("handL", [])), "R": list(M.get("handR", []))} if authored else {"L": [], "R": []}
    for s in (() if authored else ("L", "R")):
        cur, held = None, 0
        for i in range(n):
            b, sc = choose(s, i, cur)
            if cur is None:
                cur = b
            elif b != cur:
                cur_sc = float(hands[cur]["n"] @ (np.array([M[f"n{s}x"][i], M[f"n{s}y"][i], M[f"n{s}z"][i]]) * (np.array([-1, 1, 1]) if s == "R" else 1)))
                fam_changed = hands[b]["shape"] != hands[cur]["shape"] or (hands[b]["shape"] == "hang") != (hands[cur]["shape"] == "hang")
                if held >= a.hold and (fam_changed or sc - cur_sc > 0.25):
                    cur, held = b, 0
            held += 1
            chosen[s].append(cur)

    # wrist distances for the clasp
    dists = [math.hypot(M["wrRx"][i] - M["wrLx"][i], M["wrRy"][i] - M["wrLy"][i]) for i in range(n)]
    dref = 0.0 if authored else float(np.percentile(dists, 8))

    cues = json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"]
    vo_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice],
                                  capture_output=True, text=True).stdout.strip())
    n_out = min(n, int((vo_len + 0.6) * M["fps"]))
    rng = np.random.default_rng(7); blinks = []; t = 1.2
    while t < n_out / M["fps"]:
        blinks.append(t); t += 2.4 + rng.random() * 2.2
    def mouth_at(t):
        m = "X"
        for c in cues:
            if c["start"] <= t:
                m = c["value"]
        return m if t <= vo_len + 0.05 else "X"
    def eyes_at(t):
        for b in blinks:
            d = (t - b) * M["fps"]
            if 0 <= d < 1 or 3 <= d < 4: return "half"
            if 1 <= d < 3: return "closed"
        return "open"
    roll0 = 0.0 if authored else float(np.median(M["roll"]))

    SW, SH = rig["sheet"]
    desk_sheet = M["desk"] if authored else Pc["torso"]["pos"][1] + Pc["torso"]["size"][1] - 6
    gs = a.scale
    tx = OW / 2 - (Pc["torso"]["pos"][0] + Pc["torso"]["size"][0] / 2) * gs
    ty = a.top - hd["pos"][1] * gs
    G = np.array([[gs, 0, tx], [0, gs, ty]], np.float32)
    bgc = np.zeros((OH, OW, 3), np.float32)
    yy, xx = np.mgrid[0:OH, 0:OW]
    rr = np.sqrt(((xx - OW / 2) / (OW * 1.1)) ** 2 + ((yy - OH * 0.42) / (OH * 0.7)) ** 2)
    c0, c1 = np.array([1.0, 1.0, 1.0]), np.array([0.913, 0.871, 0.839])
    bgc[:] = c0 + (c1 - c0) * np.clip(rr, 0, 1)[..., None]
    cut_y = int(ty + desk_sheet * gs)

    tmp = str(pathlib.Path(a.out).with_suffix(".silent.mp4"))
    proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}",
                             "-r", str(M["fps"]), "-i", "-", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", tmp],
                            stdin=subprocess.PIPE)
    for i in range(n_out):
        t = i / M["fps"]
        cv_ = np.zeros((SH, SW, 4), np.float32)
        tgt = {}
        for s in ("L", "R"):
            sh = np.array(J[s]["shoulder"])
            if authored:
                el = np.array([M[f"el{s}x"][i], M[f"el{s}y"][i]]); wr = np.array([M[f"wr{s}x"][i], M[f"wr{s}y"][i]])
            else:
                ku, kf = seg[s]
                el = sh + np.array([M[f"el{s}x"][i] - M[f"sh{s}x"][i], M[f"el{s}y"][i] - M[f"sh{s}y"][i]]) * U * ku
                wr = el + np.array([M[f"wr{s}x"][i] - M[f"el{s}x"][i], M[f"wr{s}y"][i] - M[f"el{s}y"][i]]) * U * kf
            # keep the whole hand above the desk line: shorten the forearm (it reads as the arm
            # coming forward) instead of letting the desk cut the hand (looked like it sank)
            hn = chosen[s][i]
            hl_ = hands[hn].get("len", 0.8 * hands[hn]["img"].shape[0] * hands[hn]["k"])
            max_y = desk_sheet - hl_ * 1.02
            if wr[1] > max_y and not authored:
                wr = np.array([wr[0], max(el[1] + 10, max_y)])
            tgt[s] = (sh, el, wr)
            # upper arm (behind torso)
            ua = Pc["uarm_" + s]
            r0 = np.array(J[s]["shoulder"]) - ua["pos"]; r1 = np.array(J[s]["elbow_u"]) - ua["pos"]
            over(cv_, pc["uarm_" + s], seg_affine(r0, r1, sh, el))
        nk = Pc["neck"]; over(cv_, pc["neck"], np.array([[1, 0, nk["pos"][0]], [0, 1, nk["pos"][1]]], np.float32))
        # head: face states, rolled about the neck
        roll = max(-6.0, min(6.0, (M["roll"][i] - roll0) * 0.8))
        face = np.vstack([upper[eyes_at(t)][:sp], lower[mouth_at(t)][sp:]])
        fpiv = (head_piv - np.array(hd["pos"])) / fk
        over(cv_, face, rot_affine(fpiv, roll, head_piv + np.array([0.0, M["nod"][i] if authored else 0.0]), scale=fk))
        over(cv_, pc["torso"], np.array([[1, 0, Pc["torso"]["pos"][0]], [0, 1, Pc["torso"]["pos"][1]]], np.float32))
        clasped = not authored and dists[i] < 1.12 * dref and clasp is not None
        for s in ("L", "R"):
            sh, el, wr = tgt[s]
            fa = Pc["farm_" + s]
            r0 = np.array(J[s]["elbow_f"]) - fa["pos"]; r1 = np.array(fend[s]["pt"])
            over(cv_, pc["farm_" + s], seg_affine(r0, r1, el, wr, min_scale=0.02 if authored else 0.5))
        if clasped:
            mid = (tgt["L"][2] + tgt["R"][2]) / 2
            cl = rig["clasp"]; cpiv = (np.array(cl["cuffL"]) + np.array(cl["cuffR"])) / 2
            cw = math.hypot(cl["cuffR"][0] - cl["cuffL"][0], cl["cuffR"][1] - cl["cuffL"][1])
            d = np.linalg.norm(tgt["R"][2] - tgt["L"][2])
            ang = max(-15, min(15, math.degrees(math.atan2(tgt["R"][2][1] - tgt["L"][2][1], tgt["R"][2][0] - tgt["L"][2][0]))))
            over(cv_, clasp, rot_affine(cpiv, ang, mid, scale=0.82 * max(d, 0.9 * cw) / cw))
        else:
            for s in ("L", "R"):
                nm = chosen[s][i]
                if s == "R":                       # screen-right hand = mirror image of the drawing
                    nm = nm[:-2] if nm.endswith("~m") else nm + "~m"
                h = hands[nm]
                fdir = M["hdir" + s][i]
                rel = (fdir - h["axis"] + 180) % 360 - 180
                lim = 0.0 if h["shape"] == "hang" else (12.0 if h["shape"] == "point" else 35.0)
                if not authored:
                    rel = max(-lim, min(lim, rel))     # bigger turns = a different drawing, not a spin
                over(cv_, h["img"], rot_affine(h["piv"], rel, tgt[s][2], scale=h["k"]))
        frame = bgc.copy()
        Gi = G.copy()
        if authored:
            Gi[1, 2] += M["breath"][i]
        w = cv2.warpAffine(cv_, Gi, (OW, OH), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)).clip(0, 1)
        al = w[..., 3:4]
        frame = w[..., :3] * al + frame * (1 - al)
        frame[cut_y:] = np.array([0.341, 0.137, 0.0])                     # desk (navy, BGR)
        frame[cut_y:cut_y + 6] = np.array([0.286, 0.816, 0.957])          # marigold rule
        proc.stdin.write((np.clip(frame, 0, 1) * 255).astype(np.uint8).tobytes())
    proc.stdin.close(); proc.wait()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-i", a.voice, "-af", "loudnorm=I=-14:TP=-1.5",
                    "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-shortest", a.out], check=True)
    pathlib.Path(tmp).unlink(missing_ok=True)
    used = {s: sorted(set(chosen[s][:n_out])) for s in ("L", "R")}
    print(json.dumps({"ok": True, "frames": n_out, "hands_used": used}))


if __name__ == "__main__":
    sys.exit(main())
