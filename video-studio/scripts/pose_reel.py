#!/usr/bin/env python3
"""POSES ROUTE renderer: a library of full-body pose drawings (ChatGPT, green screen, each one
passed by pose_fit.py) with our one-drawing face rig on top, lip-synced and blinking.
The body never animates between poses: a pose change happens ONLY on a jump cut that also
changes the framing (wide <-> close), so it reads as an edit, never as a body teleporting.
Inside a shot: a slow push-in and breathing keep it alive; the face talks all the time.

  python -I pose_reel.py --poses raw/ --face face --landmarks face_landmarks.json \
      --plan plan.json --transcript transcript.json --mouth mouth.json --voice vo.wav --out reel.mp4

plan.json: [{"at": 0, "pose": "p01_rest_clasp", "frame": "wide"},
            {"at": "wrong", "pose": "p02_point_up_right", "frame": "close"}, ...]
  "at": seconds, or a word (the cut lands --lead seconds before it; words searched in order).
  "frame": wide | close (consecutive shots should alternate; the script warns if not).
The head layer carries the top of the collar, so it never moves relative to the body: no
separate head nods (they would open a seam at the collar).
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
import pose_fit as pf  # noqa: E402
from face_heal import heal, trim_below_jaw, ears_from_source, load_ear_source  # noqa: E402

FRAMES = {   # eye distance and eye-midpoint position on a 1080x1920 canvas
    "wide":  {"d": 138.0, "mid": (540.0, 520.0)},
    "close": {"d": 178.0, "mid": (540.0, 560.0)},
}


def erase_pose_head(rgba, m, mid, hX, skin_bgr=np.array([0.40, 0.56, 0.84]), fill_neck=False, keep_neck=False, out_neck=None):
    """Remove the pose drawing's OWN head (the static lower layer) so only our animated head
    shows: no ear, hair, jaw or beard of the drawing can peek out. Clothing and hands stay
    whole. Between our jaw and the collar a neck is painted (these poses have none visible:
    their jaw sits on the collar, and our jaw is a little narrower), so nothing shows through."""
    H, W = rgba.shape[:2]; d = m["d"]
    out = rgba.copy()
    bgr8 = (np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(bgr8, cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    opaque = rgba[..., 3] > 0.5
    rows = np.arange(H)[:, None]; cols = np.arange(W)[None, :]
    hb = hX > 0.5
    our_chin = int(np.nonzero(hb)[0].max())
    jaw_y = our_chin - int(0.55 * d)                       # roughly the jaw corners
    shirt = (hh > 95) & (hh < 118) & (vv > 150) & opaque
    tie = (hh > 100) & (hh < 130) & (ss > 90) & (vv < 150) & opaque & (rows > jaw_y)
    face = np.zeros((H, W), np.uint8); cv2.fillPoly(face, [m["oval"].astype(np.int32)], 1)
    face = cv2.dilate(face, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.12 * d) | 1,) * 2)).astype(bool)
    suit = (ss < 45) & (vv > 40) & (vv < 130) & opaque & (rows > jaw_y) & ~face   # hair, glasses, beard excluded
    cloth = shirt | tie | suit
    shirt_top = collar_top(bgr8, mid, d)
    zone = (rows < shirt_top + int(0.15 * d)) & (np.abs(cols - mid[0]) < 2.1 * d)
    hands = np.zeros((H, W), bool)
    hp = np.array(m["hands"]).reshape(-1, 2)
    for hand in (np.split(hp, len(hp) // 21) if len(hp) >= 21 else []):
        lo, hi = hand.min(0), hand.max(0); pad = 0.3 * (hi - lo).max() + 6
        hands[int(max(0, lo[1] - pad)):int(hi[1] + pad), int(max(0, lo[0] - pad)):int(hi[0] + pad)] = True
    # clothing keeps its own drawn outlines (dark pixels hugging the collar and lapels)
    near = cv2.dilate(cloth.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
    skinlike = (hh < 25) & (ss > 70) & (vv > 50)
    outline = near & (vv < 110) & ~skinlike & opaque & (rows > jaw_y)
    keep = ~zone | hands | cloth | outline
    out_neck = out_neck if out_neck is not None else [None]
    if keep_neck:
        # the pose's OWN neck (between its chin and the collar) stays: it already meets the collar in
        # the same line style. Only skin and its near-black side outlines below our chin are kept,
        # so no beard or jaw of the drawing can show.
        # below our chin across the collar, and up behind our tapering jaw inside the neck's own
        # width (else a flat-topped neck left background wedges under the jaw corners)
        pose_chin = float(m["oval"][18][1])
        below = (rows > our_chin - int(0.04 * d)) | ((rows > pose_chin - 0.45 * d) & (np.abs(cols - mid[0]) < 0.6 * d))
        col_band = np.abs(cols - mid[0]) < 0.95 * d
        neck_skin = (hh < 28) & (ss > 40) & (vv > 95) & opaque & below & col_band & ~(hX > 0.5)
        near_neck = cv2.dilate(neck_skin.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        neck_line = near_neck & (vv < 60) & opaque & below & col_band & (np.abs(cols - mid[0]) > 0.25 * d)
        keep |= neck_skin | neck_line
    old_skin = (hh < 28) & (ss > 45) & (vv > 120) & opaque & zone & (rows > our_chin - int(0.2 * d))
    out[..., 3] = np.where(keep, out[..., 3], 0.0)
    if keep_neck:
        out_neck[0] = neck_skin & (out[..., 3] > 0.5)
    # NECK: the hull of our jaw (below the jaw corners) and the collar band; whatever in it is
    # not clothing and not under our head becomes neck skin (old jaw/beard bits are painted over)
    pts = [np.argwhere(hb & (rows > jaw_y))[:, ::-1]]
    sb = np.argwhere(shirt & (rows > jaw_y) & (rows < shirt_top + int(0.10 * d)) & (np.abs(cols - mid[0]) < 1.3 * d))[:, ::-1]
    if len(sb):
        pts.append(sb)
    hull = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(hull, cv2.convexHull(np.vstack(pts).astype(np.int32)), 1)
    neck = hull.astype(bool) & ~(hX > 0.98) & ~shirt & ~tie & ~suit & zone
    neck = cv2.morphologyEx(neck.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    if fill_neck and neck.any():
        # what was behind the drawing's (wider) jaw is the COLLAR BAND standing up behind the
        # neck: extend the band - every gap pixel takes the colour of its nearest shirt pixel
        src = (shirt & ~cv2.dilate((vv < 110).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)).astype(np.uint8)
        _, lab_ = cv2.distanceTransformWithLabels(1 - src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        sy, sx = np.nonzero(src); idx = np.zeros(len(sy) + 1, np.int64)
        lut_y = np.concatenate([[0], sy]); lut_x = np.concatenate([[0], sx])
        ny_, nx_ = np.nonzero(neck)
        L = lab_[ny_, nx_]
        out[ny_, nx_, :3] = out[lut_y[L], lut_x[L], :3]
        out[ny_, nx_, 3] = 1.0
        # outline where the neck meets the collar or empty space (never where it meets our head)
        nk = neck.astype(np.uint8)
        edge = neck & cv2.dilate((~neck & ~(hX > 0.3)).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        out[edge, :3] = np.array([0.12, 0.14, 0.22])
    return out


def collar_top(bgr8, mid, d):
    """Row of the shirt's V tip under the chin: the first row, searching from below the mouth,
    where the centre column is shirt-blue. (Searching from the eyes hit glasses or beard
    pixels and put the 'collar' at 0.6-1.6 eye distances on 9 of 20 poses.)"""
    hsv = cv2.cvtColor(bgr8, cv2.COLOR_BGR2HSV)
    sh = (hsv[..., 0] > 95) & (hsv[..., 0] < 118) & (hsv[..., 2] > 150) & (hsv[..., 1] > 12)
    xc = int(mid[0]); y0 = int(mid[1] + 1.3 * d)
    band = sh[y0:int(mid[1] + 3.2 * d), xc - 3:xc + 4].mean(1) > 0.5
    return y0 + int(np.argmax(band)) if band.any() else int(mid[1] + 2.05 * d)


def fill_enclosed_gaps(rgba, hX):
    """Any not-quite-opaque pixel of the body that is ENCLOSED by body + our (closed-mouth) head
    - not connected to the open background - is a seam (collar corner, tie knot, under the
    chin). Fill it opaque with colour inpainted from the body around it."""
    H, W = rgba.shape[:2]
    union = np.maximum(rgba[..., 3], hX)
    solid = (union > 0.95).astype(np.uint8)
    ff = solid.copy(); mask = np.zeros((H + 2, W + 2), np.uint8)
    for sx, sy in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1), (W // 2, 0)):
        if ff[sy, sx] == 0:
            cv2.floodFill(ff, mask, (sx, sy), 2)
    gap = (ff == 0) & (hX < 0.95)              # enclosed, and not under our head
    if not gap.any():
        return rgba
    out = rgba.copy()
    bgr8 = (np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8)
    src_bad = (gap | (rgba[..., 3] < 0.5)).astype(np.uint8)
    fill = cv2.inpaint(bgr8, src_bad, 3, cv2.INPAINT_TELEA).astype(np.float32) / 255
    out[gap, :3] = fill[gap]; out[gap, 3] = 1.0
    return out


def prepare_pose(im, det, upper, lower, sp, LM, dA, midA, head_scale=1.06, name="pose", neck=True):
    """Key a pose, seat our head on it, erase its own head; returns what the renderer needs.
    neck=True (default since 2026-10-27, user: "the mascot doesn't have any neck"): our chin is
    seated on the POSE's chin (MediaPipe landmark 152) and the pose's own neck is kept, instead of
    pushing our chin down onto the collar (the collar search reads the centre column, which the
    tie covers, so it fell back to 2.05 eye distances and buried the neck)."""
    rgba = pb.key_green(im, max_hole=600)
    m = pf.measure(im, det)
    if m is None:
        raise SystemExit(f"{name}: no face found")
    sh = m["d"] / dA * head_scale
    ang = math.atan2(m["eR"][1] - m["eL"][1], m["eR"][0] - m["eL"][0])
    Mh = np.array([[math.cos(ang) * sh, -math.sin(ang) * sh, 0], [math.sin(ang) * sh, math.cos(ang) * sh, 0]])
    mid = (m["eL"] + m["eR"]) / 2
    Mh[:, 2] = mid - Mh[:, :2] @ midA
    # ERASE THE POSE'S OWN HEAD (the user's rule: the static lower layer goes, never ours).
    # Every pose pixel in the head zone that is not clothing and not a hand is removed -
    # face, hair, ears, beard. Only its NECK skin is kept, rebuilt so it always meets our jaw.
    headX = np.vstack([upper["open"][:sp], lower["X"][sp:]])
    hX = cv2.warpAffine(headX[..., 3], Mh.astype(np.float32), (rgba.shape[1], rgba.shape[0]), flags=cv2.INTER_LINEAR)
    shirt_top = collar_top(im, mid, m["d"])
    target = (float(m["oval"][18][1]) + 0.06 * m["d"]) if neck else (shirt_top - 0.03 * m["d"])
    dy = target - np.nonzero(hX > 0.5)[0].max()
    Mh[1, 2] += dy; mid = mid + np.array([0.0, dy])
    hX = cv2.warpAffine(headX[..., 3], Mh.astype(np.float32), (rgba.shape[1], rgba.shape[0]), flags=cv2.INTER_LINEAR)
    # our own skin tone (cheeks, beside the mouth) for the painted neck
    mx_, my_, mw_, mh_ = LM["mouth"]           # cheek patch: left of the mouth, above the lip line
    lx = lower["X"]; ch = lx[int(LM["lip_y"]) - 45:int(LM["lip_y"]) - 15, int(mx_) - 60:int(mx_) - 15]
    skin = np.median(ch[ch[..., 3] > 0.9][:, :3], 0) * 0.92
    nbox = [None]
    rgba = erase_pose_head(rgba, m, (m["eL"] + m["eR"]) / 2, hX, skin, keep_neck=neck, out_neck=nbox)
    rgba = fill_enclosed_gaps(rgba, hX)
    if neck and nbox[0] is not None:
        # the kept neck's sides meet open background as a bare cut: give them the drawing's
        # outline (2 px near-black). Only where it meets the OUTER background (after the gap fill),
        # never clothing or our head
        Hh, Ww = rgba.shape[:2]
        solid = ((rgba[..., 3] > 0.5) | (hX > 0.3)).astype(np.uint8)
        ff = np.pad(solid, 1); msk = np.zeros((Hh + 4, Ww + 4), np.uint8); cv2.floodFill(ff, msk, (0, 0), 2)
        outer = ff[1:-1, 1:-1] == 2
        ring = nbox[0] & (rgba[..., 3] > 0.5) & cv2.dilate(outer.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        rgba[ring, :3] = np.array([0.12, 0.13, 0.18], np.float32); rgba[ring, 3] = 1.0
    # COLLAR OVER CHIN: the pose's clothing (shirt collar, tie, lapels) must sit ON TOP of
    # our head - otherwise our neck skin / beard edge covers the collar tips (first test,
    # 6 s). Clothing = pose pixels outside its own face oval, below the mouth, that are
    # shirt-blue, tie-navy or suit-grey (never skin or beard).
    Hh, Ww = rgba.shape[:2]
    oval = np.zeros((Hh, Ww), np.uint8); cv2.fillPoly(oval, [m["oval"].astype(np.int32)], 1)
    oval = cv2.dilate(oval, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.10 * m["d"]) | 1,) * 2))
    hsv = cv2.cvtColor((np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    rows_ = np.arange(Hh)[:, None]
    shirt = (hh > 95) & (hh < 118) & (vv > 150)
    tie = (hh > 100) & (hh < 130) & (ss > 90) & (vv < 150)
    suit = (ss < 45) & (vv > 20) & (vv < 130)
    cloth = (shirt | tie | (suit & (oval == 0))) & (rgba[..., 3] > 0.5)     # the pose face is erased: shirt/tie can't be skin
    # shirt and tie (unambiguous now the pose face is erased) are in front of the chin from just
    # below the jaw corners down; suit only lower (its colour overlaps hair and beard)
    chinX = int(np.nonzero(hX > 0.5)[0].max())
    cloth &= rows_ > chinX - int(0.6 * m["d"])
    cloth &= ~((suit & ~(shirt | tie)) & (rows_ < chinX))
    # in front ONLY of what the open mouth drops below the closed-mouth face: the resting face
    # stays fully in front of the collar (as drawn), the moving chin tucks behind it
    cloth &= ~(cv2.dilate((hX > 0.5).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool))
    cloth = cv2.morphologyEx(cloth.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    over = rgba.copy(); over[..., 3] = cv2.GaussianBlur(cloth.astype(np.float32), (3, 3), 0) * rgba[..., 3]
    return {"rgba": rgba, "over": over, "d": m["d"], "mid": mid, "Mh": Mh, "hands": np.array(m["hands"]).reshape(-1, 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("poses", "face", "landmarks", "plan", "transcript", "mouth", "voice", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--lead", type=float, default=0.10)
    ap.add_argument("--head-scale", type=float, default=1.06)
    ap.add_argument("--push", type=float, default=0.025, help="slow push-in per shot (fraction)")
    a = ap.parse_args()
    OW, OH = 1080, 1920
    fd = pathlib.Path(a.face)
    F = json.loads((fd / "face.json").read_text()); sp = F["split"]
    LM = json.loads(pathlib.Path(a.landmarks).read_text())
    eA = [np.array([x + w / 2, y + h / 2]) for x, y, w, h in LM["eyes"]]
    dA = float(np.linalg.norm(eA[1] - eA[0])); midA = (eA[0] + eA[1]) / 2
    ld = lambda n: heal(cv2.imread(str(fd / n), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0)
    ears = load_ear_source(a.landmarks, F["canvas"][::-1])      # ears from the original head drawing
    fix = (lambda im: ears_from_source(im, ears, LM["jaw"])) if ears is not None else (lambda im: im)
    upper = {e: fix(ld(f"upper_{e}.png")) for e in F["eyes"]}
    jaw_y0 = int(LM["lip_y"]) + 25            # trim only below the mouth
    lower = {m: trim_below_jaw(fix(ld(f"lower_{m}.png")), jaw_y0) for m in F["shapes"]}

    words = json.loads(pathlib.Path(a.transcript).read_text())
    plan = json.loads(pathlib.Path(a.plan).read_text())
    cursor = 0.0
    shots = []
    for s in plan:
        t = s["at"]
        if isinstance(t, str):
            hit = next((w for w in words if w["start"] >= cursor - 1e-6 and
                        w["text"].lower().strip(".,!?") == t.lower().strip(".,!?")), None)
            if hit is None:
                raise SystemExit(f"word not found after {cursor:.2f}s: {t}")
            t = max(0.0, hit["start"] - a.lead); cursor = hit["start"]
        shots.append({"t": float(t), "pose": s["pose"], "frame": s["frame"]})
    for p_, q_ in zip(shots, shots[1:]):
        if p_["frame"] == q_["frame"]:
            print(f"WARNING: cut at {q_['t']:.2f}s keeps the {q_['frame']} framing - a pose change without a framing change reads as a teleport")

    # poses: keyed body + where our head goes on it (pose px)
    det = pf.detectors()
    P = {}
    for name in sorted({s["pose"] for s in shots}):
        P[name] = prepare_pose(cv2.imread(str(pathlib.Path(a.poses) / f"{name}.png")), det, upper, lower, sp, LM, dA, midA, a.head_scale, name)

    # AUTO-FRAMING: a close shot that crops the gesture hand loses the whole point of the pose
    # (first test: the raised index finger was off the left edge). Each shot keeps its scale
    # if it can, slides sideways so every hand that is in frame (and the head) sits fully
    # inside a margin, and zooms out only if it still cannot fit. Elbows and shoulders may
    # crop at the sides like any close-up; fitting the whole body made every shot the same size.
    MARGIN = 48
    BOTTOM_D = (OH - FRAMES["wide"]["mid"][1]) / FRAMES["wide"]["d"]

    def frame_for(name, kind):
        p = P[name]; fr = FRAMES[kind]
        s = fr["d"] / p["d"]; cx = fr["mid"][0]
        for _ in range(3):
            y_top = fr["mid"][1] - s * p["mid"][1]
            ybot = (OH - y_top) / s                     # last pose row on screen
            pts = []
            for hand in np.split(p["hands"], max(1, len(p["hands"]) // 21)) if len(p["hands"]) else []:
                lo, hi = hand.min(0), hand.max(0); pad = 0.25 * (hi - lo).max()
                if hi[1] + pad < ybot:                  # hand fully in frame vertically: keep it whole
                    pts += [lo - pad, hi + pad]
            pts += [p["mid"] + np.array([-1.6, 0]) * p["d"], p["mid"] + np.array([1.6, 0]) * p["d"]]   # the head
            pts = np.array(pts)
            x0 = (pts[:, 0].min() - p["mid"][0]) * s; x1 = (pts[:, 0].max() - p["mid"][0]) * s   # relative to the eyes
            if x1 - x0 > OW - 2 * MARGIN:
                s *= (OW - 2 * MARGIN) / (x1 - x0)
                continue
            cx = min(max(fr["mid"][0], MARGIN - x0), OW - MARGIN - x1)
            break
        # a shot zoomed out to fit wide hands keeps the frame bottom at the same body point
        # (below the hips, ~BOTTOM_D eye-distances under the eyes): the figure moves down
        # instead of shrinking into a full-length shot with legs (first test, open palms)
        ed = s * p["d"]
        my = max(fr["mid"][1], OH - BOTTOM_D * ed)
        return {"s": s, "mid": (float(cx), float(my))}

    for s_ in shots:
        s_["fr"] = frame_for(s_["pose"], s_["frame"])
    for p_, q_ in zip(shots, shots[1:]):
        dz = max(p_["fr"]["s"] * P[p_["pose"]]["d"], q_["fr"]["s"] * P[q_["pose"]]["d"]) / \
            min(p_["fr"]["s"] * P[p_["pose"]]["d"], q_["fr"]["s"] * P[q_["pose"]]["d"])
        dx = abs(p_["fr"]["mid"][0] - q_["fr"]["mid"][0])
        if dz < 1.15 and dx < 120:
            print(f"WARNING: cut at {q_['t']:.2f}s changes framing too little (zoom x{dz:.2f}, shift {dx:.0f}px)")

    cues = json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"]
    vo_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice],
                                  capture_output=True, text=True).stdout.strip())
    n_out = int((vo_len + 0.6) * a.fps)
    rng = np.random.default_rng(7); blinks = []; t = 1.0
    while t < n_out / a.fps:
        blinks.append(t); t += 2.4 + rng.random() * 2.2
    # never blink on the frame of a cut (reads as a glitch)
    blinks = [b for b in blinks if all(abs(b - s["t"]) > 0.2 for s in shots)]

    def mouth_at(t):
        m = "X"
        for c in cues:
            if c["start"] <= t:
                m = c["value"]
        return m if t <= vo_len + 0.05 else "X"

    def eyes_at(t):
        for b in blinks:
            d = (t - b) * a.fps
            if 0 <= d < 1 or 3 <= d < 4: return "half"
            if 1 <= d < 3: return "closed"
        return "open"

    yy, xx = np.mgrid[0:OH, 0:OW]
    rr = np.sqrt(((xx - OW / 2) / (OW * 1.1)) ** 2 + ((yy - OH * 0.35) / (OH * 0.75)) ** 2)
    c0, c1 = np.array([0.98, 0.96, 0.95]), np.array([0.86, 0.80, 0.74])
    bg = (c0 + (c1 - c0) * np.clip(rr, 0, 1)[..., None]).astype(np.float32)

    tmp = str(pathlib.Path(a.out).with_suffix(".silent.mp4"))
    proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}",
                             "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", tmp],
                            stdin=subprocess.PIPE)
    for i in range(n_out):
        t = i / a.fps
        k = max(j for j, s in enumerate(shots) if s["t"] <= t + 1e-9)
        sh_ = shots[k]; end = shots[k + 1]["t"] if k + 1 < len(shots) else n_out / a.fps
        p = P[sh_["pose"]]; fr = sh_["fr"]
        prog = (t - sh_["t"]) / max(0.3, end - sh_["t"])
        s = fr["s"] * (1 + a.push * prog)
        breath = 0.004 * math.sin(2 * math.pi * 0.23 * t)
        # pose px -> screen: uniform scale about the eyes, breathing = a tiny vertical stretch
        # anchored at the frame bottom (the whole figure, head included, so the collar stays shut)
        S = np.array([[s, 0, 0], [0, s * (1 + breath), 0]])
        S[0, 2] = fr["mid"][0] - s * p["mid"][0]
        S[1, 2] = fr["mid"][1] - s * (1 + breath) * p["mid"][1] + breath * (OH - fr["mid"][1]) * 0.0
        body = cv2.warpAffine(p["rgba"], S.astype(np.float32), (OW, OH), flags=cv2.INTER_CUBIC,
                              borderValue=(0, 0, 0, 0)).clip(0, 1)
        head = np.vstack([upper[eyes_at(t)][:sp], lower[mouth_at(t)][sp:]])
        Mf = S[:, :2] @ p["Mh"][:, :2]
        Mf = np.hstack([Mf, (S[:, :2] @ p["Mh"][:, 2] + S[:, 2])[:, None]]).astype(np.float32)
        hw = cv2.warpAffine(head, Mf, (OW, OH), flags=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR,
                            borderValue=(0, 0, 0, 0)).clip(0, 1)
        out = body[..., :3] * body[..., 3:4] + bg * (1 - body[..., 3:4])
        out = hw[..., :3] * hw[..., 3:4] + out * (1 - hw[..., 3:4])
        ov = cv2.warpAffine(p["over"], S.astype(np.float32), (OW, OH), flags=cv2.INTER_CUBIC,
                            borderValue=(0, 0, 0, 0)).clip(0, 1)
        out = ov[..., :3] * ov[..., 3:4] + out * (1 - ov[..., 3:4])
        proc.stdin.write((np.clip(out, 0, 1) * 255).astype(np.uint8).tobytes())
    proc.stdin.close(); proc.wait()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-i", a.voice, "-af", "loudnorm=I=-14:TP=-1.5",
                    "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-shortest", a.out], check=True)
    pathlib.Path(tmp).unlink(missing_ok=True)
    print(json.dumps({"ok": True, "frames": n_out, "cuts": [round(s["t"], 2) for s in shots[1:]],
                      "shots": [f"{s['pose']}/{s['frame']}" for s in shots]}))


if __name__ == "__main__":
    sys.exit(main())
