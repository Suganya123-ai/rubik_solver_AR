"""Pyraminx states: 36 face letters (F R L D), one per sticker (see geometry.py)."""
import numpy as np

from .geometry import FACES, MOVES, STICKERS

SOLVED = np.array([f for f, _, _ in STICKERS])


def apply_moves(state, moves):
    s = np.asarray(state)
    for m in (moves.split() if isinstance(moves, str) else moves):
        s = s[MOVES[m]]
    return s


def is_solved(state):
    return bool(np.all(np.asarray(state) == SOLVED))


def inverse(moves):
    out = []
    for m in reversed(moves.split() if isinstance(moves, str) else moves):
        out.append(m[:-1] if m.endswith("'") else m + "'")
    return out


def random_state(rng, n=25, tips=True):
    from .geometry import MAIN_MOVES, TIP_MOVES
    pool = MAIN_MOVES + (TIP_MOVES if tips else [])
    return apply_moves(SOLVED, [pool[int(rng.integers(len(pool)))] for _ in range(n)])


__all__ = ['SOLVED', 'FACES', 'apply_moves', 'is_solved', 'inverse', 'random_state']
