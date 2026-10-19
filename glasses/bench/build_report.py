"""Builds the benchmark report (HTML with inline SVG charts) from the
results_*.json files. Chrome prints the same page to PDF."""
import html
import json
import os

S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'  # categorical slots 1-3
INK, INK2, MUTED, GRID, BASE = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
GOOD, WARN, SERIOUS, CRIT = '#0ca30c', '#fab219', '#ec835a', '#d03b3b'

load = lambda f: json.load(open(os.path.join('results', f)))
solv = {r['solver']: r for f in ('results_solvers_app_kociemba_cubejs.json', 'results_solvers_twophase.json') for r in load(f)}
scan = load('results_scan_detect.json')
color = load('results_color.json')
track = load('results_tracking_gt_noise2_noise4_noise6_noise8_noise12.json')
real = load('results_real.json')
corner = load('results_corner_classic.json')
yk = load('results_yolo_kpts.json')
yt = load('results_tracking_yolo.json')
ytrain = load('yolo_train_summary.json')
esc = html.escape


def legend(items):
    return '<div class="legend">' + ''.join(
        f'<span><i style="background:{c}"></i>{esc(n)}</span>' for n, c in items) + '</div>'


def hbars(rows, series, unit='%', vmax=100, label_w=230, width=640, bar_h=13, gap=3, group_gap=14, fmt='{:.1f}'):
    """rows: [(label, [v per series])]; series: [(name, color)]."""
    n = len(series)
    gh = n * bar_h + (n - 1) * gap
    h = len(rows) * (gh + group_gap) + 26
    plot_w = width - label_w - 60
    x = lambda v: label_w + plot_w * (v / vmax)
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img">']
    for t in range(0, 5):
        v = vmax * t / 4
        out.append(f'<line x1="{x(v):.1f}" y1="0" x2="{x(v):.1f}" y2="{h - 22}" stroke="{GRID}" stroke-width="1"/>'
                   f'<text x="{x(v):.1f}" y="{h - 8}" text-anchor="middle" class="tick">{fmt.format(v).rstrip("0").rstrip(".") if "." in fmt.format(v) else fmt.format(v)}{unit}</text>')
    y = 4
    for label, vals in rows:
        out.append(f'<text x="{label_w - 10}" y="{y + gh / 2 + 4}" text-anchor="end" class="rowlab">{esc(label)}</text>')
        for i, ((sname, col), v) in enumerate(zip(series, vals)):
            by = y + i * (bar_h + gap)
            if v is None:
                out.append(f'<text x="{label_w + 4}" y="{by + bar_h - 3}" class="val">n/a</text>')
                continue
            w = max(plot_w * (v / vmax), 2)
            r = min(4, w / 2)
            out.append(f'<g><title>{esc(label)} · {esc(sname)}: {fmt.format(v)}{unit}</title>'
                       f'<path d="M{label_w},{by} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{bar_h - 2 * r} a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} z" fill="{col}"/>'
                       f'<text x="{label_w + w + 5:.1f}" y="{by + bar_h - 2.5}" class="val">{fmt.format(v)}{unit}</text></g>')
        y += gh + group_gap
    out.append(f'<line x1="{label_w}" y1="0" x2="{label_w}" y2="{h - 22}" stroke="{BASE}" stroke-width="1"/></svg>')
    return ''.join(out)


def line_chart(xs, series, marks=(), width=640, height=250, xlab='', ylab=''):
    L, R_, T, B = 46, 20, 12, 40
    pw, ph = width - L - R_, height - T - B
    x = lambda v: L + pw * v / max(xs)
    y = lambda v: T + ph * (1 - v / 100)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for v in range(0, 101, 25):
        out.append(f'<line x1="{L}" y1="{y(v)}" x2="{L + pw}" y2="{y(v)}" stroke="{GRID}"/>'
                   f'<text x="{L - 8}" y="{y(v) + 4}" text-anchor="end" class="tick">{v}%</text>')
    for v in xs:
        out.append(f'<text x="{x(v)}" y="{T + ph + 18}" text-anchor="middle" class="tick">{v}%</text>')
    out.append(f'<text x="{L + pw / 2}" y="{height - 4}" text-anchor="middle" class="axl">{esc(xlab)}</text>')
    for name, col, vals in series:
        pts = ' '.join(f'{x(a):.1f},{y(b):.1f}' for a, b in zip(xs, vals))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2" stroke-linejoin="round"/>')
        for a, b in zip(xs, vals):
            out.append(f'<g><title>{esc(name)} · error {a}%: {b:.1f}% correct</title>'
                       f'<circle cx="{x(a):.1f}" cy="{y(b):.1f}" r="4.5" fill="{col}" stroke="#fcfcfb" stroke-width="2"/></g>')
    for label, xv, col in marks:
        out.append(f'<line x1="{x(xv):.1f}" y1="{T}" x2="{x(xv):.1f}" y2="{T + ph}" stroke="{col}" stroke-width="1.5" stroke-dasharray="4 3"/>'
                   f'<rect x="{x(xv) + 4:.1f}" y="{T + ph * 0.55 - 14:.1f}" width="{len(label) * 6.6 + 8:.0f}" height="20" rx="4" fill="#fcfcfb"/>'
                   f'<text x="{x(xv) + 8:.1f}" y="{T + ph * 0.55:.1f}" class="dl" fill="{INK}">{esc(label)}</text>')
    out.append(f'<line x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}" stroke="{BASE}"/></svg>')
    return ''.join(out)


