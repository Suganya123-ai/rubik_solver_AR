"""Re-creates the exact first frames each benchmark used (same seeds, same
order of random draws) and saves them with a gallery page."""
import os
import random
import shutil

import cv2
import numpy as np

import render as R
from cube.cube_state import FACE_OFFSET, FACES, solved_state
from cube.moves import ALL_MOVES, apply_moves

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'test_images')
shutil.rmtree(OUT, ignore_errors=True)
sections = []


def save(sub, name, img):
    os.makedirs(f'{OUT}/{sub}', exist_ok=True)
    cv2.imwrite(f'{OUT}/{sub}/{name}.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return f'{sub}/{name}.jpg'


# 1) Sticker-finding test (bench_scan_detect.py): same seeds and draw order.
N = 8
for cname, aligned, level, sub in [('Aligned to guide grid, normal light', True, 'normal', 'scan_aligned'),
                                   ('Free hand-held, normal light', False, 'normal', 'scan_free_normal'),
                                   ('Free hand-held, hard conditions', False, 'hard', 'scan_free_hard')]:
    rng = np.random.default_rng(100 + aligned * 7 + (level == 'hard'))
    srng = random.Random(5)
    files = []
    for i in range(N):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        pose = R.scan_pose(rng, aligned=aligned)
        files.append((save(sub, f'{i:02d}', R.render(state, pose, rng, level)), f'frame {i + 1}'))
    sections.append((f'Test 2 · Finding the stickers: {cname}', 'From the 200 frames per condition in the sticker-finding test. The front face is the one being scanned.', files))

# 2) Colour test (bench_color.py): first 2 cubes, all 6 scans each.
for level, seed in (('normal', 7), ('hard', 8)):
    rng, srng = np.random.default_rng(seed), random.Random(11)
    files = []
    for c in range(2):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        truth = {f: [R.LETTER_TO_COLOR[x] for x in state[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]] for f in FACES}
        session, pal = R.new_session(rng, level), R.cube_palette(rng)
        for f in FACES:
            pose = R.scan_pose(rng, aligned=True)
            img = R.render(state, pose, rng, level, faces_override={'F': truth[f]}, pal=pal, session=session)
            files.append((save(f'color_{level}', f'cube{c + 1}_{f}', img), f'cube {c + 1}, side {f}'))
    sections.append((f'Test 3 · Colours: {level} light', 'First 2 of the 150 whole cubes: the 6 scans of one cube share the same lighting, as in a real scanning session.', files))

# 3) Tracking test (bench_tracking.py, perfect corner points): before/after pairs.
for level, seed in (('normal', 31), ('hard', 32)):
    rng, srng = np.random.default_rng(seed), random.Random(9)
    files = []
    for i in range(4):
        state = apply_moves(solved_state(), [srng.choice(ALL_MOVES) for _ in range(25)]).arr
        expected = srng.choice(ALL_MOVES)
        u = srng.random()
        if u < 0.35:
            event, moves = f'did the expected move {expected}', [expected]
        elif u < 0.60:
            event, moves = 'no move yet', []
        elif u < 0.90:
            m = srng.choice([m for m in ALL_MOVES if m != expected])
            event, moves = f'wrong move {m} (expected {expected})', [m]
        else:
            m1 = srng.choice(ALL_MOVES)
            m2 = srng.choice([m for m in ALL_MOVES if m[0] != m1[0]])
            event, moves = f'two quick moves {m1} {m2}', [m1, m2]
        after = apply_moves(solved_state().__class__(state.copy()), moves).arr
        session, pal = R.new_session(rng, level), R.cube_palette(rng)
        pa = R.corner_pose(rng)
        pb = R.jitter_pose(pa, rng)
        a = R.render(state, pa, rng, level, pal=pal, session=session)
        b = R.render(after, pb, rng, level, pal=pal, session=session)
        files.append((save(f'tracking_{level}', f'trial{i + 1}_before', a), f'trial {i + 1} before'))
        files.append((save(f'tracking_{level}', f'trial{i + 1}_after', b), f'trial {i + 1} after: {event}'))
    sections.append((f'Test 5 · Move tracking: {level} light', 'Before/after pairs from the 3,600 tracking trials. The tracker had to say what happened between the two frames.', files))

# 4) YOLO training data: a few saved frames with their labelled corner points.
files = []
for i in range(8):
    img = cv2.imread(f'data/yolo/images/train/{i:05d}.jpg')
    vals = open(f'data/yolo/labels/train/{i:05d}.txt').read().split()[5:]
    for k in range(7):
        x, y = float(vals[3 * k]) * R.W, float(vals[3 * k + 1]) * R.H
        cv2.circle(img, (int(x), int(y)), 5, (180, 30, 230), -1)
        cv2.putText(img, str(k), (int(x) + 6, int(y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 30, 230), 2)
    files.append((save('yolo_training', f'{i:05d}', img), f'training frame {i + 1}'))
sections.append(('YOLO training data', 'Samples from the 2,500 training frames, with the 7 labelled corner points the model learned to find (numbers = point order).', files))

cards = ''.join(
    f'<h2>{t}</h2><p class="note">{d}</p><div class="grid">' +
    ''.join(f'<figure><a href="{src}"><img src="{src}" alt="{cap}" loading="lazy"></a><figcaption>{cap}</figcaption></figure>' for src, cap in fs) +
    '</div>' for t, d, fs in sections)
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test Images</title><style>
:root {{ --bg:#f9f9f7; --surface:#fff; --ink:#1b1f27; --muted:#6b7280; --line:#e3e5e9; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#111214; --surface:#1a1b1e; --ink:#f1f2f4; --muted:#9aa0a8; --line:#2c2e33; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:36px 16px 80px; }}
h1 {{ font-size:30px; margin:0 0 8px; }} h2 {{ font-size:19px; margin:36px 0 2px; }}
.note {{ color:var(--muted); margin:2px 0 12px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; }}
figure {{ margin:0; background:var(--surface); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
img {{ width:100%; display:block; }} figcaption {{ font-size:13px; color:var(--muted); padding:6px 10px; }}
a.back {{ color:#2a6fdb; text-decoration:none; font-size:14px; }}
</style></head><body><main>
<a class="back" href="../what_i_tested.html">← What I tested</a>
<h1>The computer-made test images</h1>
<p class="note">These are the exact images the tests used (re-created from the same random seeds), not new examples. Each test generated its images on the fly and scored them automatically; this page saves a sample of each. Click any image to open it full size (640×480, like a webcam).</p>
{cards}</main></body></html>'''
open(f'{OUT}/index.html', 'w').write(page)
print(sum(len(fs) for _, _, fs in sections), 'images saved')
