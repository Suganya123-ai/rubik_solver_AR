"""Training pictures for the Pyraminx corner model (4 keypoints, see render_pyra.py).

Normal, hard, ceiling-lit and extreme frames; near and far (a wide camera);
hands holding it, fingers across the stickers; ~5% pictures with no puzzle.
    python make_pyra_data.py 6000 600      -> data/pyra_v1/
"""
import glob
import math
import os
import sys

import cv2
import numpy as np

import render as R
import render_pyra as P
from pyra.model import random_state

N_TRAIN, N_VAL = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (6000, 600)
root = 'data/pyra_v1'
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg'))
assert backgrounds, 'no background photos (data/backgrounds): see bench/README.md (COCO128)'
R.LEVELS['extreme'] = dict(wb=0.3, gain=(0.35, 1.6), glare_p=0.6, glare_max=1.0, hand_p=0.85, noise=(4, 14),
                           blur=(0.6, 2.4), motion_p=0.4, jpeg=(40, 80), ambient=(0.2, 0.7))


def label_line(k, w, h):
    x0, y0 = k.min(0) - 6
    x1, y1 = k.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    out = ['0'] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for x, y in k:
        out += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    return ' '.join(out) + '\n'


def fingers_across(img, k, rng):
    centre = k.mean(0)
    size = float(np.ptp(k, 0).max())
    skin = R.skin_tone(rng)
    for _ in range(rng.integers(1, 4)):
        a = rng.uniform(0, 2 * math.pi)
        d = np.array([math.cos(a), math.sin(a)])
        tip = centre + d * size * rng.uniform(0.05, 0.35)
        base = centre + d * size * rng.uniform(0.9, 1.4)
        width = max(3, int(size * rng.uniform(0.05, 0.09)))
        col = tuple(float(v) for v in skin * rng.uniform(0.85, 1.05))
        cv2.line(img, tuple(int(v) for v in tip), tuple(int(v) for v in base), col, width * 2, cv2.LINE_AA)
        cv2.circle(img, tuple(int(v) for v in tip), width, col, -1, cv2.LINE_AA)


if __name__ == '__main__':   # (make_pyra_hard.py and make_pyra_edge.py import fingers_across)
    for split, n, seed in (('train', N_TRAIN, 7000), ('val', N_VAL, 8000)):
        os.makedirs(f'{root}/images/{split}', exist_ok=True)
        os.makedirs(f'{root}/labels/{split}', exist_ok=True)
        rng = np.random.default_rng(seed)
        photos = {}
        i = 0
        while i < n:
            bg_path = backgrounds[int(rng.integers(len(backgrounds)))] if rng.uniform() < 0.8 else None
            photo = photos.setdefault(bg_path, cv2.imread(bg_path)) if bg_path else None
            if rng.uniform() < 0.05:   # no puzzle in the picture
                img = np.clip(R.background(rng, photo) + rng.normal(0, rng.uniform(2, 8), (R.H, R.W, 3)), 0, 255).astype(np.uint8)
                cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', img)
                open(f'{root}/labels/{split}/{i:05d}.txt', 'w').close()
                i += 1
                continue
            near, pose = P.corner_on_pose(rng, tilt_max=45, far=rng.uniform() < 0.3)
            if not P.valid_view(pose, near, min_facing=0.08):
                continue
            k, _ = P.keypoints(pose, near)
            if k.min() < 2 or k[:, 0].max() > R.W - 2 or k[:, 1].max() > R.H - 2:
                continue
            level = ['normal', 'hard', 'real', 'extreme'][int(rng.choice(4, p=[0.25, 0.3, 0.15, 0.3]))]
            img = P.render(random_state(rng), pose, rng, level, style='stickerless' if rng.uniform() < 0.5 else 'stickered',
                           bg_photo=photo)
            if rng.uniform() < 0.4:
                img = img.copy()
                fingers_across(img, k, rng)
            if rng.uniform() < 0.4 and k[:, 1].max() - k[:, 1].min() < 350:   # 16:9 like most webcams
                top = int(np.clip(rng.uniform(k[:, 1].max() - 358, k[:, 1].min() - 2), 0, R.H - 360))
                if k[:, 1].min() - top > 2 and k[:, 1].max() - top < 358:
                    img, k = img[top:top + 360], k - np.float32([0, top])
            h, w = img.shape[:2]
            cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', img)
            with open(f'{root}/labels/{split}/{i:05d}.txt', 'w') as fh:
                fh.write(label_line(k, w, h))
            i += 1
        print(split, n)
    with open(f'{root}/pyra.yaml', 'w') as fh:
        fh.write(f"path: {os.path.abspath(root)}\ntrain: images/train\nval: images/val\n"
                 "kpt_shape: [4, 3]\nflip_idx: [0, 1, 3, 2]\nnames:\n  0: pyraminx\n")
    print('done', N_TRAIN, N_VAL)
