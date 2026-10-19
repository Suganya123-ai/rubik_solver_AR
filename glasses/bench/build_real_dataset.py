"""Builds data/yolo_real/: reviewed real frames from ../data/captures (labelled
in /label) mixed with synthetic v2 frames, ready for train_yolo.py.

Real frames saved seconds apart are near-duplicates, so the train/test split
is by time block (runs of consecutive frames), not by random frame: the test
frames are then genuinely unseen moments. Real training frames are repeated
so they aren't drowned out by the synthetic ones.

    python build_real_dataset.py                      # defaults
    python train_yolo.py --data data/yolo_real/cube.yaml --base ../models/cube_pose_v2.pt \
        --epochs 15 --out ../models/cube_pose_real.pt --name cube_real
    python eval_real.py ../models/cube_pose_v2.pt ../models/cube_pose_real.pt
"""
import argparse
import glob
import os
import random
import shutil

p = argparse.ArgumentParser()
p.add_argument('--captures', default='../data/captures')
p.add_argument('--synthetic', default='data/yolo_v2', help='synthetic set to mix in')
p.add_argument('--out', default='data/yolo_real')
p.add_argument('--block', type=int, default=15, help='consecutive frames per split block')
p.add_argument('--val-every', type=int, default=5, help='every Nth block goes to the test split')
p.add_argument('--repeat', type=int, default=3, help='copies of each real training frame')
p.add_argument('--synthetic-ratio', type=float, default=2.0, help='synthetic frames per real training frame')
a = p.parse_args()

reviewed = sorted(f[:-3] for f in glob.glob(os.path.join(a.captures, '*', '*.ok')))  # path stems, time-ordered
if not reviewed:
    raise SystemExit(f'No reviewed frames in {a.captures}. Label some in the /label page first.')

shutil.rmtree(a.out, ignore_errors=True)
for split in ('train', 'val'):
    os.makedirs(f'{a.out}/images/{split}')
    os.makedirs(f'{a.out}/labels/{split}')

counts = {'train': 0, 'val': 0, 'negatives': 0}
for i, stem in enumerate(reviewed):
    split = 'val' if (i // a.block) % a.val_every == a.val_every - 1 else 'train'
    copies = a.repeat if split == 'train' else 1
    name = stem.replace(os.sep, '_').replace('.', '_').lstrip('_')[-40:]
    for c in range(copies):
        shutil.copy(stem + '.jpg', f'{a.out}/images/{split}/real_{name}_{c}.jpg')
        shutil.copy(stem + '.txt', f'{a.out}/labels/{split}/real_{name}_{c}.txt')
    counts[split] += 1
    counts['negatives'] += os.path.getsize(stem + '.txt') == 0

synth = sorted(glob.glob(f'{a.synthetic}/images/train/*.jpg'))
n_synth = min(len(synth), int(counts['train'] * a.repeat * a.synthetic_ratio))
for img in random.Random(0).sample(synth, n_synth):
    stem = os.path.basename(img)[:-4]
    shutil.copy(img, f'{a.out}/images/train/syn_{stem}.jpg')
    shutil.copy(f'{a.synthetic}/labels/train/{stem}.txt', f'{a.out}/labels/train/syn_{stem}.txt')

with open(f'{a.out}/cube.yaml', 'w') as fh:
    fh.write(f"path: {os.path.abspath(a.out)}\ntrain: images/train\nval: images/val\n"
             "kpt_shape: [7, 3]\nflip_idx: [0, 3, 2, 1, 6, 5, 4]\nnames:\n  0: cube\n")
print(f"real frames: {counts['train']} train (x{a.repeat}), {counts['val']} test, {counts['negatives']} 'no cube'"
      f" | synthetic mixed in: {n_synth} | -> {a.out}/cube.yaml")
if counts['val'] == 0:
    print('warning: no test frames yet (need more than', a.block * (a.val_every - 1), 'reviewed frames)')
