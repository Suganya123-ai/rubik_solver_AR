"""Reads the 27 stickers on the three visible sides (Top, Front, Right) from
the cube's 7 corner points: each side is a 4-corner shape, a perspective map
(homography) places its 3x3 grid, and each sticker's colour is the median of
the middle of its cell, which ignores glare specks and the black borders."""
import cv2
import numpy as np

# Each side's corners as keypoint indices, in the side's own raster order:
# top-left, top-right, bottom-right, bottom-left (see vision/detector.py).
FACE_CORNERS = {'U': (2, 3, 0, 1), 'F': (1, 0, 5, 6), 'R': (0, 3, 4, 5)}
_UNIT = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
SAMPLE_FRACTION = 0.4  # sample the middle 40% of each cell


def sticker_quads(kpts):
    """{face: [9 quads (4x2 float32)]} for the sampled middle of each sticker."""
    lo, hi = (1 - SAMPLE_FRACTION) / 2, (1 + SAMPLE_FRACTION) / 2
    out = {}
    for face, idx in FACE_CORNERS.items():
        homography = cv2.getPerspectiveTransform(_UNIT, np.float32([kpts[i] for i in idx]))
        cells = []
        for k in range(9):
            r, c = divmod(k, 3)
            a, b, d, e = (c + lo) / 3, (c + hi) / 3, (r + lo) / 3, (r + hi) / 3
            unit_quad = np.float32([[[a, d], [b, d], [b, e], [a, e]]])
            cells.append(cv2.perspectiveTransform(unit_quad, homography)[0])
        out[face] = cells
    return out


def read_three_faces(frame, kpts):
    """frame: BGR image; kpts: 7x2 corner points. Returns {face: [9 (r, g, b)]}
    for faces U, F, R in raster order, or None for a sticker off the frame."""
    h, w = frame.shape[:2]
    out = {}
    for face, cells in sticker_quads(kpts).items():
        colours = []
        for quad in cells:
            x0, y0 = np.floor(quad.min(0)).astype(int)
            x1, y1 = np.ceil(quad.max(0)).astype(int) + 1
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
            if x1 <= x0 or y1 <= y0:
                colours.append(None)
                continue
            mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
            cv2.fillConvexPoly(mask, np.round(quad - [x0, y0]).astype(np.int32), 255)
            pixels = frame[y0:y1, x0:x1][mask > 0]
            if len(pixels) == 0:
                colours.append(None)
                continue
            b, g, r = np.median(pixels, axis=0)
            colours.append((float(r), float(g), float(b)))
        out[face] = colours
    return out
