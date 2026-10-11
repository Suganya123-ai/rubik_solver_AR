"""7-day build plan (laptop version + XREAL glasses connection) -> reports_out/seven_day_plan.html."""
from pipe_helpers import ACCENT, ARROW_DEFS, C, FRONT, INK, LINE, MUTED, RIGHT, TOP, arrow, box, iso_cube

GREEN, AMBER, RED, PURPLE, TEAL = '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0e9f6e'
DAYS = [
    (1, 'Foundations', 'Solver + colours', '#5b6472', True),
    (2, 'Live camera', 'YOLO on webcam', ACCENT, False),
    (3, 'Real photos', 'Retrain YOLO', PURPLE, False),
    (4, '2-view scan', 'Auto capture', TEAL, False),
    (5, 'Move tracking', 'Check every move', AMBER, False),
    (6, 'Glasses', 'Eye → glasses', '#db2777', False),
    (7, 'Test + demo', 'Fix, rehearse', GREEN, False),
]


def timeline():
    w, gap = 92, 6
    out = [f'<svg viewBox="0 0 700 120" width="100%">']
    for i, (d, name, sub, col, done) in enumerate(DAYS):
        x = i * (w + gap) + 4
        out.append(f'<rect x="{x}" y="8" width="{w}" height="100" rx="12" fill="{col}" opacity="{0.55 if done else 1}"/>'
                   f'<text x="{x + w / 2}" y="34" text-anchor="middle" font-size="11" font-weight="700" fill="#fff" opacity=".85">DAY {d}</text>'
                   f'<text x="{x + w / 2}" y="60" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{name}</text>'
                   f'<text x="{x + w / 2}" y="80" text-anchor="middle" font-size="9.5" fill="#fff" opacity=".9">{sub}</text>'
                   + (f'<text x="{x + w / 2}" y="98" text-anchor="middle" font-size="10" font-weight="800" fill="#fff">✓ DONE</text>' if done else ''))
    return ''.join(out) + '</svg>'


system = f'''<svg viewBox="0 0 700 250" width="100%">{ARROW_DEFS}
<text x="10" y="18" font-size="11.5" font-weight="800" fill="{ACCENT}" letter-spacing="1">LAPTOP VERSION (DAYS 1–5)</text>
{box(10, 30, 130, 46, 'Laptop webcam', 'sees the cube')}
{arrow(142, 53, 196, 53, True, 'frames', 169, 46)}
{box(200, 22, 300, 62, 'Python server on the laptop', 'YOLO → 27 stickers → colours → tracker → kociemba', fill='#eaf7ee', stroke='#9ad5ae')}
{arrow(502, 53, 556, 53, True, 'moves', 529, 46)}
{box(560, 30, 130, 46, 'Browser', 'live view + guide')}
<text x="10" y="128" font-size="11.5" font-weight="800" fill="#db2777" letter-spacing="1">GLASSES VERSION (DAY 6) · SAME SERVER</text>
{box(10, 140, 130, 46, 'XREAL Eye', 'camera on the glasses', fill='#fdf2f8', stroke='#f5b6d3')}
{arrow(142, 163, 182, 163)}
{box(186, 132, 150, 62, 'Beam Pro', 'Unity C# app · XREAL SDK 3.x', fill='#fdf2f8', stroke='#f5b6d3')}
<path d="M338,150 C380,150 360,84 400,86" fill="none" stroke="{ACCENT}" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#ahA)"/>
<text x="372" y="128" font-size="10.5" fill="{ACCENT}" font-weight="700">Wi-Fi: frames</text>
<path d="M430,86 C470,120 420,178 338,178" fill="none" stroke="{ACCENT}" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#ahA)"/>
<text x="436" y="160" font-size="10.5" fill="{ACCENT}" font-weight="700">moves + status</text>
{arrow(261, 196, 261, 214)}
{box(186, 216, 150, 30, 'XREAL One Pro display', '', fill='#fdf2f8', stroke='#f5b6d3')}
<text x="520" y="200" font-size="10.5" fill="{MUTED}">The glasses only capture and display.</text>
<text x="520" y="216" font-size="10.5" fill="{MUTED}">All the logic stays on the laptop,</text>
<text x="520" y="232" font-size="10.5" fill="{MUTED}">so nothing is built twice.</text>
</svg>'''


