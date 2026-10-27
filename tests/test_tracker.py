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


def _hold(session, letters, frames=2 * STEADY_FRAMES, **kw):
    """Holds the cube still for `frames` frames of a 10 fps camera (two looks: a mistake is
    reported once a second look agrees)."""
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
    assert waiting['event'] is None and 'any way round' in waiting['message']  # waiting isn't "lost"
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


def _amount_case(want_half):
    """A scramble and a step whose planned move is a quarter turn (or a half turn)."""
    for seed in range(40):
        state = _scrambled(100 + seed)
        plan = solve(state)[0]
        for i, m in enumerate(plan[:-1]):
            if m.endswith('2') == want_half and i > 0:
                return state, i
    raise AssertionError('no such plan')


def _play_to(s, cube, step):
    """Follows the plan correctly up to `step`."""
    _hold(s, s.letters)
    while s.step < step:
        cube = apply_moves(cube, [s.plan[s.step]])
        assert _hold(s, cube.arr)['event'] == 'correct'
    return cube


def test_right_side_wrong_amount_is_fixed_with_one_turn():
    """Asked once, turned twice -> one turn back; asked twice, turned once -> once more; asked once,
    turned the other way -> a half turn. Then the plan carries on, with no undo and no redo."""
    from vision.tracker import amount_fix
    for want_half, did, fix in ((False, lambda m: m[0] + '2', lambda m: m[0] if m.endswith("'") else m[0] + "'"),
                                (True, lambda m: m[0], lambda m: m[0]),
                                (False, lambda m: m[0] if m.endswith("'") else m[0] + "'", lambda m: m[0] + '2')):
        state, step = _amount_case(want_half)
        s = _session(state)
        plan = list(s.plan)
        cube = _play_to(s, state, step)
        asked = plan[step]
        cube = apply_moves(cube, [did(asked)])
        st = _hold(s, cube.arr)
        assert st['event'] == 'wrong' and st['phase'] == 'undo', (asked, st)
        assert st['move'] == fix(asked) == amount_fix(did(asked), asked) and st['fix'] == [did(asked), asked]
        assert st['undo'] == []                                  # nothing to undo: just the one fix
        cube = apply_moves(cube, [st['move']])                   # the one turn
        st = _hold(s, cube.arr)
        assert st['event'] == 'correct' and st['message'] == 'Back on track.' and st['phase'] == 'tracking'
        assert s.step == step + 1 and st['move'] == plan[step + 1] and st['fix'] is None
        while not s.solved:                                      # and the rest of the same plan solves it
            cube = apply_moves(cube, [s.plan[s.step]])
            _hold(s, cube.arr)
        assert ''.join(cube.arr) == ''.join(solved_state().arr)


def test_a_wrong_amount_while_fixing_updates_the_fix():
    state, step = _amount_case(False)
    s = _session(state)
    cube = _play_to(s, state, step)
    asked = s.plan[step]
    cube = apply_moves(cube, [asked[0] + '2'])                   # twice instead of once
    st = _hold(s, cube.arr)
    cube = apply_moves(cube, [st['move'][0] + '2'])              # then the fix overdone too
    st = _hold(s, cube.arr)
    assert st['event'] == 'wrong' and st['fix'][1] == asked and st['undo'] == []
    cube = apply_moves(cube, [st['move']])
    assert _hold(s, cube.arr)['event'] == 'correct' and s.step == step + 1


def test_another_side_still_gets_undo():
    state = _scrambled(7)
    s = _session(state)
    cube = _play_to(s, state, 1)
    wrong = _wrong_move(s)
    st = _hold(s, apply_moves(cube, [wrong]).arr)
    assert st['event'] == 'wrong' and st['undo'] and st['fix'] is None


# ---------- any hold: the cube turned to show other sides, edge-on or face-on ----------
from vision.tracker import _TURNS  # noqa: E402


