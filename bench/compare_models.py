"""Old cube finder against new, on the same pictures.

1. Hard renders (data/yolo_v3 val, exact corners known): found, corner error.
2. The earlier test renders (data/yolo_v2 val): the new model must not be worse.
3. Real frames the models never trained on (HOLD_OUT sessions of the apps,
   local recordings): how often each finds the cube; the frames the old one
   missed are the interesting ones (no exact answer, so also saved as a
   picture grid to look at).

    python compare_models.py ../models/cube_pose_v2.pt ../models/cube_pose_v3.pt
"""
import glob
import json
import os
import sys

import cv2
import numpy as np
from ultralytics import YOLO

OLD, NEW = YOLO(sys.argv[1]), YOLO(sys.argv[2])
CONF = 0.5   # what the app counts as "found"
V2_VAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'rubik_solver_AR', 'bench', 'data',
                      'yolo_v2', 'images', 'val')
REAL = sorted(glob.glob('/Users/mohammadrebh/rubik_solver_AR_glasses/data/sessions/2026-10-13/173502/*.jpg'))
OUT = sys.argv[3] if len(sys.argv) > 3 else 'compare_out'
os.makedirs(OUT, exist_ok=True)


def best(model, img):
    r = model.predict(img, imgsz=640, verbose=False, device='mps')[0]
    if len(r.boxes) == 0:
        return 0.0, None
    i = int(r.boxes.conf.argmax())
    return float(r.boxes.conf[i]), r.keypoints.xy[i].cpu().numpy()


def labelled(images):
    rows = {'old': [], 'new': []}
    for path in images:
        lab = open(path.replace('/images/', '/labels/').rsplit('.', 1)[0] + '.txt').read().split()
        img = cv2.imread(path)
        h, w = img.shape[:2]
        truth = np.array(list(map(float, lab[5:])), float).reshape(7, 3)[:, :2] * [w, h] if lab else None
        for name, model in (('old', OLD), ('new', NEW)):
            conf, k = best(model, img)
            found = conf >= CONF
            if truth is None:
                rows[name].append({'empty': True, 'false_cube': found})
            else:
                size = float(np.ptp(truth, 0).max())
                err = float(np.abs(k - truth).max() / size * 100) if found else None
                rows[name].append({'empty': False, 'found': found, 'err': err})
    out = {}
    for name, r in rows.items():
        cubes = [x for x in r if not x['empty']]
        errs = [x['err'] for x in cubes if x['found']]
        empties = [x for x in r if x['empty']]
        out[name] = {'cube pictures': len(cubes), 'found %': round(100 * len(errs) / max(1, len(cubes)), 1),
                     'corner error, median % of cube size': round(float(np.median(errs)), 2) if errs else None,
                     'corner error, 90th percentile %': round(float(np.percentile(errs, 90)), 2) if errs else None,
                     'empty pictures': len(empties),
                     'cubes seen in empty pictures': sum(x['false_cube'] for x in empties)}
    return out


report = {
    'hard renders (v3 val)': labelled(sorted(glob.glob('data/yolo_v3/images/val/*.jpg'))),
    'earlier renders (v2 val)': labelled(sorted(glob.glob(os.path.join(V2_VAL, '*.jpg')))[:300]),
}
found = {'old': 0, 'new': 0, 'new only': 0, 'old only': 0}
gained = []
for path in REAL:
    img = cv2.imread(path)
    co, ko = best(OLD, img)
    cn, kn = best(NEW, img)
    fo, fn = co >= CONF, cn >= CONF
    found['old'] += fo
    found['new'] += fn
    found['new only'] += fn and not fo
    found['old only'] += fo and not fn
    if fn and not fo and len(gained) < 12:
        im = img.copy()
        for j, (x, y) in enumerate(kn):
            cv2.circle(im, (int(x), int(y)), 5, (0, 0, 255) if j == 0 else (0, 255, 255), -1)
        gained.append(cv2.resize(im, (320, 236)))
report['real glasses frames (never trained on)'] = {'frames': len(REAL), **found}
if gained:
    while len(gained) % 4:
        gained.append(np.zeros_like(gained[0]))
    grid = np.vstack([np.hstack(gained[i:i + 4]) for i in range(0, len(gained), 4)])
    cv2.imwrite(os.path.join(OUT, 'found_only_by_new.jpg'), grid)
print(json.dumps(report, indent=2))
json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=2)
