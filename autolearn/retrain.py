"""One round of the self-improving loop for one puzzle:

  1. label the new demo frames (label.py);
  2. build a training set: the labelled real frames (the ones the live model had missed count 3 times),
     the other puzzle's real frames as "nothing here" (a cube is not a pyramid, and back), and a sample of
     the earlier training pictures so nothing learnt before is forgotten;
  3. train, starting from the model in use;
  4. test the new model and the one in use on what neither trained on: real frames set aside (one stretch
     in five), the other puzzle's frames set aside, and the fixed drawn test pictures. On the real frames,
     how well a model's corners sit is measured by the colours (the share of stickers read there that match
     the puzzle's known position), not by distance to the labels: the labels were made from the model in
     use, so that distance would always favour it. The drawn pictures, with their true corners, measure
     corner error;
  5. if it passes, a whole guided solve with each model (e2e.py: replayed Pyraminx test videos, the cube
     tracking test): the new one must not do worse;
  6. switch the apps to the new model (models/current.json) only if all that holds; either way, write a
     report (data/autolearn/reports/).

    PYTHONPATH=. python -m autolearn.retrain pyra|cube [--force] [--epochs N]
"""
import argparse
import glob
import hashlib
import json
import os
import random
import shutil
import time
from datetime import datetime

import cv2
import numpy as np

from . import canon, config, e2e, label

REPLAY_N = 4000         # earlier training pictures mixed in
SYNTH_N = 300           # drawn test pictures per test folder
HARD_REPEAT = 3         # frames the live model missed, counted this many times
MIN_NEW = 30            # fewer new labelled frames than this since the last round: nothing to learn yet
MIN_TEST = 25           # fewer real test frames than this: too few to judge a new model on, no switch
EPOCHS = 5
SHAPE = {'pyra': dict(kpt=4, flip=[0, 1, 3, 2], names={0: 'corner_on', 1: 'edge_on'}),
         'cube': dict(kpt=7, flip=[0, 3, 2, 1, 6, 5, 4], names={0: 'cube'})}
# the gate: what "no worse" allows (percentage points, or as stated)
GATE = dict(real_found=0.0, real_colours=0.01, synth_found=1.0, synth_error=0.3, false=1.0)


def _label_line(k, kind, w, h):
    k = np.asarray(k, float)
    x0, y0 = np.maximum(k.min(0) - 6, 0)
    x1, y1 = np.minimum(k.max(0) + 6, [w, h])
    cls = 1 if kind == 'edge' else 0
    out = [str(cls)] + [f'{v:.6f}' for v in ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h)]
    for x, y in k:
        out += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    return ' '.join(out) + '\n'


def _put(src, dst_dir, line):
    """Copies a frame into the round's folder with its label (an empty label: nothing to find)."""
    stem = hashlib.md5(src.encode()).hexdigest()[:16]
    img = os.path.join(dst_dir, 'images', stem + '.jpg')
    if not os.path.exists(img):
        shutil.copyfile(src, img)
        with open(os.path.join(dst_dir, 'labels', stem + '.txt'), 'w') as fh:
            fh.write(line)
    return img


