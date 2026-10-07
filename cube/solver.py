from collections import deque
from dataclasses import dataclass

from .cube_state import solved_state
from .fast_search import analyze_corners, analyze_edges, find_moves
from .moves import ALL_MOVES, apply_moves
from .validation import POS_TO_INDEX, validate


class SolverError(Exception):
    pass


# ---------------------------------------------------------------------------
# Generic per-slot helpers: does slot p currently show the letters it would
# show in a solved cube? This works for ANY position (cross, corner, middle
# edge, last layer) without needing to track "which piece is this" -- if the
# right letters are in the right slot in the right orientation, it's solved.
# ---------------------------------------------------------------------------

def edge_indices_by_axis(p):
    sx, sy, sz = p
    d = {}
    if sx != 0:
        d['x'] = POS_TO_INDEX[(p, (sx, 0, 0))]
    if sy != 0:
        d['y'] = POS_TO_INDEX[(p, (0, sy, 0))]
    if sz != 0:
        d['z'] = POS_TO_INDEX[(p, (0, 0, sz))]
    return d


def corner_indices_by_axis(p):
    sx, sy, sz = p
    return {'x': POS_TO_INDEX[(p, (sx, 0, 0))], 'y': POS_TO_INDEX[(p, (0, sy, 0))], 'z': POS_TO_INDEX[(p, (0, 0, sz))]}


def letters_by_axis(p):
    sx, sy, sz = p
    d = {}
    if sx != 0:
        d['x'] = 'R' if sx == 1 else 'L'
    if sy != 0:
        d['y'] = 'U' if sy == 1 else 'D'
    if sz != 0:
        d['z'] = 'F' if sz == 1 else 'B'
    return d


def piece_is_solved(state, p, is_edge):
    idxs = edge_indices_by_axis(p) if is_edge else corner_indices_by_axis(p)
    expect = letters_by_axis(p)
    return all(state.arr[idxs[k]] == expect[k] for k in idxs)


def edge_oriented(state, p):
    """Is the up-facing sticker of whatever edge currently sits at last-layer
    slot p showing 'U'? (Its position/slot may still be wrong.)"""
    return state.arr[edge_indices_by_axis(p)['y']] == 'U'


def corner_oriented(state, p):
    """Is the up-facing sticker of whatever corner currently sits at
    last-layer slot p showing 'U'? (Assumes position is already correct --
    checked separately by corner_position_ok -- so this only measures twist.)"""
    return state.arr[corner_indices_by_axis(p)['y']] == 'U'


def corner_position_ok(state, p):
    """Correct cubie in this corner slot, ignoring twist."""
    idxs = corner_indices_by_axis(p)
    expect = set(letters_by_axis(p).values())
    observed = {state.arr[i] for i in idxs.values()}
    return observed == expect


# ---------------------------------------------------------------------------
# Generic bounded search: find a short move sequence that solves `target`
# while keeping every already-`locked` slot solved. Correct by construction
# (verified against the real move engine), no hand-derived algorithm needed.
# ---------------------------------------------------------------------------

def _analyze(state):
    return analyze_edges(state), analyze_corners(state)


def _pos_ori(home, edge, edge_analysis, corner_analysis):
    return edge_analysis[home] if edge else corner_analysis[home]


def _find_for_tracked(state, tracked, allowed_moves, max_depth):
    edge_analysis, corner_analysis = _analyze(state)
    pieces = [(e, h, *_pos_ori(h, e, edge_analysis, corner_analysis)) for h, e in tracked]
    return find_moves(pieces, allowed_moves, max_depth)


def _faces_touching(p):
    sx, sy, sz = p
    faces = []
    if sx != 0:
        faces.append('R' if sx == 1 else 'L')
    if sy != 0:
        faces.append('U' if sy == 1 else 'D')
    if sz != 0:
        faces.append('F' if sz == 1 else 'B')
    return faces


NO_D_MOVES = [m for m in ALL_MOVES if m[0] != 'D']


