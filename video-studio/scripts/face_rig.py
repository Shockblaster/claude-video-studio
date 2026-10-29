#!/usr/bin/env python3
"""ONE-DRAWING face rig: every mouth / blink / brow state is a smooth warp (plus painted
mouth interior and eyelids) of the SAME head image, so nothing can shimmer or double.

  python -I face_rig.py --head head.png --out face_dir [--parts-head parts_head.png]
         [--scale 2.0] [--debug]

head.png        the head on chroma green (or RGBA). If --parts-head is given, head.png is
                aligned onto it (same scale as the body parts) and cut to its outline.
Output in face_dir:
  base.png                    the neutral head (canvas size)
  upper_<eyes>.png            full-canvas states for the upper face (open, half, closed,
                              surprise, think)
  lower_<shape>.png           full-canvas states for the lower face (Rhubarb X A B C D E F G H)
  face.json                   split row (upper rows [0,split), lower [split,H)), landmarks
  debug_face.png              every state composited, READ IT
Upper and lower warps are exactly zero at the split row, so U + L stack without a seam.
"""
import argparse
import json
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import puppet_build as pb  # noqa: E402

SHAPES = ["X", "A", "B", "C", "D", "E", "F", "G", "H"]
# jaw drop (fraction of mouth width), pucker (width scale), teeth, tongue
VISEME = {
    "X": (0.00, 1.00, 0, 0), "A": (0.00, 0.97, 0, 0), "B": (0.10, 1.03, 1, 0),
    "C": (0.20, 1.02, 1, 0), "D": (0.34, 1.00, 1, 1), "E": (0.22, 0.84, 1, 0),
    "F": (0.09, 0.72, 0, 0), "G": (0.07, 1.00, 1, 0), "H": (0.20, 0.98, 1, 1),
}
EYES = {"open": (0.0, 0.0), "half": (0.5, 0.0), "closed": (1.0, 0.0),
        "surprise": (0.0, -1.0), "think": (0.12, 0.55)}   # (lid fraction, brow move: -up / +down)


def rgba_from(path):
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 4:
        return im.astype(np.float32) / 255.0
    return pb.key_green(im)


