"""Synthetic corner-view frames labelled with the 7 hexagon keypoints, in
Ultralytics pose format (class cx cy w h, then x y v per keypoint)."""
import os
import random
import sys

import cv2
import numpy as np

import render as R
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N_TRAIN, N_VAL = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (2500, 300)
root = 'data/yolo'
for split, n, seed in (('train', N_TRAIN, 1000), ('val', N_VAL, 2000)):
    os.makedirs(f'{root}/images/{split}', exist_ok=True)
    os.makedirs(f'{root}/labels/{split}', exist_ok=True)
    rng, srng = np.random.default_rng(seed), random.Random(seed)
    for i in range(n):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        pose = R.corner_pose(rng)
        level = 'hard' if i % 2 else 'normal'
        img = R.render(state, pose, rng, level)
        k = R.gt_keypoints(pose)
        x0, y0 = k.min(0) - 6
        x1, y1 = k.max(0) + 6
        line = [0, (x0 + x1) / 2 / R.W, (y0 + y1) / 2 / R.H, (x1 - x0) / R.W, (y1 - y0) / R.H]
        for x, y in k:
            line += [x / R.W, y / R.H, 2]
        cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', img)
        with open(f'{root}/labels/{split}/{i:05d}.txt', 'w') as fh:
            fh.write(' '.join(f'{v:.6f}' if isinstance(v, float) else str(v) for v in line) + '\n')
with open(f'{root}/cube.yaml', 'w') as fh:
    fh.write(f"path: {os.path.abspath(root)}\ntrain: images/train\nval: images/val\n"
             "kpt_shape: [7, 3]\nflip_idx: [0, 3, 2, 1, 6, 5, 4]\nnames:\n  0: cube\n")
print('done')