def _restricted_moves(target):
    """U never disturbs the D or middle layers, so it's always safe to
    include (and often needed to stage a piece through the U layer).
    Restricting the rest to just the faces the target itself touches keeps
    branching -- and how many other locked pieces can possibly be disturbed
    -- small; notably this excludes D entirely for middle/last-layer
    targets, so it never has to fight with an already-solved D layer. Falls
    back to the full move set if this is too narrow to find a solution."""
    faces = set(_faces_touching(target)) | {'U'}
    return [m for m in ALL_MOVES if m[0] in faces]


def _solve_one(state, target, is_edge, locked, max_depth, allowed_moves):
    """Find a sequence placing `target` without disturbing `locked`, widening
    the tracked set (and retrying) only if a found sequence turns out to
    disturb something. Returns None instead of raising if no luck."""
    tracked = [(target, is_edge)]
    seq = None
    for _ in range(len(locked) + 2):
        seq = _find_for_tracked(state, tracked, allowed_moves, max_depth)
        if seq is None:
            seq = _find_for_tracked(state, tracked, allowed_moves, max_depth + 2)
        if seq is None:
            return None
        trial = apply_moves(state, seq)
        broken = [(h, e) for h, e in locked if (h, e) not in tracked and not piece_is_solved(trial, h, e)]
        if not broken:
            return seq
        tracked.extend(broken)
    return None


def _solve_pieces(state, targets, is_edge, locked, max_depth, allowed_moves=ALL_MOVES):
    """Place each of `targets` (tracked by home slot) while keeping every
    already-`locked` piece solved. Uses fast_search's precomputed move
    tables (tuple-based BFS) instead of simulating the full 54-sticker state
    at every search node -- orders of magnitude faster.

    Tries a move set restricted to the target's own faces (+U/D) first --
    small branching, and few other pieces are even reachable, so widening
    to cover collateral damage rarely kicks in. Falls back to the full move
    set (which can require wider tracking, so is slower) only if that's not
    enough."""
    moves = []
    for target in targets:
        if piece_is_solved(state, target, is_edge):
            locked.append((target, is_edge))
            continue
        seq = _solve_one(state, target, is_edge, locked, max_depth, _restricted_moves(target))
        if seq is None:
            seq = _solve_one(state, target, is_edge, locked, max_depth, allowed_moves)
        if seq is None:
            raise SolverError(f"couldn't place piece at {target}")
        state = apply_moves(state, seq)
        moves.extend(seq)
        locked.append((target, is_edge))
    return moves, state, locked


# D-layer cross+corners and the middle-layer edges are solved first
# ("first two layers" in the classic method); the U layer is solved last.
STAGE1_CROSS_TARGETS = [(1, -1, 0), (0, -1, 1), (0, -1, -1), (-1, -1, 0)]
STAGE2_CORNER_TARGETS = [(1, -1, 1), (1, -1, -1), (-1, -1, -1), (-1, -1, 1)]
STAGE3_MIDDLE_EDGE_TARGETS = [(1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1)]
LAST_LAYER_EDGE_TARGETS = [(1, 1, 0), (-1, 1, 0), (0, 1, 1), (0, 1, -1)]
LAST_LAYER_CORNER_TARGETS = [(1, 1, 1), (1, 1, -1), (-1, 1, -1), (-1, 1, 1)]


# ---------------------------------------------------------------------------
# Last layer: fixed, empirically-verified-against-the-real-engine algorithms
# (each confirmed by applying it to a solved cube and checking exactly which
# stickers it touches -- see the exploration that produced these). The
# generic locked-piece search above gets prohibitively slow here (10+
# already-locked pieces to preserve), but these are true F2L-safe
# commutators, so no preservation search is needed at all: apply, and the
# first two layers are untouched by construction.
# ---------------------------------------------------------------------------

_INV_SUFFIX = {'': "'", "'": '', '2': '2'}


def _invert_sequence(seq):
    return [m[0] + _INV_SUFFIX[m[1:]] for m in reversed(seq)]


_ALIGN_OPTIONS = [[], ['U'], ['U2'], ["U'"]]

