import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube.cube_state import FACE_OFFSET, FACES, solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_moves  # noqa: E402
from cube.scan import assemble, piece_colors, read_cube, scan_result, view_center_faces, view_facelets  # noqa: E402

RGB = {'U': (240, 240, 235), 'D': (252, 216, 35), 'R': (215, 40, 55), 'L': (255, 125, 30),
       'F': (20, 175, 90), 'B': (15, 85, 205)}
NAME = {'U': 'white', 'D': 'yellow', 'R': 'red', 'L': 'orange', 'F': 'green', 'B': 'blue'}


def _scrambled(seed=1):
    rng = random.Random(seed)
    return apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(25)])


def _views(state, noise=None):
    """What the reader would return for both views of `state` (perfect colours)."""
    rgb = [RGB[x] for x in state.arr]
    if noise:
        for i, c in noise.items():
            rgb[i] = c
    out = {}
    for view in (1, 2):
        idx = view_facelets(view)
        out[view] = {vf: [rgb[i] for i in idx[9 * n:9 * n + 9]] for n, vf in enumerate('UFR')}
    return out


def test_two_views_cover_every_sticker_once():
    assert sorted(view_facelets(1) + view_facelets(2)) == list(range(54))
    assert view_center_faces(1) == ['U', 'F', 'R']
    assert view_center_faces(2) == ['D', 'L', 'B']


