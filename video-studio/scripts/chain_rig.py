#!/usr/bin/env python3
"""v3 cutout puppet from an EXPLODED VIEW (every part in its anatomical place with small
gaps) + a HAND SHEET (separate hands with a cuff stub, fingers up). The exploded layout
gives true proportions and joint positions, so nothing has to be guessed.

  python -I chain_rig.py --exploded exploded.png --hands hands.png --map map.json --out rig \
         [--poses poses.json]

map.json:
  {"exploded": {"head": 1, "torso": 2, "uarm_L": 3, "uarm_R": 4, "farm_L": 5, "farm_R": 6,
                "hand_L_rest": 7, "hand_R_rest": 8},
   "hands": {"R_open": 1, "R_point": 3, ...}, "hand_side": {"R_open": "L", ...}}
Side letters are SCREEN sides (L = left half of the image).
poses.json: {name: {"S_L": deg, "F_L": deg, "H_L": deg, "hand_L": name, ... same for R}}
  S = shoulder rotation from the drawn rest (deg, + = clockwise on screen)
  F = forearm world direction (deg, 90 = straight down, -90 = up); H = hand world direction
  (wrist to fingertips). Omit F/H to keep the drawn rest direction.
"""
import argparse
import json
import math
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import puppet_build as pb  # noqa: E402


