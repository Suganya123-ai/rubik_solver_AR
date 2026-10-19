"""Generates pipeline.html (diagrams as inline SVG); Chrome prints it to PDF."""
import math

C = {'W': '#f4f4f2', 'Y': '#ffd21f', 'R': '#d42a2a', 'O': '#ff7a1a', 'G': '#16a34a', 'B': '#1d4ed8'}
INK, MUTED, LINE, ACCENT = '#1b1f27', '#5b6472', '#d5d9e0', '#3a6ff7'


def iso_cube(cx, cy, s, top, front, right, highlight=None, stroke='#1b1f27'):
    """Isometric cube showing Top, Front (left) and Right faces; each face is
    9 color letters in raster order as seen on that face."""
    c = math.cos(math.radians(30))
    faces = {
        'top': ((cx, cy - s), (s * c / 3, s / 6), (-s * c / 3, s / 6), top),
        'front': ((cx - s * c, cy - s / 2), (s * c / 3, s / 6), (0, s / 3), front),
        'right': ((cx, cy), (s * c / 3, -s / 6), (0, s / 3), right),
    }
    out = [f'<polygon points="{cx},{cy - s} {cx + s * c},{cy - s / 2} {cx + s * c},{cy + s / 2} '
           f'{cx},{cy + s} {cx - s * c},{cy + s / 2} {cx - s * c},{cy - s / 2}" fill="{stroke}"/>']
    g = 0.09
    for name, (o, u, v, cols) in faces.items():
        for k, col in enumerate(cols):
            row, colm = divmod(k, 3)
            # top: rows go down-left (v), cols go right (u)
            i, j = (colm, row)
            pts = []
            for a, b in ((i + g, j + g), (i + 1 - g, j + g), (i + 1 - g, j + 1 - g), (i + g, j + 1 - g)):
                pts.append(f'{o[0] + a * u[0] + b * v[0]:.1f},{o[1] + a * u[1] + b * v[1]:.1f}')
            hl = highlight and name in highlight and k in highlight[name]
            sw = f' stroke="{ACCENT}" stroke-width="2.5"' if hl else ''
            out.append(f'<polygon points="{" ".join(pts)}" fill="{C[col]}"{sw} rx="2"/>')
    return '\n'.join(out)


def face_grid(x, y, size, cols, label=None, dashed=False):
    cell = size / 3
    out = [f'<rect x="{x - 3}" y="{y - 3}" width="{size + 6}" height="{size + 6}" rx="6" '
           f'fill="{"none" if dashed else INK}" stroke="{LINE if dashed else INK}" '
           f'{"stroke-dasharray=\"4 3\"" if dashed else ""}/>']
    if not dashed:
        for k, col in enumerate(cols):
            r, cc = divmod(k, 3)
            out.append(f'<rect x="{x + cc * cell + 1.5:.1f}" y="{y + r * cell + 1.5:.1f}" '
                       f'width="{cell - 3:.1f}" height="{cell - 3:.1f}" rx="2.5" fill="{C[col]}"/>')
    if label:
        out.append(f'<text x="{x + size / 2}" y="{y + size + 18}" text-anchor="middle" '
                   f'font-size="11" fill="{MUTED}">{label}</text>')
    return '\n'.join(out)


import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from cube.cube_state import FACE_OFFSET, solved_state
from cube.moves import ALL_MOVES, apply_move, apply_moves

LETTER_COLOR = {'U': 'W', 'D': 'Y', 'F': 'G', 'B': 'B', 'L': 'O', 'R': 'R'}
_rng = random.Random(11)
STATE = apply_moves(solved_state(), [_rng.choice(ALL_MOVES) for _ in range(25)])


def faces_of(state, *faces):
    return [''.join(LETTER_COLOR[x] for x in state.arr[FACE_OFFSET[f]:FACE_OFFSET[f] + 9]) for f in faces]


TOP, FRONT, RIGHT = faces_of(STATE, 'U', 'F', 'R')
OTHER = faces_of(STATE, 'D', 'L', 'B')