def test_view2_is_a_rigid_turn_of_the_cube():
    # The flip keeps the cube's handedness: picture corner 0 (Top-Front-Right) in
    # view 2 is the cube's Down-Left-Back corner, with stickers D, L, B.
    idx = view_facelets(2)
    corner = {idx[8] // 9, idx[9 + 2] // 9, idx[18] // 9}  # picture U8, F2, R0 meet at keypoint 0
    assert {FACES[i] for i in corner} == {'D', 'L', 'B'}


@pytest.mark.parametrize('seed', range(5))
def test_perfect_scan_reads_the_exact_cube(seed):
    state = _scrambled(seed)
    colors, result, got = read_cube(assemble(_views(state)))
    assert result.ok and ''.join(got.arr) == ''.join(state.arr)
    assert colors == {f: [NAME[x] for x in state.arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}


def test_piece_matching_fixes_a_misread_sticker():
    state = _scrambled(3)
    # Read a non-centre sticker as the opposite face's colour (impossible on its piece).
    i = next(i for i in range(54) if i % 9 != 4 and state.arr[i] == 'U')
    rgbs = assemble(_views(state, noise={i: RGB['D']}))
    colors = piece_colors(rgbs, {f: NAME[f] for f in FACES})
    assert colors == {f: [NAME[x] for x in state.arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}


def test_scan_result_flags_nothing_on_a_clean_scan_and_respects_locks():
    state = _scrambled(4)
    rgbs = assemble(_views(state))
    res = scan_result(rgbs)
    assert res['valid'] and res['doubtful'] == []
    face, k = 'F', 0
    true = NAME[state.arr[FACE_OFFSET[face]]]
    locked = scan_result(rgbs, locked={(face, k): true})
    assert locked['colors'][face][k] == true and (face, k) not in locked['doubtful']


# ---------- ScanSession (automatic capture) ----------
from vision.scan_session import STEADY_FRAMES, STEADY_SECONDS, ScanSession  # noqa: E402

# Frames of the simulated 10 fps camera that make a steady hold (enough frames and enough time).
STEADY_FRAMES = max(STEADY_FRAMES, round(STEADY_SECONDS / 0.1) + 1)

KPTS = [[320, 250], [200, 180], [320, 110], [440, 180], [440, 330], [320, 400], [200, 330]]


SCAN_CLOCK = [0.0]


def _feed(session, frame):
    """One frame of a 10 fps camera."""
    SCAN_CLOCK[0] += 0.1
    return session.feed(frame, now=SCAN_CLOCK[0])


def _frame(reading, shift=0.0, confident=True):
    return {'keypoints': [[x + shift, y] for x, y in KPTS], 'confident': confident, 'faces': reading}


def test_scan_session_captures_two_steady_views_and_reads_the_cube():
    state = _scrambled(7)
    views = _views(state)
    s = ScanSession()
    events = [_feed(s, _frame(views[1]))['event'] for _ in range(STEADY_FRAMES)]
    assert events[-1] == 'captured' and s.view == 2
    events = [_feed(s, _frame(views[2]))['event'] for _ in range(STEADY_FRAMES)]
    assert events[-1] == 'done'
    assert s.result['valid'] and ''.join(s.result['state'].arr) == ''.join(state.arr)


def test_scan_session_waits_while_the_cube_moves_or_is_unsure():
    views = _views(_scrambled(8))
    s = ScanSession()
    for i in range(STEADY_FRAMES * 2):
        st = _feed(s, _frame(views[1], shift=40 * i))  # moving a lot every frame
        assert st['event'] is None and st['steady'] <= 1
    for _ in range(STEADY_FRAMES * 2):
        assert _feed(s, _frame(views[1], confident=False))['steady'] == 0


def test_scan_session_rejects_the_same_view_twice():
    views = _views(_scrambled(9))
    s = ScanSession()
    for _ in range(STEADY_FRAMES):
        _feed(s, _frame(views[1]))
    for _ in range(STEADY_FRAMES):
        st = _feed(s, _frame(views[1]))  # straight after the capture: no warning yet, they're about to flip
    assert st['event'] is None and st['message'] is None and s.view == 2
    messages = [_feed(s, _frame(views[1]))['message'] for _ in range(6 * STEADY_FRAMES)]  # still not flipped
    assert any(m and 'already scanned' in m for m in messages) and s.view == 2


# ---------- live protocol (scan check / accept / tracking) ----------
def test_live_client_scan_check_accept_and_tracking():
    from vision.live_session import LiveClient, ProtocolError

    state = _scrambled(10)
    client = LiveClient()
    with pytest.raises(ProtocolError):
        client.handle_command({'type': 'scan_check'})          # no scan yet
    client.scan_rgbs = assemble(_views(state))
    checked = client.handle_command({'type': 'scan_check', 'locked': {'F0': NAME[state.arr[FACE_OFFSET['F']]]}})
    res = checked['scan_result']
    assert checked['type'] == 'scan_result' and res['valid'] and res['doubtful'] == []
    started = client.handle_command({'type': 'scan_accept', 'colors': res['colors']})
    assert started['type'] == 'track' and 0 < len(started['moves']) <= 22
    assert started['track']['phase'] == 'home' and started['track']['description']
    bad = {f: list(v) for f, v in res['colors'].items()}
    bad['U'] = ['white'] * 9
    assert client.handle_command({'type': 'scan_accept', 'colors': bad})['type'] == 'error'
    for command in ({'type': 'scan_check', 'locked': {'Q9': 'pink'}}, {'type': 'nope'}, {'type': 'scan_accept'}):
        with pytest.raises(ProtocolError):
            client.handle_command(command)
    with pytest.raises(ProtocolError):
        client.handle_frame(b'\x00' * 3_000_000)               # oversized frame
    assert client.handle_command({'type': 'ping'}) == {'type': 'pong'}


def test_scan_session_needs_real_time_not_just_repeated_frames():
    # A fast camera repeating one picture (e.g. mid-flip) must not count as holding still.
    views = _views(_scrambled(11))
    s = ScanSession()
    t = 100.0
    for _ in range(STEADY_FRAMES * 3):
        t += 0.01                                   # 15 frames in 0.15 s
        assert s.feed(_frame(views[1]), now=t)['event'] is None


def test_view2_rejected_if_any_side_repeats():
    state = _scrambled(12)
    views = _views(state)
    half = {'U': views[2]['U'], 'F': views[1]['F'], 'R': views[2]['R']}  # half-flipped: Front still showing
    s = ScanSession()
    for _ in range(STEADY_FRAMES):
        _feed(s, _frame(views[1]))
    for _ in range(STEADY_FRAMES):
        st = _feed(s, _frame(half))
    assert st['event'] is None and s.view == 2


def test_view2_rejected_if_a_side_repeats_turned():
    # Same side, but the cube was turned in the hand: its stickers come round by a quarter turn.
    views = _views(_scrambled(13))
    ring = (0, 1, 2, 5, 8, 7, 6, 3)
    turned = list(views[1]['F'])
    for a, b in zip(ring, ring[2:] + ring[:2]):
        turned[b] = views[1]['F'][a]
    s = ScanSession()
    for _ in range(STEADY_FRAMES):
        _feed(s, _frame(views[1]))
    assert s._shares_a_side_with_view1({'U': views[2]['U'], 'F': turned, 'R': views[2]['R']})
    assert not s._shares_a_side_with_view1(views[2])


LOGO = (235, 205, 205)  # a glossy logo cap on a red centre reads nearly white


def test_logo_centre_is_named_by_its_side_not_its_reading():
    state = _scrambled(14)
    noise = {FACE_OFFSET['R'] + 4: LOGO}
    res = scan_result(assemble(_views(state, noise=noise)))
    assert res['valid'] and ''.join(res['state'].arr) == ''.join(state.arr)
    assert res['centers'] == NAME
    assert ('R', 4) in res['doubtful']  # it reads like another colour: the user confirms it


def test_a_confirmed_centre_is_kept():
    state = _scrambled(15)
    rgbs = assemble(_views(state, noise={FACE_OFFSET['R'] + 4: LOGO}))
    res = scan_result(rgbs, locked={('R', 4): 'red'})
    assert res['centers']['R'] == 'red' and ('R', 4) not in res['doubtful'] and res['valid']


def test_shaded_side_does_not_turn_red_into_orange():
    # A side in shade is darker overall; hue, not brightness, decides the colour.
    state = _scrambled(16)
    dark = {i: tuple(0.45 * v for v in RGB[x]) for i, x in enumerate(state.arr) if i // 9 == FACES.index('F')}
    res = scan_result(assemble(_views(state, noise=dark)))
    assert res['valid'] and ''.join(res['state'].arr) == ''.join(state.arr)


def test_a_slow_link_still_captures_after_a_short_hold():
    # Through a forwarded port only ~4 frames/s arrive, and the hand drifts more between them.
    views = _views(_scrambled(17))
    s = ScanSession()
    t, events = 100.0, []
    for i in range(4):
        t += 0.25
        events.append(s.feed(_frame(views[1], shift=4.0 * i), now=t)['event'])  # small drift between frames
    assert 'captured' in events


def test_view2_accepted_whichever_way_the_new_corner_is_held():
    # All three ways of holding the opposite corner show the three new sides: each reads the right cube.
    from cube.scan import _VIEW2_HOLDS, scan_any_hold, view_facelets
    state = _scrambled(18)
    rgb = [RGB[x] for x in state.arr]
    first = {vf: [rgb[i] for i in view_facelets(1)[9 * n:9 * n + 9]] for n, vf in enumerate('UFR')}
    for hold in _VIEW2_HOLDS:
        idx = view_facelets(2, hold)
        second = {vf: [rgb[i] for i in idx[9 * n:9 * n + 9]] for n, vf in enumerate('UFR')}
        _, res = scan_any_hold({1: first, 2: second})
        assert res['valid'] and ''.join(res['state'].arr) == ''.join(state.arr)


def _view_held(state, hold):
    """What the reader returns for the cube held the given way (a rotation matrix)."""
    from cube.scan import view_facelets
    rgb = [RGB[x] for x in state.arr]
    idx = view_facelets(2, hold)
    return {vf: [rgb[i] for i in idx[9 * n:9 * n + 9]] for n, vf in enumerate('UFR')}


def _capture(session, reading):
    """Holds a view still until something happens; returns that status."""
    last = None
    for _ in range(12 * STEADY_FRAMES):
        last = _feed(session, _frame(reading))
        if last['event'] or last['message']:
            return last
    return last


def test_turning_the_cube_round_then_showing_the_underside_scans_it_in_three_views():
    # The natural way: same side on top, cube turned round (two new sides), then the underside.
    import numpy as np
    from cube.scan import all_holds
    state = _scrambled(19)
    round_the_back = np.diag([-1, 1, -1])                       # half a turn about the vertical: Top, Back, Left
    underside = next(m for m in all_holds() if _faces_seen(m) == ['D', 'F', 'L'] or set(_faces_seen(m)) == {'D', 'F', 'L'})
    s = ScanSession()
    st = _capture(s, _views(state)[1])
    assert st['event'] == 'captured' and st['sides_done'] == 3
    st = _capture(s, _view_held(state, round_the_back))
    assert st['event'] == 'captured' and st['sides_done'] == 5 and '1 side left' in st['message']
    st = _capture(s, _view_held(state, underside))
    assert st['event'] == 'done' and s.result['valid'] and ''.join(s.result['state'].arr) == ''.join(state.arr)


def _faces_seen(hold):
    from cube.scan import view_facelets
    idx = view_facelets(2, hold)
    return [FACES[idx[9 * i + 4] // 9] for i in range(3)]


def test_a_view_of_sides_already_scanned_asks_for_the_missing_ones():
    state = _scrambled(20)
    s = ScanSession()
    _capture(s, _views(state)[1])
    seen = [_feed(s, _frame(_views(state)[1])) for _ in range(10 * STEADY_FRAMES)]   # same view, past the grace period
    said = [st for st in seen if st['message']]
    assert said and said[-1]['refused'] == 'nothing new' and '3 sides' in said[-1]['message'] and s.views == 1


def test_a_view_that_cannot_be_placed_is_not_added():
    state = _scrambled(21)
    views = _views(state)
    s = ScanSession()
    _capture(s, views[1])
    nonsense = {'U': views[2]['U'], 'F': views[1]['F'], 'R': views[2]['R']}   # not a way a cube can be held
    seen = [_feed(s, _frame(nonsense)) for _ in range(10 * STEADY_FRAMES)]
    assert all(st['event'] is None for st in seen) and s.views == 1
    assert any(st.get('refused') == 'unclear' for st in seen)


def test_a_lookalike_side_with_another_centre_is_not_taken_for_a_scanned_one():
    # Seen on a real cube (14 Oct 2026): a scramble left two sides with the same outer
    # stickers; only the centres differed. Such a side must not be placed on the scanned one.
    from vision.scan_session import ScanSession
    views = _views(_scrambled(15))
    s = ScanSession()
    s._add(views[1], view_facelets(1))
    lookalike = list(views[1]['F'])
    lookalike[4] = views[2]['R'][4]   # the new side's own centre
    outcome, where = s._place({'U': views[2]['U'], 'F': views[2]['F'], 'R': lookalike})
    assert outcome != 'nothing new'
    if outcome == 'add':   # never by putting this side where the old one is
        assert where[22] != view_facelets(1)[13]
