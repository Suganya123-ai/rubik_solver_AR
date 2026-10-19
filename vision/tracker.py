"""Live move tracking: watches the three visible sides (cube held in the home
position: Top, Front and Right toward the camera) and works out what the user
did, by comparing the picture with every outcome the app can predict.

Each candidate (no move, any single move, any two quick moves) is a reordering
of the 54 stickers, precomputed once; scoring all ~290 against the camera is a
few array lookups. Tested in bench/bench_tracking.py: with accurate corner
points it is right ~99% of the time and almost never names a wrong move; when
unsure it waits, and only after a few seconds of nothing fitting does it ask
for a rescan."""
import itertools
import time

import numpy as np

from cube.color_detect import color_feature
from cube.cube_state import CubeState, solved_state
from cube.moves import ALL_MOVES, FACELET_DIR, INDEX_TO_POS, POS_TO_INDEX, apply_moves
from cube.scan import view_facelets

LETTERS = 'URFDLB'
_VISIBLE = np.array(view_facelets(1))                    # the 27 stickers seen in the home position
CAP = 35.0                                                # one hidden/glared sticker can't dominate
PRIOR = {0: 0.0, 1: 4.0, 2: 12.0}                         # prefer simpler explanations (moves made)
EXPECTED_BONUS = 4.0                                      # the move we asked for costs nothing extra
LOST_PER_STICKER = 22.0
MARGIN = 6.0
STEADY_FRAMES = 3      # and STEADY_SECONDS: time decides (at a normal 15 frames/s that's 6+ frames);
                       # a slow link (e.g. a forwarded port, ~4 frames/s) only needs 3
STEADY_SECONDS = 0.3      # and at least this long: a fast camera repeats frames
MAX_MOVE = 0.03          # fraction of the cube's size per 1/15 s (more allowed between frames further apart)
FRAME_GAP = 1 / 15
LOST_AFTER_S = 3.0
MAX_UNDO = 3              # more mistakes than this to undo: make a new plan instead
HOME_MESSAGE = 'Turn the cube back to the first position: Top, Front and Right toward the camera.'


def _candidates():
    out = [((), np.arange(54))]
    for m in ALL_MOVES:
        out.append(((m,), apply_moves(CubeState(np.arange(54)), [m]).arr))
        for m2 in ALL_MOVES:
            if m2[0] != m[0]:  # same-face pairs equal a single move
                out.append(((m, m2), apply_moves(CubeState(np.arange(54)), [m, m2]).arr))
    return out


def inverse(move):
    return move if move.endswith('2') else (move[0] if move.endswith("'") else move + "'")


def _quarter_turns(move):
    return 2 if move.endswith('2') else (3 if move.endswith("'") else 1)


def push_mistake(stack, move):
    """Adds a move to the mistakes to undo, merging turns of the same face
    (U then U is U2; U then U' cancels out)."""
    if stack and stack[-1][0] == move[0]:
        q = (_quarter_turns(stack.pop()) + _quarter_turns(move)) % 4
        if q:
            stack.append(move[0] + {1: '', 2: '2', 3: "'"}[q])
    else:
        stack.append(move)


def amount_fix(done, asked):
    """The right side turned by the wrong amount (done R2, asked R): the one turn of that side that goes
    from where the cube is to where the plan wanted (here R': one back), instead of undoing what was done
    and doing the move again. None if no turn is needed (they are the same)."""
    q = (_quarter_turns(asked) - _quarter_turns(done)) % 4
    return asked[0] + {1: '', 2: '2', 3: "'"}[q] if q else None


def undo_moves(stack):
    """The moves that take the cube back to where the mistakes started."""
    return [inverse(m) for m in reversed(stack)]