def _view_frame(phys, sides):
    """A frame showing only `sides` (of U, F, R, named from the camera) of the cube `phys`
    (54 colour letters, in the camera's naming)."""
    fr = _frame(phys)
    fr['faces'] = {f: (fr['faces'][f] if f in sides else None) for f in 'UFR'}
    if sides == 'F':
        fr['keypoints'] = FACE_ON.tolist()
    return fr


def _hold_view(session, phys, sides, frames=2 * STEADY_FRAMES):
    out = None
    for _ in range(frames):
        CLOCK[0] += 0.1
        st = session.feed(_view_frame(phys, sides), now=CLOCK[0])
        out = out if out and out.get('event') else st     # the first event
    return out


def _turn(phys, k):
    """The whole cube turned the k-th way (of _TURNS), as the camera now sees it."""
    return phys[_TURNS[k][1]]


def _quarter(axis_row):
    """Index in _TURNS of a quarter turn of the whole cube (about x, y or z)."""
    for k, (m, _, _) in enumerate(_TURNS):
        if np.trace(m) == 1 and m[axis_row, axis_row] == 1:
            return k


FACE_ON = np.array([[420, 140], [220, 140], [250, 170], [390, 170], [390, 310], [420, 340], [220, 340]], float)


def _spin(session, phys, way, sides='F'):
    """Turns the whole cube a quarter in the picture's plane (way +1: counterclockwise as the camera
    sees it), frame by frame, the model naming the corners from the view as it does: past 45 degrees
    the top edge is another one. Returns the cube as the camera now names it."""
    from vision.tracker import _SPIN
    c = FACE_ON[[0, 1, 5, 6]].mean(axis=0)
    for deg in range(15, 91, 15):
        q = int(np.floor(deg / 90 + 0.5))
        a = -np.radians(way * (deg - 90 * q))          # (y points down in the picture)
        rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        view = phys[_SPIN[way][1]] if q else phys
        fr = _view_frame(view, sides)
        fr['keypoints'] = ((FACE_ON - c) @ rot.T + c).tolist()
        CLOCK[0] += 0.1
        session.feed(fr, now=CLOCK[0])
    return phys[_SPIN[way][1]]