def build(puzzle, records, other, run_dir, rng):
    """Writes the round's data set; returns {'yaml', 'train', 'real_test', 'neg_test', counts...}."""
    for part in ('real', 'neg'):
        os.makedirs(os.path.join(run_dir, part, 'images'), exist_ok=True)
        os.makedirs(os.path.join(run_dir, part, 'labels'), exist_ok=True)
    ok = [r for r in records if r['ok']]
    train, real_test, neg_test = [], [], []
    for r in ok:
        img = _put(r['path'], os.path.join(run_dir, 'real'), _label_line(r['corners'], r['kind'], r['width'], r['height']))
        if r['test']:
            real_test.append(img)
        else:
            train += [img] * (HARD_REPEAT if not r['live_found'] else 1)
    others = [r for r in other if r['ok']]
    rng.shuffle(others)
    for r in others[:600]:   # the other puzzle, seen for real: nothing to find here
        img = _put(r['path'], os.path.join(run_dir, 'neg'), '')
        (neg_test if r['test'] else train).append(img)
    replay = []
    for d in config.replay(puzzle):
        replay += glob.glob(os.path.join(d, 'images', 'train', '*.jpg'))
    rng.shuffle(replay)
    train += replay[:REPLAY_N]
    rng.shuffle(train)
    synth = []
    for d in config.SYNTH_TEST[puzzle]:
        files = sorted(glob.glob(os.path.join(d, '*.jpg')))
        random.Random(0).shuffle(files)
        synth += files[:100]           # a little drawn data in the training's own check, so it keeps both in mind
    with open(os.path.join(run_dir, 'train.txt'), 'w') as fh:
        fh.write('\n'.join(train) + '\n')
    with open(os.path.join(run_dir, 'val.txt'), 'w') as fh:
        fh.write('\n'.join(real_test + synth) + '\n')
    sh = SHAPE[puzzle]
    yaml = os.path.join(run_dir, 'data.yaml')
    with open(yaml, 'w') as fh:
        fh.write(f"path: {run_dir}\ntrain: train.txt\nval: val.txt\nkpt_shape: [{sh['kpt']}, 3]\nflip_idx: {sh['flip']}\nnames:\n"
                 + ''.join(f'  {i}: {n}\n' for i, n in sh['names'].items()))
    return {'yaml': yaml, 'real_test': real_test, 'neg_test': neg_test,
            'real_test_records': [r for r in ok if r['test']], 'neg_test_paths': [r['path'] for r in others[:600] if r['test']], 'train_real': sum(1 for r in ok if not r['test']),
            'train_hard': sum(1 for r in ok if not r['test'] and not r['live_found']), 'replay': min(len(replay), REPLAY_N),
            'negatives': len(others[:600])}


def evaluate(model_path, puzzle, real_records, neg_paths, device='mps'):
    """On the real frames set aside (their records: path, label, and the puzzle's known position): found
    share (%), median distance to the label (% of size, for reference: it favours the model in use) and
    colour match at the model's corners (the share of stickers matching the known position); false finds
    (%) on the other puzzle's frames; found, corner error and false finds on the drawn test pictures."""
    from ultralytics import YOLO
    from . import sources, verify
    model = YOLO(model_path)
    multi = len(model.names) > 1

    def look(img):
        r = model.predict(img, imgsz=640, device=device, verbose=False)[0]
        if len(r.boxes) == 0:
            return None
        i = int(r.boxes.conf.argmax())
        if float(r.boxes.conf[i]) < 0.5:
            return None
        k = r.keypoints.xy[i].cpu().numpy().astype(float)
        kind = ('edge' if multi and int(r.boxes.cls[i]) == 1 else 'corner') if puzzle == 'pyra' else 'cube'
        k = canon.cube(k) if kind == 'cube' else canon.pyra(k, kind)
        return None if k is None else (k, kind)

    def error(k, t):
        return float(np.max(np.linalg.norm(k - t, axis=1)) / np.ptp(t, 0).max() * 100)

    items = {it['path']: it for it in (sources.pyra_frames(config.apps()) if puzzle == 'pyra' else sources.cube_frames(config.apps()))}
    found, errs, colours = 0, [], []
    for r in real_records:
        img = cv2.imread(r['path'])
        got = look(img)
        if got is None or got[1] != r['kind']:
            continue
        found += 1
        errs.append(error(got[0], np.array(r['corners'])))
        it = items.get(r['path'])
        if it:
            fit = (verify.pyra_cost(img, got[0], got[1], it['states'], it['feats'], it['moves']) if puzzle == 'pyra'
                   else verify.cube_cost(img, got[0], it['states'], it['feats'], it['moves']))
            colours.append(fit[0] if fit else 0.0)
    n = len(real_records)
    real = {'n': n, 'found': round(100 * found / n, 1) if n else None, 'error': round(float(np.median(errs)), 2) if errs else None,
            'colours': round(float(np.mean(colours)), 3) if colours else None, 'empty': 0, 'false': None}
    false = sum(look(cv2.imread(p)) is not None for p in neg_paths)
    other = {'n': 0, 'found': None, 'error': None, 'empty': len(neg_paths),
             'false': round(100 * false / len(neg_paths), 1) if neg_paths else None}
    synth = []
    for d in config.SYNTH_TEST[puzzle]:
        files = sorted(glob.glob(os.path.join(d, '*.jpg')))
        random.Random(1).shuffle(files)       # not the pictures put in the training's own check (seed 0)
        synth += files[:SYNTH_N]
    sf = sn = sfalse = sempty = 0
    serrs = []
    for img in synth:
        lab = open(img.replace('/images/', '/labels/')[:-4] + '.txt').read().split()
        got = look(img)
        if not lab:
            sempty += 1
            sfalse += got is not None
            continue
        sn += 1
        h, w = cv2.imread(img).shape[:2]
        t = np.array(list(map(float, lab[5:]))).reshape(-1, 3)[:, :2] * [w, h]
        kind = ('edge' if lab[0] == '1' else 'corner') if puzzle == 'pyra' else 'cube'
        if got is not None and got[1] == kind:
            sf += 1
            serrs.append(error(got[0], t))
    drawn = {'n': sn, 'found': round(100 * sf / sn, 1) if sn else None, 'error': round(float(np.median(serrs)), 2) if serrs else None,
             'empty': sempty, 'false': round(100 * sfalse / sempty, 1) if sempty else None}
    return {'real': real, 'other_puzzle': other, 'drawn': drawn}