def card(day, title, col, goal, build, done, who, note=''):
    items = ''.join(f'<li>{b}</li>' for b in build)
    return (f'<div class="card"><div class="ch" style="background:{col}"><span>Day {day}</span>{title}</div>'
            f'<div class="cb"><p class="goal"><b>Goal:</b> {goal}</p><ul>{items}</ul>'
            f'<p class="done">✅ <b>Done when:</b> {done}</p><p class="who"><b>Who:</b> {who}</p>'
            + (f'<p class="cnote">{note}</p>' if note else '') + '</div></div>')


d1 = card(1, 'Foundations · DONE', '#5b6472', 'A fast, reliable solver and colour reading.',
          ['Solver switched to <b>kociemba</b>: ~21 moves instead of ~110, in milliseconds',
           'Colour fallback added: centre rebalance, then <b>rubiks-color-resolver</b>',
           'Test harness, results and trained YOLO model moved into the repo (<code>bench/</code>, <code>models/</code>)'],
          'Solutions ≤ 22 moves · all 43 tests pass', 'Done')
d2 = card(2, 'Live camera', ACCENT, 'See YOLO find the real cube live on the laptop.',
          ['Webcam frames stream to the server (WebSocket <code>/ws/live</code>, ~10 per second)',
           'YOLO finds the 7 corner points; the 27 sticker colours are read',
           'Live view draws the points and colours over the video',
           '<b>"Save frame"</b> button to collect real photos for Day 3'],
          'Points follow the real cube smoothly (≥ 10 frames per second)', 'Python + browser',
          '<b>Glasses track starts today:</b> Unity + XREAL SDK 3.x set up, Eye camera image showing on the Beam Pro.')
d3 = card(3, 'Teach YOLO the real cube', PURPLE, 'Make YOLO reliable on our real cube, not just computer-made images.',
          ['Record 300–500 frames: many angles, distances, lighting, hands; include some from <b>eye height</b> (how the Eye will see it)',
           'Labelling page: YOLO places the 7 points, a person fixes wrong ones',
           'Retrain YOLO on real + synthetic frames (~30 min), test on real frames it never saw'],
          'On real photos: cube found ≥ 98%, average point error &lt; 5% of the cube', 'Everyone records; Python person trains',
          '<b>Most important day.</b> Everything after depends on YOLO working on the real cube.')
d4 = card(4, 'Scan in 2 views', TEAL, 'Read the whole cube in two quick, automatic captures.',
          ['View 1: Top + Front + Right. Flip the cube. View 2: Bottom + Left + Back',
           'Each view is captured automatically when the picture is steady',
           'Colours named (rebalance + resolver), cube validated, solved',
           'Checks: same view twice · wrong flip · back to the starting position before solving'],
          'A real scrambled cube scans correctly ≥ 9 times out of 10', 'Python + browser')
d5 = card(5, 'Live move tracking', AMBER, 'Check every move the user makes and re-plan after mistakes.',
          ['Show the move → wait until the view is steady (~5 frames) → compare with every possible move',
           '<b>Correct:</b> ✓ next move · <b>Wrong:</b> "You did L instead of R" + new plan · <b>Unsure:</b> wait · <b>Lost 3 s:</b> rescan',
           'Guide screen: current move, progress, warnings'],
          'A full real solve with deliberate mistakes finishes and never names a wrong move', 'Python + browser')
d6 = card(6, 'Glasses connection', '#db2777', 'Use the same system through the XREAL glasses.',
          ['Unity app on the Beam Pro sends Eye camera frames over Wi-Fi to the laptop server',
           'Receives the move and status back and shows them in the glasses',
           'Same server and logic as the laptop version, so nothing is rebuilt'],
          'You see live move instructions in the glasses while solving', 'Unity/C# + Python',
          'See page 4 for exactly how the connection works.')
d7 = card(7, 'Test, fix, demo', GREEN, 'A demo that works start to finish.',
          ['Test 5 scrambles × 3 lighting setups, on the laptop and in the glasses',
           'Fix bugs; save failed frames as future training data',
           'Rehearse the demo in the room where it will be shown'],
          'The demo runs from scan to solved cube with no problems', 'Everyone')

