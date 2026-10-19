"""The ephynes C# project's solver settings (two-phase, maxDepth 25), measured
with the equivalent kociemba call on the same 200 cubes as bench_solvers.py."""
import json
import os
import random
import statistics
import sys
import time

import kociemba

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root, for cube/
from cube.cube_state import solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_moves  # noqa: E402

rng = random.Random(42)
states = [apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(30)]) for _ in range(200)]
lens, times = [], []
for s in states:
    t0 = time.perf_counter()
    moves = kociemba.solve(''.join(s.arr), max_depth=25).split()
    times.append((time.perf_counter() - t0) * 1000)
    lens.append(len(moves))
    assert ''.join(apply_moves(s, moves).arr) == ''.join(solved_state().arr)
r = {'moves_mean': statistics.mean(lens), 'moves_max': max(lens), 'ms_median': statistics.median(times),
     'solved_pct': 100.0, 'n': len(states)}
print(r)
json.dump(r, open('results/results_solver_ephynes_settings.json', 'w'))
