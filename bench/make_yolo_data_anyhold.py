"""Training set for the any-hold cube model: the cube held any way round, not only corner-on.

Four ways of holding it (the model's classes), all with the same 7 keypoints as before, named from
the camera's point of view (0 the near top-right corner, 1 front-left-top, 2 back-left-top,
3 back-right-top, 4 back-right-bottom, 5 front-right-bottom, 6 front-left-bottom):
    0 corner       top, front and right seen (the hexagon)               all 7 points
    1 top_front    top and front seen (an edge toward the camera)        0 1 2 3 5 6  (4 hidden)
    2 front_right  front and right seen (a vertical edge toward it)      0 1 3 4 5 6  (2 hidden)
    3 face         only the front seen                                   0 1 5 6
Hidden points are labelled with visibility 0, so they don't count in training.

The cube is turned at random (any rotation); then, of the 24 ways to name its sides, the one closest
to "top up, right to the right, front toward the camera" names them, so the labels follow the view
and not the cube's colours (which are random anyway). Views of the bottom, left or back side under
that naming (the camera below the cube...) are skipped.

    python make_yolo_data_anyhold.py 6000 600      -> data/yolo_anyhold/
"""
import glob
import itertools
import os
import random
import sys

import cv2
import numpy as np

import render as R
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N_TRAIN, N_VAL = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (6000, 600)
root = 'data/yolo_anyhold'
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg')) or sorted(
    glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'rubik_solver_AR', 'bench',
                           'data', 'backgrounds', '*.jpg')))
assert backgrounds, 'no background photos: see make_yolo_data_v2.py / bench/README.md (COCO128)'

# Harder than render.py's 'hard' (as in make_yolo_data_v3.py).
R.LEVELS['extreme'] = dict(wb=0.3, gain=(0.35, 1.6), glare_p=0.6, glare_max=1.0, hand_p=0.85, noise=(4, 14),
                           blur=(0.6, 2.6), motion_p=0.45, jpeg=(35, 75), ambient=(0.2, 0.7))
CLASSES = ['corner', 'top_front', 'front_right', 'face']
VISIBLE_KPTS = {0: range(7), 1: (0, 1, 2, 3, 5, 6), 2: (0, 1, 3, 4, 5, 6), 3: (0, 1, 5, 6)}
SHARE = {0: 0.3, 1: 0.2, 2: 0.2, 3: 0.25}   # of the frames with a cube (the rest: 5% no cube)
NO_CUBE = 0.05
SEEN = 0.12      # a side counts as seen when it faces the camera at least this much (cosine)...
UNSEEN = 0.02    # ...and as hidden below this; views in between are ambiguous and skipped
ALL_CORNERS = [np.array(c, float) * R.HALF for c in itertools.product((1, -1), repeat=3)]


# (as in make_yolo_data_v3.py, which can't be imported: it runs when loaded)
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


def _rotations():
    out = []
    for axes in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            m = np.zeros((3, 3))
            for row, (col, sign) in enumerate(zip(axes, signs)):
                m[row, col] = sign
            if round(np.linalg.det(m)) == 1:
                out.append(m)
    return out


ROTATIONS = _rotations()


def random_rotation(rng):
    q = rng.normal(size=4)
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def facing(pose, face):
    n = pose.R @ np.asarray(R.FACE_NORMAL[face], float)
    c = pose.to_cam(np.asarray(R.FACE_NORMAL[face], float) * R.HALF)
    return float(n @ -c) / (np.linalg.norm(c) + 1e-9)


def view_named(pose):
    """The same pose with the cube's sides named from the view (see the module notes)."""
    def score(m):
        Rv = pose.R @ m.T
        return Rv[1, 1] + Rv[0, 0] + Rv[2, 2]     # top's normal up, right's to the right, front's toward the camera
    best = max(ROTATIONS, key=score)
    return R.Pose(pose.R @ best.T, pose.t)


def hold_class(view):
    """The class of a view-named pose, or None (ambiguous, or a side other than top/front/right seen)."""
    f = {x: facing(view, x) for x in 'UFRDLB'}
    if f['F'] < SEEN or any(f[x] > UNSEEN for x in 'DLB'):
        return None
    if any(UNSEEN < f[x] < SEEN for x in 'UR'):
        return None
    u, r = f['U'] >= SEEN, f['R'] >= SEEN
    return {(True, True): 0, (True, False): 1, (False, True): 2, (False, False): 3}[(u, r)]


