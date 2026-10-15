"""The scan during the live view: captures a view of the cube automatically
each time it is held steady, until all six sides have been seen, then names
the colours.

The first view fixes which side is the top, front and right. Every later view
may show the cube any way round: sides already scanned that appear in it tell
how the cube was turned (their stickers must match), and the sides not seen
yet are added. Two views are enough if the opposite corner is shown; turning
the cube round with the same side on top and then showing the bottom takes
three. (Insisting on one exact flip was the commonest way to get stuck.)

Steady = YOLO is confident and the 7 corner points move less than 3% of the
cube's size between frames, for at least STEADY_FRAMES frames AND
STEADY_SECONDS (a fast camera can repeat one picture several times in a
fraction of a second, e.g. mid-flip). The capture is the median of those
frames' sticker colours, which smooths camera noise."""
import time

import numpy as np

from cube.color_detect import color_feature
from cube.cube_state import FACES
from cube.scan import VIEW_INSTRUCTIONS, _misfit, all_holds, scan_any_hold, scan_result, view_facelets

STEADY_FRAMES = 3      # and STEADY_SECONDS: time decides (at a normal 15 frames/s that's 6+ frames);
                       # a slow link (e.g. a forwarded port, ~4 frames/s) only needs 3
STEADY_SECONDS = 0.4
MAX_MOVE = 0.03          # fraction of the cube's size per 1/15 s (more allowed between frames further apart)
FRAME_GAP = 1 / 15          # fraction of the cube's size
FLIP_GRACE_S = 3.0        # after view 1 is captured, give the user this long to flip before warning
MATCH_MAX = 32            # stickers of an already-scanned side must be this close (mean) to count as that side
MATCH_MARGIN = 0.75       # ...and clearly closer than the next-best way of turning the cube
OPPOSITE_FIT_MAX = 16     # a view with no scanned side in it: accept as the opposite corner if the cube fits this well
SAME_SIDE_DISTANCE = 27   # mean colour-feature distance below which two sides are the same side (renders: same <= 25, different >= 29)
SAME_CENTRE_DISTANCE = 20 # a way of turning the cube that puts a centre on a scanned centre must match it this well
                          # (red and orange centres read ~30 apart; the same centre twice reads much closer)


_HOLDS = [(m, view_facelets(2, m)) for m in all_holds()]   # each way of holding: which sticker is where in the picture


