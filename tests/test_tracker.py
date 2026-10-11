import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube.color_detect import color_feature  # noqa: E402
from cube.cube_state import CubeState, solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_moves  # noqa: E402
from cube.scan import view_facelets  # noqa: E402
from cube.solver import solve  # noqa: E402
from vision.tracker import STEADY_FRAMES, TrackSession, decide  # noqa: E402

RGB = {'U': (240, 240, 235), 'D': (252, 216, 35), 'R': (215, 40, 55), 'L': (255, 125, 30),
       'F': (20, 175, 90), 'B': (15, 85, 205)}
REFS = {x: color_feature(c) for x, c in RGB.items()}
KPTS = [[320, 250], [200, 180], [320, 110], [440, 180], [440, 330], [320, 400], [200, 330]]
VISIBLE = view_facelets(1)


def _frame(letters, noise=0.0, rng=None):
    rgb = [np.clip(np.array(RGB[letters[i]], float) + (rng.normal(0, noise, 3) if noise else 0), 0, 255)
           for i in VISIBLE]
    return {'keypoints': KPTS, 'confident': True,
            'faces': {f: [tuple(c) for c in rgb[9 * n:9 * n + 9]] for n, f in enumerate('UFR')}}


CLOCK = [0.0]


def _hold(session, letters, frames=STEADY_FRAMES, **kw):
    """Holds the cube still for `frames` frames of a 10 fps camera."""
    out = None
    for _ in range(frames):
        CLOCK[0] += 0.1
        st = session.feed(_frame(letters, **kw), now=CLOCK[0])
        out = st if st.get('event') else (out or st)
    return out


def _scrambled(seed):
    rng = random.Random(seed)
    return apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(25)])


def _session(state):
    return TrackSession(state.arr.copy(), solve(state)[0], REFS, solve=lambda s: solve(s)[0])


def test_decide_identifies_every_single_move():
    state = _scrambled(1)
    for m in ALL_MOVES:
        after = apply_moves(state, [m]).arr
        obs = np.array([REFS[after[i]] for i in VISIBLE])
        verdict, moves, new = decide(state.arr, obs, REFS, expected='U')
        assert verdict == 'ok' and ''.join(new) == ''.join(after), m


def test_follows_a_whole_solve_with_mistakes_and_replans():
    state = _scrambled(2)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    rng = random.Random(3)
    cube, steps = state, 0
    while not s.solved and steps < 80:
        steps += 1
        expected = s.plan[s.step]
        if steps % 5 == 0:  # a deliberate mistake every fifth move
            wrong = rng.choice([m for m in ALL_MOVES if m != expected])
            cube = apply_moves(cube, [wrong])
            st = _hold(s, cube.arr)
            if ''.join(cube.arr) != ''.join(solved_state().arr):
                assert st['event'] == 'wrong' and wrong in st['message'] and st['step'] == 1
        else:
            cube = apply_moves(cube, [expected])
            st = _hold(s, cube.arr)
            assert st['event'] in ('correct', 'solved')
        assert ''.join(s.letters) == ''.join(cube.arr)  # the tracker always knows the real cube
    assert s.solved


def test_two_quick_moves_are_recognised():
    state = _scrambled(4)
    s = _session(state)
    _hold(s, s.letters)
    first = s.plan[0]
    other = next(m for m in ALL_MOVES if m[0] != first[0] and m != s.plan[1])
    cube = apply_moves(state, [first, other])
    st = _hold(s, cube.arr)
    assert st['event'] == 'wrong' and ''.join(s.letters) == ''.join(cube.arr)


def test_waits_for_home_position_and_reports_lost_after_a_while():
    state = _scrambled(5)
    s = _session(state)
    st = _hold(s, apply_moves(CubeState(state.arr.copy()), ['U2', 'R2', 'F2', 'L2']).arr)
    assert st['phase'] == 'home' and not s.home_ok          # not in the first position yet
    waiting = s.feed({'keypoints': None}, now=CLOCK[0] + 10)
    assert waiting['event'] is None and 'first position' in waiting['message']  # waiting isn't "lost"
    assert _hold(s, s.letters)['event'] == 'home'
    s.feed({'keypoints': None}, now=CLOCK[0] + 1)
    assert s.feed({'keypoints': None}, now=CLOCK[0] + 10)['event'] == 'lost'  # nothing usable for > 3 s mid-solve


def test_noise_still_tracks_and_skip_works():
    state = _scrambled(6)
    s = _session(state)
    rng = np.random.default_rng(0)
    _hold(s, s.letters, noise=8, rng=rng)
    cube = apply_moves(state, [s.plan[0]])
    assert _hold(s, cube.arr, noise=8, rng=rng)['event'] == 'correct'
    st = s.skip()
    assert st['step'] == 3 and st['event'] == 'correct'
