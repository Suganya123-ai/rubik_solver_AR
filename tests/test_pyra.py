"""The Pyraminx model and its optimal solver."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyra.geometry import MAIN_MOVES, MOVES, TIP_MOVES, TIP_STICKERS  # noqa: E402
from pyra.model import SOLVED, apply_moves, inverse, is_solved, random_state  # noqa: E402
from pyra.solver import distance, solve, solve_body, table  # noqa: E402


def test_moves_have_order_three_and_move_the_right_stickers():
    for m in MAIN_MOVES + TIP_MOVES:
        assert is_solved(apply_moves(SOLVED, [m] * 3))
    assert (MOVES['U'] != np.arange(36)).sum() == 12   # tip 3 + centre 3 + 3 edges x 2
    assert (MOVES['u'] != np.arange(36)).sum() == 3


def test_every_position_is_counted_with_gods_number_eleven():
    # The published distribution (Wikipedia, "Pyraminx"): 933,120 positions, at most 11 moves.
    _, dist = table()
    assert np.bincount(dist).tolist() == [1, 8, 48, 288, 1728, 9896, 51808, 220111, 480467, 166276, 2457, 32]


@pytest.mark.parametrize('seed', range(5))
def test_random_scrambles_are_solved_in_the_fewest_moves(seed):
    rng = np.random.default_rng(seed)
    for _ in range(40):
        s = random_state(rng)
        body = solve_body(s)
        assert len(body) == distance(s)
        assert is_solved(apply_moves(s, solve(s)))


def test_tips_are_finished_in_one_turn_each_at_most():
    s = apply_moves(SOLVED, "u r' b")
    assert solve_body(s) == [] and sorted(solve(s)) == sorted(inverse("u r' b"))


def test_a_misread_colour_gives_an_impossible_position():
    s = apply_moves(SOLVED, "R U L'").copy()
    body = [i for i in range(36) if i not in TIP_STICKERS]
    s[body[0]], s[body[5]] = s[body[5]], s[body[0]]
    if distance(s) is None:
        with pytest.raises(ValueError):
            solve(s)
