"""Sticker color detection from a photo, using only Pillow + numpy (no
OpenCV -- unavailable in this environment). The frontend crops the photo to
a square that exactly frames the 3x3 sticker grid before sending it here, so
this module just needs to split that square into a 3x3 grid and classify
each cell's color.
"""

import base64
import io
import os
import sys

import numpy as np
from PIL import Image

from .cube_state import FACES

COLOR_NAMES = ['white', 'yellow', 'red', 'orange', 'green', 'blue']

# Hue ranges in Pillow's HSV convention (H, S, V all 0-255, so hue is
# degrees/360*255 rather than degrees/360*360). Red wraps around 0/255.
_HUE_RANGES = {
    'red': [(0, 6), (245, 255)],
    'orange': [(7, 26)],
    'yellow': [(27, 52)],
    'green': [(53, 115)],
    'blue': [(122, 180)],
}
_WHITE_MAX_SATURATION = 55
_WHITE_MIN_VALUE = 130


def decode_base64_image(data_url_or_b64):
    """Accepts either a raw base64 string or a data: URL."""
    if ',' in data_url_or_b64 and data_url_or_b64.strip().startswith('data:'):
        data_url_or_b64 = data_url_or_b64.split(',', 1)[1]
    raw = base64.b64decode(data_url_or_b64)
    return Image.open(io.BytesIO(raw)).convert('RGB')


def classify_hsv(h, s, v):
    if s <= _WHITE_MAX_SATURATION and v >= _WHITE_MIN_VALUE:
        return 'white'
    for name, ranges in _HUE_RANGES.items():
        if any(lo <= h <= hi for lo, hi in ranges):
            return name
    # Fall back to nearest hue range's midpoint if nothing matched cleanly
    # (e.g. unusual lighting) -- better to guess than to error out, since
    # the UI lets the user correct any misdetected cell before confirming.
    best_name, best_dist = 'white', None
    for name, ranges in _HUE_RANGES.items():
        for lo, hi in ranges:
            mid = (lo + hi) / 2
            dist = min(abs(h - mid), 255 - abs(h - mid))
            if best_dist is None or dist < best_dist:
                best_name, best_dist = name, dist
    return best_name


def _cell_rgb(rgb_array, row, col, rows, cols):
    h, w, _ = rgb_array.shape
    cell_h, cell_w = h / rows, w / cols
    y0, y1 = row * cell_h, (row + 1) * cell_h
    x0, x1 = col * cell_w, (col + 1) * cell_w
    # Sample the center 50% of the cell to avoid grout lines/glare at edges.
    pad_y, pad_x = (y1 - y0) * 0.25, (x1 - x0) * 0.25
    patch = rgb_array[int(y0 + pad_y):int(y1 - pad_y), int(x0 + pad_x):int(x1 - pad_x)]
    # Median in RGB, not HSV: hue is circular, so a red patch whose pixels
    # straddle 0/255 would otherwise get a median hue somewhere in between.
    return tuple(float(c) for c in np.median(patch.reshape(-1, 3), axis=0))


def _rgb_to_hsv(rgb):
    pixel = Image.new('RGB', (1, 1), tuple(int(round(c)) for c in rgb))
    return pixel.convert('HSV').getpixel((0, 0))


def detect_face_samples(image, grid=3):
    """`image` is a PIL Image already cropped to the sticker grid square.
    Returns (colors, rgbs): `grid*grid` color names and the median RGB each
    was classified from, both in raster order."""
    arr = np.array(image.convert('RGB'))
    colors, rgbs = [], []
    for row in range(grid):
        for col in range(grid):
            rgb = _cell_rgb(arr, row, col, grid, grid)
            rgbs.append(rgb)
            colors.append(classify_hsv(*_rgb_to_hsv(rgb)))
    return colors, rgbs


def detect_face_colors(image, grid=3):
    """`image` is a PIL Image already cropped to the sticker grid square.
    Returns a flat list of `grid*grid` color names in raster order."""
    return detect_face_samples(image, grid=grid)[0]


def rgb_to_lab(rgb):
    """sRGB (0-255) -> CIE Lab (D65), where Euclidean distance roughly tracks
    perceived color difference."""
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193],
                        [0.3576, 0.7152, 0.1192],
                        [0.1805, 0.0722, 0.9505]])
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


FEATURE_LIGHTNESS = 0.3   # brightness counts little: each side of the cube is lit differently
FEATURE_CHROMA_SCALE = 25.0


def color_feature(rgb):
    """A colour as a point where shading matters little: Lab, with lightness
    scaled down and colourfulness (chroma) squashed so every strong colour
    sits on a circle of radius ~100 at its hue angle. Hue is what stays put
    when a side is in shade or catches glare (Gevers & Smeulders 1999), and
    it is what separates red (~30 deg) from orange (~45 deg). Whites and greys
    have low chroma and stay near the middle. Works on one colour or an
    array of them (..., 3)."""
    lab = rgb_to_lab(rgb)
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    squash = 100 * np.tanh(chroma / FEATURE_CHROMA_SCALE) / np.maximum(chroma, 1e-6)
    return np.stack([FEATURE_LIGHTNESS * lab[..., 0], lab[..., 1] * squash, lab[..., 2] * squash], axis=-1)