glasses_chain = f'''<svg viewBox="0 0 700 150" width="100%">{ARROW_DEFS}
{box(4, 40, 116, 56, 'XREAL Eye', 'RGB camera add-on', fill='#fdf2f8', stroke='#f5b6d3')}
{arrow(122, 68, 140, 68)}
{box(144, 40, 116, 56, 'One Pro glasses', 'USB-C to Beam Pro', fill='#fdf2f8', stroke='#f5b6d3')}
{arrow(262, 68, 280, 68)}
{box(284, 26, 170, 84, 'Beam Pro (Android 14)', 'Unity app, XREAL SDK 3.x', fill='#fdf2f8', stroke='#f5b6d3')}
<text x="369" y="96" text-anchor="middle" font-size="10" fill="{MUTED}">camera in · display out</text>
<path d="M456,56 L560,56" stroke="{ACCENT}" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#ahA)"/>
<path d="M560,84 L458,84" stroke="{ACCENT}" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#ahA)"/>
<text x="508" y="48" text-anchor="middle" font-size="10.5" font-weight="700" fill="{ACCENT}">JPEG frames</text>
<text x="508" y="102" text-anchor="middle" font-size="10.5" font-weight="700" fill="{ACCENT}">JSON: move + status</text>
<text x="508" y="128" text-anchor="middle" font-size="10" fill="{MUTED}">same Wi-Fi network</text>
{box(564, 30, 132, 76, 'Laptop server', 'Python · port 8000', fill='#eaf7ee', stroke='#9ad5ae')}
</svg>'''

steps = [
    ('Set up Unity', 'Unity version supported by XREAL SDK 3.x, with Android build support. Import XREAL SDK 3.x and enable XREAL in XR settings. Build a sample scene to the Beam Pro to confirm the toolchain works.', 'Day 2'),
    ('Read the Eye camera', 'Use <code>XREALRGBCameraTexture</code>. Frames arrive as YUV_420_888 (three textures: Y, U, V); convert to an RGB image.', 'Day 2'),
    ('Send frames to the laptop', 'Resize to 640×480, JPEG-encode (quality ~80), send over a WebSocket to <code>ws://&lt;laptop-IP&gt;:8000/ws/live</code>. Send the next frame only after the reply arrives, so frames never pile up.', 'Day 3'),
    ('Collect Eye training photos', 'Use the same link with the laptop\'s "Save frame" feature to save real frames from the Eye\'s point of view for YOLO retraining.', 'Day 3–4'),
    ('Show the guide in the glasses', 'Read the JSON reply (current move, status, message) and show it on a panel in front of the user: move notation, a short description, ✓ / wrong-move warnings, progress.', 'Day 4–6'),
    ('Reuse the Unity scaffold', 'Our <code>xreal_ar/</code> project already has the C# cube model and a camera interface (<code>ICubeCameraSource</code>); its camera class targets the old NRSDK and must move to SDK 3.x.', 'Day 2'),
]
steps_html = ''.join(f'<tr><td class="num"><span>{i + 1}</span></td><td><b>{t}</b><br>{d}</td><td class="when">{w}</td></tr>' for i, (t, d, w) in enumerate(steps))

lanes = f'''<svg viewBox="0 0 700 120" width="100%">
<text x="0" y="40" font-size="11.5" font-weight="700" fill="{INK}">Python / browser</text>
<text x="0" y="90" font-size="11.5" font-weight="700" fill="{INK}">Unity / glasses</text>
{''.join(f'<text x="{150 + i * 78.5 + 39}" y="12" text-anchor="middle" font-size="10" fill="{MUTED}">Day {i + 1}</text>' for i in range(7))}
{''.join(f'<rect x="{150 + x * 78.5 + 2}" y="{y}" width="{w * 78.5 - 4}" height="30" rx="7" fill="{c}"/><text x="{150 + x * 78.5 + w * 78.5 / 2}" y="{y + 19}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">{t}</text>'
         for x, y, w, c, t in [
             (0, 22, 1, '#5b6472', 'Foundations ✓'), (1, 22, 1, ACCENT, 'Live camera'), (2, 22, 1, PURPLE, 'Retrain YOLO'),
             (3, 22, 1, TEAL, '2-view scan'), (4, 22, 1, AMBER, 'Tracking'), (5, 22, 1, '#db2777', 'Connect'), (6, 22, 1, GREEN, 'Test + demo'),
             (1, 72, 1, '#db2777', 'Eye feed'), (2, 72, 2, '#db2777', 'Frames → laptop · Eye photos'),
             (4, 72, 1, '#db2777', 'Guide UI'), (5, 72, 1, '#db2777', 'Connect'), (6, 72, 1, GREEN, 'Test + demo')])}
</svg>'''

