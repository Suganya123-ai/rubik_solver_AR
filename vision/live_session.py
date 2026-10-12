"""One connected device (the browser or the XREAL glasses app): its last
frame, its scan and its move tracking. Each WebSocket connection gets its own
LiveClient, so two devices never share state.

The full message protocol is documented in docs/PROTOCOL.md."""
import json
import logging
import os
import time
from datetime import datetime

import numpy as np

from cube.color_detect import COLOR_NAMES, color_feature
from cube.cube_state import FACES
from cube.scan import assemble, scan_result
from cube.solver import SolverError, enrich, solve
from cube.validation import validate_scan

from .hands import BusyHands
from .live import process_frame, save_capture
from .scan_session import ScanSession
from .tracker import TrackSession, refs_from

log = logging.getLogger('rubik.live')
MAX_FRAME_BYTES = 2_000_000
LOG_EVERY_S = 5.0     # while scanning/solving: a one-line summary of what the camera saw
SESSION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sessions')
SCAN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'scans')
MAX_RECORDED_FRAMES = 600


class SessionRecorder:
    """Writes one solving session to data/sessions/<day>/<time>/: the scan,
    every tracking judgement (what was seen, what was decided) and the frame
    it was judged on, so a session that went wrong can be replayed and fixed.
    Local files only; RUBIK_RECORD=0 turns it off."""

    def __init__(self, start):
        self.dir = os.path.join(SESSION_DIR, datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%H%M%S'))
        os.makedirs(self.dir, exist_ok=True)
        self.frames = 0
        self.write(start)

    def write(self, record, jpeg=None):
        if jpeg is not None and self.frames < MAX_RECORDED_FRAMES:
            self.frames += 1
            record = {**record, 'jpeg': f'{self.frames:04d}.jpg'}
            with open(os.path.join(self.dir, record['jpeg']), 'wb') as fh:
                fh.write(jpeg)
        with open(os.path.join(self.dir, 'session.jsonl'), 'a') as fh:
            fh.write(json.dumps({'t': round(time.time(), 2), **record}) + '\n')


class ProtocolError(ValueError):
    pass


def _scan_json(result):
    return {'colors': result['colors'], 'doubtful': [f'{f}{k}' for f, k in result['doubtful']],
            'valid': result['valid'], 'centers': result['centers']}


def _describe(status):
    if status.get('move'):
        status['description'] = enrich([status['move']], [('solving', 1)])[0].description
    return status


class LiveClient:
    def __init__(self, name='client'):
        self.name = name
        self.last_jpeg = None
        self.last_keypoints = None
        self.scan = None          # ScanSession while scanning
        self.scan_rgbs = None     # {face: [9 rgb]} of the last completed scan
        self.track = None         # TrackSession while solving
        self.busy = BusyHands()   # are the hands turning the cube right now?
        self.recorder = None      # SessionRecorder while solving
        self._scan_dir = None     # where the current scan's views are recorded
        self._seen = {}           # frame counts since the last log line
        self._logged_at = time.monotonic()

    # ---------- frames ----------
    def handle_frame(self, data):
        """data: 4-byte big-endian frame id + JPEG. Returns the reply dict."""
        if len(data) < 5:
            raise ProtocolError('frame message too short')
        if len(data) > MAX_FRAME_BYTES:
            raise ProtocolError(f'frame larger than {MAX_FRAME_BYTES // 1_000_000} MB')
        frame_id, jpeg = int.from_bytes(data[:4], 'big'), data[4:]
        result = process_frame(jpeg)  # raises ValueError on a bad image
        self.last_jpeg, self.last_keypoints = jpeg, result.get('keypoints')
        result['hands_busy'] = self.busy.update(result['hands'], result['keypoints'], time.monotonic())
        self._note(result)
        if self.scan is not None:
            result['scan'] = self.scan.feed(result)
            if result['scan']['event'] in ('captured', 'done'):
                self._record_scan_view(jpeg, result)
            if result['scan']['event'] == 'done':
                self.scan_rgbs = assemble(self.scan.readings)
                result['scan_result'] = _scan_json(self.scan.result)
                log.info('%s: scan complete (valid=%s, doubtful=%d)', self.name, self.scan.result['valid'],
                         len(self.scan.result['doubtful']))
                self.scan = None
        if self.track is not None:
            result['track'] = _describe(self.track.feed(result))
            event = result['track']['event']
            if event and event != 'unsure':
                log.info('%s: %s %s (move %s/%s)', self.name, event, result['track'].get('message') or '',
                         result['track']['step'], result['track']['total'])
                if self.recorder:
                    self.recorder.write({'event': event, 'message': result['track'].get('message'),
                                         'move': result['track'].get('move')})
        result['frame'] = frame_id
        return result

    def _record_scan_view(self, jpeg, result):
        """Saves each captured scan view (the frame, its corners and the colours
        read) to data/scans/<day>/<time>/, so a wrong scan can be looked at.
        Local files only; RUBIK_RECORD=0 turns it off."""
        if os.environ.get('RUBIK_RECORD', '1') == '0':
            return
        view = 1 if result['scan']['event'] == 'captured' else 2
        if view == 1 or self._scan_dir is None:
            self._scan_dir = os.path.join(SCAN_DIR, datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%H%M%S'))
            os.makedirs(self._scan_dir, exist_ok=True)
        with open(os.path.join(self._scan_dir, f'view{view}.jpg'), 'wb') as fh:
            fh.write(jpeg)
        record = {'view': view, 'keypoints': result.get('keypoints'), 'reading': self.scan.readings.get(view),
                  'frame_faces': result.get('faces'), 'covered': result.get('covered')}
        if view == 2 and self.scan.result is not None:
            record['result'] = _scan_json(self.scan.result)
        with open(os.path.join(self._scan_dir, 'scan.jsonl'), 'a') as fh:
            fh.write(json.dumps(record, default=float) + '\n')
        log.info('%s: scan view %d recorded to %s', self.name, view, self._scan_dir)

    def _note(self, result):
        """Counts what the camera saw and logs a summary every few seconds while
        scanning or solving: the first thing to read when it doesn't respond."""
        if self.scan is None and self.track is None:
            return
        seen = self._seen
        seen['frames'] = seen.get('frames', 0) + 1
        for key, hit in (('cube found', result.get('confident')), ('hands seen', bool(result.get('hands'))),
                         ('hands turning', result.get('hands_busy')),
                         ('stickers covered', bool(result.get('covered')) and any(
                             any(v) for v in result['covered'].values()))):
            if hit:
                seen[key] = seen.get(key, 0) + 1
        now = time.monotonic()
        if now - self._logged_at < LOG_EVERY_S:
            return
        self._logged_at = now
        parts = [f'{k} {v}' for k, v in seen.items()]
        if self.track is not None:
            judged = {k[7:]: v for k, v in self.track.counts.items() if k.startswith('judged ')}
            parts.append(f"judged {judged or 'nothing'}")
            if self.track.counts.get('cube moving'):
                parts.append(f"cube moving {self.track.counts['cube moving']}")
            last = getattr(self.track, 'last_judgement', None)
            if last:
                parts.append(f"last: {last['verdict']} (expected {last['expected']}, best {last.get('best')}, "
                             f"{last.get('per_sticker')}/sticker, margin {last.get('margin')}, "
                             f"{last.get('visible')} visible)")
            self.track.counts = {}
        log.info('%s: %s: %s', self.name, 'solving' if self.track else 'scanning', ', '.join(parts))
        self._seen = {}

    # ---------- commands ----------
    def handle_command(self, command):
        kind = command.get('type')
        handler = getattr(self, f'_cmd_{kind}', None) if isinstance(kind, str) else None
        if handler is None:
            raise ProtocolError(f'unknown command {kind!r}')
        return handler(command)

    def _cmd_ping(self, _):
        return {'type': 'pong'}

    def _cmd_scan_start(self, _):
        self.scan, self.track = ScanSession(), None
        return {'type': 'scan', 'scan': {**self.scan.status(), 'event': 'started'}}

    def _cmd_scan_cancel(self, _):
        self.scan = None
        return {'type': 'scan', 'scan': {'phase': 'off', 'event': 'cancelled'}}

    def _cmd_scan_check(self, command):
        """Re-reads the last scan with the user's confirmed stickers locked in."""
        if self.scan_rgbs is None:
            raise ProtocolError('no scan yet')
        locked = {}
        for name, color in (command.get('locked') or {}).items():
            if (not isinstance(name, str) or len(name) != 2 or name[0] not in FACES or not name[1].isdigit()
                    or color not in COLOR_NAMES):
                raise ProtocolError(f'bad sticker {name}={color}')
            locked[(name[0], int(name[1]))] = color
        return {'type': 'scan_result', 'scan_result': _scan_json(scan_result(self.scan_rgbs, locked=locked))}

    def _cmd_scan_accept(self, command):
        """Validates the colours, solves, and starts move tracking."""
        colors = command.get('colors')
        if (not isinstance(colors, dict) or sorted(colors) != sorted(FACES)
                or any(not isinstance(v, list) or len(v) != 9 or any(c not in COLOR_NAMES for c in v)
                       for v in colors.values())):
            raise ProtocolError('expected 9 colour names for each of the 6 faces')
        if self.scan_rgbs is None:
            raise ProtocolError('no scan yet')
        on_mistake = command.get('on_mistake', 'undo')
        if on_mistake not in ('undo', 'replan'):
            raise ProtocolError("on_mistake must be 'undo' or 'replan'")
        state, result = validate_scan(colors)
        if not result.ok:
            return {'type': 'error', 'code': result.error_code, 'message': result.message}
        try:
            moves = solve(state)[0]
        except SolverError as e:
            return {'type': 'error', 'code': 'SOLVER', 'message': str(e)}
        feats = [color_feature(rgb) for f in FACES for rgb in self.scan_rgbs[f]]
        letters = ''.join(state.arr)
        self.track = TrackSession(np.array(list(letters)), moves, refs_from(letters, feats),
                                  solve=lambda s: solve(s)[0], face_colors={f: colors[f][4] for f in FACES},
                                  on_mistake=on_mistake)
        log.info('%s: solving, %d moves: %s', self.name, len(moves), ' '.join(moves))
        if os.environ.get('RUBIK_RECORD', '1') != '0':
            self.recorder = SessionRecorder({'start': True, 'state': letters, 'plan': list(moves),
                                             'face_colors': self.track.face_colors, 'on_mistake': on_mistake,
                                             'scan_rgbs': self.scan_rgbs})
            self.track.on_judgement = lambda j: self.recorder.write(j, self.last_jpeg)
            log.info('%s: recording this session to %s', self.name, self.recorder.dir)
        return {'type': 'track', 'moves': list(moves), 'track': _describe(self.track.status())}

    def _cmd_track_skip(self, _):
        if self.track is None:
            raise ProtocolError('not tracking')
        return {'type': 'track', 'track': _describe(self.track.skip())}

    def _cmd_track_replan(self, _):
        if self.track is None:
            raise ProtocolError('not tracking')
        return {'type': 'track', 'track': _describe(self.track.replan())}

    def _cmd_track_stop(self, _):
        self.track = None
        return {'type': 'track', 'track': {'phase': 'off', 'event': 'stopped'}}

    def _cmd_save(self, _):
        if self.last_jpeg is None:
            raise ProtocolError('no frame to save yet')
        return {'type': 'saved', **save_capture(self.last_jpeg, self.last_keypoints)}
