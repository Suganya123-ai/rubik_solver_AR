"""The frames saved during demos, with what is known about the puzzle in each.

Pyraminx: <app>/data/pyra_sessions/<day>/<time>/ (pyra/record.py): frames.jsonl lines per frame
(stage, the live model's corners and confidence, the tracker's position) and notes (scan result with
its colours, the position solved from). Scan frames get the position the scan then found (as the user
accepted it); move frames the tracker's position at the time; idle frames are not used (unknown).
Cube: <app>/data/sessions/<day>/<time>/ (vision/live_session.py): session.jsonl starts with the
position and the scan's colours; each saved frame has the tracker's position, or (a "missed" frame)
follows the last one that did.

Each item: {'puzzle', 'path', 'session', 'index' (its line in the session), 'stage', 'live': corners or None, 'live_conf', 'live_view',
'states': [positions], 'moves': [the move the user was asked for, if any], 'feats': {letter: colour feature}}.
"""
import glob
import hashlib
import json
import os

import numpy as np

from cube.color_detect import color_feature

TEST_SHARE = 5     # one stretch in 5 (by a hash of its name) is never trained on: the real test
CHUNK = 40         # frames per stretch (~20 s): neighbouring frames look alike, so a stretch goes one way


def is_test(session, index):
    """Is frame `index` of `session` in the real test? Decided per stretch of CHUNK frames."""
    key = f'{session}#{index // CHUNK}'
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % TEST_SHARE == 0


def _lines(path):
    out = []
    with open(path) as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass   # a line cut short when the app stopped
    return out


def _keep(items):
    from . import config
    skip = config.excluded()
    return [it for it in items if it['session'] not in skip]


def pyra_frames(apps):
    from pyra.tracker import letter_features
    items = []
    for app in apps:
        for d in sorted(glob.glob(os.path.join(app, 'data', 'pyra_sessions', '*', '*'))):
            lines = _lines(os.path.join(d, 'frames.jsonl')) if os.path.exists(os.path.join(d, 'frames.jsonl')) else []
            session = os.path.relpath(d, os.path.join(app, 'data'))
            # the scans in this session, in order: (index of the line it finished on, state, colour features)
            scans, feats_now = [], None
            for i, r in enumerate(lines):
                if 'scan_result' in r and r.get('rgbs'):
                    res = r['scan_result']
                    scans.append([i, res['state'] if res.get('valid') else None, r['rgbs']])
                if 'solving' in r and scans:
                    scans[-1][1] = r['solving']            # as accepted, with the user's corrections
            def feats_of(state, rgbs):
                return letter_features([tuple(c) for c in rgbs], np.array(list(state)))
            si = 0
            for i, r in enumerate(lines):
                if 'file' not in r:
                    if 'solving' in r and scans:
                        done = [s for s in scans if s[0] <= i and s[1]]
                        if done:
                            feats_now = feats_of(done[-1][1], done[-1][2])
                    continue
                state, feats, moves = None, None, []
                if r.get('stage') == 'scan':
                    while si < len(scans) and scans[si][0] < i:
                        si += 1
                    if si < len(scans) and scans[si][1]:
                        state, feats = scans[si][1], feats_of(scans[si][1], scans[si][2])
                elif r.get('stage') == 'track' and (r.get('track') or {}).get('state') and feats_now:
                    state, feats = r['track']['state'], feats_now
                    moves = [r['track']['move']] if r['track'].get('move') else []
                if state is None:
                    continue
                items.append({'puzzle': 'pyra', 'path': os.path.join(d, r['file']), 'session': f'{os.path.basename(app)}/{session}',
                              'index': i,
                              'stage': r['stage'], 'live': r.get('keypoints') if (r.get('confidence') or 0) >= 0.5 else None,
                              'live_any': r.get('keypoints'), 'live_conf': r.get('confidence') or 0.0, 'live_view': r.get('view'),
                              'states': [state], 'moves': moves, 'feats': feats})
    return _keep(items)


def cube_frames(apps):
    from cube.cube_state import FACES
    from vision.tracker import refs_from
    items = []
    for app in apps:
        for d in sorted(glob.glob(os.path.join(app, 'data', 'sessions', '*', '*'))):
            path = os.path.join(d, 'session.jsonl')
            if not os.path.exists(path):
                continue
            lines = _lines(path)
            if not lines or not lines[0].get('start') or not lines[0].get('scan_rgbs'):
                continue
            start = lines[0]
            letters = start['state']
            rgbs = start['scan_rgbs']
            refs = refs_from(letters, [color_feature(rgb) for f in FACES for rgb in rgbs[f]])
            if len(refs) < 6:
                continue
            session = os.path.relpath(d, os.path.join(app, 'data'))
            last, expected = letters, None
            for i, r in enumerate(lines[1:]):
                if r.get('state'):
                    last = r['state']
                if r.get('expected'):
                    expected = r['expected']
                if not r.get('jpeg'):
                    continue
                items.append({'puzzle': 'cube', 'path': os.path.join(d, r['jpeg']), 'session': f'{os.path.basename(app)}/{session}',
                              'index': i,
                              'stage': 'missed' if r.get('missed') else 'track', 'live': None, 'live_any': None,
                              'live_conf': r.get('confidence') or (0.0 if r.get('missed') else 1.0), 'live_view': None,
                              'states': [last], 'moves': [expected] if expected else [], 'feats': refs})
    return _keep(items)
