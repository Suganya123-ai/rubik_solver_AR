"""The tutor running inside the phone app (android_phone/), with no laptop.

The app finds the cube itself (the same model, converted to ONNX and run by
ONNX Runtime) and calls in here once per camera frame with the picture and
the corner points; everything after that -- reading the colours, the scan,
solving, following the moves, undo -- is the same code the laptop server
runs. The replies are the same JSON the web page already understands
(docs/PROTOCOL.md), so the page is unchanged.

Python runs in the app through Chaquopy (Python 3.10, NumPy 1.26, OpenCV
4.5). Nothing is recorded to disk on the phone.
"""
import json
import os
import time

import numpy as np

os.environ.setdefault('RUBIK_RECORD', '0')   # the app's code folder is read-only
os.environ.setdefault('RUBIK_HANDS', '0')    # hands, when used, are found by the app

from cube import solver as _solver  # noqa: E402
from .live import build_result  # noqa: E402
from .live_session import LiveClient, ProtocolError  # noqa: E402


class _JavaSolver:
    """Stands in for the `kociemba` package (which has no Android build): the
    same two-phase method from the min2phase Java library bundled in the app.
    Same cube string (U R F D L B) and the same move names."""

    def __init__(self, search_class):
        self._search_class = search_class

    def solve(self, facelets):
        # 21 moves at most; a short search is enough to get ~19-21 move answers in a few ms.
        answer = str(self._search_class().solution(facelets, 21, 100000, 0, 0)).strip()
        if answer.startswith('Error'):
            raise ValueError(answer)
        return ' '.join(answer.split())


def use_java_solver(search_class=None):
    if search_class is None:
        from java import jclass  # Chaquopy
        search_class = jclass('cs.min2phase.Search')
    _solver.kociemba = _JavaSolver(search_class)


class CornerFollower:
    """Moves the cube's 7 corners from the last frame the model looked at to this one, for the frames the
    model skips (the app runs it every other frame while the cube is followed: it is the slow part).

    Points that are easy to follow (corners of stickers) are picked inside the cube where the model last
    saw it, followed into each new frame (optical flow, checked by following them back), and the motion
    that fits most of them (move, turn, size) is applied to the 7 corners. Too few points agreeing (a hand
    across the cube, a fast move, a layer turning): no corners, and the app runs the model on the next
    frame."""
    MIN_POINTS = 8
    MAX_BACK = 1.0     # pixels: a point followed forward and back must land this close to where it started

    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.gray = None
        self.points = None
        self.kpts = None
        self.confidence = 0.0

    def reset(self):
        self.gray = self.points = self.kpts = None

    def seen(self, gray, kpts, confidence):
        """The model found the cube here: start following from this frame."""
        cv2 = self.cv2
        mask = np.zeros(gray.shape, np.uint8)
        centre = kpts.mean(0)
        hull = cv2.convexHull(kpts.astype(np.float32))[:, 0]
        cv2.fillConvexPoly(mask, np.round(centre + (hull - centre) * 0.85).astype(np.int32), 255)
        self.points = cv2.goodFeaturesToTrack(gray, maxCorners=40, qualityLevel=0.01, minDistance=6, mask=mask)
        self.gray, self.kpts, self.confidence = gray, kpts.astype(np.float32), confidence

    def follow(self, gray):
        """The corners in this frame, or None."""
        cv2 = self.cv2
        if self.gray is None or self.points is None or len(self.points) < self.MIN_POINTS:
            return None
        lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
        fwd, ok1, _ = cv2.calcOpticalFlowPyrLK(self.gray, gray, self.points, None, **lk)
        back, ok2, _ = cv2.calcOpticalFlowPyrLK(gray, self.gray, fwd, None, **lk)
        good = (ok1[:, 0] == 1) & (ok2[:, 0] == 1) & (np.linalg.norm(back - self.points, axis=2)[:, 0] < self.MAX_BACK)
        if good.sum() < self.MIN_POINTS:
            self.reset()
            return None
        m, inliers = cv2.estimateAffinePartial2D(self.points[good], fwd[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
        if m is None or inliers.sum() < self.MIN_POINTS:
            self.reset()
            return None
        self.kpts = (self.kpts @ m[:, :2].T + m[:, 2]).astype(np.float32)
        self.points = fwd[good][inliers[:, 0] == 1].reshape(-1, 1, 2)
        self.gray = gray
        return self.kpts


class PhoneSession:
    def __init__(self, java_solver=True):
        if java_solver:
            use_java_solver()
        self.client = LiveClient(name='phone')
        self.frames = 0
        self.follower = CornerFollower()

    def frame(self, pixels, width, height, keypoints, confidence, hands_json=None, follow=False):
        """One camera frame.

        pixels: width*height*4 bytes, RGBA (an Android ARGB_8888 bitmap's
        bytes). keypoints: 14 numbers (7 corners, x then y, in this picture's
        pixels) or None if the cube was not found. follow: the model skipped this frame; move the
        corners from the last frame instead (CornerFollower). Returns the reply as JSON (with
        'followed': True when the corners came from following).
        """
        t0 = time.perf_counter()
        rgba = np.frombuffer(_as_bytes(pixels), np.uint8).reshape(height, width, 4)
        frame = np.ascontiguousarray(rgba[:, :, 2::-1])  # BGR, as the rest of the code expects
        found, followed = None, False
        import cv2
        gray = cv2.cvtColor(rgba, cv2.COLOR_RGBA2GRAY)
        if keypoints is not None:
            found = (np.asarray(list(keypoints), np.float32).reshape(7, 2), float(confidence))
            if found[1] >= 0.5:
                self.follower.seen(gray, found[0], found[1])
            else:
                self.follower.reset()
        elif follow:
            kpts = self.follower.follow(gray)
            if kpts is not None:
                found, followed = (kpts, self.follower.confidence), True
        else:
            self.follower.reset()
        hands = json.loads(hands_json) if hands_json else []
        self.frames += 1
        reply = self.client.handle_result(self.frames, build_result(frame, found, hands, t0))
        reply['ms'] = round((time.perf_counter() - t0) * 1000, 1)
        reply['followed'] = followed
        return json.dumps(reply, default=float)

    def command(self, text):
        """A command from the page (scan_start, scan_accept, track_skip...), as JSON text."""
        try:
            reply = self.client.handle_command(json.loads(text))
        except (ProtocolError, ValueError) as e:
            reply = {'type': 'error', 'code': 'BAD_REQUEST', 'message': str(e)}
        return json.dumps(reply, default=float)


def _as_bytes(pixels):
    if isinstance(pixels, (bytes, bytearray, memoryview)):
        return pixels
    try:
        return bytes(pixels)             # a Java byte[] (Chaquopy copies it in one go)
    except (TypeError, ValueError):      # signed bytes that bytes() refuses
        return np.asarray(pixels, np.int8).tobytes()


def self_check():
    """Solves a scrambled cube with whatever solver is in use (the app's self-test)."""
    from cube.cube_state import solved_state
    from cube.moves import apply_moves
    scramble = "R U F' L2 D B R' U2 F D' L B2 U R2 F2".split()
    t0 = time.perf_counter()
    moves = _solver.solve(apply_moves(solved_state(), scramble))[0]
    return f'{len(moves)} moves in {(time.perf_counter() - t0) * 1000:.0f} ms: {" ".join(moves)}'
