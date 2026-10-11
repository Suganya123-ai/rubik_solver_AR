"""Two-view scan during the live view: captures each view automatically once
the cube is held steady, then names the colours.

Steady = YOLO is confident and the 7 corner points move less than 3% of the
cube's size between frames, for at least STEADY_FRAMES frames AND
STEADY_SECONDS (a fast camera can repeat one picture several times in a
fraction of a second, e.g. mid-flip). The capture is the median of those
frames' sticker colours, which smooths camera noise."""
import time

import numpy as np

from cube.color_detect import color_feature
from cube.scan import VIEW_INSTRUCTIONS, assemble, scan_result

STEADY_FRAMES = 5
STEADY_SECONDS = 0.4
MAX_MOVE = 0.03          # fraction of the cube's size
SAME_SIDE_DISTANCE = 27   # mean colour-feature distance below which two sides are the same side (renders: same <= 25, different >= 29)


class ScanSession:
    def __init__(self):
        self.view = 1
        self.readings = {}
        self._buffer = []
        self._last_kpts = None
        self._steady_since = None
        self.result = None

    def status(self, message=None):
        return {'phase': 'done' if self.result else f'view{self.view}',
                'instruction': None if self.result else VIEW_INSTRUCTIONS[self.view],
                'steady': len(self._buffer), 'needed': STEADY_FRAMES, 'message': message,
                'captured': sorted(self.readings)}

    def feed(self, frame_result, now=None):
        """frame_result: the live view's per-frame result. Returns a status
        dict; status['event'] is 'captured' when a view was just captured and
        'done' when both views are in (then self.result is set)."""
        now = time.monotonic() if now is None else now
        if self.result is not None:
            return {**self.status(), 'event': None}
        kpts, faces = frame_result.get('keypoints'), frame_result.get('faces')
        if not (kpts and frame_result.get('confident') and faces and all(None not in faces[f] for f in 'UFR')):
            self._reset_steady()
            return {**self.status(), 'event': None}
        k = np.asarray(kpts, float)
        size = np.mean(np.linalg.norm(k[1:] - k[0], axis=1))
        if self._last_kpts is not None and np.max(np.linalg.norm(k - self._last_kpts, axis=1)) > MAX_MOVE * size:
            self._buffer = []
        if not self._buffer:
            self._steady_since = now
        self._last_kpts = k
        self._buffer.append(faces)
        if len(self._buffer) < STEADY_FRAMES or now - self._steady_since < STEADY_SECONDS - 1e-6:
            return {**self.status(), 'event': None}

        reading = {f: [tuple(np.median([b[f][i] for b in self._buffer], axis=0)) for i in range(9)] for f in 'UFR'}
        self._reset_steady()
        if self.view == 2 and self._shares_a_side_with_view1(reading):
            return {**self.status('That looks like the first view again. Flip the cube as shown.'), 'event': None}
        self.readings[self.view] = reading
        if self.view == 1:
            self.view = 2
            return {**self.status('View 1 captured. Now flip the cube.'), 'event': 'captured'}
        self.result = scan_result(assemble(self.readings))
        return {**self.status('Both views captured.'), 'event': 'done'}

    def _reset_steady(self):
        self._buffer = []
        self._last_kpts = None
        self._steady_since = None

    def _shares_a_side_with_view1(self, reading):
        """A correct flip shows three new sides. Any view-2 side whose 8 outer
        stickers match a view-1 side (turned any way) means the cube wasn't
        flipped, or only half-flipped. Centres are left out: a logo or
        glossy centre cap can make two different centres look alike."""
        first = [_outer_ring(self.readings[1][f]) for f in 'UFR']
        for f in 'UFR':
            ring = _outer_ring(reading[f])
            for old in first:
                for turn in range(4):  # a quarter turn of a side moves its ring by 2
                    if np.mean(np.linalg.norm(ring - np.roll(old, 2 * turn, axis=0), axis=1)) < SAME_SIDE_DISTANCE:
                        return True
        return False


_RING = (0, 1, 2, 5, 8, 7, 6, 3)  # a side's outer stickers, clockwise


def _outer_ring(colours):
    return np.array([color_feature(colours[i]) for i in _RING])