# Orients the last-layer edge cross (dot/line/L-shape/cross), F2L-safe.
_EDGE_ORIENT_ALG = ['F', 'R', 'U', "R'", "U'", "F'"]
# Cycles 3 last-layer corners (keeps 1 fixed), ignores twist; F2L-safe.
_CORNER_CYCLE_ALG = ['U', 'R', "U'", "L'", 'U', "R'", "U'", 'L']
_CORNER_CYCLE_ALG_INV = _invert_sequence(_CORNER_CYCLE_ALG)
# Double-swap of opposite last-layer corner pairs (twist-agnostic, F2L-safe).
_CORNER_SWAP_ALG = _CORNER_CYCLE_ALG + ['U'] + _CORNER_CYCLE_ALG + ["U'"]
# "T-perm": swaps one adjacent corner pair + one adjacent edge pair together
# (F2L-safe). The 3-cycle/double-swap algorithms above are even permutations
# and can never fix a single (odd) corner transposition on their own -- this
# is the corrective move for that case, since it flips corner *and* edge
# parity together, keeping the two in the equal-parity relationship every
# reachable cube state has. Also useful (via a second application at another
# alignment) for diagonal corner swaps that a single adjacent-swap can't fix.
_T_PERM = ['R', 'U', "R'", "U'", "R'", 'F', 'R2', "U'", "R'", "U'", 'R', 'U', "R'", "F'"]
# "Sune": twists last-layer corners (keeps permutation), F2L-safe.
_CORNER_TWIST_ALG = ['R', 'U', "R'", 'U', 'R', 'U2', "R'"]
_CORNER_TWIST_ALG_INV = _invert_sequence(_CORNER_TWIST_ALG)
# Pure 3-cycle of 3 last-layer edges (keeps 1 fixed, corner-safe).
_EDGE_CYCLE_ALG = ['R', "U'", 'R', 'U', 'R', 'U', 'R', "U'", "R'", "U'", 'R2']
_EDGE_CYCLE_ALG_INV = _invert_sequence(_EDGE_CYCLE_ALG)
# Double-swap of opposite last-layer edge pairs (corner-safe).
_EDGE_SWAP_ALG = _EDGE_CYCLE_ALG + ['U'] + _EDGE_CYCLE_ALG + ["U'"]


def _apply_best(state, candidates, score_fn, target_score, max_rounds):
    """BFS over applications of (pre-rotation, algorithm) combos to find the
    shortest sequence reaching target_score. A pure greedy hill-climb (always
    take whichever single application scores best right now) gets stuck on
    cases where every immediate option ties -- e.g. a diagonal corner swap,
    where the fix is "apply X to turn it into an adjacent swap, THEN apply Y",
    but step one doesn't improve the score by itself. BFS explores both
    branches of a tie and finds the multi-step fix; the state spaces here are
    tiny (a handful of last-layer cases) so this is still instant."""
    if score_fn(state) >= target_score:
        return [], state
    # Conjugate (pre + alg + pre^-1), not a bare prefix: a bare 'U' prefix
    # would permanently rotate whatever's already correctly placed (e.g.
    # already-solved corners going into the edge-permutation stage) since
    # it's never undone. Conjugating keeps each meta-move self-contained --
    # its effect on already-solved pieces is identical to alg's own (safe by
    # construction), just relabeled to a different absolute alignment.
    meta_moves = [pre + alg + _invert_sequence(pre) for alg in candidates for pre in _ALIGN_OPTIONS]
    start_key = tuple(state.arr.tolist())
    visited = {start_key}
    queue = deque([(state, [], 0)])
    while queue:
        cur_state, path, rounds = queue.popleft()
        if rounds >= max_rounds:
            continue
        for mm in meta_moves:
            trial = apply_moves(cur_state, mm)
            if score_fn(trial) >= target_score:
                return path + mm, trial
            key = tuple(trial.arr.tolist())
            if key not in visited:
                visited.add(key)
                queue.append((trial, path + mm, rounds + 1))
    raise SolverError("last-layer algorithm did not converge")


