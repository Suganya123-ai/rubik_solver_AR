"""Sticker color detection from a photo, using only Pillow + numpy (no
OpenCV -- unavailable in this environment). The frontend crops the photo to
a square that exactly frames the 3x3 sticker grid before sending it here, so
this module just needs to split that square into a 3x3 grid and classify
each cell's color.
"""

import base64
import io

import numpy as np
from PIL import Image

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


def _cell_hsv(hsv_array, row, col, rows, cols):
    h, w, _ = hsv_array.shape
    cell_h, cell_w = h / rows, w / cols
    y0, y1 = row * cell_h, (row + 1) * cell_h
    x0, x1 = col * cell_w, (col + 1) * cell_w
    # Sample the center 50% of the cell to avoid grout lines/glare at edges.
    pad_y, pad_x = (y1 - y0) * 0.25, (x1 - x0) * 0.25
    patch = hsv_array[int(y0 + pad_y):int(y1 - pad_y), int(x0 + pad_x):int(x1 - pad_x)]
    h_med, s_med, v_med = np.median(patch.reshape(-1, 3), axis=0)
    return float(h_med), float(s_med), float(v_med)


def detect_face_colors(image, grid=3):
    """`image` is a PIL Image already cropped to the sticker grid square.
    Returns a flat list of `grid*grid` color names in raster order."""
    hsv = np.array(image.convert('HSV'))
    colors = []
    for row in range(grid):
        for col in range(grid):
            h, s, v = _cell_hsv(hsv, row, col, grid, grid)
            colors.append(classify_hsv(h, s, v))
    return colors


def detect_face_colors_from_base64(data_url_or_b64, grid=3):
    image = decode_base64_image(data_url_or_b64)
    return detect_face_colors(image, grid=grid)
