"""Compares models on the real test frames in data/yolo_real/images/val:
how often the cube is found, and the average corner-point error as a % of the
cube's size (tracking needs < 5%).

    python eval_real.py ../models/cube_pose_v2.pt ../models/cube_pose_real.pt
"""
import glob
import os
import sys

import cv2
import numpy as np
from ultralytics import YOLO

frames = sorted(glob.glob('data/yolo_real/images/val/*.jpg'))
if not frames:
    raise SystemExit('No real test frames: run build_real_dataset.py first.')

for path in sys.argv[1:]:
    model = YOLO(path)
    errs, found, cubes, false_alarms = [], 0, 0, 0
    for f in frames:
        img = cv2.imread(f)
        h, w = img.shape[:2]
        vals = open(f.replace('/images/', '/labels/')[:-4] + '.txt').read().split()
        r = model.predict(img, imgsz=640, conf=0.25, verbose=False)[0]
        got = r.keypoints is not None and len(r.boxes) > 0
        if not vals:  # a "no cube" frame
            false_alarms += got
            continue
        cubes += 1
        if not got:
            continue
        found += 1
        gt = np.float32([[float(vals[5 + 3 * i]) * w, float(vals[6 + 3 * i]) * h] for i in range(7)])
        k = r.keypoints.xy[int(r.boxes.conf.argmax())].cpu().numpy()
        size = np.mean(np.linalg.norm(gt[1:] - gt[0], axis=1))
        errs.append(np.mean(np.linalg.norm(k - gt, axis=1)) / size * 100)
    print(f'{os.path.basename(path):28s} cube found {100 * found / max(cubes, 1):5.1f}% of {cubes}'
          f' | median point error {np.median(errs) if errs else float("nan"):.1f}%'
          f' | 95% under {np.percentile(errs, 95) if errs else float("nan"):.1f}%'
          f' | false alarms on {false_alarms} "no cube" frames')
