"""A test video for the Pyraminx web app (Chrome's fake camera plays it): a rendered
pyramid scanned from two corners, then solved move by move with one deliberate
wrong move and its undo, each position held still for a while.

    PYTHONPATH=.. python make_pyra_video.py out.y4m [seed]
Prints the plan the app should come up with (the scan names corners by the first view).
With EDGE=1 every view is edge-on (as the app's scan asks): the scan is two faces, then turned
around, the other two; the moves are then watched from the six edges in turn.
"""
import os
import sys

import cv2
import numpy as np

import render_pyra as P
from pyra.geometry import MOVES
from pyra.model import inverse, random_state
from pyra.solver import solve
from pyra.view import EDGE_HOLDS, HOLDS

EDGE = os.environ.get('EDGE') == '1'

FPS = 15
out_path = sys.argv[1]
rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
bg = cv2.imread(sorted(__import__('glob').glob('data/backgrounds/*.jpg'))[7])


def pose_for(near):
    while EDGE:
        e, pose = P.edge_on_pose(rng, edge=tuple(near), tilt_max=20)
        if not P.valid_edge_view(pose, e, 0.15):
            continue
        k, names = P.edge_keypoints(pose, e)
        if k.min() > 20 and k[:, 0].max() < 620 and k[:, 1].max() < 460 and np.ptp(k[:, 0]) > 180:
            return pose, names
    while True:
        n, pose = P.corner_on_pose(rng, near=near, tilt_max=20)
        if not P.valid_view(pose, n):
            continue
        k, names = P.keypoints(pose, n)
        if k.min() > 20 and k[:, 0].max() < 620 and k[:, 1].max() < 460 and np.ptp(k[:, 0]) > 180:
            return pose, names


frames = []


def hold(state, pose, seconds, jitter=0.6):
    session_rng = np.random.default_rng(int(rng.integers(1 << 30)))
    for _ in range(int(seconds * FPS)):
        img = P.render(state, pose, session_rng, 'normal', style='stickered', bg_photo=bg, hand='none')
        if jitter:
            img = cv2.warpAffine(img, np.float32([[1, 0, rng.normal(0, jitter)], [0, 1, rng.normal(0, jitter)]]), (640, 480))
        frames.append(img)


def blank(seconds):
    for _ in range(int(seconds * FPS)):
        frames.append(np.full((480, 640, 3), 60, np.uint8))


phys = random_state(rng)
pose1, first = pose_for('UL' if EDGE else 'U')
pose2, _ = pose_for('BR' if EDGE else 'L')
blank(9.0)                    # (the model loads meanwhile)
hold(phys, pose1, 3.0)        # scan view 1
blank(0.8)
hold(phys, pose2, 3.0)        # scan view 2 -> colour check
blank(4.0)                    # (the test clicks Solve here)
to_phys = {(EDGE_HOLDS if EDGE else HOLDS)[0][i]: first[i] for i in range(4)}


def phys_move(mv):
    c = to_phys[mv[0].upper()]
    return (c.lower() if mv[0].islower() else c) + mv[1:]


scan_frame = np.empty(36, '<U1')   # the position in the scan's naming, for planning
from pyra.geometry import OPPOSITE   # noqa: E402
from pyra.view import frame_permutation   # noqa: E402
to_scan = {v: k for k, v in to_phys.items()}
perm = frame_permutation(to_scan)
face_of_corner = {c: f for f, c in OPPOSITE.items()}
letter = {f: face_of_corner[to_scan[OPPOSITE[f]]] for f in OPPOSITE}   # each face is named by the corner it doesn't touch
scan_frame[perm] = [letter[x] for x in phys]
plan = solve(scan_frame)
print('plan the app should make:', ' '.join(plan))
wrong = [m for m in ('U', 'L', 'R', 'B') if m != plan[0][0]][0]
sequence = [wrong, inverse([wrong])[0]] + plan
for i, mv in enumerate(sequence):
    phys = phys[MOVES[phys_move(mv)]]
    blank(0.5)                                 # hands turning: no clean view
    pose, _ = pose_for(['UL', 'RB', 'UR', 'LB', 'UB', 'LR'][i % 6] if EDGE else 'ULRB'[i % 4])
    hold(phys, pose, 2.2)
hold(phys, pose1, 3.0)
with open(out_path, 'wb') as fh:
    fh.write(b'YUV4MPEG2 W640 H480 F15:1 Ip A1:1 C420jpeg\n')
    for f in frames:
        fh.write(b'FRAME\n' + cv2.cvtColor(f, cv2.COLOR_BGR2YUV_I420).tobytes())
print('frames', len(frames), 'seconds', len(frames) / FPS, 'sequence', ' '.join(sequence))
