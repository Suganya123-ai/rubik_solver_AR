"""Synthetic webcam frames of a Pyraminx with exact ground truth (same camera,
lighting, backgrounds, hands, blur and noise as render.py's cube frames).

The puzzle is shown corner-on: one corner points roughly at the camera, so the
three faces around it are visible. The 4 keypoints are its corners in the
picture: 0 the corner nearest the camera, then the three outer corners going
clockwise around it, starting from the highest one (smallest y). Mirroring a
picture left-right keeps 0 and 1 and swaps 2 and 3 (flip_idx [0, 1, 3, 2]).
"""
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
import render as R  # noqa: E402  (the cube renderer: camera, backgrounds, hands, effects)
from pyra.geometry import CORNERS, FACE_CORNERS, FACES, OPPOSITE, STICKERS  # noqa: E402

LETTER_TO_COLOR = {'F': 'green', 'R': 'blue', 'L': 'red', 'D': 'yellow'}
BASE_RGB = {'green': (20, 165, 70), 'blue': (10, 85, 200), 'red': (205, 25, 40), 'yellow': (250, 215, 20)}
STICKERLESS_RGB = {'green': (40, 195, 90), 'blue': (30, 110, 230), 'red': (235, 55, 65), 'yellow': (255, 225, 50)}
SCALE = 0.75   # puzzle size relative to the cube renderer's unit cube (edge ~1.2 units)


def palette(rng, style):
    base = STICKERLESS_RGB if style == 'stickerless' else BASE_RGB
    return {n: np.clip(np.asarray(c, float) + rng.normal(0, 9, 3), 0, 255) for n, c in base.items()}


def face_normal(face):
    c = np.mean([CORNERS[n] for n in FACE_CORNERS[face]], axis=0)
    return c / np.linalg.norm(c)


def visible(pose, face):
    n = pose.R @ face_normal(face)
    c = pose.to_cam(np.mean([CORNERS[n_] for n_ in FACE_CORNERS[face]], axis=0) * SCALE)
    return float(n @ -c) / (np.linalg.norm(c) + 1e-9)


def _rotation_to(a, b):
    """Rotation taking unit vector a onto unit vector b."""
    v, c = np.cross(a, b), float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else -np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def corner_on_pose(rng, near=None, tilt_max=38, far=False):
    """A random hold with corner `near` (random if None) pointing roughly at the camera."""
    near = near or 'ULRB'[int(rng.integers(4))]
    v = CORNERS[near] / np.linalg.norm(CORNERS[near])
    # tilt the corner away from the line of sight, then spin the puzzle about the line of sight
    tilt = math.radians(rng.uniform(0, tilt_max))
    phi = rng.uniform(0, 2 * math.pi)
    target = np.array([math.sin(tilt) * math.cos(phi), math.sin(tilt) * math.sin(phi), math.cos(tilt)])
    Rm = _rotation_to(v, target)
    spin = rng.uniform(0, 2 * math.pi)
    Rz = np.array([[math.cos(spin), -math.sin(spin), 0], [math.sin(spin), math.cos(spin), 0], [0, 0, 1]])
    Rm = Rz @ Rm
    size_px = rng.uniform(50, 150) if far else rng.uniform(150, 420)
    dist = R.FOCAL * 1.6 * SCALE / size_px + SCALE
    lim = (0.45, 0.35) if far else (0.28, 0.2)
    t = (rng.uniform(-lim[0], lim[0]), rng.uniform(-lim[1], lim[1]))
    return near, R.Pose(Rm, (t[0] * dist, t[1] * dist, -dist))


def keypoints(pose, near):
    """The 4 corners in the picture (0 nearest, then clockwise from the highest) and their names."""
    outer = [c for c in 'ULRB' if c != near]
    p0 = pose.project(CORNERS[near] * SCALE)
    pts = {c: pose.project(CORNERS[c] * SCALE) for c in outer}
    ang = {c: math.atan2(pts[c][1] - p0[1], pts[c][0] - p0[0]) for c in outer}   # y down: increasing = clockwise
    first = min(outer, key=lambda c: pts[c][1])
    order = sorted(outer, key=lambda c: (ang[c] - ang[first]) % (2 * math.pi))
    names = [near] + order
    return np.float32([p0] + [pts[c] for c in order]), names


