"""Close the hairline cracks in a cut-out face layer (BGRA float 0..1).

The one-drawing face had 1-2 px transparent cracks along the outer rim of the ears and the
hair edge (cut-out artifacts). Over any background they read as a thin double outline -
the "ear problem" seen in both the hybrid and the poses routes. A morphological close finds
pixels that are transparent but enclosed by opaque ones within a few px; their colour is
inpainted from the neighbours and their alpha is set to the closed value. The outer
silhouette is unchanged (closing never grows past convex-ish gaps wider than the kernel).
"""
import cv2
import numpy as np


def erase_slivers(rgba, rows, cols_frac=0.22, k=5):
    """Erase thin stray bits (<= ~k-1 px wide) along the silhouette in the ear bands only
    (outer cols_frac of the width, rows=(y0, y1)): the jaw-line cut left the ear-lobe outline
    poking out past the skin. The face itself and the hair top are untouched."""
    out = rgba.copy(); H, W = rgba.shape[:2]
    a8 = (rgba[..., 3] * 255).astype(np.uint8)
    op = cv2.morphologyEx(a8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    band = np.zeros((H, W), bool); y0, y1 = rows
    cw = int(W * cols_frac); band[y0:y1, :cw] = True; band[y0:y1, W - cw:] = True
    out[..., 3] = np.where(band, np.minimum(rgba[..., 3], op.astype(np.float32) / 255), rgba[..., 3])
    return out


def restore_lobes(rgba, lobes):
    """The face's jaw-polyline cut sliced each ear lobe flat. The colour data under the cut
    still holds the whole lobe, so restore alpha inside hand-measured lobe outlines
    (face_landmarks.json "lobes", per avatar, like the jaw). Automatic flood-filling leaked
    through gaps in the drawn outline into junk below the lobes."""
    if not lobes:
        return rgba
    out = rgba.copy(); H, W = rgba.shape[:2]
    m = np.zeros((H * 4, W * 4), np.uint8)              # 4x supersampled polygon = smooth edge
    for poly in lobes:
        cv2.fillPoly(m, [np.round(np.array(poly, np.float32) * 4).astype(np.int32)], 255)
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    paint = (np.clip(rgba[..., :3], 0, 1).max(2) > 0.02).astype(np.float32)
    out[..., 3] = np.maximum(rgba[..., 3], m * paint)
    # close pinholes inside the lobes
    a8 = (out[..., 3] * 255).astype(np.uint8)
    cl = cv2.morphologyEx(a8, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(np.float32) / 255
    region = cv2.dilate((m > 0.05).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    out[..., 3] = np.where(region, np.maximum(out[..., 3], cl), out[..., 3])
    # the restored edge had no drawn line (the ear's fold just stopped there): outline it in the
    # ear's own outline colour (darkest 10% of the ear rim pixels just above the lobes)
    solid = (out[..., 3] > 0.5).astype(np.uint8)
    rim = (solid - cv2.erode(solid, np.ones((3, 3), np.uint8))).astype(bool)
    new_edge = rim & (m > 0.05) & (rgba[..., 3] < 0.5)
    ys0 = int(min(p[1] for poly in lobes for p in poly))
    ear_rim = rim.copy(); ear_rim[ys0:] = False; ear_rim[:max(0, ys0 - 40)] = False
    rv = np.clip(rgba[..., :3], 0, 1)[ear_rim & (rgba[..., 3] > 0.5)]
    if len(rv):
        line = rv[np.argsort(rv.sum(1))[:max(1, len(rv) // 10)]].mean(0)
        out[new_edge, :3] = line; out[new_edge, 3] = 1.0
    return out


def heal(rgba, k=5):
    a = rgba[..., 3]
    a8 = (a * 255).astype(np.uint8)
    closed = cv2.morphologyEx(a8, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    crack = (closed.astype(np.int16) - a8) > 8
    if not crack.any():
        return rgba
    out = rgba.copy()
    bgr8 = (np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8)
    fill = cv2.inpaint(bgr8, crack.astype(np.uint8), 3, cv2.INPAINT_TELEA).astype(np.float32) / 255
    out[..., :3] = np.where(crack[..., None], fill, rgba[..., :3])
    out[..., 3] = np.maximum(a, closed.astype(np.float32) / 255 * crack)
    return out


def trim_below_jaw(rgba, y0, dark=25, keep_px=1):
    """Erase the lower-face layer's skin hanging BELOW its drawn jaw outline (a flap of neck
    left by the cut-out at both jaw corners; it showed as an orange ledge over the collar).
    Per column, from row y0 down, the lowest dark outline/beard pixel is the jaw edge; opaque
    pixels more than keep_px below it are removed. Columns with no dark pixel below y0 are
    cleared from y0 + 40 down (pure flap)."""
    out = rgba.copy(); H, W = rgba.shape[:2]
    v = np.clip(rgba[..., :3], 0, 1).max(2) * 255
    a = out[..., 3]
    dk = (v < dark) & (a > 0.5)
    for x in range(W):
        col = np.nonzero(dk[y0:, x])[0]
        if len(col):
            cut = y0 + col.max() + 1 + keep_px
        else:
            if not (a[y0:, x] > 0.5).any():
                continue
            cut = y0 + 40
        a[cut:, x] = 0
    # stray one-column drips below the line: an opening removes slivers < 3 px wide
    op = cv2.morphologyEx((a * 255).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(np.float32) / 255
    a[y0:] = np.minimum(a[y0:], op[y0:])
    out[..., 3] = a
    return out


def ears_from_source(rgba, src, jaw, rows=(300, 528), feather=2):
    """Replace both ear regions with the ears of the ORIGINAL head drawing (src: BGRA float,
    already warped onto the face canvas). The cut-out face layers had their ears sliced flat
    and squared off; ears never animate, so one clean source serves every mouth/eye state.
    Region: rows[0]..rows[1], outside the cheek/jaw line (the jaw polyline, held vertical
    above its first point)."""
    out = rgba.copy(); H, W = rgba.shape[:2]
    jaw = np.asarray(jaw, np.float32)
    left = jaw[jaw[:, 0] < W / 2]; right = jaw[jaw[:, 0] > W / 2]
    left = left[np.argsort(left[:, 1])]; right = right[np.argsort(right[:, 1])]
    ys = np.arange(H, dtype=np.float32)
    xl = np.interp(ys, left[:, 1], left[:, 0], left=left[0, 0], right=left[-1, 0])
    xr = np.interp(ys, right[:, 1], right[:, 0], left=right[0, 0], right=right[-1, 0])
    xx = np.arange(W, dtype=np.float32)[None, :]
    # soft mask: 1 outside the cheek line, ramping over `feather` px
    ml = np.clip((xl[:, None] - xx) / feather + 0.5, 0, 1)
    mr = np.clip((xx - xr[:, None]) / feather + 0.5, 0, 1)
    m = np.maximum(ml, mr)
    rr = np.zeros((H, 1), np.float32); y0, y1 = rows
    rr[y0:y1] = 1; rr[max(0, y0 - feather):y0] = np.linspace(0, 1, min(feather, y0))[:, None]
    m = m * rr
    a = rgba[..., 3:4]; sa = src[..., 3:4]; mm = m[..., None]
    # straight-alpha blend: colour where either has paint, alpha mixed
    out[..., 3:4] = sa * mm + a * (1 - mm)
    # on the seam (the face layer's own jaw cut is semi-transparent exactly there) take the more
    # opaque of the two, so no background hairline shows between ear and cheek
    seam = cv2.dilate(((m > 0.01) & (m < 0.99)).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & (rr[:, 0][:, None] > 0)
    out[..., 3] = np.where(seam, np.maximum(a[..., 0], sa[..., 0]), out[..., 3])
    w_src = sa * np.where(seam[..., None], np.maximum(mm, 0.5), mm); w_dst = a * (1 - mm); tot = np.maximum(w_src + w_dst, 1e-6)
    out[..., :3] = (src[..., :3] * w_src + rgba[..., :3] * w_dst) / tot
    return out


def load_ear_source(landmarks_path, face_shape):
    """face_landmarks.json "ear_src": {"file": "head_hi.png", "M": 2x3 affine onto the face
    canvas}. Returns the warped, keyed BGRA float source, or None."""
    import json, pathlib
    import puppet_build as pb
    LM = json.loads(pathlib.Path(landmarks_path).read_text())
    es = LM.get("ear_src")
    if not es:
        return None
    im = cv2.imread(str(pathlib.Path(landmarks_path).parent / es["file"]))
    return cv2.warpAffine(pb.key_green(im), np.array(es["M"], np.float32), (face_shape[1], face_shape[0]),
                          flags=cv2.INTER_AREA).clip(0, 1)
