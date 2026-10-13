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


class PhoneSession:
    def __init__(self, java_solver=True):
        if java_solver:
            use_java_solver()
        self.client = LiveClient(name='phone')
        self.frames = 0

    def frame(self, pixels, width, height, keypoints, confidence, hands_json=None):
        """One camera frame.

        pixels: width*height*4 bytes, RGBA (an Android ARGB_8888 bitmap's
        bytes). keypoints: 14 numbers (7 corners, x then y, in this picture's
        pixels) or None if the cube was not found. Returns the reply as JSON.
        """
        t0 = time.perf_counter()
        rgba = np.frombuffer(_as_bytes(pixels), np.uint8).reshape(height, width, 4)
        frame = np.ascontiguousarray(rgba[:, :, 2::-1])  # BGR, as the rest of the code expects
        found = None
        if keypoints is not None:
            found = (np.asarray(list(keypoints), np.float32).reshape(7, 2), float(confidence))
        hands = json.loads(hands_json) if hands_json else []
        self.frames += 1
        reply = self.client.handle_result(self.frames, build_result(frame, found, hands, t0))
        reply['ms'] = round((time.perf_counter() - t0) * 1000, 1)
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