def landmarks(head):
    """Mouth line, mouth corners, eye boxes, brow band, from colour on the head drawing."""
    H, W = head.shape[:2]
    bgr = (np.clip(head[..., :3], 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    a = head[..., 3] > 0.9
    ys, xs = np.nonzero(a)
    top, bot = ys.min(), ys.max()
    # eyes: bright low-saturation (sclera) blobs in the upper half
    scl = (hsv[..., 1] < 45) & (hsv[..., 2] > 200) & a
    scl[: top + int(0.25 * (bot - top))] = False
    scl[top + int(0.6 * (bot - top)):] = False
    n, lab, st, cen = cv2.connectedComponentsWithStats(scl.astype(np.uint8), 8)
    blobs = sorted([st[i] for i in range(1, n) if st[i][4] > 30], key=lambda s: -s[4])[:2]
    if len(blobs) < 2:
        raise SystemExit("could not find both eyes")
    eyes = sorted([[int(v) for v in b[:4]] for b in blobs], key=lambda b: b[0])
    # include the iris: grow the eye box to the dark iris inside it
    grown = []
    for x, y, w, h in eyes:
        pad_x, pad_y = int(0.25 * w), int(0.6 * h)
        grown.append([x - pad_x // 2, y - pad_y // 2, w + pad_x, h + pad_y])
    eyes = grown
    eye_bottom = max(y + h for x, y, w, h in eyes)
    eye_top = min(y for x, y, w, h in eyes)
    face_cx = int(np.mean([x + w / 2 for x, y, w, h in eyes]))
    eye_span = (eyes[1][0] + eyes[1][2]) - eyes[0][0]
    # mouth: reddish lip pixels below the eyes
    lip = (((hsv[..., 0] < 12) | (hsv[..., 0] > 168)) & (hsv[..., 1] > 70) & (hsv[..., 2] > 70)
           & (hsv[..., 2] < 235) & a)
    lip[: eye_bottom + int(0.15 * (bot - top))] = False
    lip[:, : face_cx - eye_span // 2] = False
    lip[:, face_cx + eye_span // 2:] = False
    lip = cv2.morphologyEx(lip.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(lip, 8)
    if n < 2:
        raise SystemExit("could not find the lips")
    i = 1 + int(np.argmax(st[1:, 4]))
    mx, my, mw, mh, _ = [int(v) for v in st[i]]
    # lip line: darkest pixel per column inside the lip box
    v = hsv[..., 2].astype(np.float32)
    line = {}
    for x in range(mx, mx + mw):
        col = v[my:my + mh, x]
        line[x] = my + int(np.argmin(col))
    ly = int(np.median(list(line.values())))
    # brows: dark band above the eyes
    dark = (hsv[..., 2] < 80) & a
    band0 = max(top, eye_top - int(0.45 * (eye_bottom - eye_top)) - int(0.08 * (bot - top)))
    rows = dark[band0:eye_top, eyes[0][0]:eyes[1][0] + eyes[1][2]].sum(1)
    brow_y = band0 + int(np.argmax(rows)) if rows.size else eye_top - 20
    return {"top": int(top), "bottom": int(bot), "eyes": eyes, "eye_top": int(eye_top),
            "eye_bottom": int(eye_bottom), "face_cx": face_cx, "eye_span": int(eye_span),
            "mouth": [mx, my, mw, mh], "lip_y": ly, "brow_y": int(brow_y)}


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def remap(img, mx, my):
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)).clip(0, 1)


def lower_state(head, L, shape, split):
    H, W = head.shape[:2]
    drop, pucker, teeth, tongue = VISEME[shape]
    mx, my, mw, mh = L["mouth"]
    cx = mx + mw / 2.0
    ly = L["lip_y"]
    d = drop * mw
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # jaw: rows below the lip line move down by d * wx, fading out before the collar
    jaw_half = 0.95 * L["eye_span"] / 2
    wx = smoothstep(1 - np.abs(xx - cx) / jaw_half)
    chin = L["bottom"]
    wy = smoothstep((yy - ly) / 3.0) * (1 - smoothstep((yy - (chin - 0.10 * (chin - ly))) / (0.35 * (chin - ly) + 1)))
    src_y = yy - d * wx * wy
    # pucker: horizontal squeeze around the mouth, zero at the split row
    k = pucker
    pz = smoothstep(1 - np.abs(xx - cx) / (0.9 * mw)) * smoothstep((yy - split) / (ly - split + 1)) \
        * (1 - smoothstep((yy - (ly + 0.9 * mh)) / (0.8 * mh + 1)))
    src_x = xx + (xx - cx) * (1 / k - 1) * pz
    out = remap(head, src_x, src_y)
    if d > 0.5:
        # mouth interior in the opened gap: between the lip line and the moved lower lip
        half_w = 0.5 * mw * k * 0.92
        prof = np.clip(1 - ((xx - cx) / half_w) ** 2, 0, 1) ** 0.6           # elliptical opening
        gap_top = ly
        gap_bot = ly + d * prof
        inside = (yy >= gap_top) & (yy <= gap_bot) & (prof > 0)
        # soft edge mask at 1 px
        dist = np.minimum(yy - gap_top, gap_bot - yy)
        m = np.clip(dist / 1.2 + 0.5, 0, 1) * (prof > 0.02)
        col = np.zeros((H, W, 3), np.float32)
        tdepth = (yy - gap_top) / np.maximum(d * prof, 1)
        base_c = np.array([0.10, 0.09, 0.30])                                   # BGR dark red
        deep_c = np.array([0.06, 0.05, 0.18])
        col[:] = base_c
        col = col * (1 - tdepth[..., None] * 0.5) + deep_c * (tdepth[..., None] * 0.5)
        if teeth:
            th = np.clip(0.30 * d, 1.5, 0.45 * d)
            tm = (yy - gap_top) < th * prof
            col[tm] = np.array([0.93, 0.94, 0.96])
            shade = tm & ((yy - gap_top) > th * prof - 1.2)
            col[shade] = np.array([0.78, 0.79, 0.83])
        if tongue:
            tcy = gap_top + 0.78 * d * prof
            tg = ((xx - cx) / (0.55 * half_w)) ** 2 + ((yy - tcy) / (0.30 * d + 1)) ** 2 < 1
            tg &= inside
            col[tg] = np.array([0.42, 0.42, 0.80])
        m = m * inside
        out[..., :3] = out[..., :3] * (1 - m[..., None]) + col * m[..., None]
        out[..., 3] = np.maximum(out[..., 3], m)
    return out


def upper_state(head, L, state, split):
    H, W = head.shape[:2]
    lid, brow = EYES[state]
    out = head.copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if brow:
        # brows move up (-) or down (+); zero at the glasses top (eye_top) and well above
        amp = brow * 0.30 * (L["eye_bottom"] - L["eye_top"])
        by = L["brow_y"]
        span = L["eye_top"] - by
        wy = smoothstep((yy - (by - 2.2 * span)) / (1.6 * span + 1)) * (1 - smoothstep((yy - by) / (0.9 * span + 1)))
        ex0 = L["eyes"][0][0] - 0.2 * L["eyes"][0][2]
        ex1 = L["eyes"][1][0] + 1.2 * L["eyes"][1][2]
        wx = smoothstep((xx - ex0) / 15.0) * smoothstep((ex1 - xx) / 15.0)
        if state == "think":     # inner ends down more: a frown
            inner = 1 - np.abs(xx - L["face_cx"]) / (0.5 * L["eye_span"])
            wx = wx * (0.4 + 0.6 * np.clip(inner, 0, 1))
        out = remap(out, xx, yy - (-amp) * wx * wy * -1 if False else yy + amp * wx * wy)
    if lid > 0:
        bgr = out[..., :3]
        for (x, y, w, h) in L["eyes"]:
            # skin tone from just above the eye (inside the glasses), lash colour from the darkest edge
            sy0, sy1 = max(0, y - int(0.35 * h)), max(1, y - 1)
            skin = np.median(bgr[sy0:sy1, x + w // 4:x + 3 * w // 4].reshape(-1, 3), 0)
            lash = np.array([0.10, 0.09, 0.10])
            cxe, cye = x + w / 2, y + h / 2
            rx, ry = w / 2, h / 2
            inside_eye = ((xx - cxe) / rx) ** 2 + ((yy - cye) / ry) ** 2 <= 1.0
            edge_y = (y) + lid * h * 1.02                                     # lid edge, straight-ish
            curve = edge_y + 0.10 * h * (1 - ((xx - cxe) / rx) ** 2)          # slight downward arc
            cover = inside_eye & (yy <= curve)
            soft = np.clip((curve - yy) / 1.0, 0, 1) * inside_eye
            bgr = bgr * (1 - soft[..., None]) + skin * soft[..., None]
            lash_m = inside_eye & (np.abs(yy - curve) < max(1.2, 0.07 * h))
            bgr[lash_m] = lash
        out[..., :3] = bgr
    return out


from face_paint import EYES, VISEME, lip_seal_check, lower_state, upper_state  # noqa: E402,F811  (supersampled versions)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--head", required=True)
    ap.add_argument("--parts-head")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--landmarks", help="JSON with hand-measured landmarks (overrides detection): "
                    "mouth [x,y,w,h] of the lips, lip_y, eyes [[x,y,w,h],[x,y,w,h]] of the visible eye, "
                    "brow_y, eye_top (glasses top), bottom (chin)")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    head = rgba_from(a.head)
    if a.parts_head:
        ph = rgba_from(a.parts_head)
        ph = cv2.resize(ph, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_CUBIC).clip(0, 1)
        M = pb.align(head, ph)
        head = pb.warp(head, M, (ph.shape[1], ph.shape[0]))
        # outline from the parts head (it matches the torso's neck); hi-res pixels inside
        # the hi-res head carries its OWN shirt collar (sitting higher than the body's): strip it,
        # the parts head / torso supply the only collar (a doubled collar was the user's "neck
        # and collar" seam)
        hsv = cv2.cvtColor((np.clip(head[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        yy_ = np.arange(head.shape[0])[:, None]
        shirt = (hsv[..., 0] > 85) & (hsv[..., 0] < 130) & (hsv[..., 2] > 140) & (yy_ > 0.65 * head.shape[0])
        shirt = cv2.dilate(shirt.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        head[..., 3] = np.where(shirt, 0, head[..., 3])
        keep = cv2.GaussianBlur((ph[..., 3] > 0.5).astype(np.float32), (0, 0), 1.0)
        head[..., 3] = np.minimum(head[..., 3], keep)
        # below the hi-res head's own outline, fall back to the parts head (collar)
        fill = (head[..., 3] < 0.5) & (ph[..., 3] > 0.5)
        head[fill] = ph[fill]
    if a.landmarks:
        L = json.loads(pathlib.Path(a.landmarks).read_text())
        L.setdefault("eye_bottom", max(e[1] + e[3] for e in L["eyes"]))
        L.setdefault("face_cx", int(L["mouth"][0] + L["mouth"][2] / 2))
        L.setdefault("eye_span", int(L["eyes"][1][0] + L["eyes"][1][2] - L["eyes"][0][0]))
        L.setdefault("top", int(np.nonzero(head[..., 3].max(1) > 0.5)[0].min()))
    else:
        L = landmarks(head)   # automatic: unreliable on stylised faces, CHECK debug_face.png
    H, W = head.shape[:2]
    if L.get("jaw"):
        # cut the face along the jaw outline (hand-measured polyline, canvas px): below it the
        # separate neck layer and the torso collar take over, nothing of either drawing's own
        # neck / collar / lapel stays in the face
        poly = np.array([[0, 0], [W - 1, 0], [W - 1, L["jaw"][-1][1]]] + L["jaw"][::-1] + [[0, L["jaw"][0][1]]], np.int32)
        m = np.zeros((H, W), np.float32)
        cv2.fillPoly(m, [poly], 1.0)
        m = cv2.GaussianBlur(m, (0, 0), 1.0)
        head[..., 3] *= m
    # split row: between the eye bottoms and the moustache top (both warps are zero there)
    split = int(L["eye_bottom"] + 0.35 * (L["mouth"][1] - L["eye_bottom"]))
    L["split"] = split
    pb.save(out / "base.png", head)
    states = {}
    for s in SHAPES:
        im = lower_state(head, L, s, split); pb.save(out / f"lower_{s}.png", im); states["lower_" + s] = im
    for e in EYES:
        im = upper_state(head, L, e, split); pb.save(out / f"upper_{e}.png", im); states["upper_" + e] = im
    # verify the seam: upper and lower warps must equal the base on the split row
    seam = max(float(np.abs(states["lower_" + s][split - 1:split + 1] - head[split - 1:split + 1]).max()) for s in SHAPES)
    seam = max(seam, max(float(np.abs(states["upper_" + e][split:split + 2] - head[split:split + 2]).max()) for e in EYES))
    # lip-seal gate (2026-10-29): no skin may show inside any mouth opening (a gap between the lips)
    seal = {s: lip_seal_check(head, L, s, split, states["lower_" + s]) for s in SHAPES}
    seal_ok = max(seal.values()) <= 0.01
    if not seal_ok:
        print("LIP SEAL FAIL (skin inside the mouth opening):", {k: v for k, v in seal.items() if v > 0.01}, file=sys.stderr)
    (out / "face.json").write_text(json.dumps({"canvas": [W, H], "split": split, "landmarks": L,
                                               "shapes": SHAPES, "eyes": list(EYES), "seam_max_diff": round(seam, 4),
                                               "lip_seal": seal, "lip_seal_ok": seal_ok}, indent=1))
    # mouth zoom sheet: every shape at 3x around the lips, READ IT (corners must meet, no skin strip)
    mx_, my_, mw_, mh_ = L["mouth"]
    zy0, zy1, zx0, zx1 = max(0, my_ - 25), my_ + mh_ + int(0.4 * mw_), max(0, mx_ - 30), mx_ + mw_ + 30
    zt = []
    for s_ in SHAPES:
        u_, l_ = states["upper_open"][zy0:zy1, zx0:zx1], states["lower_" + s_][zy0:zy1, zx0:zx1]
        rows_ = np.arange(zy0, zy1)[:, None, None]
        c_ = np.where(rows_ < split, u_, l_)                              # crop first: cheap on a 6 GB laptop
        z = (np.clip(c_[..., :3] * c_[..., 3:4] + 0.5 * (1 - c_[..., 3:4]), 0, 1) * 255).astype(np.uint8)
        z = cv2.resize(z, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        cv2.putText(z, f"{s_} seal {seal[s_]}", (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)
        zt.append(z)
    cv2.imwrite(str(out / "mouth_zoom.png"), np.vstack([np.hstack(zt[i:i + 3]) for i in range(0, 9, 3)]))
    # debug: each state as the composite the scene will show
    y0 = max(0, L["top"]); y1 = L["bottom"]

    def comp(u, l):                       # crop to the face rows FIRST, float32: fits a 6 GB laptop
        c = np.vstack([u[y0:split], l[split:y1]]).astype(np.float32)
        return c[..., :3] * c[..., 3:4] + np.float32(0.5) * (1 - c[..., 3:4])
    tiles = [comp(states["upper_open"], states["lower_" + s]) for s in SHAPES] + \
            [comp(states["upper_" + e], states["lower_X"]) for e in EYES]
    tiles = [(t * 255).astype(np.uint8) for t in tiles]
    for t, lab in zip(tiles, SHAPES + list(EYES)):
        cv2.putText(t, lab, (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)
    rows = [np.hstack(tiles[i:i + 7]) for i in range(0, 14, 7)]
    cv2.imwrite(str(out / "debug_face.png"), np.vstack(rows))
    print(json.dumps({"ok": seal_ok, "lip_seal_ok": seal_ok, "split": split, "seam_max_diff": round(seam, 4), "mouth": L["mouth"], "eyes": L["eyes"]}))


if __name__ == "__main__":
    sys.exit(main())
