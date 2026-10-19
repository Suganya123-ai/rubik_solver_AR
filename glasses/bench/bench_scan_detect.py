"""Phase A test: can each project find the 9 stickers of the face shown to
the camera? A detection counts only if all 9 centres land on the right
stickers in the right order."""
import json
import random
import statistics
import sys

import cv2
import numpy as np

import render as R
from detectors import DETECTORS, ROTATION_TOLERANT, timed
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
CONDITIONS = [('Aligned to guide grid, normal light', True, 'normal'),
              ('Free hand-held, normal light', False, 'normal'),
              ('Free hand-held, hard conditions', False, 'hard')]


ROT = [list(range(9))]
for _ in range(3):
    ROT.append([ROT[-1][(2 - c) * 3 + r] for r in range(3) for c in range(3)])  # rotate the 3x3 grid 90 deg


def correct(centres, pose, any_rotation=False):
    if centres is None:
        return False
    quads = [np.float32([pose.project(p) for p in R.sticker_quad_3d('F', k, inset=0.0)]) for k in range(9)]
    for perm in (ROT if any_rotation else ROT[:1]):
        if all(cv2.pointPolygonTest(quads[perm[i]], (float(x), float(y)), False) >= 0 for i, (x, y) in enumerate(centres)):
            return True
    return False


results = {}
for cname, aligned, level in CONDITIONS:
    rng = np.random.default_rng(100 + aligned * 7 + (level == 'hard'))
    srng = random.Random(5)
    stats = {d: {'ok': 0, 'ok_rot': 0, 'found': 0, 'ms': []} for d in DETECTORS}
    for i in range(N):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        pose = R.scan_pose(rng, aligned=aligned)
        frame = R.render(state, pose, rng, level)
        for dname, fn in DETECTORS.items():
            out, ms = timed(fn, frame)
            stats[dname]['ms'].append(ms)
            stats[dname]['found'] += out is not None
            stats[dname]['ok'] += correct(out, pose)
            stats[dname]['ok_rot'] += correct(out, pose, any_rotation=True)
    results[cname] = {d: {'correct_pct': 100 * s['ok'] / N, 'any_rotation_pct': 100 * s['ok_rot'] / N, 'found_pct': 100 * s['found'] / N,
                          'ms_median': statistics.median(s['ms']), 'ms_mean': statistics.mean(s['ms'])}
                      for d, s in stats.items()}
    print(cname)
    for d, s in results[cname].items():
        print(f"   {d:34s} correct {s['correct_pct']:5.1f}%  any-rotation {s['any_rotation_pct']:5.1f}%  found {s['found_pct']:5.1f}%  "
              f"median {s['ms_median']:7.1f} ms")
json.dump({'n': N, 'results': results}, open('results/results_scan_detect.json', 'w'), indent=1)