def valid_view(pose, near, min_facing=0.12):
    """The three faces around the near corner show, the fourth doesn't."""
    around = [f for f in FACES if OPPOSITE[f] != near]
    hidden = [f for f in FACES if OPPOSITE[f] == near][0]
    return min(visible(pose, f) for f in around) >= min_facing and visible(pose, hidden) < 0


def _sticker_poly(i, inset):
    tri = STICKERS[i][2]
    c = tri.mean(0)
    return c + (tri - c) * inset


def render(state, pose, rng, level='normal', style='stickered', bg_photo=None, hand='hand', background=None,
           out_mask=None):
    """background: a 640x480 picture to draw on exactly as it is (no crop, no drawn hand);
    out_mask: a list that receives the puzzle's silhouette (to put real fingers back on top)."""
    cfg = R.LEVELS[level]
    pal = palette(rng, style)
    img = background.astype(np.float32).copy() if background is not None else R.background(rng, bg_photo)
    holding = background is None and hand == 'hand' and rng.uniform() < 0.75
    corners2d = np.float32([pose.project(CORNERS[c] * SCALE) for c in 'ULRB'])
    if holding:
        _palm(img, corners2d, rng)
    if cfg.get('overhead'):
        light = np.array([rng.uniform(-0.3, 0.3), 1.0, rng.uniform(0.2, 0.7)])
    else:
        light = np.array([rng.uniform(-0.6, 0.6), rng.uniform(0.3, 1.0), rng.uniform(0.3, 1.0)])
    light /= np.linalg.norm(light)
    ambient = rng.uniform(*cfg['ambient'])
    body = rng.uniform(12, 40) if style == 'stickered' else rng.uniform(25, 60)
    inset = rng.uniform(0.72, 0.82) if style == 'stickered' else rng.uniform(0.86, 0.93)
    silhouette = np.zeros((R.H, R.W), np.uint8)
    for f in FACES:
        if visible(pose, f) <= 0:
            continue
        shade = ambient + (1 - ambient) * max(0.0, float((pose.R @ face_normal(f)) @ light))
        face_pts = np.int32([pose.project(CORNERS[c] * SCALE) * 16 for c in FACE_CORNERS[f]])
        cv2.fillConvexPoly(img, face_pts, tuple([body * shade] * 3), cv2.LINE_AA, shift=4)
        cv2.fillConvexPoly(silhouette, face_pts // 16, 1)
        for i, (sf, k, _) in enumerate(STICKERS):
            if sf != f:
                continue
            rgb = np.clip(pal[LETTER_TO_COLOR[state[i]]] + rng.normal(0, 4, 3), 0, 255) * shade
            poly = np.int32([pose.project(p * SCALE) * 16 for p in _sticker_poly(i, inset)])
            cv2.fillConvexPoly(img, poly, tuple(float(v) for v in rgb[::-1]), cv2.LINE_AA, shift=4)
        if rng.uniform() < cfg['glare_p'] / 2:
            ys, xs = np.nonzero(cv2.fillConvexPoly(np.zeros((R.H, R.W), np.uint8), face_pts // 16, 1))
            if len(xs):
                j = rng.integers(len(xs))
                blob = np.zeros((R.H, R.W), np.float32)
                cv2.ellipse(blob, (int(xs[j]), int(ys[j])), (int(rng.uniform(8, 30)), int(rng.uniform(5, 18))),
                            rng.uniform(0, 180), 0, 360, 1.0, -1)
                img += cv2.GaussianBlur(blob, (0, 0), rng.uniform(4, 9))[..., None] * 255 * rng.uniform(0.2, cfg['glare_max'])
    if out_mask is not None:
        out_mask.append(silhouette.copy())
    if background is None and (holding or rng.uniform() < cfg['hand_p']):
        R.add_fingers(img, silhouette, rng)
    session = R.new_session(rng, level)
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


def _palm(img, corners2d, rng):
    (cx, cy), radius = cv2.minEnclosingCircle(corners2d)
    angle = rng.uniform(-60, 60)
    d = np.array([math.sin(math.radians(angle)), math.cos(math.radians(angle))])
    centre = np.array([cx, cy]) + d * radius * rng.uniform(0.5, 0.9)
    col = tuple(float(v) for v in R.skin_tone(rng))
    cv2.ellipse(img, tuple(int(v) for v in centre), (int(radius * rng.uniform(0.7, 1.0)), int(radius * rng.uniform(0.9, 1.4))),
                angle, 0, 360, col, -1, cv2.LINE_AA)
    cv2.line(img, tuple(int(v) for v in centre), tuple(int(v) for v in centre + d * radius * 2.5), col,
             int(radius * 0.9), cv2.LINE_AA)


# ---- edge-on: an edge pointing at the camera, two whole faces in view (see pyra/view.py) ----------

def _axis_rot(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    if axis == 'x':
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'y':
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def edge_on_pose(rng, edge=None, tilt_max=30, spin_max=50, far=False, natural_p=0.5):
    """A random hold with edge (a, b) toward the camera, a above b on screen.
    Natural (natural_p of the time): standing on its base with the tip a up and corner b toward the
    camera, seen from 5-40 degrees above, as people hold it (~35 degrees off square edge-on).
    Otherwise: square edge-on tilted up to tilt_max degrees, the near edge within spin_max of upright."""
    a, b = edge or tuple(rng.choice(list('ULRB'), 2, replace=False))
    if rng.uniform() < natural_p:
        Rm = _rotation_to(-CORNERS[a] / np.linalg.norm(CORNERS[a]), np.array([0.0, -1.0, 0.0]))   # base down
        vb = Rm @ CORNERS[b]
        Rm = _axis_rot('y', -math.degrees(math.atan2(vb[0], vb[2])) + rng.uniform(-25, 25)) @ Rm  # b toward the camera
        Rm = _axis_rot('z', rng.uniform(-15, 15)) @ _axis_rot('x', rng.uniform(5, 40)) @ Rm      # seen from above, a little roll
    else:
        m = (CORNERS[a] + CORNERS[b]) / np.linalg.norm(CORNERS[a] + CORNERS[b])
        tilt = math.radians(rng.uniform(0, tilt_max))
        phi = rng.uniform(0, 2 * math.pi)
        target = np.array([math.sin(tilt) * math.cos(phi), math.sin(tilt) * math.sin(phi), math.cos(tilt)])
        Rm = _rotation_to(m, target)
        e = Rm @ (CORNERS[a] - CORNERS[b])
        spin = math.pi / 2 - math.atan2(e[1], e[0]) + math.radians(rng.uniform(-spin_max, spin_max))
        Rm = _axis_rot('z', math.degrees(spin)) @ Rm
    size_px = rng.uniform(50, 150) if far else rng.uniform(150, 420)
    dist = R.FOCAL * 1.6 * SCALE / size_px + SCALE
    lim = (0.45, 0.35) if far else (0.28, 0.2)
    t = (rng.uniform(-lim[0], lim[0]), rng.uniform(-lim[1], lim[1]))
    return (a, b), R.Pose(Rm, (t[0] * dist, t[1] * dist, -dist))


def edge_keypoints(pose, edge):
    """The 4 corners in the picture for an edge-on view: 0, 1 the near edge's ends (0 the higher),
    2 the far corner left of the line 0 -> 1 (cross product > 0, y down), 3 the other. And their names."""
    a, b = edge
    pa, pb = pose.project(CORNERS[a] * SCALE), pose.project(CORNERS[b] * SCALE)
    if pb[1] < pa[1]:
        (a, pa), (b, pb) = (b, pb), (a, pa)
    far = [c for c in 'ULRB' if c not in (a, b)]
    pts = {c: pose.project(CORNERS[c] * SCALE) for c in far}
    d = pb - pa
    cross = lambda c: d[0] * (pts[c][1] - pa[1]) - d[1] * (pts[c][0] - pa[0])   # noqa: E731
    left = max(far, key=cross)
    right = next(c for c in far if c != left)
    return np.float32([pa, pb, pts[left], pts[right]]), [a, b, left, right]


def valid_edge_view(pose, edge, min_facing=0.15, back_max=0.0):
    """The two faces on the near edge show, the other two don't (or barely: up to back_max, when it is
    seen from about level with its base)."""
    front = [f for f in FACES if OPPOSITE[f] not in edge]
    back = [f for f in FACES if OPPOSITE[f] in edge]
    return min(visible(pose, f) for f in front) >= min_facing and max(visible(pose, f) for f in back) < back_max