ARROW_DEFS = f'''<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>
<marker id="ahA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker></defs>'''


def box(x, y, w, h, title, sub='', fill='#ffffff', stroke=LINE, tcol=INK):
    t = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
         f'<text x="{x + w / 2}" y="{y + (h / 2 if not sub else h / 2 - 6)}" text-anchor="middle" '
         f'dominant-baseline="middle" font-size="13" font-weight="700" fill="{tcol}">{title}</text>')
    if sub:
        t += (f'<text x="{x + w / 2}" y="{y + h / 2 + 11}" text-anchor="middle" dominant-baseline="middle" '
              f'font-size="10.5" fill="{MUTED}">{sub}</text>')
    return t


def arrow(x1, y1, x2, y2, accent=False, label=None, lx=None, ly=None):
    col = ACCENT if accent else MUTED
    t = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="1.8" '
         f'marker-end="url(#{"ahA" if accent else "ah"})"/>')
    if label:
        t += (f'<text x="{lx if lx is not None else (x1 + x2) / 2}" y="{ly if ly is not None else (y1 + y2) / 2 - 6}" '
              f'text-anchor="middle" font-size="10.5" fill="{col}" font-weight="600">{label}</text>')
    return t


# ---------- Page 1: big picture ----------
overview = f'''<svg viewBox="0 0 700 300" width="100%">{ARROW_DEFS}
<rect x="10" y="20" width="250" height="260" rx="14" fill="#f3f6ff" stroke="#c9d6ff"/>
<text x="135" y="44" text-anchor="middle" font-size="12" font-weight="800" fill="{ACCENT}" letter-spacing="1">PHASE A · SCAN ONCE</text>
{face_grid(36, 66, 44, TOP)}{face_grid(92, 66, 44, FRONT)}{face_grid(148, 66, 44, RIGHT)}
{face_grid(36, 122, 44, OTHER[0])}{face_grid(92, 122, 44, OTHER[1])}{face_grid(148, 122, 44, OTHER[2])}
<text x="225" y="122" font-size="22" font-weight="800" fill="{INK}">×6</text>
{box(30, 190, 210, 34, 'Validate the cube', 'is this state physically possible?')}
{box(30, 234, 210, 34, 'Solve (kociemba)', '≈20 moves, milliseconds', fill='#eaf7ee', stroke='#9ad5ae')}
{arrow(270, 150, 318, 150, True, 'moves', 294, 140)}
<rect x="325" y="20" width="365" height="260" rx="14" fill="#fff8ec" stroke="#f3d29a"/>
<text x="507" y="44" text-anchor="middle" font-size="12" font-weight="800" fill="#b86e00" letter-spacing="1">PHASE B · SOLVE WITH LIVE TRACKING</text>
{iso_cube(400, 150, 58, TOP, FRONT, RIGHT)}
<text x="400" y="230" text-anchor="middle" font-size="10.5" fill="{MUTED}">camera sees</text>
<text x="400" y="244" text-anchor="middle" font-size="10.5" fill="{MUTED}">Top + Front + Right</text>
{box(475, 66, 200, 34, 'Show next move', '"R — turn right side up"')}
{box(475, 116, 200, 34, 'Watch the 27 stickers', 'wait until the view is steady')}
{box(475, 166, 200, 34, 'Compare to predictions', 'right move? wrong move? none?')}
{box(475, 216, 200, 34, 'React', '✓ next · re-plan · rescan only if lost', fill='#eaf7ee', stroke='#9ad5ae')}
{arrow(575, 100, 575, 114)}{arrow(575, 150, 575, 164)}{arrow(575, 200, 575, 214)}
<path d="M675,233 C688,233 688,83 677,83" fill="none" stroke="{ACCENT}" stroke-width="1.8" marker-end="url(#ahA)"/>
<text x="575" y="268" font-size="10.5" fill="{ACCENT}" font-weight="700" text-anchor="middle">↻ repeat until solved</text>
</svg>'''

