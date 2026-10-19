from collections import Counter, namedtuple

import numpy as np

from .cube_state import FACE_OFFSET, FACES, OPPOSITE_FACE, CubeState, solved_state
from .moves import POS_TO_INDEX

ValidationResult = namedtuple('ValidationResult', ['ok', 'error_code', 'message', 'details'])

CORNER_POSITIONS = [(sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
EDGE_POSITIONS = (
    [(sx, sy, 0) for sx in (-1, 1) for sy in (-1, 1)]
    + [(sx, 0, sz) for sx in (-1, 1) for sz in (-1, 1)]
    + [(0, sy, sz) for sy in (-1, 1) for sz in (-1, 1)]
)


def corner_facelet_indices(p):
    """3 facelet indices for corner `p`, in a fixed clockwise-as-viewed-from-
    outside order. The raw (x,y,z) axis order is clockwise for one of the two
    corner "checkerboard" parity classes and mirrored for the other (a
    standard fact about cube corner chirality), so it's flipped for
    odd-parity corners to keep the order consistently clockwise everywhere --
    required for orientation to reduce to a simple cyclic-rotation check."""
    sx, sy, sz = p
    x_i, y_i, z_i = POS_TO_INDEX[(p, (sx, 0, 0))], POS_TO_INDEX[(p, (0, sy, 0))], POS_TO_INDEX[(p, (0, 0, sz))]
    if sx * sy * sz == 1:
        return (x_i, y_i, z_i)
    return (x_i, z_i, y_i)


def edge_facelet_indices(p):
    sx, sy, sz = p
    dirs = []
    if sx != 0:
        dirs.append((sx, 0, 0))
    if sy != 0:
        dirs.append((0, sy, 0))
    if sz != 0:
        dirs.append((0, 0, sz))
    return tuple(POS_TO_INDEX[(p, d)] for d in dirs)


def _slot_letters(indices, arr):
    return frozenset(arr[i] for i in indices)


_SOLVED_ARR = solved_state().arr
_CORNER_SLOT_BY_LETTERS = {_slot_letters(corner_facelet_indices(p), _SOLVED_ARR): p for p in CORNER_POSITIONS}
_EDGE_SLOT_BY_LETTERS = {_slot_letters(edge_facelet_indices(p), _SOLVED_ARR): p for p in EDGE_POSITIONS}


def _rotations(t):
    n = len(t)
    return [tuple(t[(i + k) % n] for i in range(n)) for k in range(n)]


def _permutation_parity(perm):
    n = len(perm)
    visited = [False] * n
    parity = 0
    for i in range(n):
        if visited[i]:
            continue
        length = 0
        k = i
        while not visited[k]:
            visited[k] = True
            k = perm[k]
            length += 1
        parity += length - 1
    return parity % 2


def validate_colors(color_grid):
    """Tier 1: 9-of-each-color + 6 distinct centers. `color_grid` maps each
    face letter to a list of 9 color-name strings from the scan."""
    all_colors = [c for f in FACES for c in color_grid[f]]
    counts = Counter(all_colors)
    if len(counts) != 6 or any(v != 9 for v in counts.values()):
        return ValidationResult(False, 'ERROR_COLOR_COUNT',
                                 f"Expected exactly 9 stickers of each of 6 colors, got: {dict(counts)}. "
                                 f"Re-scan the face(s) that look off.",
                                 {'counts': dict(counts)})
    centers = {f: color_grid[f][4] for f in FACES}
    if len(set(centers.values())) != 6:
        return ValidationResult(False, 'ERROR_DUPLICATE_CENTER',
                                 f"Two faces were scanned with the same center color: {centers}. Re-scan.",
                                 {'centers': centers})
    color_to_face = {v: k for k, v in centers.items()}
    return ValidationResult(True, None, "ok", {'color_to_face': color_to_face, 'centers': centers})


def translate_to_face_letters(color_grid, color_to_face):
    arr = np.empty(54, dtype='<U1')
    for f in FACES:
        for i, col in enumerate(color_grid[f]):
            arr[FACE_OFFSET[f] + i] = color_to_face[col]
    return CubeState(arr)


def validate_piece_legality(state):
    """Tier 2: every corner/edge slot must hold a physically legal cubie
    (distinct, mutually-adjacent face letters -- no duplicates, no opposites)."""
    for p in CORNER_POSITIONS:
        idxs = corner_facelet_indices(p)
        letters = [state.arr[i] for i in idxs]
        if len(set(letters)) != 3:
            return ValidationResult(False, 'ERROR_BAD_CORNER',
                                     f"A corner has a repeated color: {letters}. Re-scan.", {'letters': letters})
        for a in letters:
            for b in letters:
                if a != b and OPPOSITE_FACE[a] == b:
                    return ValidationResult(False, 'ERROR_BAD_CORNER',
                                             f"A corner has two opposite colors together: {letters}. Re-scan.",
                                             {'letters': letters})
    for p in EDGE_POSITIONS:
        idxs = edge_facelet_indices(p)
        letters = [state.arr[i] for i in idxs]
        if len(set(letters)) != 2:
            return ValidationResult(False, 'ERROR_BAD_EDGE',
                                     f"An edge has a repeated color: {letters}. Re-scan.", {'letters': letters})
        if OPPOSITE_FACE[letters[0]] == letters[1]:
            return ValidationResult(False, 'ERROR_BAD_EDGE',
                                     f"An edge has two opposite colors together: {letters}. Re-scan.",
                                     {'letters': letters})
    return ValidationResult(True, None, "ok", {})


def validate_parity(state):
    """Tier 3: group-theory parity/orientation invariants that any legally
    scrambled cube must satisfy."""
    corner_perm = []
    corner_orientation_sum = 0
    for p in CORNER_POSITIONS:
        idxs = corner_facelet_indices(p)
        observed = tuple(state.arr[i] for i in idxs)
        home = _CORNER_SLOT_BY_LETTERS.get(frozenset(observed))
        if home is None:
            return ValidationResult(False, 'ERROR_BAD_CORNER',
                                     f"Corner colors {observed} don't match any legal cubie.", {})
        corner_perm.append(CORNER_POSITIONS.index(home))
        home_idxs = corner_facelet_indices(home)
        home_triple = tuple(_SOLVED_ARR[i] for i in home_idxs)
        k = _rotations(home_triple).index(observed) if observed in _rotations(home_triple) else None
        if k is None:
            return ValidationResult(False, 'ERROR_BAD_CORNER',
                                     f"Corner {observed} is a mirror image of a legal cubie (impossible).", {})
        corner_orientation_sum += k

    edge_perm = []
    edge_orientation_sum = 0
    for p in EDGE_POSITIONS:
        idxs = edge_facelet_indices(p)
        observed = tuple(state.arr[i] for i in idxs)
        home = _EDGE_SLOT_BY_LETTERS.get(frozenset(observed))
        if home is None:
            return ValidationResult(False, 'ERROR_BAD_EDGE',
                                     f"Edge colors {observed} don't match any legal cubie.", {})
        edge_perm.append(EDGE_POSITIONS.index(home))
        home_idxs = edge_facelet_indices(home)
        home_pair = tuple(_SOLVED_ARR[i] for i in home_idxs)
        k = _rotations(home_pair).index(observed) if observed in _rotations(home_pair) else None
        if k is None:
            return ValidationResult(False, 'ERROR_BAD_EDGE',
                                     f"Edge {observed} is a mirror image of a legal cubie (impossible).", {})
        edge_orientation_sum += k

    corner_parity = _permutation_parity(corner_perm)
    edge_parity = _permutation_parity(edge_perm)
    if corner_parity != edge_parity:
        return ValidationResult(False, 'ERROR_PARITY',
                                 "Corner and edge permutation parity don't match -- this cube state is "
                                 "physically impossible (likely two stickers were swapped during scanning). "
                                 "Re-scan.", {})
    if corner_orientation_sum % 3 != 0:
        return ValidationResult(False, 'ERROR_CORNER_TWIST',
                                 "A corner appears twisted independently of the others -- this can't happen "
                                 "on a real cube. Re-scan.", {})
    if edge_orientation_sum % 2 != 0:
        return ValidationResult(False, 'ERROR_EDGE_FLIP',
                                 "A single edge appears flipped independently of the others -- this can't "
                                 "happen on a real cube. Re-scan.", {})
    return ValidationResult(True, None, "ok", {})


def validate_scan(color_grid):
    """Full pipeline: raw scanned colors -> (CubeState in face-letter alphabet, ValidationResult).
    Returns (None, result) if any tier fails."""
    r1 = validate_colors(color_grid)
    if not r1.ok:
        return None, r1
    state = translate_to_face_letters(color_grid, r1.details['color_to_face'])
    r2 = validate_piece_legality(state)
    if not r2.ok:
        return None, r2
    r3 = validate_parity(state)
    if not r3.ok:
        return None, r3
    return state, ValidationResult(True, None, "ok", {})


def validate(state):
    """Validate an already-translated (face-letter alphabet) CubeState -- tiers 2+3 only."""
    r2 = validate_piece_legality(state)
    if not r2.ok:
        return r2
    return validate_parity(state)
