"""Day 4 check: full two-view scans through the app's real pipeline.

For each scrambled cube: render view 1 (Top/Front/Right) and view 2 (the cube
flipped as the app instructs: Bottom/Left/Back), find the corner points (true
points, or the YOLO model), read the 27 stickers per view, assemble the 54,
name the colours and validate. A scan counts as right when the cube state it
produces (which sticker matches which centre) is exactly the true state; the
colour names themselves don't matter to the solver. "Wrong" means a scan was
accepted but is wrong (dangerous); "rejected" means validation caught it and
the app asks for a rescan (safe). Target: >= 95% of scans right."""
import glob
import json
import os
import random
import sys

import cv2
import numpy as np

import render as R
from cube.cube_state import FACE_OFFSET, FACES, solved_state
from cube.moves import ALL_MOVES, apply_moves
from cube.scan import VIEW_ROTATIONS, assemble, scan_result
if os.environ.get('SCAN_IMPL'):  # e.g. SCAN_IMPL=/path/to/dir/old_scan.py to compare another colour method
    sys.path.insert(0, os.path.dirname(os.environ['SCAN_IMPL']))
    scan_result = __import__(os.path.basename(os.environ['SCAN_IMPL'])[:-3]).scan_result
from vision.reader import read_three_faces

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
MODEL = sys.argv[2] if len(sys.argv) > 2 else '../models/cube_pose_v2.pt'
backgrounds = sorted(glob.glob('data/backgrounds/*.jpg'))

from vision.detector import CubeDetector  # noqa: E402
detector = CubeDetector(MODEL)

results = {}
for style in ('stickerless', 'stickered'):
    for level in os.environ.get('LEVELS', 'normal,hard,real').split(','):
        rng = np.random.default_rng((11 if style == 'stickerless' else 12) * 10 + ('normal', 'hard', 'real').index(level))
        srng = random.Random(21)
        tally = {f'{s}_{k}': 0 for s in ('gt', 'yolo')
                 for k in ('auto_ok', 'auto_wrong', 'check', 'final_ok', 'final_wrong', 'rejected', 'checked_stickers')}
        tally['yolo_found_both'] = 0
        for i in range(N):
            state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
            truth = {f: [R.LETTER_TO_COLOR[x] for x in state[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}
            pal, session = R.cube_palette(rng, style), R.new_session(rng, level)
            readings = {'gt': {}, 'yolo': {}}
            for view in (1, 2):
                cam = R.corner_pose_wide(rng)
                pose = R.Pose(cam.R @ VIEW_ROTATIONS[view], cam.t)  # the cube as the user holds it
                photo = cv2.imread(backgrounds[int(rng.integers(len(backgrounds)))]) if backgrounds else None
                frame = R.render(state, pose, rng, level, pal=pal, session=session, style=style, bg_photo=photo,
                                 hand='hand')
                readings['gt'][view] = read_three_faces(frame, R.gt_keypoints(cam))  # picture corners
                found = detector.detect(frame)
                readings['yolo'][view] = read_three_faces(frame, found[0]) if found else None
            for src in ('gt', 'yolo'):
                views = readings[src]
                if any(v is None for v in views.values()):
                    continue
                if src == 'yolo':
                    tally['yolo_found_both'] += 1
                try:
                    rgbs = assemble(views)
                except ValueError:
                    tally[f'{src}_rejected'] += 1
                    continue
                res = scan_result(rgbs)
                centers = res['centers']
                true_names = truth  # the real colours: a scan that names a colour wrongly is wrong
                if not res['doubtful']:  # accepted with nothing to check
                    if not res['valid']:
                        tally[f'{src}_rejected'] += 1
                        continue
                    right = res['colors'] == true_names
                    tally[f'{src}_auto_ok' if right else f'{src}_auto_wrong'] += 1
                    tally[f'{src}_final_ok' if right else f'{src}_final_wrong'] += 1
                    continue
                tally[f'{src}_check'] += 1
                locked = {}
                tally[f'{src}_checked_stickers'] += 0
                for _ in range(4):  # simulated user: confirms/corrects each highlighted sticker
                    tally[f'{src}_checked_stickers'] += len(res['doubtful'])
                    for f, k in res['doubtful']:
                        locked[(f, k)] = true_names[f][k]
                    res = scan_result(rgbs, locked=locked)
                    if not res['doubtful']:
                        break
                right = res['valid'] and res['colors'] == true_names
                tally[f'{src}_final_ok' if right else f'{src}_final_wrong'] += 1
        key = f'{style}|{level}'
        results[key] = {k: 100 * v / N for k, v in tally.items()}
        r = results[key]
        for src, label in (('gt', 'true points'), ('yolo', 'YOLO')):
            print(f"{style:11s} {level:6s} {label:11s} | final right {r[src + '_final_ok']:5.1f}%  WRONG {r[src + '_final_wrong']:4.1f}%"
                  f"  rejected {r[src + '_rejected']:4.1f}% | no check needed {r[src + '_auto_ok'] + r[src + '_auto_wrong']:5.1f}%"
                  f" (WRONG {r[src + '_auto_wrong']:.1f}%) | stickers to check per scan {r[src + '_checked_stickers'] / 100:.1f}")
if not os.environ.get('SCAN_IMPL'):
    json.dump({'n': N, 'model': os.path.basename(MODEL), 'results': results},
              open('results/results_two_view_scan.json', 'w'), indent=1)
