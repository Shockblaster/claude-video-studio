#!/usr/bin/env python3
"""EXPRESSION PRESETS for a one-drawing face rig (2026-10-31).
Every expression is made locally from the ONE approved head (no new image generation):

  python -I face_expr.py --rig rig/face --landmarks rig/face_landmarks.json [--exprs happy,worried,surprised,raise]

Reads rig/face/base.png + face.json (made by face_rig.py), writes per expression E:
  upper_E_open.png, upper_E_half.png, upper_E_closed.png     brows + eyes of E, with blinks
  lower_E_<X..H>.png                                          all 9 Rhubarb mouths ON the E face
  upper_E50_* / lower_E50_*                                   the 50% in-between of E (for transitions)
  mouth_zoom_E.png                                            3x lips per shape (READ IT)
and adds "expressions" to face.json (lip-seal result per expression: every one must pass).
Also writes rig/face/expressions.png (one row per preset: open, blink, X, D) and brow_zoom_expr.png.

How an expression is built (head_E = one warped copy of the head, so upper and lower stay seamless):
  1. BROWS as a layer (brow_layer): the glasses-frame top is FITTED as a curve from the columns where
     a skin gap shows between brow and frame; the brow pixels above that curve are lifted off (soft
     alpha from darkness), the forehead under them is refilled (column colour from above the brow +
     the forehead's own grain), and the brows are pasted back moved: raise, arch, inner-raise, knit.
     Brows only ever move UP or sideways, never into the frame (the frame is never warped).
     (The old warp and band-reflection moves broke the frame and left striped patches: that is why
     the earlier rigs shipped with no_brows.)
  2. EYES: a small vertical scale inside each eye box (surprised wider, happy a touch narrower).
  3. MOUTH: a smile / frown field that lifts or drops the mouth corners (zero at the split row and
     at the chin). The lip line is moved with the same field, so face_paint's mouths (and the lip-seal
     gate) work on the expression face exactly as on the neutral one.
"""
import argparse
import json
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import face_paint as fp  # noqa: E402
import puppet_build as pb  # noqa: E402

SHAPES = ["X", "A", "B", "C", "D", "E", "F", "G", "H"]
LIDS = {"open": 0.0, "half": 0.55, "closed": 1.0}
# amounts: brow moves in eye heights (h = eye box height), smile in mouth widths, eye scale factor
EXPRS = {
    "happy":     {"raise": 0.35, "arch": 0.15, "eye": 0.90, "smile": 0.095, "widen": 0.04},
    "worried":   {"raise": 0.15, "inner": 1.25, "knit": 0.25, "eye": 1.04, "smile": -0.070, "widen": -0.04},
    "surprised": {"raise": 1.20, "arch": 0.35, "eye": 1.12, "smile": -0.015, "widen": -0.03},
    "raise":     {"raise": 0.70, "arch": 0.15},             # an emphasis beat: brows up, nothing else
}


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- brows
def frame_top_curve(head, L, dark=70, max_run=16):
    """Fit the glasses frame's top edge y(x) across the brow span. Per column, scanning UP from just
    above the eye box, the first dark run is the frame; if it is longer than max_run the brow is fused
    to it and the column is skipped. A 4th-degree fit with outlier rejection fills the fused columns."""
    v = (np.clip(head[..., :3], 0, 1).max(2) * 255)
    (x0e, y0e, w0, h0), (x1e, y1e, w1, h1) = L["eyes"]
    xa, xb = int(x0e - 0.35 * w0), int(x1e + 1.35 * w1)
    ystart = int(min(y0e, y1e)) - 2
    ytop = int(L.get("brow_top", L["brow_y"] - 15)) - 40
    xs, ys = [], []
    for x in range(xa, xb):
        col = v[ytop:ystart, x][::-1]                 # upward from ystart
        dk = col < dark
        idx = np.nonzero(dk)[0]
        if not len(idx):
            continue
        # the first dark run at least 3 px thick: thinner runs are the upper lash / lid line (1-2 px),
        # which pulled the whole curve down to the frame's BOTTOM edge and erased the bar
        found = False
        for i0 in idx:
            if i0 >= 40:
                break
            i1 = i0
            while i1 + 1 < len(col) and dk[i1 + 1]:
                i1 += 1
            if i1 - i0 + 1 >= 3:
                found = True
                break
        if not found or i1 - i0 + 1 > max_run:
            continue
        # a grey specular line (1-3 px) on the frame's top edge belongs to the frame
        k = i1
        while k + 1 < len(col) and k - i1 < 3 and dark <= col[k + 1] < 190:
            k += 1
        xs.append(x); ys.append(ystart - 1 - k)          # top row of the frame
    xs, ys = np.array(xs, np.float64), np.array(ys, np.float64)
    if len(xs) < 20:
        raise SystemExit("frame_top_curve: too few clean columns (brows fused to the frame everywhere?)")
    keep = np.ones(len(xs), bool)
    for _ in range(4):
        c = np.polyfit(xs[keep], ys[keep], 4)
        r = ys - np.polyval(c, xs)
        s = 1.4826 * np.median(np.abs(r[keep])) + 0.75
        keep = np.abs(r) < 2.5 * s
    X = np.arange(head.shape[1])
    fy = np.polyval(c, np.clip(X, xa, xb - 1))
    return fy, (xa, xb), float(keep.mean())


