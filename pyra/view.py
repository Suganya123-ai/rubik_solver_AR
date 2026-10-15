"""From the camera's 4 corner points to stickers.

A corner-on view shows the three faces around the corner nearest the camera.
Keypoints (see bench/render_pyra.py): 0 the near corner, 1-3 the outer corners
clockwise on screen from the highest. The three faces in the picture are
    view face 0: (k0, k1, k2)   view face 1: (k0, k2, k3)   view face 2: (k0, k3, k1)
and each is read as 9 stickers in the face's own layout with its corners in
that order (tips at k0, a, b; centres next to them; edges k0-a, a-b, b-k0).

A "hold" says which physical corner is where: the near corner and the one at
k1 (the other two follow, clockwise). There are 12 holds (the tetrahedron's
rotations). For each, `view_stickers(hold)` lists which physical sticker each
of the 27 picture stickers is.
"""
import itertools

import cv2
import numpy as np

from .geometry import CORNERS, FACE_CORNERS, FACES, STICKERS

VIEW_FACES = ((0, 1, 2), (0, 2, 3), (0, 3, 1))
_LOCAL = {}   # sticker k on a face with corners (p, q, r) -> its barycentric triangle (shared with geometry's layout)


def _local_layout():
    up = lambda i, j, k: [(i + 1, j, k), (i, j + 1, k), (i, j, k + 1)]      # noqa: E731
    down = lambda i, j, k: [(i, j + 1, k + 1), (i + 1, j, k + 1), (i + 1, j + 1, k)]   # noqa: E731
    tris = [up(2, 0, 0), up(0, 2, 0), up(0, 0, 2), down(1, 0, 0), down(0, 1, 0), down(0, 0, 1),
            up(1, 1, 0), up(0, 1, 1), up(1, 0, 1)]
    return [np.array(t, float) / 3 for t in tris]


LAYOUT = _local_layout()


def clockwise_from_outside(near):
    """The other three corners in clockwise order, seen looking at `near` from outside."""
    v = CORNERS[near] / np.linalg.norm(CORNERS[near])
    e1 = np.cross(v, [0.3, 1.0, 0.2])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(v, e1)
    outer = [c for c in 'ULRB' if c != near]
    ang = {c: np.arctan2(np.dot(CORNERS[c], e2), np.dot(CORNERS[c], e1)) for c in outer}
    # right-handed (e1, e2, v): increasing angle is anticlockwise seen from outside
    return sorted(outer, key=lambda c: -ang[c])


def holds():
    """All 12 holds as corner-name lists [near, at k1, at k2, at k3]."""
    out = []
    for near in 'ULRB':
        cw = clockwise_from_outside(near)
        for s in range(3):
            out.append([near] + cw[s:] + cw[:s])
    return out


HOLDS = holds()


def _physical_sticker(corner_names):
    """For a picture face whose corners are physical corners (p, q, r): picture sticker k -> physical index."""
    p, q, r = corner_names
    face = next(f for f in FACES if set(FACE_CORNERS[f]) == {p, q, r})
    fc = FACE_CORNERS[face]
    pos = {n: fc.index(n) for n in (p, q, r)}
    sides = {frozenset((fc[0], fc[1])): 6, frozenset((fc[1], fc[2])): 7, frozenset((fc[2], fc[0])): 8}
    base = FACES.index(face) * 9
    return [base + pos[p], base + pos[q], base + pos[r],
            base + 3 + pos[p], base + 3 + pos[q], base + 3 + pos[r],
            base + sides[frozenset((p, q))], base + sides[frozenset((q, r))], base + sides[frozenset((r, p))]]


def view_stickers(hold):
    """27 physical sticker indices for the picture stickers (view face 0's 9, then 1's, then 2's)."""
    out = []
    for vf in VIEW_FACES:
        out += _physical_sticker([hold[i] for i in vf])
    return out


HOLD_STICKERS = [view_stickers(h) for h in HOLDS]


def sticker_polygons(kpts, shrink=0.5):
    """27 image triangles (the middle part of each sticker, `shrink` of its size) from the 4 corner points."""
    k = np.asarray(kpts, float)
    polys = []
    for vf in VIEW_FACES:
        P = k[list(vf)]
        for tri in LAYOUT:
            pts = tri @ P
            c = pts.mean(0)
            polys.append(c + (pts - c) * shrink)
    return polys


def read_stickers(frame, kpts, shrink=0.5):
    """frame: BGR. Returns 27 (r, g, b) medians (None where off the picture), in view_stickers order."""
    h, w = frame.shape[:2]
    out = []
    for poly in sticker_polygons(kpts, shrink):
        x0, y0 = np.floor(poly.min(0)).astype(int)
        x1, y1 = np.ceil(poly.max(0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
        if x1 - x0 < 2 or y1 - y0 < 2:
            out.append(None)
            continue
        mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillConvexPoly(mask, np.round(poly - [x0, y0]).astype(np.int32), 255)
        px = frame[y0:y1, x0:x1][mask > 0]
        if len(px) == 0:
            out.append(None)
            continue
        b, g, r = np.median(px, axis=0)
        out.append((float(r), float(g), float(b)))
    return out


def face_share(kpts):
    """Smallest picture face's area over the largest's (1 = held squarely corner-on)."""
    k = np.asarray(kpts, float)

    def area(idx):
        q = k[list(idx)]
        (ax, ay), (bx, by) = q[1] - q[0], q[2] - q[0]
        return abs(ax * by - ay * bx) / 2
    a = [area(vf) for vf in VIEW_FACES]
    return min(a) / max(max(a), 1e-9)


__all__ = ['HOLDS', 'HOLD_STICKERS', 'VIEW_FACES', 'clockwise_from_outside', 'face_share', 'read_stickers',
           'sticker_polygons', 'view_stickers', 'itertools']


def frame_permutation(rename):
    """Sticker permutation between two namings of the corners. rename: {corner in frame A: corner in frame B}.
    Returns P with stateB[P[i]] = stateA[i] (sticker i in A is sticker P[i] in B)."""
    out = []
    for i, (f, k, _) in enumerate(STICKERS):
        fc = FACE_CORNERS[f]
        names = [rename[c] for c in fc]
        g = next(x for x in FACES if set(FACE_CORNERS[x]) == set(names))
        gc = FACE_CORNERS[g]
        base = FACES.index(g) * 9
        if k < 6:
            out.append(base + (k // 3) * 3 + gc.index(names[k % 3]))
        else:
            a, b = names[k - 6], names[(k - 6 + 1) % 3]
            sides = {frozenset((gc[0], gc[1])): 6, frozenset((gc[1], gc[2])): 7, frozenset((gc[2], gc[0])): 8}
            out.append(base + sides[frozenset((a, b))])
    return np.array(out)
