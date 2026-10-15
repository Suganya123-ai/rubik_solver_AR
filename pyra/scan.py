"""The Pyraminx scan: views are captured whenever the puzzle is held still
corner-on, until all 36 stickers have been seen.

The first view fixes the frame (its near corner is called U, the one at k1 L,
and so on). A corner-on view shows 3 of the 4 faces, so a second view with
another corner toward the camera shows the 4th face plus two already scanned:
those tell how the puzzle was turned (whichever of the 12 holds fits their
colours best, clearly better than the next). Stickers seen in several views
are averaged. Then colours.name_colours decodes the most likely possible
position.
"""
import time

import numpy as np

from cube.color_detect import color_feature

from .colours import name_colours
from .geometry import FACE_CORNERS, STICKERS
from .view import HOLD_STICKERS, HOLDS

STEADY_FRAMES = 3
STEADY_SECONDS = 0.4
MAX_MOVE = 0.03          # corner movement per 1/15 s, as a share of the puzzle's size
FRAME_GAP = 1 / 15
MIN_FACE_SHARE = 0.15    # smallest face over the largest: below this a face is a sliver (see view.face_share)
MATCH_MAX = 60           # mean colour distance of the shared stickers for a hold to count
MATCH_MARGIN = 0.7       # ...and clearly better than the next-best hold
SETTLE_S = 3.0           # after a capture, quiet while the user turns the puzzle


def _piece_of(i):
    """Stickers that belong to the same piece as sticker i (for flagging whole pieces)."""
    f, k, tri = STICKERS[i]
    c = tri.mean(0)
    if k < 6:   # tips and centres: the 3 stickers at the same corner, same layer
        corner = FACE_CORNERS[f][k % 3]
        return [j for j, (f2, k2, _) in enumerate(STICKERS) if (k2 < 3) == (k < 3) and k2 < 6
                and FACE_CORNERS[f2][k2 % 3] == corner]
    others = [j for j, (f2, k2, t2) in enumerate(STICKERS) if k2 >= 6 and f2 != f]
    return [i, min(others, key=lambda j: np.linalg.norm(STICKERS[j][2].mean(0) - c))]


class ScanSession:
    def __init__(self):
        self.views = 0
        self.samples = {}          # sticker -> list of rgb
        self.result = None
        self.rgbs = None
        self._buffer = []
        self._last_kpts = None
        self._last_time = None
        self._steady_since = None
        self._captured_at = None
        self._now = 0.0

    def known(self):
        return sorted(self.samples)

    def faces_done(self):
        return sum(all(9 * f + k in self.samples for k in range(9)) for f in range(4))

    def status(self, message=None):
        progress = 0 if not self._buffer or self._steady_since is None else int(
            10 * min(1.0, len(self._buffer) / STEADY_FRAMES, (self._now - self._steady_since) / STEADY_SECONDS))
        return {'phase': 'done' if self.result else ('view1' if self.views == 0 else 'view2'),
                'steady': progress, 'needed': 10, 'message': message, 'faces_done': self.faces_done(),
                'stickers_done': len(self.samples), 'views': self.views,
                'instruction': None if self.result else (
                    'Hold the pyramid with a corner pointing at the camera, so three faces show.' if self.views == 0
                    else 'Now point another corner at the camera, so the face you have not shown yet is in view.')}

    def feed(self, fr, now=None):
        now = time.monotonic() if now is None else now
        self._now = now
        if self.result is not None:
            return {**self.status(), 'event': None}
        k, rgbs = fr.get('keypoints'), fr.get('stickers')
        if not (k and fr.get('confident') and rgbs and None not in rgbs) or fr.get('face_share', 1) < MIN_FACE_SHARE:
            self._reset()
            return {**self.status(), 'event': None}
        k = np.asarray(k, float)
        size = np.mean(np.linalg.norm(k[1:] - k[0], axis=1))
        gap = min(3.0, max(1.0, (now - self._last_time) / FRAME_GAP)) if self._last_time is not None else 1.0
        self._last_time = now
        if self._last_kpts is not None and np.max(np.linalg.norm(k - self._last_kpts, axis=1)) > MAX_MOVE * size * gap:
            self._buffer = []
        if not self._buffer:
            self._steady_since = now
        self._last_kpts = k
        self._buffer.append(rgbs)
        if len(self._buffer) < STEADY_FRAMES or now - self._steady_since < STEADY_SECONDS - 1e-6:
            return {**self.status(), 'event': None}
        reading = [tuple(np.median([b[i] for b in self._buffer], axis=0)) for i in range(27)]
        self._reset()
        settling = self._captured_at is not None and now - self._captured_at < SETTLE_S
        if self.views == 0:
            self._add(reading, HOLD_STICKERS[0])
            self._captured_at = now
            return {**self.status('3 of 4 faces scanned. Now point another corner at the camera.'), 'event': 'captured'}
        outcome, stickers = self._place(reading)
        if outcome == 'unclear':
            return {**self.status(None if settling else
                                  "Couldn't tell how the pyramid was turned. Hold it still, a corner toward the camera."),
                    'event': None, 'refused': 'unclear'}
        if not any(i not in self.samples for i in stickers):
            return {**self.status(None if settling else
                                  'Those faces are already scanned. Point another corner at the camera.'),
                    'event': None, 'refused': 'nothing new'}
        self._add(reading, stickers)
        self._captured_at = now
        if len(self.samples) == 36:
            self.rgbs = [tuple(np.mean(self.samples[i], axis=0)) for i in range(36)]
            self.result = scan_result(self.rgbs)
            return {**self.status('All 4 faces scanned.'), 'event': 'done'}
        return {**self.status(f'{self.faces_done()} of 4 faces scanned.'), 'event': 'captured'}

    def _add(self, reading, stickers):
        for rgb, i in zip(reading, stickers):
            self.samples.setdefault(i, []).append(rgb)
        self.views += 1

    def _place(self, reading):
        seen = np.array([color_feature(c) for c in reading])
        known = {i: np.array(color_feature(np.mean(v, axis=0))) for i, v in self.samples.items()}
        fits = []
        for stickers in HOLD_STICKERS:
            shared = [j for j in range(27) if stickers[j] in known]
            if len(shared) < 9:
                continue
            fits.append((float(np.mean([np.linalg.norm(seen[j] - known[stickers[j]]) for j in shared])), stickers))
        fits.sort(key=lambda t: t[0])
        if fits and fits[0][0] < MATCH_MAX and (len(fits) == 1 or fits[0][0] < MATCH_MARGIN * fits[1][0]):
            return 'add', fits[0][1]
        return 'unclear', None

    def _reset(self):
        self._buffer = []
        self._last_kpts = None
        self._steady_since = None


def scan_result(rgbs, locked=None):
    """The decoded position from 36 colours; `locked` {sticker: letter} are the user's corrections."""
    res = name_colours(rgbs)
    state = res['state']
    doubtful = set(res['doubtful'])
    doubtful = sorted({j for i in doubtful for j in _piece_of(i)})
    if locked:
        state = state.copy()
        for i, letter in locked.items():
            state[int(i)] = letter
        doubtful = [i for i in doubtful if str(i) not in {str(x) for x in locked}]
    from .solver import distance
    return {'state': ''.join(state), 'valid': distance(state) is not None, 'doubtful': doubtful,
            'colour_of': res['colour_of'], 'confidence': res['confidence']}


__all__ = ['ScanSession', 'scan_result', 'HOLDS']
