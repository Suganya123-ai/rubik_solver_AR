import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube.cube_state import solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_moves  # noqa: E402
from vision.hands import BusyHands, covered_stickers  # noqa: E402
from vision.reader import sticker_quads  # noqa: E402
from vision.scan_session import STEADY_FRAMES as SCAN_FRAMES, ScanSession  # noqa: E402
from vision.tracker import decide  # noqa: E402

from tests.test_tracker import KPTS, REFS, VISIBLE, _frame, _scrambled, _session  # noqa: E402


def _finger_over(face, i, kpts=KPTS):
    """A straight 'hand' whose index finger lies across one sticker."""
    c = sticker_quads(np.asarray(kpts, float))[face][i].mean(axis=0)
    pts = [[c[0] - 200, c[1] + 200]] * 21          # everything far away...
    pts[5], pts[6], pts[7], pts[8] = [c[0] - 30, c[1]], [c[0] - 10, c[1]], [c[0] + 10, c[1]], [c[0] + 30, c[1]]
    return {'points': pts, 'score': 1.0}


def test_a_finger_covers_the_sticker_under_it_only():
    covered = covered_stickers(KPTS, [_finger_over('F', 4)])
    assert covered['F'][4] and sum(sum(v) for v in covered.values()) <= 3
    assert covered_stickers(KPTS, []) == {f: [False] * 9 for f in 'UFR'}


def test_decide_ignores_covered_stickers():
    state = _scrambled(20)
    after = apply_moves(state, ['R']).arr
    obs = np.array([REFS[after[i]] for i in VISIBLE])
    visible = np.ones(27, bool)
    obs[3] = REFS['L'] * 0 + 50          # skin-like nonsense on one sticker...
    visible[3] = False                   # ...which a finger covers
    verdict, moves, _ = decide(state.arr, obs, REFS, expected='R', visible=visible)
    assert verdict == 'ok' and moves == ('R',)
    verdict, _, _ = decide(state.arr, obs, REFS, expected='R', visible=np.arange(27) < 8)
    assert verdict == 'unsure'           # most of the cube hidden: wait


def test_tracker_waits_while_hands_are_turning():
    state = _scrambled(21)
    s = _session(state)
    t = 0.0
    for _ in range(STEADY_FRAMES_TRACK := 8):
        t += 0.1
        st = s.feed({**_frame(s.letters), 'hands_busy': True}, now=t)
    assert st['event'] is None and not s.home_ok   # nothing judged mid-turn
    for _ in range(STEADY_FRAMES_TRACK):
        t += 0.1
        st = s.feed(_frame(s.letters), now=t)
        if st['event']:
            break
    assert st['event'] == 'home'


def test_scan_uses_only_uncovered_frames_for_a_sticker():
    views = {1: _frame(apply_moves(solved_state(), [ALL_MOVES[3]]).arr)['faces']}
    s = ScanSession()
    covered = {f: [False] * 9 for f in 'UFR'}
    covered['F'][2] = True
    t = 0.0
    for n in range(SCAN_FRAMES + 3):
        t += 0.1
        faces = {f: list(v) for f, v in views[1].items()}
        hidden = n % 2 == 0
        if hidden:
            faces['F'][2] = (200, 150, 120)   # skin over the sticker in half the frames
        s.feed({'keypoints': KPTS, 'confident': True, 'faces': faces, 'covered': covered if hidden else None}, now=t)
        if s.view == 2:
            break
    assert s.readings[1]['F'][2] == tuple(np.array(views[1]['F'][2], float))


def _shift(points, dx, dy=0):
    return [[x + dx, y + dy] for x, y in points]


def test_busy_hands_means_fingers_moving_relative_to_the_cube():
    busy = BusyHands()
    hand = _finger_over('F', 4)
    rng = np.random.default_rng(0)
    t = 0.0
    for _ in range(20):                       # holding the cube: hand and cube shake together, plus jitter
        t += 0.05
        d = rng.normal(0, 6, 2)
        pts = [[x + d[0] + rng.normal(0, 2), y + d[1] + rng.normal(0, 2)] for x, y in hand['points']]
        assert not busy.update([{'points': pts}], _shift(KPTS, *d), t)
    t += 0.05
    turned = {'points': _shift(hand['points'], 70)}  # fingers sweep across while the cube stays
    assert busy.update([turned], KPTS, t)
    assert busy.update([turned], KPTS, t + 0.1) and not busy.update([turned], KPTS, t + 1.0)  # short hold, then calm


def test_a_finger_behind_the_cube_does_not_cover_a_sticker():
    # MediaPipe guesses hidden fingers too; a sticker that still shows its own colour isn't covered.
    frame = np.full((480, 640, 3), (60, 90, 130), np.uint8)       # BGR skin-ish everywhere (palm samples)
    faces = _frame(_scrambled(22).arr)['faces']
    hand = _finger_over('F', 4)
    for p in hand['points']:
        p[0], p[1] = min(max(p[0], 0), 639), min(max(p[1], 0), 479)
    assert not covered_stickers(KPTS, [hand], frame, faces)['F'][4]
    faces['F'][4] = (130, 90, 60)                                   # now it reads as skin
    assert covered_stickers(KPTS, [hand], frame, faces)['F'][4]


def test_a_hidden_finger_jumping_around_is_not_turning():
    # MediaPipe's guesses for fingers behind the cube jump about; that alone isn't a turn.
    busy = BusyHands()
    hand = _finger_over('F', 4)
    rng = np.random.default_rng(1)
    for i in range(20):
        pts = [list(p) for p in hand['points']]
        pts[8] = [pts[8][0] + rng.normal(0, 60), pts[8][1] + rng.normal(0, 60)]   # index tip jumping
        pts[12] = [pts[12][0] + rng.normal(0, 60), pts[12][1] + rng.normal(0, 60)]  # middle tip too
        assert not busy.update([{'points': pts}], KPTS, 0.05 * i)