class ScanSession:
    def __init__(self):
        self.views = 0            # views captured so far
        self.readings = {}        # {view number: {'U','F','R': [9 rgb]}} as captured (for the recording)
        self.known = {}           # {facelet index 0..53: rgb} everything scanned so far, in cube positions
        self._buffer = []
        self._last_kpts = None
        self._last_time = None
        self._now = 0.0
        self._steady_since = None
        self._captured_at = None
        self.result = None
        self.rgbs = None          # {face: [9 rgb]} once all six sides are in
        self.rejected = None      # the last reading that added nothing / couldn't be placed (for the recording)

    @property
    def view(self):               # (older name: 1 while waiting for the first view, then 2)
        return 1 if self.views == 0 else 2

    def sides_done(self):
        return [f for i, f in enumerate(FACES) if all(9 * i + k in self.known for k in range(9))]

    def _steady_progress(self):
        return _progress(self._buffer, self._steady_since, self._now)

    def status(self, message=None):
        done = self.sides_done()
        return {'phase': 'done' if self.result else f'view{self.view}',
                'instruction': None if self.result else VIEW_INSTRUCTIONS[self.view],
                'steady': self._steady_progress(), 'needed': 10, 'message': message,
                'captured': list(range(1, self.views + 1)), 'sides_done': len(done),
                # centre colours of the sides already scanned
                'scanned_centres': [[round(v) for v in self.known[9 * FACES.index(f) + 4]] for f in done]}

    def feed(self, frame_result, now=None):
        """frame_result: the live view's per-frame result. Returns a status
        dict; status['event'] is 'captured' when a view just added sides and
        'done' when all six are in (then self.result is set)."""
        now = time.monotonic() if now is None else now
        self._now = now
        if self.result is not None:
            return {**self.status(), 'event': None}
        kpts, faces = frame_result.get('keypoints'), frame_result.get('faces')
        # (Hands turning the cube aren't checked here: the cube's corners must be
        # still for a capture anyway, and a false "turning" blocked captures.)
        if not (kpts and frame_result.get('confident') and faces and all(None not in faces[f] for f in 'UFR')):
            self._reset_steady()
            return {**self.status(), 'event': None}
        k = np.asarray(kpts, float)
        size = np.mean(np.linalg.norm(k[1:] - k[0], axis=1))
        gap = min(3.0, max(1.0, (now - self._last_time) / FRAME_GAP)) if self._last_time is not None else 1.0
        self._last_time = now
        if self._last_kpts is not None and np.max(np.linalg.norm(k - self._last_kpts, axis=1)) > MAX_MOVE * size * gap:
            self._buffer = []
        if not self._buffer:
            self._steady_since = now
        self._last_kpts = k
        self._buffer.append((faces, frame_result.get('covered')))
        if len(self._buffer) < STEADY_FRAMES or now - self._steady_since < STEADY_SECONDS - 1e-6:
            return {**self.status(), 'event': None}

        reading = {f: [_uncovered_median(self._buffer, f, i) for i in range(9)] for f in 'UFR'}
        self._reset_steady()
        if self.views == 0:  # the first view decides which side is the top, front and right
            self._add(reading, view_facelets(1))
            self._captured_at = now
            return {**self.status('3 of 6 sides scanned. Now turn the cube to show the others.'), 'event': 'captured'}

        outcome, where = self._place(reading)
        # Right after a capture the same sides are still in view while the user gets
        # ready to turn the cube: say nothing for a moment.
        settling = self._captured_at is not None and now - self._captured_at < FLIP_GRACE_S
        if outcome == 'nothing new':
            self.rejected = reading
            left = 6 - len(self.sides_done())
            message = None if settling else (
                f"These sides are already scanned. Turn the cube to show the {left} side{'s' if left != 1 else ''} "
                'not shown yet (the underside, if you have only turned it round).')
            return {**self.status(message), 'event': None, 'refused': 'nothing new'}
        if outcome == 'unclear':
            self.rejected = reading
            message = None if settling else (
                "Couldn't tell how the cube was turned. Hold it still with a corner toward the camera, "
                'three sides showing.')
            return {**self.status(message), 'event': None, 'refused': 'unclear'}
        if outcome == 'opposite':  # the opposite corner: all three sides new, read as a whole cube
            self.views += 1
            self.readings[self.views] = reading
            self.rgbs, self.result = where
            return {**self.status('All 6 sides scanned.'), 'event': 'done'}
        self._add(reading, where)
        self._captured_at = now
        done = len(self.sides_done())
        if len(self.known) == 54:
            self.rgbs = {f: [self.known[9 * i + k] for k in range(9)] for i, f in enumerate(FACES)}
            self.result = scan_result(self.rgbs)
            return {**self.status('All 6 sides scanned.'), 'event': 'done'}
        left = 6 - done
        return {**self.status(f"{done} of 6 sides scanned. Now show the {left} side{'s' if left != 1 else ''} left."),
                'event': 'captured'}

    def _add(self, reading, facelets):
        """Stores a view's stickers at their cube positions (new ones only)."""
        flat = [rgb for f in 'UFR' for rgb in reading[f]]
        for index, rgb in zip(facelets, flat):
            self.known.setdefault(index, rgb)
        self.views += 1
        self.readings[self.views] = reading

    def _place(self, reading):
        """Works out how the cube is turned in this view from the already-scanned
        sides in it. Returns ('add', facelets), ('nothing new', None),
        ('opposite', (rgbs, result)) or ('unclear', None)."""
        flat = [rgb for f in 'UFR' for rgb in reading[f]]
        seen = np.array([color_feature(c) for c in flat])
        known = {i: color_feature(c) for i, c in self.known.items()}
        fits = []
        for _, facelets in _HOLDS:
            # Stickers of this view that would land on already-scanned ones (centres left
            # out of the score: a logo or a glossy cap makes two different centres look alike).
            shared = [k for k in range(27) if facelets[k] in known and k % 9 != 4]
            if len(shared) < 8:
                continue
            # ...but a centre landing on a scanned centre of another colour rules this way out:
            # some scrambles leave two sides with the same outer stickers, only the centres differ.
            if any(facelets[k] in known and np.linalg.norm(seen[k] - known[facelets[k]]) >= SAME_CENTRE_DISTANCE
                   for k in (4, 13, 22)):
                continue
            cost = float(np.mean([np.linalg.norm(seen[k] - known[facelets[k]]) for k in shared]))
            fits.append((cost, facelets))
        fits.sort(key=lambda t: t[0])
        if fits and fits[0][0] < MATCH_MAX and (len(fits) == 1 or fits[0][0] < MATCH_MARGIN * fits[1][0]):
            facelets = fits[0][1]
            return ('add', facelets) if any(i not in self.known for i in facelets) else ('nothing new', None)
        if self.views == 1:  # no scanned side recognised: it may be the opposite corner (three new sides)
            rgbs, result = scan_any_hold({1: self.readings[1], 2: reading})
            if result['valid'] and _misfit(rgbs, result['colors']) < OPPOSITE_FIT_MAX:
                return 'opposite', (rgbs, result)
        return 'unclear', None

    def _reset_steady(self):
        self._buffer = []
        self._last_kpts = None
        self._steady_since = None

    def _side_seen_before(self, reading):
        """A correct turn shows three new sides. Returns the picture position
        ('U' top, 'F' left, 'R' right) of a view-2 side whose 8 outer stickers
        match a view-1 side (turned any way), else None. Centres are left
        out: a logo or glossy centre cap can make two different centres look alike."""
        first = [_outer_ring(self.readings[1][f]) for f in 'UFR']
        for f in 'UFR':
            ring = _outer_ring(reading[f])
            for old in first:
                for turn in range(4):  # a quarter turn of a side moves its ring by 2
                    if np.mean(np.linalg.norm(ring - np.roll(old, 2 * turn, axis=0), axis=1)) < SAME_SIDE_DISTANCE:
                        return f
        return None

    def _shares_a_side_with_view1(self, reading):
        return self._side_seen_before(reading) is not None


def _uncovered_median(buffer, face, i):
    """A sticker's colour over the steady frames, using only frames where no
    finger covered it (all frames if it was covered in every one)."""
    clear = [faces[face][i] for faces, covered in buffer if not (covered and covered[face][i])]
    return tuple(np.median(clear or [faces[face][i] for faces, _ in buffer], axis=0))


_RING = (0, 1, 2, 5, 8, 7, 6, 3)  # a side's outer stickers, clockwise


def _outer_ring(colours):
    return np.array([color_feature(colours[i]) for i in _RING])


def _progress(buffer, since, now):
    """How far a steady hold has got, 0..10: both enough frames and enough time are needed."""
    if not buffer or since is None:
        return 0
    return int(10 * min(1.0, len(buffer) / STEADY_FRAMES, (now - since) / STEADY_SECONDS))
