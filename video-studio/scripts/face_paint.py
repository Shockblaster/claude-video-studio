"""Painted parts for face_rig.py: mouth interior and eyelids, supersampled (4x) so every
edge is smooth, shaped to the drawing (lens-shaped mouth opening along the real lip line,
almond eyelids with per-column skin tone and a moving lash line), plus a rigid brow shift."""
import cv2
import numpy as np

SS = 4

# jaw drop (fraction of mouth width), pucker (width scale), teeth, tongue
VISEME = {
    "X": (0.00, 1.00, 0, 0), "A": (0.00, 0.97, 0, 0), "B": (0.10, 1.03, 1, 0),
    "C": (0.20, 1.02, 1, 0), "D": (0.34, 1.00, 1, 1), "E": (0.22, 0.84, 1, 0),
    "F": (0.09, 0.72, 0, 0), "G": (0.07, 1.00, 1, 0), "H": (0.20, 0.98, 1, 1),
}
EYES = {"open": (0.0, 0.0), "half": (0.55, 0.0), "closed": (1.0, 0.0),
        "surprise": (0.0, -1.0), "think": (0.0, 0.6)}   # (lid fraction, brow move: -up / +down)


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def remap(img, mx, my):
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)).clip(0, 1)


def _ss_grid(x0, y0, w, h):
    ys, xs = np.mgrid[0:h * SS, 0:w * SS].astype(np.float32)
    return xs / SS + x0 + 0.5 / SS, ys / SS + y0 + 0.5 / SS


def _down(img, w, h):
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)


