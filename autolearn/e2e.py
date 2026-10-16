"""The last test before a switch: a whole guided solve with the candidate model, not just its corners.

Pyraminx: three rendered test videos held edge-on (bench/make_pyra_video.py, EDGE=1: a scan, one
deliberate wrong move, its undo, then the plan), replayed frame by frame through the app's own scan and
move tracking. Every move must be called in the time it is on screen: the wrong move "wrong", the undo
and each planned move "correct" (the last "solved"); a call before the move is shown (too early), a
missing call, or any other call is a problem.
Cube: bench/bench_tracking.py with the model (rendered before/after views, normal and hard): moves
judged right, and moves judged WRONG (the costly mistake).

    PYTHONPATH=. python -m autolearn.e2e pyra|cube <model file>    -> prints a JSON result
"""
import json
import os
import subprocess
import sys

import numpy as np

from . import config

VIDEO_SEEDS = (4, 7, 11)
FPS = 15
# make_pyra_video.py, in whole frames (int(seconds * FPS)): blank 9 s, view 1 3 s, blank 0.8 s, view 2 3 s,
# blank 4 s; then per move: hands turning 0.5 s (7 frames, no clean view), then held still 2.2 s (33)
MOVES_START = 135 + 45 + 12 + 45 + 60
TURNING, HELD = 7, 33
MOVE_SLOT = TURNING + HELD
CUBE_CASES = 150
E2E = os.path.join(config.WORK, 'e2e')


def _backgrounds():
    """The renderers draw on the COCO128 background photos (bench/data/backgrounds, not in git): link the
    set another folder on this laptop already has."""
    link = os.path.join(config.ROOT, 'bench', 'data', 'backgrounds')
    if not os.path.exists(link):
        os.makedirs(os.path.dirname(link), exist_ok=True)
        for src in (os.path.join(config.HOME, 'rubik_solver_AR', 'bench', 'data', 'backgrounds'),
                    os.path.join(config.HOME, 'rubik_solver_AR_pyraminx', 'bench', 'data', 'backgrounds')):
            if os.path.isdir(src):
                os.symlink(os.path.realpath(src), link)
                break


def _videos():
    """The test videos (made once): [(path, sequence of moves shown)]."""
    os.makedirs(E2E, exist_ok=True)
    _backgrounds()
    out = []
    for seed in VIDEO_SEEDS:
        path, meta = os.path.join(E2E, f'pyra_edge_{seed}.y4m'), os.path.join(E2E, f'pyra_edge_{seed}.json')
        if not (os.path.exists(path) and os.path.exists(meta)):
            res = subprocess.run([sys.executable, 'make_pyra_video.py', path, str(seed)], cwd=os.path.join(config.ROOT, 'bench'),
                                 env={**os.environ, 'EDGE': '1', 'PYTHONPATH': config.ROOT}, capture_output=True, text=True, check=True)
            seq = res.stdout.strip().splitlines()[-1].split('sequence ')[1].split()
            json.dump({'sequence': seq}, open(meta, 'w'))
        out.append((path, json.load(open(meta))['sequence']))
    return out


def _frames(path):
    import cv2
    data = open(path, 'rb').read()
    _, rest = data.split(b'\n', 1)
    w, h = 640, 480
    size = w * h * 3 // 2
    i = 0
    while i < len(rest):
        i += 6                                  # b'FRAME\n'
        yuv = np.frombuffer(rest[i:i + size], np.uint8).reshape(h * 3 // 2, w)
        i += size
        yield cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)


