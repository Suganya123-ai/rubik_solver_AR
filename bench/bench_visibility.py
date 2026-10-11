"""How much of the cube must the camera see? For random cubes, checks whether
every single move (and every pair of moves) leaves a different picture on the
visible sides. No images needed: it uses the cube model directly."""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root, for cube/
from cube.cube_state import FACE_OFFSET, solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_move, apply_moves  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def view(state, faces):
    return tuple(tuple(state.arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]) for f in faces)


rng = random.Random(0)
results = {}
for faces in (['F'], ['U', 'F'], ['U', 'F', 'R']):
    one = two = 0
    for _ in range(N):
        s = apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(25)])
        outcomes = [view(s, faces)] + [view(apply_move(s, m), faces) for m in ALL_MOVES]
        one += len(set(outcomes)) < len(outcomes)
        seen = {}
        for a in ALL_MOVES:
            for b in ALL_MOVES:
                t = apply_moves(s, [a, b])
                seen.setdefault(view(t, faces), set()).add(t.arr.tobytes())
        two += any(len(v) > 1 for v in seen.values())
    results['+'.join(faces)] = {'one_move_ambiguous_pct': 100 * one / N, 'two_moves_ambiguous_pct': 100 * two / N}
    print('+'.join(faces), results['+'.join(faces)])
json.dump({'n': N, 'results': results}, open('results/results_visibility.json', 'w'), indent=1)
