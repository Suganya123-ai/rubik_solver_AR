"""Per-frame processing for the live view, and saving frames as future YOLO
training data (with the model's current guess as a pre-label to correct)."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import cv2
import numpy as np

from .detector import get_detector
from .hands import covered_stickers, get_hand_tracker
from .reader import read_three_faces

CONFIDENT = 0.5  # below this the live view shows the guess as "unsure"
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'captures')


def label_line(kpts, w, h):
    k = np.asarray(kpts, float)
    (x0, y0), (x1, y1) = k.min(0) - 6, k.max(0) + 6
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    values = [f'{(x0 + x1) / 2 / w:.6f}', f'{(y0 + y1) / 2 / h:.6f}', f'{(x1 - x0) / w:.6f}', f'{(y1 - y0) / h:.6f}']
    for x, y in k:
        values += [f'{x / w:.6f}', f'{y / h:.6f}', '2']
    return '0 ' + ' '.join(values) + '\n'


def decode_jpeg(jpeg_bytes):
    frame = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError('not a decodable image')
    return frame


_hand_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='hands')


def process_frame(jpeg_bytes):
    """JPEG bytes -> what the live view needs: corner points, confidence, the
    27 sampled sticker colours, the hands and which stickers they cover (all
    in the sent frame's pixels). Hands are found alongside the cube."""
    t0 = time.perf_counter()
    frame = decode_jpeg(jpeg_bytes)
    h, w = frame.shape[:2]
    tracker = get_hand_tracker()
    hands_job = _hand_pool.submit(tracker.detect, frame) if tracker else None
    found = get_detector().detect(frame)
    hands = hands_job.result() if hands_job else []
    result = {'type': 'frame', 'width': w, 'height': h, 'keypoints': None, 'confidence': None, 'faces': None,
              'confident': False, 'hands': hands, 'covered': None}
    if found is not None:
        kpts, confidence = found
        faces = read_three_faces(frame, kpts)
        result.update(keypoints=kpts.round(1).tolist(), confidence=round(confidence, 3),
                      faces=faces, confident=confidence >= CONFIDENT,
                      covered=covered_stickers(kpts, hands, frame, faces))
    result['ms'] = round((time.perf_counter() - t0) * 1000, 1)
    return result


def save_capture(jpeg_bytes, keypoints=None, capture_dir=None):
    """Saves the frame, plus a YOLO pose label from the current detection so
    Day 3's labelling only has to fix mistakes. Returns the path and total count."""
    capture_dir = capture_dir or CAPTURE_DIR
    day_dir = os.path.join(capture_dir, datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(day_dir, exist_ok=True)
    stem = datetime.now().strftime('%H%M%S_%f')
    image_path = os.path.join(day_dir, f'{stem}.jpg')
    with open(image_path, 'wb') as fh:
        fh.write(jpeg_bytes)
    if keypoints is not None:
        h, w = decode_jpeg(jpeg_bytes).shape[:2]
        with open(os.path.join(day_dir, f'{stem}.txt'), 'w') as fh:
            fh.write(label_line(keypoints, w, h))
    count = sum(f.endswith('.jpg') for _, _, files in os.walk(capture_dir) for f in files)
    return {'saved': os.path.relpath(image_path, os.path.dirname(capture_dir)), 'count': count,
            'prelabelled': keypoints is not None}
