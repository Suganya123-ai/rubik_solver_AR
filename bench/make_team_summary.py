"""4-page team summary (first person) with charts from the benchmark results."""
import html
import json
import sys

import build_report as B  # noqa: E402  (loads all results + chart helpers)
from pipe_helpers import ARROW_DEFS, FRONT, RIGHT, TOP, arrow, box, iso_cube  # noqa: E402

esc = html.escape
scan, color, solv, corner = B.scan['results'], B.color['results'], B.solv, B.corner['results']
vis = json.load(open('results/results_visibility.json'))['results']
ytn, yth, ykn, yk = B.ytn, B.yth, B.yk_n, B.yk
conds = B.conds
INK, MUTED, LINE, ACCENT = '#1b1f27', '#5b6472', '#d5d9e0', '#3a6ff7'
S1, S2 = B.S1, B.S2

# ---------- charts ----------
solver_chart = B.hbars([('Current solver', [solv['Current app solver']['moves_mean']]),
                        ('kociemba', [solv['kociemba (C)']['moves_mean']])],
                       [('Average moves', S1)], unit='', vmax=120, fmt='{:.0f}', label_w=140, width=330, bar_h=16)

free = conds[1]
best = lambda d: max(scan[free][d]['correct_pct'], 0)
hand_chart = B.hbars([('Current app (grid)', [scan[free]['Current app (fixed grid)']['correct_pct']]),
                      ('qbr', [scan[free]['qbr + multi-scale (our tweak)']['correct_pct']]),
                      ('rubiks-cube-tracker', [scan[free]['rubiks-cube-tracker (dwalton76)']['correct_pct']]),
                      ('ephynes (C#)', [scan[free]['ephynes + multi-scale (our tweak)']['correct_pct']])],
                     [('Face found correctly', S1)], label_w=150, width=330, bar_h=14)

corner_chart = B.hbars([('qbr', [corner['normal']['qbr + multi-scale (our tweak)']]),
                        ('rubiks-cube-tracker', [corner['normal']['rubiks-cube-tracker (dwalton76)']]),
                        ('ephynes (C#)', [corner['normal']['ephynes + multi-scale (our tweak)']]),
                        ('YOLO (trained by me)', [ykn['found_pct']])],
                       [('Cube found', S1)], label_w=150, width=330, bar_h=14)

cm = [('Old HSV thresholds', 'Current app: HSV thresholds (old)'), ('ephynes (C#)', 'ephynes: per-face colours (C# port)'),
      ('rubiks-color-resolver', 'rubiks-color-resolver'), ('Centre rebalance', 'Current app: centre rebalance (new)'),
      ('Rebalance + resolver', 'Combined: app rebalance, resolver if invalid')]
color_chart = B.hbars([(lab, [color['normal'][k]['cube_correct_pct'], color['hard'][k]['cube_correct_pct']]) for lab, k in cm],
                      [('Normal light', S1), ('Hard lighting', S2)], label_w=170, width=640, bar_h=12)

vis_chart = B.hbars([('Front only', [vis['F']['one_move_ambiguous_pct'], vis['F']['two_moves_ambiguous_pct']]),
                     ('Top + Front', [vis['U+F']['one_move_ambiguous_pct'], vis['U+F']['two_moves_ambiguous_pct']]),
                     ('Top + Front + Right', [vis['U+F+R']['one_move_ambiguous_pct'], vis['U+F+R']['two_moves_ambiguous_pct']])],
                    [('1 move', S1), ('2 quick moves', S2)], label_w=150, width=330, bar_h=13)

xs = [0, 2, 4, 6, 8, 12]
ex = [round(e * 1.2533, 1) for e in xs]
tr = B.track['results']
corr = {l: [tr[f'{l}|{"gt" if e == 0 else f"noise{e}"}']['correct'] for e in xs] for l in ('normal', 'hard')}
track_chart = B.line_chart(ex, [('Normal light', S1, corr['normal']), ('Hard lighting', S2, corr['hard'])],
                           marks=[(f'YOLO ≈ {ykn["err_median_pct"]:.1f}%', ykn['err_median_pct'], '#52514e')],
                           width=330, height=210, xlab='Corner-point error (% of cube size)')

