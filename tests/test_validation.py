import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube.cube_state import FACES, FACE_OFFSET, solved_state
from cube.moves import apply_moves, ALL_MOVES
from cube.validation import (
    corner_facelet_indices, edge_facelet_indices, validate, validate_colors, validate_scan,
)


def make_color_grid_from_state(state):
    """Build a raw scan-shaped color_grid (using arbitrary color-name strings,
    one per face-letter) from a translated CubeState, for tier-1 tests."""
    color_of_face = {'U': 'white', 'D': 'yellow', 'F': 'green', 'B': 'blue', 'L': 'orange', 'R': 'red'}
    grid = {}
    for f in FACES:
        grid[f] = [color_of_face[letter] for letter in state.face(f)]
    return grid


def test_solved_state_is_valid():
    r = validate(solved_state())
    assert r.ok, r.message


def test_legal_scramble_is_always_valid():
    rng = random.Random(7)
    for _ in range(15):
        scramble = [rng.choice(ALL_MOVES) for _ in range(20)]
        s = apply_moves(solved_state(), scramble)
        r = validate(s)
        assert r.ok, f"{scramble} produced invalid state: {r.message}"


def test_full_scan_pipeline_round_trip():
    s = apply_moves(solved_state(), ['R', 'U', "F'", 'L2', 'D', "B'"])
    grid = make_color_grid_from_state(s)
    translated, result = validate_scan(grid)
    assert result.ok, result.message
    assert translated == s


def test_color_count_error():
    grid = make_color_grid_from_state(solved_state())
    grid['U'][0] = 'yellow'  # break the 9-of-each-color count
    r = validate_colors(grid)
    assert not r.ok and r.error_code == 'ERROR_COLOR_COUNT'


def test_duplicate_center_error():
    grid = make_color_grid_from_state(solved_state())
    # Swap U's center with a non-center D sticker so both totals stay at 9,
    # but U and D centers now show the same color.
    grid['U'][4], grid['D'][0] = grid['D'][0], grid['U'][4]
    r = validate_colors(grid)
    assert not r.ok and r.error_code == 'ERROR_DUPLICATE_CENTER', r


def test_twisted_corner_detected():
    s = solved_state().copy()
    # Cyclically rotate the 3 stickers of the UFR corner (1,1,1) in place --
    # a twist impossible on a real cube (no move set can twist just one).
    i0, i1, i2 = corner_facelet_indices((1, 1, 1))
    a, b, c = s.arr[i0], s.arr[i1], s.arr[i2]
    s.arr[i0], s.arr[i1], s.arr[i2] = b, c, a
    r = validate(s)
    assert not r.ok and r.error_code == 'ERROR_CORNER_TWIST', r.message


def test_flipped_edge_detected():
    s = solved_state().copy()
    i0, i1 = edge_facelet_indices((0, 1, 1))  # UF edge
    s.arr[i0], s.arr[i1] = s.arr[i1], s.arr[i0]
    r = validate(s)
    assert not r.ok and r.error_code == 'ERROR_EDGE_FLIP', r.message


def test_swapped_edges_parity_error():
    s = solved_state().copy()
    # Swap the UF edge pair with the UB edge pair (2-cycle only -> odd
    # permutation on edges while corners stay solved -> parity mismatch).
    uf = edge_facelet_indices((0, 1, 1))
    ub = edge_facelet_indices((0, 1, -1))
    for a, b in zip(uf, ub):
        s.arr[a], s.arr[b] = s.arr[b], s.arr[a]
    r = validate(s)
    assert not r.ok and r.error_code == 'ERROR_PARITY', r.message


def test_opposite_colors_on_one_corner_detected():
    s = solved_state().copy()
    i0, _, _ = corner_facelet_indices((1, 1, 1))
    s.arr[i0] = 'D'  # opposite of U -- impossible on any one corner
    r = validate(s)
    assert not r.ok and r.error_code == 'ERROR_BAD_CORNER', r.message


if __name__ == '__main__':
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
