"""Team-facing implementation plan (HTML -> PDF via headless Chrome)."""
import json
import math
import os

from pipe_helpers import (ACCENT, ARROW_DEFS, C, FRONT, INK, LINE, MUTED, OTHER, RIGHT, STATE, TOP, arrow, box,
                          face_grid, faces_of, iso_cube)

BENCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
load = lambda f: json.load(open(os.path.join(BENCH, f)))
track = load('results_tracking_gt_noise2_noise4_noise6_noise8_noise12.json')['results']
yk = load('results_yolo_kpts.json')['results']
yt = load('results_tracking_yolo.json')['results']
color = load('results_color.json')['results']
solv = {r['solver']: r for f in ('results_solvers_app_kociemba_cubejs.json',) for r in load(f)}
scan = load('results_scan_detect.json')['results']

GOOD, WARN, SERIOUS, CRIT = '#16a34a', '#f59e0b', '#ea7a4f', '#dc2626'
S1, S2 = '#2a78d6', '#eb6834'
c30 = math.cos(math.radians(30))


def hexpts(cx, cy, s):
    """The 7 keypoints in model order: 0 FRU centre, 1 FLU, 2 BLU, 3 BRU, 4 BRD, 5 FRD, 6 FLD."""
    return [(cx, cy), (cx - s * c30, cy - s / 2), (cx, cy - s), (cx + s * c30, cy - s / 2),
            (cx + s * c30, cy + s / 2), (cx, cy + s), (cx - s * c30, cy + s / 2)]


def kpt_dots(cx, cy, s, numbers=True):
    out = []
    for i, (x, y) in enumerate(hexpts(cx, cy, s)):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#e11d74" stroke="#fff" stroke-width="1.5"/>')
        if numbers:
            dx = 0 if i in (0, 2, 5) else (-11 if i in (1, 6) else 11)
            dy = -9 if i in (2,) else (14 if i == 5 else (4 if i else -9))
            if i == 0:
                dx, dy = 0, 20
                out.append(f'<rect x="{x - 7:.1f}" y="{y + 9:.1f}" width="14" height="14" rx="3" fill="#fff"/>')
            out.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="middle" font-size="10" font-weight="800" fill="#e11d74">{i}</text>')
    return ''.join(out)


def section_head(kicker, title, lead=None):
    return (f'<div class="kicker">{kicker}</div><h2>{title}</h2>' + (f'<p class="lead">{lead}</p>' if lead else ''))


def foot(n):
    return f'<div class="foot"><span>Live Cube Solver · Implementation Plan</span><span>{n} / 8</span></div>'


def table(head, rows, widths=None, cls=''):
    cols = ''.join(f'<col style="width:{w}">' for w in widths) if widths else ''
    h = ''.join(f'<th>{c}</th>' for c in head)
    b = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<table class="{cls}"><colgroup>{cols}</colgroup><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def tag(text, kind):
    return f'<span class="tag {kind}">{text}</span>'


# ---------------------------------------------------------------- page 1
ytn, yth = yt['normal|yolo'], yt['hard|yolo']
ykn = yk['mps|normal']
DBL_TOP, DBL_FRONT, DBL_RIGHT = faces_of(STATE, 'D', 'L', 'B')

flow = f'''<svg viewBox="0 0 700 250" width="100%">{ARROW_DEFS}
<rect x="6" y="8" width="268" height="234" rx="14" fill="#f3f6ff" stroke="#c9d6ff"/>
<text x="140" y="30" text-anchor="middle" font-size="11.5" font-weight="800" fill="{ACCENT}" letter-spacing="1">1 · SCAN (2 VIEWS, AUTO-CAPTURE)</text>
{iso_cube(76, 112, 46, TOP, FRONT, RIGHT)}
<text x="76" y="182" text-anchor="middle" font-size="10.5" font-weight="700" fill="{INK}">View 1: Top·Front·Right</text>
{arrow(128, 112, 152, 112)}
{iso_cube(204, 112, 46, DBL_TOP, DBL_FRONT, DBL_RIGHT)}
<text x="204" y="182" text-anchor="middle" font-size="10.5" font-weight="700" fill="{INK}">View 2: Bottom·Left·Back</text>
{box(28, 196, 224, 36, 'Validate → solve (kociemba)', '~21 moves, milliseconds', fill='#eaf7ee', stroke='#9ad5ae')}
{arrow(280, 214, 318, 214, True)}
<rect x="324" y="8" width="370" height="234" rx="14" fill="#fff8ec" stroke="#f3d29a"/>
<text x="509" y="30" text-anchor="middle" font-size="11.5" font-weight="800" fill="#b86e00" letter-spacing="1">2 · SOLVE WITH LIVE TRACKING</text>
{box(342, 44, 160, 38, 'Show next move', 'overlay on live video')}
{box(342, 98, 160, 38, 'Wait until steady', '~5 identical frames')}
{box(342, 152, 160, 38, 'Match vs predictions', 'none · 18 moves · pairs')}
{arrow(422, 82, 422, 96)}{arrow(422, 136, 422, 150)}
{arrow(502, 171, 526, 63)}{arrow(502, 171, 526, 117)}{arrow(502, 171, 526, 171)}{arrow(502, 171, 526, 222)}
<rect x="528" y="46" width="156" height="34" rx="9" fill="#eaf7ee" stroke="#9ad5ae"/><text x="606" y="67" text-anchor="middle" font-size="11.5" font-weight="700" fill="#15803d">Correct → next move</text>
<rect x="528" y="100" width="156" height="34" rx="9" fill="#f6f7f9" stroke="{LINE}"/><text x="606" y="121" text-anchor="middle" font-size="11.5" font-weight="700" fill="{MUTED}">Unsure → keep waiting</text>
<rect x="528" y="154" width="156" height="34" rx="9" fill="#fff4e5" stroke="#f3c27a"/><text x="606" y="175" text-anchor="middle" font-size="11.5" font-weight="700" fill="#b45309">Wrong → say it, re-plan</text>
<rect x="528" y="205" width="156" height="34" rx="9" fill="#fdecec" stroke="#f1a3a3"/><text x="606" y="226" text-anchor="middle" font-size="11.5" font-weight="700" fill="#b91c1c">Lost 3 s → rescan</text>
<path d="M528,63 C514,30 450,30 430,42" fill="none" stroke="{ACCENT}" stroke-width="1.6" marker-end="url(#ahA)"/>
</svg>'''