flow = f'''<svg viewBox="0 0 700 150" width="100%">{ARROW_DEFS}
{iso_cube(56, 70, 38, TOP, FRONT, RIGHT)}
<text x="56" y="138" text-anchor="middle" font-size="11" font-weight="700" fill="{INK}">Camera sees cube</text>
{arrow(104, 70, 124, 70)}
{box(128, 46, 120, 48, 'YOLO', '7 corner points')}
{arrow(250, 70, 270, 70)}
{box(274, 46, 120, 48, 'Read 3 sides', '27 sticker colours')}
{arrow(396, 70, 416, 70)}
{box(420, 46, 130, 48, 'Compare moves', 'right · wrong · none')}
{arrow(552, 70, 572, 70)}
<rect x="576" y="10" width="118" height="30" rx="8" fill="#eaf7ee" stroke="#9ad5ae"/><text x="635" y="30" text-anchor="middle" font-size="11" font-weight="700" fill="#15803d">✓ next move</text>
<rect x="576" y="55" width="118" height="30" rx="8" fill="#fff4e5" stroke="#f3c27a"/><text x="635" y="75" text-anchor="middle" font-size="11" font-weight="700" fill="#b45309">wrong → re-plan</text>
<rect x="576" y="100" width="118" height="30" rx="8" fill="#fdecec" stroke="#f1a3a3"/><text x="635" y="120" text-anchor="middle" font-size="11" font-weight="700" fill="#b91c1c">lost → rescan</text>
<text x="335" y="128" text-anchor="middle" font-size="10.5" fill="{MUTED}">kociemba re-plans in ~11 ms after a wrong move</text>
</svg>'''

hw = f'''<svg viewBox="0 0 700 190" width="100%">{ARROW_DEFS}
{box(10, 20, 170, 54, 'XREAL One Pro', 'glasses: display only', fill='#f3f6ff', stroke='#c9d6ff')}
{box(10, 110, 170, 54, 'XREAL Eye', 'camera add-on (we have it)', fill='#eaf7ee', stroke='#9ad5ae')}
<line x1="95" y1="108" x2="95" y2="76" stroke="#5b6472" stroke-width="1.8"/><text x="102" y="96" font-size="10" fill="#5b6472">clips onto glasses</text>
{box(250, 62, 190, 64, 'Beam Pro', 'Android 14 · Snapdragon 6 Gen 1')}
<text x="345" y="142" text-anchor="middle" font-size="10.5" fill="{MUTED}">C# Unity app · XREAL SDK 3.x</text>
{arrow(248, 80, 184, 50)}{arrow(184, 134, 248, 104)}
<text x="205" y="52" font-size="10" fill="{MUTED}">display</text><text x="196" y="160" font-size="10" fill="{MUTED}">camera frames</text>
<rect x="500" y="14" width="190" height="72" rx="10" fill="#fff" stroke="{LINE}"/>
<text x="595" y="36" text-anchor="middle" font-size="11.5" font-weight="800" fill="{INK}">Phase 1 · now</text>
<text x="595" y="54" text-anchor="middle" font-size="10.5" fill="{MUTED}">laptop + its webcam</text>
<text x="595" y="70" text-anchor="middle" font-size="10.5" fill="{MUTED}">Python pipeline, browser view</text>
<rect x="500" y="104" width="190" height="72" rx="10" fill="#fff" stroke="{LINE}"/>
<text x="595" y="126" text-anchor="middle" font-size="11.5" font-weight="800" fill="{INK}">Phase 2 · after</text>
<text x="595" y="144" text-anchor="middle" font-size="10.5" fill="{MUTED}">same pipeline on the glasses,</text>
<text x="595" y="160" text-anchor="middle" font-size="10.5" fill="{MUTED}">Eye camera, C# app on Beam Pro</text>
{arrow(595, 87, 595, 102)}{arrow(442, 108, 498, 138)}
</svg>'''

ytbl = B.table(['', 'Normal light', 'Hard lighting'], [
    ['Correct', f"{ytn['correct']:.1f}%", f"{yth['correct']:.1f}%"],
    ['Wrong move named', f"{ytn['wrong']:.1f}%", f"{yth['wrong']:.1f}%"],
    ['Unsure / lost (waits or rescans)', f"{ytn['unsure'] + ytn['lost'] + ytn['no_kpts']:.1f}%", f"{yth['unsure'] + yth['lost'] + yth['no_kpts']:.1f}%"]])