def gate(cur, new):
    """(switch?, reasons). No worse anywhere (within GATE), and better on the real frames."""
    reasons, ok = [], True

    def no_worse(name, a, b, tol, higher_better=True):
        nonlocal ok
        if a is None or b is None:
            return
        worse = (b < a - tol) if higher_better else (b > a + tol)
        if worse:
            ok = False
            reasons.append(f'{name} worse: {a} -> {b}')
    no_worse('real frames found', cur['real']['found'], new['real']['found'], GATE['real_found'])
    no_worse('real frames colour match at the corners', cur['real'].get('colours'), new['real'].get('colours'), GATE['real_colours'])
    no_worse('drawn pictures found', cur['drawn']['found'], new['drawn']['found'], GATE['synth_found'])
    no_worse('drawn pictures corner error', cur['drawn']['error'], new['drawn']['error'], GATE['synth_error'], False)
    no_worse('false finds (drawn, empty)', cur['drawn']['false'], new['drawn']['false'], GATE['false'], False)
    no_worse('false finds (other puzzle)', cur['other_puzzle']['false'], new['other_puzzle']['false'], GATE['false'], False)
    if cur['real']['n'] < MIN_TEST:
        ok = False
        reasons.append(f"only {cur['real']['n']} real test frames (at least {MIN_TEST} needed to judge)")
    better = (new['real']['found'] or 0) > (cur['real']['found'] or 0) or (
        new['real']['found'] == cur['real']['found'] and (new['real'].get('colours') or 0) > (cur['real'].get('colours') or 0) + 0.005)
    if ok and not better:
        ok = False
        reasons.append('not better on the real frames')
    return ok, reasons


