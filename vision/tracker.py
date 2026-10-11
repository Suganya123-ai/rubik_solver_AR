"""Live move tracking: watches the three visible sides (cube held in the home
position: Top, Front and Right toward the camera) and works out what the user
did, by comparing the picture with every outcome the app can predict.

Each candidate (no move, any single move, any two quick moves) is a reordering
of the 54 stickers, precomputed once; scoring all ~290 against the camera is a
few array lookups. Tested in bench/bench_tracking.py: with accurate corner
points it is right ~99% of the time and almost never names a wrong move; when
unsure it waits, and only after a few seconds of nothing fitting does it ask
for a rescan."""
import time

import numpy as np

from cube.color_detect import color_feature
from cube.cube_state import CubeState, solved_state
from cube.moves import ALL_MOVES, apply_moves
from cube.scan import view_facelets

LETTERS = 'URFDLB'
_VISIBLE = np.array(view_facelets(1))                    # the 27 stickers seen in the home position
CAP = 35.0                                                # one hidden/glared sticker can't dominate
PRIOR = {0: 0.0, 1: 4.0, 2: 12.0}                         # prefer simpler explanations (moves made)
EXPECTED_BONUS = 4.0                                      # the move we asked for costs nothing extra
LOST_PER_STICKER = 22.0
MARGIN = 6.0
STEADY_FRAMES = 5
STEADY_SECONDS = 0.3      # and at least this long: a fast camera repeats frames
MAX_MOVE = 0.03
LOST_AFTER_S = 3.0
HOME_MESSAGE = 'Turn the cube back to the first position: Top, Front and Right toward the camera.'


def _candidates():
    out = [((), np.arange(54))]
    for m in ALL_MOVES:
        out.append(((m,), apply_moves(CubeState(np.arange(54)), [m]).arr))
        for m2 in ALL_MOVES:
            if m2[0] != m[0]:  # same-face pairs equal a single move
                out.append(((m, m2), apply_moves(CubeState(np.arange(54)), [m, m2]).arr))
    return out


_CANDIDATES = _candidates()
_CAND_VISIBLE = np.stack([idx[_VISIBLE] for _, idx in _CANDIDATES])   # (n, 27) sticker sources


def reading_features(reading):
    """reader output {U,F,R: [9 rgb]} -> (27, 3) colour features (see
    color_feature: shading-tolerant) in _VISIBLE order."""
    return np.array([color_feature(rgb) for f in 'UFR' for rgb in reading[f]])


def decide(state_letters, obs, refs, expected=None):
    """Scores every candidate against the observed 27 stickers. Returns
    (status, moves, new_letters): status 'ok' | 'unsure' | 'lost'."""
    letter_idx = np.array([LETTERS.index(x) for x in state_letters])
    ref_mat = np.stack([refs[x] for x in LETTERS])                       # (6, 3)
    dist = np.minimum(np.linalg.norm(obs[:, None, :] - ref_mat[None], axis=2), CAP)  # (27, 6)
    cand_letters = letter_idx[_CAND_VISIBLE]                             # (n, 27)
    scores = dist[np.arange(27)[None, :], cand_letters].sum(axis=1)
    scores += np.array([PRIOR[len(m)] - (EXPECTED_BONUS if expected and m == (expected,) else 0)
                        for m, _ in _CANDIDATES])
    # Candidates that look identical from here (same visible stickers) count once.
    best = {}
    for i in np.argsort(scores):
        key = cand_letters[i].tobytes()
        if key not in best:
            best[key] = i
        if len(best) == 2:
            break
    first, second = list(best.values())
    moves = _CANDIDATES[first][0]
    new_letters = np.array(state_letters)[_CANDIDATES[first][1]]
    if scores[first] / 27 > LOST_PER_STICKER:
        return 'lost', moves, new_letters
    if scores[second] - scores[first] < MARGIN:
        return 'unsure', moves, new_letters
    return 'ok', moves, new_letters


def refs_from(letters_by_index, feats_by_index):
    """Median colour-feature reference per face letter from stickers whose letters are known."""
    out = {}
    for x in LETTERS:
        pts = [feat for letter, feat in zip(letters_by_index, feats_by_index) if letter == x]
        if pts:
            out[x] = np.median(pts, axis=0)
    return out


