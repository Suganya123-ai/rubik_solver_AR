import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cube.cube_state import solved_state
from cube.moves import apply_moves, ALL_MOVES
from cube.solver import MAX_SANE_MOVES, SolverError, enrich, solve


def _check_round_trip(scramble):
    s = apply_moves(solved_state(), scramble)
    moves, stage_bounds = solve(s)
    result = apply_moves(s, moves)
    assert result == solved_state(), f"scramble {scramble} -> solution {moves} did not solve"
    assert len(moves) <= MAX_SANE_MOVES, f"solution too long ({len(moves)}) for scramble {scramble}"
    return moves, stage_bounds


def test_already_solved_cube():
    moves, _ = _check_round_trip([])
    assert moves == []


def test_every_single_move_scramble():
    for m in ALL_MOVES:
        _check_round_trip([m])


def test_random_scrambles_many_seeds():
    for seed in range(200):
        rng = random.Random(seed)
        scramble = [rng.choice(ALL_MOVES) for _ in range(25)]
        _check_round_trip(scramble)


def test_random_scrambles_varied_length():
    for seed in range(100):
        rng = random.Random(seed + 10_000)
        scramble = [rng.choice(ALL_MOVES) for _ in range(rng.randint(1, 40))]
        _check_round_trip(scramble)


def test_two_generator_scrambles():
    # Scrambles using only 2 of the 6 faces exercise different stage-skip
    # patterns than typical random scrambles (many pieces stay untouched).
    rng = random.Random(99)
    for faces in [('U', 'D'), ('R', 'L'), ('F', 'B'), ('U', 'R')]:
        moves_pool = [f + s for f in faces for s in ('', "'", '2')]
        scramble = [rng.choice(moves_pool) for _ in range(20)]
        _check_round_trip(scramble)


def test_solution_is_deterministic():
    rng = random.Random(7)
    scramble = [rng.choice(ALL_MOVES) for _ in range(25)]
    s = apply_moves(solved_state(), scramble)
    moves1, _ = solve(s)
    moves2, _ = solve(s)
    assert moves1 == moves2


def test_enrich_produces_valid_instructions():
    rng = random.Random(3)
    scramble = [rng.choice(ALL_MOVES) for _ in range(25)]
    s = apply_moves(solved_state(), scramble)
    moves, stage_bounds = solve(s)
    instructions = enrich(moves, stage_bounds)
    assert len(instructions) == len(moves)
    for i, instr in enumerate(instructions):
        assert instr.step_index == i + 1
        assert instr.total_steps == len(moves)
        assert instr.notation == moves[i]
        assert instr.direction in ('CW', 'CCW', '180')


def test_invalid_scan_rejected():
    s = solved_state().copy()
    s.arr[4] = 'D'  # break U's center to create an illegal state
    try:
        solve(s)
        assert False, "expected SolverError for an invalid scan"
    except SolverError:
        pass


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
