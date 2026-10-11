"""Saved live-view frames and their labels, for retraining YOLO on real photos.

Each frame is data/captures/<day>/<stem>.jpg with a YOLO pose label
<stem>.txt (class, box, 7 x (x, y, visible), all normalised). A label is a
model guess until a person reviews it, which writes <stem>.ok. An empty .txt
with .ok means "no cube in this frame" (a useful negative example)."""
import os

import cv2

from .live import CAPTURE_DIR, label_line


def _paths(capture_id, capture_dir=None):
    capture_dir = capture_dir or CAPTURE_DIR
    day, stem = capture_id.split('/')
    if os.sep in stem or '..' in day or '..' in stem:
        raise ValueError('bad capture id')
    base = os.path.join(capture_dir, day, stem)
    if not os.path.exists(base + '.jpg'):
        raise FileNotFoundError(capture_id)
    return base


def list_captures(capture_dir=None):
    capture_dir = capture_dir or CAPTURE_DIR
    out = []
    if not os.path.isdir(capture_dir):
        return out
    for day in sorted(os.listdir(capture_dir)):
        day_dir = os.path.join(capture_dir, day)
        if not os.path.isdir(day_dir):
            continue
        for f in sorted(os.listdir(day_dir)):
            if f.endswith('.jpg'):
                stem = f[:-4]
                out.append({'id': f'{day}/{stem}', 'reviewed': os.path.exists(os.path.join(day_dir, stem + '.ok'))})
    return out


def read_label(capture_id, predict=None, capture_dir=None):
    """Keypoints in image pixels: the reviewed label if there is one, else a
    fresh model guess (predict(frame) -> (kpts, conf) or None), else the label
    saved with the frame. keypoints None means "no cube"."""
    base = _paths(capture_id, capture_dir)
    frame = cv2.imread(base + '.jpg')
    h, w = frame.shape[:2]
    reviewed = os.path.exists(base + '.ok')
    kpts, source = None, 'none'
    if not reviewed and predict is not None:
        found = predict(frame)
        if found is not None:
            kpts, source = found[0].tolist(), 'model'
    if kpts is None and os.path.exists(base + '.txt'):
        vals = open(base + '.txt').read().split()
        if len(vals) >= 5 + 21:
            kpts = [[float(vals[5 + 3 * i]) * w, float(vals[6 + 3 * i]) * h] for i in range(7)]
            source = 'reviewed' if reviewed else 'saved'
        elif reviewed:
            source = 'reviewed'
    return {'id': capture_id, 'width': w, 'height': h, 'keypoints': kpts, 'reviewed': reviewed, 'source': source}


def write_label(capture_id, keypoints, capture_dir=None):
    """keypoints: 7 [x, y] in image pixels, or None for "no cube in this frame"."""
    base = _paths(capture_id, capture_dir)
    if keypoints is not None:
        if len(keypoints) != 7 or any(len(p) != 2 for p in keypoints):
            raise ValueError('expected 7 [x, y] points')
        h, w = cv2.imread(base + '.jpg').shape[:2]
        text = label_line(keypoints, w, h)
    else:
        text = ''
    with open(base + '.txt', 'w') as fh:
        fh.write(text)
    open(base + '.ok', 'w').close()
    return {'id': capture_id, 'reviewed': True}


def delete_capture(capture_id, capture_dir=None):
    base = _paths(capture_id, capture_dir)
    for ext in ('.jpg', '.txt', '.ok'):
        if os.path.exists(base + ext):
            os.remove(base + ext)
    return {'id': capture_id, 'deleted': True}