ephynes = B.table(['', 'ephynes (C#)', 'Our pipeline'], [
    ['Checks the user\'s moves', '<b>No</b> (advances on any stable face)', f"Yes: {ytn['correct']:.1f}% correct, 0 wrong"],
    ['Finds a hand-held face', f"{scan[free]['ephynes + multi-scale (our tweak)']['correct_pct']:.1f}% (grid often rotated)", 'YOLO: 100% found'],
    ['Colours (whole cube right)', f"{color['normal']['ephynes: per-face colours (C# port)']['cube_correct_pct']:.0f}%", f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}%"],
    ['Solver', '20.7 moves', '20.7 moves'],
    ['Speed per frame', f"{scan[conds[0]]['ephynes AR solver (C# port)']['ms_median']:.1f} ms", f"YOLO {ykn['ms_median']:.0f} ms (laptop GPU)"],
], num_from=99)

using = B.table(['Step', 'Choice', 'Result'], [
    ['Solver', '<b>kociemba</b>', f"{solv['kociemba (C)']['moves_mean']:.1f} moves vs {solv['Current app solver']['moves_mean']:.0f} today · {solv['kociemba (C)']['ms_median']:.0f} ms"],
    ['Colours', '<b>Centre rebalance + rubiks-color-resolver fallback</b>', f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}% / {color['hard']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.1f}% of cubes fully right"],
    ['Finding the cube', '<b>YOLO pose model</b> (7 corner points)', f"{ykn['found_pct']:.0f}% found · {ykn['err_median_pct']:.1f}% point error · {ykn['ms_median']:.0f} ms"],
    ['Reading 3 sides', '<b>7-corner-point method</b> (idea from sebastienlato/cube-solver)', '27 stickers per frame'],
    ['Move tracking', '<b>Our own</b>: compare with every possible move', f"{ytn['correct']:.1f}% / {yth['correct']:.1f}% correct · 0 wrong moves named"],
], num_from=99)

tiles = ''.join(f'<div class="tile"><div class="tv">{a}</div><div class="ts">{b}</div></div>' for a, b in [
    (f"{solv['kociemba (C)']['moves_mean']:.0f} moves", f"per solve (today: {solv['Current app solver']['moves_mean']:.0f})"),
    (f"{color['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}%", 'of cubes read fully right'),
    (f"{ykn['found_pct']:.0f}%", 'cube found by YOLO'),
    (f"{ytn['correct']:.1f}%", 'moves tracked correctly, 0 wrong'),
])

css = f'''@page {{ size: Letter; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: {INK}; background: #fff; }}
.page {{ width: 8.5in; height: 11in; padding: 0.55in 0.6in; page-break-after: always; position: relative; overflow: hidden; }}
.page:last-child {{ page-break-after: auto; }}
.kicker {{ font-size: 10.5px; letter-spacing: 2px; text-transform: uppercase; color: {ACCENT}; font-weight: 800; margin-bottom: 4px; }}
h1 {{ font-size: 28px; margin: 0 0 8px; letter-spacing: -0.4px; }}
h2 {{ font-size: 20px; margin: 0 0 6px; }}
h3 {{ font-size: 13px; margin: 12px 0 4px; }}
p {{ font-size: 11.8px; line-height: 1.5; margin: 6px 0; }}
.lead {{ font-size: 13px; color: {MUTED}; }}
.note {{ font-size: 10.3px; color: {MUTED}; }}
.callout {{ background: #f3f6ff; border-left: 4px solid {ACCENT}; border-radius: 8px; padding: 9px 13px; margin: 10px 0; font-size: 12px; line-height: 1.5; }}
.callout.warn {{ background: #fff8ec; border-left-color: #f59e0b; }}
.tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 10px 0; }}
.tile {{ border: 1px solid {LINE}; border-radius: 10px; padding: 10px 12px; }}
.tv {{ font-size: 21px; font-weight: 800; }} .ts {{ font-size: 10.5px; color: {MUTED}; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
th {{ text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: .8px; color: {MUTED}; padding: 5px 7px; border-bottom: 2px solid {INK}; }}
td {{ font-size: 11px; padding: 5px 7px; border-bottom: 1px solid #eef0f3; vertical-align: top; line-height: 1.4; }}
.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
.legend {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 10.5px; color: {MUTED}; margin: 2px 0 4px; }}
.legend i {{ display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }}
svg text {{ font-family: -apple-system, Helvetica, sans-serif; }}
.tick {{ font-size: 10.5px; fill: #898781; }} .rowlab {{ font-size: 11.5px; fill: {INK}; }} .val {{ font-size: 10.5px; fill: #52514e; }}
.axl {{ font-size: 11px; fill: #52514e; }} .dl {{ font-size: 11px; font-weight: 600; }} .seg {{ font-size: 11px; fill: #0b0b0b; font-weight: 600; }}
ul {{ margin: 4px 0; padding-left: 18px; }} li {{ font-size: 11.8px; line-height: 1.5; margin: 3px 0; }}
.foot {{ position: absolute; bottom: 0.35in; left: 0.6in; right: 0.6in; font-size: 9.5px; color: #9aa3b2; display: flex; justify-content: space-between; }}
'''
foot = lambda n: f'<div class="foot"><span>Live Rubik\'s Cube Solver · Benchmark summary</span><span>{n} / 4</span></div>'

