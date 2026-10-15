"""Pyraminx end to end on rendered frames (true corner points): two-view scan, then a guided solve with one
deliberate wrong move first; reports scans right, wrong move caught, false wrong calls, solves finished.
    PYTHONPATH=.. python bench_pyra_e2e.py normal|hard|real [N]"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_pyra as P
from pyra.model import random_state, is_solved
from pyra.geometry import MOVES
from pyra.view import read_stickers, face_share, HOLDS, frame_permutation
from pyra.scan import ScanSession
from pyra.tracker import TrackSession, letter_features
from pyra.solver import solve
LEVEL = sys.argv[1] if len(sys.argv) > 1 else 'normal'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
rng=np.random.default_rng(31)
def frame(st, near):
    for _ in range(200):
        n,pose=P.corner_on_pose(rng,near=near, tilt_max=25)
        if not P.valid_view(pose,n): continue
        k,names=P.keypoints(pose,n)
        if k.min()<2 or k[:,0].max()>638 or k[:,1].max()>478: continue
        img=P.render(st,pose,rng,LEVEL,style='stickered' if rng.uniform()<0.5 else 'stickerless',hand='none')
        return {'keypoints':k.tolist(),'confident':True,'stickers':read_stickers(img,k),'face_share':face_share(k)}, names
ok_scan=ok_solve=0; wrong_calls=0; missed=0
for trial in range(N):
    phys=random_state(rng); s=ScanSession(); t=0.0; first=None
    for near in ['U','L','R','B']:
        fr,names=frame(phys,near); first=first or names
        for _ in range(8):
            t+=0.1; s.feed(fr,now=t)
        t+=4
        if s.result: break
    if not s.result: print(trial,'scan incomplete'); continue
    # the scan names corners by the first view's hold: physical corner first[i] is scan corner HOLDS[0][i]
    to_phys = {HOLDS[0][i]: first[i] for i in range(4)}
    plan = solve(np.array(list(s.result['state'])))
    def phys_move(mv): return to_phys[mv[0].upper()].lower() + mv[1:] if mv[0].islower() else to_phys[mv[0]] + mv[1:]
    test = phys.copy()
    for mv in plan: test = test[MOVES[phys_move(mv)]]
    good = is_solved(test); ok_scan += good
    if not good: print(trial, 'scan wrong'); continue
    state=s.result['state']
    tr=TrackSession(state, plan, letter_features(s.rgbs, state))
    events=[]
    def show():
        fr,_=frame(phys, 'ULRB'[int(rng.integers(4))])
        ev=None
        for _ in range(6):
            out=tr.feed(fr)
            if out['event'] and out['event']!='unsure': ev=out['event']
        out['event']=ev
        return out
    wrong=[mv for mv in ['U','L','R','B'] if mv!=plan[0][0]][0]
    phys=phys[MOVES[phys_move(wrong)]]
    for look in range(3):
        ev=show()['event']
        if ev not in (None, 'unsure'): break
    events.append(ev)
    if ev != 'wrong':
        print(trial, 'deliberate wrong move NOT caught'); continue
    for _ in range(30):
        if tr.done: break
        exp=tr.expected; phys=phys[MOVES[phys_move(exp)]]
        for look in range(3):   # hold it still, from another corner if needed, until the move registers
            out=show()
            if out['event'] not in (None, 'unsure'): break
        events.append(out['event']); missed+=out['event'] in (None,'unsure')
        if out['event'] in (None, 'unsure'): break   # never do a move twice; count it as stuck
    wrong_calls += events[1:].count('wrong')
    ok_solve+=tr.done
    print(trial, 'wrong move caught:', events[0]=='wrong', '| solved' if tr.done else '| NOT solved', '| plan', len(plan), '| false wrong calls', events[1:].count('wrong'))
print(f'{LEVEL}: scans right {ok_scan}/{N}, solves to the end {ok_solve}/{N}, false wrong calls {wrong_calls}, moves needing a second look {missed}')