evidence = [
    ('Solver', f"{solv['kociemba (C)']['moves_mean']:.1f} moves", f"kociemba, {solv['kociemba (C)']['ms_median']:.0f} ms median · today: {solv['Current app solver']['moves_mean']:.0f} moves"),
    ('Colour naming', f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}% cubes right", f"normal light · {color['hard']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.1f}% in hard conditions"),
    ('Finding the cube', f"{ykn['found_pct']:.0f}% found", f"YOLO pose · {ykn['err_median_pct']:.1f}% point error · {ykn['ms_median']:.0f} ms GPU / {yk['cpu|normal']['ms_median']:.0f} ms CPU"),
    ('Live tracking', f"{ytn['correct']:.1f}% correct", f"0 wrong moves named in 600 trials · {yth['correct']:.1f}% in hard conditions"),
]
ev_html = ''.join(f'<div class="tile"><div class="tk">{a}</div><div class="tv">{b}</div><div class="ts">{c}</div></div>' for a, b, c in evidence)

changes = table(['', 'Today', 'New'], [
    ['Scanning', '6 faces, Capture button, line up with a grid', '2 corner views, captured automatically when steady'],
    ['Solver', 'Layer-by-layer, ~110 moves', 'kociemba two-phase, ~21 moves'],
    ['Colours', 'Centre-based rebalance', 'Same + rubiks-color-resolver fallback when invalid'],
    ['During the solve', 'User taps "next"; mistakes go unnoticed', 'Camera checks every move; wrong moves trigger a re-plan'],
    ['Cube detection', 'None (fixed grid)', 'YOLO pose model: 7 corner points per frame'],
], widths=['18%', '38%', '44%'])

page1 = f'''<section class="page">
<div class="kicker">Rubik's Cube Solver · Engineering</div>
<h1>Live Cube Solver: Implementation Plan</h1>
<div class="stripe"><div style="background:{C['W']};border:1px solid {LINE}"></div><div style="background:{C['Y']}"></div><div style="background:{C['R']}"></div><div style="background:{C['O']}"></div><div style="background:{C['G']}"></div><div style="background:{C['B']}"></div></div>
<p class="lead">A webcam watches the user's cube. After one quick scan the app computes the solution, then follows every move live. A correct move advances the guide; a wrong move is identified, the solution is re-planned from the real cube state, and the user is told what to do next. A rescan is requested only if tracking is lost.</p>
<p class="lead" style="margin-top:-6px"><b>This plan is Phase 1: everything runs on a laptop with its webcam.</b> Once it works, Phase 2 moves the same pipeline to our XREAL One Pro glasses with the XREAL Eye camera add-on.</p>
{flow}
<h3>Why these choices: measured, not guessed</h3>
<div class="tiles">{ev_html}</div>
<p class="note">From our benchmark of the open-source candidates (synthetic test frames + one real photo set; see page 8 and Benchmark_Report.pdf).</p>
<h3>What changes compared with today's app</h3>{changes}
{foot(1)}</section>'''

# ---------------------------------------------------------------- page 2
arch = f'''<svg viewBox="0 0 700 330" width="100%">{ARROW_DEFS}
<rect x="6" y="6" width="214" height="318" rx="14" fill="#f3f6ff" stroke="#c9d6ff"/>
<text x="113" y="28" text-anchor="middle" font-size="11.5" font-weight="800" fill="{ACCENT}" letter-spacing="1">BROWSER</text>
{box(20, 42, 186, 40, 'Camera capture', 'getUserMedia, 640×480')}
{box(20, 92, 186, 40, 'Frame sender', 'JPEG ~10 fps over WebSocket')}
{box(20, 142, 186, 40, 'Live view + overlay', '7 points, sticker grid, arrows')}
{box(20, 192, 186, 40, 'Guide panel', 'current move, ✓ / warnings')}
{box(20, 242, 186, 40, 'Scan panel', '2 views + captured sides')}
<text x="113" y="306" text-anchor="middle" font-size="10" fill="{MUTED}">static/live.js · static/overlay.js</text>
{arrow(226, 112, 300, 112, True, 'frames', 263, 104)}
{arrow(300, 160, 226, 160, True, 'state', 263, 176)}
<text x="263" y="140" text-anchor="middle" font-size="10.5" font-weight="700" fill="{INK}">/ws/live</text>
<rect x="306" y="6" width="388" height="318" rx="14" fill="#eaf7ee" stroke="#9ad5ae"/>
<text x="500" y="28" text-anchor="middle" font-size="11.5" font-weight="800" fill="#15803d" letter-spacing="1">PYTHON SERVER (FastAPI)</text>
{box(322, 42, 172, 44, 'Cube detector', 'vision/detector.py · YOLO')}
{box(322, 96, 172, 44, 'Sticker reader', 'vision/reader.py · 7-pt homography')}
{box(322, 150, 172, 44, 'Steady buffer', 'tracking/steady.py')}
{box(322, 204, 172, 44, 'Move matcher', 'tracking/matcher.py')}
{box(322, 258, 172, 44, 'Session controller', 'tracking/session.py (state machine)')}
{box(508, 42, 172, 44, 'Scan assembler', 'cube/scan.py · 2 views → 54')}
{box(508, 96, 172, 44, 'Colour naming', 'cube/color_detect.py + resolver')}
{box(508, 150, 172, 44, 'Validation', 'cube/validation.py (existing)')}
{box(508, 204, 172, 44, 'Cube model', 'cube/moves.py (existing)')}
{box(508, 258, 172, 44, 'Solver', 'cube/solver.py → kociemba')}
{arrow(408, 86, 408, 94)}{arrow(408, 140, 408, 148)}{arrow(408, 194, 408, 202)}{arrow(408, 248, 408, 256)}
{arrow(494, 280, 506, 280)}{arrow(494, 226, 506, 226)}{arrow(494, 64, 506, 64)}
</svg>'''

