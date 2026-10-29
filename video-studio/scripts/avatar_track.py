#!/usr/bin/env python3
"""PLACED AVATAR TRACK: one transparent layer of the talking avatar that sits in a fixed spot of
the reel at a CONSTANT size, mixing both body routes:

  pose    a ChatGPT pose drawing (poses route, pose_reel.prepare_pose) with our face rig on top
  hybrid  a Gemini clip of the character (real motion) keyed off its plain background, with our
          face rig tracked onto its head (hybrid_head)

  python -I avatar_track.py --plan avatar/plan.json --poses raw/ --clips library/ --face face \
      --landmarks face_landmarks.json --mouth mouth.json --voice vo.wav --out avatar/avatar.webm \
      [--preview avatar/preview.mp4]

plan.json:
  {"box": [376, 880, 704, 1040],       screen rect the track covers (x, y, w, h on 1080x1920)
   "anchor": [750, 1150], "d": 94,     eye-midpoint on screen and the LOCKED eye distance (px)
   "segments": [
     {"start": 1.5, "route": "pose", "pose": "p12_point_viewer", "enter": "in"},
     {"start": 6.2, "route": "hybrid", "clip": "g06_chest_size_calm", "from": 0.0},
     {"start": 34.5, "route": "pose", "pose": "p14_stop_palm", "enter": "pop"}, ...],
   "end": 86.0}
  A segment runs until the next one starts. "enter": "in" (rises in from below), "pop" (a 6-frame
  micro scale pop that hides the change) or "cut" (default: the reel covers the change with a
  foreground sweep). Before the first segment the track is empty.

The placement rules: the avatar's size and place never change;
a pose change is hidden by a graphic beat or a tiny pop, never by a size change. So every segment
is scaled to the same eye distance and its (median) eyes put on the same anchor. A hybrid clip
keeps its own small body sway around that anchor.
Output: WebM VP9 with alpha (yuva420p) of the box only, plus an optional preview MP4 on magenta
for the every-frame audit.
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pose_fit as pf  # noqa: E402
from pose_reel import prepare_pose  # noqa: E402
from hybrid_head import smooth, L_EYE, R_EYE, MODELS  # noqa: E402
from face_heal import heal, trim_below_jaw, ears_from_source, load_ear_source  # noqa: E402
from mediapipe.tasks import python as mpt  # noqa: E402


def fit_background(fr, person_x):
    """The Gemini plate is a smooth light gradient. Fit a 2D quadratic per channel to the pixels
    left and right of the person and evaluate it everywhere: the clean plate behind the body.
    (A temporal median fails: the torso never moves, so the median IS the torso.)"""
    H, W = fr.shape[:2]
    yy, xx = np.mgrid[0:H:4, 0:W:4]
    side = (xx < person_x[0]) | (xx > person_x[1])
    X = xx[side].astype(np.float64) / W; Y = yy[side].astype(np.float64) / H
    A = np.stack([np.ones_like(X), X, Y, X * X, X * Y, Y * Y], 1)
    gy, gx = np.mgrid[0:H, 0:W]
    G = np.stack([np.ones(H * W), (gx / W).ravel(), (gy / H).ravel(), (gx / W).ravel() ** 2,
                  (gx * gy / (W * H)).ravel(), (gy / H).ravel() ** 2], 1)
    bg = np.zeros((H, W, 3), np.float32)
    sub = fr[0:H:4, 0:W:4].astype(np.float64)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(A, sub[..., c][side], rcond=None)
        bg[..., c] = (G @ coef).reshape(H, W)
    return bg


def key_plate(fr, bg, lo=6.0, hi=15.0, centre=None):
    """Alpha from the distance to the fitted plate (fit error p99 ~4.3 levels, so the ramp sits
    just above it); holes enclosed by the body are filled (the light-blue shirt is close to the
    backdrop colour but is always enclosed by suit and face); the body interior is solid and
    only a 2 px rim keeps soft alpha (a soft interior let magenta through the shirt and cuffs);
    only the largest blob is kept (drops the sparkle watermark); edge colour is un-mixed."""
    f = fr.astype(np.float32)
    dist = np.abs(f - bg).max(2)
    a = np.clip((dist - lo) / (hi - lo), 0, 1)
    # solid mask from a median-smoothed distance: compression noise (dist 6-10 on plain backdrop next
    # to the hair) formed thin solid chains that ENCLOSED backdrop pockets, which were then filled opaque
    dsm = cv2.medianBlur(np.clip(dist, 0, 255).astype(np.uint8), 5).astype(np.float32)
    solid = (dsm > lo + 0.35 * (hi - lo)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(solid, 8)
    if n > 1:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        keep = (lab == big).astype(np.uint8)
    else:
        keep = solid
    H, W = keep.shape
    # flood the backdrop from a guaranteed-empty 1 px border: seeding at the corner pixel failed
    # whenever that corner (the weakest spot of the plate fit) counted as solid; the whole backdrop
    # then became a "hole" and was filled opaque (a pale panel flashing beside the avatar)
    ff = np.pad(keep, 1); m = np.zeros((H + 4, W + 4), np.uint8)
    cv2.floodFill(ff, m, (0, 0), 2)
    holes = ff[1:-1, 1:-1] == 0
    # an enclosed hole can also be BACKDROP (the gap between an arm and the waist): a large
    # hole region that matches the plate stays see-through; small matching specks are shirt
    # (measured on g01: the gap's core is 2-6 levels off the plate, its shaded fringe 7-25, the
    # shirt 16+ with no plate-like core). A core of >60 plate pixels seeds the gap; it grows
    # through everything under 26 until it hits the drawn outlines (150+).
    # Narrow gaps have no such core but are SHADED plate: the plate's chroma at 75-98% of its
    # brightness (the shirt is brighter than the plate, the suit far darker).
    # What tells a gap from shirt or cuff (both pale blue, both enclosed): SATURATION. Shaded
    # backdrop is paler than the plate (S 32-37 vs 42-45 on g06); shirt and cuffs are as
    # saturated or more (41-48 vs 38-45). A hand on the chest let a shirt patch seed and the
    # whole shirt V went see-through before this test.
    body = keep.astype(bool) | holes
    fs = f.sum(2) + 1e-3; bs = bg.sum(2) + 1e-3
    chroma = np.abs(f / fs[..., None] - bg / bs[..., None]).max(2)
    ratio = fs / bs
    sat = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32)
    sat_bg = cv2.cvtColor(np.clip(bg, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32)
    shade = body & (chroma < 0.012) & (ratio > 0.75) & (ratio < 0.98)
    plate = ((holes & (dist < lo)) | shade).astype(np.uint8)
    n2, lab2, st2, cen2 = cv2.connectedComponentsWithStats(plate, 8)
    seeds = np.zeros_like(holes)
    for j in range(1, n2):
        if st2[j, cv2.CC_STAT_AREA] <= 40:
            continue
        mm = lab2 == j
        if float(dist[mm].mean()) < lo:
            # unshaded plate pocket (beside the hair). Pale shirt patches can be this close to the
            # plate too (a 2nd full render showed 16 frames of shirt holes), so only above the chin
            # or away from the shirt column
            above_chin = centre is None or len(centre) < 3 or cen2[j][1] < centre[2] + 1.6 * centre[1]
            if above_chin or abs(cen2[j][0] - centre[0]) > 1.0 * centre[1]:
                seeds |= mm
            continue
        if float((sat[mm] - sat_bg[mm]).mean()) > -3.0:
            continue                                   # as saturated as the plate: shirt or cuff
        if centre is not None and abs(cen2[j][0] - centre[0]) < 1.0 * centre[1]:
            continue                                   # the shirt V lives on the centre line
        seeds |= mm
    gap = np.zeros_like(holes)
    if seeds.any():
        soft = (body & (dist < 26) & (sat < sat_bg + 2)).astype(np.uint8)
        n3, lab3 = cv2.connectedComponents(soft, connectivity=8)
        gap = np.isin(lab3, np.unique(lab3[seeds & (soft > 0)])) & (lab3 > 0)
        body &= ~gap
    near = cv2.dilate(keep, np.ones((5, 5), np.uint8)).astype(bool) & ~gap
    inner = cv2.erode(body.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    a = np.where(inner, 1.0, np.where(near, a, 0.0)).astype(np.float32)
    # geometric matte: the soft distance ramp left dark speckles along the suit's outer edge
    # (the clip's faint halo). Binary body, opened to drop specks, then anti-aliased; the hair,
    # the one place a soft edge matters, is under our head anyway.
    hard = cv2.morphologyEx((a > 0.5).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    hard = cv2.erode(hard, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)))   # 1 px light rim of plate colour
    a = cv2.GaussianBlur(hard.astype(np.float32), (3, 3), 0.8)
    am = np.maximum(a, 0.02)[..., None]
    col = np.clip((f - (1 - a[..., None]) * bg) / am, 0, 255)
    col = np.where(a[..., None] > 0.97, f, col)
    return np.dstack([col / 255.0, a]).astype(np.float32)


class Frames:
    """A clip's frames held as JPEG bytes, decoded on access (a list of raw frames is ~660 MB per 10 s)."""
    def __init__(self):
        self.buf = []

    def append(self, fr):
        self.buf.append(cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 97])[1])

    def __len__(self):
        return len(self.buf)

    def __getitem__(self, i):
        return cv2.imdecode(self.buf[i], cv2.IMREAD_COLOR)

    def __iter__(self):
        return (self[i] for i in range(len(self)))


