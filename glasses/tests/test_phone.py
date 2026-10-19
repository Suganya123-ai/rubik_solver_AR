"""The entry point the phone app calls (vision/phone.py): the same tutor,
given the picture and the cube's corners instead of a JPEG."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube import solver  # noqa: E402
from vision import phone  # noqa: E402

W, H = 640, 472
# A cube held corner-on, as the finder reports it (7 corners, x then y).
CORNERS = [320, 236, 220, 180, 320, 120, 420, 180, 420, 300, 320, 356, 220, 300]


def _pixels(rgb=(200, 30, 30)):
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = 255
    return rgba.tobytes()


def test_frame_without_a_cube():
    session = phone.PhoneSession(java_solver=False)
    reply = json.loads(session.frame(_pixels(), W, H, None, 0.0))
    assert reply['type'] == 'frame' and reply['keypoints'] is None
    assert (reply['width'], reply['height']) == (W, H)


def test_frame_reads_colours_in_rgb_order():
    session = phone.PhoneSession(java_solver=False)
    reply = json.loads(session.frame(_pixels((200, 30, 30)), W, H, CORNERS, 0.9))
    assert reply['confident'] and len(reply['keypoints']) == 7
    assert reply['faces']['U'][4] == [200.0, 30.0, 30.0]   # red stays red: the bytes are RGBA, not BGRA


def test_signed_bytes_are_accepted():
    """A Java byte[] holds -128..127; whatever form it arrives in, the picture is the same."""
    signed = np.frombuffer(_pixels((250, 10, 130)), np.uint8).astype(np.int8)
    assert phone._as_bytes(signed.tolist()) == _pixels((250, 10, 130))


def test_commands_and_scan_progress():
    session = phone.PhoneSession(java_solver=False)
    assert json.loads(session.command('{"type": "ping"}')) == {'type': 'pong'}
    assert json.loads(session.command('{"type": "scan_start"}'))['scan']['event'] == 'started'
    reply = json.loads(session.frame(_pixels(), W, H, CORNERS, 0.9))
    assert 'scan' in reply
    assert json.loads(session.command('{"type": "nonsense"}'))['type'] == 'error'


def test_java_solver_stands_in_for_kociemba():
    class Search:   # the shape of cs.min2phase.Search
        def solution(self, facelets, max_depth, probe_max, probe_min, verbose):
            return 'Error 2' if 'X' in facelets else "R  U2 F' "

    before = solver.kociemba
    try:
        phone.use_java_solver(Search)
        assert solver.kociemba.solve('U' * 54) == "R U2 F'"
        try:
            solver.kociemba.solve('X' * 54)
            raise AssertionError('an unsolvable cube must raise')
        except ValueError:
            pass
    finally:
        solver.kociemba = before


def test_corner_follower_moves_the_corners_with_the_cube():
    """vision/phone.py CornerFollower: the picture moves a few pixels; the 7 corners move with it."""
    import cv2
    from vision.phone import CornerFollower
    rng = np.random.default_rng(0)
    img = cv2.GaussianBlur((rng.uniform(0, 255, (472, 640)) > 200).astype(np.uint8) * 255, (0, 0), 1.5)
    kpts = np.float32([[320, 236], [250, 190], [320, 140], [390, 190], [390, 280], [320, 330], [250, 280]])
    f = CornerFollower()
    f.seen(img, kpts, 0.9)
    shift = np.float32([6.0, -4.0])
    moved = cv2.warpAffine(img, np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]), (640, 472))
    out = f.follow(moved)
    assert out is not None and np.abs(out - (kpts + shift)).max() < 0.5
    assert f.follow(np.zeros_like(img)) is None          # nothing to follow: give up (the model runs next)