def outcome_bar(parts, width=640):
    """100% stacked bar of tracking outcomes with status colours + labels."""
    x, out = 0, [f'<svg viewBox="0 0 {width} 30" width="100%" role="img">']
    for name, v, col in parts:
        w = width * v / 100
        if w <= 0:
            continue
        out.append(f'<g><title>{esc(name)}: {v:.1f}%</title><rect x="{x:.1f}" y="2" width="{max(w - 2, 1):.1f}" height="24" rx="4" fill="{col}"/>'
                   + (f'<text x="{x + 8:.1f}" y="19" class="seg">{esc(name)} {v:.1f}%</text>' if w > 120 else '') + '</g>')
        x += w
    return ''.join(out) + '</svg>'


def table(head, rows, num_from=1):
    h = ''.join(f'<th{" class=n" if i >= num_from else ""}>{esc(c)}</th>' for i, c in enumerate(head))
    b = ''.join('<tr>' + ''.join(f'<td{" class=n" if i >= num_from else ""}>{c}</td>' for i, c in enumerate(r)) + '</tr>'
                for r in rows)
    return f'<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


# ---------- numbers ----------
order_s = ['Current app solver', 'kociemba (C)', 'RubikTwoPhase (Python)', 'cubejs (JavaScript)']
conds = list(scan['results'])
dets = list(scan['results'][conds[0]])
cmeth = list(color['results']['normal'])
xs = [0, 2, 4, 6, 8, 12]
tr = track['results']
corr = {lvl: [tr[f'{lvl}|{"gt" if e == 0 else f"noise{e}"}']['correct'] for e in xs] for lvl in ('normal', 'hard')}
wrong = {lvl: [tr[f'{lvl}|{"gt" if e == 0 else f"noise{e}"}']['wrong'] for e in xs] for lvl in ('normal', 'hard')}
yk_n, yk_h = yk['results']['mps|normal'], yk['results']['mps|hard']
ytn, yth = yt['results']['normal|yolo'], yt['results']['hard|yolo']

charts = {}
charts['moves'] = hbars([(s, [solv[s]['moves_mean']]) for s in order_s], [('average moves', S1)], unit='', vmax=120, fmt='{:.1f}')
charts['scan'] = hbars([(d, [scan['results'][c][d]['correct_pct'] for c in conds]) for d in dets],
                       [(c, col) for c, col in zip(conds, (S1, S2, S3))])
charts['color'] = hbars([(m, [color['results']['normal'][m]['cube_correct_pct'], color['results']['hard'][m]['cube_correct_pct']]) for m in cmeth],
                        [('Normal light', S1), ('Hard conditions', S2)], label_w=290)
# Noise was added per x/y coordinate with std sigma; the average straight-line
# error that produces is sigma*sqrt(pi/2) ~ 1.25*sigma, the same measure as YOLO's error.
xs_err = [round(e * 1.2533, 1) for e in xs]
charts['track'] = line_chart(xs_err, [('Normal light', S1, corr['normal']), ('Hard conditions', S2, corr['hard'])],
                             marks=[(f'YOLO error ≈ {yk_n["err_median_pct"]:.1f}%', yk_n['err_median_pct'], INK2)],
                             xlab='Average corner-point error (% of cube size)')


def outcomes(r):
    parts = [('Correct', r['correct'], GOOD), ('Unsure → waits', r['unsure'], WARN),
             ('Lost → asks rescan', r['lost'] + r['no_kpts'], SERIOUS), ('Wrong move named', r['wrong'], CRIT)]
    return outcome_bar(parts) + legend([(f'{n}: {v:.1f}%', c) for n, v, c in parts])
    return outcome_bar([('Correct', r['correct'], GOOD), ('Unsure → waits', r['unsure'], WARN),
                        ('Lost → rescan', r['lost'] + r['no_kpts'], SERIOUS), ('Wrong', r['wrong'], CRIT)])