def comps(P):
    a = (P[..., 3] > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(a, 8)
    return lab, st


def cut(P, lab, st, i, pad=8):
    x, y, w, h, _ = st[i]
    x0, y0 = max(0, x - pad), max(0, y - pad)
    pc = P[y0:y + h + pad, x0:x + w + pad].copy()
    pc[..., 3] *= (lab[y0:y + h + pad, x0:x + w + pad] == i)
    return pc, (int(x0), int(y0))


def ends(piece):
    """Top and bottom centre points and half-widths of a roughly vertical piece."""
    a = piece[..., 3] > 0.5
    rows = np.nonzero(a.any(1))[0]
    t, b = rows.min(), rows.max()
    h = b - t
    def band(y0, y1):
        cols = np.nonzero(a[y0:y1].any(0))[0]
        return (cols.min() + cols.max()) / 2.0, (cols.max() - cols.min()) / 2.0
    tc, tw = band(t, t + max(3, int(0.12 * h)))
    bc, bw = band(b - max(3, int(0.12 * h)), b + 1)
    return {"top": [tc, float(t)], "bottom": [bc, float(b)], "top_hw": tw, "bot_hw": bw, "h": float(h)}


def strip_sleeve(hand):
    """Remove the dark jacket-sleeve stub under the cuff (keep the light cuff)."""
    rgb = (np.clip(hand[..., :3], 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
    a = hand[..., 3] > 0.5
    rows = np.nonzero(a.any(1))[0]
    b = rows.max()
    cut_y = b + 1
    for y in range(b, rows.min() + int(0.5 * (b - rows.min())), -1):
        m = a[y]
        if m.sum() < 5:
            continue
        dark = ((hsv[y, :, 2] < 90) & m).sum() / m.sum()
        if dark > 0.6:
            cut_y = y
        else:
            break
    out = hand.copy()
    out[cut_y:] = 0
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exploded", required=True)
    ap.add_argument("--hands", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--poses")
    ap.add_argument("--clasp", help="sheet with both-hands-together drawings (first = interlaced)")
    a = ap.parse_args()
    mp = json.loads(pathlib.Path(a.map).read_text())
    out = pathlib.Path(a.out); (out / "pieces").mkdir(parents=True, exist_ok=True)
    E = pb.key_green(cv2.imread(a.exploded))
    lab, st = comps(E)
    P, off = {}, {}
    for name, i in mp["exploded"].items():
        P[name], off[name] = cut(E, lab, st, i)
    # ARMS TUCK UNDER THE JACKET SHOULDERS. The exploded view leaves a gap, so each arm chain
    # (upper arm, forearm, rest hand) moves inward until the upper arm's centre sits
    # inset_frac of an arm-width inside the torso's outer edge at shoulder level.
    tor, tpos = P["torso"], off["torso"]
    ta = tor[..., 3] > 0.5
    inset_frac = mp.get("arm_inset", 0.42)
    shifts = {}
    for s in ("L", "R"):
        ua, upos = P["uarm_" + s], off["uarm_" + s]
        e = ends(ua)
        row_sheet = upos[1] + e["top"][1] + 2.2 * e["top_hw"]
        r = int(np.clip(row_sheet - tpos[1], 0, ta.shape[0] - 1))
        cols = np.nonzero(ta[r])[0]
        edge = tpos[0] + (cols.min() if s == "L" else cols.max())
        arm_cx = upos[0] + e["top"][0]
        target = edge + (inset_frac * 2 * e["top_hw"]) * (1 if s == "L" else -1)
        dx = int(round(target - arm_cx))
        # and DOWN until the rounded cap top hides under the jacket's shoulder line
        col = int(np.clip(arm_cx + dx - tpos[0], 0, ta.shape[1] - 1))
        rows_t = np.nonzero(ta[:, col])[0]
        shoulder_line = tpos[1] + (rows_t.min() if len(rows_t) else 0)
        arm_top = upos[1] + e["top"][1]
        dy = int(max(0, shoulder_line + mp.get("cap_hide", 10) - arm_top))
        shifts[s] = [dx, dy]
        for part in ("uarm_", "farm_", "hand_"):
            key = part + s + ("_rest" if part == "hand_" else "")
            off[key] = (off[key][0] + dx, off[key][1] + dy)
    # NECK INTO THE COLLAR. The head piece carries its own shirt collar, which stacked on the
    # torso's collar (the seam the user saw). Remove the shirt pixels from the head, extend
    # the neck skin downward, and draw the head BEHIND the torso so the torso collar wraps it.
    hd = P["head"].copy()
    hh, hw_ = hd.shape[:2]
    hsv = cv2.cvtColor((np.clip(hd[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    yy = np.arange(hh)[:, None]
    shirt = (hsv[..., 0] > 85) & (hsv[..., 0] < 130) & (hsv[..., 2] > 140) & (yy > 0.7 * hh)
    dark_tie = (hsv[..., 2] < 90) & (yy > 0.88 * hh)
    hd[..., 3] = np.where(shirt | dark_tie, 0, hd[..., 3])
    hd[..., 3] = cv2.morphologyEx((hd[..., 3] > 0.5).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) * hd[..., 3]
    skin = (hsv[..., 0] < 25) & (hsv[..., 1] > 50) & (hd[..., 3] > 0.9)
    alpha_rows = np.nonzero((hd[..., 3] > 0.5).any(1))[0]
    head_w = int((hd[int(0.5 * hh), :, 3] > 0.5).sum())
    ccols = np.nonzero(hd[int(0.5 * hh), :, 3] > 0.5)[0]
    cx = (ccols.min() + ccols.max()) / 2.0
    # chin = lowest beard/jaw row in the centre third of the head
    Vv = hsv[..., 2]
    cmask = np.zeros_like(skin); cmask[:, int(cx - head_w / 6):int(cx + head_w / 6)] = True
    beard = (Vv < 110) & (hd[..., 3] > 0.5) & cmask
    beard_rows = [y for y in range(int(0.6 * hh), hh) if beard[y].sum() > 6]
    chin = max(beard_rows) if beard_rows else int(0.85 * hh)
    hd[chin + 2:, :, 3] = 0                                   # nothing of the head below the chin
    # NECK as its own layer (drawn behind the head and the torso): one skin tone from the
    # cheeks, rounded shading, from inside the jaw down into the collar
    cheek = skin.copy(); cheek[: int(0.35 * hh)] = False; cheek[int(0.6 * hh):] = False
    tone = np.median(hd[cheek][:, :3], 0) * 0.97 if cheek.any() else np.array([0.45, 0.6, 0.85])
    neck_w = int(mp.get("neck_w", 0.50) * head_w)
    top = int(chin - 0.16 * hh)
    ext = int(mp.get("neck_ext", 110))
    nh = int(chin - top + ext)
    neck = np.zeros((nh, neck_w + 8, 4), np.float32)
    xs = np.arange(neck_w + 8, dtype=np.float32)
    u = (xs - (neck_w + 8) / 2) / (neck_w / 2)
    inside = np.clip((1 - np.abs(u)) * neck_w / 3, 0, 1)                    # 1.5 px soft edge
    shade = 1.0 - 0.18 * np.clip(u, -1, 1) ** 2
    ol = np.array([0.13, 0.12, 0.16])                                       # drawing outline colour
    edge = np.abs(np.abs(u) - 1) * neck_w / 2 < 1.6                          # 3 px side outline
    for y in range(nh):
        d = y - (chin - top)
        k = 1.0 - 0.10 * np.clip(1 - abs(d - 10) / 28.0, 0, 1)                # soft shadow just under the jaw
        row = tone[None, :] * (shade * k)[:, None]
        row[edge] = ol
        neck[y, :, :3] = row
        neck[y, :, 3] = np.maximum(inside, edge * 1.0)
    P["neck"] = neck
    off["neck"] = (int(off["head"][0] + cx - (neck_w + 8) / 2), int(off["head"][1] + top + int(mp.get("head_drop", 80))))
    P["head"] = hd
    rig_head_shift = int(mp.get("head_drop", 80))
    off["head"] = (off["head"][0], off["head"][1] + rig_head_shift)
    Hs = pb.key_green(cv2.imread(a.hands))
    hlab, hst = comps(Hs)
    # scale sheet hands so their cuff width matches the forearm's cuff width
    fa_e = {s: ends(P["farm_" + s]) for s in ("L", "R")}
    cuff_w = np.mean([fa_e[s]["bot_hw"] for s in ("L", "R")]) * 2
    hands = {}
    for name, i in mp["hands"].items():
        h, _ = cut(Hs, hlab, hst, i)
        h = strip_sleeve(h)
        e = ends(h)
        k = cuff_w * 1.04 / (2 * e["bot_hw"])
        h = cv2.resize(h, None, fx=k, fy=k, interpolation=cv2.INTER_AREA).clip(0, 1)
        hands[name] = h
    rig = {"pieces": {}, "hands": {}, "sheet": [E.shape[1], E.shape[0]]}
    for name, pc in P.items():
        pb.save(out / "pieces" / f"{name}.png", pc)
        rig["pieces"][name] = {"pos": off[name], "size": [pc.shape[1], pc.shape[0]], **ends(pc)}
    for name, h in hands.items():
        pb.save(out / "pieces" / f"{name}.png", h)
        e = ends(h)
        # pivot: centre of the cuff, a little above its bottom edge; axis: wrist -> fingertips (up)
        piv = [e["bottom"][0], e["bottom"][1] - 0.35 * e["bot_hw"]]
        # REAL finger direction: pivot -> centroid of the skin pixels farthest from the pivot
        # (palm-up "presenting" hands point sideways, not up; assuming -90 aimed them wrong)
        hsv_h = cv2.cvtColor((np.clip(h[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        sk = (hsv_h[..., 0] < 25) & (hsv_h[..., 1] > 50) & (h[..., 3] > 0.5)
        ys_, xs_ = np.nonzero(sk)
        if len(xs_) > 50:
            d = np.hypot(xs_ - piv[0], ys_ - piv[1])
            far = d > np.percentile(d, 80)
            fx, fy = xs_[far].mean(), ys_[far].mean()
            axis = math.degrees(math.atan2(fy - piv[1], fx - piv[0]))
        else:
            axis = -90.0
        rig["hands"][name] = {"size": [h.shape[1], h.shape[0]], "pivot": piv, "axis": round(axis, 2),
                              "side": mp["hand_side"][name]}
    # joints in SHEET coordinates
    J = {}
    for s in ("L", "R"):
        ua, fa = rig["pieces"]["uarm_" + s], rig["pieces"]["farm_" + s]
        ux, uy = ua["pos"]; fx, fy = fa["pos"]
        shoulder = [ux + ua["top"][0], uy + ua["top"][1] + ua["top_hw"]]
        elbow_u = [ux + ua["bottom"][0], uy + ua["bottom"][1] - ua["bot_hw"]]
        elbow_f = [fx + fa["top"][0], fy + fa["top"][1] + fa["top_hw"]]
        wrist = [fx + fa["bottom"][0], fy + fa["bottom"][1] - 0.35 * fa["bot_hw"]]
        J[s] = {"shoulder": shoulder, "elbow_u": elbow_u, "elbow_f": elbow_f, "wrist": wrist,
                "fdir": math.degrees(math.atan2(wrist[1] - elbow_f[1], wrist[0] - elbow_f[0])),
                "udir": math.degrees(math.atan2(elbow_u[1] - shoulder[1], elbow_u[0] - shoulder[0]))}
        hr = rig["pieces"]["hand_" + s + "_rest"]
        hx, hy = hr["pos"]
        J[s]["hand_rest_pivot"] = [hr["top"][0], hr["top"][1] + 4]          # in its own pixels
        J[s]["hand_rest_axis"] = math.degrees(math.atan2(hr["bottom"][1] - hr["top"][1], hr["bottom"][0] - hr["top"][0]))
    if a.clasp:
        Cs = pb.key_green(cv2.imread(a.clasp))
        clab, cst = comps(Cs)
        ids = sorted([i for i in range(1, cst.shape[0]) if cst[i][4] > 2000], key=lambda i: cst[i][0])
        cp, _ = cut(Cs, clab, cst, ids[0])
        hsv_c = cv2.cvtColor((np.clip(cp[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        cuff = ((hsv_c[..., 0] > 90) & (hsv_c[..., 0] < 125) & (hsv_c[..., 1] > 25) & (hsv_c[..., 2] > 150) & (cp[..., 3] > 0.5)).astype(np.uint8)
        n_, l_, s_, c_ = cv2.connectedComponentsWithStats(cuff, 8)
        bl = sorted([c_[i] for i in range(1, n_) if s_[i][4] > 30], key=lambda c: -0)  # all blobs
        bl = sorted(bl, key=lambda c: c[0])
        cL, cR = bl[0], bl[-1]
        # scale so the clasp's cuff width matches the forearm cuff width
        cw = np.mean([s_[i][3] for i in range(1, n_) if s_[i][4] > 30]) if n_ > 1 else 30
        k = (cuff_w * 0.8) / max(cw, 1)
        cp = cv2.resize(cp, None, fx=k, fy=k, interpolation=cv2.INTER_AREA).clip(0, 1)
        pb.save(out / "pieces" / "clasp.png", cp)
        rig["clasp"] = {"size": [cp.shape[1], cp.shape[0]], "cuffL": [float(cL[0] * k), float(cL[1] * k)],
                        "cuffR": [float(cR[0] * k), float(cR[1] * k)]}
    t, hd = rig["pieces"]["torso"], rig["pieces"]["head"]
    rig["joints"] = J
    rig["neck_gap"] = (t["pos"][1] + t["top"][1]) - (hd["pos"][1] + hd["bottom"][1])
    (out / "rig.json").write_text(json.dumps(rig, indent=1))
    if a.poses:
        preview(rig, out, json.loads(pathlib.Path(a.poses).read_text()))
    rig["arm_shift"] = shifts
    (out / "rig.json").write_text(json.dumps(rig, indent=1))
    print(json.dumps({"ok": True, "arm_shift": shifts, "joints": {s: {k: [round(v, 1) for v in J[s][k]] if isinstance(J[s][k], list) else round(J[s][k], 1)
                                               for k in ("shoulder", "elbow_u", "elbow_f", "wrist", "fdir")} for s in J},
                      "neck_gap": rig["neck_gap"], "hand_scale_cuff_w": round(float(cuff_w), 1)}))


def rot(deg):
    t = math.radians(deg)
    return np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])


def place(canvas, img, pivot_px, deg, at):
    R = rot(deg)
    M = np.zeros((2, 3), np.float32)
    M[:, :2] = R
    M[:, 2] = np.array(at) - R @ np.array(pivot_px)
    w = pb.warp(img, M, (canvas.shape[1], canvas.shape[0]))
    al = w[..., 3:4]
    canvas[..., :3] = w[..., :3] * al + canvas[..., :3] * (1 - al)
    canvas[..., 3:4] = al + canvas[..., 3:4] * (1 - al)


def solve(rig, pose, s):
    """World angles for one arm: shoulder S, forearm dir F, hand dir H -> rotations to apply."""
    J = rig["joints"][s]
    S = pose.get("S_" + s, 0.0)
    F = pose.get("F_" + s, J["fdir"] + S)
    hand = pose.get("hand_" + s, "rest")
    return S, F, hand


def preview(rig, out, poses):
    W, H = rig["sheet"]
    tiles = []
    for name, pose in poses.items():
        cv = np.zeros((H, W, 4), np.float32)
        load = lambda n: cv2.imread(str(out / "pieces" / f"{n}.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
        arms = {}
        for s in ("L", "R"):
            J = rig["joints"][s]
            S, F, hand = solve(rig, pose, s)
            sh = np.array(J["shoulder"])
            eu = sh + rot(S) @ (np.array(J["elbow_u"]) - sh)
            # forearm: rotate its sheet pose about elbow_f so its axis points along F, elbow_f -> eu
            fdeg = F - J["fdir"]
            wr = eu + rot(fdeg) @ (np.array(J["wrist"]) - np.array(J["elbow_f"]))
            arms[s] = (S, fdeg, eu, wr, F, hand)
        # upper arms behind the torso
        for s in ("L", "R"):
            ua = rig["pieces"]["uarm_" + s]; J = rig["joints"][s]
            px = [J["shoulder"][0] - ua["pos"][0], J["shoulder"][1] - ua["pos"][1]]
            place(cv, load("uarm_" + s), px, arms[s][0], J["shoulder"])
        nk = rig["pieces"]["neck"]
        place(cv, load("neck"), [0, 0], 0, nk["pos"])            # neck behind head and collar
        hd = rig["pieces"]["head"]
        place(cv, load("head"), [0, 0], 0, hd["pos"])
        t = rig["pieces"]["torso"]
        place(cv, load("torso"), [0, 0], 0, t["pos"])
        for s in ("L", "R"):
            S, fdeg, eu, wr, F, hand = arms[s]
            fa = rig["pieces"]["farm_" + s]; J = rig["joints"][s]
            if hand == "rest":                                   # rest hand tucks under the cuff
                hr = rig["pieces"]["hand_" + s + "_rest"]
                hdeg = pose.get("H_" + s, F) - J["hand_rest_axis"]
                place(cv, load("hand_" + s + "_rest"), J["hand_rest_pivot"], hdeg, wr)
            px = [J["elbow_f"][0] - fa["pos"][0], J["elbow_f"][1] - fa["pos"][1]]
            place(cv, load("farm_" + s), px, fdeg, eu)
            if hand != "rest":
                hh = rig["hands"][hand]
                Hd = pose.get("H_" + s, F)
                place(cv, load(hand), hh["pivot"], Hd - hh["axis"], wr)
        bg = np.full(cv.shape[:2] + (3,), 0.82)
        tile = (cv[..., :3] * cv[..., 3:4] + bg * (1 - cv[..., 3:4])) * 255
        tile = cv2.resize(tile.astype(np.uint8), None, fx=0.45, fy=0.45)
        cv2.putText(tile, name, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        tiles.append(tile)
    cv2.imwrite(str(out / "preview_poses.png"), np.hstack(tiles))


if __name__ == "__main__":
    sys.exit(main())
