"""The phone's corner follower (vision/phone.py CornerFollower) on a recorded glasses session: the model
(the phone's finder, phone_models.py) on every EVERY-th frame, the follower in between. For the frames
followed: how often following worked, and how far its corners are from the model's on the same frame
(% of the cube's size); and how many model runs a frame that leaves.

    PYTHONPATH=.. python phone_follow.py <model.onnx> [EVERY]
"""
import sys

import cv2
import numpy as np

from phone_models import FRAMES, Finder
from vision.phone import CornerFollower

model, every = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2
f, fol = Finder(model), CornerFollower()
since, errs, tried, worked, runs0 = 0, [], 0, 0, 0
for path in FRAMES:
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if f.around is not None and since < every - 1:
        since += 1
        tried += 1
        k = fol.follow(gray)
        truth = f.run(img, f.around)                       # what the model would have said (not counted as a run)
        f.runs -= 1
        if k is not None:
            worked += 1
            if truth[1] >= 0.5:
                errs.append(np.max(np.linalg.norm(k - truth[0], axis=1)) / np.ptp(truth[0], 0).max() * 100)
            continue
    since = 0
    got = f.find(img)
    if got is not None and got[1] >= 0.5:
        fol.seen(gray, got[0], got[1])
    else:
        fol.reset()
print(f'model every {every}: frames followed {tried}, following worked {worked} ({100 * worked / max(tried, 1):.0f}%), '
      f'corners vs the model: median {np.median(errs):.1f}%, 90th {np.percentile(errs, 90):.1f}% | model runs a frame {f.runs / len(FRAMES):.2f}')
