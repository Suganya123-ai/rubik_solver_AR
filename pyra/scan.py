"""The Pyraminx scan: two views, each with an edge pointing at the camera (two whole faces in view).

The first view fixes the frame (EDGE_HOLDS[0]: its near edge's ends are called U and L, the far corners B and R).
Turned around, the second view shows the other two faces. They share no sticker with the first
view, so how the puzzle was turned (two ways: which end of the new near edge is on top) is told by
decoding both: only the right one gives a possible Pyraminx that matches the colours well. A view
that shares faces with what is scanned is placed by those shared colours instead (the same faces
again: "already scanned"; one new face: added, and a third view finishes it). Then
colours.name_colours decodes the most likely possible position.
"""
import time

import numpy as np

from cube.color_detect import color_feature

from .colours import name_colours
from .geometry import FACE_CORNERS, STICKERS
from .view import EDGE_HOLD_STICKERS, EDGE_HOLDS, HOLDS

STEADY_FRAMES = 3
STEADY_SECONDS = 0.4
MAX_MOVE = 0.03          # corner movement per 1/15 s, as a share of the puzzle's size
FRAME_GAP = 1 / 15
MIN_FACE_SHARE = 0.15    # smallest face over the largest: below this a face is a sliver (see view.face_share)
MATCH_MAX = 60           # mean colour distance of the shared stickers for a hold to count
MATCH_MARGIN = 0.7       # ...and clearly better than the next-best hold
TURN_MARGIN = 0.8        # second view: the decoded cost of one way of turning clearly below the other's
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
                    'Hold the pyramid with an edge pointing at the camera, tip up, so two faces show.' if self.views == 0
                    else 'Now turn it around to show the other two faces, again an edge toward the camera, tip up.')}

    def feed(self, fr, now=None):
        now = time.monotonic() if now is None else now
        self._now = now
        if self.result is not None:
            return {**self.status(), 'event': None}
        k, rgbs = fr.get('keypoints'), fr.get('stickers')
        if k and fr.get('confident') and fr.get('view') == 'corner':
            self._reset()
            return {**self.status('Turn it so an edge points at the camera (tip up), not a corner: two faces in view.'),
                    'event': None, 'refused': 'corner'}
        if not (k and fr.get('confident') and rgbs and None not in rgbs and len(rgbs) == 18) \
                or fr.get('face_share', 1) < MIN_FACE_SHARE:
            self._reset()
            return {**self.status(), 'event': None}
        k = np.asarray(k, float)
        size = float(np.ptp(k, 0).max())
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
        reading = [tuple(np.median([b[i] for b in self._buffer], axis=0)) for i in range(18)]
        self._reset()
        settling = self._captured_at is not None and now - self._captured_at < SETTLE_S
        if self.views == 0:
            self._add(reading, EDGE_HOLD_STICKERS[0])
            self._captured_at = now
            return {**self.status('2 of 4 faces scanned. Now turn it around to show the other two.'), 'event': 'captured'}
        outcome, stickers = self._place(reading)
        if outcome == 'unclear':
            return {**self.status(None if settling else
                                  "Couldn't tell how the pyramid was turned. Hold it still, an edge toward the camera."),
                    'event': None, 'refused': 'unclear'}
        if not any(i not in self.samples for i in stickers):
            return {**self.status(None if settling else
                                  'Those faces are already scanned. Turn it around to show the other two.'),
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
        """('add', the 18 physical stickers of this view) or ('unclear', None)."""
        seen = np.array([color_feature(c) for c in reading])
        known = {i: np.array(color_feature(np.mean(v, axis=0))) for i, v in self.samples.items()}
        fits, fresh = [], []
        for stickers in EDGE_HOLD_STICKERS:
            shared = [j for j in range(18) if stickers[j] in known]
            if not shared:
                fresh.append(stickers)
            elif len(shared) >= 9:
                fits.append((float(np.mean([np.linalg.norm(seen[j] - known[stickers[j]]) for j in shared])), stickers))
        fits.sort(key=lambda t: t[0])
        if fits and fits[0][0] < MATCH_MAX:      # faces seen before are in view: placed by their colours
            if len(fits) == 1 or fits[0][0] < MATCH_MARGIN * fits[1][0]:
                return 'add', fits[0][1]
            return 'unclear', None
        if len(fresh) == 2 and len(known) == 18:  # the other two faces: which way round, by decoding both
            costs = []
            for stickers in fresh:
                rgbs = {i: np.mean(v, axis=0) for i, v in self.samples.items()}
                rgbs.update(zip(stickers, reading))
                costs.append((name_colours([tuple(rgbs[i]) for i in range(36)])['cost'], stickers))
            costs.sort(key=lambda t: t[0])
            if costs[0][0] < TURN_MARGIN * costs[1][0]:
                return 'add', costs[0][1]
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
