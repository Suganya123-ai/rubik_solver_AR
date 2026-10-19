"""Synthetic webcam frames of a Rubik's cube with exact ground truth.

Cube states come from the app's own move model, so the stickers drawn are
the real result of real moves. Faces are drawn with a pinhole camera and
per-face perspective warps; then lighting, white balance, glare, fingers,
background clutter, blur, noise and JPEG compression are applied.
"""
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root, for cube/
from cube.cube_state import FACE_OFFSET  # noqa: E402

W, H, FOCAL = 640, 480, 600.0
HALF = 0.5
COLOR_NAMES = ['white', 'yellow', 'red', 'orange', 'green', 'blue']
LETTER_TO_COLOR = {'U': 'white', 'D': 'yellow', 'R': 'red', 'L': 'orange', 'F': 'green', 'B': 'blue'}
BASE_RGB = {'white': (238, 238, 232), 'yellow': (250, 212, 25), 'red': (196, 24, 44),
            'orange': (255, 108, 22), 'green': (0, 158, 82), 'blue': (0, 78, 188)}

# Each face: top-left corner, column direction, row direction (standard
# facelet rasters, matching the app's model and kociemba).
FACE_GEOM = {
    'U': ((-HALF, HALF, -HALF), (1, 0, 0), (0, 0, 1)),
    'F': ((-HALF, HALF, HALF), (1, 0, 0), (0, -1, 0)),
    'R': ((HALF, HALF, HALF), (0, 0, -1), (0, -1, 0)),
    'D': ((-HALF, -HALF, HALF), (1, 0, 0), (0, 0, -1)),
    'L': ((-HALF, HALF, -HALF), (0, 0, 1), (0, -1, 0)),
    'B': ((HALF, HALF, -HALF), (-1, 0, 0), (0, -1, 0)),
}
FACE_NORMAL = {'U': (0, 1, 0), 'D': (0, -1, 0), 'F': (0, 0, 1), 'B': (0, 0, -1), 'R': (1, 0, 0), 'L': (-1, 0, 0)}
# 7 hexagon keypoints of the U-F-R corner view: FRU (centre), then FLU, BLU, BRU, BRD, FRD, FLD.
CORNER_KPTS = [(HALF, HALF, HALF), (-HALF, HALF, HALF), (-HALF, HALF, -HALF), (HALF, HALF, -HALF),
               (HALF, -HALF, -HALF), (HALF, -HALF, HALF), (-HALF, -HALF, HALF)]

LEVELS = {
    'normal': dict(wb=0.08, gain=(0.85, 1.15), glare_p=0.15, glare_max=0.45, hand_p=0.3, noise=(1, 4),
                   blur=(0, 0.8), motion_p=0.05, jpeg=(80, 95), ambient=(0.55, 0.75)),
    'hard': dict(wb=0.2, gain=(0.55, 1.35), glare_p=0.5, glare_max=0.9, hand_p=0.6, noise=(3, 9),
                 blur=(0.3, 1.6), motion_p=0.25, jpeg=(55, 85), ambient=(0.35, 0.7)),
    # Like the first real test (a room lit from the ceiling): warm light from
    # above, so the top side is bright and the others in shade, and glossy
    # logo caps on the centres that reflect the light and read almost white.
    'real': dict(wb=0.1, gain=(0.75, 1.25), glare_p=0.4, glare_max=0.7, hand_p=0.6, noise=(2, 6),
                 blur=(0.2, 1.2), motion_p=0.1, jpeg=(65, 90), ambient=(0.25, 0.45),
                 overhead=True, warm=(0.05, 0.2), logo_p=0.5),
}


def rot(yaw, pitch, roll):
    a, b, c = map(math.radians, (yaw, pitch, roll))
    ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return rz @ rx @ ry


class Pose:
    def __init__(self, R, t):
        self.R, self.t = R, np.asarray(t, float)

    def to_cam(self, p):
        return self.R @ np.asarray(p, float) + self.t

    def project(self, p):
        x, y, z = self.to_cam(p)
        return np.array([W / 2 + FOCAL * x / -z, H / 2 - FOCAL * y / -z])

    def visible(self, face):
        n = self.R @ np.asarray(FACE_NORMAL[face], float)
        centre = self.to_cam(np.asarray(FACE_NORMAL[face], float) * HALF)
        return float(n @ -centre) > 1e-6


