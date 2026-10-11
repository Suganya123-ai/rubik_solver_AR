"""Can the classical one-face detectors cope with the corner-on view needed
for tracking? Success = they correctly locate any one of the 3 visible faces
(tracking actually needs all 3)."""
import json
import random
import sys

import cv2
import numpy as np

import render as R
from detectors import DETECTORS, timed
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
names = [n for n in DETECTORS if 'Current app' not in n]
results = {}
for level in ('normal', 'hard'):
    rng, srng = np.random.default_rng(55 if level == 'normal' else 56), random.Random(3)
    hits = {n: 0 for n in names}
    for i in range(N):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        pose = R.corner_pose(rng)
        frame = R.render(state, pose, rng, level)
        for n in names:
            out, _ = timed(DETECTORS[n], frame)
            if out is None:
                continue
            for f in 'UFR':
                quads = [np.float32([pose.project(p) for p in R.sticker_quad_3d(f, k, inset=0.0)]) for k in range(9)]
                # any ordering of the 9 is accepted here: just "found this face"
                if all(any(cv2.pointPolygonTest(q, (float(x), float(y)), False) >= 0 for q in quads) for x, y in out):
                    hits[n] += 1
                    break
    results[level] = {n: 100 * h / N for n, h in hits.items()}
    print(level, results[level])
json.dump({'n': N, 'results': results}, open('results/results_corner_classic.json', 'w'), indent=1)
