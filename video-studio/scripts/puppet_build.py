#!/usr/bin/env python3
"""Build a cutout puppet rig from three generated sheets on chroma green.

  python -I puppet_build.py --pose pose.png --mouth mouth.png --eyes eyes.png --out rig_dir
         [--poses relaxed,point,present,count] [--height 1500]

Sheets (see references/avatars.md for the prompts):
  pose.png   N waist-up figures side by side, same head, only the arms differ
  mouth.png  3x3 grid, same head, mouths in Rhubarb order X A B C D E F G H
  eyes.png   3x2 grid, same head: open, half, closed, surprise, think, side

Output in rig_dir:
  pose_<name>.png   full-canvas RGBA layers, every head aligned to pose 0
  mouth_<X..H>.png  feathered patches, eyes_<state>.png likewise
  rig.json          canvas size, patch positions, names
  debug_*.png       contact sheets to READ before using the rig
"""
import argparse
import json
import pathlib
import sys

import cv2
import numpy as np

MOUTHS = ["X", "A", "B", "C", "D", "E", "F", "G", "H"]
EYES = ["open", "half", "closed", "surprise", "think", "side"]


def key_green(bgr, max_hole=None):
    """Chroma key + despill. Returns BGRA float32 0..1.
    max_hole: only fill enclosed green regions up to this many px (specks); a pose with an
    arm away from the body encloses real background, which must stay keyed."""
    im = bgr.astype(np.float32)
    b, g, r = im[..., 0], im[..., 1], im[..., 2]
    spill = g - np.maximum(r, b)
    alpha = np.clip((90.0 - spill) / 60.0, 0, 1)          # spill>=90 -> 0, <=30 -> 1
    g2 = np.minimum(g, np.maximum(r, b) + 8)                # despill
    # fill holes INSIDE the character (greenish pixels between glasses and skin got keyed
    # out and showed the background through as specks); only the outside stays keyed
    solid = (alpha > 0.5).astype(np.uint8)
    flood = solid.copy()
    hh_, ww_ = flood.shape
    ffmask = np.zeros((hh_ + 2, ww_ + 2), np.uint8)
    for sx, sy in ((0, 0), (ww_ - 1, 0), (0, hh_ - 1), (ww_ - 1, hh_ - 1)):
        if flood[sy, sx] == 0:
            cv2.floodFill(flood, ffmask, (sx, sy), 2)
    holes = (flood == 0)
    if max_hole is not None and holes.any():
        nl, lab_, st_, _ = cv2.connectedComponentsWithStats(holes.astype(np.uint8), 8)
        big = np.nonzero(st_[1:, cv2.CC_STAT_AREA] > max_hole)[0] + 1
        holes &= ~np.isin(lab_, big)
    if holes.any():
        rgb8 = np.dstack([b, g2, r]).clip(0, 255).astype(np.uint8)
        rgb8 = cv2.inpaint(rgb8, holes.astype(np.uint8), 3, cv2.INPAINT_TELEA)
        b, g2, r = [rgb8[..., i].astype(np.float32) for i in range(3)]
        alpha = np.where(holes, 1.0, alpha)
    # pull the edge in by a pixel and soften it: removes the dark dotted fringe on hair
    a8 = (alpha * 255).astype(np.uint8)
    a8 = cv2.erode(a8, np.ones((3, 3), np.uint8))
    alpha = cv2.GaussianBlur(a8, (0, 0), 0.8).astype(np.float32) / 255.0
    # edge colour bleed: soft-edge pixels still carry green-screen colour (a speckled
    # magenta/green fringe along the jaw in the audit). Give every non-solid pixel the
    # colour of the nearest solid interior pixel; only alpha stays soft.
    rgb8 = np.dstack([b, g2, r]).clip(0, 255).astype(np.uint8)
    edge = ((alpha < 0.98) & (alpha > 0.0)).astype(np.uint8)
    solid_px = alpha >= 0.98
    if edge.any() and solid_px.any():
        fill = rgb8.copy()
        fill[~solid_px] = 0
        known = solid_px.astype(np.uint8)
        for _ in range(6):                   # grow solid colour outward a few px
            grown = cv2.dilate(fill, np.ones((3, 3), np.uint8))
            kd = cv2.dilate(known, np.ones((3, 3), np.uint8))
            new = (kd > 0) & (known == 0)
            # average of known neighbours (sum / count) for the newly reached pixels
            s = cv2.blur(fill.astype(np.float32) * known[..., None], (3, 3))
            c = cv2.blur(known.astype(np.float32), (3, 3))[..., None]
            avg = (s / np.maximum(c, 1e-6)).clip(0, 255).astype(np.uint8)
            fill[new] = avg[new]
            known = np.maximum(known, new.astype(np.uint8))
        rgb8 = np.where(edge[..., None] > 0, fill, rgb8)
        b, g2, r = [rgb8[..., i].astype(np.float32) for i in range(3)]
    out = np.dstack([b, g2, r, alpha * 255]) / 255.0
    return out


