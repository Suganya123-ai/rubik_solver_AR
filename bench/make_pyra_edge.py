"""Training pictures of the Pyraminx held edge-on (an edge toward the camera, two whole faces in
view: the way the scan asks for it), class 1 of the pyramid model (class 0 is corner-on).

Normal, hard, ceiling-lit and extreme frames (heavy blur, dark, colour casts), near and far, hands
holding it, fingers across the stickers, 16:9 crops, ~5% pictures with no puzzle.
    PYTHONPATH=.. python make_pyra_edge.py 5500 550      -> data/pyra_edge/
"""
import glob
import os
import sys

import cv2
import numpy as np

import render as R
import render_pyra as P
from make_pyra_data import fingers_across
from pyra.model import random_state

N_TRAIN, N_VAL = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (5500, 550)
root = 'data/pyra_edge'
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg'))
assert backgrounds, 'no background photos (data/backgrounds): see bench/README.md (COCO128)'
R.LEVELS['extreme'] = dict(wb=0.35, gain=(0.3, 1.7), glare_p=0.7, glare_max=1.0, hand_p=0.9, noise=(5, 16),
                           blur=(0.8, 3.0), motion_p=0.55, jpeg=(30, 70), ambient=(0.15, 0.7))


def label_line(k, w, h, cls):
    x0, y0 = k.min(0) - 6
    x1, y1 = k.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    out = [str(cls)] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for x, y in k:
        out += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    return ' '.join(out) + '\n'


if __name__ == '__main__':
    for split, n, seed in (('train', N_TRAIN, 9100), ('val', N_VAL, 9200)):
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
                cv2.imwrite(f'{root}/images/{split}/e{i:05d}.jpg', img)
                open(f'{root}/labels/{split}/e{i:05d}.txt', 'w').close()
                i += 1
                continue
            edge, pose = P.edge_on_pose(rng, tilt_max=35, far=rng.uniform() < 0.3)
            if not P.valid_edge_view(pose, edge, min_facing=0.12):
                continue
            k, _ = P.edge_keypoints(pose, edge)
            if k.min() < 2 or k[:, 0].max() > R.W - 2 or k[:, 1].max() > R.H - 2:
                continue
            level = ['normal', 'hard', 'real', 'extreme'][int(rng.choice(4, p=[0.2, 0.3, 0.15, 0.35]))]
            img = P.render(random_state(rng), pose, rng, level, style='stickerless' if rng.uniform() < 0.5 else 'stickered',
                           bg_photo=photo)
            if rng.uniform() < 0.5:
                img = img.copy()
                for _ in range(int(rng.integers(1, 3))):
                    fingers_across(img, k, rng)
            if rng.uniform() < 0.4 and k[:, 1].max() - k[:, 1].min() < 350:   # 16:9 like most webcams
                top = int(np.clip(rng.uniform(k[:, 1].max() - 358, k[:, 1].min() - 2), 0, R.H - 360))
                if k[:, 1].min() - top > 2 and k[:, 1].max() - top < 358:
                    img, k = img[top:top + 360], k - np.float32([0, top])
            h, w = img.shape[:2]
            cv2.imwrite(f'{root}/images/{split}/e{i:05d}.jpg', img)
            with open(f'{root}/labels/{split}/e{i:05d}.txt', 'w') as fh:
                fh.write(label_line(k, w, h, 1))
            i += 1
        print(split, n)
