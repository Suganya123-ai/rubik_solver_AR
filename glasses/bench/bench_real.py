"""Real-photo sanity check on dwalton76's 6 photos of a real 3x3 cube (a robot
holds it). Every detector gets the same crop; a face counts as found only if
every detected sticker's colour matches the known value for that position
(within 25 per channel, like the project's own test uses 15 on its exact sampling)."""
import json

import cv2
import numpy as np

from detectors import DETECTORS, timed

SIDES = ('U', 'L', 'F', 'R', 'B', 'D')
truth_rgb = {int(k): v for k, v in json.load(open('third_party/rubiks-cube-tracker/test-data/3x3x3-random-01.txt')).items()}
centres = {s: np.array(truth_rgb[i * 9 + 5], float) for i, s in enumerate(SIDES)}


def label(rgb):
    return min(centres, key=lambda s: np.linalg.norm(np.asarray(rgb, float) - centres[s]))


results = {d: {'faces_read': 0, 'ms': []} for d in DETECTORS}
for i, side in enumerate(SIDES):
    img = cv2.imread(f'third_party/rubiks-cube-tracker/test-data/3x3x3-random-01/rubiks-side-{side}.png')[160:980, 450:1450]
    want = [np.array(truth_rgb[i * 9 + 1 + k], float) for k in range(9)]
    for name, fn in DETECTORS.items():
        out, ms = timed(fn, img)
        results[name]['ms'].append(ms)
        if out is None:
            continue
        got = []
        for x, y in out:
            x, y = int(x), int(y)
            patch = img[max(0, y - 8):y + 8, max(0, x - 8):x + 8].reshape(-1, 3)
            b, g, r = np.median(patch, axis=0)
            got.append(np.array((r, g, b)))
        results[name]['faces_read'] += all(np.abs(g - w).max() < 25 for g, w in zip(got, want))
for name, r in results.items():
    print(f"{name:34s} faces read {r['faces_read']}/6   median {np.median(r['ms']):.1f} ms")
json.dump({n: {'faces_read': r['faces_read'], 'of': 6, 'ms_median': float(np.median(r['ms']))}
           for n, r in results.items()}, open('results/results_real.json', 'w'), indent=1)
