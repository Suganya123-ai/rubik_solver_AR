"""The check that makes a label trustworthy without a person: read the stickers at the proposed corners
and compare them with how the puzzle is known to look at that moment (from the recorded scan and moves),
held any way, allowing for a move or two the recording hadn't caught up with. Wrong corners read stickers
from the wrong places, which matches no hold of the known position: a high cost, and no label.

Both return (agreement, cost, state index, hold index, hold margin, worst corner) for the best fit:
agreement = the share of the stickers in view whose colour is nearest the colour the fit says they should
have (right corners: all or nearly all; wrong ones lose many); cost = mean colour distance per sticker (as
the trackers measure it); hold margin = how much better that hold fits than the next; worst corner = the
lowest agreement among the stickers around any one corner (catches a single misplaced corner)."""
import numpy as np

from cube.color_detect import color_feature

CAP = 35.0   # one glared or covered sticker can't dominate


def _pyra_corner_stickers(kind):
    """For each of the 4 keypoints: the picture stickers touching it (tips and centres at it, edges next
    to it), so a single misplaced corner shows as wrong colours around that corner."""
    from pyra.view import VIEWS
    out = {j: [] for j in range(4)}
    for f, vf in enumerate(VIEWS[kind]):
        for pos, j in enumerate(vf):
            out[j] += [9 * f + pos, 9 * f + 3 + pos, 9 * f + 6 + pos, 9 * f + 6 + (pos - 1) % 3]
    return out


def pyra_cost(frame, kpts, kind, states, letter_feats, moves=()):
    """frame: BGR picture; kpts: 4 corners in the model's order (autolearn.canon); kind: 'corner' | 'edge';
    states: candidate positions (36 letters each); moves: moves that may have just been made from them
    (the one the user was asked for); letter_feats: {letter: colour feature} from the scan.
    Returns (cost, state index, hold index) or None if the stickers can't be read."""
    from pyra.geometry import MOVES
    from pyra.view import HOLDS_OF, face_share, read_stickers
    if face_share(kpts, kind) < 0.15:
        return None
    rgbs = read_stickers(frame, kpts, kind=kind)
    if any(c is None for c in rgbs):
        return None
    obs = np.array([color_feature(c) for c in rgbs])
    letters = 'FRLD'
    ref = np.array([letter_feats[L] for L in letters])
    dist = np.minimum(np.linalg.norm(obs[:, None] - ref[None], axis=2), CAP)      # (n stickers, 4)
    holds = np.array(HOLDS_OF[kind][1])                                           # (12, n)
    nearest = dist.argmin(1)
    best = None
    for si, st in enumerate(states):
        code = np.array([letters.index(x) for x in st])
        for cand in [code] + [code[MOVES[m]] for m in moves]:                     # now, or the move asked for
            want = cand[holds]                                                    # (12, n) letters per hold
            costs = dist[np.arange(holds.shape[1])[None], want].mean(1)
            order = np.argsort(costs)
            h = int(order[0])
            if best is None or costs[h] < best[1]:
                hit = nearest == want[h]
                worst = min(float(np.mean(hit[ids])) for ids in _pyra_corner_stickers(kind).values())
                best = (float(np.mean(hit)), float(costs[h]), si, h, float(costs[order[1]] - costs[h]), worst)
    return best


def cube_cost(frame, kpts, states, refs, moves=()):
    """kpts: 7 corners (autolearn.canon.cube order); states: candidate positions (54 letters, the cube
    tracker's naming); moves: moves that may have just been made (the one asked for); refs: {letter:
    colour feature} from the scan. Returns the fit or None."""
    from vision.reader import read_three_faces
    from cube.cube_state import CubeState
    from cube.moves import apply_moves
    from vision.tracker import _TURNS, _VISIBLE, LETTERS, reading_features
    reading = read_three_faces(frame, np.asarray(kpts, np.float32))
    if any(c is None for f in reading.values() for c in f):   # part of the cube off the picture
        return None
    obs = reading_features(reading)                                               # (27, 3)
    ref = np.stack([refs[x] for x in LETTERS])
    dist = np.minimum(np.linalg.norm(obs[:, None] - ref[None], axis=2), CAP)      # (27, 6)
    nearest = dist.argmin(1)
    best = None
    after = [np.arange(54)] + [apply_moves(CubeState(np.arange(54)), [m]).arr for m in moves]   # now, or the move asked for
    for si, st in enumerate(states):
        code = np.array([LETTERS.index(x) for x in st])
        for a in after:
            # held any of 24 ways: (24, 27) letters in view
            want = np.stack([code[a][perm][_VISIBLE] for _, perm, _ in _TURNS])
            costs = dist[np.arange(27)[None], want].mean(1)
            order = np.argsort(costs)
            h = int(order[0])
            if best is None or costs[h] < best[1]:
                hit = nearest == want[h]
                worst = min(float(np.mean(hit[f * 9:(f + 1) * 9])) for f in range(3))   # the worst of the 3 faces
                best = (float(np.mean(hit)), float(costs[h]), si, h, float(costs[order[1]] - costs[h]), worst)
    return best