class TrackSession:
    """Follows the user through the solution. state_letters: the scanned cube
    (54 face letters); plan: the solution moves; refs: {letter: weighted Lab}
    from the scan; solve: function(CubeState) -> moves, for re-planning;
    face_colors: {face letter: colour name}, passed on to clients so they can
    draw the cube in its real colours."""

    def __init__(self, state_letters, plan, refs, solve, face_colors=None):
        self.letters = np.array(state_letters)
        self.plan = list(plan)
        self.step = 0
        self.refs = dict(refs)
        self.solve = solve
        self.face_colors = dict(face_colors or {})
        self.home_ok = False
        self._buffer, self._last_kpts = [], None
        self._steady_since = None
        self._lost_since = None
        self.history = []

    @property
    def solved(self):
        return ''.join(self.letters) == ''.join(solved_state().arr)

    def status(self, event=None, message=None):
        expected = self.plan[self.step] if self.step < len(self.plan) else None
        if message is None and not self.home_ok and not self.solved:
            message = HOME_MESSAGE  # always say it while waiting, so clients don't flicker
        return {'phase': 'solved' if self.solved else ('tracking' if self.home_ok else 'home'),
                'step': self.step + 1, 'total': len(self.plan), 'move': expected,
                'steady': len(self._buffer), 'needed': STEADY_FRAMES, 'event': event, 'message': message,
                'state': ''.join(self.letters), 'face_colors': self.face_colors}

    def skip(self):
        """The user says they did the shown move (fallback if tracking struggles)."""
        if self.step < len(self.plan):
            self.letters = apply_moves(CubeState(self.letters), [self.plan[self.step]]).arr
            self.step += 1
        return self.status('correct', 'Marked as done.')

    def feed(self, frame_result, now=None):
        now = time.monotonic() if now is None else now
        if self.solved:
            return self.status('solved' if self.step else None)
        kpts, faces = frame_result.get('keypoints'), frame_result.get('faces')
        if not (kpts and frame_result.get('confident') and faces and all(None not in faces[f] for f in 'UFR')):
            self._buffer, self._last_kpts = [], None
            return self._maybe_lost(now)
        k = np.asarray(kpts, float)
        size = np.mean(np.linalg.norm(k[1:] - k[0], axis=1))
        if self._last_kpts is not None and np.max(np.linalg.norm(k - self._last_kpts, axis=1)) > MAX_MOVE * size:
            self._buffer = []
        if not self._buffer:
            self._steady_since = now
        self._last_kpts = k
        self._buffer.append(reading_features(faces))
        if len(self._buffer) < STEADY_FRAMES or now - self._steady_since < STEADY_SECONDS - 1e-6:
            return self.status()
        obs = np.median(self._buffer, axis=0)
        self._buffer = []
        expected = self.plan[self.step] if self.step < len(self.plan) else None
        verdict, moves, new_letters = decide(self.letters, obs, self.refs, expected)

        if not self.home_ok:
            if verdict == 'ok' and moves == ():
                self.home_ok = True
                self._lost_since = None
                self._recalibrate(obs)
                return self.status('home', 'Cube in position. Do the first move.')
            return self._maybe_lost(now, HOME_MESSAGE)
        if verdict == 'lost':
            return self._maybe_lost(now)
        self._lost_since = None
        if verdict == 'unsure':
            return self.status('unsure')
        self._recalibrate(obs, new_letters)
        if moves == ():
            return self.status()
        self.history.append(moves)
        self.letters = new_letters
        if moves == (expected,):
            self.step += 1
            if self.solved:
                return self.status('solved', 'Solved!')
            return self.status('correct')
        # Anything else: say what happened and re-plan from the real cube.
        did = ' then '.join(moves)
        if self.solved:
            return self.status('solved', f'You did {did} -- and that solved it!')
        self.plan = self.solve(CubeState(self.letters))
        self.step = 0
        return self.status('wrong', f'You did {did} instead of {expected}. New plan: {len(self.plan)} moves.')

    def _recalibrate(self, obs, letters=None):
        letters = self.letters if letters is None else letters
        fresh = refs_from(letters[_VISIBLE], obs)
        for x, lab in fresh.items():  # follow lighting changes gently
            self.refs[x] = 0.5 * self.refs[x] + 0.5 * lab

    def _maybe_lost(self, now, message=None):
        if not self.home_ok:  # still turning the cube back after the scan: not lost, just not there yet
            return self.status(None, HOME_MESSAGE)
        if self._lost_since is None:
            self._lost_since = now
        if now - self._lost_since >= LOST_AFTER_S:
            return self.status('lost', message or "Lost track of the cube. Turn it back to the first position, "
                                                  "or scan again if the moves got mixed up.")
        return self.status(None, message)