modules = table(['Module', 'Location', 'Responsibility', 'Status'], [
    ['WebSocket endpoint', 'main.py · /ws/live', 'Receive frames, run the pipeline, send state back', tag('New', 'new')],
    ['Cube detector', 'vision/detector.py', 'YOLO pose → 7 corner points + confidence', tag('New', 'new')],
    ['Sticker reader', 'vision/reader.py', '3 homographies → 27 sticker colours (Lab, median of cell centre)', tag('New', 'new')],
    ['Steady buffer', 'tracking/steady.py', 'Accept a reading only after N consistent frames', tag('New', 'new')],
    ['Move matcher', 'tracking/matcher.py', 'Score readings against every predicted outcome', tag('New', 'new')],
    ['Session controller', 'tracking/session.py', 'Phase/state machine: scan → solve → track → rescan', tag('New', 'new')],
    ['Scan assembler', 'cube/scan.py', 'Map 2 corner views to the 54 facelets', tag('New', 'new')],
    ['Colour naming', 'cube/color_detect.py', 'Add rubiks-color-resolver fallback', tag('Change', 'chg')],
    ['Solver', 'cube/solver.py', 'Wrap kociemba; keep the enrich() move descriptions', tag('Change', 'chg')],
    ['Cube model + validation', 'cube/moves.py, cube/validation.py', 'Unchanged; reused by matcher and scan', tag('Existing', 'old')],
    ['Live page', 'static/live.js, overlay.js', 'Camera, frame sending, overlay, guide UI', tag('New', 'new')],
    ['Label tool', 'static/label.html', 'Drag 7 points to correct YOLO pre-labels', tag('New', 'new')],
    ['Benchmark + renderer', 'bench/', 'Synthetic frames, regression benchmarks, training data', tag('Move in', 'old')],
], widths=['20%', '26%', '42%', '12%'], cls='small')

page2 = f'''<section class="page">{section_head('Architecture', 'System overview', 'The browser only captures video and draws. All vision, tracking and solving runs in the Python server, so it can be reused in Phase 2 on our XREAL glasses with the Eye camera.')}
{arch}{modules}{foot(2)}</section>'''

# ---------------------------------------------------------------- page 3
stickers27 = ''.join(face_grid(x, 64, 34, cols) for x, cols in ((454, TOP), (494, FRONT), (534, RIGHT)))
per_frame = f'''<svg viewBox="0 0 700 175" width="100%">{ARROW_DEFS}
<rect x="6" y="20" width="110" height="110" rx="10" fill="#1b1f27"/>{iso_cube(61, 75, 34, TOP, FRONT, RIGHT)}
<text x="61" y="150" text-anchor="middle" class="st">1 · Frame</text>
{arrow(120, 75, 140, 75)}
<rect x="146" y="20" width="110" height="110" rx="10" fill="#1b1f27"/>{iso_cube(201, 75, 34, TOP, FRONT, RIGHT)}{kpt_dots(201, 75, 34, False)}
<text x="201" y="150" text-anchor="middle" class="st">2 · YOLO: 7 points</text>
{arrow(260, 75, 280, 75)}
<rect x="286" y="20" width="140" height="110" rx="10" fill="#f6f7f9" stroke="{LINE}"/>
{''.join(f'<polygon points="{p}" fill="none" stroke="{col}" stroke-width="2.5"/>' for p, col in (
    (' '.join(f'{x:.1f},{y:.1f}' for x, y in (hexpts(356, 75, 40)[i] for i in (2, 3, 0, 1))), '#e11d74'),
    (' '.join(f'{x:.1f},{y:.1f}' for x, y in (hexpts(356, 75, 40)[i] for i in (1, 0, 5, 6))), ACCENT),
    (' '.join(f'{x:.1f},{y:.1f}' for x, y in (hexpts(356, 75, 40)[i] for i in (0, 3, 4, 5))), '#16a34a')))}
<text x="356" y="150" text-anchor="middle" class="st">3 · 3 homographies</text>
{arrow(430, 75, 448, 75)}
{stickers27}
<text x="511" y="150" text-anchor="middle" class="st">4 · 27 sticker colours</text>
{arrow(578, 75, 596, 75)}
<rect x="602" y="20" width="92" height="110" rx="10" fill="#fff8ec" stroke="#f3d29a"/>
<text x="648" y="62" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">Steady?</text>
<text x="648" y="80" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">Match +</text>
<text x="648" y="98" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">decide</text>
<text x="648" y="150" text-anchor="middle" class="st">5 · Tracker</text>
</svg>'''

budget = table(['Stage', 'Measured', 'Target', 'Notes'], [
    ['YOLO pose (yolo26n-pose, 640 px)', f"{ykn['ms_median']:.0f} ms GPU (M1 Pro) · {yk['cpu|normal']['ms_median']:.0f} ms CPU", '≤ 40 ms', 'Runs every frame; can skip frames under load'],
    ['Sticker reader + move matcher', '~62 ms (prototype)', '≤ 10 ms', 'Precompute move permutations as numpy index arrays instead of applying moves in Python'],
    ['kociemba re-plan', f"{solv['kociemba (C)']['ms_median']:.0f} ms median", '—', 'Only after a confirmed wrong move'],
    ['End-to-end per frame', '~130 ms (prototype)', '≤ 100 ms (≥ 10 fps)', 'Browser sends the next frame only after a reply (no queue build-up)'],
], widths=['27%', '28%', '15%', '30%'], cls='small')