def face_corners_3d(face):
    o, c, r = (np.asarray(v, float) for v in FACE_GEOM[face])
    s = 2 * HALF
    return [o, o + c * s, o + c * s + r * s, o + r * s]


def sticker_center_3d(face, k):
    o, c, r = (np.asarray(v, float) for v in FACE_GEOM[face])
    row, col = divmod(k, 3)
    cell = 2 * HALF / 3
    return o + c * cell * (col + 0.5) + r * cell * (row + 0.5)


def sticker_quad_3d(face, k, inset=0.08):
    o, c, r = (np.asarray(v, float) for v in FACE_GEOM[face])
    row, col = divmod(k, 3)
    cell = 2 * HALF / 3
    a, b = cell * (col + inset), cell * (col + 1 - inset)
    d, e = cell * (row + inset), cell * (row + 1 - inset)
    return [o + c * a + r * d, o + c * b + r * d, o + c * b + r * e, o + c * a + r * e]


# Stickerless cubes (coloured plastic, no black body) are brighter and lighter.
STICKERLESS_RGB = {'white': (246, 246, 240), 'yellow': (255, 222, 45), 'red': (236, 62, 72),
                   'orange': (255, 142, 40), 'green': (35, 190, 95), 'blue': (25, 95, 222)}


def cube_palette(rng, style='stickered'):
    """Per-cube sticker colors: real cubes differ in plastic shade."""
    pal = {}
    for name, rgb in (STICKERLESS_RGB if style == 'stickerless' else BASE_RGB).items():
        jitter = rng.normal(0, 9, 3)
        pal[name] = np.clip(np.asarray(rgb, float) + jitter, 0, 255)
    return pal


def stickerless_texture(colors, pal, rng, T=240):
    """Coloured plastic tiles separated by thin dark grooves; centres carry a
    round cap in a slightly different shade (like most speed cubes)."""
    tex = np.full((T, T, 3), rng.uniform(20, 55), np.float32)
    cell = T / 3
    for k, name in enumerate(colors):
        row, col = divmod(k, 3)
        inset = rng.uniform(0.02, 0.05) * cell
        x0, y0 = int(col * cell + inset), int(row * cell + inset)
        x1, y1 = int((col + 1) * cell - inset), int((row + 1) * cell - inset)
        rgb = np.clip(pal[name] + rng.normal(0, 4, 3), 0, 255)
        bgr = tuple(float(v) for v in rgb[::-1])
        r = int(rng.uniform(0.12, 0.25) * cell)
        cv2.rectangle(tex, (x0 + r, y0), (x1 - r, y1), bgr, -1)
        cv2.rectangle(tex, (x0, y0 + r), (x1, y1 - r), bgr, -1)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
            cv2.circle(tex, (cx, cy), r, bgr, -1, lineType=cv2.LINE_AA)
        grad = np.linspace(1.04, 0.92, y1 - y0)[:, None, None]  # soft plastic shading
        tex[y0:y1, x0:x1] *= grad
        if k == 4 and rng.uniform() < 0.8:
            cap = tuple(float(v) for v in np.clip(rgb * rng.uniform(0.85, 1.12), 0, 255)[::-1])
            cv2.circle(tex, (int((x0 + x1) / 2), int((y0 + y1) / 2)), int(rng.uniform(0.28, 0.38) * cell), cap, -1,
                       lineType=cv2.LINE_AA)
    return tex


def face_texture(colors, pal, rng, T=240, style='stickered'):
    if style == 'stickerless':
        return stickerless_texture(colors, pal, rng, T)
    tex = np.full((T, T, 3), 18, np.float32) + rng.normal(0, 2, (T, T, 3)).astype(np.float32)
    cell = T / 3
    for k, name in enumerate(colors):
        row, col = divmod(k, 3)
        x0, y0 = int(col * cell + 0.08 * cell), int(row * cell + 0.08 * cell)
        x1, y1 = int((col + 1) * cell - 0.08 * cell), int((row + 1) * cell - 0.08 * cell)
        rgb = np.clip(pal[name] + rng.normal(0, 4, 3), 0, 255)
        r = int(0.14 * cell)
        bgr = tuple(float(v) for v in rgb[::-1])
        cv2.rectangle(tex, (x0 + r, y0), (x1 - r, y1), bgr, -1)
        cv2.rectangle(tex, (x0, y0 + r), (x1, y1 - r), bgr, -1)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
            cv2.circle(tex, (cx, cy), r, bgr, -1, lineType=cv2.LINE_AA)
    return tex


