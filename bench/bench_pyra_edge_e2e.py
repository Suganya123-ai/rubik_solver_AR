"""Pyraminx end to end on rendered edge-on frames (true corner points), the way the app asks for it:
scan view 1 (an edge toward the camera, two faces), the same view again (must be refused: nothing
new), then turned around (the other two faces); then a guided solve, seen edge-on from random edges,
with one deliberate wrong move first. Reports scans right, wrong move caught, false wrong calls,
solves finished.
    PYTHONPATH=.. python bench_pyra_edge_e2e.py normal|hard|real [N]"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_pyra as P  # noqa: E402
from pyra.geometry import MOVES  # noqa: E402
from pyra.model import is_solved, random_state  # noqa: E402
from pyra.scan import ScanSession  # noqa: E402
from pyra.solver import solve  # noqa: E402
from pyra.tracker import TrackSession, letter_features  # noqa: E402
from pyra.view import EDGE_HOLDS, face_share, read_stickers  # noqa: E402

LEVEL = sys.argv[1] if len(sys.argv) > 1 else 'normal'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
rng = np.random.default_rng(41)


def frame(st, edge=None):
    for _ in range(300):
        e = edge if edge and rng.uniform() < 0.5 else (edge[::-1] if edge else None)   # either end on top
        e, pose = P.edge_on_pose(rng, edge=e, tilt_max=25)
        if not P.valid_edge_view(pose, e, 0.12):
            continue
        k, names = P.edge_keypoints(pose, e)
        if k.min() < 2 or k[:, 0].max() > 638 or k[:, 1].max() > 478:
            continue
        img = P.render(st, pose, rng, LEVEL, style='stickered' if rng.uniform() < 0.5 else 'stickerless', hand='none')
        return {'keypoints': k.tolist(), 'confident': True, 'view': 'edge', 'stickers': read_stickers(img, k, kind='edge'),
                'face_share': face_share(k, 'edge')}, names
    raise RuntimeError('no view')


def hold_still(s, fr, t):
    out = None
    for _ in range(8):
        t += 0.1
        out = s.feed(fr, now=t)
        if out['event'] or out.get('refused'):
            break
    return out, t + 4


ok_scan = ok_solve = refused_again = wrong_calls = missed = 0
for trial in range(N):
    phys = random_state(rng)
    s, t = ScanSession(), 0.0
    a, b = rng.choice(list('ULRB'), 2, replace=False)
    fr, first = frame(phys, (a, b))
    _, t = hold_still(s, fr, t)
    fr, _ = frame(phys, (a, b))                        # the same two faces again
    out, t = hold_still(s, fr, t)
    refused_again += out.get('refused') == 'nothing new'
    c, d = [x for x in 'ULRB' if x not in (a, b)]
    fr, _ = frame(phys, (c, d))                        # turned around: the other two
    _, t = hold_still(s, fr, t)
    if not s.result:
        print(trial, 'scan incomplete')
        continue
    to_phys = {EDGE_HOLDS[0][i]: first[i] for i in range(4)}   # scan frame -> physical corner names

    def phys_move(mv):
        return (to_phys[mv[0].upper()].lower() if mv[0].islower() else to_phys[mv[0]]) + mv[1:]
    plan = solve(np.array(list(s.result['state'])))
    test = phys.copy()
    for mv in plan:
        test = test[MOVES[phys_move(mv)]]
    good = is_solved(test)
    ok_scan += good
    if not good:
        print(trial, 'scan wrong')
        continue
    state = s.result['state']
    tr = TrackSession(state, plan, letter_features(s.rgbs, state))
    events = []

    def show():
        fr, _ = frame(phys)
        ev, out = None, None
        for _ in range(6):
            out = tr.feed(fr)
            if out['event'] and out['event'] != 'unsure':
                ev = out['event']
        out['event'] = ev
        return out
    wrong = [mv for mv in ['U', 'L', 'R', 'B'] if mv != plan[0][0]][0]
    phys = phys[MOVES[phys_move(wrong)]]
    ev = None
    for look in range(3):
        ev = show()['event']
        if ev not in (None, 'unsure'):
            break
    events.append(ev)
    if ev != 'wrong':
        print(trial, 'deliberate wrong move NOT caught')
        continue
    for _ in range(30):
        if tr.done:
            break
        phys = phys[MOVES[phys_move(tr.expected)]]
        for look in range(3):
            out = show()
            if out['event'] not in (None, 'unsure'):
                break
        events.append(out['event'])
        missed += out['event'] in (None, 'unsure')
        if out['event'] in (None, 'unsure'):
            break
    wrong_calls += events[1:].count('wrong')
    ok_solve += tr.done
    print(trial, 'wrong move caught:', events[0] == 'wrong', '| solved' if tr.done else '| NOT solved', '| plan', len(plan),
          '| false wrong calls', events[1:].count('wrong'))
print(f'{LEVEL}: scans right {ok_scan}/{N}, same faces refused {refused_again}/{N}, solves to the end {ok_solve}/{N}, '
      f'false wrong calls {wrong_calls}, moves needing a second look {missed}')