def lip_line(head, L):
    """Per-column lip line (darkest pixel between the lips), smoothed."""
    mx, my, mw, mh = L["mouth"]
    xs = np.arange(mx, mx + mw)
    if L.get("lip_line"):
        # hand/landmark-measured curve [[x, y], ...] corner to corner: a smiling mouth curves far
        # more than the +-6 px search below allows (it notched the corners on a smiling presenter)
        P = np.array(sorted(L["lip_line"]), np.float32)
        return xs.astype(np.float32), np.interp(xs, P[:, 0], P[:, 1]).astype(np.float32)
    v = cv2.cvtColor((np.clip(head[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    ly = L["lip_y"]
    ys = []
    for x in xs:
        c0, c1 = max(my, ly - 6), min(my + mh, ly + 7)
        ys.append(c0 + int(np.argmin(v[c0:c1, x])))
    ys = np.convolve(np.array(ys, np.float32), np.ones(9) / 9, mode="same")
    ys[:4] = ys[4]
    ys[-4:] = ys[-5]
    return xs.astype(np.float32), ys


def lower_state(head, L, shape, split):
    H, W = head.shape[:2]
    drop, pucker, teeth, tongue = VISEME[shape]
    mx, my, mw, mh = L["mouth"]
    cx = mx + mw / 2.0
    ly = L["lip_y"]
    d = drop * mw
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    jaw_half = 0.95 * L["eye_span"] / 2
    wx = smoothstep(1 - np.abs(xx - cx) / jaw_half)
    chin = L["bottom"]
    lxs, lys = lip_line(head, L)
    k = pucker
    pz = smoothstep(1 - np.abs(xx - cx) / (0.9 * mw)) * smoothstep((yy - split) / (ly - split + 1)) \
        * (1 - smoothstep((yy - (ly + 0.9 * mh)) / (0.8 * mh + 1)))
    src_x = xx + (xx - cx) * (1 / k - 1) * pz
    # the lip line where it appears in THIS state: a pucker moves the corners in, so look the line up at
    # the source x (unsqueezed). Using the dest x tilted the opening on a smiling, tilted mouth ("F slid")
    line_full = np.interp(src_x, np.arange(W, dtype=np.float32),
                          np.interp(np.arange(W, dtype=np.float32), lxs, lys, left=ly, right=ly))
    wy = smoothstep((yy - line_full) / 2.0) * \
        (1 - smoothstep((yy - (chin - 0.10 * (chin - ly))) / (0.35 * (chin - ly) + 1)))
    # LIP SEAL (fix 2026-10-29, user: "lower lip being separated from upper lip"): the lips must meet
    # at the corners in every open shape. The old drop used only the jaw falloff wx (based on the eye
    # span, wider than the mouth), so the lower lip still dropped ~25% at the corners while the painted
    # opening below closed to a point there: the stretched lip line showed as a dark wedge and the lips
    # looked detached. Now, at the lip line, the drop follows the SAME lens profile as the opening (zero
    # at the corners); deeper toward the chin it blends back to the jaw falloff so the jaw still moves.
    half_w = 0.5 * mw * k * 0.94
    prof_x = np.clip(1 - ((xx - cx) / half_w) ** 2, 0, 1) ** 0.85
    b = smoothstep((yy - line_full) / (0.9 * mh + 1))                  # 0 at the lip line, 1 by the chin
    src_y = yy - d * wy * (prof_x * (1 - b) + wx * b)
    out = remap(head, src_x, src_y)
    if d > 0.5:
        x0, x1 = int(cx - half_w) - 2, int(cx + half_w) + 3
        # the box must reach the HIGHEST point of the lip line: on a smiling mouth the corners sit well
        # above lip_y, and a box starting at lip_y - 8 clipped the opening flat there, leaving a strip of
        # skin between the upper lip and the opening (the user's "lower lip separated", 2026-10-29)
        y0, y1 = int(min(lys.min(), ly) - 8), int(max(lys.max(), ly) + d + 10)
        w, h = x1 - x0, y1 - y0
        X, Y = _ss_grid(x0, y0, w, h)
        u = (X - cx) / half_w
        prof = np.clip(1 - u ** 2, 0, 1) ** 0.85                         # lens: pointed corners
        top = np.interp(cx + (X - cx) / k, lxs, lys, left=ly, right=ly)  # the real lip line, at source x
        bot = top + d * prof                                            # the moved lower lip
        inside = (Y >= top) & (Y <= bot) & (prof > 0.005)
        t = np.clip((Y - top) / np.maximum(d * prof, 1e-3), 0, 1)
        c_top = np.array([0.16, 0.13, 0.36])
        c_deep = np.array([0.07, 0.05, 0.17])                           # BGR dark reds
        col = c_top * (1 - t[..., None]) + c_deep * t[..., None]
        col = col * (0.65 + 0.35 * prof[..., None])                     # darker toward corners
        if teeth:
            th = np.clip(0.24 * d, 1.2, 9.0) * np.sqrt(prof)
            tm = (Y - top) < th
            tooth = np.array([0.90, 0.92, 0.95]) * (0.78 + 0.22 * np.sqrt(prof[..., None]))
            tooth = tooth * (1 - 0.12 * np.clip((Y - top) / np.maximum(th, 1e-3), 0, 1))[..., None]
            col = np.where(tm[..., None], tooth, col)
        if tongue:
            tcy = top + 0.86 * d * prof
            rr = ((X - cx) / (0.62 * half_w)) ** 2 + ((Y - tcy) / (0.42 * d + 1)) ** 2
            tw = np.clip(1.25 - rr, 0, 1) ** 0.7
            col = col * (1 - tw[..., None]) + np.array([0.40, 0.40, 0.78]) * tw[..., None]
        m = inside.astype(np.float32)
        m_d = _down(m, w, h)
        col_d = _down((col * m[..., None]).astype(np.float32), w, h) / np.maximum(m_d[..., None], 1e-3)
        reg = out[y0:y1, x0:x1]
        reg[..., :3] = reg[..., :3] * (1 - m_d[..., None]) + col_d * m_d[..., None]
        reg[..., 3] = np.maximum(reg[..., 3], m_d)
    return out


def lip_seal_check(head, L, shape, split, im):
    """Gate for the 2026-10-29 bug: is any SKIN showing inside the mouth opening? Rebuilds the lens
    (top = lip line, bottom = moved lower lip) exactly as lower_state draws it and counts skin-coloured
    pixels inside it, 1 px in from its edges. A gap between the lips (the user's "lower lip separated
    from upper lip") shows up as skin here. Returns the skin fraction (0 = sealed); fail above 0.01."""
    drop, k = VISEME[shape][0], VISEME[shape][1]
    mx, my, mw, mh = L["mouth"]
    cx, ly = mx + mw / 2.0, L["lip_y"]
    d = drop * mw
    if d <= 0.5:
        return 0.0
    lxs, lys = lip_line(head, L)
    half_w = 0.5 * mw * k * 0.94
    yy, xx = np.mgrid[0:im.shape[0], 0:im.shape[1]].astype(np.float32)
    u = (xx - cx) / half_w
    prof = np.clip(1 - u ** 2, 0, 1) ** 0.85
    top = np.interp(cx + (xx - cx) / k, lxs, lys, left=ly, right=ly)
    inside = (yy >= top + 1) & (yy <= top + d * prof - 1) & (prof > 0.05)
    if inside.sum() == 0:
        return 0.0
    b, g, r = im[..., 0], im[..., 1], im[..., 2]
    skin = (r > 0.62) & (g > 0.42) & (b > 0.30) & (r - b > 0.18)       # warm light skin, not teeth (grey-white)
    return round(float((skin & inside).sum() / inside.sum()), 4)


def brow_layer_move(head, L, state):
    """Brows as their own layer. Cartoon brows often sit right on a glasses frame with no
    skin to stretch, so a warp bends the frame. Lift the brow pixels off, refill the band with
    forehead skin (reflected from just above), and paste the brows back moved:
    surprise = up with a slight arch, think = inner ends up (thoughtful)."""
    H, W = head.shape[:2]
    out = head.copy()
    g = cv2.cvtColor((np.clip(head[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    bt = int(L.get("brow_top", L["brow_y"] - 9))
    bb = int(L.get("brow_bottom", L["brow_y"] + 9))
    ex0 = int(L["eyes"][0][0] - 0.30 * L["eyes"][0][2])
    ex1 = int(L["eyes"][1][0] + 1.30 * L["eyes"][1][2])
    fill_top = bt - 6
    mask = np.zeros((H, W), np.float32)
    clean = out.copy()
    for x in range(max(0, ex0), min(W, ex1)):
        # frame top: first row at/after (bb - 4) that starts a dark run of >= 4 px
        ft = bb + 6
        for y in range(bb - 4, min(H - 4, bb + 14)):
            if (g[y:y + 4, x] < 40).all():
                ft = y
                break
        for y in range(fill_top, ft - 1):
            mask[y, x] = np.clip((150 - g[y, x]) / 90, 0, 1)
            ry = 2 * (fill_top - 1) - y                                   # reflect forehead skin
            clean[y, x] = head[max(0, ry), x]
    m = cv2.GaussianBlur(mask, (0, 0), 0.7)
    m3 = m[..., None]
    base = out * (1 - m3) + clean * m3                                     # brows removed
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    span = (ex1 - ex0) / 2.0
    cx = (ex0 + ex1) / 2.0
    h = L["eye_bottom"] - L["eye_top"]
    if state == "surprise":
        dy = -0.22 * h - 0.06 * h * (1 - ((xx - cx) / span) ** 2).clip(0, 1)
    else:   # think: inner ends up
        inner = 1 - np.abs(xx - cx) / (0.5 * span)
        dy = -0.14 * h * np.clip(inner, 0, 1)
    brow_rgba = np.dstack([head[..., :3], m])
    moved = remap(brow_rgba, xx, yy - dy)
    a = moved[..., 3:4]
    res = base.copy()
    res[..., :3] = moved[..., :3] * a + base[..., :3] * (1 - a)
    return res


def lid_warp(head, L, lid):
    """Blink by sliding the drawing's OWN upper lid down (no painted patch): per column, the band
    from the crease down to the bottom of the drawn liner is stretched downward by s, so the liner
    travels with the lid and the stretched lid skin keeps the artist's shading. Below the moved
    liner the eye shows unchanged (the liner hides the cut). At lid=1 the liner meets the lower lid.
    Supersampled (SS x) so the lid edge is anti-aliased.
    Per-avatar keys: lid_mode "warp", lid_crease (crease height above the eye top, in eye heights,
    default 0.55), lid_liner (band end below the eye top, in eye heights; 0 or slightly negative
    when the eye box follows the opening), lid_reach (lower lid, in half eye heights), lid_wide."""
    out = head.copy()
    for (x, y, w, h) in L["eyes"]:
        cxe, cye = x + w / 2.0, y + h / 2.0
        rx, ry = w / 2.0 * float(L.get("lid_wide", 1.0)), h / 2.0
        reach = float(L.get("lid_reach", 0.92))
        c = float(L.get("lid_crease", 0.55)) * h
        lt = float(L.get("lid_liner", 0.16)) * h
        x0, x1 = int(cxe - rx) - 2, int(cxe + rx) + 3
        y0, y1 = int(cye - ry - c) - 2, int(cye + ry * reach) + 4
        X, Y = _ss_grid(x0, y0, x1 - x0, y1 - y0)
        u = np.clip((X - cxe) / rx, -1, 1)
        inside = np.abs(X - cxe) <= rx
        yT = cye - ry * (1 - u ** 2) ** 0.6
        yB = cye + ry * reach * (1 - u ** 2) ** 0.8
        s = lid * np.maximum(0.0, yB - yT - lt) * inside
        a, b = yT - c, yT + lt
        b2 = b + s
        band = (Y >= a) & (Y <= b2) & (s > 0.05)
        src_y = np.where(band, a + (Y - a) * (b - a) / np.maximum(b2 - a, 1e-3), Y)
        reg = remap(head, X, src_y)
        out[y0:y1, x0:x1] = _down(reg, x1 - x0, y1 - y0)
    return out


def upper_state(head, L, state, split):
    H, W = head.shape[:2]
    lid, brow = EYES[state]
    out = head.copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if brow and not L.get("no_brows"):
        out = brow_layer_move(out, L, state)
    if lid > 0 and L.get("lid_mode") == "warp":
        return lid_warp(out, L, lid)
    if lid > 0:
        for (x, y, w, h) in L["eyes"]:
            pad = 6
            x0, y0 = x - pad, y - pad
            ww, hh = w + 2 * pad, h + 2 * pad
            X, Y = _ss_grid(x0, y0, ww, hh)
            cxe, cye = x + w / 2.0, y + h / 2.0
            rx, ry = w / 2.0, h / 2.0
            u = np.clip((X - cxe) / rx, -1, 1)
            yT = cye - ry * (1 - u ** 2) ** 0.6                   # upper lid line (almond)
            yB = cye + ry * 0.92 * (1 - u ** 2) ** 0.8            # lower lid line
            within = np.abs(X - cxe) <= rx
            yL = yT + lid * (yB - yT)                              # the moving lid edge
            if L.get("lid_arch"):
                # keep the upper-lid arch while it comes down (a straight bar read as fake)
                yL = np.minimum(yT + lid * (2 * ry * 0.96), yB)
            # per-avatar: a thick drawn upper liner must be covered too, or the closed eye shows
            # the old lash line above the lid (a long-lashed presenter); the lash then matches the liner weight
            extra = float(L.get("lid_cover_px", 3.0))
            lash_t = float(L.get("lash_px", 1.6 + 1.2 * lid)) * (0.6 + 0.4 * lid)
            cover = within & (Y >= yT - extra) & (Y <= yL)
            reg = out[y0:y0 + hh, x0:x0 + ww]
            # skin tone: the light skin just BELOW the eye (inside the lens); the area above
            # the eye has a crease shadow and gave a brown lid
            sk = []
            for c in range(ww):
                colm = reg[min(hh - 1, pad + h + 1):min(hh, pad + h + 5), c, :3]
                sk.append(np.median(colm.reshape(-1, 3), 0) if colm.size else np.array([0.5, 0.6, 0.8]))
            sk = np.array(sk, np.float32)
            if L.get("lid_skin") == "flat":
                # one robust tone per eye: per-column samples caught lower lashes -> stripes
                band = reg[min(hh - 1, pad + h + 2):min(hh, pad + h + 12), int(0.2 * ww):int(0.8 * ww), :3].reshape(-1, 3)
                lum = band.mean(1); band = band[lum > np.percentile(lum, 40)]
                sk = np.repeat(np.median(band, 0)[None, :], ww, 0).astype(np.float32)
            sk = cv2.GaussianBlur(sk.reshape(1, -1, 3), (0, 0), 5).reshape(-1, 3)
            skin_ss = np.repeat(np.repeat(sk[None, :, :], hh * SS, 0), SS, 1)
            shade = 1 - 0.10 * np.clip((Y - (yT - 3)) / np.maximum(yL - yT + 3, 1), 0, 1)
            col = skin_ss * shade[..., None]
            lash = within & (np.abs(Y - yL) <= lash_t / 2) & (lid > 0.05)
            col = np.where(lash[..., None], np.array([0.09, 0.08, 0.09]), col)
            soft = np.clip((Y - (yT - extra)) / max(1.0, float(L.get("lid_soft_px", 0.0))), 0, 1) \
                if L.get("lid_soft_px") else 1.0                          # feathered lid top edge
            m = np.maximum(cover * soft, lash).astype(np.float32)
            m_d = _down(m, ww, hh)
            col_d = _down((col * m[..., None]).astype(np.float32), ww, hh) / np.maximum(m_d[..., None], 1e-3)
            reg[..., :3] = reg[..., :3] * (1 - m_d[..., None]) + col_d * m_d[..., None]
    return out