p1 = f'''<section class="page"><div class="kicker">Rubik's Cube Solver · Team update</div>
<h1>What I tested and what we'll build on</h1>
<p class="lead">I benchmarked the open-source options for every part of a live, camera-guided Rubik's Cube solver on the same tests. This is the short version; the full numbers are in Benchmark_Report.pdf.</p>
<div class="callout"><b>Bottom line:</b> no existing project checks the user's moves live and re-plans after a mistake. We'll combine the best piece for each step and build the move tracking ourselves, and in my tests that tracking worked. <b>Phase 1</b> runs on a laptop with its webcam; <b>Phase 2</b> then moves it to our XREAL glasses with the Eye camera.</div>
<div class="tiles">{tiles}</div>
<h3>How the live solver works</h3>{flow}
<h3>What we're using</h3>{using}
<h3>What I did</h3>
<ul><li>Reviewed about 20 open-source cube solvers and scanners; ran 8 of them in depth, including the C# AR solver (ported to Python to test it), and re-implemented the 3-side reading method of a 9th.</li>
<li>Wrote a test-image generator: a 3D cube in real scrambled states with random lighting, glare, fingers, blur and camera noise, so every result is scored automatically.</li>
<li>Ran the same tests on every option: 200 cubes per solver, 600 frames per detector, 300 whole cubes for colours, 3,600 tracking trials, plus 6 real photos.</li>
<li>Built and tested the move-tracking logic, and trained a YOLO model (2,500 frames, 32 min) to find the cube for it.</li>
<li>Checked the XREAL hardware and SDK to see what the glasses can actually run.</li></ul>
<p class="note">Normal light = even lighting, few fingers in the way. Hard lighting = colour casts, glare, more fingers, blur, noisy camera.</p>
{foot(1)}</section>'''

p2 = f'''<section class="page"><div class="kicker">The evidence</div><h2>Why each choice won</h2>
<div class="two"><div><h3>Solver: moves per solve</h3><p class="note" style="margin:0">200 random cubes, every solution verified</p>{solver_chart}
<p>kociemba solves in about a fifth of the moves, in ~11 ms.</p></div>
<div><h3>Finding a hand-held cube face</h3><p class="note" style="margin:0">200 frames, cube held freely, normal light</p>{hand_chart}
<p>Classical detectors only work when the cube is lined up with a guide grid. Held freely, the best got 38.5%.</p></div></div>
<h3>Naming the colours: % of cubes with all 54 stickers right</h3>
{B.legend([('Normal light', S1), ('Hard lighting', S2)])}{color_chart}
<p>Combining our centre rebalance with rubiks-color-resolver beats either alone, especially in hard lighting.</p>
<div class="two"><div><h3>Finding the cube corner-on (needed for tracking)</h3><p class="note" style="margin:0">150 / 300 frames, normal light</p>{corner_chart}</div>
<div><h3>Why YOLO</h3><p>Tracking needs the camera to see the cube corner-on. Every classical detector fails at this view (0–4%). The YOLO model I trained finds it in every test frame, in 15 ms on a laptop GPU.</p></div></div>
{foot(2)}</section>'''

