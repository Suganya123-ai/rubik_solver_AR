"""Second training set for the cube keypoint model, closer to real webcam use:
stickerless and stickered cubes, real photo backgrounds (COCO128, many with
people), a hand holding the cube, close-ups and wider angles, and half the
frames cropped to 16:9 like most webcams. Ultralytics pose label format."""
import glob
import os
import random
import sys

import cv2
import numpy as np

import render as R
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N_TRAIN, N_VAL = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (4000, 400)
root = 'data/yolo_v2'
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg'))
assert backgrounds, 'run: download COCO128 into data/backgrounds (see README)'


def label_line(k, w, h):
    x0, y0 = k.min(0) - 6
    x1, y1 = k.max(0) + 6
    vals = [(x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h]
    for x, y in k:
        vals += [x / w, y / h]
    out = ['0'] + [f'{v:.6f}' for v in vals[:4]]
    for i in range(7):
        out += [f'{vals[4 + 2 * i]:.6f}', f'{vals[5 + 2 * i]:.6f}', '2']
    return ' '.join(out) + '\n'


for split, n, seed in (('train', N_TRAIN, 3000), ('val', N_VAL, 4000)):
    os.makedirs(f'{root}/images/{split}', exist_ok=True)
    os.makedirs(f'{root}/labels/{split}', exist_ok=True)
    rng, srng = np.random.default_rng(seed), random.Random(seed)
    photos = {}
    i = 0
    while i < n:
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        pose = R.corner_pose_wide(rng)
        k = R.gt_keypoints(pose)
        if k.min() < 2 or k[:, 0].max() > R.W - 2 or k[:, 1].max() > R.H - 2:
            continue  # keep all 7 corners in the frame
        bg_path = backgrounds[int(rng.integers(len(backgrounds)))] if rng.uniform() < 0.75 else None
        photo = None
        if bg_path:
            photo = photos.setdefault(bg_path, cv2.imread(bg_path))
        img = R.render(state, pose, rng, 'hard' if rng.uniform() < 0.5 else 'normal',
                       style='stickerless' if rng.uniform() < 0.6 else 'stickered', bg_photo=photo, hand='hand')
        if rng.uniform() < 0.5 and k[:, 1].max() - k[:, 1].min() < 350:  # 16:9 crop, if the cube fits
            top = int(np.clip(rng.uniform(k[:, 1].max() - 358, k[:, 1].min() - 2), 0, R.H - 360))
            if k[:, 1].min() - top > 2 and k[:, 1].max() - top < 358:
                img, k = img[top:top + 360], k - np.float32([0, top])
        h, w = img.shape[:2]
        cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', img)
        with open(f'{root}/labels/{split}/{i:05d}.txt', 'w') as fh:
            fh.write(label_line(k, w, h))
        i += 1
with open(f'{root}/cube.yaml', 'w') as fh:
    fh.write(f"path: {os.path.abspath(root)}\ntrain: images/train\nval: images/val\n"
             "kpt_shape: [7, 3]\nflip_idx: [0, 3, 2, 1, 6, 5, 4]\nnames:\n  0: cube\n")
print('done', N_TRAIN, N_VAL)
