"""Phase B test: before/after frames of the corner view; can the pipeline
tell what the user did? Keypoints come from ground truth, ground truth plus
detector-like noise, or a trained YOLO pose model."""
import json
import random
import sys
import time

import cv2
import numpy as np

import render as R
import tracking as T
from cube.cube_state import solved_state
from cube.moves import ALL_MOVES, apply_moves

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
SOURCES = sys.argv[2].split(',') if len(sys.argv) > 2 else ['gt', 'noise2', 'noise4', 'noise6']
yolo = None
if 'yolo' in SOURCES:
    from ultralytics import YOLO
    yolo = YOLO(sys.argv[3] if len(sys.argv) > 3 else '../models/cube_pose_synthetic.pt')


def kpts_for(source, frame, pose, rng):
    gt = R.gt_keypoints(pose)
    if source == 'gt':
        return gt
    if source.startswith('noise'):
        size = np.mean(np.linalg.norm(gt[1:] - gt[0], axis=1))
        return gt + rng.normal(0, int(source[5:]) / 100 * size, gt.shape).astype(np.float32)
    if source == 'yolo':
        r = yolo.predict(frame, imgsz=640, verbose=False)[0]
        if r.keypoints is None or len(r.keypoints.xy) == 0:
            return None
        i = int(r.boxes.conf.argmax())
        return r.keypoints.xy[i].cpu().numpy().astype(np.float32)


def fallback_refs(pal, session):
    out = {}
    for L, name in R.LETTER_TO_COLOR.items():
        bgr = np.clip(pal[name][::-1] * session['wb'][::-1] * session['gain'] * 0.8, 0, 255)
        lab = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
        out[L] = np.array([lab[0] * 100 / 255, lab[1] - 128, lab[2] - 128])
    return out


results = {}
for level in ('normal', 'hard'):
    for source in SOURCES:
        rng = np.random.default_rng(31 if level == 'normal' else 32)
        srng = random.Random(9)
        tally = {'correct': 0, 'wrong': 0, 'unsure': 0, 'lost': 0, 'no_kpts': 0}
        by_event = {}
        ms = []
        for i in range(N):
            state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
            expected = srng.choice(ALL_MOVES)
            u = srng.random()
            if u < 0.35:
                event, moves = 'did expected move', [expected]
            elif u < 0.60:
                event, moves = 'no move yet', []
            elif u < 0.90:
                event, moves = 'wrong single move', [srng.choice([m for m in ALL_MOVES if m != expected])]
            else:
                m1 = srng.choice(ALL_MOVES)
                event, moves = 'two quick moves', [m1, srng.choice([m for m in ALL_MOVES if m[0] != m1[0]])]
            after = apply_moves(solved_state().__class__(state.copy()), moves).arr
            session, pal = R.new_session(rng, level), R.cube_palette(rng)
            pose_a = R.corner_pose(rng)
            pose_b = R.jitter_pose(pose_a, rng)
            frame_a = R.render(state, pose_a, rng, level, pal=pal, session=session)
            frame_b = R.render(after, pose_b, rng, level, pal=pal, session=session)
            t0 = time.perf_counter()
            ka, kb = kpts_for(source, frame_a, pose_a, rng), kpts_for(source, frame_b, pose_b, rng)
            ev = by_event.setdefault(event, {'n': 0, 'correct': 0})
            ev['n'] += 1
            if ka is None or kb is None:
                tally['no_kpts'] += 1
                continue
            refs = T.references(T.read_three_faces(frame_a, ka), state, fallback_refs(pal, session))
            status, label = T.decide(T.read_three_faces(frame_b, kb), refs, T.candidates(state, expected))
            ms.append((time.perf_counter() - t0) * 1000)
            truth = ' '.join(moves) if moves else 'none'
            if status != 'ok':
                tally[status] += 1
            else:
                # Equivalent explanations (same resulting state) count as correct.
                same = ''.join(apply_moves(solved_state().__class__(state.copy()),
                                           [] if label == 'none' else label.split()).arr) == ''.join(after)
                tally['correct' if same else 'wrong'] += 1
                ev['correct'] += same
        key = f'{level}|{source}'
        results[key] = {k: 100 * v / N for k, v in tally.items()}
        results[key]['ms_median'] = float(np.median(ms)) if ms else None
        results[key]['by_event'] = {e: 100 * v['correct'] / v['n'] for e, v in by_event.items()}
        r = results[key]
        print(f"{level:6s} {source:7s} correct {r['correct']:5.1f}%  WRONG {r['wrong']:4.1f}%  unsure {r['unsure']:4.1f}%  "
              f"lost {r['lost']:4.1f}%  no-kpts {r['no_kpts']:4.1f}%  {r['ms_median']} ms  {r['by_event']}")
json.dump({'n': N, 'results': results}, open(f'results/results_tracking_{"_".join(SOURCES)}.json', 'w'), indent=1)