def _min_cost_assignment(cost):
    """Hungarian algorithm for a square cost matrix. Returns `assign` where
    row i is matched to column assign[i], minimizing the total cost."""
    n = len(cost)
    INF = float('inf')
    u, v = [0.0] * (n + 1), [0.0] * (n + 1)
    p, way = [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    assign = [0] * n
    for j in range(1, n + 1):
        if p[j]:
            assign[p[j] - 1] = j - 1
    return assign


def rebalance_colors(colors_by_face, rgbs_by_face, locked_by_face, per_color=9, lightness_weight=1.0):
    """Re-classify every sticker against the cube's own center stickers so
    each color appears exactly `per_color` times. Fixed hue thresholds drift
    with lighting and camera white balance; the six scanned centers were
    captured under the same conditions, so they make far better references.

    Centers and any cell in `locked_by_face` (indices the user corrected by
    hand) keep their color. Returns a new {face: [9 colors]} dict, or None if
    the centers aren't six distinct colors or the locked cells already
    over-use a color."""
    faces = list(colors_by_face)
    centers = {f: colors_by_face[f][4] for f in faces}
    if sorted(centers.values()) != sorted(COLOR_NAMES):
        return None

    result = {f: list(colors_by_face[f]) for f in faces}
    capacity = {c: per_color for c in COLOR_NAMES}
    free = []  # (face, index) of cells to re-classify
    for f in faces:
        locked = set(locked_by_face.get(f, ())) | {4}
        for i in range(9):
            if i in locked:
                capacity[result[f][i]] -= 1
            else:
                free.append((f, i))
    if any(v < 0 for v in capacity.values()):
        return None

    # lightness_weight < 1 makes brightness count less than hue, so a sticker on
    # a shaded side (a corner-on view lights each side differently) still
    # matches its own colour.
    weights = np.array([lightness_weight, 1.0, 1.0])
    labs = {(f, i): rgb_to_lab(rgbs_by_face[f][i]) * weights for f in faces for i in range(9)}
    refs = {centers[f]: labs[(f, 4)] for f in faces}
    slots = [c for c in COLOR_NAMES for _ in range(capacity[c])]

    # Two passes: assign against the centers, then against the mean of each
    # color's assigned stickers (smooths out a glare-y or shadowed center).
    for _ in range(2):
        cost = [[float(np.linalg.norm(labs[cell] - refs[c])) for c in slots] for cell in free]
        assign = _min_cost_assignment(cost)
        members = {c: [labs[(f, 4)]] for f, c in centers.items()}
        for k, (f, i) in enumerate(free):
            result[f][i] = slots[assign[k]]
            members[result[f][i]].append(labs[(f, i)])
        refs = {c: np.mean(m, axis=0) for c, m in members.items()}
    return result


_THIRD_PARTY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'third_party')
_RESOLVER_SIDE_ORDER = ['U', 'L', 'F', 'R', 'B', 'D']  # how the resolver numbers its 54 squares


def resolver_colors(rgbs_by_face, colors_by_face):
    """Second-opinion colour naming with dwalton76's rubiks-color-resolver
    (vendored in third_party/). It clusters all 54 sampled colours on its own
    and labels each sticker with the side whose centre it matches; we map that
    back to the confirmed centre colour of that side. Hand corrections are not
    honoured, so it is only a fallback. Returns {face: [9 colours]} or None."""
    if _THIRD_PARTY not in sys.path:
        sys.path.insert(0, _THIRD_PARTY)
    from rubikscolorresolver.solver import RubiksColorSolverGeneric

    centers = {f: colors_by_face[f][4] for f in FACES}
    data, n = {}, 1
    for side in _RESOLVER_SIDE_ORDER:
        for rgb in rgbs_by_face[side]:
            data[n] = tuple(int(round(c)) for c in rgb)
            n += 1
    try:
        resolver = RubiksColorSolverGeneric(3)
        resolver.write_debug_file = False
        resolver.enter_scan_data(data)
        resolver.crunch_colors()
        sides = ''.join(resolver.cube_for_kociemba_strict())  # U, R, F, D, L, B -- same as FACES
        return {f: [centers[x] for x in sides[k * 9:(k + 1) * 9]] for k, f in enumerate(FACES)}
    except Exception:  # its internals assume a sane scan; any failure just means "no opinion"
        return None


def detect_face_samples_from_base64(data_url_or_b64, grid=3):
    image = decode_base64_image(data_url_or_b64)
    return detect_face_samples(image, grid=grid)
