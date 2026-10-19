"""Colour test: whole cubes (6 scanned faces, one lighting session per cube).
Stickers are sampled at their true positions, so this isolates the
colour-naming step from sticker finding."""
import json
import random
import sys

import cv2
import numpy as np

import render as R
from cube.color_detect import COLOR_NAMES, _rgb_to_hsv, classify_hsv, rebalance_colors
from cube.cube_state import FACE_OFFSET, FACES, solved_state
from cube.moves import ALL_MOVES, apply_moves
from cube.validation import validate_scan

sys.path.insert(0, 'third_party/qbr/src')
sys.path.insert(0, '../third_party')  # vendored rubikscolorresolver
from helpers import bgr2lab, ciede2000  # noqa: E402  (qbr)
from rubikscolorresolver.solver import RubiksColorSolverGeneric  # noqa: E402
from ephynes_port import face_colours  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
QBR_PALETTE = {'red': (0, 0, 255), 'orange': (0, 165, 255), 'blue': (255, 0, 0), 'green': (0, 255, 0),
               'white': (255, 255, 255), 'yellow': (0, 255, 255)}
RESOLVER_SIDES = ['U', 'L', 'F', 'R', 'B', 'D']  # its square numbering order


def sample(frame, pose):
    out = []
    for k in range(9):
        q = np.float32([pose.project(p) for p in R.sticker_quad_3d('F', k, inset=0.3)])
        mask = np.zeros(frame.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, q.astype(np.int32), 255)
        px = frame[mask > 0]
        b, g, r = np.median(px, axis=0)
        out.append((float(r), float(g), float(b)))
    return out


def qbr_name(rgb, palette):
    lab = bgr2lab(rgb[::-1])
    return min(palette, key=lambda n: ciede2000(lab, bgr2lab(palette[n])))


def resolver(rgbs):
    data, i = {}, 1
    for side in RESOLVER_SIDES:
        for rgb in rgbs[side]:
            data[i] = tuple(int(round(v)) for v in rgb)
            i += 1
    c = RubiksColorSolverGeneric(3)
    c.write_debug_file = False
    c.enter_scan_data(data)
    c.crunch_colors()
    s = ''.join(c.cube_for_kociemba_strict())
    return {f: [R.LETTER_TO_COLOR[x] for x in s[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}


def methods(rgbs, truth):
    hsv = {f: [classify_hsv(*_rgb_to_hsv(c)) for c in rgbs[f]] for f in FACES}
    out = {'Current app: HSV thresholds (old)': hsv}
    fixed = {f: list(hsv[f]) for f in FACES}
    for f in FACES:
        fixed[f][4] = truth[f][4]  # the app makes you confirm 6 distinct centres
    out['Current app: centre rebalance (new)'] = rebalance_colors(fixed, rgbs, {}) or fixed
    out['qbr: default palette'] = {f: [qbr_name(c, QBR_PALETTE) for c in rgbs[f]] for f in FACES}
    calib = {truth[f][4]: tuple(rgbs[f][4][::-1]) for f in FACES}  # qbr calibrate mode: scan each centre
    out['qbr: calibrated palette'] = {f: [qbr_name(c, calib) for c in rgbs[f]] for f in FACES}
    out['rubiks-color-resolver'] = resolver(rgbs)
    out['ephynes: per-face colours (C# port)'] = {f: face_colours(rgbs[f]) for f in FACES}
    app = out['Current app: centre rebalance (new)']
    out['Combined: app rebalance, resolver if invalid'] = app if validate_scan(app)[1].ok else out['rubiks-color-resolver']
    return out


results = {}
for level in ('normal', 'hard'):
    rng = np.random.default_rng(7 if level == 'normal' else 8)
    srng = random.Random(11)
    acc = {}
    for i in range(N):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        truth = {f: [R.LETTER_TO_COLOR[x] for x in state[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}
        session, pal = R.new_session(rng, level), R.cube_palette(rng)
        rgbs = {}
        for f in FACES:
            pose = R.scan_pose(rng, aligned=True)
            frame = R.render(state, pose, rng, level, faces_override={'F': truth[f]}, pal=pal, session=session)
            rgbs[f] = sample(frame, pose)
        preds = methods(rgbs, truth)
        for name, pred in preds.items():
            right = sum(p == t for f in FACES for p, t in zip(pred[f], truth[f]))
            a = acc.setdefault(name, {'stickers': 0, 'cubes': 0})
            a['stickers'] += right
            a['cubes'] += right == 54
    results[level] = {name: {'sticker_acc_pct': 100 * a['stickers'] / (54 * N), 'cube_correct_pct': 100 * a['cubes'] / N}
                      for name, a in acc.items()}
    print(level)
    for name, r in results[level].items():
        print(f"   {name:38s} stickers {r['sticker_acc_pct']:6.2f}%   whole cube right {r['cube_correct_pct']:5.1f}%")
json.dump({'n': N, 'results': results}, open('results/results_color.json', 'w'), indent=1)
