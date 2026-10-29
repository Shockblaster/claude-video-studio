#!/usr/bin/env python3
"""Cutout-puppet body rig from a generated PARTS SHEET (head, torso, separate upper arms,
forearms with hands) on chroma green. Limbs rotate smoothly at real joints, so gestures
travel instead of teleporting; hand shapes swap on the forearm mid-motion.

  python -I cutout_rig.py --sheet parts.png --map map.json --out rig_dir [--preview pose.json]

map.json names the sheet's connected components (reading order, see --list) and how the
pieces join:
  {"pieces": {"head": 1, "torso": 2, "uarm_L": 3, ...},
   "upper_arms": ["uarm_L", "uarm_R"], "forearms": {"fore_relax_L": "L", "fore_point": "R", ...},
   "head_offset": [0, 40]}     # extra shift of the head onto the neck, sheet px
Writes rig_dir/pieces/*.png, rig_dir/rig.json (every piece's joint points in its own pixel
coordinates + the attach points on the torso), and preview PNGs for READING.
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


def components(P):
    a = (P[..., 3] > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(a, 8)
    comps = [i for i in range(1, n) if st[i][4] > 2000]
    return lab, st, comps


def skin_mask(rgb):
    hsv = cv2.cvtColor((np.clip(rgb, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    return (hsv[..., 0] < 25) & (hsv[..., 1] > 60) & (hsv[..., 2] > 120)


def limb_joints(piece, kind):
    """Joint points (piece pixel coords). Upper arm: shoulder = top end, elbow = bottom end.
    Forearm: elbow = sleeve end farthest from the hand's skin; hand = skin centroid."""
    a = piece[..., 3] > 0.5
    ys, xs = np.nonzero(a)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    ax = vt[0]
    proj = (pts - c) @ ax
    perp = np.array([-ax[1], ax[0]])

    def inward(e, toward):
        near = pts[np.abs(((pts - c) @ ax) - ((e - c) @ ax)) < 20]
        hw = (((near - c) @ perp).max() - ((near - c) @ perp).min()) / 2 if len(near) > 5 else 15
        d = toward - e
        d = d / (np.linalg.norm(d) + 1e-6)
        return e + d * hw * 0.9, hw

    if kind == "upper":
        e1, e2 = c + ax * proj.min(), c + ax * proj.max()
        top, bot = (e1, e2) if e1[1] < e2[1] else (e2, e1)
        s, hw_s = inward(top, bot)
        e, hw_e = inward(bot, top)
        return {"shoulder": s.tolist(), "elbow": e.tolist(), "radius": float(hw_e)}
    sk = skin_mask(piece[..., :3]) & a
    hand = np.stack(np.nonzero(sk)[::-1], 1).mean(0) if sk.sum() > 50 else c + ax * proj.max()
    far = pts[np.argmax(np.linalg.norm(pts - hand, axis=1))]
    e, hw = inward(far, hand)
    return {"elbow": e.tolist(), "hand": hand.tolist(), "radius": float(hw)}


def torso_attach(torso):
    """Shoulder sockets: centres of the round caps at the torso's left/right top; neck: top centre."""
    a = torso[..., 3] > 0.5
    ys, xs = np.nonzero(a)
    top, bot = ys.min(), ys.max()
    h = bot - top
    band = a.copy()
    band[: top + int(0.05 * h)] = False
    band[top + int(0.35 * h):] = False
    sockets = []
    for side in (-1, 1):
        cols = np.nonzero(band.any(0))[0]
        xe = cols.min() if side < 0 else cols.max()
        rows = np.nonzero(band[:, xe])[0]
        yc = rows.mean()
        r = 0.06 * (xs.max() - xs.min())
        sockets.append([float(xe - side * r), float(yc)])
    neck_cols = np.nonzero(a[top + 2])[0]
    neck = [float(neck_cols.mean()), float(top)]
    return {"socket_L": sockets[0], "socket_R": sockets[1], "neck": neck}


def place(canvas, piece, M):
    w = pb.warp(piece, M, (canvas.shape[1], canvas.shape[0]))
    a = w[..., 3:4]
    canvas[..., :3] = w[..., :3] * a + canvas[..., :3] * (1 - a)
    canvas[..., 3:4] = a + canvas[..., 3:4] * (1 - a)