# ---------- Page 2: phase A steps ----------
scan_steps = f'''<svg viewBox="0 0 700 190" width="100%">{ARROW_DEFS}
<rect x="10" y="20" width="140" height="140" rx="12" fill="{INK}"/>
<text x="80" y="38" text-anchor="middle" font-size="10" fill="#9aa3b2">live camera</text>
<g transform="rotate(-8 80 95)">{face_grid(45, 60, 70, FRONT)}</g>
<text x="80" y="180" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">1 · Camera frame</text>
{arrow(158, 90, 192, 90)}
<rect x="200" y="20" width="140" height="140" rx="12" fill="{INK}"/>
<g transform="rotate(-8 270 95)">{face_grid(235, 60, 70, FRONT)}
<rect x="230" y="55" width="80" height="80" fill="none" stroke="#3ecf8e" stroke-width="2.5" rx="4"/></g>
<text x="270" y="180" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">2 · Find 9 stickers</text>
{arrow(348, 90, 382, 90)}
{face_grid(400, 50, 80, FRONT)}
<text x="440" y="180" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">3 · Straighten + read</text>
{arrow(498, 90, 532, 90)}
<circle cx="610" cy="90" r="52" fill="#eaf7ee" stroke="#9ad5ae" stroke-width="2"/>
<path d="M588,90 l15,15 l30,-32" fill="none" stroke="#16a34a" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
<text x="610" y="180" text-anchor="middle" font-size="11.5" font-weight="700" fill="{INK}">4 · Steady ½ s → captured</text>
</svg>'''

# ---------- Page 3: phase B decision flow ----------
flow = f'''<svg viewBox="0 0 700 430" width="100%">{ARROW_DEFS}
{box(225, 10, 250, 44, 'Read the 3 visible sides', 'every frame, ~10 per second')}
{arrow(350, 54, 350, 78)}
{box(225, 80, 250, 44, 'Same reading for ~5 frames?', 'ignores hands and half-done turns')}
{arrow(475, 102, 560, 102, False, 'no', 517, 94)}
<rect x="562" y="84" width="128" height="36" rx="10" fill="#f6f7f9" stroke="{LINE}"/>
<text x="626" y="106" text-anchor="middle" font-size="11" fill="{MUTED}">keep watching</text>
{arrow(350, 124, 350, 150, False, 'yes', 365, 142)}
<polygon points="350,152 470,197 350,242 230,197" fill="#f3f6ff" stroke="#c9d6ff" stroke-width="1.5"/>
<text x="350" y="193" text-anchor="middle" font-size="12.5" font-weight="700" fill="{INK}">Which prediction</text>
<text x="350" y="209" text-anchor="middle" font-size="12.5" font-weight="700" fill="{INK}">matches best?</text>
{arrow(300, 230, 95, 290)}{arrow(330, 240, 270, 290)}{arrow(370, 240, 435, 290)}{arrow(400, 230, 610, 290)}
<rect x="15" y="292" width="160" height="128" rx="12" fill="#eaf7ee" stroke="#9ad5ae"/>
<text x="95" y="314" text-anchor="middle" font-size="12.5" font-weight="800" fill="#15803d">Expected move</text>
<text x="95" y="340" text-anchor="middle" font-size="11" fill="{INK}">✓ Correct!</text>
<text x="95" y="358" text-anchor="middle" font-size="11" fill="{INK}">Show the next move</text>
<rect x="190" y="292" width="160" height="128" rx="12" fill="#f6f7f9" stroke="{LINE}"/>
<text x="270" y="314" text-anchor="middle" font-size="12.5" font-weight="800" fill="{MUTED}">No change</text>
<text x="270" y="340" text-anchor="middle" font-size="11" fill="{INK}">Move not done yet</text>
<text x="270" y="358" text-anchor="middle" font-size="11" fill="{INK}">Keep watching</text>
<rect x="365" y="292" width="160" height="128" rx="12" fill="#fff4e5" stroke="#f3c27a"/>
<text x="445" y="314" text-anchor="middle" font-size="12.5" font-weight="800" fill="#b45309">A different move</text>
<text x="445" y="336" text-anchor="middle" font-size="11" fill="{INK}">"You did L, not R"</text>
<text x="445" y="354" text-anchor="middle" font-size="11" fill="{INK}">Update cube state</text>
<text x="445" y="372" text-anchor="middle" font-size="11" fill="{INK}">Re-solve (ms)</text>
<text x="445" y="390" text-anchor="middle" font-size="11" fill="{INK}">Show new next move</text>
<rect x="540" y="292" width="150" height="128" rx="12" fill="#fdecec" stroke="#f1a3a3"/>
<text x="615" y="314" text-anchor="middle" font-size="12.5" font-weight="800" fill="#b91c1c">Lost track</text>
<text x="615" y="334" text-anchor="middle" font-size="11" fill="{INK}">No prediction fits,</text>
<text x="615" y="350" text-anchor="middle" font-size="11" fill="{INK}">or readings keep</text>
<text x="615" y="366" text-anchor="middle" font-size="11" fill="{INK}">jumping around</text>
<text x="615" y="388" text-anchor="middle" font-size="11" font-weight="700" fill="{INK}">Only now: rescan</text>
<text x="615" y="404" text-anchor="middle" font-size="10" fill="{MUTED}">(rare fallback)</text>
</svg>'''

