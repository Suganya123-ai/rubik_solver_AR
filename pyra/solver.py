"""Optimal Pyraminx solver: a complete table of every position's distance to solved.

The puzzle without its tips has 933,120 positions and none is more than 11
moves from solved (God's number), so every position's exact distance is
worked out once (a breadth-first search from the solved puzzle, ~2 s) and
stored. Then:

- solving is a walk downhill: each move taken lowers the distance by one, so
  the solution is always the shortest possible;
- among the equally short solutions, the one easiest to follow is chosen
  (fewest changes of corner, so the hands move least; then fewest
  anticlockwise turns);
- the tips go last (one turn each at most);
- the table also says how far ANY position is from solved, which the move
  tracker uses, and whether a scanned position exists at all (a misread
  colour gives a position that is not in the table).

The four tips twist on their own, so they are left out of the table.
"""
import os

import numpy as np

from .geometry import MAIN_MOVES, MOVES, STICKERS, TIP_STICKERS
from .model import SOLVED

_BODY = np.array([i for i in range(len(STICKERS)) if i not in TIP_STICKERS])   # the 24 non-tip stickers
_CODE = {'F': 0, 'R': 1, 'L': 2, 'D': 3}
_WEIGHTS = (4 ** np.arange(len(_BODY), dtype=np.int64))[::-1]
_PERMS = np.array([MOVES[m] for m in MAIN_MOVES])
_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'table.npz')
_table = None


def _codes(states):
    """(n, 36) letter arrays -> (n, 36) small ints."""
    lut = np.zeros(128, np.int8)
    for k, v in _CODE.items():
        lut[ord(k)] = v
    return lut[np.asarray(states).view(np.int32).reshape(len(states), -1)] if np.asarray(states).dtype.kind == 'U' \
        else np.asarray(states, np.int8)


def _keys(codes):
    """One 48-bit number per position (the 24 non-tip stickers, 2 bits each)."""
    return codes[:, _BODY].astype(np.int64) @ _WEIGHTS


def _build():
    solved = _codes(SOLVED[None])
    frontier = solved
    keys = [_keys(solved)]
    dists = [np.zeros(1, np.uint8)]
    seen = keys[0]
    depth = 0
    while len(frontier):
        depth += 1
        nxt = np.concatenate([frontier[:, p] for p in _PERMS])
        k = _keys(nxt)
        k, first = np.unique(k, return_index=True)
        fresh = ~np.isin(k, seen)
        frontier = nxt[first[fresh]]
        if not len(frontier):
            break
        keys.append(k[fresh])
        dists.append(np.full(fresh.sum(), depth, np.uint8))
        seen = np.sort(np.concatenate([seen, k[fresh]]))
    keys, dists = np.concatenate(keys), np.concatenate(dists)
    order = np.argsort(keys)
    return keys[order], dists[order]


def table():
    """(sorted keys, distances) for all 933,120 positions; built once, then loaded from table.npz."""
    global _table
    if _table is None:
        if os.path.exists(_CACHE):
            z = np.load(_CACHE)
            _table = (z['keys'], z['dist'])
        else:
            _table = _build()
            np.savez_compressed(_CACHE, keys=_table[0], dist=_table[1])
    return _table


def distance(state):
    """Moves (without tips) from solved, or None if the position can't exist (e.g. a misread colour)."""
    keys, dist = table()
    k = _keys(_codes(np.asarray(state)[None]))[0]
    i = np.searchsorted(keys, k)
    return int(dist[i]) if i < len(keys) and keys[i] == k else None


def _distances(states):
    keys, dist = table()
    k = _keys(_codes(states))
    i = np.clip(np.searchsorted(keys, k), 0, len(keys) - 1)
    return np.where(keys[i] == k, dist[i].astype(int), 99)


def _cost(moves):
    changes = sum(1 for a, b in zip(moves, moves[1:]) if a[0] != b[0])
    return changes, sum(m.endswith("'") for m in moves)


def solve_body(state):
    """Shortest solution for everything but the tips, the easiest of the shortest to follow."""
    d0 = distance(state)
    if d0 is None:
        raise ValueError('this position cannot exist on a Pyraminx (a colour was probably misread)')
    best = [None]

    def walk(s, d, path):
        if d == 0:
            if best[0] is None or _cost(path) < _cost(best[0]):
                best[0] = list(path)
            return
        nxt = np.array([s[MOVES[m]] for m in MAIN_MOVES])
        for m, n, dn in zip(MAIN_MOVES, nxt, _distances(nxt)):
            if dn == d - 1 and not (path and path[-1][0] == m[0]):   # (two turns of one corner = one turn)
                walk(n, dn, path + [m])

    walk(np.asarray(state), d0, [])
    return best[0]


def tip_moves(state):
    """The tip turns that finish a puzzle whose body is solved."""
    s = np.asarray(state)
    out = []
    for c in 'ULRB':
        # which turn of this tip solves it: none, clockwise or anticlockwise
        for m in ('', c.lower(), c.lower() + "'"):
            t = s[MOVES[m]] if m else s
            idx = [i for i in TIP_STICKERS if _corner_of(i) == c]
            if np.all(t[idx] == SOLVED[idx]):
                if m:
                    out.append(m)
                    s = t
                break
    return out


def _corner_of(sticker):
    from .geometry import FACE_CORNERS
    f, k, _ = STICKERS[sticker]
    return FACE_CORNERS[f][k]


def solve(state):
    """The full solution: the body in the fewest moves, then the tips."""
    from .model import apply_moves
    body = solve_body(state)
    return body + tip_moves(apply_moves(state, body))