css = f'''@page {{ size: Letter; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: {INK}; background: #fff; }}
.page {{ width: 8.5in; height: 11in; padding: 0.55in 0.6in; page-break-after: always; position: relative; overflow: hidden; }}
.page:last-child {{ page-break-after: auto; }}
.kicker {{ font-size: 10.5px; letter-spacing: 2px; text-transform: uppercase; color: {ACCENT}; font-weight: 800; margin-bottom: 4px; }}
h1 {{ font-size: 30px; margin: 0 0 8px; letter-spacing: -.5px; }} h2 {{ font-size: 21px; margin: 0 0 6px; }} h3 {{ font-size: 13.5px; margin: 14px 0 6px; }}
p {{ font-size: 11.8px; line-height: 1.5; margin: 6px 0; }} .lead {{ font-size: 13px; color: {MUTED}; }}
.stripe {{ display: flex; height: 7px; border-radius: 4px; overflow: hidden; margin: 0 0 12px; width: 170px; }} .stripe div {{ flex: 1; }}
.callout {{ background: #f3f6ff; border-left: 4px solid {ACCENT}; border-radius: 8px; padding: 9px 13px; margin: 10px 0; font-size: 11.8px; line-height: 1.5; }}
.callout.warn {{ background: #fff8ec; border-left-color: #f59e0b; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.scope {{ border: 1px solid {LINE}; border-radius: 10px; padding: 10px 14px; }} .scope h3 {{ margin-top: 0; }}
ul {{ margin: 4px 0; padding-left: 18px; }} li {{ font-size: 11.3px; line-height: 1.45; margin: 3px 0; }}
.card {{ border: 1px solid {LINE}; border-radius: 12px; overflow: hidden; margin-bottom: 11px; }}
.ch {{ color: #fff; font-weight: 800; font-size: 14px; padding: 7px 14px; }} .ch span {{ font-size: 10.5px; opacity: .85; margin-right: 10px; letter-spacing: 1px; text-transform: uppercase; }}
.cb {{ padding: 8px 14px 10px; }} .cb p {{ margin: 4px 0; font-size: 11.3px; }} .goal {{ color: {INK}; }}
.done {{ background: #eaf7ee; border-radius: 6px; padding: 5px 9px; }} .who {{ color: {MUTED}; }} .cnote {{ color: #b45309; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
th {{ text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: .8px; color: {MUTED}; padding: 5px 7px; border-bottom: 2px solid {INK}; }}
td {{ font-size: 11px; padding: 6px 7px; border-bottom: 1px solid #eef0f3; vertical-align: top; line-height: 1.45; }}
td.num span {{ display: inline-flex; width: 22px; height: 22px; border-radius: 50%; background: #db2777; color: #fff; font-weight: 800; font-size: 11px; align-items: center; justify-content: center; }}
td.when {{ white-space: nowrap; color: {MUTED}; font-weight: 700; }}
code {{ font-family: Menlo, monospace; font-size: 10px; background: #f3f4f6; padding: 0 3px; border-radius: 3px; }}
.foot {{ position: absolute; bottom: 0.35in; left: 0.6in; right: 0.6in; font-size: 9.5px; color: #9aa3b2; display: flex; justify-content: space-between; }}
'''
foot = lambda n: f'<div class="foot"><span>Live Rubik\'s Cube Solver · 7-day build plan</span><span>{n} / 5</span></div>'
stripe = ''.join(f'<div style="background:{C[k]}{";border:1px solid " + LINE if k == "W" else ""}"></div>' for k in 'WYROGB')

p1 = f'''<section class="page"><div class="kicker">Rubik's Cube Solver · Build plan</div>
<h1>7-Day Build Plan</h1><div class="stripe">{stripe}</div>
<p class="lead">In 7 days we build a camera-guided Rubik's Cube solver that checks every move the user makes, re-plans after mistakes, and works both on a laptop and through our XREAL One Pro glasses with the Eye camera.</p>
{timeline()}
<div class="two" style="margin-top:8px">
<div class="scope"><h3>✅ Done by Day 7</h3><ul>
<li>Laptop version: webcam, automatic 2-view scan, ~21-move solution, live move checking with re-planning</li>
<li>YOLO retrained on real photos of our cube</li>
<li>Glasses version: Eye camera → Beam Pro → laptop server → instructions shown in the glasses</li>
<li>Tested in 3 lighting setups, demo rehearsed</li></ul></div>
<div class="scope"><h3>⏭ After Day 7</h3><ul>
<li>Running everything on the Beam Pro alone (no laptop): YOLO and logic ported to C#</li>
<li>Turn arrows drawn on the real cube</li>
<li>Licence decision before any release (kociemba GPL, YOLO AGPL)</li></ul></div></div>
<h3>How the system fits together</h3>{system}
{foot(1)}</section>'''