# Predictions illustration: current + candidate outcomes
def mini_iso(cx, cy, top, front, right, label, good=None):
    border = {'good': '#16a34a', 'bad': '#d97706', None: LINE}[good]
    return (f'<rect x="{cx - 52}" y="{cy - 58}" width="104" height="128" rx="10" fill="#fff" stroke="{border}" stroke-width="{2 if good else 1.2}"/>'
            + iso_cube(cx, cy, 36, top, front, right)
            + f'<text x="{cx}" y="{cy + 60}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{INK}">{label}</text>')


predictions = f'''<svg viewBox="0 0 700 150" width="100%">
{mini_iso(60, 68, TOP, FRONT, RIGHT, 'Now')}
<text x="128" y="72" font-size="20" fill="{MUTED}">→</text>
{mini_iso(205, 68, *faces_of(apply_move(STATE, 'R'), 'U', 'F', 'R'), 'R (expected)', 'good')}
{mini_iso(325, 68, TOP, FRONT, RIGHT, 'no change')}
{mini_iso(445, 68, *faces_of(apply_move(STATE, 'L'), 'U', 'F', 'R'), "L (wrong)", 'bad')}
{mini_iso(565, 68, *faces_of(apply_move(STATE, 'U'), 'U', 'F', 'R'), "U (wrong)", 'bad')}
<text x="628" y="62" font-size="11" fill="{MUTED}">…all 18</text>
<text x="628" y="78" font-size="11" fill="{MUTED}">moves and</text>
<text x="628" y="94" font-size="11" fill="{MUTED}">324 pairs</text>
</svg>'''

# ---------- Page 4: why 3 sides ----------
def bar(y, label, pct1, pct2, note):
    w = 330
    return (f'<text x="0" y="{y + 14}" font-size="12" font-weight="700" fill="{INK}">{label}</text>'
            f'<rect x="170" y="{y}" width="{w}" height="18" rx="4" fill="#eef0f3"/>'
            f'<rect x="170" y="{y}" width="{max(w * pct1, 3)}" height="18" rx="4" fill="{"#d42a2a" if pct1 > 0.5 else ("#f59e0b" if pct1 > 0 else "#16a34a")}"/>'
            f'<text x="{170 + w + 10}" y="{y + 14}" font-size="11.5" fill="{INK}">{pct1 * 100:.0f}% · 1 move</text>'
            f'<rect x="170" y="{y + 22}" width="{w}" height="18" rx="4" fill="#eef0f3"/>'
            f'<rect x="170" y="{y + 22}" width="{max(w * pct2, 3)}" height="18" rx="4" fill="{"#d42a2a" if pct2 > 0.5 else ("#f59e0b" if pct2 > 0 else "#16a34a")}"/>'
            f'<text x="{170 + w + 10}" y="{y + 36}" font-size="11.5" fill="{INK}">{pct2 * 100:.0f}% · 2 moves</text>'
            f'<text x="0" y="{y + 34}" font-size="10.5" fill="{MUTED}">{note}</text>')