def test_follows_the_cube_held_any_way_round():
    """The whole solve, the cube turned a quarter turn now and then and held corner-on,
    edge-on (two sides) or face-on (one side, turned in the picture's plane too): every
    move is followed."""
    state = _scrambled(11)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    phys = state.arr.copy()
    plan = [(_quarter(0), 'UF'), (_quarter(1), 'FR'), (+1, 'F'), (_quarter(1), 'UFR'), (-1, 'F'),
            (_quarter(0), 'UF'), (_quarter(1), 'F')]
    steps = 0
    while not s.solved and steps < 40:
        if steps % 3 == 0:  # turn the whole cube to show other sides, and hold it another way
            turn, sides = plan[(steps // 3) % len(plan)]
            if sides == 'F' and turn in (1, -1):
                phys = _spin(s, phys, turn)
            else:
                phys = _turn(phys, turn)
            _hold_view(s, phys, sides, STEADY_FRAMES * 2)
        steps += 1
        if not s.status()['hold_ok']:  # as the tutor asks: hold it so the move shows (here corner-on)
            sides = 'UFR'
        move = s.plan[s.step]
        phys = apply_moves(CubeState(phys), [move]).arr
        st = _hold_view(s, phys, sides, STEADY_FRAMES * 2)
        assert st['event'] in ('correct', 'solved'), (steps, sides, move, st)
    assert s.solved


def test_turning_the_front_is_not_taken_for_turning_the_cube():
    """Face-on, the front side turned (the corners stay put) is a move, not the cube turned."""
    state = _scrambled(13)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    phys = _turn(state.arr.copy(), _quarter(1))
    _hold_view(s, phys, 'F', STEADY_FRAMES * 2)
    phys = _spin(s, phys, +1)
    _hold_view(s, phys, 'F', STEADY_FRAMES * 2)
    assert s.counts.get('spun') == 1
    move = s.plan[s.step]
    phys = apply_moves(CubeState(phys), [move]).arr
    for _ in range(STEADY_FRAMES * 2):     # the move made face-on: not judged there...
        CLOCK[0] += 0.1
        fr = _view_frame(phys, 'F')
        fr['keypoints'] = FACE_ON.tolist()
        assert s.feed(fr, now=CLOCK[0]).get('event') in (None, 'unsure')
    assert _hold_view(s, phys, 'UFR')['event'] == 'correct'   # ...but once the cube shows it


def test_held_face_on_the_tutor_asks_for_another_hold_and_judges_nothing():
    """Face-on no move can be checked well: the tutor asks for another hold and judges nothing;
    a mistake made meanwhile is caught once the cube shows two or three sides."""
    state = _scrambled(12)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    expected = s.plan[0]
    wrong = next(m for m in ALL_MOVES if m[0] not in (expected[0], 'B'))
    phys = apply_moves(state, [wrong]).arr
    st = _hold_view(s, phys, 'F')
    assert st['event'] is None and not st['hold_ok'] and s.step == 0
    st = _hold_view(s, phys, 'UFR')
    assert st['hold_ok'] and st['event'] == 'wrong' and wrong in st['message']


def test_a_one_look_glitch_is_not_a_mistake():
    """A glint or a finger making the 3 back-row stickers look like a back-side turn for one look
    (the cube not turned): no mistake reported, and the plan carries on."""
    state = _scrambled(14)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    expected = s.plan[0]
    fake = next(m for m in ('B', "B'", 'B2') if m != expected)
    glitch = apply_moves(state, [fake]).arr
    events = []
    for letters in (glitch, state.arr, state.arr):
        for _ in range(STEADY_FRAMES):
            CLOCK[0] += 0.1
            events.append(s.feed(_view_frame(letters, 'UF'), now=CLOCK[0]).get('event'))
    assert 'wrong' not in events and s.step == 0 and not s.off
    after = apply_moves(state, [expected]).arr
    assert _hold_view(s, after, 'UF')['event'] == 'correct'


def test_which_holds_show_which_moves():
    from vision.tracker import hold_shows
    assert all(hold_shows(m, 'UFR') for m in ALL_MOVES)                     # corner-on: every move
    assert not any(hold_shows(m, 'F') for m in ALL_MOVES)                   # face-on: none
    assert {m[0] for m in ALL_MOVES if hold_shows(m, 'UF')} == set('UFLR')  # not the bottom or back
    assert {m[0] for m in ALL_MOVES if hold_shows(m, 'FR')} == set('FRUD')  # not the left or back


def test_lost_after_missed_moves_finds_the_step_again():
    """Three moves done while the camera wasn't looking (more than it can explain from where it was):
    it finds the step along the plan and carries on, even with the cube held another way round."""
    state = _scrambled(21)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    cube = apply_moves(state, s.plan[:3])
    phys = _turn(cube.arr, _quarter(1))
    st = _hold_view(s, phys, 'UFR')
    assert st['event'] == 'resynced' and s.step == 3, st
    cube = apply_moves(CubeState(phys), [s.plan[3]])
    assert _hold_view(s, cube.arr, 'UFR')['event'] == 'correct'


def test_solved_while_lost_is_seen():
    """The rest of the plan done out of the camera's sight: the finished cube is recognised."""
    state = _scrambled(22)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    done = apply_moves(state, s.plan)
    st = _hold_view(s, _turn(done.arr, _quarter(0)), 'UFR')
    assert st['event'] == 'solved' and s.solved


def test_solved_by_another_route_is_seen():
    """Solved some other way (not the plan's moves): three sides each one colour is solved."""
    state = _scrambled(23)
    s = _session(state)
    assert _hold(s, s.letters)['event'] == 'home'
    st = _hold_view(s, solved_state().arr, 'UFR')
    assert st['event'] == 'solved'
