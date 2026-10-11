"""Solver benchmark: same random cubes through every candidate solver.
Each solution is replayed on the app's own cube model to confirm it solves."""
import json
import os
import random
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root, for cube/
from cube.cube_state import CubeState, solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_moves  # noqa: E402
from cube import solver as app_solver  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
which = sys.argv[2].split(',') if len(sys.argv) > 2 else ['app', 'kociemba', 'cubejs', 'twophase']

rng = random.Random(42)
states = [apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(30)]) for _ in range(N)]
strings = [''.join(s.arr) for s in states]


def normalize(tokens):
    out = []
    for t in tokens:
        if t.startswith('('):
            continue
        face, suf = t[0], t[1:]
        out.append(face + {'': '', "'": "'", '2': '2', '1': '', '3': "'"}[suf])
    return out


def verify(state, moves):
    return ''.join(apply_moves(state, moves).arr) == ''.join(solved_state().arr)


def run(name, fn):
    lens, times, ok = [], [], 0
    for s, cs in zip(states, strings):
        t0 = time.perf_counter()
        moves = fn(s, cs)
        times.append((time.perf_counter() - t0) * 1000)
        lens.append(len(moves))
        ok += verify(s, moves)
    return summarize(name, lens, times, ok)


def summarize(name, lens, times, ok):
    times_sorted = sorted(times)
    return {
        'solver': name, 'n': len(lens), 'solved_pct': 100 * ok / len(lens),
        'moves_mean': statistics.mean(lens), 'moves_median': statistics.median(lens),
        'moves_min': min(lens), 'moves_max': max(lens),
        'ms_mean': statistics.mean(times), 'ms_median': statistics.median(times),
        'ms_p95': times_sorted[int(0.95 * (len(times) - 1))], 'ms_max': max(times),
        'lens': lens, 'times': times,
    }


results = []
if 'app' in which:
    results.append(run('Current app solver', lambda s, cs: list(app_solver.solve_layer_by_layer(CubeState(s.arr.copy()))[0])))  # the pre-kociemba solver
if 'kociemba' in which:
    import kociemba
    kociemba.solve(strings[0])  # warm-up (loads tables)
    results.append(run('kociemba (C)', lambda s, cs: normalize(kociemba.solve(cs).split())))
if 'twophase' in which:
    import twophase.solver as tp
    results.append(run('RubikTwoPhase (Python)', lambda s, cs: normalize(tp.solve(cs, 20, 3).split())))
if 'cubejs' in which:
    js = r"""
const Cube = require('cubejs');
const t0 = Date.now(); Cube.initSolver(); const init = Date.now() - t0;
const out = [];
for (const s of JSON.parse(require('fs').readFileSync(0, 'utf8'))) {
  const a = process.hrtime.bigint();
  const sol = Cube.fromString(s).solve();
  out.push({sol, ms: Number(process.hrtime.bigint() - a) / 1e6});
}
console.log(JSON.stringify({init, out}));
"""
    p = subprocess.run(['node', '-e', js], input=json.dumps(strings), capture_output=True, text=True,
                       cwd='third_party/node', check=True)
    data = json.loads(p.stdout)
    lens, times, ok = [], [], 0
    for s, r in zip(states, data['out']):
        moves = normalize(r['sol'].split())
        lens.append(len(moves))
        times.append(r['ms'])
        ok += verify(s, moves)
    res = summarize('cubejs (JavaScript)', lens, times, ok)
    res['init_ms'] = data['init']
    results.append(res)

for r in results:
    print(f"{r['solver']:26s} solved {r['solved_pct']:5.1f}%  moves mean {r['moves_mean']:6.1f} "
          f"med {r['moves_median']:5.1f} max {r['moves_max']:4d}  ms mean {r['ms_mean']:8.2f} "
          f"p95 {r['ms_p95']:8.2f} max {r['ms_max']:8.2f}" + (f"  init {r.get('init_ms')} ms" if 'init_ms' in r else ''))
json.dump(results, open(f'results/results_solvers_{"_".join(which)}.json', 'w'))