bars = f'''<svg viewBox="0 0 640 170" width="100%">
<text x="170" y="10" font-size="10.5" fill="{MUTED}">share of 300 random cubes where the move CAN'T be identified (lower is better)</text>
{bar(22, 'Front only', 1.0, 1.0, 'back turns invisible')}
{bar(72, 'Top + Front', 13 / 300, 154 / 300, 'often confused')}
{bar(122, 'Top + Front + Right', 0, 0, 'always identified ✓')}
</svg>'''

hold = f'''<svg viewBox="0 0 300 230" width="100%">
<rect x="0" y="0" width="300" height="230" rx="14" fill="#f6f7f9"/>
<circle cx="250" cy="40" r="20" fill="{INK}"/><circle cx="250" cy="40" r="9" fill="#5b6472"/>
<text x="250" y="76" text-anchor="middle" font-size="10" fill="{MUTED}">camera</text>
{iso_cube(120, 120, 70, TOP, FRONT, RIGHT)}
<text x="120" y="38" text-anchor="middle" font-size="11" font-weight="700" fill="{INK}">TOP</text>
<text x="48" y="190" text-anchor="middle" font-size="11" font-weight="700" fill="{INK}">FRONT</text>
<text x="192" y="190" text-anchor="middle" font-size="11" font-weight="700" fill="{INK}">RIGHT</text>
<line x1="232" y1="55" x2="175" y2="98" stroke="{ACCENT}" stroke-width="1.8" stroke-dasharray="5 4"/>
</svg>'''

# ---------- Page 5: architecture ----------
arch = f'''<svg viewBox="0 0 700 250" width="100%">{ARROW_DEFS}
<rect x="10" y="10" width="220" height="230" rx="14" fill="#f3f6ff" stroke="#c9d6ff"/>
<text x="120" y="34" text-anchor="middle" font-size="12" font-weight="800" fill="{ACCENT}" letter-spacing="1">BROWSER (your page)</text>
{box(30, 50, 180, 40, 'Camera', 'getUserMedia')}
{box(30, 105, 180, 40, 'Live view + overlay', 'move, arrows, ✓ / warnings')}
{box(30, 160, 180, 40, 'Captured sides panel', 'what you have now')}
{arrow(240, 80, 448, 80, True, 'video frames (~10/s)', 345, 70)}
{arrow(448, 135, 240, 135, True, 'what it sees + what to do', 345, 152)}
<text x="345" y="110" text-anchor="middle" font-size="11" font-weight="700" fill="{INK}">WebSocket</text>
<rect x="455" y="10" width="235" height="230" rx="14" fill="#eaf7ee" stroke="#9ad5ae"/>
<text x="572" y="34" text-anchor="middle" font-size="12" font-weight="800" fill="#15803d" letter-spacing="1">PYTHON SERVER</text>
{box(470, 46, 205, 36, 'OpenCV sticker finder', 'later: YOLO')}
{box(470, 90, 205, 36, 'Color reader', 'matches the 6 centers')}
{box(470, 134, 205, 36, 'Move tracker', 'predict · compare · decide')}
{box(470, 178, 205, 50, 'Cube model + checks', 'existing cube/ code + kociemba')}
</svg>'''

roadmap_items = [
    ('1', 'Swap in the kociemba solver', '~20-move solutions; fast enough to re-plan instantly.', 'Small'),
    ('2', 'Live video + auto-capture scan', 'Phase A. No Capture button, no grid to line up.', 'Medium'),
    ('3', 'Read 3 sides from a tilted cube', 'Find the 27 stickers in the corner-on view.', 'Hardest'),
    ('4', 'Move tracking + re-plan + rescan fallback', 'Phase B: compare to predictions, re-solve after mistakes.', 'Medium'),
    ('5', 'YOLO cube detector (only if needed)', 'If OpenCV struggles with hands covering the cube.', 'Optional'),
]
roadmap = ''.join(
    f'<div class="rm"><div class="num">{n}</div><div class="rmb"><b>{t}</b><span>{d}</span></div>'
    f'<div class="tag tag-{e.lower()}">{e}</div></div>' for n, t, d, e in roadmap_items)