def photo_background(rng, photo):
    """A real photo (e.g. a COCO image, often with people) as the backdrop:
    random crop, flip, brightness and blur."""
    ph, pw = photo.shape[:2]
    scale = max(W / pw, H / ph) * rng.uniform(1.0, 1.6)
    img = cv2.resize(photo, (int(pw * scale) + 1, int(ph * scale) + 1)).astype(np.float32)
    y = int(rng.uniform(0, img.shape[0] - H + 1))
    x = int(rng.uniform(0, img.shape[1] - W + 1))
    img = img[y:y + H, x:x + W]
    if rng.uniform() < 0.5:
        img = img[:, ::-1]
    img = img * rng.uniform(0.6, 1.15)
    return cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 2.5))


def background(rng, photo=None):
    if photo is not None:
        return photo_background(rng, photo)
    base = rng.uniform(40, 200, 3)
    grad = np.linspace(rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.2), H)[:, None, None]
    img = np.ones((H, W, 3), np.float32) * base * grad
    for _ in range(rng.integers(12, 35)):
        col = tuple(float(v) for v in rng.uniform(0, 255, 3))
        kind = rng.integers(0, 3)
        x, y = int(rng.uniform(0, W)), int(rng.uniform(0, H))
        if kind == 0:
            cv2.rectangle(img, (x, y), (x + int(rng.uniform(15, 160)), y + int(rng.uniform(15, 160))), col, -1)
        elif kind == 1:
            cv2.circle(img, (x, y), int(rng.uniform(8, 70)), col, -1)
        else:
            cv2.line(img, (x, y), (int(rng.uniform(0, W)), int(rng.uniform(0, H))), col, int(rng.uniform(2, 9)))
    noise = cv2.GaussianBlur(rng.normal(0, 25, (H, W, 1)).astype(np.float32), (0, 0), 6)
    return cv2.GaussianBlur(img + noise[..., None], (0, 0), rng.uniform(0.5, 3))