def track_eyes(frames, fps):
    det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(MODELS / "face_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO, num_faces=1,
        min_face_detection_confidence=0.3, min_tracking_confidence=0.3))
    H, W = frames[0].shape[:2]
    eL, eR = [], []
    for i, fr in enumerate(frames):
        r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)),
                                 int(i * 1000 / fps))
        if r.face_landmarks:
            p = r.face_landmarks[0]
            a_ = np.mean([[p[k].x * W, p[k].y * H] for k in L_EYE], 0)
            b_ = np.mean([[p[k].x * W, p[k].y * H] for k in R_EYE], 0)
            l_, r_ = (a_, b_) if a_[0] < b_[0] else (b_, a_)
            eL.append(l_); eR.append(r_)
        else:
            eL.append(None); eR.append(None)
    det.close()
    idx = np.arange(len(frames)); tr = {}
    for nm, arr in (("lx", [v[0] if v is not None else np.nan for v in eL]), ("ly", [v[1] if v is not None else np.nan for v in eL]),
                    ("rx", [v[0] if v is not None else np.nan for v in eR]), ("ry", [v[1] if v is not None else np.nan for v in eR])):
        arr = np.array(arr, float); g = ~np.isnan(arr)
        if not g.any():
            raise SystemExit("no face tracked in clip")
        tr[nm] = smooth(np.interp(idx, idx[g], arr[g]), 0.45)
    return np.stack([tr["lx"], tr["ly"]], 1), np.stack([tr["rx"], tr["ry"]], 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("plan", "poses", "clips", "face", "landmarks", "mouth", "voice", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--preview")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--head-scale", type=float, default=1.06)
    ap.add_argument("--only", help="render only t0:t1 seconds (testing)")
    a = ap.parse_args()
    plan = json.loads(pathlib.Path(a.plan).read_text())
    bx, by, bw, bh = plan["box"]
    AX, AY = plan["anchor"]; D = float(plan["d"])
    segs = sorted(plan["segments"], key=lambda s: s["start"])
    t_end = float(plan["end"])

    fd = pathlib.Path(a.face)
    F = json.loads((fd / "face.json").read_text()); sp = F["split"]
    LM = json.loads(pathlib.Path(a.landmarks).read_text())
    eA = [np.array([x + w / 2, y + h / 2]) for x, y, w, h in LM["eyes"]]
    dA = float(np.linalg.norm(eA[1] - eA[0])); midA = (eA[0] + eA[1]) / 2
    ld = lambda n: heal(cv2.imread(str(fd / n), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0)
    patch_mode = plan.get("face_mode") == "patch"     # long hair: face-only patch (face_patch.py)
    if patch_mode:
        upper = {e: ld(f"upper_{e}.png") for e in F["eyes"]}
        lower = {m: ld(f"lower_{m}.png") for m in F["shapes"]}
        import face_patch as fpz
        pmask = cv2.imread(str(fd.parent / "face_mask.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
        plm = np.load(fd.parent / "head_lm.npy")
    else:
        ears = load_ear_source(a.landmarks, F["canvas"][::-1])
        fix = (lambda im: ears_from_source(im, ears, LM["jaw"])) if ears is not None else (lambda im: im)
        upper = {e: fix(ld(f"upper_{e}.png")) for e in F["eyes"]}
        lower = {m: trim_below_jaw(fix(ld(f"lower_{m}.png")), int(LM["lip_y"]) + 25) for m in F["shapes"]}

    # ---- prepare every body source once
    det = pf.detectors()
    POSE = {}
    for s in segs:
        if s["route"] == "pose" and s["pose"] not in POSE:
            img = cv2.imread(str(pathlib.Path(a.poses) / f"{s['pose']}.png"))
            if patch_mode:
                p = fpz.prepare_patch_pose(img, det, plm, pmask, np.vstack([upper["open"][:sp], lower["X"][sp:]]))
            else:
                p = prepare_pose(img, det, upper, lower, sp, LM, dA, midA, a.head_scale, s["pose"])
            k = D / p["d"]                                   # pose px -> screen, eyes on the anchor
            S = np.array([[k, 0, AX - k * p["mid"][0]], [0, k, AY - k * p["mid"][1]]])
            p["S"] = S
            POSE[s["pose"]] = p
    CLIP = {}
    for s in segs:
        if s["route"] == "hybrid" and s["clip"] not in CLIP:
            cap = cv2.VideoCapture(str(pathlib.Path(a.clips) / f"{s['clip']}.mp4"))
            sfps = cap.get(cv2.CAP_PROP_FPS) or 24
            # frames are kept JPEG-compressed: six raw 10 s clips are ~4 GB and ran this laptop
            # out of memory; q97 JPEG of an H.264 source costs nothing visible
            frames = Frames()
            while True:
                ok, fr = cap.read()
                if not ok:
                    break
                frames.append(fr)
            cap.release()
            cache = pathlib.Path(a.out).parent / f"{s['clip']}.eyes.npz"     # tracking is the slow part
            if cache.exists():
                z = np.load(cache); L, R = z["L"], z["R"]
            else:
                L, R = track_eyes(frames, sfps)
                cache.parent.mkdir(parents=True, exist_ok=True); np.savez(cache, L=L, R=R)
            mids = (L + R) / 2; ds = np.linalg.norm(R - L, axis=1)
            cx = float(np.median(mids[:, 0])); d0 = float(np.median(ds))
            bg = fit_background(frames[0], (cx - 4.2 * d0, cx + 4.2 * d0))
            CLIP[s["clip"]] = {"frames": frames, "fps": sfps, "L": L, "R": R, "bg": bg, "d": d0}
    # each hybrid segment: one fixed similarity per segment (scale to D, median eyes of its window
    # onto the anchor); the clip's own sway stays
    for i, s in enumerate(segs):
        s["end"] = segs[i + 1]["start"] if i + 1 < len(segs) else t_end
        if s["route"] == "hybrid":
            c = CLIP[s["clip"]]; f0 = s.get("from", 0.0)
            n = len(c["frames"])
            i0 = int(f0 * c["fps"]); i1 = min(n, int((f0 + s["end"] - s["start"]) * c["fps"]) + 1)
            if i1 - i0 < (s["end"] - s["start"]) * c["fps"] - 2:
                print(f"WARNING: {s['clip']} from {f0}s is shorter than the segment at {s['start']}s; it ping-pongs")
            mids = (c["L"][i0:i1] + c["R"][i0:i1]) / 2
            k = D / c["d"]
            m = np.median(mids, 0)
            s["S"] = np.array([[k, 0, AX - k * m[0]], [0, k, AY - k * m[1]]])

    cues = json.loads(pathlib.Path(a.mouth).read_text())["mouthCues"]
    vo_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice],
                                  capture_output=True, text=True).stdout.strip())
    n_out = int(round(t_end * a.fps))
    rng = np.random.default_rng(11); blinks = []; t = 1.0
    while t < t_end:
        blinks.append(t); t += 2.4 + rng.random() * 2.2
    blinks = [b for b in blinks if all(abs(b - s["start"]) > 0.25 for s in segs)]
    ci = [0]

    def mouth_at(t):
        if t > vo_len + 0.05:
            return "X"
        while ci[0] + 1 < len(cues) and cues[ci[0] + 1]["start"] <= t:
            ci[0] += 1
        while ci[0] > 0 and cues[ci[0]]["start"] > t:
            ci[0] -= 1
        return cues[ci[0]]["value"] if cues[0]["start"] <= t else "X"

    def eyes_at(t):
        for b in blinks:
            d = (t - b) * a.fps
            if 0 <= d < 1 or 3 <= d < 4: return "half"
            if 1 <= d < 3: return "closed"
        return "open"

    def to_box(S):
        """screen similarity -> box coordinates"""
        B = S.copy(); B[0, 2] -= bx; B[1, 2] -= by
        return B

    def over(dst, src):
        al = src[..., 3:4]
        dst[..., :3] = src[..., :3] * al + dst[..., :3] * (1 - al)
        dst[..., 3:4] = al + dst[..., 3:4] * (1 - al)

    def enter_fx(s, t):
        """returns (scale about the anchor, alpha, y offset) for entrances"""
        e = s.get("enter", "cut"); u = (t - s["start"]) * a.fps
        if e == "in" and u < 12:
            x = u / 12; ease = 1 - (1 - x) ** 3
            return 1.0, min(1.0, x * 1.6), (1 - ease) * 260
        if e == "pop" and u < 7:
            x = u / 7    # back-out: 0.94 -> 1.03 -> 1.0
            c1 = 1.9; c3 = c1 + 1
            ease = 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
            return 0.94 + 0.06 * ease, 1.0, 0.0
        return 1.0, 1.0, 0.0

    rng_t = (0, n_out)
    if a.only:
        t0, t1 = [float(v) for v in a.only.split(":")]
        rng_t = (int(t0 * a.fps), int(t1 * a.fps))
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{bw}x{bh}",
                            "-r", str(a.fps), "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "18", "-b:v", "0",
                            "-deadline", "good", "-cpu-used", "5", "-row-mt", "1", "-threads", "2", "-auto-alt-ref", "0", str(out)],
                           stdin=subprocess.PIPE)
    prev = None
    if a.preview:
        prev = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{bw}x{bh}",
                                 "-r", str(a.fps), "-i", "-", "-i", a.voice, "-ss", str(rng_t[0] / a.fps),
                                 "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-af", "apad", "-shortest", a.preview],
                                stdin=subprocess.PIPE) if not a.only else \
            subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{bw}x{bh}",
                              "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", a.preview],
                             stdin=subprocess.PIPE)
    magenta = np.zeros((bh, bw, 3), np.float32); magenta[:] = (1.0, 0.0, 1.0)
    log = []
    for i in range(*rng_t):
        t = i / a.fps
        canvas = np.zeros((bh, bw, 4), np.float32)
        live = [s for s in segs if s["start"] <= t + 1e-9 < s["end"]]
        if live:
            s = live[0]
            sc, alpha, yoff = enter_fx(s, t)
            breath = 0.004 * math.sin(2 * math.pi * 0.23 * t)
            # entrance scale about the anchor, y offset; breathing = tiny vertical stretch about the anchor
            E = np.array([[sc, 0, AX * (1 - sc)], [0, sc * (1 + breath), AY * (1 - sc * (1 + breath)) + yoff]])
            if s["route"] == "pose":
                p = POSE[s["pose"]]
                S = E[:, :2] @ p["S"]; S = np.hstack([S[:, :2], (E[:, :2] @ p["S"][:, 2] + E[:, 2])[:, None]])
                B = to_box(S)
                body = cv2.warpAffine(p["rgba"], B.astype(np.float32), (bw, bh), flags=cv2.INTER_AREA,
                                      borderValue=(0, 0, 0, 0)).clip(0, 1)
                head = np.vstack([upper[eyes_at(t)][:sp], lower[mouth_at(t)][sp:]])
                if patch_mode:
                    head = head.copy()
                    head[..., :3] = np.clip(head[..., :3] * p["gain"], 0, 1)
                    head[..., 3] *= pmask
                Mf = B[:, :2] @ p["Mh"][:, :2]
                Mf = np.hstack([Mf, (B[:, :2] @ p["Mh"][:, 2] + B[:, 2])[:, None]]).astype(np.float32)
                hw = cv2.warpAffine(head, Mf, (bw, bh), flags=cv2.INTER_AREA, borderValue=(0, 0, 0, 0)).clip(0, 1)
                ov = cv2.warpAffine(p["over"], B.astype(np.float32), (bw, bh), flags=cv2.INTER_AREA,
                                    borderValue=(0, 0, 0, 0)).clip(0, 1)
                over(canvas, body); over(canvas, hw); over(canvas, ov)
                ed = D * sc
            else:
                c = CLIP[s["clip"]]
                u = s.get("from", 0.0) + (t - s["start"])
                n = len(c["frames"]); fi = int(u * c["fps"])
                if fi >= n:                                   # ping-pong past the end
                    fi = max(0, 2 * (n - 1) - fi)
                fr = c["frames"][fi]
                body_src = key_plate(fr, c["bg"], centre=(float((c["L"][fi][0] + c["R"][fi][0]) / 2), c["d"], float((c["L"][fi][1] + c["R"][fi][1]) / 2)))
                S = E[:, :2] @ s["S"]; S = np.hstack([S[:, :2], (E[:, :2] @ s["S"][:, 2] + E[:, 2])[:, None]])
                B = to_box(S)
                body = cv2.warpAffine(body_src, B.astype(np.float32), (bw, bh), flags=cv2.INTER_CUBIC,
                                      borderValue=(0, 0, 0, 0)).clip(0, 1)
                # our head on the clip's eyes (clip px -> box via B)
                Lc = B[:, :2] @ c["L"][fi] + B[:, 2]; Rc = B[:, :2] @ c["R"][fi] + B[:, 2]
                dV = float(np.linalg.norm(Rc - Lc)); k = dV / dA * a.head_scale
                ang = math.atan2(Rc[1] - Lc[1], Rc[0] - Lc[0])
                M = np.array([[math.cos(ang) * k, -math.sin(ang) * k, 0], [math.sin(ang) * k, math.cos(ang) * k, 0]], np.float32)
                M[:, 2] = (Lc + Rc) / 2 - M[:, :2] @ midA
                head = np.vstack([upper[eyes_at(t)][:sp], lower[mouth_at(t)][sp:]])
                hw = cv2.warpAffine(head, M, (bw, bh), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)).clip(0, 1)
                # the clip's own head must never peek out around ours: inside our head's column
                # band, above our chin, the clip keeps only what lies under our head
                # (only ABOVE mouth level: lower, the suit's shoulder line rises above our chin
                # beside the neck (a cut at the chin sliced the shoulders off), and erasing skin
                # there opened a see-through sliver between our beard and the collar)
                hm = hw[..., 3] > 0.02
                ys, xs = np.nonzero(hm)
                if len(ys):
                    x0, x1 = xs.min(), xs.max()
                    mouth_y = int((Lc[1] + Rc[1]) / 2 + 0.9 * dV)
                    hmd = cv2.dilate(hm.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
                    zone = np.zeros((bh, bw), bool)
                    zone[:max(0, mouth_y), max(0, x0 - 6):x1 + 7] = True
                    body[..., 3] = np.where(zone & ~hmd, 0.0, body[..., 3])
                over(canvas, body); over(canvas, hw)
                ed = dV
            canvas[..., 3] *= alpha
            log.append(round(ed, 2))
        bgra = (np.clip(canvas, 0, 1) * 255).astype(np.uint8)
        enc.stdin.write(bgra.tobytes())
        if prev:
            pv = canvas[..., :3] * canvas[..., 3:4] + magenta * (1 - canvas[..., 3:4])
            pv8 = (np.clip(pv, 0, 1) * 255).astype(np.uint8)
            cv2.putText(pv8, f"{i} {t:5.2f}", (8, bh - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            prev.stdin.write(pv8.tobytes())
    enc.stdin.close(); enc.wait()
    if prev:
        prev.stdin.close(); prev.wait()
    eds = np.array(log) if log else np.array([D])
    print(json.dumps({"ok": True, "frames": rng_t[1] - rng_t[0], "eye_d": {"min": float(eds.min()), "max": float(eds.max()),
                      "median": float(np.median(eds))}, "out": str(out)}))


if __name__ == "__main__":
    sys.exit(main())
