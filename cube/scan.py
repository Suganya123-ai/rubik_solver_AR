"""Two-view scan: the camera reads 3 sides per view (Top, Front, Right as seen
in the picture), so two views cover all 54 stickers.

View 1 (home position): the cube's Top, Front and Right.
View 2: turn the cube upside down (top <-> bottom, front <-> back), then a
quarter turn so the old Left side faces the camera. The picture then shows
the cube's Bottom (on top), Left (in front) and Back (on the right).

Which picture sticker is which cube sticker is derived from the cube model's
own geometry (cube/moves.py), never written out by hand.
"""
import numpy as np

import itertools

from .color_detect import (COLOR_NAMES, _min_cost_assignment, color_feature, rebalance_colors, resolver_colors,
                           rgb_to_lab)
from .cube_state import FACE_OFFSET, FACES, CubeState
from .moves import FACELET_DIR, _grid_cubie_pos
from .validation import (CORNER_POSITIONS, EDGE_POSITIONS, _SOLVED_ARR, _rotations, corner_facelet_indices,
                         edge_facelet_indices, validate, validate_scan)

VIEW_FACES = ('U', 'F', 'R')  # sides as seen in the picture, in the reader's order
# Rotation taking cube coordinates to view coordinates (axes: +x R, +y U, +z F).
VIEW_ROTATIONS = {
    1: np.eye(3, dtype=int),
    # upside down (180 deg about x), then a quarter turn about y bringing Left to the front
    2: np.array([[0, 0, -1], [0, -1, 0], [-1, 0, 0]]),
}
VIEW_INSTRUCTIONS = {
    1: 'Hold the cube corner-on so the camera sees its Top, Front and Right sides.',
    2: 'Turn the cube upside down (top and bottom swap, front and back swap), then a quarter turn so '
       'the old Left side faces the camera. The camera now sees the Bottom, Left and Back.',
}
OPPOSITE_COLOR = {'white': 'yellow', 'yellow': 'white', 'red': 'orange', 'orange': 'red',
                  'green': 'blue', 'blue': 'green'}
# Typical sticker colours, only used to give the six centres their names.
_REFERENCE_RGB = {'white': (240, 240, 235), 'yellow': (252, 216, 35), 'red': (215, 40, 55),
                  'orange': (255, 125, 30), 'green': (20, 175, 90), 'blue': (15, 85, 205)}


def _facelet_index(pos, normal):
    face = next(f for f, d in FACELET_DIR.items() if tuple(d) == tuple(normal))
    for k in range(9):
        r, c = divmod(k, 3)
        if _grid_cubie_pos(face, r, c) == tuple(pos):
            return FACE_OFFSET[face] + k
    raise ValueError((pos, normal))


def view_facelets(view):
    """The 27 cube facelet indices seen in `view`, in the reader's order
    (picture Top 0-8, Front 0-8, Right 0-8)."""
    back = VIEW_ROTATIONS[view].T  # view -> cube coordinates
    out = []
    for vface in VIEW_FACES:
        for k in range(9):
            r, c = divmod(k, 3)
            pos = back @ np.array(_grid_cubie_pos(vface, r, c))
            normal = back @ np.array(FACELET_DIR[vface])
            out.append(_facelet_index(tuple(int(v) for v in pos), tuple(int(v) for v in normal)))
    return out