def rot_about(px, py, deg, tx, ty):
    """Affine: rotate about (px,py) by deg, then move (px,py) to (tx,ty)."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return np.array([[c, -s, tx - c * px + s * py], [s, c, ty - s * px - c * py]], np.float32)


def compose(rig, pieces, pose, size):
    """Python preview of a pose, the same maths as the HyperFrames scene."""
    W, H = size
    canvas = np.zeros((H, W, 4), np.float32)
    T = rig["torso_pos"]
    att = rig["torso_attach"]
    for side in ("L", "R"):
        ua = rig["upper_" + side]
        sock = [T[0] + att["socket_" + side][0], T[1] + att["socket_" + side][1]]
        ang = pose["shoulder_" + side]
        place(canvas, pieces[ua["name"]], rot_about(*ua["shoulder"], ang, *sock))
    place(canvas, pieces["torso"], np.array([[1, 0, T[0]], [0, 1, T[1]]], np.float32))
    for side in ("L", "R"):
        ua = rig["upper_" + side]
        sock = [T[0] + att["socket_" + side][0], T[1] + att["socket_" + side][1]]
        ang = math.radians(pose["shoulder_" + side])
        ex, ey = ua["elbow"][0] - ua["shoulder"][0], ua["elbow"][1] - ua["shoulder"][1]
        elbow = [sock[0] + math.cos(ang) * ex - math.sin(ang) * ey, sock[1] + math.sin(ang) * ex + math.cos(ang) * ey]
        fa = rig["forearms"][pose["hand_" + side]]
        # forearm angle: its rest axis rotated so it points along (upper-arm direction + elbow bend)
        up = math.atan2(ey, ex) + ang
        rest = math.atan2(fa["hand"][1] - fa["elbow"][1], fa["hand"][0] - fa["elbow"][0])
        if ("fdir_" + side) in pose:      # absolute forearm direction, degrees (90 = down, -90 = up)
            deg = pose["fdir_" + side] - math.degrees(rest)
        else:
            deg = math.degrees(up - rest) + pose.get("elbow_" + side, 0)
        place(canvas, pieces[fa["name"]], rot_about(*fa["elbow"], deg, *elbow))
    hp = rig["head_pos"]
    place(canvas, pieces["head"], rot_about(rig["head_pivot"][0], rig["head_pivot"][1], pose.get("head", 0),
                                            hp[0] + rig["head_pivot"][0], hp[1] + rig["head_pivot"][1]))
    return canvas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--map")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--poses", help="JSON file: {name: {shoulder_L, elbow_L, hand_L, shoulder_R, ...}}")
    a = ap.parse_args()
    P = pb.key_green(cv2.imread(a.sheet))
    lab, st, comps = components(P)
    if a.list:
        for i in comps:
            print(i, [int(v) for v in st[i]])
        return 0
    mp = json.loads(pathlib.Path(a.map).read_text())
    out = pathlib.Path(a.out); (out / "pieces").mkdir(parents=True, exist_ok=True)
    pieces, boxes = {}, {}
    for name, i in mp["pieces"].items():
        x, y, w, h, _ = st[i]
        pad = 8
        x0, y0 = max(0, x - pad), max(0, y - pad)
        pc = P[y0:y + h + pad, x0:x + w + pad].copy()
        pc[..., 3] *= (lab[y0:y + h + pad, x0:x + w + pad] == i)
        pieces[name] = pc
        boxes[name] = [int(x0), int(y0)]
        pb.save(out / "pieces" / f"{name}.png", pc)
    torso = pieces["torso"]
    att = torso_attach(torso)
    rig = {"pieces": list(pieces), "torso_attach": att, "forearms": {}}
    for side, ua_name in zip(("L", "R"), mp["upper_arms"]):
        j = limb_joints(pieces[ua_name], "upper"); j["name"] = ua_name
        rig["upper_" + side] = j
    for fa_name, side in mp["forearms"].items():
        j = limb_joints(pieces[fa_name], "fore"); j["name"] = fa_name; j["side"] = side
        rig["forearms"][fa_name] = j
    # layout: torso at its sheet position; head on the neck (its bottom-centre onto the torso neck)
    rig["torso_pos"] = boxes["torso"]
    hd = pieces["head"]
    ha = hd[..., 3] > 0.5
    hys, hxs = np.nonzero(ha)
    head_bottom = [float(hxs[hys > hys.max() - 6].mean()), float(hys.max())]
    off = mp.get("head_offset", [0, 0])
    neck_abs = [rig["torso_pos"][0] + att["neck"][0], rig["torso_pos"][1] + att["neck"][1]]
    rig["head_pivot"] = [head_bottom[0], head_bottom[1] - 0.12 * (hys.max() - hys.min())]
    rig["head_pos"] = [neck_abs[0] - head_bottom[0] + off[0], neck_abs[1] - head_bottom[1] + off[1]]
    rig["sheet_size"] = [P.shape[1], P.shape[0]]
    (out / "rig.json").write_text(json.dumps(rig, indent=1))
    if a.poses:
        poses = json.loads(pathlib.Path(a.poses).read_text())
        tiles = []
        for name, pose in poses.items():
            c = compose(rig, pieces, pose, (P.shape[1], P.shape[0]))
            bg = np.full(c.shape[:2] + (3,), 0.82)
            t = (c[..., :3] * c[..., 3:4] + bg * (1 - c[..., 3:4])) * 255
            t = cv2.resize(t.astype(np.uint8), None, fx=0.5, fy=0.5)
            cv2.putText(t, name, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
            tiles.append(t)
        cv2.imwrite(str(out / "preview_poses.png"), np.hstack(tiles))
    print(json.dumps({"ok": True, "attach": att, "head_pos": rig["head_pos"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
