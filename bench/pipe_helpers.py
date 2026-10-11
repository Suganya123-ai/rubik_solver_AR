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


