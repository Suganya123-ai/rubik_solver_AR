"""Labels the saved demo frames automatically (no person): for each frame, the teacher's looks
(teacher.py) are put in the model's corner order (canon.py), grouped where they agree, and a group
becomes the label only if

  1. at least LOOKS_AGREE looks put every corner within AGREE of each other (a single wrong look is
     outvoted; the label is their average, more precise than any one look),
  2. the stickers read there match the position the puzzle is known to be in (verify.py): at least
     MIN_AGREEMENT of them, at least MIN_WORST around every corner (pyramid), and one way of holding it
     clearly fitting best (MIN_HOLD_MARGIN).

Results are cached per frame (data/autolearn/labels/<puzzle>.jsonl), so each week only new frames, and
frames an older model could not label, are looked at again.
    PYTHONPATH=. python -m autolearn.label pyra|cube
"""
import json
import os
import sys
import time

import cv2
import numpy as np

from . import canon, config, sources, verify

LOOKS_AGREE = 2
AGREE = 0.07            # of the puzzle's size, for every corner
MIN_AGREEMENT = 0.8
MIN_WORST = 0.5
MIN_HOLD_MARGIN = 3.0


def _groups(props):
    """Proposals [(corners, conf, kind)] grouped by agreement; best (largest, then most confident) first."""
    groups = []
    for k, c, kind in props:
        size = float(np.ptp(k, 0).max()) or 1.0
        for g in groups:
            if g['kind'] == kind and np.max(np.linalg.norm(g['k'] - k, axis=1)) < AGREE * size:
                g['members'].append(k)
                g['conf'] = max(g['conf'], c)
                g['k'] = np.mean(g['members'], axis=0)
                break
        else:
            groups.append({'k': k, 'members': [k], 'conf': c, 'kind': kind})
    return sorted(groups, key=lambda g: (-len(g['members']), -g['conf']))


def label_frame(teacher, item):
    """{'ok': bool, why, corners, kind, ...} for one frame."""
    img = cv2.imread(item['path'])
    if img is None:
        return {'ok': False, 'why': 'unreadable'}
    props = []
    for k, c, cls in teacher.proposals(img, hints=[item.get('live_any')]):
        kind = ('edge' if cls == 1 else 'corner') if item['puzzle'] == 'pyra' else 'cube'
        kk = canon.cube(k) if kind == 'cube' else canon.pyra(k, kind)
        if kk is not None:
            props.append((kk, c, kind))
    if not props:
        return {'ok': False, 'why': 'nothing found'}
    why = 'looks disagree'
    for g in _groups(props):
        if len(g['members']) < LOOKS_AGREE:
            break
        k = g['k']
        if item['puzzle'] == 'pyra':
            fit = verify.pyra_cost(img, k, g['kind'], item['states'], item['feats'], item['moves'])
        else:
            fit = verify.cube_cost(img, k, item['states'], item['feats'], item['moves'])
        if fit is None:
            why = 'stickers off the picture'
            continue
        agreement, cost, _, _, margin, worst = fit
        if agreement < MIN_AGREEMENT or worst < MIN_WORST or margin < MIN_HOLD_MARGIN:
            why = f'colours do not match ({agreement:.2f}, worst corner {worst:.2f}, margin {margin:.1f})'
            continue
        h, w = img.shape[:2]
        return {'ok': True, 'corners': np.round(k, 1).tolist(), 'kind': g['kind'], 'looks': len(g['members']),
                'agreement': round(agreement, 3), 'cost': round(cost, 1), 'width': w, 'height': h}
    return {'ok': False, 'why': why}


def run(puzzle, model_name, limit=None, log=print):
    """Labels every frame not labelled yet (or rejected by another model). Returns the cache's records."""
    from .teacher import Teacher
    items = sources.pyra_frames(config.apps()) if puzzle == 'pyra' else sources.cube_frames(config.apps())
    cache_path = os.path.join(config.WORK, 'labels', f'{puzzle}.jsonl')
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                r = json.loads(line)
                cache[r['path']] = r
            except ValueError:
                pass
    todo = [it for it in items if it['path'] not in cache
            or (not cache[it['path']]['ok'] and cache[it['path']].get('model') != model_name)]
    if limit:
        todo = todo[:limit]
    log(f'{puzzle}: {len(items)} frames with a known position, {len(todo)} to label with {model_name}')
    if todo:
        teacher = Teacher(os.path.join(config.MODELS, model_name))
        t0 = time.time()
        with open(cache_path, 'a') as fh:
            for n, it in enumerate(todo):
                r = label_frame(teacher, it)
                r.update(path=it['path'], session=it['session'], index=it['index'], stage=it['stage'],
                         live_found=(it['live_conf'] or 0) >= 0.5 and it['stage'] != 'missed', model=model_name,
                         test=sources.is_test(it['session'], it['index']))
                cache[it['path']] = r
                fh.write(json.dumps(r) + '\n')
                if (n + 1) % 200 == 0:
                    log(f'  {n + 1}/{len(todo)} looked at ({time.time() - t0:.0f} s)')
    records = [cache[it['path']] for it in items if it['path'] in cache]
    ok = [r for r in records if r['ok']]
    log(f'{puzzle}: labelled {len(ok)} of {len(records)} ({sum(not r["live_found"] for r in ok)} the live model had missed)')
    return records


if __name__ == '__main__':
    from vision.current_model import current_model
    p = sys.argv[1]
    model = os.path.basename(current_model(p, 'pyra_pose_v3.pt' if p == 'pyra' else 'cube_pose_v3.pt'))
    run(p, model, limit=int(sys.argv[2]) if len(sys.argv) > 2 else None)
