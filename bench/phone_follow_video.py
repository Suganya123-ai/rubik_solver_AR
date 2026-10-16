"""The phone's corner follower on continuous video: a rendered cube held up and moved the way a hand
moves it (still, then drifting and turning, then still), 15 frames a second, with the true corners of
every frame. The phone's finder runs on every EVERY-th frame while it follows the cube, the follower
(vision/phone.py) in between. Reports the corner error against the truth (% of the cube's size) for the
model's frames and the followed frames, how often following failed (then the model runs instead), and
the model runs a frame.

    PYTHONPATH=.. python phone_follow_video.py <model.onnx> [EVERY] [SECONDS]
"""
import glob
import math
import sys

import cv2
import numpy as np

import render as R
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves
from phone_models import Finder
from vision.phone import CornerFollower

model = sys.argv[1]
every = int(sys.argv[2]) if len(sys.argv) > 2 else 2
seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 40
FPS = 15
rng0 = np.random.default_rng(5)
state = apply_moves(solved_state(), [ALL_MOVES[int(i)] for i in rng0.integers(len(ALL_MOVES), size=20)]).arr
photo = cv2.imread(sorted(glob.glob('data/backgrounds/*.jpg'))[11])


def pose_at(t):
    """A hand holding the cube up: still for a while, then moving (drift, a turn, a nod), then still."""
    calm = 0.5 - 0.5 * math.cos(2 * math.pi * t / 8.0)      # 0 (still) .. 1 (moving), an 8 s cycle
    yaw = -45 + 10 * calm * math.sin(1.3 * t)
    pitch = 30 + 6 * calm * math.sin(0.9 * t + 1)
    roll = 5 * calm * math.sin(0.7 * t)
    size = 230 + 40 * math.sin(0.25 * t)
    dist = R.FOCAL * 1.6 / size + R.HALF
    x, y = 0.12 * calm * math.sin(0.8 * t), 0.08 * calm * math.cos(0.6 * t) + 0.04
    return R.Pose(R.rot(yaw, pitch, roll), (x * dist, y * dist, -dist))


f, fol = Finder(model), CornerFollower()
since, model_err, follow_err, failed, followed = 0, [], [], 0, 0
n = int(seconds * FPS)
for i in range(n):
    pose = pose_at(i / FPS)
    img = R.render(state, pose, np.random.default_rng(1), 'normal', bg_photo=photo, hand='fingers')
    img = cv2.resize(img, (640, 472))          # the phone's window size
    truth = R.gt_keypoints(pose) * [640 / R.W, 472 / R.H]
    size = np.ptp(truth, 0).max()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if f.around is not None and since < every - 1:
        since += 1
        k = fol.follow(gray)
        if k is not None:
            followed += 1
            follow_err.append(np.max(np.linalg.norm(k - truth, axis=1)) / size * 100)
            continue
        failed += 1
    since = 0
    got = f.find(img)
    if got is not None and got[1] >= 0.5:
        fol.seen(gray, got[0], got[1])
        model_err.append(np.max(np.linalg.norm(got[0] - truth, axis=1)) / size * 100)
    else:
        fol.reset()
print(f'model every {every}, {n} frames: model frames {len(model_err)} (corner error median {np.median(model_err):.1f}%), '
      f'followed {followed} (median {np.median(follow_err) if follow_err else float("nan"):.1f}%, 90th '
      f'{np.percentile(follow_err, 90) if follow_err else float("nan"):.1f}%), following failed {failed} | model runs a frame {f.runs / n:.2f}')