def view_center_faces(view):
    """Which cube faces the picture's Top, Front and Right centres are."""
    idx = view_facelets(view)
    return [FACES[idx[9 * i + 4] // 9] for i in range(3)]


def assemble(view_readings):
    """view_readings: {1: {'U': [9 rgb], 'F': [...], 'R': [...]}, 2: {...}}
    -> {face: [9 rgb]} for all six cube faces."""
    flat = [None] * 54
    for view, reading in view_readings.items():
        rgbs = [rgb for vface in VIEW_FACES for rgb in reading[vface]]
        for idx, rgb in zip(view_facelets(view), rgbs):
            flat[idx] = rgb
    if any(v is None for v in flat):
        raise ValueError('a sticker was not read')
    return {f: flat[FACE_OFFSET[f]:FACE_OFFSET[f] + 9] for f in FACES}


_FACE_PAIRS = (('U', 'D'), ('F', 'B'), ('R', 'L'))
_PALETTE = {n: color_feature(rgb) for n, rgb in _REFERENCE_RGB.items()}


def _features(rgbs_by_face):
    """(54, 3) colour features in facelet order (see color_feature)."""
    return np.array([color_feature(rgb) for f in FACES for rgb in rgbs_by_face[f]])


def _balanced_assign(points, means, per):
    """Assigns each point to a cluster, exactly `per` points per cluster, at
    the lowest total distance."""
    dist = np.linalg.norm(points[:, None, :] - np.asarray(means)[None], axis=2)
    cols = np.repeat(np.arange(len(means)), per)
    assign = _min_cost_assignment(dist[:, cols].tolist())
    return cols[assign]


def _balanced_clusters(points, k=6, per=8, iters=8, starts=4):
    """k-means where every cluster gets exactly `per` points (a real cube has
    8 non-centre stickers of each colour). Tries a few farthest-point
    starts and keeps the tightest result. Returns (labels, means)."""
    best = None
    for s in range(starts):
        means = [points[(s * 11) % len(points)]]
        while len(means) < k:  # farthest point from those picked so far
            d = np.min(np.linalg.norm(points[:, None] - np.array(means)[None], axis=2), axis=1)
            means.append(points[int(np.argmax(d))])
        means = np.array(means)
        labels = None
        for _ in range(iters):
            new = _balanced_assign(points, means, per)
            if labels is not None and np.array_equal(new, labels):
                break
            labels = new
            means = np.array([points[labels == c].mean(axis=0) for c in range(k)])
        spread = float(np.linalg.norm(points - means[labels], axis=1).sum())
        if best is None or spread < best[0]:
            best = (spread, labels, means)
    return best[1], best[2]


def colour_groups(rgbs_by_face):
    """Groups the 48 non-centre stickers into the six colours (8 each) and
    names the groups. The centres are not trusted to define the colours:
    a logo or a glossy centre cap can read as a different colour entirely.
    Returns (names_by_index {facelet index: name} for non-centres, {name: mean feature})."""
    feats = _features(rgbs_by_face)
    idx = [i for i in range(54) if i % 9 != 4]
    labels, means = _balanced_clusters(feats[idx])
    cost = [[float(np.linalg.norm(m - _PALETTE[n])) for n in COLOR_NAMES] for m in means]
    name_of = {c: COLOR_NAMES[j] for c, j in enumerate(_min_cost_assignment(cost))}
    return {i: name_of[c] for i, c in zip(idx, labels)}, {name_of[c]: means[c] for c in range(len(means))}


def name_centers(rgbs_by_face, groups=None, locked=None):
    """Gives the six centres six different colour names: each centre gets the
    colour group it is closest to, with opposite sides holding opposite
    colours (white/yellow, red/orange, green/blue) wherever possible.
    locked: {(face, 4): colour} centres the user confirmed."""
    _, refs = groups or colour_groups(rgbs_by_face)
    feats = {f: color_feature(rgbs_by_face[f][4]) for f in FACES}
    must = {f: c for (f, k), c in (locked or {}).items() if k == 4}
    best = None
    for names in itertools.permutations(COLOR_NAMES):
        centers = dict(zip(FACES, names))
        if any(centers[f] != c for f, c in must.items()):
            continue
        cost = sum(float(np.linalg.norm(feats[f] - refs[centers[f]])) for f in FACES)
        if not opposite_centers_ok(centers):
            cost += 1000  # standard colour scheme strongly preferred
        if best is None or cost < best[0]:
            best = (cost, centers)
    return best[1]


def _doubtful_centers(rgbs_by_face, centers, refs):
    """Centres whose own reading is closer to another colour's group than to
    the one they were given (logo, glare): the user should confirm them."""
    out = []
    for f in FACES:
        feat = color_feature(rgbs_by_face[f][4])
        nearest = min(refs, key=lambda n: np.linalg.norm(feat - refs[n]))
        if nearest != centers[f]:
            out.append((f, 4))
    return out


def opposite_centers_ok(centers):
    return all(OPPOSITE_COLOR[centers[a]] == centers[b] for a, b in (('U', 'D'), ('F', 'B'), ('R', 'L')))


LIGHTNESS_WEIGHT = 0.3  # brightness counts less than hue: each side of a corner-on view is lit differently

_CORNER_SLOTS = [corner_facelet_indices(p) for p in CORNER_POSITIONS]
_EDGE_SLOTS = [edge_facelet_indices(p) for p in EDGE_POSITIONS]
# Each real piece as its face letters in the slots' own (clockwise) order; its
# legal placements are the cyclic rotations of that tuple (never mirrors).
_CORNER_PIECES = [tuple(_SOLVED_ARR[i] for i in idx) for idx in _CORNER_SLOTS]
_EDGE_PIECES = [tuple(_SOLVED_ARR[i] for i in idx) for idx in _EDGE_SLOTS]


def piece_colors(rgbs_by_face, centers, rounds=3, locked=None, refs=None):
    """Names all 54 stickers by matching whole pieces: each measured corner (3
    stickers) to one of the 8 real corner pieces and each edge (2 stickers) to
    one of the 12 real edge pieces, in the cheapest legal orientation, with
    every piece used exactly once. A sticker that is hard to read on its own
    (orange or yellow?) is settled by its neighbours, because only real pieces
    are allowed. Remaining rule breaks (twisted corner, flipped edge, parity)
    are repaired with the cheapest single change. locked: {(face, k): colour}
    the user confirmed; every placement must respect them. refs: {colour:
    feature} to start from (default: the colour groups, see colour_groups).
    Returns {face: [9 names]}."""
    labs = _features(rgbs_by_face)
    if refs is None:
        refs = colour_groups(rgbs_by_face)[1]
    letter_of = {centers[f]: f for f in FACES}
    refs = {f: refs[centers[f]] for f in FACES}
    not_centre = np.arange(54) % 9 != 4
    must = {FACE_OFFSET[f] + k: letter_of[c] for (f, k), c in (locked or {}).items()}

    def cost(slot, letters):
        penalty = sum(1e6 for i, x in zip(slot, letters) if i in must and must[i] != x)
        return penalty + float(sum(np.linalg.norm(labs[i] - refs[x]) for i, x in zip(slot, letters)))

    def best_placement(slot, piece):
        return min(((cost(slot, rot), rot) for rot in _rotations(piece)), key=lambda t: t[0])

    for _ in range(rounds):
        placed = {}
        for slots, pieces in ((_CORNER_SLOTS, _CORNER_PIECES), (_EDGE_SLOTS, _EDGE_PIECES)):
            table = [[best_placement(slot, piece) for piece in pieces] for slot in slots]
            assign = _min_cost_assignment([[c for c, _ in row] for row in table])
            for si, pi in enumerate(assign):
                placed[slots[si]] = table[si][pi][1]
        arr = np.array(_SOLVED_ARR, copy=True)
        for slot, letters in placed.items():
            for i, x in zip(slot, letters):
                arr[i] = x
        # Re-estimate each colour's reference from everything assigned to it.
        # (centres left out: a logo centre would drag its colour off.)
        refs = {f: labs[(arr == f) & not_centre].mean(axis=0) for f in FACES}

    arr = _repair(arr, placed, cost)
    return {f: [centers[x] for x in arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}


def _total(placed, cost):
    return sum(cost(slot, letters) for slot, letters in placed.items())


def _with(placed, changes):
    new = dict(placed)
    new.update(changes)
    arr = np.array(_SOLVED_ARR, copy=True)
    for slot, letters in new.items():
        for i, x in zip(slot, letters):
            arr[i] = x
    return new, arr


def _repair(arr, placed, cost):
    """Fixes permutation parity, corner twist and edge flip, each with the
    cheapest single change (swap two pieces / re-orient one piece)."""
    for code in ('ERROR_PARITY', 'ERROR_CORNER_TWIST', 'ERROR_EDGE_FLIP'):
        result = validate(CubeState(arr))
        if result.ok or result.error_code != code:
            continue
        candidates = []
        if code == 'ERROR_PARITY':
            for slots in (_CORNER_SLOTS, _EDGE_SLOTS):
                for a in range(len(slots)):
                    for b in range(a + 1, len(slots)):
                        pa, pb = placed[slots[a]], placed[slots[b]]
                        ra = min(_rotations(pb), key=lambda r: cost(slots[a], r))
                        rb = min(_rotations(pa), key=lambda r: cost(slots[b], r))
                        candidates.append({slots[a]: ra, slots[b]: rb})
        else:
            slots = _CORNER_SLOTS if code == 'ERROR_CORNER_TWIST' else _EDGE_SLOTS
            for slot in slots:
                for r in _rotations(placed[slot])[1:]:
                    candidates.append({slot: r})
        best = None
        for change in candidates:
            new, new_arr = _with(placed, change)
            r = validate(CubeState(new_arr))
            if r.ok or r.error_code != code:
                c = _total(new, cost)
                if best is None or c < best[0]:
                    best = (c, new, new_arr)
        if best:
            _, placed, arr = best
    return arr


DOUBT_RATIO = 0.8  # a sticker this close to a second colour (distance ratio) gets checked


def poor_fit(rgbs_by_face, colors, ratio=None):
    """Stickers that are nearly as close to another colour as to the one they
    were given (a finger, glare or shadow over them)."""
    ratio = DOUBT_RATIO if ratio is None else ratio
    feats = _features(rgbs_by_face)
    names = [c for f in FACES for c in colors[f]]
    side = [i for i in range(54) if i % 9 != 4]
    refs = {n: feats[[i for i in side if names[i] == n]].mean(axis=0) for n in set(names)}
    out = set()
    for i in side:
        own = np.linalg.norm(feats[i] - refs[names[i]])
        other = min(np.linalg.norm(feats[i] - refs[n]) for n in refs if n != names[i])
        if own > ratio * other:
            out.add((FACES[i // 9], i % 9))
    return out


def scan_result(rgbs_by_face, locked=None, centers=None):
    """The scan as the app shows it: colours from piece matching, plus the
    stickers to double-check -- wherever the sticker-by-sticker grouping
    disagrees with piece matching, and any centre that reads like another
    colour (logo, glare). locked: {(face, k): colour} the user confirmed;
    they're kept and never flagged again."""
    locked = locked or {}
    groups = colour_groups(rgbs_by_face)
    by_index, refs = groups
    centers = centers or name_centers(rgbs_by_face, groups, locked)
    colors = piece_colors(rgbs_by_face, centers, locked=locked, refs=refs)
    unsure = poor_fit(rgbs_by_face, colors)
    doubtful = [(f, k) for f in FACES for k in range(9) if k != 4 and (f, k) not in locked
                and (colors[f][k] != by_index[FACE_OFFSET[f] + k] or (f, k) in unsure)]
    doubtful += [fk for fk in _doubtful_centers(rgbs_by_face, centers, refs) if fk not in locked]
    state, result = validate_scan(colors)
    return {'colors': colors, 'doubtful': sorted(doubtful, key=lambda fk: (FACES.index(fk[0]), fk[1])),
            'valid': result.ok, 'state': state if result.ok else None, 'centers': centers}


def read_cube(rgbs_by_face):
    """Names all 54 colours and validates the cube: piece matching first, then
    the sticker-level centre rebalance, then rubiks-color-resolver. Returns
    (colors_by_face, validation_result, state)."""
    centers = name_centers(rgbs_by_face)
    seed = {f: [centers[f]] * 9 for f in FACES}  # only the centres matter to the rebalance
    attempts = [piece_colors(rgbs_by_face, centers),
                lambda: rebalance_colors(seed, rgbs_by_face, {}, lightness_weight=LIGHTNESS_WEIGHT),
                lambda: resolver_colors(rgbs_by_face, seed)]
    last = None
    for attempt in attempts:
        colors = attempt() if callable(attempt) else attempt
        if colors is None:
            continue
        state, result = validate_scan(colors)
        if result.ok:
            return colors, result, state
        last = (colors, result, None)
    return last if last else (None, None, None)