def random_pose(rng):
    far = rng.uniform() < 0.3
    cube_px = rng.uniform(55, 160) if far else rng.uniform(150, 420)
    dist = R.FOCAL * 1.6 / cube_px + R.HALF
    t = (rng.uniform(-0.45, 0.45), rng.uniform(-0.35, 0.35)) if far else (rng.uniform(-0.3, 0.3), rng.uniform(-0.22, 0.22))
    return R.Pose(random_rotation(rng), (t[0] * dist, t[1] * dist, -dist))


def label_line(cls, box, k, w, h):
    x0, y0 = box.min(0) - 6
    x1, y1 = box.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    out = [str(cls)] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for i, (x, y) in enumerate(k):
        out += [f'{x / w:.6f}', f'{y / h:.6f}', '2'] if i in VISIBLE_KPTS[cls] else ['0', '0', '0']
    return ' '.join(out) + '\n'


def main():
    for split, n, seed in (('train', N_TRAIN, 7100), ('val', N_VAL, 7200)):
        os.makedirs(f'{root}/images/{split}', exist_ok=True)
        os.makedirs(f'{root}/labels/{split}', exist_ok=True)
        rng, srng = np.random.default_rng(seed), random.Random(seed)
        quota = {c: int(round(n * (1 - NO_CUBE) * s / sum(SHARE.values()))) for c, s in SHARE.items()}
        made = {c: 0 for c in SHARE}
        empties = n - sum(quota.values())
        photos = {}
        i = 0
        while i < n:
            bg_path = backgrounds[int(rng.integers(len(backgrounds)))] if rng.uniform() < 0.8 else None
            photo = photos.setdefault(bg_path, cv2.imread(bg_path)) if bg_path else None
            if empties > 0 and (all(made[c] >= quota[c] for c in SHARE) or rng.uniform() < NO_CUBE):
                empties -= 1
                cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', empty_frame(rng, photo))
                open(f'{root}/labels/{split}/{i:05d}.txt', 'w').close()
                i += 1
                continue
            pose = random_pose(rng)
            view = view_named(pose)
            cls = hold_class(view)
            if cls is None or made[cls] >= quota[cls]:
                continue
            k = np.float32([view.project(p) for p in R.CORNER_KPTS])
            box = np.float32([view.project(c) for c in ALL_CORNERS])
            kv = k[list(VISIBLE_KPTS[cls])]
            if kv.min() < 2 or kv[:, 0].max() > R.W - 2 or kv[:, 1].max() > R.H - 2:
                continue  # the seen corners all in the picture
            state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
            level = 'extreme' if rng.uniform() < 0.4 else ('hard' if rng.uniform() < 0.6 else 'real')
            img = R.render(state, pose, rng, level, style='stickerless' if rng.uniform() < 0.55 else 'stickered',
                           bg_photo=photo, hand='hand')
            if rng.uniform() < 0.4:
                img = img.copy()
                heavy_fingers(img, view, rng)
            if rng.uniform() < 0.4 and kv[:, 1].max() - kv[:, 1].min() < 350:  # 16:9 crop, if the cube fits
                top = int(np.clip(rng.uniform(kv[:, 1].max() - 358, kv[:, 1].min() - 2), 0, R.H - 360))
                if kv[:, 1].min() - top > 2 and kv[:, 1].max() - top < 358:
                    img, k, box = img[top:top + 360], k - np.float32([0, top]), box - np.float32([0, top])
            h, w = img.shape[:2]
            cv2.imwrite(f'{root}/images/{split}/{i:05d}.jpg', img)
            with open(f'{root}/labels/{split}/{i:05d}.txt', 'w') as fh:
                fh.write(label_line(cls, box, k, w, h))
            made[cls] += 1
            i += 1
        print(split, n, {CLASSES[c]: v for c, v in made.items()})
    names = ''.join(f'  {i}: {c}\n' for i, c in enumerate(CLASSES))
    with open(f'{root}/cube.yaml', 'w') as fh:
        fh.write(f"path: {os.path.abspath(root)}\ntrain: images/train\nval: images/val\n"
                 f"kpt_shape: [7, 3]\nflip_idx: [0, 1, 2, 3, 4, 5, 6]\nnames:\n{names}")
    print('done', N_TRAIN, N_VAL)


if __name__ == '__main__':
    main()
