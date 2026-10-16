"""The self-improving loop's checks (autolearn/): the corner order is recovered from the picture, the colour
check accepts right corners and rejects wrong ones, and a retrained model is only switched to when it is
no worse anywhere and better on the real frames."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bench'))

from autolearn import canon, retrain, verify  # noqa: E402


def test_cube_corner_order_from_any_model_order():
    import render as R
    rng = np.random.default_rng(0)
    wrong = 0
    for _ in range(300):
        k = R.gt_keypoints(R.corner_pose_wide(rng))
        shift = int(rng.integers(3)) * 2             # the model's order, turned by whole faces...
        order = [0] + [1 + (shift + j) % 6 for j in range(6)]
        if rng.uniform() < 0.5:                      # ...and/or the other way round
            order = order[:2] + order[2:][::-1]
        out = canon.cube(k[order])
        wrong += out is not None and not np.allclose(out, k, atol=1e-3)
    assert wrong == 0   # a frame it can't order is skipped, never mislabelled


def test_pyramid_corner_order():
    import render_pyra as P
    rng = np.random.default_rng(1)
    for _ in range(200):
        e, pose = P.edge_on_pose(rng)
        if P.valid_edge_view(pose, e, 0.12):
            k, _ = P.edge_keypoints(pose, e)
            assert np.allclose(canon.pyra(k[[1, 0, 3, 2]], 'edge'), k, atol=1e-3)
        near, pose = P.corner_on_pose(rng)
        if P.valid_view(pose, near, 0.08):
            k, _ = P.keypoints(pose, near)
            assert np.allclose(canon.pyra(k[[0, 3, 1, 2]], 'corner'), k, atol=1e-3)


def test_colour_check_accepts_right_corners_and_rejects_wrong_ones():
    import render_pyra as P
    from cube.color_detect import color_feature
    from pyra.model import random_state
    rng = np.random.default_rng(2)
    feats = {L: color_feature(P.BASE_RGB[P.LETTER_TO_COLOR[L]]) for L in 'FRLD'}
    right, wrong = [], []
    while len(right) < 20:
        st = random_state(rng)
        e, pose = P.edge_on_pose(rng, tilt_max=20, natural_p=0)
        if not P.valid_edge_view(pose, e, 0.15):
            continue
        k, _ = P.edge_keypoints(pose, e)
        if k.min() < 40 or k[:, 0].max() > 600 or k[:, 1].max() > 440:
            continue
        img = P.render(st, pose, rng, 'normal', style='stickered', hand='none')
        right.append(verify.pyra_cost(img, k, 'edge', [''.join(st)], feats)[0])
        moved = k + np.ptp(k, 0).max() * 0.5 * np.array([1.0, 0.0])          # found in the wrong place
        w = verify.pyra_cost(img, moved, 'edge', [''.join(st)], feats)
        if w is not None:
            wrong.append(w[0])
    assert np.median(right) >= 0.9 and np.mean(np.array(right) >= 0.8) >= 0.9
    assert np.mean(np.array(wrong) >= 0.8) <= 0.1


def _scores(real_found, real_colours, drawn_found=99.0, n=40):
    return {'real': {'n': n, 'found': real_found, 'error': 4.0, 'colours': real_colours, 'empty': 0, 'false': None},
            'other_puzzle': {'n': 0, 'found': None, 'error': None, 'empty': 50, 'false': 0.0},
            'drawn': {'n': 300, 'found': drawn_found, 'error': 3.0, 'empty': 20, 'false': 0.0}}


def test_gate():
    assert retrain.gate(_scores(80.0, 0.90), _scores(85.0, 0.90))[0]                     # finds more real frames
    assert retrain.gate(_scores(80.0, 0.90), _scores(80.0, 0.93))[0]                     # corners sit better
    assert not retrain.gate(_scores(80.0, 0.90), _scores(80.0, 0.90))[0]                 # no better: keep
    assert not retrain.gate(_scores(80.0, 0.90), _scores(90.0, 0.85))[0]                 # finds more, sits worse
    assert not retrain.gate(_scores(80.0, 0.90), _scores(90.0, 0.92, drawn_found=95.0))[0]  # forgot drawn pictures
    assert not retrain.gate(_scores(80.0, 0.90, n=10), _scores(95.0, 0.95, n=10))[0]     # too few real tests to judge
