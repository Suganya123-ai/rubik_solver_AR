"""Following the moves on the real Pyraminx.

Every time the puzzle is held still, the 27 stickers in view are compared
with how each candidate position would look, held any of the 12 ways:
the position now, and the position after each single move (8 layer turns,
8 tip turns). The best fit, if it is clear and repeated over a few frames,
says what the user did:
    the expected move -> "correct", next move;
    another move      -> "wrong": its undo is shown, then the same plan goes on
                         (more than MAX_UNDO wrong moves: a new plan from there);
    nothing           -> keep waiting.
Colours are compared as colour features, with each face letter's colour
taken from the scan.
"""
import numpy as np

from cube.color_detect import color_feature

from .geometry import MAIN_MOVES, MOVES, TIP_MOVES
from .model import SOLVED, inverse, is_solved
from .solver import solve
from .view import HOLD_STICKERS, HOLDS

CANDIDATE_MOVES = MAIN_MOVES + TIP_MOVES
CONFIRM = 3              # the same verdict this many steady frames in a row
MARGIN = 25.0            # best position clearly better than any other: mean colour distance over the
                         # stickers where the two would look different (different colours are ~60-150 apart)
MAX_FIT = 40.0           # and good in itself
MAX_UNDO = 3
TIP_MARGIN = 30.0        # tip stickers are the smallest: a verdict about a tip turn needs a clearer lead
TIP_CONFIRM = 3
# Usually the user did what was asked, so "you did something else" needs stronger evidence than
# "correct": a bigger lead, more agreeing frames, and a view where no face is a thin sliver.
WRONG_MARGIN = 45.0
WRONG_CONFIRM = 5
WRONG_MIN_SHARE = 0.4


class TrackSession:
    def __init__(self, state, plan, letter_features):
        self.state = np.array(list(state))
        self.plan = list(plan)
        self.step = 0
        self.undo = []                       # moves that undo the wrong moves, most recent last
        self.features = {L: np.asarray(f, float) for L, f in letter_features.items()}
        self.hold = None                     # index into HOLDS, the last one seen
        self._votes = []
        self.done = is_solved(self.state)

    @property
    def expected(self):
        if self.undo:
            return self.undo[-1]
        return self.plan[self.step] if self.step < len(self.plan) else None

    def status(self, event=None, message=None):
        return {'phase': 'solved' if self.done else ('undo' if self.undo else 'guided'),
                'step': self.step, 'total': len(self.plan), 'move': self.expected, 'undo': list(self.undo),
                'state': ''.join(self.state), 'hold': HOLDS[self.hold] if self.hold is not None else None,
                'event': event, 'message': message, 'plan': self.plan}

    def _fit(self, observed):
        """Best (cost, move or None, hold index) over candidate positions and holds, and its lead over the
        best other position, measured only on the stickers where the two would look different (a tip
        turn changes 3 stickers: averaged over all 27 the difference would be washed out)."""
        obs = np.array([color_feature(c) if c is not None else (np.nan, np.nan, np.nan) for c in observed])
        ok = ~np.isnan(obs).any(1)
        if ok.sum() < 12:
            return None
        results = []
        for move in [None] + CANDIDATE_MOVES:
            pos = self.state if move is None else self.state[MOVES[move]]
            best = None
            for h, stickers in enumerate(HOLD_STICKERS):
                letters = pos[stickers]
                d = np.linalg.norm(obs - np.array([self.features[L] for L in letters]), axis=1)
                c = float(np.mean(d[ok]))
                if best is None or c < best[0]:
                    best = (c, move, h, letters, d)
            results.append(best)
        results.sort(key=lambda t: t[0])
        (c0, m0, h0, l0, d0), (_, _, _, l1, d1) = results[0], results[1]
        differ = ok & (l0 != l1)
        lead = float(np.mean(d1[differ] - d0[differ])) if differ.any() else 0.0
        return (c0, m0, h0), lead

    def feed(self, fr):
        if self.done:
            return self.status()
        if not (fr.get('confident') and fr.get('stickers')) or fr.get('face_share', 1) < 0.15:
            self._votes = []
            return self.status()
        fit = self._fit(fr['stickers'])
        if fit is None:
            return self.status()
        (cost, move, hold), lead = fit
        tip = (move is not None and move[0].islower()) or (self.expected or 'X')[0].islower()
        wrong = move is not None and move != self.expected
        margin = WRONG_MARGIN if wrong else (TIP_MARGIN if tip else MARGIN)
        if cost > MAX_FIT or lead < margin or (wrong and fr.get('face_share', 1) < WRONG_MIN_SHARE):
            self._votes = []
            return self.status(event='unsure')
        self.hold = hold
        self._votes.append(move)
        need = WRONG_CONFIRM if wrong else (TIP_CONFIRM if tip else CONFIRM)
        if len(self._votes) < need or len(set(self._votes[-need:])) != 1:
            return self.status()
        self._votes = []
        if move is None:
            return self.status()
        return self._moved(move)

    def _moved(self, move):
        self.state = self.state[MOVES[move]]
        expected = self.expected
        if is_solved(self.state):
            self.done = True
            return self.status('solved', 'Solved!')
        if move == expected:
            if self.undo:
                self.undo.pop()
                msg = 'Undone, back on track.' if not self.undo else 'Good. Keep undoing.'
            else:
                self.step += 1
                msg = 'Correct.'
            return self.status('correct', msg)
        # a wrong move: undo it, or (too many) make a new plan from here
        if len(self.undo) >= MAX_UNDO:
            self.plan, self.step, self.undo = solve(self.state), 0, []
            return self.status('replan', f'You did {move}. New plan from here: {len(self.plan)} moves.')
        self.undo.append(inverse([move])[0])
        return self.status('wrong', f'You did {move} instead of {expected}. Undo it: {self.undo[-1]}.')

    def skip(self):
        """The user says the expected move was done (the camera missed it)."""
        m = self.expected
        return self._moved(m) if m else self.status()

    def replan(self):
        self.plan, self.step, self.undo = solve(self.state), 0, []
        return self.status('replan', f'New plan: {len(self.plan)} moves.')


def letter_features(rgbs, state):
    """Each face letter's colour feature, from the scan (mean over its 9 stickers)."""
    feats = np.array([color_feature(c) for c in rgbs])
    st = np.array(list(state))
    return {L: feats[st == L].mean(0).tolist() for L in 'FRLD'}


__all__ = ['TrackSession', 'letter_features', 'SOLVED']