best_track = f"{ytn['correct']:.1f}%"
tiles = [
    ('Solver', 'kociemba', f"{solv['kociemba (C)']['moves_mean']:.1f} moves avg, {solv['kociemba (C)']['ms_median']:.0f} ms (app today: {solv['Current app solver']['moves_mean']:.0f})"),
    ('Colour naming', 'App rebalance + resolver', f"{color['results']['normal']['Combined: app rebalance, resolver if invalid']['cube_correct_pct']:.0f}% of cubes fully right (normal light)"),
    ('Finding the cube', 'YOLO pose (trained)', f"{yk_n['found_pct']:.0f}% found, {yk_n['err_median_pct']:.1f}% point error, {yk_n['ms_median']:.0f} ms"),
    ('Live move tracking', 'YOLO + 7-point method', f"{best_track} correct, {ytn['wrong']:.1f}% wrong (normal light)"),
]
tile_html = ''.join(f'<div class="tile"><div class="tk">{esc(a)}</div><div class="tv">{esc(b)}</div><div class="ts">{esc(c)}</div></div>' for a, b, c in tiles)

solver_table = table(['Solver', 'Solved', 'Avg moves', 'Max moves', 'Median time', '95% of solves under'],
                     [[s, f"{solv[s]['solved_pct']:.0f}%", f"{solv[s]['moves_mean']:.1f}", solv[s]['moves_max'],
                       f"{solv[s]['ms_median']:.0f} ms", f"{solv[s]['ms_p95']:.0f} ms"] for s in order_s])
scan_speed = table(['Detector', 'Median time / frame', 'Real photos (6 faces)'],
                   [[d, f"{scan['results'][conds[0]][d]['ms_median']:.1f} ms", f"{real[d]['faces_read']}/6"] for d in dets])
false_rows = [[d, f"{scan['results'][conds[1]][d]['found_pct'] - scan['results'][conds[1]][d]['correct_pct']:.1f}%",
               f"{scan['results'][conds[2]][d]['found_pct'] - scan['results'][conds[2]][d]['correct_pct']:.1f}%"]
              for d in dets if 'Current app' not in d]
false_table = table(['Detector', 'Wrong (normal)', '(hard)'], false_rows)
color_table = table(['Method', 'Stickers right (normal)', 'Stickers right (hard)'],
                    [[m, f"{color['results']['normal'][m]['sticker_acc_pct']:.2f}%", f"{color['results']['hard'][m]['sticker_acc_pct']:.2f}%"] for m in cmeth])
track_table = table(['Average point error'] + ['0% (perfect)' if e == 0 else f'{e}%' for e in xs_err],
                    [['Correct · normal'] + [f'{v:.1f}%' for v in corr['normal']],
                     ['Wrong · normal'] + [f'{v:.1f}%' for v in wrong['normal']],
                     ['Correct · hard'] + [f'{v:.1f}%' for v in corr['hard']],
                     ['Wrong · hard'] + [f'{v:.1f}%' for v in wrong['hard']]])
corner_table = table(['Detector', 'Found any 1 face (normal)', '(hard)', 'Can read all 3 sides?'],
                     [[d, f"{corner['results']['normal'][d]:.1f}%", f"{corner['results']['hard'][d]:.1f}%", 'No — built for one flat face']
                      for d in corner['results']['normal']] +
                     [['YOLO pose (trained here)', f"{yk_n['found_pct']:.1f}%", f"{yk_h['found_pct']:.1f}%", 'Yes — finds the 7 corner points']])
yolo_table = table(['', 'Normal light', 'Hard conditions'],
                   [['Cube found', f"{yk_n['found_pct']:.1f}%", f"{yk_h['found_pct']:.1f}%"],
                    ['Median point error', f"{yk_n['err_median_pct']:.1f}%", f"{yk_h['err_median_pct']:.1f}%"],
                    ['95% of frames under', f"{yk_n['err_p95_pct']:.1f}%", f"{yk_h['err_p95_pct']:.1f}%"],
                    ['Speed (M1 Pro GPU)', f"{yk_n['ms_median']:.0f} ms", f"{yk_h['ms_median']:.0f} ms"],
                    ['Speed (CPU only)', f"{yk['results']['cpu|normal']['ms_median']:.0f} ms", f"{yk['results']['cpu|hard']['ms_median']:.0f} ms"],
                    ['Tracking: correct', f"{ytn['correct']:.1f}%", f"{yth['correct']:.1f}%"],
                    ['Tracking: wrong move named', f"{ytn['wrong']:.1f}%", f"{yth['wrong']:.1f}%"],
                    ['Tracking: unsure / lost (waits or asks rescan)', f"{ytn['unsure'] + ytn['lost'] + ytn['no_kpts']:.1f}%", f"{yth['unsure'] + yth['lost'] + yth['no_kpts']:.1f}%"]])

