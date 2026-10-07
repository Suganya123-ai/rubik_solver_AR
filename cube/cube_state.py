import numpy as np

FACES = ['U', 'R', 'F', 'D', 'L', 'B']
FACE_OFFSET = {f: i * 9 for i, f in enumerate(FACES)}
CENTER_INDEX = {f: FACE_OFFSET[f] + 4 for f in FACES}

OPPOSITE_FACE = {'U': 'D', 'D': 'U', 'L': 'R', 'R': 'L', 'F': 'B', 'B': 'F'}

# The engine's internal sticker alphabet is the face letters themselves
# (a solved cube has every sticker on face X labeled 'X'). This keeps the
# engine agnostic to any real-world color scheme: translating a physical
# scan's color names to this face-letter alphabet (via each face's scanned
# center color) is a one-time step done at the API boundary, not here.
# See color_detect.py / validation.py for that translation.


def flat_index(face, r, c):
    return FACE_OFFSET[face] + r * 3 + c


def solved_array():
    arr = np.empty(54, dtype='<U1')
    for f in FACES:
        arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9] = f
    return arr


class CubeState:
    __slots__ = ('arr',)

    def __init__(self, arr):
        self.arr = arr

    def face(self, f):
        o = FACE_OFFSET[f]
        return self.arr[o:o + 9]

    def sticker(self, face, r, c):
        return self.arr[flat_index(face, r, c)]

    def as_dict(self):
        return {f: self.face(f).reshape(3, 3).copy() for f in FACES}

    def copy(self):
        return CubeState(self.arr.copy())

    def __eq__(self, other):
        return isinstance(other, CubeState) and np.array_equal(self.arr, other.arr)

    def __repr__(self):
        rows = []
        for f in FACES:
            rows.append(f"{f}: {''.join(self.face(f))}")
        return " | ".join(rows)


def solved_state():
    return CubeState(solved_array())