def pyra_replay(video, sequence):
    """Problems (list of strings) and the calls made, for one video with the model in PYRA_MODEL."""
    import cv2
    from pyra.live import process_frame
    from pyra.scan import ScanSession
    from pyra.solver import solve
    from pyra.tracker import TrackSession, letter_features
    scan, track, calls = ScanSession(), None, []
    for n, frame in enumerate(_frames(video)):
        t = n / FPS
        fr = process_frame(cv2.imencode('.jpg', frame)[1].tobytes())
        if track is None:
            scan.feed(fr, t)
            if scan.result:
                st = np.array(list(scan.result['state']))
                track = TrackSession(st, solve(st), letter_features(scan.rgbs, st))
            continue
        out = track.feed(fr)
        if out['event'] and out['event'] != 'unsure':
            calls.append((n, out['event']))
        if track.done:
            break
    if track is None:
        return ['scan not finished'], calls
    want = ['wrong'] + ['correct'] * (len(sequence) - 2) + ['solved']
    problems, used = [], set()
    for i, kind in enumerate(want):
        start = MOVES_START + i * MOVE_SLOT + TURNING        # the move is on screen from this frame...
        end = start + MOVE_SLOT                              # ...until the next one is
        hit = [j for j, (t, e) in enumerate(calls) if e == kind and start <= t < end and j not in used]
        early = [j for j, (t, e) in enumerate(calls) if start - MOVE_SLOT <= t < start and j not in used and e == kind]
        if hit:
            used.add(hit[0])
        elif early:
            used.add(early[0])
            problems.append(f'move {i + 1} ({sequence[i]}): "{kind}" called before it was shown')
        else:
            problems.append(f'move {i + 1} ({sequence[i]}): no "{kind}" call')
    problems += [f'unexpected "{e}" at {t / FPS:.1f} s' for j, (t, e) in enumerate(calls) if j not in used]
    return problems, [(round(t / FPS, 2), e) for t, e in calls]


def run_pyra():
    out = {'videos': []}
    for video, seq in _videos():
        problems, calls = pyra_replay(video, seq)
        out['videos'].append({'video': os.path.basename(video), 'problems': problems, 'calls': calls})
    out['problems'] = sum(len(v['problems']) for v in out['videos'])
    return out


def run_cube(model):
    _backgrounds()
    bench = os.path.join(config.ROOT, 'bench')
    os.makedirs(os.path.join(bench, 'results'), exist_ok=True)
    out = os.path.join(bench, 'results', 'results_tracking_yolo.json')
    kept = open(out).read() if os.path.exists(out) else None   # the benchmark's recorded result: put back after
    try:
        subprocess.run([sys.executable, 'bench_tracking.py', str(CUBE_CASES), 'yolo', model], cwd=bench, check=True,
                       env={**os.environ, 'PYTHONPATH': config.ROOT}, capture_output=True)
        res = json.load(open(out))['results']
    finally:
        if kept is not None:
            with open(out, 'w') as fh:
                fh.write(kept)
    return {level.split('|')[0]: {'correct': round(r['correct'], 1), 'wrong': round(r['wrong'], 1)} for level, r in res.items()}


def check(puzzle, model):
    """Runs the check for a model in a fresh process (the apps' code loads one model per process)."""
    env = {**os.environ, 'PYTHONPATH': config.ROOT, 'PYRA_RECORD': '0', 'RUBIK_RECORD': '0'}
    if puzzle == 'pyra':
        env['PYRA_MODEL'] = model
    res = subprocess.run([sys.executable, '-m', 'autolearn.e2e', puzzle, model], cwd=config.ROOT, env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout.strip().splitlines()[-1])


def no_worse(puzzle, cur, new):
    """Reasons the candidate does worse in the whole-solve test (empty: no worse)."""
    if puzzle == 'pyra':
        if new['problems'] > cur['problems']:
            got = [p for v in new['videos'] for p in v['problems']]
            return [f"whole solves: {new['problems']} problems (model in use: {cur['problems']}): " + '; '.join(got[:3])]
        return []
    out = []
    for level in cur:
        c, n = cur[level], new.get(level, {'correct': 0, 'wrong': 100})
        if n['wrong'] > c['wrong'] + 0.5:
            out.append(f"move tracking ({level}): moves judged WRONG {c['wrong']}% -> {n['wrong']}%")
        if n['correct'] < c['correct'] - 2.0:
            out.append(f"move tracking ({level}): moves judged right {c['correct']}% -> {n['correct']}%")
    return out


if __name__ == '__main__':
    puzzle, model = sys.argv[1], sys.argv[2]
    print(json.dumps(run_pyra() if puzzle == 'pyra' else run_cube(model)))