proto = '''<div class="code"><b>Browser → server</b> (binary message): 4-byte frame id + JPEG bytes (640×480, quality ~80)
<b>Server → browser</b> (JSON):
{ "frame": 812, "phase": "tracking",              // scan_view_1 | scan_view_2 | solving | tracking | rescan | solved
  "keypoints": [[x,y], … 7 points] | null,  "confidence": 0.97,
  "stickers": {"U": ["white", …9], "F": […], "R": […]},
  "status": "waiting_steady",                 // waiting_steady | correct | wrong_move | unsure | lost
  "step": {"index": 7, "total": 21, "move": "R'", "description": "Turn the right side down"},
  "message": "You did L instead of R. New plan: 19 moves." }</div>'''

page3 = f'''<section class="page">{section_head('Per-frame pipeline', 'What happens to every camera frame', 'Each frame is a stateless function from pixels to 27 sticker colours. Only the tracker keeps state.')}
{per_frame}
<div class="two">
<div><h3>Keypoint order (the model's output contract)</h3>
<svg viewBox="0 0 240 200" width="100%" style="max-width:220px;display:block;margin:0 auto">{iso_cube(120, 105, 70, TOP, FRONT, RIGHT)}{kpt_dots(120, 105, 70)}</svg></div>
<div><h3>Face quads from the 7 points</h3>
<table class="small"><thead><tr><th>Face</th><th>Corners (TL, TR, BR, BL)</th></tr></thead><tbody>
<tr><td>Top (U)</td><td>2, 3, 0, 1</td></tr><tr><td>Front (F)</td><td>1, 0, 5, 6</td></tr><tr><td>Right (R)</td><td>0, 3, 4, 5</td></tr></tbody></table>
<p class="note">0 = corner nearest the camera (Front-Right-Top), then 1 FLU, 2 BLU, 3 BRU, 4 BRD, 5 FRD, 6 FLD. Each sticker is sampled as the median colour of the middle 40% of its cell (ignores glare specks and black borders), converted to Lab.</p></div></div>
<h3>Latency budget</h3>{budget}
<h3>WebSocket protocol</h3>{proto}
{foot(3)}</section>'''

# ---------------------------------------------------------------- page 4
def node(x, y, w, h, title, sub, fill, stroke):
    return box(x, y, w, h, title, sub, fill=fill, stroke=stroke)


sm = f'''<svg viewBox="0 0 700 330" width="100%">{ARROW_DEFS}
{node(10, 20, 130, 46, 'SCAN_VIEW_1', 'Top·Front·Right', '#f3f6ff', '#c9d6ff')}
{node(10, 100, 130, 46, 'SCAN_VIEW_2', 'Bottom·Left·Back', '#f3f6ff', '#c9d6ff')}
{node(10, 180, 130, 46, 'VALIDATE', 'colours → 54 · solve', '#f3f6ff', '#c9d6ff')}
{node(10, 252, 130, 40, 'HOME_CHECK', 'back to view 1?', '#f3f6ff', '#c9d6ff')}
{arrow(75, 66, 75, 98, False, 'steady', 98, 86)}{arrow(75, 146, 75, 178, False, 'steady', 98, 166)}{arrow(75, 226, 75, 250, False, 'valid', 96, 242)}
{node(210, 120, 150, 50, 'SHOW_MOVE', 'step i of n', '#ffffff', LINE)}
{node(210, 210, 150, 50, 'WAIT_STEADY', 'N = 5 equal readings', '#ffffff', LINE)}
{arrow(140, 272, 208, 245)}<text x="178" y="286" text-anchor="middle" font-size="10.5" fill="{MUTED}" font-weight="600">centres match</text>
{arrow(285, 170, 285, 208)}
{node(430, 210, 120, 50, 'DECIDE', 'match predictions', '#fff8ec', '#f3d29a')}
{arrow(360, 235, 428, 235, False, 'steady', 394, 228)}
{node(590, 120, 100, 44, 'NEXT', 'correct ✓', '#eaf7ee', '#9ad5ae')}
{node(590, 200, 100, 44, 'REPLAN', 'wrong move', '#fff4e5', '#f3c27a')}
{node(590, 252, 100, 40, 'RESCAN', 'lost ≥ 3 s', '#fdecec', '#f1a3a3')}
{node(590, 20, 100, 44, 'SOLVED', 'all faces 1 colour', '#eaf7ee', '#9ad5ae')}
{arrow(550, 228, 588, 142)}{arrow(550, 233, 588, 222)}{arrow(550, 240, 588, 268)}
<path d="M490,210 C490,175 400,175 360,224" fill="none" stroke="{MUTED}" stroke-width="1.6" marker-end="url(#ah)"/>
<text x="418" y="201" text-anchor="middle" font-size="10.5" fill="{MUTED}" font-weight="600">unsure → wait</text>
{arrow(590, 132, 362, 140)}{arrow(590, 212, 362, 152)}
{arrow(640, 120, 640, 66, False, 'last step', 668, 98)}
<path d="M640,292 V306 H75 V294" fill="none" stroke="#b91c1c" stroke-width="1.4" stroke-dasharray="4 3" marker-end="url(#ah)"/>
<text x="360" y="322" text-anchor="middle" font-size="10.5" fill="#b91c1c">rescan: back to SCAN_VIEW_1</text>
</svg>'''

rules = table(['Rule', 'Value (from benchmark)', 'Why'], [
    ['Steady reading', '5 consecutive frames with the same 27 colours and keypoints moving < 3% of cube size', 'Ignores half-done turns and fingers passing over'],
    ['Candidates', 'No move, all 18 single moves, all 2-move pairs on different faces (≈ 340 states)', 'Covers a quick double move; shown to be unambiguous from Top+Front+Right'],
    ['Score', 'Sum over 27 stickers of colour distance (ΔE, capped at 35) to the predicted colour', 'Cap stops one glared or covered sticker dominating'],
    ['Priors', 'expected move 0 · other single move +4 · pair +12', 'Prefer the simplest explanation'],
    ['Reference colours', 'Re-calibrated from the last confirmed steady frame', 'Follows lighting changes during the solve'],
    ['Unsure', 'Best and second-best differ by < 6', 'Wait for more frames rather than guess'],
    ['Lost', 'Best score > 22 per sticker, or no keypoints, for ≥ 3 s', 'Only then ask for a rescan'],
], widths=['18%', '50%', '32%'], cls='small')

