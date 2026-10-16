"""One connected browser for the Pyraminx tutor: its frames, its scan and its move tracking.

Same WebSocket protocol as the cube app (docs/PROTOCOL.md): binary messages
are frames (4-byte frame id + JPEG), text messages are JSON commands:
    scan_start, scan_cancel, scan_check {locked: {sticker: letter}},
    scan_accept {locked}, track_skip, track_replan, track_stop, ping.
"""
import logging
import os
import threading
import time

import cv2
import numpy as np

from .geometry import COLOURS
from .scan import ScanSession, scan_result
from .solver import solve, table
from .tracker import TrackSession, letter_features
from .view import face_share, read_stickers

log = logging.getLogger('rubik.pyra')
MODELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
MODEL_PATH = os.environ.get('PYRA_MODEL') or os.path.join(MODELS, 'pyra_pose_v3.pt')
CONFIDENT = 0.5
MAX_FRAME_BYTES = 2_000_000
_detector = None
_lock = threading.Lock()


class ProtocolError(ValueError):
    pass


def detector():
    """The Pyraminx corner model (YOLO pose, 4 corners), loaded once."""
    global _detector
    if _detector is None:
        with _lock:
            if _detector is None:
                from vision.detector import CubeDetector
                _detector = CubeDetector(MODEL_PATH)
    return _detector


def detect(frame, min_confidence=0.25):
    """(4 corner points, confidence, view kind) of the most confident pyramid, or None. The kind is
    'edge' (an edge toward the camera, class 1) or 'corner' (class 0; the only one older models know)."""
    d = detector()
    r = d.model.predict(frame, imgsz=640, device=d.device, verbose=False)[0]
    if r.keypoints is None or len(r.boxes) == 0:
        return None
    best = int(r.boxes.conf.argmax())
    conf = float(r.boxes.conf[best])
    if conf < min_confidence:
        return None
    kind = 'edge' if len(d.model.names) > 1 and int(r.boxes.cls[best]) == 1 else 'corner'
    return r.keypoints.xy[best].cpu().numpy().astype(np.float32), conf, kind


def process_frame(jpeg):
    t0 = time.perf_counter()
    frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError('not a decodable image')
    h, w = frame.shape[:2]
    found = detect(frame)
    out = {'type': 'frame', 'width': w, 'height': h, 'keypoints': None, 'confidence': None, 'confident': False,
           'stickers': None, 'face_share': None, 'view': None}
    if found is not None:
        k, conf, kind = found
        out.update(keypoints=k.round(1).tolist(), confidence=round(conf, 3), confident=conf >= CONFIDENT, view=kind,
                   stickers=read_stickers(frame, k, kind=kind), face_share=round(face_share(k, kind), 3))
    out['ms'] = round((time.perf_counter() - t0) * 1000, 1)
    return out


def _scan_json(res):
    state = res['state']
    return {'state': state, 'valid': res['valid'], 'doubtful': res['doubtful'],
            'colour_of': res['colour_of'], 'colours': [res['colour_of'].get(L, COLOURS[L]) for L in state]}


class PyraClient:
    def __init__(self, name='client'):
        self.name = name
        self.scan = None
        self.rgbs = None
        self.last = None        # last scan result (with the user's corrections)
        self.track = None

    def handle_frame(self, data):
        if len(data) < 5 or len(data) > MAX_FRAME_BYTES:
            raise ProtocolError('bad frame message')
        frame_id = int.from_bytes(data[:4], 'big')
        result = process_frame(data[4:])
        result['frame'] = frame_id
        if self.scan is not None:
            result['scan'] = self.scan.feed(result)
            if result['scan']['event'] == 'done':
                self.rgbs = self.scan.rgbs
                self.last = self.scan.result
                result['scan_result'] = _scan_json(self.last)
                log.info('%s: scan done in %d views, doubtful %d', self.name, self.scan.views, len(self.last['doubtful']))
                self.scan = None
        if self.track is not None:
            result['track'] = self._track_json(self.track.feed(result))
            ev = result['track']['event']
            if ev and ev != 'unsure':
                log.info('%s: %s %s', self.name, ev, result['track'].get('message') or '')
        return result

    def _track_json(self, status):
        return {**status, 'colour_of': self.last['colour_of'] if self.last else {}}

    def handle_command(self, cmd):
        kind = cmd.get('type')
        fn = getattr(self, f'_cmd_{kind}', None) if isinstance(kind, str) else None
        if fn is None:
            raise ProtocolError(f'unknown command {kind!r}')
        return fn(cmd)

    def _cmd_ping(self, _):
        return {'type': 'pong'}

    def _cmd_scan_start(self, _):
        table()   # make sure the solver's table is loaded before it is needed
        self.scan, self.track = ScanSession(), None
        return {'type': 'scan', 'scan': {**self.scan.status(), 'event': 'started'}}

    def _cmd_scan_cancel(self, _):
        self.scan = None
        return {'type': 'scan', 'scan': {'phase': 'off', 'event': 'cancelled'}}

    def _locked(self, cmd):
        locked = {}
        for k, v in (cmd.get('locked') or {}).items():
            if not str(k).isdigit() or not 0 <= int(k) < 36 or v not in ('F', 'R', 'L', 'D'):
                raise ProtocolError(f'bad sticker {k}={v}')
            locked[int(k)] = v
        return locked

    def _cmd_scan_check(self, cmd):
        if self.rgbs is None:
            raise ProtocolError('no scan yet')
        self.last = scan_result(self.rgbs, self._locked(cmd))
        return {'type': 'scan_result', 'scan_result': _scan_json(self.last)}

    def _cmd_scan_accept(self, cmd):
        if self.rgbs is None:
            raise ProtocolError('no scan yet')
        if cmd.get('locked'):
            self.last = scan_result(self.rgbs, self._locked(cmd))
        if not self.last['valid']:
            return {'type': 'error', 'code': 'INVALID', 'message': 'Those colours are not a possible Pyraminx. Check the highlighted stickers.'}
        state = np.array(list(self.last['state']))
        plan = solve(state)
        self.track = TrackSession(state, plan, letter_features(self.rgbs, state))
        log.info('%s: solving, %d moves: %s', self.name, len(plan), ' '.join(plan))
        return {'type': 'track', 'plan': plan, 'track': self._track_json(self.track.status())}

    def _cmd_track_skip(self, _):
        if self.track is None:
            raise ProtocolError('not tracking')
        return {'type': 'track', 'track': self._track_json(self.track.skip())}

    def _cmd_track_replan(self, _):
        if self.track is None:
            raise ProtocolError('not tracking')
        return {'type': 'track', 'track': self._track_json(self.track.replan())}

    def _cmd_track_stop(self, _):
        self.track = None
        return {'type': 'track', 'track': {'phase': 'off', 'event': 'stopped'}}


def geometry_json():
    """The puzzle's layout for the web app (ghost pyramid, arrows): one source of truth."""
    from .geometry import CORNERS, FACE_CORNERS, FACES, MOVES, STICKERS
    return {'corners': {k: v.round(6).tolist() for k, v in CORNERS.items()},
            'faces': list(FACES), 'face_corners': FACE_CORNERS, 'colours': COLOURS,
            'stickers': [{'face': f, 'k': k, 'tri': t.round(6).tolist()} for f, k, t in STICKERS],
            'moves': {m: p.tolist() for m, p in MOVES.items()}}
