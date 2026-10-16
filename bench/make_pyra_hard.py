"""Unclear situations for the Pyraminx model, and 3x3 cubes as counter-examples.

- 2,500 pyramids in the hardest conditions: the 'extreme' level (heavy blur and
  motion, very dark or bright, colour casts, noise, strong JPEG), up to four
  fingers across the stickers, near and far, steep angles.
- 1,000 rendered 3x3 cubes (render.py, the cube app's renderer) with an empty
  label: a cube is not a pyramid.

    PYTHONPATH=.. python make_pyra_hard.py      -> data/pyra_hard/
"""
import glob
import os
import random

import cv2
import numpy as np

import render as R
import render_pyra as P
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves
from make_pyra_data import fingers_across, label_line
from pyra.model import random_state

root = 'data/pyra_hard'
N_PYRA, N_CUBE = 2500, 1000
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg'))
R.LEVELS['extreme'] = dict(wb=0.35, gain=(0.3, 1.7), glare_p=0.7, glare_max=1.0, hand_p=0.9, noise=(5, 16),
                           blur=(0.8, 3.0), motion_p=0.55, jpeg=(30, 70), ambient=(0.15, 0.7))

for split in ('train', 'val'):
    os.makedirs(f'{root}/images/{split}', exist_ok=True)
    os.makedirs(f'{root}/labels/{split}', exist_ok=True)
rng, srng = np.random.default_rng(11), random.Random(11)
photos = {}
i = 0
while i < N_PYRA:
    photo = photos.setdefault(b := backgrounds[int(rng.integers(len(backgrounds)))], cv2.imread(b)) if rng.uniform() < 0.85 else None
    near, pose = P.corner_on_pose(rng, tilt_max=50, far=rng.uniform() < 0.35)
    if not P.valid_view(pose, near, min_facing=0.06):
        continue
    k, _ = P.keypoints(pose, near)
    if k.min() < 2 or k[:, 0].max() > R.W - 2 or k[:, 1].max() > R.H - 2:
        continue
    img = P.render(random_state(rng), pose, rng, 'extreme' if rng.uniform() < 0.7 else 'hard',
                   style='stickerless' if rng.uniform() < 0.5 else 'stickered', bg_photo=photo).copy()
    for _ in range(int(rng.integers(1, 3))):
        fingers_across(img, k, rng)
    split = 'val' if i % 10 == 0 else 'train'
    cv2.imwrite(f'{root}/images/{split}/p{i:05d}.jpg', img)
    with open(f'{root}/labels/{split}/p{i:05d}.txt', 'w') as fh:
        fh.write(label_line(k, R.W, R.H))
    i += 1
j = 0
while j < N_CUBE:
    photo = photos.setdefault(b := backgrounds[int(rng.integers(len(backgrounds)))], cv2.imread(b)) if rng.uniform() < 0.75 else None
    pose = R.corner_pose_wide(rng)
    k = R.gt_keypoints(pose)
    if k.min() < 2 or k[:, 0].max() > R.W - 2 or k[:, 1].max() > R.H - 2:
        continue
    state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
    img = R.render(state, pose, rng, ['normal', 'hard', 'real'][j % 3], style='stickerless' if rng.uniform() < 0.6 else 'stickered',
                   bg_photo=photo, hand='hand')
    split = 'val' if j % 10 == 0 else 'train'
    cv2.imwrite(f'{root}/images/{split}/c{j:05d}.jpg', img)
    open(f'{root}/labels/{split}/c{j:05d}.txt', 'w').close()
    j += 1
print('hard pyramids', N_PYRA, 'cube counter-examples', N_CUBE)
