"""Fast piece-tracking search used by the solver.

Tracking full 54-sticker CubeStates through a deep BFS is too slow (numpy
array allocation per node). Instead, precompute -- once, from the verified
move engine -- a per-move transition table for each of the 8 corner slots
and 12 edge slots: "whatever sits at position p, after this move, ends up at
position p' with orientation shifted by k". Search then operates on tuples
of (position, orientation) for just the handful of pieces a stage cares
about, with a visited-set BFS (dedup keeps the explored space bounded by the
reduced state space size, not by move-sequence branching).
"""

from .cube_state import solved_state
from .moves import ALL_MOVES, apply_move
from .validation import (
    CORNER_POSITIONS, EDGE_POSITIONS, _CORNER_SLOT_BY_LETTERS, _EDGE_SLOT_BY_LETTERS,
    _SOLVED_ARR, _rotations, corner_facelet_indices, edge_facelet_indices,
)


def _build_table(positions, facelet_fn, slot_by_letters):
    solved = solved_state()
    table = {}
    for move in ALL_MOVES:
        after = apply_move(solved, move)
        mapping = {}
        for p in positions:
            idxs = facelet_fn(p)
            observed = tuple(after.arr[i] for i in idxs)
            q = slot_by_letters[frozenset(observed)]
            home_tuple = tuple(_SOLVED_ARR[i] for i in facelet_fn(q))
            k = _rotations(home_tuple).index(observed)
            mapping[q] = (p, k)
        table[move] = mapping
    return table


CORNER_TABLE = _build_table(CORNER_POSITIONS, corner_facelet_indices, _CORNER_SLOT_BY_LETTERS)
EDGE_TABLE = _build_table(EDGE_POSITIONS, edge_facelet_indices, _EDGE_SLOT_BY_LETTERS)


def analyze(state, positions, facelet_fn, slot_by_letters):
    """For a real CubeState, find each home slot's current (position, orientation)."""
    result = {}
    for p in positions:
        idxs = facelet_fn(p)
        observed = tuple(state.arr[i] for i in idxs)
        q = slot_by_letters[frozenset(observed)]
        home_tuple = tuple(_SOLVED_ARR[i] for i in facelet_fn(q))
        k = _rotations(home_tuple).index(observed)
        result[q] = (p, k)
    return result


def analyze_corners(state):
    return analyze(state, CORNER_POSITIONS, corner_facelet_indices, _CORNER_SLOT_BY_LETTERS)


def analyze_edges(state):
    return analyze(state, EDGE_POSITIONS, edge_facelet_indices, _EDGE_SLOT_BY_LETTERS)


_INV_SUFFIX = {'': "'", "'": '', '2': '2'}


def _inverse_move(move):
    return move[0] + _INV_SUFFIX[move[1:]]


def find_moves(pieces, allowed_moves, max_depth):
    """pieces: list of (is_edge, home, current_pos, current_ori). Returns the
    shortest move list (from allowed_moves) that brings every piece to
    (home, 0), or None if none exists within max_depth.

    Bidirectional BFS: a plain single-direction search's cost is dominated by
    branching^depth. Meeting a forward search (from the scrambled state) with
    a backward search (from the goal, walked via inverse moves) needs only
    two independent branching^(depth/2) searches, which is what keeps this
    fast even when many pieces are tracked at once (e.g. most of a stage
    already locked in) and the true solution is 6-8 moves deep."""
    tables = [EDGE_TABLE if is_edge else CORNER_TABLE for is_edge, *_ in pieces]
    mods = [2 if is_edge else 3 for is_edge, *_ in pieces]
    start = tuple((pos, ori) for _, _, pos, ori in pieces)
    goal = tuple((home, 0) for _, home, _, _ in pieces)
    if start == goal:
        return []

    def transition(state, move):
        return tuple(
            (tables[i][move][pos][0], (ori + tables[i][move][pos][1]) % mods[i])
            for i, (pos, ori) in enumerate(state)
        )

    inverses = {m: _inverse_move(m) for m in allowed_moves}
    path_f = {start: []}
    path_b = {goal: []}
    frontier_f = [start]
    frontier_b = [goal]

    for _ in range(max_depth):
        if not frontier_f and not frontier_b:
            return None

        next_f = []
        for s in frontier_f:
            for move in allowed_moves:
                ns = transition(s, move)
                if ns in path_b:
                    return path_f[s] + [move] + path_b[ns]
                if ns not in path_f:
                    path_f[ns] = path_f[s] + [move]
                    next_f.append(ns)
        frontier_f = next_f

        next_b = []
        for s in frontier_b:
            for move in allowed_moves:
                pred = transition(s, inverses[move])
                if pred in path_f:
                    return path_f[pred] + [move] + path_b[s]
                if pred not in path_b:
                    path_b[pred] = [move] + path_b[s]
                    next_b.append(pred)
        frontier_b = next_b

    return None