p3 = f'''<section class="page"><div class="kicker">Live tracking</div><h2>Checking every move the user makes</h2>
<div class="two"><div><h3>How much of the cube must the camera see?</h3>
<p class="note" style="margin:0">% of 300 cubes where the move can't be identified (lower is better)</p>
{B.legend([('1 move', S1), ('2 quick moves', S2)])}{vis_chart}</div>
<div><h3>&nbsp;</h3><p>With only the front visible, turns of the back side are invisible. With <b>Top + Front + Right</b>, every move and every pair of quick moves can be identified. So during solving the user holds the cube corner-on to the camera and turns layers only.</p></div></div>
<div class="two"><div><h3>How accurate must the cube's corner points be?</h3>
{B.legend([('Normal light', S1), ('Hard lighting', S2)])}{track_chart}</div>
<div><h3>&nbsp;</h3><p>Tracking stays about 99% correct (normal light) while the corner points are within ~5% of the cube's size. YOLO's error is 5.2%, right at that line.</p>
<p>Even when the points are poor it almost never names a wrong move: it says "unsure" and waits, or asks for a rescan.</p></div></div>
<h3>Tracking with YOLO finding the cube (300 trials per lighting level)</h3>{ytbl}
<p class="note" style="margin-top:6px">Normal light</p>{B.outcomes(ytn)}
<p class="note" style="margin:4px 0 0">Hard lighting</p>{B.outcomes(yth)}
{foot(3)}</section>'''

p4 = f'''<section class="page"><div class="kicker">C# and hardware</div><h2>The C# repo and our glasses</h2>
<h3>ephynes/AR-Optimal-Rubiks-Cube-solver (C#): not better</h3>{ephynes}
<p>It's fast and has the best classical detector, but it can't check moves, which is our core feature. We may reuse its Unity structure and its C# solver once the solver's licence is confirmed.</p>
<h3>Rollout and hardware</h3>{hw}
<ul><li><b>Phase 1 (now):</b> everything runs on a laptop with its webcam. <b>Phase 2 (once Phase 1 works):</b> the same pipeline moves to our XREAL One Pro glasses.</li>
<li>Our glasses have the <b>XREAL Eye</b> camera add-on, so in Phase 2 the camera sees exactly what the wearer sees: the ideal view of the cube in their hands.</li>
<li>Our Unity scaffold targets the old NRSDK; the One Pro needs <b>XREAL SDK 3.x</b>.</li></ul>
<h3>Risks and decisions</h3>
<div class="callout warn"><b>Main risk:</b> most tests used synthetic images I generated (realistic lighting, glare, fingers, blur). YOLO has only seen synthetic frames, so it needs fine-tuning on a few hundred real photos of our cubes before we trust these numbers.</div>
<ul><li><b>Licences:</b> kociemba is GPL and YOLO (Ultralytics) is AGPL. Fine for internal use; we need a decision before any release.</li>
<li><b>Phase 2 detail, decided later:</b> whether the glasses stream frames to the laptop or run everything on the Beam Pro.</li></ul>
<h3>Next steps (Phase 1, on the laptop)</h3>
<ol style="margin:4px 0;padding-left:18px"><li style="font-size:11.8px">Switch to kociemba and the colour fallback.</li>
<li style="font-size:11.8px">Live camera view with YOLO, then record and label real frames to retrain it.</li>
<li style="font-size:11.8px">Two-view scan, then live move tracking with re-planning.</li>
<li style="font-size:11.8px">Then Phase 2: move it to the XREAL glasses with the Eye camera.</li></ol>
{foot(4)}</section>'''

html_doc = f'<!doctype html><html><head><meta charset="utf-8"><title>Cube Solver Team Summary</title><style>{css}</style></head><body>{p1}{p2}{p3}{p4}</body></html>'
open('reports_out/team_summary.html', 'w').write(html_doc)
print('ok')
