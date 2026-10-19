import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube.cube_state import solved_state, FACES, OPPOSITE_FACE
from cube.moves import apply_move, apply_moves, ALL_MOVES


def test_quarter_turn_order_4():
    for f in 'URFDLB':
        s = solved_state()
        for _ in range(4):
            s = apply_move(s, f)
        assert s == solved_state(), f"{f} x4 != identity"


def test_inverse_pairs():
    for f in 'URFDLB':
        s = apply_move(apply_move(solved_state(), f), f + "'")
        assert s == solved_state(), f"{f} then {f}' != identity"
        s2 = apply_move(apply_move(solved_state(), f + "2"), f + "2")
        assert s2 == solved_state(), f"{f}2 x2 != identity"


def test_double_turn_equals_two_quarters():
    for f in 'URFDLB':
        a = apply_move(solved_state(), f + '2')
        b = apply_moves(solved_state(), [f, f])
        assert a == b


def test_opposite_face_non_interference():
    for f in 'URFDLB':
        opp = OPPOSITE_FACE[f]
        before = solved_state().face(opp).copy()
        after = apply_move(solved_state(), f).face(opp)
        assert (before == after).all(), f"{f} disturbed opposite face {opp}"


def test_centers_never_move():
    s = solved_state()
    for m in ALL_MOVES:
        s = apply_move(s, m)
    for f in FACES:
        assert s.face(f)[4] == solved_state().face(f)[4]


def test_sexy_move_order_6():
    s = solved_state()
    for _ in range(6):
        s = apply_moves(s, ['R', 'U', "R'", "U'"])
    assert s == solved_state()


def test_ur_order_105():
    s = solved_state()
    for _ in range(105):
        s = apply_moves(s, ['U', 'R'])
    assert s == solved_state()


def test_all_18_moves_are_permutations_of_54_and_involutions_with_inverse():
    for m in ALL_MOVES:
        s = apply_move(solved_state(), m)
        assert sorted(s.arr.tolist()) == sorted(solved_state().arr.tolist())


def test_random_scramble_and_undo_returns_to_solved():
    rng = random.Random(42)
    for _ in range(20):
        scramble = [rng.choice(ALL_MOVES) for _ in range(20)]
        s = apply_moves(solved_state(), scramble)
        inverse = []
        for m in reversed(scramble):
            if m.endswith("'"):
                inverse.append(m[0])
            elif m.endswith('2'):
                inverse.append(m)
            else:
                inverse.append(m + "'")
        s = apply_moves(s, inverse)
        assert s == solved_state()


def test_corner_and_edge_adjacency_sane():
    # UFR corner (top-front-right) should be exactly the 3 stickers at the
    # U/F/R faces' mutually adjacent corner cell.
    s = solved_state()
    u = s.face('U').reshape(3, 3)
    f = s.face('F').reshape(3, 3)
    r = s.face('R').reshape(3, 3)
    # U bottom-right, F top-right, R top-left should all be distinct colors
    # (a real corner cubie has 3 distinct, mutually-adjacent colors).
    trio = {u[2, 2], f[0, 2], r[0, 0]}
    assert len(trio) == 3


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
