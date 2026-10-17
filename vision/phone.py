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
from . import live as _live  # noqa: E402
from .live import build_result  # noqa: E402
from .reader import read_three_faces_sampled  # noqa: E402

# The phone reads the stickers the faster way (all at once; ~15 ms a frame the other way there).
_live.read_three_faces = read_three_faces_sampled
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
    model skips (the app runs it every few frames while the cube is followed: it is the slow part).

    Points that are easy to follow (corners of stickers) are picked inside the cube where the model last
    saw it, followed into each new frame (optical flow, checked by following them back), and the motion
    that fits most of them (move, turn, size) is applied to the 7 corners. Too few points agreeing (a hand
    across the cube, a fast move, a layer turning): no corners, and the app runs the model on the next
    frame. Only a square around the cube is worked on (the phone's processor is shared with the glasses'
    own software: the whole picture took ~40 ms a frame there, this a few)."""
    MIN_POINTS = 8
    MAX_BACK = 1.0     # pixels: a point followed forward and back must land this close to where it started
    MARGIN = 0.4       # the square worked on: the cube's size plus this much of it on each side

    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.crop = None      # the last frame's square around the cube (gray)
        self.box = None       # where that square is in the frame: x0, y0, x1, y1
        self.points = None    # points to follow, in the square's pixels
        self.kpts = None
        self.confidence = 0.0

    def reset(self):
        self.crop = self.box = self.points = self.kpts = None

    def _box(self, kpts, shape):
        (x0, y0), (x1, y1) = kpts.min(0), kpts.max(0)
        m = max(x1 - x0, y1 - y0) * self.MARGIN + 8
        h, w = shape
        return (int(max(0, x0 - m)), int(max(0, y0 - m)), int(min(w, x1 + m)), int(min(h, y1 + m)))

    def _gray(self, picture, box):
        """The square `box` of the picture, grey (picture: grey, or RGBA as the phone sends it)."""
        x0, y0, x1, y1 = box
        part = picture[y0:y1, x0:x1]
        return self.cv2.cvtColor(part, self.cv2.COLOR_RGBA2GRAY) if part.ndim == 3 else part.copy()

    def seen(self, gray, kpts, confidence):
        """The model found the cube here: start following from this frame."""
        cv2 = self.cv2
        self.box = x0, y0, x1, y1 = self._box(kpts, gray.shape[:2])
        self.crop = self._gray(gray, self.box)
        mask = np.zeros(self.crop.shape, np.uint8)
        local = kpts - [x0, y0]
        centre = local.mean(0)
        hull = cv2.convexHull(local.astype(np.float32))[:, 0]
        cv2.fillConvexPoly(mask, np.round(centre + (hull - centre) * 0.85).astype(np.int32), 255)
        self.points = cv2.goodFeaturesToTrack(self.crop, maxCorners=30, qualityLevel=0.01, minDistance=6, mask=mask)
        self.kpts, self.confidence = kpts.astype(np.float32), confidence

    def follow(self, gray):
        """The corners in this frame, or None."""
        cv2 = self.cv2
        if self.crop is None or self.points is None or len(self.points) < self.MIN_POINTS:
            return None
        x0, y0, x1, y1 = self.box
        now = self._gray(gray, self.box)              # the same square in this frame
        lk = dict(winSize=(15, 15), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 15, 0.05))
        fwd, ok1, _ = cv2.calcOpticalFlowPyrLK(self.crop, now, self.points, None, **lk)
        back, ok2, _ = cv2.calcOpticalFlowPyrLK(now, self.crop, fwd, None, **lk)
        good = (ok1[:, 0] == 1) & (ok2[:, 0] == 1) & (np.linalg.norm(back - self.points, axis=2)[:, 0] < self.MAX_BACK)
        if good.sum() < self.MIN_POINTS:
            self.reset()
            return None
        m, inliers = cv2.estimateAffinePartial2D(self.points[good], fwd[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
        if m is None or inliers.sum() < self.MIN_POINTS:
            self.reset()
            return None
        kpts = ((self.kpts - [x0, y0]) @ m[:, :2].T + m[:, 2] + [x0, y0]).astype(np.float32)
        # carry on from this frame: the square moves with the cube, the points that agreed come along
        pts = fwd[good][inliers[:, 0] == 1].reshape(-1, 2) + [x0, y0]
        self.box = nx0, ny0, nx1, ny1 = self._box(kpts, gray.shape[:2])
        self.crop = self._gray(gray, self.box)
        inside = (pts[:, 0] >= nx0) & (pts[:, 0] < nx1) & (pts[:, 1] >= ny0) & (pts[:, 1] < ny1)
        self.points = (pts[inside] - [nx0, ny0]).astype(np.float32).reshape(-1, 1, 2)
        self.kpts = kpts
        return kpts


class PhoneSession:
    def __init__(self, java_solver=True):
        if java_solver:
            use_java_solver()
        self.client = LiveClient(name='phone')
        self.frames = 0
        self.follower = CornerFollower()
        import cv2
        cv2.setNumThreads(1)
        self._times = {}      # where the time goes, averaged and printed every 60 frames (logcat: python.stdout)   # the phone's cores are shared with the glasses' software: OpenCV's own threads only add waiting

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
        frame = rgba[:, :, 2::-1]  # BGR, as the rest of the code expects (a view: no copy)
        t1 = time.perf_counter()
        found, followed = None, False
        gray = rgba    # the follower makes grey only the square around the cube
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
        t2 = time.perf_counter()
        result = build_result(frame, found, hands, t0)
        t3 = time.perf_counter()
        reply = self.client.handle_result(self.frames, result)
        t4 = time.perf_counter()
        reply['ms'] = round((t4 - t0) * 1000, 1)
        reply['followed'] = followed
        out = json.dumps(reply, default=float)
        t5 = time.perf_counter()
        track = reply.get('track') or {}
        scan = reply.get('scan') or {}
        said = (track.get('phase'), track.get('step'), track.get('event') if track.get('event') != 'unsure' else None,
                track.get('message'), scan.get('event'), scan.get('message'))
        if (track or scan) and said != getattr(self, '_said', None) and any(said):
            self._said = said
            if track:
                print(f"tracker: {track.get('phase')} move {track.get('step')}/{track.get('total')} "
                      f"event={track.get('event')} '{track.get('message') or ''}'")
            else:
                print(f"scan: event={scan.get('event')} '{scan.get('message') or ''}' sides={scan.get('sides_done')}")
        if found is not None:
            for name, dt in (('picture', t1 - t0), ('follow', t2 - t1), ('read', t3 - t2), ('scan/track', t4 - t3), ('json', t5 - t4)):
                self._times[name] = self._times.get(name, 0.0) + dt
            self._times['n'] = self._times.get('n', 0) + 1
            if self._times['n'] >= 60:
                n = self._times.pop('n')
                print('tutor time a frame (cube in view): ' + ', '.join(f'{k} {v / n * 1000:.1f} ms' for k, v in self._times.items()))
                self._times = {}
        return out

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