def _whole_cube_turns():
    """The 24 ways to hold the cube, each as (rotation matrix, sticker
    permutation, face renaming). After holding it turned by `m`: the sticker
    now at index j is the one that was at perm[j], and a side that was face X
    is now face rename[X]."""
    out = []
    for axes in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            m = np.zeros((3, 3), int)
            for row, (col, sign) in enumerate(zip(axes, signs)):
                m[row, col] = sign
            if round(np.linalg.det(m)) != 1:
                continue  # mirror images aren't real ways to hold a cube
            perm = np.zeros(54, int)
            for i in range(54):
                pos, d = INDEX_TO_POS[i]
                perm[POS_TO_INDEX[(tuple(int(v) for v in m @ np.array(pos)), tuple(int(v) for v in m @ np.array(d)))]] = i
            rename = {x: next(y for y, dy in FACELET_DIR.items() if tuple(m @ np.array(dx)) == tuple(dy))
                      for x, dx in FACELET_DIR.items()}
            out.append((m, perm, rename))
    return out


_TURNS = _whole_cube_turns()
REORIENT_GAIN = 0.85  # another way of holding the cube must fit this much better (score ratio) to switch to it
WELL_FITTING = 12.0   # a judgement fitting this well (per sticker) with at most one move is trusted as is


def rename_move(move, rename):
    return rename[move[0]] + move[1:]


_CANDIDATES = _candidates()
_CAND_VISIBLE = np.stack([idx[_VISIBLE] for _, idx in _CANDIDATES])   # (n, 27) sticker sources


def reading_features(reading):
    """reader output {U,F,R: [9 rgb]} -> (27, 3) colour features (see
    color_feature: shading-tolerant) in _VISIBLE order."""
    return np.array([color_feature(rgb) for f in 'UFR' for rgb in reading[f]])


MIN_VISIBLE = 12  # fewer stickers than this in view (hands over the rest): don't judge


