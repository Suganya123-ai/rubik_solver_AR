"""Records demo use of the Pyraminx app, for training later.

Each browser connection gets data/pyra_sessions/<day>/<time>/ with camera frames as the camera sent
them (no grid or arrows drawn on), and frames.jsonl: one line per saved frame (file, time, what the
model found: corners, confidence, hold, face share; the app's stage, scan and move events) plus lines
for the scan result, the plan and each verdict. Knowing the puzzle's position at every step, frames
can later be labelled and checked automatically.

Which frames: every SCAN_EVERY_S while scanning or solving, every IDLE_EVERY_S otherwise (often no
pyramid: counter-examples), every frame with an event (a scan view captured or refused, a move judged),
and unsure frames (pyramid found below the app's threshold: the hardest, most useful ones) every
UNSURE_EVERY_S. At most MAX_FRAMES per session. Local files only; PYRA_RECORD=0 turns it off.
"""
import json
import logging
import os
import time
from datetime import datetime

log = logging.getLogger('rubik.pyra')
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'pyra_sessions')
SCAN_EVERY_S = 0.5
IDLE_EVERY_S = 2.0
UNSURE_EVERY_S = 0.5
MAX_FRAMES = 3000


def enabled():
    return os.environ.get('PYRA_RECORD', '1') != '0'


class Recorder:
    def __init__(self, name='client', root=ROOT):
        now = datetime.now()
        self.dir = os.path.join(root, now.strftime('%Y-%m-%d'), now.strftime('%H%M%S'))
        os.makedirs(self.dir, exist_ok=True)
        self.name = name
        self.saved = 0
        self._last = {}            # kind of save -> when
        log.info('%s: recording frames for training to %s', name, self.dir)

    def note(self, record):
        """A line without a frame (scan result, plan, commands)."""
        with open(os.path.join(self.dir, 'frames.jsonl'), 'a') as fh:
            fh.write(json.dumps({'t': round(time.time(), 2), **record}, default=float) + '\n')

    def frame(self, jpeg, result, stage):
        """Saves this frame if it is due (see the module doc). result: the server's reply for it."""
        if self.saved >= MAX_FRAMES:
            return
        now = time.monotonic()
        scan, track = result.get('scan') or {}, result.get('track') or {}
        event = scan.get('event') or scan.get('refused') or (track.get('event') if track.get('event') != 'unsure' else None)
        conf = result.get('confidence') or 0.0
        unsure = 0.25 <= conf < 0.5
        busy = stage in ('scan', 'track')
        kind = 'event' if event else 'unsure' if unsure else 'busy' if busy else 'idle'
        every = {'event': 0.0, 'unsure': UNSURE_EVERY_S, 'busy': SCAN_EVERY_S, 'idle': IDLE_EVERY_S}[kind]
        if now - self._last.get(kind, -1e9) < every:
            return
        self._last[kind] = now
        self.saved += 1
        name = f'{self.saved:05d}.jpg'
        with open(os.path.join(self.dir, name), 'wb') as fh:
            fh.write(jpeg)
        self.note({'file': name, 'why': kind, 'stage': stage, 'event': event,
                   'width': result.get('width'), 'height': result.get('height'),
                   'keypoints': result.get('keypoints'), 'confidence': result.get('confidence'),
                   'view': result.get('view'), 'face_share': result.get('face_share'),
                   'scan': {k: scan.get(k) for k in ('faces_done', 'views', 'message')} if scan else None,
                   'track': {k: track.get(k) for k in ('step', 'move', 'state', 'hold', 'view', 'message')} if track else None})
        if self.saved == MAX_FRAMES:
            log.info('%s: %d frames recorded, no more this session', self.name, MAX_FRAMES)
