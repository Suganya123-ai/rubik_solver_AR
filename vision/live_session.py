"""One connected device (the browser or the XREAL glasses app): its last
frame, its scan and its move tracking. Each WebSocket connection gets its own
LiveClient, so two devices never share state.

The full message protocol is documented in docs/PROTOCOL.md."""
import logging

import numpy as np

from cube.color_detect import COLOR_NAMES, color_feature
from cube.cube_state import FACES
from cube.scan import assemble, scan_result
from cube.solver import SolverError, enrich, solve
from cube.validation import validate_scan

from .live import process_frame, save_capture
from .scan_session import ScanSession
from .tracker import TrackSession, refs_from

log = logging.getLogger('rubik.live')
MAX_FRAME_BYTES = 2_000_000


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
        if self.scan is not None:
            result['scan'] = self.scan.feed(result)
            if result['scan']['event'] == 'done':
                self.scan_rgbs = assemble(self.scan.readings)
                result['scan_result'] = _scan_json(self.scan.result)
                log.info('%s: scan complete (valid=%s, doubtful=%d)', self.name, self.scan.result['valid'],
                         len(self.scan.result['doubtful']))
                self.scan = None
        if self.track is not None:
            result['track'] = _describe(self.track.feed(result))
            if result['track']['event'] in ('wrong', 'lost', 'solved'):
                log.info('%s: %s %s', self.name, result['track']['event'], result['track'].get('message') or '')
        result['frame'] = frame_id
        return result

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
                                  solve=lambda s: solve(s)[0], face_colors={f: colors[f][4] for f in FACES})
        log.info('%s: solving, %d moves', self.name, len(moves))
        return {'type': 'track', 'moves': list(moves), 'track': _describe(self.track.status())}

    def _cmd_track_skip(self, _):
        if self.track is None:
            raise ProtocolError('not tracking')
        return {'type': 'track', 'track': _describe(self.track.skip())}

    def _cmd_track_stop(self, _):
        self.track = None
        return {'type': 'track', 'track': {'phase': 'off', 'event': 'stopped'}}

    def _cmd_save(self, _):
        if self.last_jpeg is None:
            raise ProtocolError('no frame to save yet')
        return {'type': 'saved', **save_capture(self.last_jpeg, self.last_keypoints)}
