"""Corner points in the order each model was trained with, worked out from the picture alone, so a
label never depends on the order a model happened to output them in.

Cube (7 points, bench/render.py CORNER_KPTS): 0 the near corner (inside the hexagon), then the
outer six clockwise on screen, starting so that 0-1-2-3 is the top face (the highest of the three
faces): 1 front-left-top, 2 back-left-top, 3 back-right-top, 4 back-right-bottom, 5 front-right-bottom,
6 front-left-bottom.
Pyraminx corner-on (4): 0 the near corner (inside the triangle), then the outer three clockwise from
the highest. Edge-on (4): 0, 1 the near edge's ends (which two: the model's call, from how it looks;
0 the higher), 2 the far corner left of the line 0 -> 1, 3 the other.
"""
import numpy as np


def _clockwise_from(pts, centre):
    """Indices of pts sorted clockwise on screen (y down) around centre."""
    ang = np.arctan2(pts[:, 1] - centre[1], pts[:, 0] - centre[0])
    return list(np.argsort(ang))


def _inner(pts):
    """Index of the near corner: the one point not on the outline (convex hull); if none or several
    are inside, the one deepest inside (closest to the middle of the others)."""
    import cv2
    hull = set(cv2.convexHull(np.float32(pts), returnPoints=False).ravel().tolist())
    inside = [i for i in range(len(pts)) if i not in hull]
    if len(inside) == 1:
        return inside[0]
    cand = inside or range(len(pts))
    return int(min(cand, key=lambda i: np.linalg.norm(pts[i] - np.delete(pts, i, 0).mean(0))))


def cube(k):
    """k: 7 points in the model's own order. Which outer corners pair up into faces is the model's
    call, and so is the near corner (a wrong pairing or near corner reads stickers across faces, which
    matches no cube: the colour check rejects it); here the ring is made clockwise and turned
    (by whole faces) so that the highest face is 0-1-2-3. None if the ring is not a clockwise or
    anticlockwise loop around the near corner (a broken detection)."""
    k = np.asarray(k, float)
    i0 = 0   # the model's near corner (close up, perspective can put another corner inside the outline)
    ring = list(range(1, 7))
    ang = np.unwrap([np.arctan2(k[i][1] - k[i0][1], k[i][0] - k[i0][0]) for i in ring + ring[:1]])
    turn = ang[-1] - ang[0]
    if abs(abs(turn) - 2 * np.pi) > 0.5:
        return None
    if turn < 0:   # anticlockwise on screen: reverse, keeping ring[0]
        ring = ring[:1] + ring[1:][::-1]
    r = min((0, 2, 4), key=lambda s: np.mean([k[ring[(s + j) % 6]][1] for j in range(3)]))
    return k[[i0] + [ring[(r + j) % 6] for j in range(6)]]


def pyra_corner(k):
    k = np.asarray(k, float)
    i0 = _inner(k)
    outer = [i for i in range(4) if i != i0]
    ring = [outer[j] for j in _clockwise_from(k[outer], k[i0])]
    top = min(range(3), key=lambda s: k[ring[s]][1])
    return k[[i0] + [ring[(top + j) % 3] for j in range(3)]]


def pyra_edge(k):
    k = np.asarray(k, float)
    a, b = (0, 1) if k[0][1] <= k[1][1] else (1, 0)
    d = k[b] - k[a]
    cross = lambda i: d[0] * (k[i][1] - k[a][1]) - d[1] * (k[i][0] - k[a][0])   # noqa: E731
    left, right = sorted((2, 3), key=cross, reverse=True)
    return k[[a, b, left, right]]


def pyra(k, kind):
    return pyra_edge(k) if kind == 'edge' else pyra_corner(k)
