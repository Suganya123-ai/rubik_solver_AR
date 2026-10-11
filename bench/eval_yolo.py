"""YOLO keypoint accuracy on fresh synthetic corner frames (not seen in
training): detection rate, keypoint error as % of cube size, speed."""
import json
import random
import sys
import time

import numpy as np
from ultralytics import YOLO

import render as R
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

weights = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 300
results = {}
for device in ('mps', 'cpu'):
    model = YOLO(weights)
    for level in ('normal', 'hard'):
        rng, srng = np.random.default_rng(777 if level == 'normal' else 778), random.Random(4)
        errs, ms, found = [], [], 0
        model.predict(np.zeros((480, 640, 3), np.uint8), imgsz=640, device=device, verbose=False)  # warm-up
        for i in range(N):
            state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
            pose = R.corner_pose(rng)
            frame = R.render(state, pose, rng, level)
            t0 = time.perf_counter()
            r = model.predict(frame, imgsz=640, device=device, verbose=False)[0]
            ms.append((time.perf_counter() - t0) * 1000)
            if r.keypoints is None or len(r.keypoints.xy) == 0:
                continue
            found += 1
            k = r.keypoints.xy[int(r.boxes.conf.argmax())].cpu().numpy()
            gt = R.gt_keypoints(pose)
            size = np.mean(np.linalg.norm(gt[1:] - gt[0], axis=1))
            errs.append(float(np.mean(np.linalg.norm(k - gt, axis=1)) / size * 100))
        results[f'{device}|{level}'] = {
            'found_pct': 100 * found / N, 'err_mean_pct': float(np.mean(errs)), 'err_median_pct': float(np.median(errs)),
            'err_p95_pct': float(np.percentile(errs, 95)), 'ms_median': float(np.median(ms))}
        print(device, level, results[f'{device}|{level}'])
json.dump({'n': N, 'results': results}, open('results/results_yolo_kpts.json', 'w'), indent=1)
