"""Real frames labelled by the corner-only model (make_real_pseudo.py) carry all 7 corners, even when
the cube was held nearly edge-on (a side barely showing, its corners squashed onto the next ones).
This names their hold for the any-hold model, from how big each side looks next to the front:
a side under HIDDEN of the front's area counts as not seen (its own far corner hidden), one over
SEEN as seen; frames with a side in between are left out (ambiguous).
    python relabel_real_holds.py data/real_pseudo data/real_pseudo_new -> data/real_holds/
"""
import glob
import os
import shutil
import sys

import numpy as np

HIDDEN, SEEN = 0.12, 0.25
HIDE = {0: (), 1: (4,), 2: (2,), 3: (2, 3, 4)}
root = 'data/real_holds'


def area(k, idx):
    q = k[list(idx)]
    return 0.5 * abs(sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4)))


counts = {}
for src in sys.argv[1:]:
    for split in ('train', 'val'):
        os.makedirs(f'{root}/images/{split}', exist_ok=True)
        os.makedirs(f'{root}/labels/{split}', exist_ok=True)
        for lab in sorted(glob.glob(f'{src}/labels/{split}/*.txt')):
            v = open(lab).read().split()
            if not v:
                continue
            k = np.array(list(map(float, v[5:]))).reshape(7, 3)[:, :2]
            f = area(k, (1, 0, 5, 6)) or 1e-9
            u, r = area(k, (2, 3, 0, 1)) / f, area(k, (0, 3, 4, 5)) / f
            if any(HIDDEN <= x < SEEN for x in (u, r)):
                counts['skipped'] = counts.get('skipped', 0) + 1
                continue
            cls = {(True, True): 0, (True, False): 1, (False, True): 2, (False, False): 3}[(u >= SEEN, r >= SEEN)]
            out = [str(cls)] + v[1:5]
            for i, (x, y) in enumerate(k):
                out += ['0', '0', '0'] if i in HIDE[cls] else [f'{x:.6f}', f'{y:.6f}', '2']
            name = f"{os.path.basename(src)}_{os.path.basename(lab)[:-4]}"
            shutil.copy(lab.replace('/labels/', '/images/')[:-4] + '.jpg', f'{root}/images/{split}/{name}.jpg')
            with open(f'{root}/labels/{split}/{name}.txt', 'w') as fh:
                fh.write(' '.join(out) + '\n')
            counts[cls] = counts.get(cls, 0) + 1
print({({0: 'corner', 1: 'top_front', 2: 'front_right', 3: 'face'}.get(c, c)): n for c, n in counts.items()})
