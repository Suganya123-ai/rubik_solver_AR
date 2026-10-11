"""First-person benchmark report covering every test run. Reuses the chart
helpers and loaded results from build_report.py."""
import html
import json

import build_report as B

esc = html.escape
load = B.load
vis = load('results_visibility.json')['results']
eph_solver = load('results_solver_ephynes_settings.json')
scan, color, solv, real, corner = B.scan['results'], B.color['results'], B.solv, B.real, B.corner['results']
yk, yt = B.yk, B.yt
ytn, yth = B.ytn, B.yth
yk_n, yk_h = B.yk_n, B.yk_h
conds, dets = B.conds, B.dets

# ---------- solver ----------
order_s = ['Current app solver', 'kociemba (C)', 'RubikTwoPhase (Python)', 'cubejs (JavaScript)']
solver_rows = [(s, solv[s]) for s in order_s] + [('ephynes settings (depth 25)', eph_solver)]
moves_chart = B.hbars([(n, [r['moves_mean']]) for n, r in solver_rows], [('Average moves to solve', B.S1)],
                      unit='', vmax=120, fmt='{:.1f}', label_w=270)
solver_table = B.table(['Solver', 'Solved', 'Avg moves', 'Max moves', 'Median time'],
                       [[n, f"{r['solved_pct']:.0f}%", f"{r['moves_mean']:.1f}", r['moves_max'], f"{r['ms_median']:.0f} ms"]
                        for n, r in solver_rows])

# ---------- scan detection ----------
scan_chart = B.hbars([(d, [scan[c][d]['correct_pct'] for c in conds]) for d in dets],
                     [(c, col) for c, col in zip(conds, (B.S1, B.S2, B.S3))], label_w=250)
scan_table = B.table(['Detector', 'Free, normal: right order', 'any rotation', 'Free, hard: right order', 'any rotation', 'Speed', 'Real photos'],
                     [[d, f"{scan[conds[1]][d]['correct_pct']:.1f}%", f"{scan[conds[1]][d].get('any_rotation_pct', 0):.1f}%",
                       f"{scan[conds[2]][d]['correct_pct']:.1f}%", f"{scan[conds[2]][d].get('any_rotation_pct', 0):.1f}%",
                       f"{scan[conds[0]][d]['ms_median']:.1f} ms", f"{real[d]['faces_read']}/6"] for d in dets])

# ---------- colours ----------
cmeth = list(color['normal'])
color_chart = B.hbars([(m, [color['normal'][m]['cube_correct_pct'], color['hard'][m]['cube_correct_pct']]) for m in cmeth],
                      [('Normal light', B.S1), ('Hard conditions', B.S2)], label_w=300)
color_table = B.table(['Method', 'Stickers right (normal)', 'Stickers right (hard)'],
                      [[m, f"{color['normal'][m]['sticker_acc_pct']:.2f}%", f"{color['hard'][m]['sticker_acc_pct']:.2f}%"] for m in cmeth])

# ---------- visibility ----------
vis_rows = [('Front only', 'F'), ('Top + Front', 'U+F'), ('Top + Front + Right', 'U+F+R')]
vis_chart = B.hbars([(lab, [vis[k]['one_move_ambiguous_pct'], vis[k]['two_moves_ambiguous_pct']]) for lab, k in vis_rows],
                    [('One move: cannot tell which', B.S1), ('Two quick moves: cannot tell which', B.S2)], label_w=200)

# ---------- corner view ----------
corner_table = B.table(['Detector', 'Found any 1 face (normal)', '(hard)', 'Reads all 3 sides?'],
                       [[d, f"{corner['normal'][d]:.1f}%", f"{corner['hard'][d]:.1f}%", 'No: built for one flat face'] for d in corner['normal']] +
                       [['YOLO pose (trained by me)', f"{yk_n['found_pct']:.1f}%", f"{yk_h['found_pct']:.1f}%", 'Yes: finds the 7 corner points']])

tiles = [
    ('Solver', 'kociemba', f"{solv['kociemba (C)']['moves_mean']:.1f} moves avg, {solv['kociemba (C)']['ms_median']:.0f} ms (current app: {solv['Current app solver']['moves_mean']:.0f})"),
    ('Colour naming', 'Rebalance + resolver', f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}% of cubes fully right (normal light)"),
    ('Finding the cube', 'YOLO pose (trained)', f"{yk_n['found_pct']:.0f}% found, {yk_n['err_median_pct']:.1f}% point error, {yk_n['ms_median']:.0f} ms"),
    ('Live move tracking', 'YOLO + 7-point method', f"{ytn['correct']:.1f}% correct, {ytn['wrong']:.1f}% wrong (normal light)"),
]
tile_html = ''.join(f'<div class="tile"><div class="tk">{esc(a)}</div><div class="tv">{esc(b)}</div><div class="ts">{esc(c)}</div></div>' for a, b, c in tiles)

