"""Third training set for the cube keypoint model: the hard cases seen with
real users, on top of v2 (webcam-like frames, photo backgrounds, hands).

- Steeper angles: one side seen nearly edge-on (the cube held almost
  face-on), wider roll, as people hold it after a move.
- Small and far cubes (a wide-angle camera such as the glasses'), and cubes
  near the edge of the picture.
- Fingers reaching well onto the stickers, from more sides.
- Heavier blur and motion blur, more noise, stronger JPEG, dark and
  over-exposed light, colour casts.
- Some frames with no cube at all (empty label), so the model stops seeing
  cubes in clutter.

Ultralytics pose label format, 7 corner points (all inside the picture).
    python make_yolo_data_v3.py 5000 500      -> data/yolo_v3/
"""
import glob
import os
import random
import sys

import cv2
import numpy as np

import render as R
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N_TRAIN, N_VAL = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (5000, 500)
root = 'data/yolo_v3'
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg')) or sorted(
    glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'rubik_solver_AR', 'bench',
                           'data', 'backgrounds', '*.jpg')))
assert backgrounds, 'no background photos: see make_yolo_data_v2.py / bench/README.md (COCO128)'
NO_CUBE = 0.05        # share of frames with no cube
MIN_FACING = 0.10     # each of the three sides must face the camera at least this much (cosine)

# Harder than render.py's 'hard': applied to about half the frames.
R.LEVELS['extreme'] = dict(wb=0.3, gain=(0.35, 1.6), glare_p=0.6, glare_max=1.0, hand_p=0.85, noise=(4, 14),
                           blur=(0.6, 2.6), motion_p=0.45, jpeg=(35, 75), ambient=(0.2, 0.7))


def label_line(k, w, h):
    x0, y0 = k.min(0) - 6
    x1, y1 = k.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    out = ['0'] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for x, y in k:
        out += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    return ' '.join(out) + '\n'


def facing(pose, face):
    """How squarely a side faces the camera (cosine between its normal and the view direction)."""
    n = pose.R @ np.asarray(R.FACE_NORMAL[face], float)
    c = pose.to_cam(np.asarray(R.FACE_NORMAL[face], float) * R.HALF)
    return float(n @ -c) / (np.linalg.norm(c) + 1e-9)


def hard_pose(rng):
    """Any corner-on hold from nearly face-on to a clean three-side view, near or far."""
    kind = rng.uniform()
    if kind < 0.35:      # one side nearly edge-on: yaw or pitch pushed to the extremes
        yaw = rng.uniform(-84, -6) if rng.uniform() < 0.5 else rng.uniform(-60, -30)
        pitch = rng.uniform(4, 70) if rng.uniform() < 0.6 else rng.uniform(15, 45)
    else:
        yaw, pitch = rng.uniform(-70, -20), rng.uniform(8, 58)
    Rm = R.rot(yaw, pitch, rng.uniform(-45, 45))
    far = rng.uniform() < 0.35
    cube_px = rng.uniform(55, 160) if far else rng.uniform(150, 440)
    dist = R.FOCAL * 1.6 / cube_px + R.HALF
    t = (rng.uniform(-0.45, 0.45), rng.uniform(-0.35, 0.35)) if far else (rng.uniform(-0.3, 0.3), rng.uniform(-0.22, 0.22))
    return R.Pose(Rm, (t[0] * dist, t[1] * dist, -dist))


def heavy_fingers(img, pose, rng):
    """Extra fingers crossing the stickers (a hand turning the cube)."""
    k = R.gt_keypoints(pose)
    centre = k.mean(0)
    size = float(np.ptp(k, 0).max())
    skin = R.skin_tone(rng)
    for _ in range(rng.integers(1, 4)):
        a = rng.uniform(0, 2 * np.pi)
        d = np.array([np.cos(a), np.sin(a)])
        tip = centre + d * size * rng.uniform(0.05, 0.35)
        base = centre + d * size * rng.uniform(0.9, 1.4)
        width = max(3, int(size * rng.uniform(0.06, 0.1)))
        col = tuple(float(v) for v in skin * rng.uniform(0.85, 1.05))
        cv2.line(img, tuple(int(v) for v in tip), tuple(int(v) for v in base), col, width * 2, cv2.LINE_AA)
        cv2.circle(img, tuple(int(v) for v in tip), width, col, -1, cv2.LINE_AA)


def empty_frame(rng, photo):
    img = R.background(rng, photo)
    if rng.uniform() < 0.5:  # a hand with nothing in it
        p = R.Pose(R.rot(-45, 30, 0), (0, 0, -3.0))
        R.add_palm(img, p, rng)
    img = np.clip(img + rng.normal(0, rng.uniform(2, 8), img.shape), 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, int(rng.uniform(50, 90))])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


for split, n, seed in (('train', N_TRAIN, 5000), ('val', N_VAL, 6000)):
    os.makedirs(f'{root}/images/{split}', exist_ok=True)
    os.makedirs(f'{root}/labels/{split}', exist_ok=True)
    rng, srng = np.random.default_rng(seed), random.Random(seed)
    photos = {}
    i = 0
    while i < n:
        bg_path = backgrounds[int(rng.integers(len(backgrounds)))] if rng.uniform() < 0.8 else None
        photo = photos.setdefault(bg_path, cv2.imread(bg_path)) if bg_path else None
        if rng.uniform() < NO_CUBE:
            cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', empty_frame(rng, photo))
            open(f'{root}/labels/{split}/{i:05d}.txt', 'w').close()
            i += 1
            continue
        pose = hard_pose(rng)
        if min(facing(pose, f) for f in 'UFR') < MIN_FACING:
            continue  # a side turned away: not a corner-on view
        k = R.gt_keypoints(pose)
        if k.min() < 2 or k[:, 0].max() > R.W - 2 or k[:, 1].max() > R.H - 2:
            continue  # all 7 corners in the picture
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        level = 'extreme' if rng.uniform() < 0.5 else ('hard' if rng.uniform() < 0.6 else 'real')
        img = R.render(state, pose, rng, level, style='stickerless' if rng.uniform() < 0.55 else 'stickered',
                       bg_photo=photo, hand='hand')
        if rng.uniform() < 0.45:
            img = img.copy()
            heavy_fingers(img, pose, rng)
        if rng.uniform() < 0.4 and k[:, 1].max() - k[:, 1].min() < 350:  # 16:9 crop, if the cube fits
            top = int(np.clip(rng.uniform(k[:, 1].max() - 358, k[:, 1].min() - 2), 0, R.H - 360))
            if k[:, 1].min() - top > 2 and k[:, 1].max() - top < 358:
                img, k = img[top:top + 360], k - np.float32([0, top])
        h, w = img.shape[:2]
        cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', img)
        with open(f'{root}/labels/{split}/{i:05d}.txt', 'w') as fh:
            fh.write(label_line(k, w, h))
        i += 1
    print(split, n)
with open(f'{root}/cube.yaml', 'w') as fh:
    fh.write(f"path: {os.path.abspath(root)}\ntrain: images/train\nval: images/val\n"
             "kpt_shape: [7, 3]\nflip_idx: [0, 3, 2, 1, 6, 5, 4]\nnames:\n  0: cube\n")
print('done', N_TRAIN, N_VAL)