def brow_masks(head, L, fy, span):
    """Soft brow alpha (only on the brow blobs, wrinkles excluded) and the refill region."""
    H, W = head.shape[:2]
    v = (np.clip(head[..., :3], 0, 1).max(2) * 255).astype(np.float32)
    xa, xb = span
    yy, xx = np.mgrid[0:H, 0:W]
    fyy = fy[None, :]
    above = np.clip(fyy - yy, 0, 1).astype(np.float32)               # soft: 1 above the frame top, 0 on it
    band = (yy < fyy) & (yy > int(L.get("brow_top", L["brow_y"] - 15)) - 35) & (xx >= xa) & (xx < xb)
    core = (v < 90) & band
    core = cv2.morphologyEx(core.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(core, 8)
    big = np.zeros((H, W), np.uint8)
    for i in range(1, n):
        if st[i, 4] > 400:                            # brows are big blobs; hair wisps / wrinkles are not
            big[lab == i] = 1
    # the light wispy hairs at the brow ends belong to the brow too (left behind, they read as ghost hairs)
    near = cv2.dilate(big, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))).astype(bool)
    g = cv2.cvtColor((np.clip(head[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    skin_g = float(np.median(g[band & ~near])) if (band & ~near).any() else 190.0
    # brown wisps on orange skin keep a high max channel: judge darkness by luminance vs the skin
    # ...but saturated orange SHADING (high max channel) is skin, not hair: counting it moved a grey
    # haze up with the brow and walled off the fill
    wisp = ((g < skin_g - 40) & (v < 175) & band).astype(np.uint8)
    n2, lab2, _, _ = cv2.connectedComponentsWithStats(wisp, 8)
    hit = np.unique(lab2[near & (wisp > 0)]); hit = hit[hit > 0]
    wisp = np.isin(lab2, hit).astype(np.uint8)
    region = (cv2.dilate(big, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) |
              cv2.dilate(wisp, np.ones((7, 7), np.uint8))).astype(bool) & (yy < fyy + 2)
    # every column under a brow is cleared all the way down to the frame: thin wisps lying right on the
    # frame escaped the blob masks and stayed behind as stubble when the brow rose
    # widen sideways so the region's ends land on clean skin past the last wisps (an end ON the wisps
    # left stray hairs and gave the fill no skin to anchor to: a vertical step at the inner brow ends)
    btop = int(L.get("brow_top", L["brow_y"] - 15)) - 35
    region = cv2.dilate(region.astype(np.uint8), np.ones((5, 27), np.uint8)).astype(bool) & \
        (yy < fyy + 2) & (yy > btop) & (xx >= xa) & (xx < xb)
    has = region.any(0)
    topr = np.where(has, region.argmax(0), H)
    region |= has[None, :] & (yy >= topr[None, :]) & (yy < fyy + 2)
    skin_v = float(np.median(v[band & ~near])) if (band & ~near).any() else 245.0
    alpha = np.clip((skin_v - 12 - v) / (skin_v - 40), 0, 1) * region * (yy < fyy - 1)
    # the brow's bottom edge was cut flat where it sat on the frame: fade it over ~5 px so a raised
    # brow keeps a soft, natural underside instead of a ruler-straight cut
    alpha = alpha * smoothstep((fyy - 1.5 - yy) / 3.0)          # 6 px read as a grey haze when raised
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), 0.6) * region
    return alpha, region, above


def refill_forehead(head, region, above, fy):
    """Forehead skin under the brows: per column a vertical gradient from the skin just above the brow
    to the skin just above the frame (taken from the columns where a gap shows, interpolated across the
    fused ones), plus the forehead's own fine texture copied from the band above. The fill stops on
    the fitted frame-top curve (anti-aliased), so the frame keeps one crisp top edge."""
    H, W = head.shape[:2]
    out = head.copy()
    ys, xs = np.nonzero(region)
    if not len(ys):
        return out
    v = np.clip(head[..., :3], 0, 1).max(2) * 255
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    hgt = y1 - y0
    nx = x1 - x0
    top_c = np.zeros((nx, 3), np.float32); top_y = np.zeros(nx, np.float32)
    bot_c = np.full((nx, 3), np.nan, np.float32)
    for i, x in enumerate(range(x0, x1)):
        col = np.nonzero(region[y0:y1, x])[0]
        yt = y0 + (col.min() if len(col) else 0) - 3
        top_y[i] = yt
        top_c[i] = np.median(head[max(0, yt - 6):max(1, yt), x, :3], 0)
        f = int(round(fy[x]))
        seg = head[f - 6:f - 2, x, :3]; sv = v[f - 6:f - 2, x]
        if len(sv) and (sv > 140).all():
            bot_c[i] = np.median(seg, 0)
    ok = ~np.isnan(bot_c[:, 0])
    for c in range(3):
        bot_c[:, c] = np.interp(np.arange(nx), np.nonzero(ok)[0], bot_c[ok, c]) if ok.sum() > 3 else top_c[:, c]
    top_c = cv2.GaussianBlur(top_c[None], (0, 0), 16)[0]
    bot_c = cv2.GaussianBlur(bot_c[None], (0, 0), 9)[0]
    Y = np.arange(y0, y1, dtype=np.float32)[:, None]
    fyc = fy[x0:x1][None, :].astype(np.float32)
    t = np.clip((Y - top_y[None, :]) / np.maximum(fyc - top_y[None, :], 1), 0, 1)[..., None]
    src = head[max(0, y0 - hgt - 4):y0 - 4, x0:x1, :3]
    src = cv2.resize(src, (nx, hgt)) if src.shape[0] != hgt else src
    gsrc = cv2.cvtColor((np.clip(src, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    skin_src = (gsrc > np.median(gsrc) - 35).astype(np.float32)          # never copy hair strokes as grain
    grain = np.clip((src - cv2.GaussianBlur(src, (0, 0), 4)) * cv2.GaussianBlur(skin_src, (0, 0), 1.5)[..., None], -0.05, 0.05)
    base_fill = top_c[None] * (1 - t) + bot_c[None] * t
    # harmonic fill (Laplace, Jacobi): the colour inside the brow region is solved from the SKIN around
    # it, so it meets the surroundings without a block edge (a column-sampled gradient left a lighter
    # patch under one brow). The frame below and dark hair are no-flux (never bleed in).
    pad = 12
    Y0, Y1, X0, X1 = max(0, y0 - pad), min(H, y1 + pad), max(0, x0 - pad), min(W, x1 + pad)
    sub = head[Y0:Y1, X0:X1, :3].astype(np.float32).copy()
    Z = region[Y0:Y1, X0:X1] & (np.arange(Y0, Y1)[:, None] < fy[X0:X1][None, :])
    gsub = cv2.cvtColor((np.clip(sub, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    skin_g = float(np.median(gsub[~Z & (gsub > 120)])) if (~Z & (gsub > 120)).any() else 180.0
    vsub = np.clip(sub, 0, 1).max(2) * 255
    frame_or_dark = (np.arange(Y0, Y1)[:, None] >= fy[X0:X1][None, :]) | (vsub < 150)   # hair / brow / frame only
    # the frame's top row under the brows is a KNOWN boundary with the skin tone measured just above the
    # frame (bot_c): with a no-flux bottom the fill took only the lighter forehead colour (a pale band)
    for i, x in enumerate(range(x0, x1)):
        if region[:, x].any():
            r = int(np.ceil(fy[x])) - Y0
            if 0 <= r < sub.shape[0]:
                sub[r, x - X0] = bot_c[i]; frame_or_dark[r, x - X0] = False; Z[r, x - X0] = False
    Wt = (Z | ~frame_or_dark).astype(np.float32)
    sub[Z] = base_fill[(np.nonzero(Z)[0] + Y0 - y0).clip(0, hgt - 1), (np.nonzero(Z)[1] + X0 - x0).clip(0, nx - 1)]
    kern = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], np.float32)
    den = cv2.filter2D(Wt, -1, kern, borderType=cv2.BORDER_CONSTANT)
    for _ in range(700):
        num = cv2.filter2D(sub * Wt[..., None], -1, kern, borderType=cv2.BORDER_CONSTANT)
        upd = num / np.maximum(den[..., None], 1e-6)
        sub[Z] = upd[Z]
    harm = sub[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0]
    fill = harm + grain[::-1]
    reg = region[y0:y1, x0:x1]
    m = cv2.GaussianBlur(cv2.dilate(reg.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 2.5)
    m = np.maximum(m, reg) * above[y0:y1, x0:x1]
    blk = out[y0:y1, x0:x1]
    blk[..., :3] = blk[..., :3] * (1 - m[..., None]) + np.clip(fill, 0, 1) * m[..., None]
    return out


def brow_layer(head, L, raise_=0.0, arch=0.0, inner=0.0, knit=0.0, _cache={}):
    """Move the brows as a layer (see the module doc). Returns a new head."""
    key = id(head)
    if key not in _cache:
        fy, span, ok = frame_top_curve(head, L)
        alpha, region, above = brow_masks(head, L, fy, span)
        _cache.clear()
        _cache[key] = (fy, span, alpha, region, above, refill_forehead(head, region, above, fy))
    fy, span, alpha, region, above, clean = _cache[key]
    if not (raise_ or arch or inner or knit):
        return head.copy()
    H, W = head.shape[:2]
    h = float(np.mean([e[3] for e in L["eyes"]]))
    cx = float(L.get("face_cx", (L["eyes"][0][0] + L["eyes"][1][0] + L["eyes"][1][2]) / 2))
    half = (L["eyes"][1][0] + L["eyes"][1][2] - L["eyes"][0][0]) / 2.0 * 1.15
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = np.clip(np.abs(xx - cx) / half, 0, 1)                       # 0 at the nose, 1 at the outer ends
    # per brow: arch peaks at its middle; inner = the inner end up (worried)
    um = np.clip(1 - np.abs(u - 0.55) / 0.45, 0, 1)
    dy = -(raise_ * 0.55 * h + arch * 0.55 * h * um ** 1.5 + inner * 0.55 * h * np.clip(1 - u / 0.65, 0, 1) ** 1.3)
    dx = -np.sign(xx - cx) * knit * 0.55 * h * np.clip(1 - u / 0.7, 0, 1)
    layer = np.dstack([head[..., :3], alpha])
    moved = fp.remap(layer, xx - dx, yy - dy)
    a = moved[..., 3:4] * above[..., None]                          # never onto or below the frame
    out = clean.copy()
    out[..., :3] = moved[..., :3] * a + clean[..., :3] * (1 - a)
    return out


# ---------------------------------------------------------------- eyes
def eye_scale(head, L, s):
    if abs(s - 1) < 1e-3:
        return head, L
    H, W = head.shape[:2]
    out = head.copy(); L2 = json.loads(json.dumps(L)); eyes2 = []
    for (x, y, w, h) in L["eyes"]:
        cxe, cye = x + w / 2.0, y + h / 2.0
        x0, x1, y0, y1 = int(x - 0.15 * w), int(x + 1.15 * w), int(cye - 1.05 * h), int(cye + 1.05 * h)
        X, Y = np.meshgrid(np.arange(x0, x1, dtype=np.float32), np.arange(y0, y1, dtype=np.float32))
        wgt = smoothstep(1 - np.abs(X - cxe) / (0.62 * w)) * smoothstep(1 - np.abs(Y - cye) / (1.05 * h))
        k = 1 + (s - 1) * wgt
        reg = fp.remap(head, X, cye + (Y - cye) / k)
        out[y0:y1, x0:x1] = reg
        nh = h * s
        eyes2.append([x, int(round(cye - nh / 2)), w, int(round(nh))])
    L2["eyes"] = eyes2
    return out, L2


# ---------------------------------------------------------------- mouth
def smile_field(L, split, smile, widen, shape):
    """Displacement (dx, dy) in px on the full canvas: corners up (smile > 0) or down, mouth wider or
    narrower; zero above the split row and at the chin."""
    H, W = shape
    mx, my, mw, mh = L["mouth"]
    lx = np.array(sorted(L["lip_line"]), np.float32) if L.get("lip_line") else None
    cl = (lx[0] if lx is not None else np.array([mx, L["lip_y"]], np.float32))
    cr = (lx[-1] if lx is not None else np.array([mx + mw, L["lip_y"]], np.float32))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = 0.38 * mw
    dx = np.zeros((H, W), np.float32); dy = np.zeros((H, W), np.float32)
    for c, side in ((cl, -1), (cr, 1)):
        g = np.exp(-(((xx - c[0]) / r) ** 2 + ((yy - c[1]) / (0.8 * r)) ** 2))
        dy += -smile * mw * g
        dx += side * widen * mw * g
    chin = L["bottom"]
    win = smoothstep((yy - split) / max(8.0, 0.6 * (L["lip_y"] - split))) * (1 - smoothstep((yy - (chin - 0.25 * (chin - L["lip_y"]))) / (0.3 * (chin - L["lip_y"]) + 1)))
    return dx * win, dy * win


def apply_smile(head, L, split, smile, widen):
    if not smile and not widen:
        return head, L
    H, W = head.shape[:2]
    dx, dy = smile_field(L, split, smile, widen, (H, W))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    out = fp.remap(head, xx - dx, yy - dy)                       # backward map: dest q shows src q - d(q)
    L2 = json.loads(json.dumps(L))

    def fwd(p):                                                  # src p -> dest q with q - d(q) = p
        q = np.array(p, np.float32)
        for _ in range(8):
            xi, yi = int(np.clip(round(q[0]), 0, W - 1)), int(np.clip(round(q[1]), 0, H - 1))
            q = np.array(p, np.float32) + np.array([dx[yi, xi], dy[yi, xi]])
        return q
    if L.get("lip_line"):
        L2["lip_line"] = [[round(float(a), 1), round(float(b), 1)] for a, b in (fwd(p) for p in L["lip_line"])]
        P = np.array(L2["lip_line"])
        mx, my, mw, mh = L["mouth"]
        o = np.array(sorted(L["lip_line"]))
        nx0 = mx + (P[:, 0].min() - o[:, 0].min()); nx1 = mx + mw + (P[:, 0].max() - o[:, 0].max())
        ny0 = my + min(0.0, P[:, 1].min() - o[:, 1].min())
        L2["mouth"] = [int(round(nx0)), int(round(ny0)), int(round(nx1 - nx0)), int(round(my + mh - ny0))]
        L2["lip_y"] = int(round(L["lip_y"] + np.median(P[:, 1] - o[:, 1])))
    return out, L2


# ---------------------------------------------------------------- build
def build_expression(head, L, split, p):
    he = brow_layer(head, L, p.get("raise", 0), p.get("arch", 0), p.get("inner", 0), p.get("knit", 0))
    he, Le = eye_scale(he, L, p.get("eye", 1.0))
    he, Le = apply_smile(he, Le, split, p.get("smile", 0.0), p.get("widen", 0.0))
    return he, Le


def comp_tile(u, l, split, y0, y1):
    c = np.vstack([u[y0:split], l[split:y1]]).astype(np.float32)
    return (np.clip(c[..., :3] * c[..., 3:4] + 0.5 * (1 - c[..., 3:4]), 0, 1) * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rig", required=True, help="face dir made by face_rig.py")
    ap.add_argument("--landmarks", required=True)
    ap.add_argument("--exprs", default=",".join(EXPRS))
    a = ap.parse_args()
    fd = pathlib.Path(a.rig)
    F = json.loads((fd / "face.json").read_text()); split = F["split"]
    L = json.loads(pathlib.Path(a.landmarks).read_text())
    for k, v in F["landmarks"].items():
        L.setdefault(k, v)
    head = cv2.imread(str(fd / "base.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    names = [e for e in a.exprs.split(",") if e]
    res = {}; rows = []
    y0, y1 = max(0, L["top"]), L["bottom"] + 30
    neutral_u = cv2.imread(str(fd / "upper_open.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    neutral = [comp_tile(neutral_u, cv2.imread(str(fd / f"lower_{s}.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255, split, y0, y1)
               for s in ("X", "D")]
    nu_c = cv2.imread(str(fd / "upper_closed.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    rows.append(["neutral", neutral[0], comp_tile(nu_c, cv2.imread(str(fd / "lower_X.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255, split, y0, y1), neutral[0], neutral[1]])
    brow_tiles = []
    # every preset also gets a 50% in-between (<name>50): avatar_track steps neutral -> 50% -> 100% so a
    # mood change MOVES over a few frames instead of snapping or dissolving (a dissolve doubles the brows)
    half = lambda P: {k: (1 + (v - 1) * 0.5 if k == "eye" else v * 0.5) for k, v in P.items()}
    jobs = [(e, EXPRS[e], True) for e in names] + [(e + "50", half(EXPRS[e]), False) for e in names]
    for e, P, full in jobs:
        he, Le = build_expression(head, L, split, P)
        ups = {}
        for lid, f in LIDS.items():
            im = he.copy() if f == 0 else (fp.lid_warp(he, Le, f) if Le.get("lid_mode") == "warp"
                                           else fp.upper_state(he, {**Le, "no_brows": True}, lid, split))
            pb.save(fd / f"upper_{e}_{lid}.png", im); ups[lid] = im
        lows = {}
        for s in SHAPES:
            im = fp.lower_state(he, Le, s, split); pb.save(fd / f"lower_{e}_{s}.png", im); lows[s] = im
        seal = {s: fp.lip_seal_check(he, Le, s, split, lows[s]) for s in SHAPES}
        ok = max(seal.values()) <= 0.01
        seam = max(float(np.abs(lows[s][split - 1:split + 1] - he[split - 1:split + 1]).max()) for s in SHAPES)
        res[e] = {"params": P, "eyes": list(LIDS), "shapes": SHAPES, "lip_seal": seal, "lip_seal_ok": ok,
                  "seam_max_diff": round(seam, 4), "lip_line": Le.get("lip_line"), "mouth": Le["mouth"]}
        if not ok:
            print(f"LIP SEAL FAIL on {e}:", {k: v for k, v in seal.items() if v > 0.01}, file=sys.stderr)
        if not full:
            continue
        # mouth zoom for this expression
        mx_, my_, mw_, mh_ = Le["mouth"]
        zy0, zy1, zx0, zx1 = max(0, my_ - 25), my_ + mh_ + int(0.4 * mw_), max(0, mx_ - 30), mx_ + mw_ + 30
        zt = []
        for s in SHAPES:
            rr = np.arange(zy0, zy1)[:, None, None]
            c_ = np.where(rr < split, ups["open"][zy0:zy1, zx0:zx1], lows[s][zy0:zy1, zx0:zx1])
            z = (np.clip(c_[..., :3] * c_[..., 3:4] + 0.5 * (1 - c_[..., 3:4]), 0, 1) * 255).astype(np.uint8)
            z = cv2.resize(z, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
            cv2.putText(z, f"{e} {s} seal {seal[s]}", (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)
            zt.append(z)
        cv2.imwrite(str(fd / f"mouth_zoom_{e}.png"), np.vstack([np.hstack(zt[i:i + 3]) for i in range(0, 9, 3)]))
        rows.append([e, comp_tile(ups["open"], lows["X"], split, y0, y1), comp_tile(ups["closed"], lows["X"], split, y0, y1),
                     comp_tile(ups["half"], lows["X"], split, y0, y1), comp_tile(ups["open"], lows["D"], split, y0, y1)])
        # brow zoom tile
        bx0 = L["eyes"][0][0] - 110; bx1 = L["eyes"][1][0] + L["eyes"][1][2] + 110
        by0 = L.get("brow_top", L["brow_y"] - 15) - 70; by1 = L["eyes"][0][1] + L["eyes"][0][3] + 60
        c_ = ups["open"][by0:by1, bx0:bx1].astype(np.float32)
        t = (np.clip(c_[..., :3] * c_[..., 3:4] + 0.5 * (1 - c_[..., 3:4]), 0, 1) * 255).astype(np.uint8)
        t = cv2.resize(t, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        cv2.putText(t, e, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 2)
        brow_tiles.append(t)
    sheet = []
    for r in rows:
        ts = [t.copy() for t in r[1:]]
        cv2.putText(ts[0], r[0], (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 255), 3)
        sheet.append(np.hstack(ts))
    cv2.imwrite(str(fd / "expressions.png"), np.vstack(sheet))
    if brow_tiles:
        cv2.imwrite(str(fd / "brow_zoom_expr.png"), np.vstack(brow_tiles))
    F["expressions"] = res
    (fd / "face.json").write_text(json.dumps(F, indent=1))
    allok = all(v["lip_seal_ok"] for v in res.values())
    print(json.dumps({"ok": allok, "lip_seal_ok": allok, "expressions": {k: {"seal_max": max(v["lip_seal"].values()),
                      "seam": v["seam_max_diff"]} for k, v in res.items()}}))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
