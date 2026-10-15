"""Exact 3D layout of the Pyraminx, shared by the solver, the renderer and the camera code.

A regular tetrahedron centred on the origin, one corner straight up:
    U (top), L (front-left), R (front-right), B (back)   -- the four corners
    F (front), L, R, D (down)                           -- the four faces, each named after
                                                           the corner it does NOT touch:
    face F is opposite corner B, L opposite R, R opposite L, D opposite U.
WCA colours: F green, R blue, L red, D yellow.

Each face has 9 small triangles ("stickers"), numbered face*9 + k:
    k 0-2  tips      (the corner triangles at the face's corners c0, c1, c2)
    k 3-5  centres   (axial pieces: the downward triangles next to c0, c1, c2)
    k 6-8  edges     (the triangles on the sides c0-c1, c1-c2, c2-c0)
A face's corners c0, c1, c2 run counter-clockwise seen from outside.

Moves (WCA notation): U L R B turn the two layers at that corner (tip and the
layer under it) 120 degrees clockwise, seen looking at the corner from
outside; u l r b turn only the tip; ' is anticlockwise.
"""
import numpy as np

_r = np.sqrt(8) / 3
CORNERS = {
    'U': np.array([0.0, 1.0, 0.0]),
    'L': np.array([-_r * np.sin(np.pi / 3), -1 / 3, _r * np.cos(np.pi / 3)]),
    'R': np.array([_r * np.sin(np.pi / 3), -1 / 3, _r * np.cos(np.pi / 3)]),
    'B': np.array([0.0, -1 / 3, -_r]),
}
OPPOSITE = {'F': 'B', 'L': 'R', 'R': 'L', 'D': 'U'}   # face -> the corner it doesn't touch
FACES = ('F', 'R', 'L', 'D')
COLOURS = {'F': 'green', 'R': 'blue', 'L': 'red', 'D': 'yellow'}


def _face_corners(face):
    names = [c for c in 'ULRB' if c != OPPOSITE[face]]
    a, b, c = (CORNERS[n] for n in names)
    if np.dot(np.cross(b - a, c - a), (a + b + c)) < 0:   # make them anticlockwise seen from outside
        names[1], names[2] = names[2], names[1]
    # start from the top-most corner (U if on the face), for a fixed, readable order
    start = names.index('U') if 'U' in names else int(np.argmax([CORNERS[n][2] for n in names]))
    return names[start:] + names[:start]


FACE_CORNERS = {f: _face_corners(f) for f in FACES}   # e.g. F: ['U', 'L', 'R']


def _bary(face, w):
    """3D point from barycentric weights (w0, w1, w2) over the face's corners."""
    c = [CORNERS[n] for n in FACE_CORNERS[face]]
    return (w[0] * c[0] + w[1] * c[1] + w[2] * c[2]) / sum(w)


def _sticker_triangles(face):
    """The 9 small triangles of a face as barycentric corner triples (on the 3-step grid)."""
    up = lambda i, j, k: [(i + 1, j, k), (i, j + 1, k), (i, j, k + 1)]      # noqa: E731
    down = lambda i, j, k: [(i, j + 1, k + 1), (i + 1, j, k + 1), (i + 1, j + 1, k)]   # noqa: E731
    tips = [up(2, 0, 0), up(0, 2, 0), up(0, 0, 2)]
    centres = [down(1, 0, 0), down(0, 1, 0), down(0, 0, 1)]
    edges = [up(1, 1, 0), up(0, 1, 1), up(1, 0, 1)]
    return tips + centres + edges


# STICKERS[i] = (face, k, 3x3 array of the triangle's corners in 3D)
STICKERS = []
BARY = {}   # (face, k) -> 3 barycentric points (for reading a face from its picture)
for _f in FACES:
    for _k, _tri in enumerate(_sticker_triangles(_f)):
        STICKERS.append((_f, _k, np.array([_bary(_f, w) for w in _tri])))
        BARY[(_f, _k)] = np.array(_tri, float) / 3
CENTROIDS = np.array([t.mean(0) for _, _, t in STICKERS])
TIP_STICKERS = [i for i, (_, k, _) in enumerate(STICKERS) if k < 3]


def _rotation(axis, angle):
    a = axis / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K


def _move_permutation(corner, layers):
    """perm such that new_state[i] = state[perm[i]] for a clockwise turn of `layers` (1 tip, 2 tip+layer)."""
    v = CORNERS[corner]
    height = np.linalg.norm(v) * 4 / 3            # corner to the opposite face
    depth = np.array([np.dot(v - p, v / np.linalg.norm(v)) for p in CENTROIDS]) / height
    turning = depth < layers / 3 - 1e-6
    rot = _rotation(v, -2 * np.pi / 3)            # clockwise looking at the corner from outside
    perm = np.arange(len(STICKERS))
    for src in np.nonzero(turning)[0]:
        moved = rot @ CENTROIDS[src]
        dest = int(np.argmin(np.linalg.norm(CENTROIDS - moved, axis=1)))
        assert np.linalg.norm(CENTROIDS[dest] - moved) < 1e-6
        perm[dest] = src
    return perm


MOVES = {}
for _c in 'ULRB':
    for _name, _layers in ((_c, 2), (_c.lower(), 1)):
        p = _move_permutation(_c, _layers)
        MOVES[_name] = p
        MOVES[_name + "'"] = p[p]            # anticlockwise = two clockwise turns
MAIN_MOVES = [m for m in MOVES if m[0].isupper()]
TIP_MOVES = [m for m in MOVES if m[0].islower()]