def split_by_heads(bgra, expected):
    """Watershed split of touching figures, seeded from the head band."""
    a = (bgra[..., 3] > 0.5).astype(np.uint8)
    ys_fg = np.nonzero(a.any(1))[0]
    top, bot = ys_fg.min(), ys_fg.max()
    best = None
    # heads live in the top ~40% of the figures; arms and hands lower down also separate
    for y0 in range(top, top + int(0.4 * (bot - top)), 6):
        band = np.zeros_like(a)
        band[y0:y0 + 40] = a[y0:y0 + 40]
        n, lab, st, _ = cv2.connectedComponentsWithStats(band, 8)
        comps = [i for i in range(1, n) if st[i][4] > 300]
        if len(comps) == expected:
            best = (0, lab, comps, st)   # first band from the top = the heads
            break
    if best is None:
        raise SystemExit(f"could not find {expected} separate heads")
    _, lab, comps, st = best
    comps = sorted(comps, key=lambda i: st[i][0])
    markers = np.zeros(a.shape, np.int32)
    for k, i in enumerate(comps):
        markers[lab == i] = k + 2
        # spine seed: a thin strip under the head centre down to the bottom of the figure
        x, y, w, hh, _ = st[i]
        cx = x + w // 2
        strip = np.zeros_like(a)
        strip[y:bot, cx - 6:cx + 6] = 1
        markers[(strip == 1) & (a == 1)] = k + 2
    # geodesic growth: each label spreads only through foreground, one pixel ring per step,
    # so a figure keeps its own head and arms and touching neighbours split where they meet
    kernel = np.ones((3, 3), np.uint8)
    for _ in range(4000):
        free = (a == 1) & (markers == 0)
        if not free.any():
            break
        grew = False
        for k in range(expected):
            d = cv2.dilate((markers == k + 2).astype(np.uint8), kernel).astype(bool) & free
            if d.any():
                markers[d] = k + 2
                free &= ~d
                grew = True
        if not grew:
            break
    cells = []
    for k in range(expected):
        m = (markers == k + 2).astype(np.uint8)
        ys, xs = np.nonzero(m)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        cell = bgra[y0:y1, x0:x1].copy()
        cell[..., 3] *= m[y0:y1, x0:x1]
        cells.append(cell)
    return cells


