"""Frame-accurate removal of the Gemini/Veo sparkle watermark (1280x720 clips).

History, because each version failed differently (all judged on 1:1 corner crops of a
bright clip AND a dark textured one):
  v0  ffmpeg un-blend + delogo                    blocky smear on texture
  v0b un-blend + feathered rim blur               red/colour fringe on dark plates
  v1  un-blend blended with a smooth inpaint,     no fringe, but a soft star-shaped SMUDGE on
      weighted by darkness                        dark textured plates (water, shredded paper)
  v2  luma un-blend + chroma inpaint + rim blur   texture kept, but a faint blurred star OUTLINE:
                                                  the stored alpha map does not match each clip's
                                                  compression-softened edge
  v3  (this) estimate the alpha map PER CLIP from the clip itself (negative values allowed, for
      the codec's dark ringing halo), then un-blend exactly

Why per-clip estimation works: the mark is identical in every frame while the scene
moves. For each frame, G = a smooth inpaint of the patch from pixels outside the mark
approximates the background. Then  A - G = a (255 - G) + (1 - a)(bg - G),  and the last
term averages towards zero over ~240 frames of moving content. Least squares over all
frames and channels gives a(x) with the clip's real edge profile, so the un-blend leaves
no outline. Chroma inside the mark is still replaced by the inpaint (the fringe is a
yuv420p chroma artefact); luma is the exact un-blend, so texture survives.

The stored alpha map (../assets/veo-watermark-alpha.png) is only used to locate the mark.
"""
import os
import subprocess

import cv2
import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(_here)), "assets", "veo-watermark-alpha.png"),   # <skill>/assets
    os.path.join(os.path.dirname(_here), "assets", "veo-watermark-alpha.png"),
    os.path.join(_here, "veo-watermark-alpha.png"),
]
ALPHA = next((p for p in _candidates if os.path.exists(p)), _candidates[-1])
X0, Y0, W, H = 1090, 530, 160, 140          # patch containing the mark with margin

_a0 = cv2.imread(ALPHA, cv2.IMREAD_GRAYSCALE).astype(np.float32)[Y0:Y0 + H, X0:X0 + W] / 255.0
_core = (_a0 > 0.02).astype(np.uint8)
REGION = cv2.dilate(_core, np.ones((9, 9), np.uint8)).astype(bool)        # where alpha may be non-zero
OUTSIDE = (1 - cv2.dilate(_core, np.ones((15, 15), np.uint8))).astype(np.float32)
W_C = np.clip(cv2.GaussianBlur(cv2.dilate(_core, np.ones((9, 9), np.uint8)).astype(np.float32),
                               (0, 0), 2.0) * 1.1, 0, 1)[..., None]


def _inpaint(img, sig=6.0):
    num = cv2.GaussianBlur(img * OUTSIDE[..., None], (0, 0), sig)
    den = cv2.GaussianBlur(OUTSIDE, (0, 0), sig)[..., None] + 1e-4
    return num / den


def _read_patches(ffmpeg, src, w=1280, h=720):
    dec = subprocess.Popen([ffmpeg, "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    size, out = w * h * 3, []
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        out.append(fr[Y0:Y0 + H, X0:X0 + W].astype(np.float32))
    dec.wait()
    return out


def estimate_alpha(patches):
    """Per-pixel alpha of the white overlay, least squares over every frame and channel."""
    num = np.zeros((H, W), np.float64)
    den = np.zeros((H, W), np.float64)
    for p in patches:
        g = _inpaint(p)
        d = 255.0 - g
        num += ((p - g) * d).sum(-1)
        den += (d * d).sum(-1)
    a = (num / np.maximum(den, 1e-6)).astype(np.float32)
    # NEGATIVE alpha is real: H.264 leaves a static dark ringing halo just outside the
    # mark's bright edge. Clamping at 0 cannot cancel it and leaves a hairline dark
    # outline of the star. No blur either: it would soften the edge profile we just measured.
    a = np.where(REGION, np.clip(a, -0.25, 0.6), 0.0)
    return a.astype(np.float32)[..., None]


def clean_patch(p, a):
    p = p.astype(np.float32)
    U = np.clip((p - 255.0 * a) / (1.0 - a), 0, 255) / 255.0   # exact un-blend with the clip's own alpha
    # OpenCV float YCrCb expects 0..1 (chroma offset 0.5). Never feed 0..255 and never clip
    # between the two conversions: negative chroma gets destroyed and the patch turns purple.
    Uy = cv2.cvtColor(U, cv2.COLOR_RGB2YCrCb)
    G = cv2.cvtColor(_inpaint(U), cv2.COLOR_RGB2YCrCb)
    out = Uy.copy()
    out[..., 1:] = Uy[..., 1:] * (1 - W_C) + G[..., 1:] * W_C  # chroma from outside: no fringe
    rgb = cv2.cvtColor(out.astype(np.float32), cv2.COLOR_YCrCb2RGB)
    return np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def scrub_file(ffmpeg, src, dst, w=1280, h=720, fps="24"):
    a = estimate_alpha(_read_patches(ffmpeg, src, w, h))
    dec = subprocess.Popen([ffmpeg, "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen([ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{w}x{h}", "-r", fps, "-i", "-", "-an", "-c:v", "libx264",
                            "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", dst],
                           stdin=subprocess.PIPE)
    n, size = 0, w * h * 3
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
        fr[Y0:Y0 + H, X0:X0 + W] = clean_patch(fr[Y0:Y0 + H, X0:X0 + W], a)
        enc.stdin.write(fr.tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    return n