xs = [0, 2, 4, 6, 8, 12]
ex = [round(e * 1.2533, 1) for e in xs]
corr_n = [track[f'normal|{"gt" if e == 0 else f"noise{e}"}']['correct'] for e in xs]
corr_h = [track[f'hard|{"gt" if e == 0 else f"noise{e}"}']['correct'] for e in xs]


def mini_line(width=330, height=150):
    L, R_, T, B = 36, 10, 10, 30
    pw, ph = width - L - R_, height - T - B
    X = lambda v: L + pw * v / max(ex)
    Y = lambda v: T + ph * (1 - v / 100)
    o = [f'<svg viewBox="0 0 {width} {height}" width="100%">']
    for v in (0, 50, 100):
        o.append(f'<line x1="{L}" y1="{Y(v)}" x2="{L + pw}" y2="{Y(v)}" stroke="#e1e0d9"/><text x="{L - 6}" y="{Y(v) + 4}" text-anchor="end" font-size="9.5" fill="#898781">{v}%</text>')
    for v in (0, 5, 10, 15):
        o.append(f'<text x="{X(v)}" y="{T + ph + 14}" text-anchor="middle" font-size="9.5" fill="#898781">{v}%</text>')
    for vals, col in ((corr_n, S1), (corr_h, S2)):
        o.append(f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(ex, vals))}" fill="none" stroke="{col}" stroke-width="2"/>')
        o += [f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="3.5" fill="{col}" stroke="#fff" stroke-width="1.5"/>' for a, b in zip(ex, vals)]
    xv = ykn['err_median_pct']
    o.append(f'<line x1="{X(xv):.1f}" y1="{T}" x2="{X(xv):.1f}" y2="{T + ph}" stroke="#52514e" stroke-dasharray="3 3"/>'
             f'<text x="{X(xv) + 4:.1f}" y="{T + ph * 0.62:.1f}" font-size="9.5" font-weight="700" fill="{INK}">YOLO today</text>')
    o.append(f'<text x="{L + pw / 2}" y="{height - 2}" text-anchor="middle" font-size="9.5" fill="#52514e">average corner-point error</text></svg>')
    return ''.join(o)


page4 = f'''<section class="page">{section_head('Session logic', 'Tracking state machine', 'One controller owns the phase. Every frame either keeps the state or moves it along one arrow.')}
{sm}
<h3>Decision rules</h3>{rules}
<div class="two" style="margin-top:12px">
<div><h3 style="margin-top:0">How accurate must the 7 points be?</h3>
<div class="legend"><span><i style="background:{S1}"></i>Normal light</span><span><i style="background:{S2}"></i>Hard conditions</span></div>
{mini_line()}</div>
<div><h3 style="margin-top:0">Reading the chart</h3>
<p>Tracking stays ~99% correct (normal light) while the average point error is ≤ 5% of the cube size, then drops fast. Wrong moves are almost never named, even when error is high: the tracker says "unsure" or "lost" instead.</p>
<p><b>Target for the YOLO model on real frames: average error &lt; 5%.</b> Today's synthetic-trained model sits right at that line.</p></div></div>
{foot(4)}</section>'''

# ---------------------------------------------------------------- page 5
scan2 = f'''<svg viewBox="0 0 700 210" width="100%">{ARROW_DEFS}
<rect x="6" y="6" width="200" height="198" rx="12" fill="#f6f7f9"/>
{iso_cube(106, 100, 54, TOP, FRONT, RIGHT)}
<text x="106" y="30" text-anchor="middle" font-size="11" font-weight="800" fill="{INK}">VIEW 1 (home position)</text>
<text x="106" y="190" text-anchor="middle" font-size="10.5" fill="{MUTED}">sees Top · Front · Right</text>
<rect x="250" y="40" width="200" height="130" rx="12" fill="#fff" stroke="{LINE}"/>
<text x="350" y="64" text-anchor="middle" font-size="11.5" font-weight="800" fill="{INK}">Flip (shown on screen)</text>
<text x="350" y="88" text-anchor="middle" font-size="11" fill="{INK}">1. Turn the cube upside down</text>
<text x="350" y="106" text-anchor="middle" font-size="11" fill="{INK}">(top ↔ bottom, front ↔ back)</text>
<text x="350" y="128" text-anchor="middle" font-size="11" fill="{INK}">2. Turn it a quarter so the old</text>
<text x="350" y="146" text-anchor="middle" font-size="11" fill="{INK}">Left side faces the camera</text>
{arrow(208, 105, 246, 105)}{arrow(452, 105, 490, 105)}
<rect x="494" y="6" width="200" height="198" rx="12" fill="#f6f7f9"/>
{iso_cube(594, 100, 54, DBL_TOP, DBL_FRONT, DBL_RIGHT)}
<text x="594" y="30" text-anchor="middle" font-size="11" font-weight="800" fill="{INK}">VIEW 2</text>
<text x="594" y="190" text-anchor="middle" font-size="10.5" fill="{MUTED}">sees Bottom · Left · Back</text>
</svg>'''

color_flow = f'''<svg viewBox="0 0 700 120" width="100%">{ARROW_DEFS}
{box(6, 30, 104, 56, '54 samples', 'Lab, both views')}
{arrow(112, 58, 128, 58)}
{box(130, 30, 112, 56, 'Rebalance', '6 centres as refs')}
{arrow(244, 58, 260, 58)}
<polygon points="318,24 376,58 318,92 260,58" fill="#f3f6ff" stroke="#c9d6ff" stroke-width="1.5"/>
<text x="318" y="62" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">Valid?</text>
{arrow(376, 58, 552, 58, False, 'yes', 400, 50)}
<path d="M318,92 V100 H386" fill="none" stroke="{MUTED}" stroke-width="1.8" marker-end="url(#ah)"/>
<text x="352" y="114" text-anchor="middle" font-size="10.5" fill="{MUTED}" font-weight="600">no</text>
{box(390, 78, 124, 40, 'Resolver fallback', 'rubiks-color-resolver')}
{arrow(516, 90, 552, 66)}
{box(554, 30, 140, 56, 'Validate → solve', 'else: ask to rescan', fill='#eaf7ee', stroke='#9ad5ae')}
</svg>'''

checks = table(['Check', 'When', 'User sees'], [
    ['Same view twice', 'View 2 centres equal view 1 centres', '"That is the same side again: flip the cube as shown"'],
    ['Opposite centres', 'The 3 view-2 centres must be the opposites of the 3 view-1 centres (white↔yellow, red↔orange, green↔blue)', '"Flip doesn\'t look right: try again"'],
    ['Colour counts / legal cube', 'After rebalance and fallback (existing validation)', 'Per-colour counts, then rescan the view that looks off'],
    ['Back in home position', 'Before tracking starts: visible centres must equal view 1', '"Turn the cube back to the first position"'],
], widths=['20%', '45%', '35%'], cls='small')

page5 = f'''<section class="page">{section_head('Scan', 'Scanning in 2 views', 'Each corner view shows 3 sides, so 2 views cover the cube. The same detector and reader are used for scanning and tracking.')}
{scan2}
<p class="note">The facelet mapping for view 2 (which image row/column becomes which of the 54 facelets) is derived from the cube model and must be verified by a renderer test before the UI is built (Step 4).</p>
<h3>Colour naming</h3>
{color_flow}
<p>Benchmark (150 whole cubes per lighting level): this combination got <b>{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}%</b> of cubes fully right in normal light and <b>{color['hard']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.1f}%</b> in hard conditions, better than either method alone ({color['normal']['Current app: centre rebalance (new)']['cube_correct_pct']:.0f}% / {color['normal']['rubiks-color-resolver']['cube_correct_pct']:.0f}% in normal light).</p>
<h3>Scan checks</h3>{checks}
<h3>Auto-capture rule</h3>
<p>A view is captured when YOLO confidence &gt; 0.8 and the same 27 colours are read for ~0.5 s (5 frames). The captured view appears in the bottom panel; the user can tap it to redo it.</p>
{foot(5)}</section>'''

# ---------------------------------------------------------------- page 6
loop = f'''<svg viewBox="0 0 700 215" width="100%">{ARROW_DEFS}
{box(6, 20, 132, 52, 'Synthetic renderer', 'bench/render.py')}
{box(160, 20, 132, 52, 'Pre-train YOLO', 'done: 2,500 frames')}
{box(314, 20, 132, 52, 'Live debug view', 'points on real video')}
{box(468, 20, 132, 52, 'Capture frames', '"Save frame" button')}
{arrow(140, 46, 158, 46)}{arrow(294, 46, 312, 46)}{arrow(448, 46, 466, 46)}
{box(468, 120, 132, 52, 'Label tool', 'YOLO pre-labels, fix')}
{box(314, 120, 132, 52, 'Fine-tune', 'real + synthetic mix')}
{box(160, 120, 132, 52, 'Evaluate', 'held-out real frames')}
{box(6, 120, 132, 52, 'Ship model', 'models/cube_pose.pt', fill='#eaf7ee', stroke='#9ad5ae')}
{arrow(534, 72, 534, 118)}{arrow(466, 146, 448, 146)}{arrow(312, 146, 294, 146)}{arrow(158, 146, 140, 146)}
<path d="M226,174 C226,192 380,192 380,176" fill="none" stroke="#b91c1c" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#ah)"/>
<text x="303" y="210" text-anchor="middle" font-size="10.5" fill="#b91c1c">below target → capture more of the failing cases, fine-tune again</text>
</svg>'''

dataset = table(['Item', 'Specification'], [
    ['Model', 'Ultralytics YOLO pose, yolo26n-pose (nano), 640 px input'],
    ['Keypoints', '7, in the fixed order on page 3; kpt_shape [7, 3]; flip_idx [0, 3, 2, 1, 6, 5, 4]'],
    ['Labels', 'One "cube" box + 7 points per image (Ultralytics pose txt format)'],
    ['Real data', '300–500 frames of our cubes: different angles, distances, lighting (daylight, lamp, dim), hands in all grips, a few motion-blurred frames'],
    ['Split', '80% train / 20% held-out test, split by recording session (not by frame) so the test is honest'],
    ['Mix', 'Real frames + the synthetic set (keeps rare poses covered)'],
    ['Targets on real test set', 'Cube found ≥ 98% · average point error < 5% of cube size · ≤ 40 ms on CPU'],
    ['Export (later)', 'ONNX for the XREAL / Unity port'],
], widths=['24%', '76%'], cls='small')

page6 = f'''<section class="page">{section_head('Model', 'YOLO data and training plan', 'The detector is the biggest risk: it has only been trained and tested on synthetic frames. Real frames of our cubes come first.')}
{loop}
<h3>Dataset and targets</h3>{dataset}
<h3>Current model (synthetic only)</h3>
{table(['', 'Normal light', 'Hard conditions'], [
    ['Cube found', f"{yk['mps|normal']['found_pct']:.0f}%", f"{yk['mps|hard']['found_pct']:.0f}%"],
    ['Median point error', f"{yk['mps|normal']['err_median_pct']:.1f}%", f"{yk['mps|hard']['err_median_pct']:.1f}%"],
    ['Tracking correct / wrong', f"{ytn['correct']:.1f}% / {ytn['wrong']:.1f}%", f"{yth['correct']:.1f}% / {yth['wrong']:.1f}%"],
], widths=['40%', '30%', '30%'], cls='small')}
<p class="note">Trained 8 passes (~32 min on an M1 Pro) on 2,500 synthetic frames; tested on 300 unseen synthetic frames per lighting level. Real-world performance is unknown until Step 3.</p>
{foot(6)}</section>'''

# ---------------------------------------------------------------- page 7
steps = [
    ('1', 'Foundations', 'Move bench/ into the repo; kociemba solver; colour resolver fallback', '200-cube solver test ≤ 22 moves; all existing tests pass', 'Backend', 'Small'),
    ('2', 'Live loop + debug view', '/ws/live endpoint; YOLO on every frame; overlay of 7 points + 27 colours', 'Points follow the real cube at ≥ 10 fps', 'All', 'Medium'),
    ('3', 'Real data + fine-tune', 'Save-frame button; label tool; fine-tune; real test set', 'Real test set: found ≥ 98%, error < 5%', 'Vision/ML', 'Large'),
    ('4', 'Two-view scan', 'scan.py facelet mapping; auto-capture; scan checks; UI', '≥ 95% of synthetic 2-view scans fully right; works on our cubes', 'Backend + Frontend', 'Medium'),
    ('5', 'Live tracking', 'steady buffer, matcher (vectorised), session state machine, re-plan, rescan; guide UI', 'Synthetic solve video with mistakes: 0 wrong moves named; real solves complete', 'Backend + Frontend', 'Large'),
    ('6', 'Polish, then Phase 2', 'Turn arrows drawn on the cube faces; sounds. Then Phase 2: XREAL glasses with the Eye camera (YOLO exported to ONNX)', 'Phase 1 complete on the laptop', 'Frontend / Vision', 'Medium'),
]
road = ''.join(
    f'<div class="rm"><div class="num">{n}</div><div class="rmb"><b>{t}</b><span>{d}</span><span class="done">Done when: {done}</span></div>'
    f'<div class="rmr"><span class="tag ws">{w}</span><span class="tag sz">{sz}</span></div></div>' for n, t, d, done, w, sz in steps)

lanes = f'''<svg viewBox="0 0 700 120" width="100%">
<text x="0" y="24" font-size="11" font-weight="700" fill="{INK}">Vision / ML</text>
<text x="0" y="60" font-size="11" font-weight="700" fill="{INK}">Backend</text>
<text x="0" y="96" font-size="11" font-weight="700" fill="{INK}">Frontend</text>
{''.join(f'<rect x="{x}" y="{y}" width="{w}" height="24" rx="6" fill="{f}"/><text x="{x + w / 2}" y="{y + 16}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#fff">{t}</text>'
         for x, y, w, f, t in (
             (100, 46, 90, '#5b6472', '1 Foundations'),
             (196, 10, 110, ACCENT, '2 Debug view'), (196, 46, 110, ACCENT, '2 /ws/live'), (196, 82, 110, ACCENT, '2 Overlay'),
             (312, 10, 200, '#7c3aed', '3 Capture · label · fine-tune'),
             (312, 46, 120, '#0e9f6e', '4 Scan mapping'), (312, 82, 120, '#0e9f6e', '4 Scan UI'),
             (438, 46, 160, '#d97706', '5 Tracker + re-plan'), (438, 82, 160, '#d97706', '5 Guide UI'),
             (518, 10, 80, '#7c3aed', '3 Retrain'),
             (604, 10, 96, '#5b6472', '6 ONNX'), (604, 82, 96, '#5b6472', '6 Arrows')))}
</svg>'''

testing = table(['Level', 'What', 'When'], [
    ['Unit tests', 'Facelet mapping, matcher scoring, state machine transitions, solver wrapper', 'Every commit'],
    ['Benchmarks', 'bench/ suite: solver, colours, tracking vs point error, YOLO accuracy', 'Every model or tracker change'],
    ['Synthetic solve video', 'Rendered video of a full solve with random mistakes, streamed through /ws/live', 'Before merging Step 5'],
    ['Real-camera checklist', '5 scrambles × 3 lighting setups; record misses as new training data', 'End of Steps 3, 4, 5'],
], widths=['20%', '58%', '22%'], cls='small')

page7 = f'''<section class="page">{section_head('Roadmap', 'Build order', 'Each step leaves the app working. Step 1 is shared groundwork; after it, the three workstreams run in parallel.')}
{road}
<h3>Workstreams</h3>{lanes}
<h3>Testing</h3>{testing}
{foot(7)}</section>'''

# ---------------------------------------------------------------- page 8
risks = table(['Risk', 'Impact', 'Mitigation'], [
    ['YOLO is weaker on real video than on synthetic frames', 'Tracking gets "lost" often', 'Step 3 comes before scan/tracking work; capture failing cases and retrain; target < 5% error'],
    ['Users rotate the whole cube mid-solve', 'Nothing matches → lost', 'Clear "home position" UI; home check; rescan is cheap (2 views)'],
    ['Glare and fingers hide stickers', 'Wrong or unsure readings', 'Capped scoring, steady buffer, re-calibrated references'],
    ['Server too slow on CPU-only laptops', '< 10 fps', 'Vectorised matcher; skip frames; GPU/MPS when available'],
    ['Licences: kociemba GPL-2.0, Ultralytics AGPL-3.0', 'Matters if sold or closed-source', 'Fine for internal use; decide before any release (alternatives exist)'],
    ['sebastienlato/cube-solver has no licence', 'Cannot copy its code', 'We use the method only (own implementation, already prototyped)'],
], widths=['30%', '22%', '48%'], cls='small')

ev = table(['Benchmark', 'Result', 'Setup'], [
    ['Solvers', f"kociemba {solv['kociemba (C)']['moves_mean']:.1f} moves, 100% solved; current app {solv['Current app solver']['moves_mean']:.0f} moves", '200 random cubes, replayed on our cube model'],
    ['Sticker finding, cube held freely', f"best classical {max(scan['Free hand-held, normal light'][d]['correct_pct'] for d in scan['Free hand-held, normal light']):.1f}% of frames", '200 synthetic frames per condition'],
    ['Sticker finding, corner view', 'classical 0–2.7%; YOLO 100%', '150 / 300 synthetic frames'],
    ['Colours (combined)', f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}% / {color['hard']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.1f}% cubes fully right", '150 cubes per lighting level'],
    ['Tracking with YOLO', f"{ytn['correct']:.1f}% / {yth['correct']:.1f}% correct, 0% wrong", '300 before/after trials per lighting level'],
    ['Real photos', 'rubiks-cube-tracker and qbr (multi-scale) read 6/6 faces', 'dwalton76 test photos, one real cube'],
], widths=['26%', '44%', '30%'], cls='small')

page8 = f'''<section class="page">{section_head('Risks and evidence', 'Risks, open questions, sources')}
{risks}
<h3>Open questions for the team</h3>
<ol class="oq"><li>Licensing: is GPL / AGPL acceptable for how this will be shipped?</li>
<li>Hardware: which laptops must reach 10 fps? Is a GPU/Apple-silicon minimum acceptable?</li>
<li>Who records and labels the 300–500 real frames for Step 3, and with which cubes (sticker vs stickerless)?</li>
<li>Do we keep the 6-face scan as a fallback, or ship the 2-view scan only?</li></ol>
<h3>Benchmark evidence</h3>{ev}
<p class="note">Full numbers and charts: <b>Benchmark_Report.pdf</b>. Caveat: almost all test images are synthetic renders (realistic lighting, glare, fingers, blur, noise); real-world results will be lower until Step 3 is done.</p>
<h3>Open-source components</h3>
{table(['Component', 'Used for', 'Licence'], [
    ['kociemba (muodov/kociemba)', 'Solver', 'GPL-2.0'],
    ['rubiks-color-resolver (dwalton76)', 'Colour fallback', 'MIT'],
    ['Ultralytics YOLO', 'Cube keypoint detector', 'AGPL-3.0'],
    ['sebastienlato/cube-solver', '7-point / homography method (idea only)', 'None stated'],
    ['OpenCV, FastAPI, NumPy', 'Imaging, server, maths', 'Apache-2.0 / MIT / BSD'],
], widths=['38%', '40%', '22%'], cls='small')}
{foot(8)}</section>'''

css = f'''
@page {{ size: Letter; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: {INK}; background: #fff; }}
.page {{ width: 8.5in; height: 11in; padding: 0.55in 0.6in; page-break-after: always; position: relative; overflow: hidden; }}
.page:last-child {{ page-break-after: auto; }}
.kicker {{ font-size: 10.5px; letter-spacing: 2px; text-transform: uppercase; color: {ACCENT}; font-weight: 800; margin-bottom: 4px; }}
h1 {{ font-size: 30px; margin: 0 0 8px; letter-spacing: -0.5px; }}
h2 {{ font-size: 22px; margin: 0 0 4px; letter-spacing: -0.3px; }}
h3 {{ font-size: 13.5px; margin: 14px 0 6px; }}
p.lead {{ font-size: 13px; color: {MUTED}; line-height: 1.5; margin: 0 0 12px; }}
p {{ font-size: 11.5px; line-height: 1.5; margin: 6px 0; }}
.note {{ font-size: 10.5px; color: {MUTED}; }}
.stripe {{ display: flex; height: 7px; border-radius: 4px; overflow: hidden; margin: 0 0 14px; width: 170px; }}
.stripe div {{ flex: 1; }}
.tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
.tile {{ border: 1px solid {LINE}; border-radius: 10px; padding: 9px 11px; }}
.tk {{ font-size: 9.5px; letter-spacing: 1px; text-transform: uppercase; color: {MUTED}; font-weight: 800; }}
.tv {{ font-size: 16px; font-weight: 800; margin: 2px 0; }}
.ts {{ font-size: 10px; color: {MUTED}; line-height: 1.35; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 4px; table-layout: fixed; }}
th {{ text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.8px; color: {MUTED}; padding: 5px 7px; border-bottom: 2px solid {INK}; }}
td {{ font-size: 11px; padding: 6px 7px; border-bottom: 1px solid #eef0f3; vertical-align: top; line-height: 1.4; }}
table.small td {{ font-size: 10.3px; padding: 4.5px 7px; }}
.tag {{ font-size: 9.5px; font-weight: 800; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }}
.tag.new {{ background: #eaf7ee; color: #15803d; }} .tag.chg {{ background: #fff4e5; color: #b45309; }} .tag.old {{ background: #f1f3f6; color: {MUTED}; }}
.tag.ws {{ background: #f3f6ff; color: {ACCENT}; }} .tag.sz {{ background: #f1f3f6; color: {MUTED}; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: start; }}
.code {{ font-family: Menlo, Consolas, monospace; font-size: 9.6px; line-height: 1.5; background: #f6f7f9; border: 1px solid {LINE}; border-radius: 8px; padding: 9px 11px; white-space: pre-wrap; }}
.code b {{ font-family: -apple-system, Helvetica, sans-serif; font-size: 10.5px; }}
.st {{ font-size: 10.5px; font-weight: 700; fill: {INK}; }}
.legend {{ display: flex; gap: 14px; font-size: 10.5px; color: {MUTED}; }}
.legend i {{ display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }}
.rm {{ display: flex; align-items: center; gap: 12px; border: 1px solid {LINE}; border-radius: 10px; padding: 8px 12px; margin-bottom: 7px; }}
.num {{ width: 28px; height: 28px; border-radius: 50%; background: {INK}; color: #fff; font-weight: 800; display: flex; align-items: center; justify-content: center; flex: none; font-size: 13px; }}
.rmb {{ flex: 1; }} .rmb b {{ display: block; font-size: 12.5px; }} .rmb span {{ display: block; font-size: 10.5px; color: {MUTED}; line-height: 1.4; }}
.rmb .done {{ color: {INK}; }}
.rmr {{ display: flex; flex-direction: column; gap: 4px; align-items: flex-end; }}
ol.oq {{ margin: 4px 0 0; padding-left: 18px; }} ol.oq li {{ font-size: 11.5px; line-height: 1.55; }}
.foot {{ position: absolute; bottom: 0.35in; left: 0.6in; right: 0.6in; font-size: 9.5px; color: #9aa3b2; display: flex; justify-content: space-between; }}
'''

html = f'''<!doctype html><html><head><meta charset="utf-8"><title>Live Cube Solver Implementation Plan</title><style>{css}</style></head>
<body>{page1}{page2}{page3}{page4}{page5}{page6}{page7}{page8}</body></html>'''
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports_out', 'implementation_plan.html'), 'w').write(html)
print('ok')