N_s, N_scan, N_col, N_tr, N_y = solv['kociemba (C)']['n'], scan['n'], color['n'], track['n'], yk['n']

page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cube Pipeline Benchmark</title>
<style>
:root {{ --surface:#fcfcfb; --page:#f9f9f7; --ink:{INK}; --ink2:{INK2}; --muted:{MUTED}; --line:{GRID}; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--page); color:var(--ink); font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:860px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:28px; margin:0 0 6px; letter-spacing:-.3px; }}
h2 {{ font-size:19px; margin:0 0 4px; }}
h3 {{ font-size:14px; margin:18px 0 6px; }}
.lead {{ color:var(--ink2); font-size:15px; margin:0 0 20px; }}
section {{ background:var(--surface); border:1px solid rgba(11,11,11,.08); border-radius:12px; padding:20px 22px; margin:16px 0; break-inside:avoid; }}
.q {{ color:var(--ink2); margin:0 0 12px; }}
.verdict {{ border-left:4px solid {S1}; background:#f2f6fd; padding:9px 12px; border-radius:6px; margin:12px 0 0; }}
.tiles {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }}
.tile {{ border:1px solid var(--line); border-radius:10px; padding:12px 14px; background:var(--surface); }}
.tk {{ font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
.tv {{ font-size:18px; font-weight:700; margin:2px 0; }}
.ts {{ font-size:12.5px; color:var(--ink2); }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; font-size:12.5px; color:var(--ink2); margin:4px 0 6px; }}
.legend i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; vertical-align:-1px; }}
svg text {{ font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
.tick {{ font-size:11px; fill:{MUTED}; }} .rowlab {{ font-size:12.5px; fill:{INK}; }} .val {{ font-size:11.5px; fill:{INK2}; }}
.axl {{ font-size:12px; fill:{INK2}; }} .dl {{ font-size:12px; font-weight:600; }} .seg {{ font-size:11.5px; fill:#0b0b0b; font-weight:600; }}
table {{ width:100%; border-collapse:collapse; margin:8px 0 0; font-size:12.5px; }}
th {{ text-align:left; color:var(--muted); font-weight:600; font-size:11.5px; padding:6px 8px; border-bottom:1px solid {BASE}; }}
td {{ padding:6px 8px; border-bottom:1px solid var(--line); }}
.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
.note {{ font-size:12px; color:var(--ink2); margin-top:8px; }}
.caveat {{ background:#fff7eb; border-left:4px solid {WARN}; padding:9px 12px; border-radius:6px; font-size:13px; }}
ol.stack li {{ margin:4px 0; }}
@media (max-width:600px) {{ .tiles {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:#fff; }} main {{ padding:0; }} section {{ border-color:#ddd; break-inside:auto; }}
  svg, table, .verdict, .tiles, .caveat, h3 {{ break-inside:avoid; }} h2, h3 {{ break-after:avoid; }} }}
</style></head><body><main>
<h1>Live cube solver: which tools work best</h1>
<p class="lead">I tried each candidate on the same tests and measured it. Each step of the pipeline is below with its numbers, then the stack I recommend.</p>

<section><h2>The winners</h2><div class="tiles">{tile_html}</div>
<p class="note">Normal light = even lighting and few fingers in the way. Hard conditions = strong colour casts, glare, more fingers, blur, a noisy camera.</p></section>

<section><h2>1 · Solver</h2><p class="q">Same {N_s} random cubes through every solver. Each solution was replayed on your app's cube model to check it really solves.</p>
{legend([('Average moves to solve', S1)])}{charts['moves']}{solver_table}
<p class="verdict"><b>kociemba wins.</b> All solve 100% of cubes, but the current app needs about 5× more moves. kociemba is the fastest of the short-solution solvers: re-planning after a mistake takes milliseconds.</p></section>

<section><h2>2 · Finding the stickers during the scan</h2><p class="q">{N_scan} synthetic webcam frames per condition. A frame counts only if all 9 stickers are found, in the right spots and order.</p>
{legend([(c, col) for c, col in zip(conds, (S1, S2, S3))])}{charts['scan']}
<h3>Speed and real photos</h3>{scan_speed}
<h3>Wrong detections (found something, but wrong spot or rotated grid)</h3>{false_table}
<p class="verdict"><b>No classical detector is good enough for a hand-held cube.</b> Lined up with the guide grid, the current app and rubiks-cube-tracker are near 100%. Held freely, every classical detector finds the face in the right order in only 5–39% of frames (best: the ephynes C# detector with our multi-scale tweak), and several latch onto wrong spots or return the grid rotated. On the clean real photos, rubiks-cube-tracker and qbr + multi-scale read all 6 faces; ephynes + multi-scale read 2; the fixed grid, plain qbr and plain ephynes read none, because that cube didn't fill the guide area or sat outside their fixed sticker-size limits.</p></section>

<section><h2>3 · Naming the colours</h2><p class="q">{N_col} whole cubes per lighting level (6 scans each, one lighting session per cube). Stickers sampled at their true positions, so only the colour step is tested.</p>
{legend([('Normal light', S1), ('Hard conditions', S2)])}<p class="note" style="margin:0 0 4px">% of cubes with all 54 stickers right</p>{charts['color']}{color_table}
<p class="verdict"><b>Best: your app's centre rebalance, falling back to dwalton76's rubiks-color-resolver when the result is invalid</b>: 98% of cubes fully right in normal light, 88.7% in hard conditions. Each alone is worse, and qbr's default palette almost never gets a whole cube right.</p></section>

<section><h2>4 · Live move tracking (reading 3 sides)</h2><p class="q">{N_tr} before/after trials per point: the right move, no move, a wrong move, or two quick moves. The 3 sides are read from the 7 corner points (the method from sebastienlato/cube-solver, re-implemented in Python), then matched against every possible move.</p>
{legend([('Normal light', S1), ('Hard conditions', S2)])}<p class="note" style="margin:0 0 4px">% of trials where it correctly says what happened, by how far off the corner points are</p>{charts['track']}{track_table}
<p class="verdict"><b>The tracking logic works</b>: with an average corner-point error up to ~5% of the cube size, 99.7% right in normal light and 92% in hard conditions, and it almost never names the wrong move. When unsure it waits or asks for a rescan instead of guessing. So the real question is how accurately the corner points can be found.</p>
<h3>Can existing detectors find the corner view?</h3>{corner_table}</section>

<section><h2>5 · YOLO to find the cube</h2><p class="q">A small YOLO pose model (yolo26n-pose) trained here on {ytrain['n_train']:,} synthetic corner frames ({ytrain['epochs']} passes, {ytrain['minutes']:.0f} min on the M1 Pro), then tested on {N_y} new frames per lighting level that it never saw.</p>
{yolo_table}
<h3>Tracking outcomes with YOLO finding the points</h3>
<p class="note" style="margin:0">Normal light</p>{outcomes(ytn)}
<p class="note" style="margin:4px 0 0">Hard conditions</p>{outcomes(yth)}
<p class="verdict"><b>YOLO is the piece that makes live tracking possible.</b> It found the cube in every test frame, its ~5% point error sits right at what tracking tolerates, and with it tracking was {ytn['correct']:.1f}% right in normal light and {yth['correct']:.1f}% in hard conditions without ever naming a wrong move. At {yk_n['ms_median']:.0f} ms per frame on the M1 Pro GPU it is fast enough for a live feed. Every classical detector fails at this view.</p></section>

<section><h2>Recommended stack</h2><ol class="stack">
<li><b>Solver:</b> kociemba (pip install kociemba).</li>
<li><b>Finding the cube:</b> a YOLO pose model, both for the scan and for tracking. Classical detectors only work with a lined-up cube.</li>
<li><b>Reading 3 sides:</b> the 7-corner-point method (sebastienlato/cube-solver), sampling the middle of each sticker.</li>
<li><b>Colours:</b> your app's centre rebalance, with rubiks-color-resolver as fallback; during tracking, re-calibrate from the previous frame.</li>
<li><b>Move tracking:</b> compare against every predicted move (as tested above); wait when unsure, rescan only when lost.</li></ol>
<div class="caveat"><b>Important limits.</b> Almost all images are synthetic (rendered cubes with realistic lighting, glare, fingers and blur), so real-world numbers will be lower. This matters most for YOLO: it was trained and tested on synthetic frames, so it must be retrained or fine-tuned on a few hundred real photos of your cube before it can be trusted. The only real photos were dwalton76's 6 photos of one cube, held still by a robot. Tracking was tested on single before/after frames; the real app will also average several steady frames, which should help.</div>
</section>
</main></body></html>'''
open('reports_out/benchmark_report_v1.html', 'w').write(page)
print('report written')