p2 = f'''<section class="page"><div class="kicker">Days 1–4</div><h2>Build the laptop version</h2>
{d1}{d2}{d3}{d4}{foot(2)}</section>'''

p3 = f'''<section class="page"><div class="kicker">Days 5–7</div><h2>Tracking, glasses, demo</h2>
{d5}{d6}{d7}
<div class="callout"><b>Every day ends the same way:</b> run the tests, try it with the real cube, and show the team a short demo of what changed. If something isn't working by mid-day, say so early.</div>
{foot(3)}</section>'''

p4 = f'''<section class="page"><div class="kicker">XREAL glasses connection</div><h2>How the glasses connect</h2>
<p class="lead">The glasses act as a camera and a screen. The Eye camera's frames travel to the laptop over Wi-Fi; the laptop sends back what to show. The laptop version and the glasses version share one server.</p>
{glasses_chain}
<h3>Build steps</h3>
<table><thead><tr><th></th><th>Step</th><th>When</th></tr></thead><tbody>{steps_html}</tbody></table>
<h3>Requirements</h3><ul>
<li><b>Same Wi-Fi:</b> laptop and Beam Pro on the same network; the server listens on all interfaces (<code>--host 0.0.0.0</code>) and the laptop firewall allows port 8000.</li>
<li><b>Speed:</b> aim for ≥ 10 frames per second round trip. If Wi-Fi is slow, lower the JPEG quality or the frame size.</li>
<li><b>The view changes:</b> the Eye sees the cube from the wearer's eyes, closer and from above, which is why Day 3 includes eye-height photos and Eye frames for training.</li>
<li><b>Device:</b> XREAL warns against upgrading development devices to Android 16; keep the Beam Pro on its current version.</li></ul>
{foot(4)}</section>'''

p5 = f'''<section class="page"><div class="kicker">Team and risks</div><h2>Who does what, and what could go wrong</h2>
<h3>Two tracks in parallel</h3>{lanes}
<p>The Unity/glasses track starts on <b>Day 2</b>, not Day 6, so connecting the glasses is assembly, not a fresh start.</p>
<div class="two"><div><h3>If a day runs late, cut these first</h3><ol style="padding-left:18px;margin:4px 0">
<li style="font-size:11.3px">Turn arrows drawn on the cube (text instructions are enough)</li>
<li style="font-size:11.3px">Polish of the labelling page</li>
<li style="font-size:11.3px">Hard-lighting tuning (demo in normal room light)</li></ol>
<p><b>Never cut Day 3.</b> Real photos for YOLO decide whether everything else works.</p></div>
<div><h3>Biggest risks</h3>
<table><tbody>
<tr><td><b>YOLO on real video</b></td><td>Only tested on computer-made images so far. Fix: collect frames where it fails, retrain.</td></tr>
<tr><td><b>XREAL setup</b></td><td>New SDK, device and Android builds. Fix: start Day 2, test the Eye feed first.</td></tr>
<tr><td><b>Wi-Fi speed</b></td><td>Slow network = laggy glasses. Fix: smaller frames, lower JPEG quality.</td></tr>
<tr><td><b>Demo lighting</b></td><td>Fix: test in the demo room on Day 7.</td></tr></tbody></table></div></div>
<h3>Demo-day checklist</h3><ul>
<li>Laptop server running, YOLO model loaded, laptop and Beam Pro on the same Wi-Fi</li>
<li>Cube scrambled; scan both views; solve with one deliberate mistake to show the re-plan</li>
<li>Repeat in the glasses with the Eye camera</li>
<li>Backup: the laptop version alone if the network fails</li></ul>
<div class="callout warn"><b>Reference documents:</b> Implementation_Plan.pdf (architecture and rules), Benchmark_Report.pdf (why each tool was chosen), Team_Summary.pdf (short version).</div>
{foot(5)}</section>'''

html = f'<!doctype html><html><head><meta charset="utf-8"><title>7-Day Build Plan</title><style>{css}</style></head><body>{p1}{p2}{p3}{p4}{p5}</body></html>'
open('reports_out/seven_day_plan.html', 'w').write(html)
print('ok')