def run(puzzle, force=False, epochs=EPOCHS, log=print, device='mps'):
    from vision.current_model import current_model, set_current_model
    from ultralytics import YOLO
    stamp = datetime.now().strftime('%Y%m%d-%H%M')
    cur_path = current_model(puzzle, config.BASE_MODEL[puzzle])
    cur_name = os.path.basename(cur_path)
    records = label.run(puzzle, cur_name, log=log)
    other = label.run('cube' if puzzle == 'pyra' else 'pyra', os.path.basename(
        current_model('cube' if puzzle == 'pyra' else 'pyra', config.BASE_MODEL['cube' if puzzle == 'pyra' else 'pyra'])), log=log)
    state_path = os.path.join(config.WORK, f'{puzzle}_state.json')
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    ok_train = [r['path'] for r in records if r['ok'] and not r['test']]
    new = len(set(ok_train) - set(state.get('trained_on', [])))
    report = {'puzzle': puzzle, 'when': stamp, 'model_in_use': cur_name, 'labelled': sum(r['ok'] for r in records),
              'frames': len(records), 'new_labelled': new}
    if new < MIN_NEW and not force:
        report['outcome'] = f'skipped: {new} new labelled frames (at least {MIN_NEW} needed)'
        _report(report, log)
        return report
    run_dir = os.path.join(config.WORK, 'rounds', f'{puzzle}-{stamp}')
    data = build(puzzle, records, other, run_dir, random.Random(stamp))
    report['data'] = {k: (len(v) if isinstance(v, list) else v) for k, v in data.items()
                      if k not in ('yaml', 'real_test_records', 'neg_test_paths')}
    log(f"{puzzle}: training {epochs} passes on {data['train_real']} real frames ({data['train_hard']} the live model missed), "
        f"{data['negatives']} other-puzzle frames, {data['replay']} earlier pictures")
    t0 = time.time()
    YOLO(cur_path).train(data=data['yaml'], epochs=epochs, imgsz=640, batch=16, device=device, workers=4,
                         project=run_dir, name='train', exist_ok=True, plots=False, verbose=False)
    best = os.path.join(run_dir, 'train', 'weights', 'best.pt')
    report['train_minutes'] = round((time.time() - t0) / 60, 1)
    log(f'{puzzle}: testing the model in use and the new one')
    report['in_use'] = evaluate(cur_path, puzzle, data['real_test_records'], data['neg_test_paths'], device)
    report['new'] = evaluate(best, puzzle, data['real_test_records'], data['neg_test_paths'], device)
    switch, reasons = gate(report['in_use'], report['new'])
    if switch:
        switch, reasons = _whole_solves(puzzle, cur_path, best, report, log)
    report['reasons'] = reasons
    state['trained_on'] = sorted(set(state.get('trained_on', [])) | set(ok_train))
    if switch:
        name = f'{puzzle}_pose_auto_{stamp[:8]}.pt'
        shutil.copyfile(best, os.path.join(config.MODELS, name))
        set_current_model(puzzle, name)
        report['outcome'] = f'switched to {name} (restart the app to use it)'
    else:
        report['outcome'] = f'kept {cur_name}: ' + '; '.join(reasons)
    with open(state_path, 'w') as fh:
        json.dump(state, fh)
    shutil.rmtree(os.path.join(run_dir, 'real'), ignore_errors=True)   # copies of frames: the originals stay
    shutil.rmtree(os.path.join(run_dir, 'neg'), ignore_errors=True)
    _report(report, log)
    return report


def _whole_solves(puzzle, cur_path, best, report, log):
    log(f'{puzzle}: whole guided solves with both models')
    report['solves_in_use'] = e2e.check(puzzle, cur_path)
    report['solves_new'] = e2e.check(puzzle, best)
    worse = e2e.no_worse(puzzle, report['solves_in_use'], report['solves_new'])
    return not worse, worse