e_free = scan[conds[1]]['ephynes AR solver (C# port)']
e_free_ms = scan[conds[1]]['ephynes + multi-scale (our tweak)']
ephynes_table = B.table(['Area', 'ephynes (C#)', 'Best option found', 'Verdict'], [
    ['Following moves during the solve', 'None: advances whenever a stable face reappears; never checks the move', f"YOLO + matcher: {ytn['correct']:.1f}% correct, 0 wrong", '<b>Missing</b>'],
    ['Finding a hand-held face', f"{e_free['correct_pct']:.1f}% right order ({e_free_ms['correct_pct']:.1f}% with multi-scale); grid often rotated", 'YOLO: 100% found', 'Best classical, not enough'],
    ['Corner view (3 sides)', f"{corner['normal']['ephynes AR solver (C# port)']:.1f}%", 'YOLO: 100%', 'No'],
    ['Colours', f"{color['normal']['ephynes: per-face colours (C# port)']['cube_correct_pct']:.0f}% / {color['hard']['ephynes: per-face colours (C# port)']['cube_correct_pct']:.0f}% cubes right", f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}% / {color['hard']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.1f}%", 'No'],
    ['Solver', f"{eph_solver['moves_mean']:.1f} moves (two-phase, maxDepth 25)", f"kociemba {solv['kociemba (C)']['moves_mean']:.1f}", 'Same'],
    ['Speed per frame', f"{scan[conds[0]]['ephynes AR solver (C# port)']['ms_median']:.1f} ms", f"YOLO {yk_n['ms_median']:.0f} ms (M1 Pro GPU)", 'Faster'],
], num_from=99)

candidates = B.table(['Project', 'What I did with it', 'Licence'], [
    ['muodov/kociemba', 'Solver benchmark', 'GPL-2.0'],
    ['hkociemba/RubiksCube-TwophaseSolver (RubikTwoPhase)', 'Solver benchmark', 'GPL-3.0'],
    ['cubejs', 'Solver benchmark', 'MIT'],
    ['kkoomen/qbr', 'Sticker finding + colour benchmarks (plus my multi-scale variant)', 'MIT'],
    ['dwalton76/rubiks-cube-tracker', 'Sticker finding + real photos', 'MIT'],
    ['dwalton76/rubiks-color-resolver', 'Colour benchmark', 'MIT'],
    ['ephynes/AR-Optimal-Rubiks-Cube-solver (C#)', 'Read the code; ported detection + colours to Python; all benchmarks', 'MIT (solver origin unlicensed)'],
    ['sebastienlato/cube-solver', '7-corner-point / homography method, re-implemented (no code copied)', 'None stated'],
    ['Ultralytics YOLO (yolo26n-pose)', 'Trained and tested a cube keypoint model', 'AGPL-3.0'],
    ['RubikClear, cube-cv, CubeCV, cubeworks, RubikVision, Bishwaswarup/rubiks, cdbharath/rubiks_cube_3dcv, ios-rubik-solver', 'Reviewed only: none does live move checking; nothing to add over the tested ones', 'various'],
], num_from=99)

css_extra = '''
ul.find li { margin:4px 0; font-size:13px; }
.method td:first-child { font-weight:600; width:24%; }
'''

page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cube Solver Benchmark</title>
<style>{B.page.split('<style>')[1].split('</style>')[0]}{css_extra}</style></head><body><main>
<h1>Live Rubik's Cube Solver: Benchmark of Open-Source Options</h1>
<p class="lead">I tested the open-source options for every part of a live, camera-guided cube solver on the same tests, to decide what to build on. This report covers everything I ran, the numbers, and what I'm choosing.</p>

<section><h2>Summary: the winners</h2><div class="tiles">{tile_html}</div>
<p class="note">Normal light = even lighting and few fingers in the way. Hard conditions = strong colour casts, glare, more fingers, blur and a noisy camera.</p>
<p class="verdict"><b>No single open-source project does the whole job.</b> None of them checks the user's moves live. The pipeline I'm building combines the best piece for each step and adds the move tracking myself.</p></section>

