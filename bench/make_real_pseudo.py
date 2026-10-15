"""Real camera frames for training, labelled by the current model where it is sure.

Takes the frames saved by the apps' scans and solving sessions (data/scans,
data/sessions in the given app folders, local files only), runs the current
model on each, and keeps the frames where it found the cube with confidence
>= MIN_CONF as labelled examples. They teach the new model what real cameras
look like (webcam and the glasses' camera); the hard poses come from the v3
renders. Frames from HOLD_OUT sessions are left out: they are the real test.

    python make_real_pseudo.py ../models/cube_pose_v2.pt <app folder> [<app folder> ...]
        -> data/real_pseudo/
"""
import glob
import os
import random
import sys

import cv2
from ultralytics import YOLO

MIN_CONF = 0.85
MAX_FRAMES = 1500
HOLD_OUT = ('2026-10-13/173502', '2026-10-14/1')   # a glasses session and the 14 Oct webcam sessions
root = 'data/real_pseudo'

model = YOLO(sys.argv[1])
frames = []
for app in sys.argv[2:]:
    frames += glob.glob(os.path.join(app, 'data', 'scans', '*', '*', '*.jpg'))
    frames += glob.glob(os.path.join(app, 'data', 'sessions', '*', '*', '*.jpg'))
frames = sorted(f for f in frames if not any(h in f for h in HOLD_OUT))
random.Random(7).shuffle(frames)
kept = 0
for split in ('train', 'val'):
    os.makedirs(f'{root}/images/{split}', exist_ok=True)
    os.makedirs(f'{root}/labels/{split}', exist_ok=True)
for path in frames:
    if kept >= MAX_FRAMES:
        break
    img = cv2.imread(path)
    if img is None:
        continue
    r = model.predict(img, imgsz=640, verbose=False, device='mps')[0]
    if len(r.boxes) == 0 or float(r.boxes.conf.max()) < MIN_CONF:
        continue
    k = r.keypoints.xy[int(r.boxes.conf.argmax())].cpu().numpy()
    h, w = img.shape[:2]
    if k.min() < 1 or k[:, 0].max() > w - 1 or k[:, 1].max() > h - 1:
        continue
    split = 'val' if kept % 10 == 0 else 'train'
    x0, y0 = k.min(0) - 6
    x1, y1 = k.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    vals = ['0'] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for x, y in k:
        vals += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    name = f'{kept:05d}'
    cv2.imwrite(f'{root}/images/{split}/{name}.jpg', img)
    with open(f'{root}/labels/{split}/{name}.txt', 'w') as fh:
        fh.write(' '.join(vals) + '\n')
    kept += 1
print('frames looked at:', len(frames), 'kept:', kept)