def render(state_arr, pose, rng, level='normal', faces_override=None, pal=None, session=None,
           style='stickered', bg_photo=None, hand='fingers'):
    """session: optional {'wb': 3 multipliers, 'gain': g} shared by frames of one sitting."""
    """state_arr: 54 face letters (app order). faces_override: {face: 9 color names}
    to paint a face's content regardless of state (used for scan frames).
    style: 'stickered' (black body) or 'stickerless'; bg_photo: a real photo to
    use as background; hand: 'fingers' (fingertips only) or 'hand' (a palm
    behind the cube plus fingers). The defaults reproduce the original frames."""
    cfg = LEVELS[level]
    pal = pal if pal is not None else cube_palette(rng, style)
    img = background(rng, bg_photo)
    holding = hand == 'hand' and rng.uniform() < 0.75
    if holding:
        add_palm(img, pose, rng)
    if cfg.get('overhead'):  # from above the picture, a little toward the camera
        light = np.array([rng.uniform(-0.3, 0.3), 1.0, rng.uniform(0.2, 0.7)])
    else:
        light = np.array([rng.uniform(-0.6, 0.6), rng.uniform(0.3, 1.0), rng.uniform(0.3, 1.0)])
    light /= np.linalg.norm(light)
    ambient = rng.uniform(*cfg['ambient'])

    order = sorted((f for f in FACE_GEOM if pose.visible(f)),
                   key=lambda f: pose.to_cam(np.asarray(FACE_NORMAL[f], float) * HALF)[2])
    silhouette = np.zeros((H, W), np.uint8)
    for f in order:
        colors = (faces_override or {}).get(f) or [LETTER_TO_COLOR[x] for x in state_arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]]
        tex = face_texture(colors, pal, rng, style=style)
        if rng.uniform() < cfg.get('logo_p', 0):
            add_logo(tex, pal[colors[4]], rng)
        T = tex.shape[0]
        src = np.float32([[0, 0], [T, 0], [T, T], [0, T]])
        dst = np.float32([pose.project(p) for p in face_corners_3d(f)])
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(tex, M, (W, H), flags=cv2.INTER_LINEAR)
        mask = cv2.warpPerspective(np.ones((T, T), np.float32), M, (W, H))
        n = pose.R @ np.asarray(FACE_NORMAL[f], float)
        shade = ambient + (1 - ambient) * max(0.0, float(n @ light))
        warped *= shade
        img = img * (1 - mask[..., None]) + warped * mask[..., None]
        silhouette |= (mask > 0.5).astype(np.uint8)
        if rng.uniform() < cfg['glare_p'] / max(1, len(order) - 1):
            ys, xs = np.nonzero(mask > 0.5)
            if len(xs):
                i = rng.integers(len(xs))
                blob = np.zeros((H, W), np.float32)
                cv2.ellipse(blob, (int(xs[i]), int(ys[i])), (int(rng.uniform(8, 35)), int(rng.uniform(5, 22))),
                            rng.uniform(0, 180), 0, 360, 1.0, -1)
                blob = cv2.GaussianBlur(blob, (0, 0), rng.uniform(4, 10)) * mask
                img += blob[..., None] * 255 * rng.uniform(0.2, cfg['glare_max'])

    if holding or rng.uniform() < cfg['hand_p']:
        add_fingers(img, silhouette, rng)

    if session is None:
        session = new_session(rng, level)
    img = img * session['wb'][::-1] * session['gain']
    sigma = rng.uniform(*cfg['blur'])
    if sigma > 0.05:
        img = cv2.GaussianBlur(img, (0, 0), sigma)
    if rng.uniform() < cfg['motion_p']:
        k = int(rng.uniform(5, 13))
        kernel = np.zeros((k, k), np.float32)
        kernel[k // 2, :] = 1 / k
        M = cv2.getRotationMatrix2D((k / 2, k / 2), rng.uniform(0, 180), 1)
        img = cv2.filter2D(img, -1, cv2.warpAffine(kernel, M, (k, k)))
    img += rng.normal(0, rng.uniform(*cfg['noise']), img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, int(rng.uniform(*cfg['jpeg']))])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def add_logo(tex, centre_rgb, rng):
    """A glossy logo cap on the centre sticker: mostly reflected light, so it
    reads close to white, with only a rim of the real colour around it."""
    T = tex.shape[0]
    mix = rng.uniform(0.55, 0.85)
    rgb = np.asarray(centre_rgb, float) * (1 - mix) + 245 * mix
    cv2.circle(tex, (T // 2, T // 2), int(rng.uniform(0.3, 0.42) * T / 3), tuple(float(v) for v in rgb[::-1]), -1,
               lineType=cv2.LINE_AA)


def new_session(rng, level='normal'):
    cfg = LEVELS[level]
    wb = 1 + rng.uniform(-cfg['wb'], cfg['wb'], 3)
    if cfg.get('warm'):  # warm room light: more red, less blue
        w = rng.uniform(*cfg['warm'])
        wb *= np.array([1 + w / 2, 1.0, 1 - w])
    return {'wb': wb, 'gain': rng.uniform(*cfg['gain'])}


def skin_tone(rng):
    """BGR skin colour on a light-to-dark scale (channels move together)."""
    t = rng.uniform()
    light, dark = np.array([238, 198, 172]), np.array([92, 60, 44])
    return np.clip(dark + (light - dark) * t + rng.normal(0, 6, 3), 0, 255)[::-1]


def add_palm(img, pose, rng):
    """A palm under/behind the cube (drawn before the cube), like a hand holding it."""
    corners = np.float32([pose.project((x, y, z)) for x in (-HALF, HALF) for y in (-HALF, HALF) for z in (-HALF, HALF)])
    (cx, cy), radius = cv2.minEnclosingCircle(corners)
    angle = rng.uniform(-60, 60)
    d = np.array([math.sin(math.radians(angle)), math.cos(math.radians(angle))])
    centre = np.array([cx, cy]) + d * radius * rng.uniform(0.5, 0.9)
    col = tuple(float(v) for v in skin_tone(rng))
    cv2.ellipse(img, tuple(int(v) for v in centre), (int(radius * rng.uniform(0.7, 1.0)), int(radius * rng.uniform(0.9, 1.4))),
                angle, 0, 360, col, -1, cv2.LINE_AA)
    wrist_end = centre + d * radius * 2.5
    cv2.line(img, tuple(int(v) for v in centre), tuple(int(v) for v in wrist_end), col, int(radius * 0.9), cv2.LINE_AA)


def add_fingers(img, silhouette, rng):
    cnts, _ = cv2.findContours(silhouette, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return
    cnt = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    (cx, cy), _ = cv2.minEnclosingCircle(cnt)
    size = math.sqrt(cv2.contourArea(cnt))
    skin = np.array([rng.uniform(150, 235), rng.uniform(110, 180), rng.uniform(85, 150)])[::-1]
    for _ in range(rng.integers(1, 4)):
        px, py = cnt[rng.integers(len(cnt))]
        d = np.array([px - cx, py - cy], float)
        d /= np.linalg.norm(d) + 1e-6
        depth = rng.uniform(0.04, 0.16) * size  # how far the fingertip reaches onto the cube
        tip = np.array([px, py]) - d * depth
        base = np.array([px, py]) + d * size * 0.8
        width = int(size * rng.uniform(0.07, 0.11))
        col = tuple(float(v) for v in skin * rng.uniform(0.85, 1.05))
        cv2.line(img, tuple(int(v) for v in tip), tuple(int(v) for v in base), col, width * 2, cv2.LINE_AA)
        cv2.circle(img, tuple(int(v) for v in tip), width, col, -1, cv2.LINE_AA)


# ---------- poses ----------
def scan_pose(rng, aligned=False):
    """Front face toward the camera, like the scanning step."""
    if aligned:
        R = rot(rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-4, 4))
        face_px = 0.84 * min(W, H) * rng.uniform(0.95, 1.05)
        t = (rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03))
    else:
        R = rot(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(-25, 25))
        face_px = rng.uniform(120, 240)
        t = (rng.uniform(-0.25, 0.25), rng.uniform(-0.2, 0.2))
    dist = FOCAL * 1.0 / face_px + HALF
    return Pose(R, (t[0] * dist, t[1] * dist, -dist))


