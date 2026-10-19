"""3-side reading from the 7 corner keypoints (the sebastienlato/cube-solver
method, re-implemented in Python) and the move matcher from the plan."""
import cv2
import numpy as np

from cube.cube_state import FACE_OFFSET
from cube.moves import ALL_MOVES, apply_move

# Keypoint order: 0 FRU (centre), 1 FLU, 2 BLU, 3 BRU, 4 BRD, 5 FRD, 6 FLD.
FACE_KPTS = {'U': (2, 3, 0, 1), 'F': (1, 0, 5, 6), 'R': (0, 3, 4, 5)}  # TL, TR, BR, BL
VISIBLE = [(f, k) for f in 'UFR' for k in range(9)]


def read_three_faces(frame, kpts):
    """Lab colour of the 27 visible stickers, sampled from the middle of each
    cell through a per-face homography (median ignores glare specks)."""
    lab_img = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_img[..., 0] *= 100 / 255
    lab_img[..., 1:] -= 128
    out = []
    unit = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    for f in 'UFR':
        Hm = cv2.getPerspectiveTransform(unit, np.float32([kpts[i] for i in FACE_KPTS[f]]))
        for k in range(9):
            r, c = divmod(k, 3)
            a, b = (c + 0.3) / 3, (c + 0.7) / 3
            d, e = (r + 0.3) / 3, (r + 0.7) / 3
            quad = cv2.perspectiveTransform(np.float32([[[a, d], [b, d], [b, e], [a, e]]]), Hm)[0]
            mask = np.zeros(frame.shape[:2], np.uint8)
            cv2.fillConvexPoly(mask, quad.astype(np.int32), 255)
            px = lab_img[mask > 0]
            out.append(np.median(px, axis=0) if len(px) else np.array([50.0, 0, 0]))
    return np.array(out)


def visible_letters(arr):
    return tuple(arr[FACE_OFFSET[f] + k] for f, k in VISIBLE)


def references(lab27, arr, fallback):
    """Per-colour reference Lab from a frame whose state is known (the frame
    before the move): the tracker keeps re-calibrating to current lighting."""
    letters = visible_letters(arr)
    refs = {}
    for L in 'URFDLB':
        pts = [lab27[i] for i, x in enumerate(letters) if x == L]
        refs[L] = np.median(pts, axis=0) if pts else fallback[L]
    return refs


def candidates(arr, expected):
    """(label, state_arr, prior penalty): no move, every single move, every pair."""
    from cube.cube_state import CubeState
    s = CubeState(np.array(arr))
    out = [('none', s.arr, 0.0)]
    for m in ALL_MOVES:
        s1 = apply_move(s, m)
        out.append((m, s1.arr, 0.0 if m == expected else 4.0))
        for m2 in ALL_MOVES:
            if m2[0] == m[0]:
                continue  # same-face pairs equal a single move
            out.append((m + ' ' + m2, apply_move(s1, m2).arr, 12.0))
    return out


def decide(lab27, refs, cands, cap=35.0, lost_per_sticker=22.0, margin=6.0):
    best = {}
    for label, arr, prior in cands:
        vis = visible_letters(arr)
        d = np.linalg.norm(lab27 - np.array([refs[x] for x in vis]), axis=1)
        score = float(np.minimum(d, cap).sum()) + prior
        if vis not in best or score < best[vis][0]:
            best[vis] = (score, label)
    ranked = sorted(best.values())
    (s1, l1), (s2, _) = ranked[0], ranked[1]
    if s1 / 27 > lost_per_sticker:
        return 'lost', l1
    if s2 - s1 < margin:
        return 'unsure', l1
    return 'ok', l1