<section><h2>How I tested</h2>
<table class="method"><tbody>
<tr><td>Test images</td><td>A renderer I wrote draws a 3D cube in any scrambled state (states come from our own cube model) on cluttered backgrounds, with random lighting, colour casts, glare, fingers, blur, camera noise and JPEG compression. Every sticker position is known exactly, so every result can be scored automatically.</td></tr>
<tr><td>Real photos</td><td>dwalton76's published photos of one real cube (6 faces, held by a robot) as a real-world check.</td></tr>
<tr><td>Fairness</td><td>Each project's own code ran with its own settings. Where a fixed size limit made a project fail on our frame sizes (qbr, ephynes), I also ran a <b>multi-scale variant</b> that retries on scaled copies of the frame, labelled "our tweak". The C# project could not run here (no .NET/Unity), so I ported its detection and colour code to Python line by line with all original thresholds.</td></tr>
<tr><td>Scoring</td><td>Sticker finding counts only if all 9 stickers land on the right stickers in the right order. Colours count whole cubes with all 54 stickers right. Tracking counts a trial correct only if it names exactly what happened.</td></tr>
<tr><td>Machine</td><td>Apple M1 Pro laptop.</td></tr>
</tbody></table></section>

<section><h2>1 · Solver</h2><p class="q">The same {solv['kociemba (C)']['n']} random cubes through every solver; each solution was replayed on our cube model to confirm it really solves.</p>
{B.legend([('Average moves to solve', B.S1)])}{moves_chart}{solver_table}
<p class="verdict"><b>kociemba wins.</b> Every solver solves 100% of cubes, but our current solver needs about 5× more moves. kociemba is the fastest of the short-solution solvers, so re-planning after a mistake takes milliseconds.</p></section>

<section><h2>2 · Finding the stickers during the scan</h2><p class="q">{B.N_scan} frames per condition. "Right order" means all 9 stickers found in the correct positions.</p>
{B.legend([(c, col) for c, col in zip(conds, (B.S1, B.S2, B.S3))])}{scan_chart}{scan_table}
<p class="verdict"><b>No classical detector is good enough for a hand-held cube.</b> Lined up with a guide grid, our current app and rubiks-cube-tracker are near 100%. Held freely, the best (the ephynes detector with my multi-scale tweak) gets the right order in only 38.5% of frames, and it and rubiks-cube-tracker often lock onto the wrong spot or return the grid rotated.</p></section>

<section><h2>3 · Naming the colours</h2><p class="q">{B.N_col} whole cubes per lighting level (6 scans each, one lighting session per cube). Stickers sampled at their true positions, so only the colour step is tested.</p>
{B.legend([('Normal light', B.S1), ('Hard conditions', B.S2)])}<p class="note" style="margin:0 0 4px">% of cubes with all 54 stickers right</p>{color_chart}{color_table}
<p class="verdict"><b>Best: our centre-based rebalance, with rubiks-color-resolver as a fallback when the result is invalid</b>: 98% of cubes fully right in normal light and 88.7% in hard conditions, better than either alone.</p></section>

<section><h2>4 · How much of the cube the camera must see</h2><p class="q">For 300 random cubes I checked, using our cube model, whether every possible move (and every pair of moves) leaves a different picture on the visible sides.</p>
{B.legend([('One move: cannot tell which', B.S1), ('Two quick moves: cannot tell which', B.S2)])}<p class="note" style="margin:0 0 4px">% of cubes where the move can't be identified (lower is better)</p>{vis_chart}
<p class="verdict"><b>The camera must see 3 sides (Top, Front, Right) during the solve.</b> With the front alone, turns of the back are invisible; with Top + Front, two quick moves are confused half the time; with 3 sides every move and every pair is identifiable.</p></section>

<section><h2>5 · Live move tracking</h2><p class="q">{B.track['n']} before/after trials per point: the right move, no move, a wrong move, or two quick moves. The 3 sides are read from the cube's 7 corner points (the sebastienlato/cube-solver method, which I re-implemented), then compared with every possible move.</p>
{B.legend([('Normal light', B.S1), ('Hard conditions', B.S2)])}<p class="note" style="margin:0 0 4px">% of trials where it correctly says what happened, by how far off the corner points are</p>{B.charts['track']}{B.track_table}
<p class="verdict"><b>The tracking logic works</b>: with an average corner-point error up to about 5% of the cube size it is 99.7% right in normal light and 92% in hard conditions, and it almost never names a wrong move. When unsure it waits or asks for a rescan instead of guessing.</p>
<h3>Can existing detectors handle the corner view?</h3>{corner_table}</section>

