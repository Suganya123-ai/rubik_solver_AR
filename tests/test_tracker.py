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
from vision.tracker import STEADY_FRAMES, STEADY_SECONDS, TrackSession, decide, push_mistake, undo_moves  # noqa: E402

# Frames of the simulated 10 fps camera that make a steady hold (enough frames and enough time).
STEADY_FRAMES = max(STEADY_FRAMES, round(STEADY_SECONDS / 0.1) + 1)

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


def _session(state, on_mistake='undo'):
    return TrackSession(state.arr.copy(), solve(state)[0], REFS, solve=lambda s: solve(s)[0], on_mistake=on_mistake)


def test_decide_identifies_every_single_move():
    state = _scrambled(1)
    for m in ALL_MOVES:
        after = apply_moves(state, [m]).arr
        obs = np.array([REFS[after[i]] for i in VISIBLE])
        verdict, moves, new = decide(state.arr, obs, REFS, expected='U')
        assert verdict == 'ok' and ''.join(new) == ''.join(after), m


def test_follows_a_whole_solve_with_mistakes_and_replans():
    state = _scrambled(2)
    s = _session(state, on_mistake='replan')
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
    s = _session(state, on_mistake='replan')
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


def test_mistakes_merge_per_face():
    stack = []
    for m in ('U', 'U'):
        push_mistake(stack, m)
    assert stack == ['U2'] and undo_moves(stack) == ['U2']
    push_mistake(stack, 'U2')
    assert stack == []
    for m in ('R', "F'"):
        push_mistake(stack, m)
    assert undo_moves(stack) == ['F', "R'"]  # last mistake first


def _wrong_move(s):
    expected = s.plan[s.step]
    return next(m for m in ALL_MOVES if m[0] != expected[0] and (s.step + 1 >= len(s.plan) or m[0] != s.plan[s.step + 1][0]))


def test_a_mistake_is_undone_then_the_same_plan_continues():
    state = _scrambled(7)
    s = _session(state)
    _hold(s, s.letters)
    plan = list(s.plan)
    cube = apply_moves(state, [plan[0]])
    assert _hold(s, cube.arr)['event'] == 'correct'
    wrong = _wrong_move(s)
    cube = apply_moves(cube, [wrong])
    st = _hold(s, cube.arr)
    assert st['event'] == 'wrong' and st['phase'] == 'undo'
    assert st['move'] == st['undo'][0] and st['plan_move'] == plan[1] and wrong in st['message']
    cube = apply_moves(cube, [st['move']])            # the user undoes it
    st = _hold(s, cube.arr)
    assert st['event'] == 'undone' and st['phase'] == 'tracking'
    assert s.plan == plan and st['move'] == plan[1]   # same plan, same step
    while not s.solved:                               # and it still solves the cube
        cube = apply_moves(cube, [s.plan[s.step]])
        _hold(s, cube.arr)
    assert ''.join(s.letters) == ''.join(cube.arr)


def test_a_second_mistake_while_undoing_is_added_to_the_undo():
    state = _scrambled(8)
    s = _session(state)
    _hold(s, s.letters)
    first = _wrong_move(s)
    cube = apply_moves(state, [first])
    _hold(s, cube.arr)
    second = next(m for m in ALL_MOVES if m[0] not in (first[0], s.plan[0][0]))
    cube = apply_moves(cube, [second])
    st = _hold(s, cube.arr)
    assert st['event'] == 'wrong' and st['undo'] == [undo_moves([second])[0], undo_moves([first])[0]]
    for m in list(st['undo']):
        cube = apply_moves(cube, [m])
        st = _hold(s, cube.arr)
    assert st['event'] == 'undone' and st['move'] == s.plan[0]


def test_too_many_mistakes_gives_a_new_plan_and_replan_on_request():
    state = _scrambled(9)
    s = _session(state)
    _hold(s, s.letters)
    cube = state
    faces = [f for f in 'URFDLB' if f != s.plan[0][0]]
    for f in faces[:4]:                                # four separate mistakes
        cube = apply_moves(cube, [f])
        st = _hold(s, cube.arr)
    assert st['event'] == 'wrong' and 'new plan' in st['message'] and st['phase'] == 'tracking' and st['step'] == 1
    cube = apply_moves(cube, [_wrong_move(s)])
    assert _hold(s, cube.arr)['phase'] == 'undo'
    st = s.replan()
    assert st['event'] == 'replanned' and st['phase'] == 'tracking' and st['undo'] == []
    assert ''.join(s.letters) == ''.join(cube.arr)


def test_skip_works_while_undoing():
    state = _scrambled(10)
    s = _session(state)
    _hold(s, s.letters)
    cube = apply_moves(state, [_wrong_move(s)])
    assert _hold(s, cube.arr)['phase'] == 'undo'
    st = s.skip()
    assert st['event'] == 'undone' and ''.join(s.letters) == ''.join(state.arr)


def test_cube_held_turned_round_is_followed():
    # After the scan the user holds the cube turned 180 degrees (front <-> back, left <-> right):
    # the tracker notices, renames sides and the plan, and carries on.
    from vision.tracker import _TURNS
    state = _scrambled(30)
    s = _session(state)
    m, perm, rename = next(t for t in _TURNS if (t[0] == np.diag([-1, 1, -1])).all())
    held = state.arr[perm]                     # what the camera sees, held turned round
    plan = list(s.plan)
    st = _hold(s, np.array([x for x in held]))
    assert st['event'] in ('home', 'reoriented') and s.home_ok
    assert s.plan == [rename[mv[0]] + mv[1:] for mv in plan]
    cube = CubeState(np.array(held))
    for mv in s.plan[:3]:                      # the renamed moves, done on the held cube, are recognised
        cube = apply_moves(cube, [mv])
        assert _hold(s, cube.arr)['event'] == 'correct'