def corner_pose(rng):
    """Cube held corner-on so Top, Front and Right are visible (tracking step)."""
    R = rot(rng.uniform(-55, -35), rng.uniform(22, 38), rng.uniform(-12, 12))
    cube_px = rng.uniform(170, 280)  # rough on-screen height of the cube
    dist = FOCAL * 1.6 / cube_px + HALF
    t = (rng.uniform(-0.2, 0.2), rng.uniform(-0.15, 0.15))
    return Pose(R, (t[0] * dist, t[1] * dist, -dist))


def corner_pose_wide(rng):
    """Like corner_pose, but closer (the cube can fill most of the frame) and at
    wider angles, as when a person holds the cube up to a webcam."""
    R = rot(rng.uniform(-62, -28), rng.uniform(12, 48), rng.uniform(-25, 25))
    cube_px = rng.uniform(170, 440)
    dist = FOCAL * 1.6 / cube_px + HALF
    t = (rng.uniform(-0.25, 0.25), rng.uniform(-0.18, 0.18))
    return Pose(R, (t[0] * dist, t[1] * dist, -dist))


def jitter_pose(pose, rng, deg=3.0, shift=0.02):
    R = rot(rng.normal(0, deg), rng.normal(0, deg), rng.normal(0, deg)) @ pose.R
    t = pose.t + np.array([rng.normal(0, shift), rng.normal(0, shift), rng.normal(0, shift)])
    return Pose(R, t)


def gt_sticker_quads(pose, face):
    return [np.float32([pose.project(p) for p in sticker_quad_3d(face, k)]) for k in range(9)]


def gt_keypoints(pose):
    return np.float32([pose.project(p) for p in CORNER_KPTS])