<section><h2>6 · YOLO to find the cube</h2><p class="q">I trained a small YOLO pose model (yolo26n-pose) on {B.ytrain['n_train']:,} synthetic corner frames ({B.ytrain['epochs']} passes, {B.ytrain['minutes']:.0f} min on the M1 Pro) and tested it on {B.N_y} new frames per lighting level.</p>
{B.yolo_table}
<h3>Tracking outcomes with YOLO finding the points</h3>
<p class="note" style="margin:0">Normal light</p>{B.outcomes(ytn)}
<p class="note" style="margin:4px 0 0">Hard conditions</p>{B.outcomes(yth)}
<p class="verdict"><b>YOLO is what makes live tracking possible.</b> It found the cube in every test frame, its ~5% point error sits right at what tracking tolerates, and tracking with it never named a wrong move. Every classical detector fails at this view.</p></section>

<section><h2>7 · The ephynes C# project (AR-Optimal-Rubiks-Cube-solver)</h2>
<p class="q">Because our end product runs on XREAL glasses with a C# (Unity) app, I checked this C# AR solver in detail. It is a Unity port of AndroidSteve's "Rubik Cube Wizard", built for a Meta 2 headset study.</p>
{ephynes_table}
<ul class="find">
<li><b>No move checking:</b> during the solve it moves to the next instruction whenever the camera sees a stable face again (<code>AppStateMachine.cs</code>), so a wrong move goes unnoticed and nothing is re-planned.</li>
<li><b>Rotated grid:</b> it orders the 9 stickers from whichever corner of a sticker is highest in the image, so a small tilt left or right can rotate the grid by 90°. Allowing any rotation, it finds the face in {e_free['any_rotation_pct']:.1f}% of frames, versus {e_free['correct_pct']:.1f}% in the right order.</li>
<li><b>Colour check disabled:</b> its "exactly 9 of each colour" step is commented out and would crash if enabled, so colours are named one face at a time.</li>
<li><b>Worth reusing:</b> its Unity structure (camera into OpenCvSharp, state machine, Kalman filter) and possibly its C# two-phase solver, once the solver's licence is confirmed (it was translated from a project with no licence file).</li></ul>
<p class="verdict"><b>It does not perform better.</b> It has the best classical face detector and is very fast, but it can't check moves, which is the core feature I need.</p></section>

<section><h2>8 · Hardware findings (XREAL One Pro + Beam Pro)</h2><ul class="find">
<li><b>Camera:</b> our glasses have the <b>XREAL Eye</b> camera add-on, so the camera sees what the wearer sees, which is the ideal view for this app. XREAL's documentation confirms the Eye is the camera apps can use on the One series.</li>
<li><b>Compute:</b> the Beam Pro is an Android 14 device with a Snapdragon 6 Gen 1 and two 50 MP rear cameras. YOLO can run on it in Unity through the Inference Engine (Sentis) from an ONNX export; speed on this mid-range chip still needs measuring.</li>
<li><b>SDK:</b> the One Pro uses XREAL SDK 3.x (camera class <code>XREALRGBCameraTexture</code>, YUV_420_888 frames), not the older NRSDK our Unity scaffold was written against.</li></ul></section>

<section><h2>What I'm going with</h2><ol class="stack">
<li><b>Solver:</b> kociemba.</li>
<li><b>Finding the cube:</b> a YOLO pose model for both the scan and tracking.</li>
<li><b>Reading 3 sides:</b> the 7-corner-point method.</li>
<li><b>Colours:</b> centre rebalance with rubiks-color-resolver as fallback; re-calibrated from the last frame during tracking.</li>
<li><b>Move tracking:</b> compare against every predicted move; wait when unsure, rescan only when lost.</li>
<li><b>Rollout:</b> Phase 1 runs on a laptop with its webcam (Python pipeline + browser view). Phase 2, once Phase 1 works, moves it to our XREAL glasses with the Eye camera, with the app in C# on the Beam Pro.</li></ol>
<div class="caveat"><b>Limits.</b> Almost all images are synthetic, so real-world numbers will be lower; YOLO in particular has only seen synthetic frames and must be fine-tuned on a few hundred real photos of our cubes. The only real photos were 6 photos of one robot-held cube. Tracking was tested on single before/after frames; the real app will also average several steady frames.</div></section>

<section><h2>Everything I looked at</h2>{candidates}</section>
</main></body></html>'''
open('reports_out/benchmark_report.html', 'w').write(page)
print('v2 written')
