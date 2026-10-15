"""Naming the 36 scanned sticker colours of a Pyraminx.

1. Group: the 36 colours go into 4 groups of exactly 9 (every colour appears
   9 times on a Pyraminx), by colour hue (cube.color_detect.color_feature:
   shading and glare matter little), with a balanced assignment.
2. Name the groups by the puzzle itself, not by a fixed colour scheme: the
   face opposite a corner has the one colour that corner's tip doesn't have.
3. Decode with the puzzle's rules: of all positions that can exist (the
   solver's table: 933,120 body positions x 81 tip turns) and all 24 ways of
   naming the 4 groups, take the one that best matches the 36 colours read
   (least total colour distance). A few misread stickers (a finger, glare)
   can't make an impossible puzzle; they are corrected, and flagged.
"""
import itertools

import numpy as np

from cube.color_detect import _min_cost_assignment, color_feature

from .geometry import FACE_CORNERS, FACES, MOVES, OPPOSITE, STICKERS, TIP_STICKERS

NAMES = {'green': (35, 170, 80), 'blue': (20, 90, 210), 'red': (210, 35, 50), 'yellow': (250, 215, 30)}


def _groups(feats):
    """4 balanced groups of 9; returns (group per sticker, centres, cost of each sticker's group)."""
    n = len(feats)
    # start: four colours far apart (farthest-point), then balanced k-means
    centres = [feats[int(np.argmax(np.linalg.norm(feats - feats.mean(0), axis=1)))]]
    while len(centres) < 4:
        d = np.min([np.linalg.norm(feats - c, axis=1) for c in centres], axis=0)
        centres.append(feats[int(np.argmax(d))])
    centres = np.array(centres)
    group = None
    for _ in range(10):
        cost = np.linalg.norm(feats[:, None] - centres[None], axis=2)            # (36, 4)
        slots = np.repeat(cost, n // 4, axis=1)                                 # each group has 9 slots
        assign = _min_cost_assignment(slots.tolist())
        new = np.array([a // (n // 4) for a in assign])
        if group is not None and np.array_equal(new, group):
            break
        group = new
        centres = np.array([feats[group == g].mean(0) for g in range(4)])
    cost = np.linalg.norm(feats[:, None] - centres[None], axis=2)
    return group, centres, cost


def _letters(group):
    """Face letter per sticker from the groups, using the tips (see module doc). None if inconsistent."""
    letter_of_group = {}
    for f in FACES:
        corner = OPPOSITE[f]
        tip = [i for i in TIP_STICKERS if FACE_CORNERS[STICKERS[i][0]][STICKERS[i][1]] == corner]
        missing = set(range(4)) - {int(group[i]) for i in tip}
        if len(missing) != 1:
            return None
        letter_of_group[missing.pop()] = f
    if len(letter_of_group) != 4:
        return None
    return np.array([letter_of_group[int(g)] for g in group])


_LETTERS = np.array(list('FRLD'))
_body_letters = None


def _all_bodies():
    """(933120, 24) letter codes (0..3 = F R L D) of every possible body position."""
    global _body_letters
    if _body_letters is None:
        from .solver import _BODY, table
        keys, _ = table()
        shifts = 2 * np.arange(len(_BODY) - 1, -1, -1, dtype=np.int64)
        _body_letters = ((keys[:, None] >> shifts[None]) & 3).astype(np.int8)
    return _body_letters


def _tip_options():
    """For each corner: its 3 tip stickers and the 3 letter triples a tip can show (turned 0, 1, 2 times)."""
    from .model import SOLVED
    out = []
    for c in 'ULRB':
        idx = [i for i in TIP_STICKERS if FACE_CORNERS[STICKERS[i][0]][STICKERS[i][1]] == c]
        opts, s = [], SOLVED.copy()
        for _ in range(3):
            opts.append([int(np.where(_LETTERS == s[i])[0][0]) for i in idx])
            s = s[MOVES[c.lower()]]
        out.append((idx, np.array(opts)))
    return out


def decode(cost):
    """cost: (36, 4) colour distance of each sticker to each group. Returns (state letters, total cost,
    runner-up total cost) for the best possible puzzle position and naming of the groups."""
    from .solver import _BODY
    bodies = _all_bodies()
    tips = _tip_options()
    best = (None, np.inf, np.inf)
    for perm in itertools.permutations(range(4)):         # perm[letter code] = group
        lc = cost[:, list(perm)]                          # (36, 4): cost of each sticker showing each letter
        body_cost = lc[_BODY][np.arange(len(_BODY))[None], bodies].sum(1)
        tip_cost, tip_pick = 0.0, []
        for idx, opts in tips:
            c = lc[idx][np.arange(3)[None], opts].sum(1)
            tip_cost += c.min()
            tip_pick.append(opts[int(np.argmin(c))])
        two = np.partition(body_cost, 1)[:2]
        total, second = two[0] + tip_cost, two[1] + tip_cost
        if total < best[1]:
            state = np.empty(36, '<U1')
            state[_BODY] = _LETTERS[bodies[int(np.argmin(body_cost))]]
            for (idx, _), pick in zip(tips, tip_pick):
                state[idx] = _LETTERS[pick]
            best = (state, total, min(second, best[1]))
        else:
            best = (best[0], best[1], min(best[2], total))
    return best


def name_colours(rgbs, valid=None):
    """rgbs: 36 (r, g, b) in physical sticker order. Returns {'state': 36 letters (always a possible
    position), 'valid', 'doubtful': [sticker indices], 'colour_of': {letter: colour name}, 'confidence'}."""
    feats = np.array([color_feature(c) for c in rgbs])
    group, centres, cost = _groups(feats)
    state, total, second = decode(cost)
    # letter -> group, from the decoded state; stickers whose colour sits closer to another group are doubtful
    group_of = {L: int(np.bincount(group[state == L], minlength=4).argmax()) for L in 'FRLD'}
    fitted = np.array([cost[i, group_of[state[i]]] for i in range(36)])
    nearest = cost.min(1)
    doubtful = sorted(int(i) for i in np.nonzero(fitted - nearest > 1e-6)[0])
    margins = np.sort(cost, axis=1)
    doubtful = sorted(set(doubtful) | {int(i) for i in np.argsort(margins[:, 1] - margins[:, 0])[:3]
                                        if margins[i, 1] - margins[i, 0] < 10})
    colour_of = {L: min(NAMES, key=lambda n: np.linalg.norm(np.array(color_feature(NAMES[n])) - centres[g]))
                 for L, g in group_of.items()}
    return {'state': state, 'valid': True, 'doubtful': doubtful, 'colour_of': colour_of,
            'confidence': float(second - total), 'group_features': centres}