def retest(puzzle, run_dir, log=print, device='mps'):
    """Tests a finished round's model again (as `run` does after training) and switches to it if it passes."""
    from vision.current_model import current_model, set_current_model
    cur_path = current_model(puzzle, config.BASE_MODEL[puzzle])
    records = label.run(puzzle, os.path.basename(cur_path), log=log)
    other_p = 'cube' if puzzle == 'pyra' else 'pyra'
    other = label.run(other_p, os.path.basename(current_model(other_p, config.BASE_MODEL[other_p])), log=log)
    best = os.path.join(run_dir, 'train', 'weights', 'best.pt')
    real = [r for r in records if r['ok'] and r['test']]
    neg = [r['path'] for r in other if r['ok'] and r['test']][:600]
    stamp = os.path.basename(run_dir).split('-', 1)[1]
    report = {'puzzle': puzzle, 'when': stamp + '-retest', 'model_in_use': os.path.basename(cur_path),
              'labelled': sum(r['ok'] for r in records), 'frames': len(records), 'new_labelled': 0,
              'train_minutes': 0, 'data': {'real_test': len(real), 'neg_test': len(neg), 'retest_of': run_dir}}
    report['in_use'] = evaluate(cur_path, puzzle, real, neg, device)
    report['new'] = evaluate(best, puzzle, real, neg, device)
    switch, report['reasons'] = gate(report['in_use'], report['new'])
    if switch:
        switch, report['reasons'] = _whole_solves(puzzle, cur_path, best, report, log)
    if switch:
        name = f'{puzzle}_pose_auto_{stamp[:8]}.pt'
        shutil.copyfile(best, os.path.join(config.MODELS, name))
        set_current_model(puzzle, name)
        report['outcome'] = f'switched to {name} (restart the app to use it)'
    else:
        report['outcome'] = f"kept {report['model_in_use']}: " + '; '.join(report['reasons'])
    _report(report, log)
    return report


def puzzle_of(report):
    return report['puzzle']


def _report(report, log):
    d = os.path.join(config.WORK, 'reports')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'history.jsonl'), 'a') as fh:
        fh.write(json.dumps(report) + '\n')
    lines = [f"# {report['puzzle']} — {report['when']}", '', f"**{report['outcome']}**", '',
             f"Model in use: {report['model_in_use']}. Frames with a known position: {report['frames']}, "
             f"labelled automatically: {report['labelled']} ({report['new_labelled']} new)."]
    if 'new' in report:
        lines += ['', '| Test | In use | New |', '| --- | --- | --- |']
        for part, title in (('real', 'Real frames set aside'), ('other_puzzle', 'Other puzzle (should find nothing)'),
                            ('drawn', 'Drawn test pictures')):
            a, b = report['in_use'][part], report['new'][part]
            if a['n'] and part == 'real':
                lines.append(f"| {title}: found | {a['found']}% | {b['found']}% |")
                lines.append(f"| {title}: stickers matching at the corners | {a.get('colours')} | {b.get('colours')} |")
                lines.append(f"| {title}: distance to the labels (made with the model in use) | {a['error']}% | {b['error']}% |")
            elif a['n']:
                lines.append(f"| {title}: found / corner error | {a['found']}% / {a['error']}% | {b['found']}% / {b['error']}% |")
            if a['empty']:
                lines.append(f"| {title}: false finds | {a['false']}% | {b['false']}% |")
        if 'solves_new' in report:
            a, b = report['solves_in_use'], report['solves_new']
            if puzzle_of(report) == 'pyra':
                lines.append(f"| Whole guided solves (3 test videos): problems | {a['problems']} | {b['problems']} |")
            else:
                for level in a:
                    lines.append(f"| Move tracking ({level}): judged right / judged WRONG | {a[level]['correct']}% / {a[level]['wrong']}% "
                                 f"| {b.get(level, {}).get('correct')}% / {b.get(level, {}).get('wrong')}% |")
        lines += ['', f"Training: {report['train_minutes']} min; data: {report['data']}"]
    with open(os.path.join(d, f"{report['when']}-{report['puzzle']}.md"), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    log(f"{report['puzzle']}: {report['outcome']}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('puzzle', choices=('pyra', 'cube'))
    ap.add_argument('--force', action='store_true', help='train even with few new frames')
    ap.add_argument('--epochs', type=int, default=EPOCHS)
    ap.add_argument('--retest', metavar='ROUND_DIR', help="test a finished round's model again (no training)")
    a = ap.parse_args()
    if a.retest:
        retest(a.puzzle, os.path.abspath(a.retest))
    else:
        run(a.puzzle, a.force, a.epochs)