def decide(state_letters, obs, refs, expected=None, visible=None, info=None):
    """Scores every candidate against the observed 27 stickers. visible: 27
    bools, False for stickers a hand covers (they count for nothing). info: a
    dict to fill with the scores (for logging). Returns (status, moves,
    new_letters): status 'ok' | 'unsure' | 'lost'."""
    letter_idx = np.array([LETTERS.index(x) for x in state_letters])
    ref_mat = np.stack([refs[x] for x in LETTERS])                       # (6, 3)
    dist = np.minimum(np.linalg.norm(obs[:, None, :] - ref_mat[None], axis=2), CAP)  # (27, 6)
    visible = np.ones(27, bool) if visible is None else np.asarray(visible, bool)
    dist[~visible] = 0.0
    n_visible = int(visible.sum())
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
    if info is not None:
        info.update(best=list(moves), second=list(_CANDIDATES[second][0]), visible=n_visible,
                    per_sticker=round(float(scores[first]) / max(n_visible, 1), 1),
                    margin=round(float(scores[second] - scores[first]), 1))
    if n_visible < MIN_VISIBLE:
        return 'unsure', moves, new_letters
    if scores[first] / n_visible > LOST_PER_STICKER:
        return 'lost', moves, new_letters
    if scores[second] - scores[first] < MARGIN * n_visible / 27:
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
    draw the cube in its real colours. on_mistake: 'undo' (show how to turn
    back, then carry on with the same plan) or 'replan' (solve again from
    wherever the cube is)."""

    def __init__(self, state_letters, plan, refs, solve, face_colors=None, on_mistake='undo'):
        self.letters = np.array(state_letters)
        self.plan = list(plan)
        self.step = 0
        self.refs = dict(refs)
        self.solve = solve
        self.face_colors = dict(face_colors or {})
        self.on_mistake = on_mistake
        self.off = []                  # mistakes still to undo (merged per face)
        self.counts = {}               # what happened to the frames, for the log (see LiveClient)
        self.on_judgement = None       # optional callback(dict) after each judgement (session recording)
        self._resume_letters = None    # the cube where the plan carries on once they're undone
        self.home_ok = False
        self._buffer, self._last_kpts = [], None
        self._steady_since = None
        self._last_time = None
        self._now = 0.0
        self._lost_since = None
        self._lost_reported = False
        self.history = []
        self.fixing = None             # (done, asked) while the move shown is an amount fix (amount_fix)

    @property
    def solved(self):
        return ''.join(self.letters) == ''.join(solved_state().arr)

    def _reorient(self, obs, visible, score_now):
        """Tries every other way of holding the cube (with no move, or one
        move made meanwhile). If one fits clearly better, switches to it:
        the state, colours, plan and undo list are renamed to the new
        orientation (the same physical moves), and tracking carries on."""
        best = None
        for m, perm, rename in _TURNS:
            if np.array_equal(m, np.eye(3)):
                continue
            letters = np.array([rename[x] for x in self.letters[perm]])
            refs = {rename[x]: v for x, v in self.refs.items()}
            info = {}
            verdict, moves, _ = decide(letters, obs, refs, None, visible, info)
            if verdict == 'ok' and len(moves) <= 1 and (best is None or info['per_sticker'] < best[0]):
                best = (info['per_sticker'], perm, rename)
        if best is None or best[0] > REORIENT_GAIN * score_now:
            return False
        _, perm, rename = best
        self.letters = np.array([rename[x] for x in self.letters[perm]])
        self.refs = {rename[x]: v for x, v in self.refs.items()}
        self.face_colors = {rename[x]: c for x, c in self.face_colors.items()}
        self.plan = [rename_move(mv, rename) for mv in self.plan]
        self.off = [rename_move(mv, rename) for mv in self.off]
        if self._resume_letters is not None:
            self._resume_letters = np.array([rename[x] for x in np.asarray(self._resume_letters)[perm]])
        self._count('reoriented')
        return True

    def _count(self, what):
        self.counts[what] = self.counts.get(what, 0) + 1

    def position_hint(self):
        """How to hold the cube, in its own colours (the centres never move)."""
        c = self.face_colors
        if not all(c.get(f) for f in 'UFR'):
            return 'Hold it in the first position: Top, Front and Right toward the camera.'
        return f"Hold it with {c['U']} on top, {c['F']} facing you and {c['R']} on the right."

    def home_message(self):
        return 'Turn the cube back to the first position. ' + self.position_hint()

    def _plan_move(self):
        return self.plan[self.step] if self.step < len(self.plan) else None

    def _expected(self):
        """The move to show: the next undo move while off track, else the plan's next move."""
        return undo_moves(self.off)[0] if self.off else self._plan_move()

    def _steady_progress(self):
        return _progress(self._buffer, self._steady_since, self._now)

    def status(self, event=None, message=None):
        expected = self._expected()
        if message is None and not self.home_ok and not self.solved:
            message = self.home_message()  # always say it while waiting, so clients don't flicker
        if self.solved:
            phase = 'solved'
        elif not self.home_ok:
            phase = 'home'
        else:
            phase = 'undo' if self.off or self.fixing else 'tracking'
        return {'phase': phase, 'undo': undo_moves(self.off), 'plan_move': self._plan_move(),
                'fix': list(self.fixing) if self.fixing and not self.off else None,
                'step': self.step + 1, 'total': len(self.plan), 'move': expected,
                'steady': self._steady_progress(), 'needed': 10, 'event': event, 'message': message,
                'state': ''.join(self.letters), 'face_colors': self.face_colors}

    def skip(self):
        """The user says they did the shown move (fallback if tracking struggles)."""
        move = self._expected()
        if move is None:
            return self.status()
        self.letters = apply_moves(CubeState(self.letters), [move]).arr
        if self.off:
            push_mistake(self.off, move)
            if not self.off:
                return self.status('undone', f'Back on track. Now do {self._plan_move()}.')
        else:
            self.step += 1
            self.fixing = None
        return self.status('correct', 'Marked as done.')

    def replan(self):
        """Gives up on undoing and solves again from where the cube is now."""
        self.off, self._resume_letters = [], None
        self.fixing = None
        if not self.solved:
            self.plan = self.solve(CubeState(self.letters))
            self.step = 0
        return self.status('replanned', f'New plan: {len(self.plan)} moves.')

    def feed(self, frame_result, now=None):
        now = time.monotonic() if now is None else now
        self._now = now
        if self.solved:  # (the 'solved' event was already sent with the move that solved it)
            return self.status()
        kpts, faces = frame_result.get('keypoints'), frame_result.get('faces')
        self._count('frames')
        if frame_result.get('hands_busy'):  # mid-turn: judge the result once the hands stop
            self._count('hands turning')
            self._buffer, self._last_kpts, self._lost_since = [], None, None
            return self.status()
        if not (kpts and frame_result.get('confident') and faces and all(None not in faces[f] for f in 'UFR')):
            self._count('no cube')
            self._buffer, self._last_kpts = [], None
            return self._maybe_lost(now)
        k = np.asarray(kpts, float)
        size = np.mean(np.linalg.norm(k[1:] - k[0], axis=1))
        gap = min(3.0, max(1.0, (now - self._last_time) / FRAME_GAP)) if self._last_time is not None else 1.0
        self._last_time = now
        if self._last_kpts is not None and np.max(np.linalg.norm(k - self._last_kpts, axis=1)) > MAX_MOVE * size * gap:
            self._count('cube moving')
            self._buffer = []
        if not self._buffer:
            self._steady_since = now
        self._last_kpts = k
        covered = frame_result.get('covered')
        self._buffer.append((reading_features(faces),
                             np.array([not (covered and covered[f][i]) for f in 'UFR' for i in range(9)])))
        if len(self._buffer) < STEADY_FRAMES or now - self._steady_since < STEADY_SECONDS - 1e-6:
            return self.status()
        feats = np.array([f for f, _ in self._buffer])                   # (frames, 27, 3)
        clear = np.array([v for _, v in self._buffer])                   # (frames, 27)
        visible = clear.any(axis=0)
        # Each sticker: the median over the frames where nothing covered it.
        obs = np.array([np.median(feats[clear[:, i], i] if visible[i] else feats[:, i], axis=0) for i in range(27)])
        self._buffer = []
        expected = self._expected()
        info = {}
        verdict, moves, new_letters = decide(self.letters, obs, self.refs, expected, visible, info)
        reoriented = False
        if not (verdict == 'ok' and len(moves) <= 1 and info.get('per_sticker', 99) < WELL_FITTING):
            # Nothing explains it well: maybe the cube is just held another way round.
            if self._reorient(obs, visible, info.get('per_sticker', 99)):
                reoriented = True
                expected = self._expected()
                info = {}
                verdict, moves, new_letters = decide(self.letters, obs, self.refs, expected, visible, info)
        self._count(f'judged {verdict}')
        self.last_judgement = {'phase': 'tracking' if self.home_ok else 'home', 'expected': expected,
                               'verdict': verdict, **info}
        if self.on_judgement:
            self.on_judgement({**self.last_judgement, 'obs': np.round(obs, 1).tolist(),
                               'visible': visible.tolist(), 'state': ''.join(self.letters)})

        if not self.home_ok:
            if verdict == 'ok' and moves == ():
                self.home_ok = True
                self._lost_since = None
                self._recalibrate(obs, None, visible)
                return self.status('home', 'Cube in position. Do the first move.')
            if reoriented:  # (it fits another way round, but not yet without a move: keep waiting)
                return self.status('reoriented', 'Following the cube the way you are holding it now.')
            return self._maybe_lost(now, self.home_message())
        if verdict == 'lost':
            return self._maybe_lost(now)
        self._lost_since = None
        self._lost_reported = False
        if verdict == 'unsure':
            return self.status('unsure')
        self._recalibrate(obs, new_letters, visible)
        if moves == ():
            return self.status('reoriented', 'Following the cube the way you are holding it now.') if reoriented \
                else self.status()
        self.history.append(moves)
        self.letters = new_letters
        if self.solved:
            if not self.off and moves == (expected,):
                self.step += 1
            self.off, self._resume_letters = [], None
            return self.status('solved', 'Solved!' if moves == (expected,) else
                               f"You did {' then '.join(moves)} -- and that solved it!")
        if not self.off and len(moves) == 2 and moves[0] == expected:
            self.step += 1  # the right move, then another one: only the second needs undoing
            moves, expected = moves[1:], self._plan_move()
        if not self.off and moves == (expected,):
            self.step += 1
            if self.fixing:
                self.fixing = None
                return self.status('correct', 'Back on track.')
            return self.status('correct')
        if not self.off and expected and len(moves) == 1 and moves[0][0] == expected[0]:
            # The right side, the wrong amount (twice instead of once, the other way...): one turn of that side
            # from here reaches where the plan wanted, so that is what is shown, then the plan carries on.
            fix = amount_fix(moves[0], expected)
            asked = self.fixing[1] if self.fixing else expected
            self.plan[self.step] = fix
            self.fixing = (moves[0], asked)
            return self.status('wrong', f'You did {moves[0]} instead of {expected}. Fix it with {fix}, then carry on.')
        if self.off:
            return self._while_off_track(moves, expected)
        # A different move from the one asked for.
        did = ' then '.join(moves)
        if self.on_mistake == 'replan':
            self.plan = self.solve(CubeState(self.letters))
            self.step = 0
            return self.status('wrong', f'You did {did} instead of {expected}. New plan: {len(self.plan)} moves.')
        self._resume_letters = apply_moves(CubeState(self.letters), undo_moves(list(moves))).arr
        for m in moves:
            push_mistake(self.off, m)
        if not self.off:  # e.g. the two moves cancelled each other out
            return self.status()
        return self._undo_or_replan(f'You did {did} instead of {expected}.')

    def _while_off_track(self, moves, expected):
        for m in moves:
            push_mistake(self.off, m)
        if not self.off:
            self._resume_letters = None
            return self.status('undone', f'Undone -- back on track. Now do {self._plan_move()}.')
        nxt = self._plan_move()
        if nxt and ''.join(self.letters) == ''.join(apply_moves(CubeState(self._resume_letters), [nxt]).arr):
            # They reached the plan's next position another way: that's fine too.
            self.off, self._resume_letters = [], None
            self.step += 1
            return self.status('correct', 'That works too -- back on track.')
        if moves == (expected,):
            return self.status('correct', f"Good. Now undo: {' then '.join(undo_moves(self.off))}.")
        return self._undo_or_replan(f"You did {' then '.join(moves)} instead of {expected}.")

    def _undo_or_replan(self, what):
        undo = undo_moves(self.off)
        if len(undo) > MAX_UNDO:
            self.off, self._resume_letters = [], None
            self.plan = self.solve(CubeState(self.letters))
            self.step = 0
            return self.status('wrong', f'{what} Too many moves to undo, so here is a new plan: {len(self.plan)} moves.')
        return self.status('wrong', f"{what} Undo it: {' then '.join(undo)}, then carry on with the plan.")

    def _recalibrate(self, obs, letters=None, visible=None):
        letters = self.letters if letters is None else letters
        keep = np.ones(27, bool) if visible is None else visible  # never learn a colour from a finger
        fresh = refs_from(np.asarray(letters)[_VISIBLE][keep], obs[keep])
        for x, lab in fresh.items():  # follow lighting changes gently
            self.refs[x] = 0.5 * self.refs[x] + 0.5 * lab

    def _maybe_lost(self, now, message=None):
        if not self.home_ok:  # still turning the cube back after the scan: not lost, just not there yet
            return self.status(None, self.home_message())
        if self._lost_since is None:
            self._lost_since = now
        if now - self._lost_since >= LOST_AFTER_S:
            first = not self._lost_reported
            self._lost_reported = True  # the 'lost' event once; the message stays until the cube is back
            return self.status('lost' if first else None, message or f"Lost track of the cube. {self.position_hint()} "
                                                  "If the moves got mixed up, scan again.")
        return self.status(None, message)


def _progress(buffer, since, now):
    """How far a steady hold has got, 0..10: both enough frames and enough time are needed."""
    if not buffer or since is None:
        return 0
    return int(10 * min(1.0, len(buffer) / STEADY_FRAMES, (now - since) / STEADY_SECONDS))