tools = [
    ('Camera + screen', 'Your current web page', 'Already works; nothing new to install for you.'),
    ('Sending frames', 'WebSocket (FastAPI)', 'A continuous fast stream instead of one request per photo.'),
    ('Finding stickers', 'OpenCV (Python)', 'Standard vision library: finds square shapes, straightens tilted sides.'),
    ('Reading colors', 'Your center-based matcher', 'Already handles lighting; tracking only compares to predictions.'),
    ('Cube model + checks', 'Your existing cube/ code', 'Already correct and tested — reused as is.'),
    ('Solving', 'kociemba', '~20 moves vs 60–150 today; re-plans in milliseconds.'),
    ('Finding the cube (later)', 'YOLO (Ultralytics)', 'Learns the cube\'s corners even with fingers on it.'),
]
tool_rows = ''.join(f'<tr><td><b>{a}</b></td><td class="tool">{b}</td><td>{c}</td></tr>' for a, b, c in tools)

html = f'''<!doctype html><html><head><meta charset="utf-8"><title>Live Cube Solver Pipeline</title>
<style>
@page {{ size: Letter; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: {INK}; background: #fff; }}
.page {{ width: 8.5in; height: 11in; padding: 0.6in 0.65in; page-break-after: always; position: relative; overflow: hidden; }}
.page:last-child {{ page-break-after: auto; }}
.kicker {{ font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: {ACCENT}; font-weight: 800; margin-bottom: 6px; }}
h1 {{ font-size: 34px; margin: 0 0 8px; letter-spacing: -0.5px; }}
h2 {{ font-size: 24px; margin: 0 0 6px; letter-spacing: -0.3px; }}
h3 {{ font-size: 15px; margin: 22px 0 8px; }}
p.lead {{ font-size: 14.5px; color: {MUTED}; line-height: 1.5; margin: 0 0 18px; }}
p, li {{ font-size: 12.5px; line-height: 1.55; }}
.stripe {{ display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 0 0 28px; width: 180px; }}
.stripe div {{ flex: 1; }}
.cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 18px; }}
.card {{ border: 1px solid {LINE}; border-radius: 12px; padding: 12px 14px; }}
.card b {{ display: block; font-size: 13px; margin-bottom: 4px; }}
.card span {{ font-size: 11.5px; color: {MUTED}; line-height: 1.45; }}
.steps {{ counter-reset: s; list-style: none; padding: 0; margin: 10px 0 0; }}
.steps li {{ counter-increment: s; position: relative; padding: 8px 0 8px 40px; border-bottom: 1px solid #eef0f3; }}
.steps li::before {{ content: counter(s); position: absolute; left: 0; top: 7px; width: 26px; height: 26px; border-radius: 50%;
  background: {ACCENT}; color: #fff; font-weight: 800; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
.callout {{ background: #f3f6ff; border-left: 4px solid {ACCENT}; border-radius: 8px; padding: 10px 14px; margin: 14px 0; font-size: 12.5px; line-height: 1.5; }}
.callout.warn {{ background: #fff8ec; border-left-color: #f59e0b; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
th {{ text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: {MUTED}; padding: 8px 10px; border-bottom: 2px solid {INK}; }}
td {{ font-size: 11.5px; padding: 6px 10px; border-bottom: 1px solid #eef0f3; vertical-align: top; line-height: 1.45; }}
td.tool {{ color: {ACCENT}; font-weight: 700; white-space: nowrap; }}
.two {{ display: grid; grid-template-columns: 1.05fr 1fr; gap: 22px; align-items: start; }}
.rm {{ display: flex; align-items: center; gap: 14px; border: 1px solid {LINE}; border-radius: 12px; padding: 7px 14px; margin-bottom: 7px; }}
.num {{ width: 30px; height: 30px; border-radius: 50%; background: {INK}; color: #fff; font-weight: 800; display: flex; align-items: center; justify-content: center; flex: none; }}
.rmb {{ flex: 1; }} .rmb b {{ display: block; font-size: 13px; }} .rmb span {{ font-size: 11.5px; color: {MUTED}; }}
.tag {{ font-size: 10.5px; font-weight: 800; padding: 3px 10px; border-radius: 999px; }}
.tag-small {{ background: #eaf7ee; color: #15803d; }} .tag-medium {{ background: #f3f6ff; color: {ACCENT}; }}
.tag-hardest {{ background: #fdecec; color: #b91c1c; }} .tag-optional {{ background: #f6f7f9; color: {MUTED}; }}
.rules {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
.rule {{ border-radius: 12px; padding: 12px 14px; background: #f6f7f9; font-size: 12px; line-height: 1.45; }}
.rule .ic {{ font-size: 20px; display: block; margin-bottom: 4px; }}
.foot {{ position: absolute; bottom: 0.4in; left: 0.65in; right: 0.65in; font-size: 10px; color: #9aa3b2; display: flex; justify-content: space-between; }}
</style></head><body>

<section class="page">
  <div class="kicker">Rubik's Cube Solver · Plan</div>
  <h1>Live Camera Solver Pipeline</h1>
  <div class="stripe"><div style="background:{C['W']};border:1px solid {LINE}"></div><div style="background:{C['Y']}"></div><div style="background:{C['R']}"></div><div style="background:{C['O']}"></div><div style="background:{C['G']}"></div><div style="background:{C['B']}"></div></div>
  <p class="lead">You scan the cube once. The app works out the solution, then watches you through the camera while you solve.
  When you do the right move it moves on. If you do a wrong move, it figures out <b>which</b> move you did, re-plans, and tells you what to do next.</p>
  {overview}
  <div class="cards">
    <div class="card"><b>1 · Scan once</b><span>Show each of the 6 sides one time, at the start. After that, no more scanning unless tracking gets lost.</span></div>
    <div class="card"><b>2 · Solve</b><span>The cube is checked and solved in about 20 moves — in milliseconds.</span></div>
    <div class="card"><b>3 · Track live</b><span>Hold the cube tilted. Every move you make is checked; mistakes trigger a re-plan.</span></div>
  </div>
  <div class="foot"><span>Live Camera Solver Pipeline</span><span>1 / 5</span></div>
</section>

<section class="page">
  <div class="kicker">Phase A</div>
  <h2>Scan the cube once</h2>
  <p class="lead">This full scan happens <b>once, at the start</b>. Like today, but with no Capture button and no grid to line up — the camera finds the side by itself.</p>
  {scan_steps}
  <ol class="steps">
    <li><b>Camera on.</b> Your browser streams the computer camera to the Python server about 10 times per second.</li>
    <li><b>Find the side.</b> In each frame the server looks for 9 small squares arranged in a 3×3 grid.</li>
    <li><b>Straighten and read.</b> The side is "flattened" (even if tilted) and each sticker's color is read by comparing it to the cube's own center stickers.</li>
    <li><b>Auto-capture.</b> When the same 9 colors are seen for about half a second, the side is captured and shown in the bottom panel.</li>
    <li><b>Repeat ×6.</b> A side shown twice is rejected (same center color), exactly as it works now.</li>
    <li><b>Check + solve.</b> The app confirms the cube is physically possible, then computes the solution (~20 moves).</li>
  </ol>
  <div class="callout">After the scan you hold the cube in one <b>home position</b> for the rest of the solve: same side up, same side facing you, tilted so the right side shows (see page 4).</div>
  <div class="foot"><span>Live Camera Solver Pipeline</span><span>2 / 5</span></div>
</section>

<section class="page">
  <div class="kicker">Phase B</div>
  <h2>Solve with live tracking</h2>
  <p class="lead">The app always knows the full cube state, so it can predict what the camera <b>should</b> see after every possible move — then check which one actually happened.</p>
  <div style="width:80%;margin:0 auto">{flow}</div>
  <h3 style="margin-top:10px">The trick: compare against predictions</h3>
  <p style="margin:0 0 6px;color:{MUTED}">From the current state, the app builds what the 3 visible sides would look like after each possibility, then picks the closest to what the camera sees.</p>
  <div style="width:88%;margin:0 auto">{predictions}</div>
  <h3 style="margin-top:10px">When does it ask for a rescan?</h3>
  <p style="margin:0 0 8px;color:{MUTED}">Almost never. The first scan is the only one you normally do. A rescan is only requested when the tracker can no longer trust what it sees:</p>
  <div class="cards" style="margin-top:6px">
    <div class="card"><b>🔍 No prediction fits</b><span>What the camera sees doesn't match the correct move, no move, or any 1–2 wrong moves (e.g. the whole cube was rotated).</span></div>
    <div class="card"><b>〰️ Readings jump around</b><span>The best match keeps flipping between options for a few seconds — a sign the colors are being misread.</span></div>
    <div class="card"><b>👀 Cube out of view</b><span>Put the cube down? Hold it back in the home position. If it still matches, tracking simply continues — no rescan.</span></div>
  </div>
  <div class="foot"><span>Live Camera Solver Pipeline</span><span>3 / 5</span></div>
</section>

<section class="page">
  <div class="kicker">Why it works</div>
  <h2>Why the cube must show 3 sides</h2>
  <p class="lead">With one camera you only see part of the cube. We tested 300 random cubes with your app's own cube model:
  can the app tell exactly which move you did?</p>
  {bars}
  <div class="two" style="margin-top:14px">
    <div>
      <h3 style="margin-top:0">What this means</h3>
      <p><b>Front only:</b> a turn of the back side changes nothing the camera can see — impossible to track.</p>
      <p><b>Top + Front:</b> works most of the time, but two quick moves are confused about half the time.</p>
      <p><b>Top + Front + Right:</b> every one of the 18 possible moves — and every pair of moves — looks different. <b>Always identified.</b></p>
      <div class="callout warn">So during solving, hold the cube corner-on to the camera like the picture, and only turn layers — don't rotate the whole cube.</div>
    </div>
    <div>{hold}<p style="text-align:center;color:{MUTED};font-size:11px;margin-top:6px">Home position: the camera looks at the corner where Top, Front and Right meet.</p></div>
  </div>
  <h3>Rules for you while solving</h3>
  <div class="rules">
    <div class="rule"><span class="ic">🧊</span><b>Same side up and facing you</b> for the whole solve, tilted so the right side shows.</div>
    <div class="rule"><span class="ic">🔄</span><b>Turn layers only.</b> Rotating the whole cube makes it lose track and ask for a rescan.</div>
    <div class="rule"><span class="ic">💡</span><b>Even light.</b> Strong direct light causes glare that hides colors.</div>
  </div>
  <div class="foot"><span>Live Camera Solver Pipeline</span><span>4 / 5</span></div>
</section>

<section class="page">
  <div class="kicker">What we'll use</div>
  <h2>Tools, and why each one</h2>
  <div style="width:88%;margin:0 auto">{arch}</div>
  <table><tr><th style="width:24%">Part</th><th style="width:26%">Tool</th><th>Why</th></tr>{tool_rows}</table>
  <h3>Build order — the app keeps working after every step</h3>
  {roadmap}
  <p style="font-size:10.5px;color:{MUTED};margin-top:8px">Note: kociemba is GPL-licensed — fine for personal use; it matters only if the app is ever sold or released as closed source.</p>
  <div class="foot"><span>Live Camera Solver Pipeline</span><span>5 / 5</span></div>
</section>
</body></html>'''

open('reports_out/pipeline.html', 'w').write(html)
