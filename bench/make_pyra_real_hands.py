"""Pyramids in real hands: training pictures made from real camera frames.

Takes real frames from the cube apps' recordings (data/scans, data/sessions in
the given app folders: the user's own hands holding a cube, real light, real
webcam and glasses cameras). In each frame where a cube is found:
  1. the hands are found (MediaPipe) and their skin marked;
  2. the cube is painted out;
  3. a Pyraminx is rendered where the cube was (same place and size, random
     turn and colours);
  4. the fingers that were in front of the cube are put back on top.
The frames themselves (with the cube) are kept as counter-examples: a cube is
not a pyramid (empty label).

    PYTHONPATH=.. python make_pyra_real_hands.py ../models/cube_pose_v3.pt <app folder> [...]
        -> data/pyra_real_hands/ (images, labels, train / val)
With EDGE=1 the pyramid is drawn edge-on (class 1, see render_pyra.edge_on_pose) instead, into
data/pyra_edge_hands/, and the cube frames are not kept again.
"""
import glob
import os
import random
import sys

import cv2
import numpy as np

import render as R
import render_pyra as P
from pyra.model import random_state

EDGE = os.environ.get('EDGE') == '1'
root = 'data/pyra_edge_hands' if EDGE else 'data/pyra_real_hands'
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", 1600))
BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
         (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


def to_640(img):
    h, w = img.shape[:2]
    s = min(R.W / w, R.H / h)
    small = cv2.resize(img, (int(w * s), int(h * s)))
    out = np.full((R.H, R.W, 3), 0, np.uint8)
    y, x = (R.H - small.shape[0]) // 2, (R.W - small.shape[1]) // 2
    out[y:y + small.shape[0], x:x + small.shape[1]] = small
    if small.shape != out.shape:   # fill the borders with stretched edges, not black bars
        out = cv2.resize(small, (R.W, R.H))
    return out


def skin_mask(img, hands):
    """The hands' skin: thick lines along each finger, kept where the colour is close to the hand's skin."""
    mask = np.zeros(img.shape[:2], np.uint8)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    for hand in hands:
        pts = np.array(hand['points'], float)
        size = np.ptp(pts, 0).max()
        bones = np.zeros_like(mask)
        for a, b in BONES:
            cv2.line(bones, tuple(map(int, pts[a])), tuple(map(int, pts[b])), 255, max(4, int(size * 0.16)))
        cv2.fillConvexPoly(bones, cv2.convexHull(pts[[0, 1, 5, 9, 13, 17]].astype(np.int32)), 255)
        inside = bones > 0
        if not inside.any():
            continue
        ref = np.median(lab[inside], axis=0)
        close = np.linalg.norm(lab - ref, axis=2) < 22
        mask |= (inside & close).astype(np.uint8) * 255
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def pose_at(rng, centre, size_px):
    """A random corner-on hold of the pyramid at a picture position and size."""
    for _ in range(200):
        near, pose = P.edge_on_pose(rng, tilt_max=30) if EDGE else P.corner_on_pose(rng, tilt_max=40)
        dist = R.FOCAL * 1.6 * P.SCALE / size_px + P.SCALE
        X = (centre[0] - R.W / 2) * dist / R.FOCAL
        Y = -(centre[1] - R.H / 2) * dist / R.FOCAL
        pose = R.Pose(pose.R, (X, Y, -dist))
        if not (P.valid_edge_view(pose, near, 0.12) if EDGE else P.valid_view(pose, near, 0.08)):
            continue
        k, _ = P.edge_keypoints(pose, near) if EDGE else P.keypoints(pose, near)
        if k.min() > 2 and k[:, 0].max() < R.W - 2 and k[:, 1].max() < R.H - 2:
            return near, pose, k
    return None


def label_line(k, w, h, cls=0):
    x0, y0 = k.min(0) - 6
    x1, y1 = k.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    out = [str(cls)] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for x, y in k:
        out += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    return ' '.join(out) + '\n'


def main():
    from ultralytics import YOLO
    sys.path.insert(0, '..')
    from vision.hands import HandTracker
    cube_model = YOLO(sys.argv[1])
    hands_model = HandTracker()
    frames = []
    for app in sys.argv[2:]:
        frames += glob.glob(os.path.join(app, 'data', 'scans', '*', '*', '*.jpg'))
        frames += glob.glob(os.path.join(app, 'data', 'sessions', '*', '*', '*.jpg'))
    random.Random(3).shuffle(frames)
    frames = frames[:MAX_FRAMES]
    rng = np.random.default_rng(19 if EDGE else 9)
    for split in ('train', 'val'):
        os.makedirs(f'{root}/images/{split}', exist_ok=True)
        os.makedirs(f'{root}/labels/{split}', exist_ok=True)
    made = negatives = 0
    for n, path in enumerate(frames):
        img = cv2.imread(path)
        if img is None:
            continue
        img = to_640(img)
        split = 'val' if n % 10 == 0 else 'train'
        r = cube_model.predict(img, imgsz=640, verbose=False, device='mps')[0]
        if len(r.boxes) == 0 or float(r.boxes.conf.max()) < 0.6:
            continue
        cube = r.keypoints.xy[int(r.boxes.conf.argmax())].cpu().numpy()
        # the frame as it is: a cube, not a pyramid
        if not EDGE and rng.uniform() < 0.5:
            cv2.imwrite(f'{root}/images/{split}/neg_{n:05d}.jpg', img)
            open(f'{root}/labels/{split}/neg_{n:05d}.txt', 'w').close()
            negatives += 1
        hands = hands_model.detect(img)
        skin = skin_mask(img, hands)
        hull = cv2.convexHull(cube.astype(np.int32))
        cube_mask = cv2.fillConvexPoly(np.zeros(img.shape[:2], np.uint8), hull, 255)
        grow = max(15, int(np.ptp(cube, 0).max() * 0.18))   # the stickers often reach past the corner points
        cube_mask = cv2.dilate(cube_mask, np.ones((grow, grow), np.uint8))
        clean = cv2.inpaint(img, cv2.bitwise_and(cube_mask, cv2.bitwise_not(skin)), 15, cv2.INPAINT_TELEA)
        clean = np.where(cube_mask[..., None] > 0, cv2.GaussianBlur(clean, (0, 0), 6), clean)   # no leftover sticker colours
        size = float(np.ptp(cube, 0).max()) * rng.uniform(1.1, 1.4)
        placed = pose_at(rng, cube.mean(0), size)
        if placed is None:
            continue
        near, pose, k = placed
        sil = []
        level = 'normal' if rng.uniform() < 0.6 else 'hard'
        out = P.render(random_state(rng), pose, rng, level, style='stickerless' if rng.uniform() < 0.5 else 'stickered',
                       background=clean, out_mask=sil)
        front = (skin > 0) & (sil[0] > 0)
        out[front] = img[front]                         # real fingers in front of the puzzle
        cv2.imwrite(f'{root}/images/{split}/pos_{n:05d}.jpg', out)
        with open(f'{root}/labels/{split}/pos_{n:05d}.txt', 'w') as fh:
            fh.write(label_line(k, R.W, R.H, 1 if EDGE else 0))
        made += 1
    print('frames looked at', len(frames), '| pyramids in real hands', made, '| cube counter-examples', negatives)


if __name__ == '__main__':
    main()
