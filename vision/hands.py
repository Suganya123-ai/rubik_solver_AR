"""Hand tracking (Google MediaPipe Hand Landmarker, 21 points per hand), and
what the cube pipeline needs from it:

- which stickers a finger or palm is covering, so the scan and the move
  tracker don't read skin as a sticker colour;
- whether the hands are busy turning the cube, so nothing is judged mid-turn.

Runs on the CPU (~25 ms a frame on an M1), alongside the cube detector.
Turned off with RUBIK_HANDS=0, or if the model file or package is missing
(then everything works as before, just without hands).
"""
import logging
import os
import threading

import cv2
import numpy as np

from cube.color_detect import rgb_to_lab

from .reader import FACE_CORNERS, sticker_quads

log = logging.getLogger('rubik.hands')
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'hand_landmarker.task')

# MediaPipe's 21 points: 0 wrist, then 4 per finger (thumb 1-4, index 5-8, middle 9-12, ring 13-16, little 17-20).
BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
         (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]
PALM = [0, 1, 5, 9, 13, 17]
FINGER_REACH = 0.45   # a sticker may be covered if a finger bone passes within this many sticker widths of its centre...
SKIN_DELTA_E = 10     # ...and it is covered if its colour is this close to the hand's skin colour
                      # (18 was too loose: in warm light an orange sticker is ~18 from skin)
# (MediaPipe also guesses fingers hidden *behind* the cube; in the picture those
# lie across the stickers, so position alone over-marks. On real frames, stickers
# under such hidden fingers were >= 28 from skin colour, real skin < 15.)
TURN_MOTION = 0.2     # the hand's points moving this far relative to the cube (median, in cube sizes)...
TURN_WINDOW_S = 0.4   # ...within this long = turning. The median ignores fingers hidden behind the cube,
                      # whose guessed positions jump around (one jumping fingertip made every frame "turning").
BUSY_HOLD_S = 0.35    # it counts as turning for this long after the last such movement


class HandTracker:
    def __init__(self, model_path=MODEL_PATH, max_hands=2):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path), running_mode=vision.RunningMode.IMAGE,
            num_hands=max_hands, min_hand_detection_confidence=0.4, min_hand_presence_confidence=0.4)
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._lock = threading.Lock()  # one landmarker shared by all connections

    def detect(self, frame):
        """frame: BGR image. Returns [{'points': [[x, y] x 21] in frame pixels, 'score': s}]."""
        h, w = frame.shape[:2]
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        with self._lock:
            result = self._landmarker.detect(image)
        hands = []
        for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
            hands.append({'points': [[round(p.x * w, 1), round(p.y * h, 1)] for p in landmarks],
                          'score': round(float(handedness[0].score), 3)})
        return hands


_tracker = None
_tried = False


def get_hand_tracker():
    """The shared hand tracker, or None if hands are turned off or unavailable."""
    global _tracker, _tried
    if not _tried:
        _tried = True
        if os.environ.get('RUBIK_HANDS', '1') == '0':
            log.info('hand tracking turned off (RUBIK_HANDS=0)')
        elif not os.path.exists(MODEL_PATH):
            log.warning('hand tracking off: %s not found', MODEL_PATH)
        else:
            try:
                _tracker = HandTracker()
            except Exception:  # missing package or unsupported platform: run without hands
                log.exception('hand tracking off: could not load MediaPipe')
    return _tracker


def _segment_distance(p, a, b):
    ab, ap = b - a, p - a
    t = np.clip(np.dot(ap, ab) / max(np.dot(ab, ab), 1e-9), 0, 1)
    return float(np.linalg.norm(ap - t * ab))


def skin_lab(frame, hand):
    """The hand's skin colour (Lab): median around the palm and finger-base points."""
    h, w = frame.shape[:2]
    samples = []
    for i in (0, 1, 2, 5, 6, 9, 10, 13, 14, 17, 18):
        x, y = (int(round(v)) for v in hand['points'][i])
        patch = frame[max(y - 3, 0):min(y + 4, h), max(x - 3, 0):min(x + 4, w)].reshape(-1, 3)
        if len(patch):
            samples.append(np.median(patch, axis=0)[::-1])
    return rgb_to_lab(np.median(samples, axis=0)) if samples else None


def covered_stickers(kpts, hands, frame=None, faces=None):
    """{face: [9 bools]} for faces U, F, R: True where a hand covers the
    sticker. With the frame and the sticker readings, a sticker near a finger
    only counts if it also looks like skin."""
    out = {f: [False] * 9 for f in 'UFR'}
    if not hands:
        return out
    skins = [skin_lab(frame, hand) if frame is not None else None for hand in hands]
    k = np.asarray(kpts, float)
    for face, cells in sticker_quads(k).items():
        corners = k[list(FACE_CORNERS[face])]
        cell = np.mean([np.linalg.norm(corners[i] - corners[(i + 1) % 4]) for i in range(4)]) / 3
        for i, quad in enumerate(cells):
            centre = quad.mean(axis=0)
            for hand, skin in zip(hands, skins):
                pts = np.asarray(hand['points'], float)
                palm = cv2.convexHull(pts[PALM].astype(np.float32))
                near = cv2.pointPolygonTest(palm, (float(centre[0]), float(centre[1])), False) >= 0 or \
                    min(_segment_distance(centre, pts[a], pts[b]) for a, b in BONES) < FINGER_REACH * cell
                if near and (skin is None or faces is None or faces[face] is None or faces[face][i] is None or
                             np.linalg.norm(rgb_to_lab(faces[face][i]) - skin) < SKIN_DELTA_E):
                    out[face][i] = True
                    break
    return out


class BusyHands:
    """Per connection: are the hands turning the cube right now?

    The hand's 21 points are measured relative to the cube (its centre and
    size), so a hand that just holds the cube -- and shakes with it -- doesn't
    count. A turn moves the whole hand relative to the cube, so the *median*
    point movement is used: fingers hidden behind the cube (whose guessed
    positions jump around) can't trigger it on their own. A short hold makes
    one turn one busy stretch."""

    def __init__(self):
        self._history = []          # [(time, [hand points relative to the cube])]
        self._busy_until = -1.0

    def update(self, hands, kpts, now):
        if kpts is None or not hands:
            self._history = []
            return now < self._busy_until
        k = np.asarray(kpts, float)
        centre = k.mean(axis=0)
        size = float(np.mean(np.linalg.norm(k[1:] - k[0], axis=1))) or 1.0
        lo, hi = k.min(axis=0) - 0.5 * size, k.max(axis=0) + 0.5 * size
        current = []
        for h in hands:
            p = np.asarray(h['points'], float)
            if np.any(np.all((p >= lo) & (p <= hi), axis=1)):  # a hand at the cube
                current.append((p - centre) / size)
        self._history = [(t, v) for t, v in self._history if now - t <= TURN_WINDOW_S] + [(now, current)]
        for _, old in self._history[:-1]:
            for hand in current:
                if not old:
                    continue
                # The same hand earlier: the one whose wrist was closest. (Comparing with *any*
                # hand nearby compared the left hand with the right one when both hold the cube.)
                prev = min(old, key=lambda q: np.linalg.norm(q[0] - hand[0]))
                if np.linalg.norm(prev[0] - hand[0]) > 0.6:
                    continue
                if np.median(np.linalg.norm(hand - prev, axis=1)) > TURN_MOTION:
                    self._busy_until = now + BUSY_HOLD_S
        return now < self._busy_until