def solve_last_layer(state):
    moves = []
    # Edge orientation first -- verified stable under every corner algorithm
    # below (none of them touch the up-facing sticker of a last-layer edge).
    seq, state = _apply_best(
        state, [_EDGE_ORIENT_ALG],
        lambda s: sum(edge_oriented(s, t) for t in LAST_LAYER_EDGE_TARGETS), 4, 4)
    moves.extend(seq)
    # Position and orientation together: a twist algorithm (Sune) applied
    # when corners aren't yet all correctly positioned can shuffle which
    # cubie is at which slot even while satisfying "shows U on top" at every
    # slot, so position-only, then orientation-only, as separate passes,
    # isn't reliable. Target the full solve and let BFS combine whichever
    # algorithms are needed, in whichever order.
    seq, state = _apply_best(
        state,
        [_T_PERM, _CORNER_CYCLE_ALG, _CORNER_CYCLE_ALG_INV, _CORNER_SWAP_ALG,
         _CORNER_TWIST_ALG, _CORNER_TWIST_ALG_INV],
        lambda s: sum(piece_is_solved(s, t, False) for t in LAST_LAYER_CORNER_TARGETS), 4, 8)
    moves.extend(seq)
    seq, state = _apply_best(
        state, [_EDGE_CYCLE_ALG, _EDGE_CYCLE_ALG_INV, _EDGE_SWAP_ALG],
        lambda s: sum(piece_is_solved(s, t, True) for t in LAST_LAYER_EDGE_TARGETS), 4, 3)
    moves.extend(seq)
    return moves, state


MAX_SANE_MOVES = 400


def solve(state, cross_depth=6, corner_depth=7, edge_depth=7):
    result = validate(state)
    if not result.ok:
        raise SolverError(f"{result.error_code}: {result.message}")

    s = state.copy()
    solution = []
    stage_bounds = []

    def record(name, seq):
        solution.extend(seq)
        stage_bounds.append((name, len(solution)))

    locked = []
    seq, s, locked = _solve_pieces(s, STAGE1_CROSS_TARGETS, True, locked, cross_depth, ALL_MOVES)
    record('cross', seq)
    seq, s, locked = _solve_pieces(s, STAGE2_CORNER_TARGETS, False, locked, corner_depth, ALL_MOVES)
    record('first_layer_corners', seq)
    seq, s, locked = _solve_pieces(s, STAGE3_MIDDLE_EDGE_TARGETS, True, locked, edge_depth, NO_D_MOVES)
    record('middle_layer', seq)
    seq, s = solve_last_layer(s)
    record('last_layer', seq)

    if s != solved_state():
        raise SolverError("internal error: solver finished but the cube is not solved")
    if len(solution) > MAX_SANE_MOVES:
        raise SolverError(f"internal error: solution unexpectedly long ({len(solution)} moves)")
    return solution, stage_bounds


# ---------------------------------------------------------------------------
# Human-facing move enrichment
# ---------------------------------------------------------------------------

FACE_NAMES = {'U': 'Top', 'D': 'Bottom', 'L': 'Left', 'R': 'Right', 'F': 'Front', 'B': 'Back'}
DIRECTION_PHRASE = {
    'CW': "clockwise (like turning a doorknob to the right), looking straight at that face",
    'CCW': "counter-clockwise (like turning a doorknob to the left), looking straight at that face",
    '180': "180 degrees (a half turn -- direction doesn't matter)",
}


@dataclass(frozen=True)
class MoveInstruction:
    notation: str
    face: str
    face_name: str
    direction: str
    step_index: int
    total_steps: int
    stage: str
    description: str


def _stage_for_index(i, stage_bounds):
    for name, end in stage_bounds:
        if i < end:
            return name
    return stage_bounds[-1][0] if stage_bounds else 'unknown'


def enrich(moves, stage_bounds):
    total = len(moves)
    result = []
    for i, m in enumerate(moves):
        face = m[0]
        suffix = m[1:]
        direction = {'': 'CW', "'": 'CCW', '2': '180'}[suffix]
        stage = _stage_for_index(i, stage_bounds)
        result.append(MoveInstruction(
            notation=m,
            face=face,
            face_name=FACE_NAMES[face],
            direction=direction,
            step_index=i + 1,
            total_steps=total,
            stage=stage,
            description=f"Turn the {FACE_NAMES[face]} ({face}) face {DIRECTION_PHRASE[direction]}.",
        ))
    return result