def separated(bgra, expected):
    """Figures that do not touch: return them in reading order, else None."""
    a = (bgra[..., 3] > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(a, 8)
    comps = [i for i in range(1, n) if st[i][4] > 0.02 * a.size / expected]
    if len(comps) != expected:
        return None
    rowh = max(st[i][3] for i in comps) * 0.5
    comps.sort(key=lambda i: (round(st[i][1] / rowh), st[i][0]))
    out = []
    for i in comps:
        x, y, w, h, _ = st[i]
        c = bgra[y:y + h, x:x + w].copy()
        c[..., 3] *= (lab[y:y + h, x:x + w] == i)
        out.append(c)
    return out


def split_grid(bgra, cols, rows):
    """Split a grid by its separated components (falls back to head watershed per row)."""
    a = (bgra[..., 3] > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(a, 8)
    comps = [i for i in range(1, n) if st[i][4] > 5000]
    if len(comps) == cols * rows:
        comps.sort(key=lambda i: (round(st[i][1] / 100), st[i][0]))
        cells = []
        for i in comps:
            x, y, w, h, _ = st[i]
            c = bgra[y:y + h, x:x + w].copy()
            c[..., 3] *= (lab[y:y + h, x:x + w] == i)
            cells.append(c)
        return cells
    hh = bgra.shape[0] // rows
    cells = []
    for r in range(rows):
        cells += split_by_heads(bgra[r * hh:(r + 1) * hh], cols)
    return cells


def gray(bgra):
    g = cv2.cvtColor((bgra[..., :3] * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)
    g[bgra[..., 3] < 0.5] = 0
    return g


def head_box(bgra, frac=0.42):
    """Top part of a figure: the head region used for alignment."""
    ys, xs = np.nonzero(bgra[..., 3] > 0.5)
    top = ys.min()
    hh = int((ys.max() - top) * frac)
    return top, top + hh


def sift_match(gs, gd, ms, md):
    """(M, inliers) for a similarity transform src->dst from SIFT matches inside the masks."""
    sift = cv2.SIFT_create(6000)
    ks, ds = sift.detectAndCompute(gs, ms)
    kd, dd = sift.detectAndCompute(gd, md)
    if ds is None or dd is None or len(ds) < 10 or len(dd) < 10:
        return None, 0
    knn = cv2.BFMatcher(cv2.NORM_L2).knnMatch(ds, dd, k=2)
    mt = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(mt) < 10:
        return None, 0
    p1 = np.float32([ks[m.queryIdx].pt for m in mt])
    p2 = np.float32([kd[m.trainIdx].pt for m in mt])
    M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=4)
    return M, int(inl.sum()) if inl is not None else 0


def align(src, dst, dst_head=None):
    """Similarity transform mapping src onto dst using SIFT, refined by ECC.
    Tries the FACE first (hair strands differ between cells and dragged a long-haired
    character's blink cell ~25 px low), then the whole head band (flat cartoon skin can
    have too few face features)."""
    gs, gd = gray(src), gray(dst)
    t0, t1 = head_box(src)
    d0, d1 = dst_head or head_box(dst)
    face_s = (face_mask(src, (t0, t1)) * 255).astype(np.uint8)
    face_d = (face_mask(dst, (d0, d1)) * 255).astype(np.uint8)
    band_s = np.zeros_like(gs); band_s[t0:t1] = 255
    band_d = np.zeros_like(gd); band_d[d0:d1] = 255
    M, n = sift_match(gs, gd, face_s, face_d)
    if M is None or n < 15:
        M2, n2 = sift_match(gs, gd, band_s, band_d)
        if M2 is not None and n2 > n:
            M = M2
    if M is None:
        raise SystemExit("alignment failed (too few matches)")
    # ECC refinement on the head crop
    warped = cv2.warpAffine(gs, M, (gd.shape[1], gd.shape[0]))
    try:
        W = np.eye(2, 3, dtype=np.float32)
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)
        _, W = cv2.findTransformECC(gd[d0:d1].astype(np.float32), warped[d0:d1].astype(np.float32), W,
                                    cv2.MOTION_EUCLIDEAN, None, 5)
        A = np.vstack([M, [0, 0, 1]]); Wm = np.vstack([W, [0, 0, 1]])
        M = (np.linalg.inv(Wm) @ A)[:2]
    except cv2.error:
        pass
    return M


def warp(bgra, M, size):
    # Lanczos rings on hard black lines (glasses, outlines): values go below 0 / above 1, and
    # dividing by a small alpha later blew them up into cyan/red/white speckles. Clamp, and
    # zero the colour where alpha is ~0 so no division can amplify it.
    o = cv2.warpAffine(bgra, M, size, flags=cv2.INTER_LANCZOS4, borderValue=(0, 0, 0, 0))
    o = np.clip(o, 0.0, 1.0)
    o[o[..., 3] < 0.004] = 0
    return o


def face_mask(bgra, head):
    """Convex hull of the skin in the head band, stretched down over the chin/beard.
    Keeps feature detection off hair: long wavy hair differs between cells and won."""
    bgr = (bgra[..., :3] * 255).astype(np.uint8)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    skin = cv2.inRange(hsv, (0, 30, 70), (25, 210, 255)) > 0
    skin &= bgra[..., 3] > 0.9
    band = np.zeros_like(skin); band[head[0]:head[1]] = True
    skin = (skin & band).astype(np.uint8)
    skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(skin, 8)
    if n < 2:
        return np.ones(skin.shape, np.float32)
    i = 1 + int(np.argmax(st[1:, 4]))
    pts = cv2.findNonZero((lab == i).astype(np.uint8))
    hull = cv2.convexHull(pts)
    m = np.zeros(skin.shape, np.uint8)
    cv2.fillConvexPoly(m, hull, 1)
    x, y, w, h = cv2.boundingRect(hull)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, w // 10), max(3, int(h * 0.3)))))
    m[:y] = 0   # never above the skin top (hair)
    return m.astype(np.float32)


def change_box(stack, pad, ylim=None, mask=None):
    """Bounding box of the pixels that differ across aligned cells (the feature region).
    ylim=(y0, y1) restricts the search to a band (eyes live above the mouth)."""
    arr = np.stack([s[..., :3] for s in stack])
    alpha = np.min(np.stack([s[..., 3] for s in stack]), 0)
    v = arr.std(0).mean(-1) * (alpha > 0.9)
    if ylim:
        band = np.zeros_like(v); band[ylim[0]:ylim[1]] = 1
        v = v * band; alpha = alpha * band
    if mask is not None:
        v = v * mask; alpha = alpha * mask
    v = cv2.GaussianBlur(v, (0, 0), 3)
    # 92nd percentile: the whole feature, not just its strongest pixels (97 left the corners
    # of the base grin outside the patch, and they ghosted through as a double mouth)
    thr = np.percentile(v[alpha > 0.9], 92)
    m = (v > thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    i = 1 + int(np.argmax(st[1:, 4]))
    x, y, w, h, _ = st[i]
    # merge components close to the biggest (e.g. both eyes)
    for j in range(1, n):
        if j != i and st[j][4] > st[i][4] * 0.15:
            xx, yy, ww, hh, _ = st[j]
            x0, y0 = min(x, xx), min(y, yy); x1, y1 = max(x + w, xx + ww), max(y + h, yy + hh)
            x, y, w, h = x0, y0, x1 - x0, y1 - y0
    return max(0, x - pad), max(0, y - pad), w + 2 * pad, h + 2 * pad


def color_match(patch, ref):
    """Match patch colour stats to the reference region (Lab mean/std), alpha kept."""
    p = cv2.cvtColor((patch[..., :3] * 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    r = cv2.cvtColor((ref[..., :3] * 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    m = (patch[..., 3] > 0.9) & (ref[..., 3] > 0.9)
    if m.sum() < 50:
        return patch
    for c in range(3):
        ps, rs = p[..., c][m], r[..., c][m]
        p[..., c] = (p[..., c] - ps.mean()) * (rs.std() / (ps.std() + 1e-6)) + rs.mean()
    out = patch.copy()
    out[..., :3] = cv2.cvtColor(np.clip(p, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR) / 255.0
    return out


def feather_patch(full, box, feather):
    x, y, w, h = box
    p = full[y:y + h, x:x + w].copy()
    # rounded rectangle, feathered: keeps the corners of the box (an oval faded the eyes out)
    mask = np.zeros((h, w), np.float32)
    r = max(2, feather)
    cv2.rectangle(mask, (r, r), (w - r - 1, h - r - 1), 1, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), feather / 2)
    p[..., 3] = p[..., 3] * mask
    return p


def save(path, bgra):
    cv2.imwrite(str(path), np.clip(bgra * 255, 0, 255).astype(np.uint8))


def sheet(images, path, scale=0.35):
    tiles = []
    for im in images:
        bg = np.ones(im.shape[:2] + (3,), np.float32) * 0.92
        comp = im[..., :3] * im[..., 3:4] + bg * (1 - im[..., 3:4])
        t = cv2.resize((comp * 255).astype(np.uint8), None, fx=scale, fy=scale)
        tiles.append(t)
    h = max(t.shape[0] for t in tiles)
    row = np.hstack([np.pad(t, ((0, h - t.shape[0]), (4, 4), (0, 0)), constant_values=255) for t in tiles])
    cv2.imwrite(str(path), row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pose", required=True)
    ap.add_argument("--mouth", required=True)
    ap.add_argument("--eyes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--poses", default="relaxed,point,present,count")
    ap.add_argument("--height", type=int, default=1500, help="output canvas height in px")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    names = a.poses.split(",")

    pose_sheet = key_green(cv2.imread(a.pose))
    poses = separated(pose_sheet, len(names)) or split_by_heads(pose_sheet, len(names))
    mouths = split_grid(key_green(cv2.imread(a.mouth)), 3, 3)
    eyes = split_grid(key_green(cv2.imread(a.eyes)), 3, 2)
    if len(mouths) != 9 or len(eyes) != 6:
        raise SystemExit(f"grid split gave {len(mouths)} mouths, {len(eyes)} eyes")

    # canvas: pose 0 scaled to --height, padded so other poses' arms fit
    base = poses[0]
    s = a.height / base.shape[0]
    pad = int(0.35 * base.shape[1] * s)
    W, H = int(base.shape[1] * s) + 2 * pad, a.height
    S = np.array([[s, 0, pad], [0, s, 0]], np.float32)
    canvas_base = warp(base, S, (W, H))
    size = (W, H)

    pose_layers = [canvas_base]
    for p in poses[1:]:
        M = align(p, canvas_base)
        pose_layers.append(warp(p, M, size))
    # common bottom edge: crop every pose at the highest of their bottoms so nothing jumps
    bottom = min(int(np.nonzero(l[..., 3].max(1) > 0.5)[0].max()) for l in pose_layers) - 2
    for l in pose_layers:
        l[bottom:] = 0
    for n, layer in zip(names, pose_layers):
        save(out / f"pose_{n}.png", layer)

    head = head_box(canvas_base)
    m_al = [warp(m, align(m, canvas_base, head), size) for m in mouths]
    e_al = [warp(e, align(e, canvas_base, head), size) for e in eyes]

    # ONE HEAD FOR EVERY POSE. Each pose cell drew its own head (different jaw, beard edge,
    # ears); mouth patches from the mouth grid on top of those gave a doubled jaw and
    # double mouths (user caught it, 2026-10-26). The neutral mouth cell becomes the head
    # plate: every pose's own head is erased and the plate goes on top, so all mouth
    # patches come from the same drawing as the face they sit on.
    plate = m_al[0]
    pf = face_mask(plate, head)        # the base's head band: the plate's own band was too short
    pfx, pfy, pfw, pfh_raw = cv2.boundingRect((pf > 0).astype(np.uint8))
    # The skin hull is dilated and a beard is not skin, so its box says nothing reliable about
    # the chin (it put "chin" at the shoulders and the shoulders got erased = a light gap).
    # The chin is the bottom of what MOVES across the mouth cells (the jaw drops on "AA").
    # Neither skin (beards, V-necks) nor mouth motion locate the chin reliably. The silhouette
    # does: the NECK is the narrowest row between head and shoulders (with long hair, the dip
    # where hair meets shoulders). Measured on all four characters, 2026-10-26.
    pa = plate[..., 3] > 0.5
    rows = np.nonzero(pa.any(1))[0]
    ptop, pbot = int(rows.min()), int(rows.max())
    widths = np.convolve(pa.sum(1).astype(np.float32), np.ones(9) / 9, mode="same")
    lo, hi = ptop + int(0.5 * (pbot - ptop)), ptop + int(0.85 * (pbot - ptop))
    # narrowest row = bottom of the chin/beard (a beard tapers); the collar/shoulders start
    # where the width climbs past 1.2x that. The head fades out in that band, BELOW the chin
    # (fading above it showed the pose's own chin under the plate's = a double chin)
    def chin_neck(alpha_rows):
        w = np.convolve(alpha_rows, np.ones(9) / 9, mode="same")
        c = lo + int(np.argmin(w[lo:hi]))
        aft = np.nonzero(w[c:hi] > 1.2 * w[c])[0]
        return c, c + (int(aft[0]) if len(aft) else int(0.08 * (pbot - ptop)))
    chin_y, neck_plate = chin_neck(pa.sum(1).astype(np.float32))
    # the POSE was drawn with its own (often lower) chin: measured on the relaxed pose,
    # whose arms hang below the head. The hand-over has to sit under BOTH chins, or the
    # pose's beard shows below the plate's = a double chin
    chin_pose, neck_pose = chin_neck((pose_layers[0][..., 3] > 0.5).sum(1).astype(np.float32))
    neck_y = max(neck_plate, neck_pose)
    fade_from = max(chin_y, chin_pose)
    pfh = max(20, chin_y - pfy)        # forehead skin top to chin: every band below uses this
    ramp = int(max(6, min(0.07 * pfh, neck_y - fade_from)))
    plate_bottom = pbot
    # finish above the plate cell's own cut edge too (that edge showed as a light line)
    neck = min(H - 1, neck_y, plate_bottom - ramp - 6)
    yy = np.arange(H, dtype=np.float32)[:, None]
    keep_top = np.clip((neck - yy) / ramp, 0, 1)              # 1 above the neck line, fades out
    plate_layer = plate.copy()
    plate_layer[..., 3] *= keep_top[:, 0][:, None]
    # below the cheeks keep only the neck column: the plate's own shoulder outline sat a few
    # px off the pose's and showed as a thin double edge on top of the shoulders
    xx = np.arange(W, dtype=np.float32)[None, :]
    # below the CHIN only a narrow neck column survives (wider columns kept slivers of the
    # head drawing's own shoulders, which smudged against the pose's shoulder outline)
    cx0, cx1 = pfx + 0.14 * pfw, pfx + pfw * 0.86
    soft = max(6.0, 0.06 * pfw)
    col = np.clip(np.minimum(xx - cx0, cx1 - xx) / soft, 0, 1)            # 1 inside the column
    # full width down to the measured neck (below both chins); only then the neck column.
    # Trimming from the plate's chin left the pose's wider, lower beard uncovered
    below = np.clip((yy - (neck - ramp)) / soft, 0, 1)
    plate_layer[..., 3] *= 1 - below * (1 - col)
    plate_mask = keep_top * (1 - below * (1 - col))                        # where the head lives
    # LOWER FACE COMES WHOLE FROM THE MOUTH CELL. Lips pursing changes the moustache, beard
    # and jaw; a small mouth patch blended two moustaches and two jaws at its edge (user:
    # "the jaw also had problems... overlap... looked very weird"). Each mouth shape now
    # supplies everything from the nose down (jaw outline included); the plate has no
    # lower face. The only blend is a soft band across the nose/cheeks: plain skin.
    # the lower face starts just under the lowest pixel that changes across the EYE cells
    # (data, not a guess: a fixed fraction would cut through glasses on some faces)
    erx, ery, erw, erh = change_box(e_al, pad=0, ylim=(pfy, pfy + int(0.6 * pfh)), mask=pf)
    lf0 = float(ery + erh + int(0.02 * H))
    # long band: a pursed-lip drawing has puffed (wider, darker) cheeks; a short band showed
    # that step as stray lines across the cheeks
    lf_ramp = max(12.0, 0.12 * pfh)
    lower = np.clip((yy - lf0) / lf_ramp, 0, 1)                             # 0 above, 1 below
    full_plate_cov = cv2.dilate((plate_layer[..., 3] > 0.5).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    # plate stays solid through the band (mouth layer fades in over it), gone below it
    plate_layer[..., 3] *= (lower < 0.999)
    reach = cv2.dilate((pf > 0).astype(np.uint8), np.ones((int(0.25 * pfw) | 1, int(0.25 * pfw) | 1), np.uint8))
    for k, L in enumerate(pose_layers):
        a8 = (L[..., 3] > 0.3).astype(np.uint8)
        a8[neck:] = 0
        n, lab, st, _ = cv2.connectedComponentsWithStats(a8, 8)
        erase = np.zeros(a8.shape, bool)
        for i in range(1, n):
            comp = lab == i
            if (comp & (reach > 0)).any():                    # the pose's own head (+ hair)
                erase |= comp                                 # a raised hand elsewhere survives
        erase = cv2.dilate(erase.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        # erase only ABOVE the fade zone; inside it the pose stays solid and the plate fades
        # over it (fading both left a see-through band across the shoulders)
        full_plate = (keep_top[:, 0] >= 0.999)[:, None]
        # and only where the plate really covers (its trimmed shoulders left notches when
        # the pose's own shoulder tops were erased too)
        covered = full_plate_cov     # the FULL plate (incl. the lower face the mouth layer supplies)
        # above the cheeks the pose head goes completely (a partial erase left a thin shell of
        # the pose's own hair outside the plate's hair = a light halo)
        upper = (yy < pfy + 0.75 * pfh)
        # above the hand-over band the pose's head component goes completely: the band now
        # sits below both chins, so nothing of the pose's own face can show
        L[..., 3] = np.where(erase & full_plate, 0, L[..., 3])
        a = plate_layer[..., 3:4]
        rgb = plate_layer[..., :3] * a + L[..., :3] * L[..., 3:4] * (1 - a)
        alpha = a + L[..., 3:4] * (1 - a)
        pose_layers[k] = np.clip(np.dstack([rgb / np.maximum(alpha, 0.02), alpha]), 0, 1)
    canvas_base = pose_layers[0]
    for n_, layer in zip(names, pose_layers):
        save(out / f"pose_{n_}.png", layer)

    feather = max(6, int(0.012 * H))
    # search bands come from face proportions: a 3D mouth sheet whose eyes also varied
    # stretched the mouth box up to the eyes; collar differences pulled it into the shirt
    # measure the face on the PLATE: pose layers no longer have a lower face
    face = pf
    fx, fy, fw, fh = pfx, pfy, pfw, pfh
    # mouth layers: the whole lower face of each mouth cell, masked like the plate
    mmask = plate_mask * lower
    content = np.max(np.stack([m[..., 3] for m in m_al]), 0) * mmask         # real pixels only
    ys_, xs_ = np.nonzero(content > 0.01)
    mbox = (int(xs_.min()), int(ys_.min()), int(xs_.max() - xs_.min() + 1), int(ys_.max() - ys_.min() + 1))
    ebox = change_box(e_al + [canvas_base], pad=int(0.028 * H), ylim=(fy, fy + int(0.6 * fh)), mask=face)
    # eyes stop at the start of the lower-face band (two noses blended otherwise)
    ex, ey, ew, eh = ebox
    ebox = (ex, ey, ew, max(10, min(eh, int(lf0 + 0.5 * lf_ramp) - ey)))
    rig = {"canvas": [W, H], "bottom": int(bottom), "head": [int(head[0]), int(head[1])], "neck": int(neck),
           "poses": names, "mouth": {"box": [int(v) for v in mbox], "shapes": MOUTHS},
           "eyes": {"box": [int(v) for v in ebox], "states": EYES}}
    ref = canvas_base
    x0, y0, w0, h0 = mbox
    # match each mouth drawing's skin tone to the plate in the blend band (cheeks)
    band = np.zeros((H, W), bool)
    band[int(lf0):int(lf0 + lf_ramp)] = True
    band &= (pf > 0)
    def tone_match(im):
        p = cv2.cvtColor((im[..., :3] * 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
        r = cv2.cvtColor((plate[..., :3] * 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
        m = band & (im[..., 3] > 0.9) & (plate[..., 3] > 0.9)
        if m.sum() < 50:
            return im
        for c in range(3):
            p[..., c] += r[..., c][m].mean() - p[..., c][m].mean()      # shift only: keeps contrast
        o = im.copy(); o[..., :3] = cv2.cvtColor(np.clip(p, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR) / 255.0
        return o
    # tone_match darkened faces and tinted teeth blue (2026-10-26 audit): kept for reference, OFF
    #
    # Mouth shapes are chosen by EYE, per character, with debug_mouth_zoom.png: an automatic
    # edge-disagreement score could not separate clean drawings from ghosting ones (all cells
    # differ from the plate by AI texture noise). Bad shapes go into the scene's --remap.
    for name, im in zip(MOUTHS, m_al):
        p = im[y0:y0 + h0, x0:x0 + w0].copy()
        p[..., 3] *= mmask[y0:y0 + h0, x0:x0 + w0]
        save(out / f"mouth_{name}.png", p)
    for name, im in zip(EYES, e_al):
        save(out / f"eyes_{name}.png", feather_patch(color_match(im, ref), ebox, feather))
    (out / "rig.json").write_text(json.dumps(rig, indent=1))

    # debug: poses WITH the rest mouth and open eyes on (pose layers alone have no lower face)
    def over(base_im, patch, box):
        o = base_im.copy(); x, y, w, h = box
        pa = patch[..., 3:4]; ba = o[y:y + h, x:x + w, 3:4]
        rgb = patch[..., :3] * pa + o[y:y + h, x:x + w, :3] * ba * (1 - pa)
        al = pa + ba * (1 - pa)
        o[y:y + h, x:x + w, :3] = rgb / np.maximum(al, 1e-6); o[y:y + h, x:x + w, 3:4] = al
        return o
    mX = cv2.imread(str(out / "mouth_X.png"), cv2.IMREAD_UNCHANGED) / 255.0
    eO = cv2.imread(str(out / "eyes_open.png"), cv2.IMREAD_UNCHANGED) / 255.0
    full = [over(over(l, mX, mbox), eO, ebox) for l in pose_layers]
    sheet(full, out / "debug_poses.png", 0.25)
    ref = full[0]

    def comp(base_im, patch, box):
        o = base_im.copy(); x, y, w, h = box
        a_ = patch[..., 3:4]
        o[y:y + h, x:x + w, :3] = patch[..., :3] * a_ + o[y:y + h, x:x + w, :3] * (1 - a_)
        return o[max(0, y - h):y + 2 * h, max(0, x - w // 2):x + w + w // 2]

    mp = [cv2.imread(str(out / f"mouth_{n}.png"), cv2.IMREAD_UNCHANGED) / 255.0 for n in MOUTHS]
    ep = [cv2.imread(str(out / f"eyes_{n}.png"), cv2.IMREAD_UNCHANGED) / 255.0 for n in EYES]
    sheet([comp(ref, p, mbox) for p in mp], out / "debug_mouths.png", 1.0)
    zx0, zx1 = int(pfx - 0.05 * pfw), int(pfx + 1.05 * pfw)
    zy0, zy1 = int(lf0 - 0.15 * pfh), int(neck + 0.05 * pfh)
    zooms = []
    for nm, p_ in zip(MOUTHS, mp):
        o = over(ref, p_, mbox)[zy0:zy1, zx0:zx1]
        bg = np.full(o.shape[:2] + (3,), 0.5)
        c = o[..., :3] * o[..., 3:4] + bg * (1 - o[..., 3:4])
        t = cv2.resize((c * 255).astype(np.uint8), None, fx=1.6, fy=1.6)
        cv2.putText(t, nm, (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 0, 255), 3)
        zooms.append(t)
    rows_ = [np.hstack(zooms[i:i + 3]) for i in (0, 3, 6)]
    cv2.imwrite(str(out / "debug_mouth_zoom.png"), np.vstack(rows_))
    sheet([comp(ref, p, ebox) for p in ep], out / "debug_eyes.png", 1.0)
    print(json.dumps({"ok": True, **rig}))


if __name__ == "__main__":
    sys.exit(main())
