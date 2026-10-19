"""Thin adapters that run each project's own sticker-finding code on a frame
and return the 9 sticker centres in raster order (or None if not found)."""
import ast
import logging
import sys
import time
from copy import deepcopy

import cv2

sys.path.insert(0, 'third_party/rubiks-cube-tracker')
from rubikscubetracker import RubiksImage  # noqa: E402

logging.disable(logging.CRITICAL)


def _load_qbr_find_contours():
    # Pull qbr's find_contours method out of video.py without importing the
    # module (importing opens the webcam and writes ~/.config/qbr).
    src = open('third_party/qbr/src/video.py').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'find_contours':
            mod = ast.Module(body=[node], type_ignores=[])
            ns = {'cv2': cv2}
            exec(compile(mod, 'qbr_video', 'exec'), ns)
            return ns['find_contours']
    raise RuntimeError('find_contours not found')


_qbr_find = _load_qbr_find_contours()


def qbr_detect(frame):
    """qbr's exact preprocessing from Webcam.run() + find_contours()."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.blur(gray, (3, 3))
    canny = cv2.Canny(blurred, 30, 60, 3)
    dilated = cv2.dilate(canny, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    contours = _qbr_find(None, dilated)
    if len(contours) != 9:
        return None
    return [(x + w / 2, y + h / 2) for (x, y, w, h) in contours]


def qbr_multiscale_detect(frame):
    """Our tweak: qbr only accepts 30-60 px stickers, so also try it on
    scaled-down copies of the frame and keep the first hit."""
    for scale in (1.0, 0.75, 0.5, 0.375, 0.25):
        small = frame if scale == 1.0 else cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        out = qbr_detect(small)
        if out is not None:
            return [(x / scale, y / scale) for x, y in out]
    return None


def tracker_detect(frame):
    """dwalton76/rubiks-cube-tracker RubiksImage.analyze()."""
    r = RubiksImage(0, 'frame')
    r.image = frame.copy()
    try:
        ok = r.analyze(webcam=False, cube_size=3)
    except Exception:
        return None
    if not ok or r.size != 3 or len(r.candidates) != 9:
        return None
    ordered = r.sort_by_row_col(deepcopy(r.candidates), 3)
    return [(c.cX, c.cY) for c in ordered]


def app_grid_detect(frame):
    """The current app: fixed 3x3 grid in the centre square, inset 8%."""
    h, w = frame.shape[:2]
    side = min(w, h)
    inset = side * 0.08
    g = side - 2 * inset
    x0, y0 = (w - side) / 2 + inset, (h - side) / 2 + inset
    return [(x0 + (c + 0.5) * g / 3, y0 + (r + 0.5) * g / 3) for r in range(3) for c in range(3)]


from ephynes_port import ephynes_detect, ephynes_multiscale_detect  # noqa: E402

DETECTORS = {
    'Current app (fixed grid)': app_grid_detect,
    'qbr (kkoomen)': qbr_detect,
    'qbr + multi-scale (our tweak)': qbr_multiscale_detect,
    'rubiks-cube-tracker (dwalton76)': tracker_detect,
    'ephynes AR solver (C# port)': ephynes_detect,
    'ephynes + multi-scale (our tweak)': ephynes_multiscale_detect,
}
ROTATION_TOLERANT = {'ephynes AR solver (C# port)', 'ephynes + multi-scale (our tweak)'}


def timed(fn, frame):
    t0 = time.perf_counter()
    out = fn(frame)
    return out, (time.perf_counter() - t0) * 1000
