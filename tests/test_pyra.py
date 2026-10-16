"""The Pyraminx model and its optimal solver."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyra.geometry import MAIN_MOVES, MOVES, TIP_MOVES, TIP_STICKERS  # noqa: E402
from pyra.model import SOLVED, apply_moves, inverse, is_solved, random_state  # noqa: E402
from pyra.solver import distance, solve, solve_body, table  # noqa: E402


def test_moves_have_order_three_and_move_the_right_stickers():
    for m in MAIN_MOVES + TIP_MOVES:
        assert is_solved(apply_moves(SOLVED, [m] * 3))
    assert (MOVES['U'] != np.arange(36)).sum() == 12   # tip 3 + centre 3 + 3 edges x 2
    assert (MOVES['u'] != np.arange(36)).sum() == 3


def test_every_position_is_counted_with_gods_number_eleven():
    # The published distribution (Wikipedia, "Pyraminx"): 933,120 positions, at most 11 moves.
    _, dist = table()
    assert np.bincount(dist).tolist() == [1, 8, 48, 288, 1728, 9896, 51808, 220111, 480467, 166276, 2457, 32]


@pytest.mark.parametrize('seed', range(5))
def test_random_scrambles_are_solved_in_the_fewest_moves(seed):
    rng = np.random.default_rng(seed)
    for _ in range(40):
        s = random_state(rng)
        body = solve_body(s)
        assert len(body) == distance(s)
        assert is_solved(apply_moves(s, solve(s)))


def test_tips_are_finished_in_one_turn_each_at_most():
    s = apply_moves(SOLVED, "u r' b")
    assert solve_body(s) == [] and sorted(solve(s)) == sorted(inverse("u r' b"))


def test_a_misread_colour_gives_an_impossible_position():
    s = apply_moves(SOLVED, "R U L'").copy()
    body = [i for i in range(36) if i not in TIP_STICKERS]
    s[body[0]], s[body[5]] = s[body[5]], s[body[0]]
    if distance(s) is None:
        with pytest.raises(ValueError):
            solve(s)


def test_edge_holds():
    """12 edge-on holds, each showing two whole faces (18 stickers), all different; the renderer labels
    its edge-on pictures with exactly these holds."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bench'))
    import render_pyra as P
    from pyra.view import EDGE_HOLDS, EDGE_HOLD_STICKERS
    assert len({tuple(h) for h in EDGE_HOLDS}) == 12
    for st in EDGE_HOLD_STICKERS:
        assert len(set(st)) == 18 and len({i // 9 for i in st}) == 2
    rng = np.random.default_rng(0)
    for _ in range(200):
        edge, pose = P.edge_on_pose(rng)
        if P.valid_edge_view(pose, edge, 0.12):
            assert P.edge_keypoints(pose, edge)[1] in EDGE_HOLDS


def test_edge_scan_needs_the_right_turn():
    """Two edge-on views on rendered frames: the same faces again are refused, the other two finish the scan."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bench'))
    import render_pyra as P
    from pyra.model import random_state
    from pyra.scan import ScanSession
    from pyra.view import face_share, read_stickers
    rng = np.random.default_rng(5)
    st = random_state(rng)

    def view(edge):
        while True:
            e, pose = P.edge_on_pose(rng, edge=edge, tilt_max=15, natural_p=0)
            k, _ = P.edge_keypoints(pose, e)
            if P.valid_edge_view(pose, e) and k.min() > 2 and k[:, 0].max() < 638 and k[:, 1].max() < 478:
                img = P.render(st, pose, rng, 'normal', hand='none')
                return {'keypoints': k.tolist(), 'confident': True, 'view': 'edge', 'face_share': face_share(k, 'edge'),
                        'stickers': read_stickers(img, k, kind='edge')}
    s, t, events = ScanSession(), 0.0, []
    for edge in (('U', 'L'), ('L', 'U'), ('R', 'B')):
        fr = view(edge)
        for _ in range(8):
            t += 0.1
            out = s.feed(fr, now=t)
            if out['event'] or out.get('refused'):
                events.append(out['event'] or out['refused'])
                break
        t += 4
    assert events == ['captured', 'nothing new', 'done'] and s.result['valid']


def test_wrong_way_is_fixed_by_one_more_turn_the_same_way():
    """The planned corner turned the other way: the fix is one more turn the way it was turned (the arrow
    flips), it lands where the plan wanted, and the plan carries on."""
    from pyra.tracker import TrackSession
    st = apply_moves(SOLVED, "B L' U")
    plan = solve(st)
    tr = TrackSession(''.join(st), plan, {L: [0, 0, 0] for L in 'FRLD'})
    e = tr.expected
    w = e[:-1] if e.endswith("'") else e + "'"
    out = tr._moved(w)
    assert out['event'] == 'wrong' and out['fix'] and out['move'] == w and out['phase'] == 'undo'
    out = tr._moved(out['move'])
    assert out['event'] == 'correct' and not out['fix'] and out['step'] == 1
    assert ''.join(tr.state) == ''.join(apply_moves(st, plan[:1]))
    while not tr.done:
        tr._moved(tr.expected)
    assert is_solved(tr.state)
