import numpy as np

from .cube_state import CENTER_INDEX, FACES, CubeState, flat_index

# Each sticker is (cubie_pos, facelet_dir): cubie_pos in {-1,0,1}^3 identifies
# which of the 26 non-center cubies it belongs to, facelet_dir is the unit
# axis vector the sticker is glued to (matching one nonzero coordinate of the
# cubie). Axes: +x=R, -x=L, +y=U, -y=D, +z=F, -z=B.

FACELET_DIR = {'U': (0, 1, 0), 'D': (0, -1, 0), 'F': (0, 0, 1), 'B': (0, 0, -1), 'R': (1, 0, 0), 'L': (-1, 0, 0)}


def _grid_cubie_pos(face, r, c):
    """cubie_pos for grid cell (r,c) on `face`, viewed head-on from outside
    that face. Derived from a consistent right-handed screen convention
    (right x up = outward normal) verified independently for all 6 faces."""
    if face == 'U':
        return (c - 1, 1, r - 1)
    if face == 'D':
        return (c - 1, -1, 1 - r)
    if face == 'F':
        return (c - 1, 1 - r, 1)
    if face == 'B':
        return (1 - c, 1 - r, -1)
    if face == 'R':
        return (1, 1 - r, 1 - c)
    if face == 'L':
        return (-1, 1 - r, c - 1)
    raise ValueError(face)


def _build_position_table():
    """(cubie_pos, facelet_dir) -> flat index, and the reverse, for all 54 stickers."""
    pos_to_index = {}
    index_to_pos = {}
    for face in FACES:
        for r in range(3):
            for c in range(3):
                idx = flat_index(face, r, c)
                cp = _grid_cubie_pos(face, r, c)
                fd = FACELET_DIR[face]
                pos_to_index[(cp, fd)] = idx
                index_to_pos[idx] = (cp, fd)
    return pos_to_index, index_to_pos


POS_TO_INDEX, INDEX_TO_POS = _build_position_table()

# 90-degree rotation of (x,y,z), clockwise as viewed by someone standing
# outside that face looking at it (the physical turning convention).
# Derived from the screen convention (right x up = outward normal) for each
# face and cross-checked with an explicit "does the top edge move to the
# right edge" (12 o'clock -> 3 o'clock, i.e. clockwise) sanity check.
_ROTATE = {
    'U': lambda x, y, z: (-z, y, x),
    'D': lambda x, y, z: (z, y, -x),
    'F': lambda x, y, z: (y, -x, z),
    'B': lambda x, y, z: (-y, x, z),
    'R': lambda x, y, z: (x, z, -y),
    'L': lambda x, y, z: (x, -z, y),
}

# Which axis (0=x,1=y,2=z) and layer value identifies the 9 cubies affected
# by turning this face (its own layer, i.e. the face plus the touching ring).
_LAYER = {
    'U': (1, 1), 'D': (1, -1),
    'F': (2, 1), 'B': (2, -1),
    'R': (0, 1), 'L': (0, -1),
}


def _build_move_perm(face):
    axis, layer_value = _LAYER[face]
    rotate = _ROTATE[face]
    perm = list(range(54))
    for j in range(54):
        cp, fd = INDEX_TO_POS[j]
        if cp[axis] != layer_value:
            continue
        cp2 = rotate(*cp)
        fd2 = rotate(*fd)
        i = POS_TO_INDEX[(cp2, fd2)]
        perm[i] = j
    return np.array(perm, dtype=np.int64)


def _invert_perm(p):
    inv = np.empty_like(p)
    inv[p] = np.arange(len(p))
    return inv


MOVES = {f: _build_move_perm(f) for f in 'URFDLB'}
INV_MOVES = {f: _invert_perm(MOVES[f]) for f in 'URFDLB'}

ALL_MOVES = [f + s for f in 'URFDLB' for s in ('', "'", '2')]


def apply_move(state, move):
    base = move[0]
    suffix = move[1:]
    arr = state.arr
    if suffix == '':
        arr = arr[MOVES[base]]
    elif suffix == "'":
        arr = arr[INV_MOVES[base]]
    elif suffix == '2':
        arr = arr[MOVES[base]][MOVES[base]]
    else:
        raise ValueError(f"bad move {move!r}")
    return CubeState(arr)


def apply_moves(state, moves):
    for m in moves:
        state = apply_move(state, m)
    return state


def center_color(state, face):
    return state.arr[CENTER_INDEX[face]]
