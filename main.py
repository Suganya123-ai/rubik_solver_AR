import asyncio
import json
import time
import re
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from cube.color_detect import COLOR_NAMES, detect_face_samples_from_base64, rebalance_colors, resolver_colors
from cube.cube_state import FACES
from cube.solver import SolverError, enrich, solve
from cube.validation import validate_scan

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

logging.basicConfig(level=os.environ.get('RUBIK_LOG_LEVEL', 'INFO'),
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('rubik')


@asynccontextmanager
async def lifespan(_app):
    # Load the YOLO model in the background at startup, so the first person to
    # open the live view doesn't wait for it. Set RUBIK_PRELOAD=0 to skip.
    if os.environ.get('RUBIK_PRELOAD', '1') != '0':
        def preload():
            try:
                from vision.detector import get_detector
                get_detector()
                log.info('cube detector loaded')
            except Exception:
                log.exception('could not load the cube detector')
            from vision.hands import get_hand_tracker
            if get_hand_tracker() is not None:
                log.info('hand tracker loaded')
        threading.Thread(target=preload, daemon=True).start()
    yield


app = FastAPI(title="Rubik's Cube Solver", lifespan=lifespan)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


@app.middleware('http')
async def no_cache(request, call_next):
    # Local dev tool: always serve the latest JS/CSS so edits show up on reload.
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response

# Single-user, in-memory session -- this is a local personal tool, no auth
# or multi-user support needed.
SESSION = {
    'scans': {},       # face letter -> {'colors': auto-detected names, 'rgbs': sampled RGB}
    'confirmed': {},   # face letter -> list of 9 color names
    'instructions': [],  # enriched MoveInstruction dicts, once solved
    'step_index': 0,
}


class ScanFaceRequest(BaseModel):
    face: str
    image: str


class LabelRequest(BaseModel):
    keypoints: list[list[float]] | None  # 7 [x, y] in image pixels, or null for "no cube"


class ConfirmFaceRequest(BaseModel):
    face: str
    colors: list[str]


FACE_NAMES = {'U': 'Top', 'R': 'Right', 'F': 'Front', 'D': 'Bottom', 'L': 'Left', 'B': 'Back'}


def _duplicate_of(face, colors):
    """Every side has a unique center color, so a center already seen on a
    different confirmed side means the same side was captured twice."""
    for other, other_colors in SESSION['confirmed'].items():
        if other != face and other_colors[4] == colors[4]:
            return other
    return None


def _require_face(face):
    if face not in FACES:
        raise HTTPException(400, f"Unknown face '{face}', expected one of {FACES}")


@app.get('/')
def index():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))


@app.get('/live')
def live_page():
    return FileResponse(os.path.join(STATIC_DIR, 'live.html'))


# Sessions kept after their connection drops, so a page that reconnects (a stalled forwarded port,
# a network hiccup) carries on with the same scan or solve: ?session=<id chosen by the page>.
_sessions = {}            # id -> (LiveClient, time it was last used)
SESSION_KEEP_S = 15 * 60


def _session_for(sid, make):
    now = time.monotonic()
    for old in [k for k, (_, t) in _sessions.items() if now - t > SESSION_KEEP_S]:
        del _sessions[old]
    if not sid or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', sid):
        return make(), False
    if sid in _sessions:
        client = _sessions[sid][0]
        _sessions[sid] = (client, now)
        return client, True
    client = make()
    _sessions[sid] = (client, now)
    return client, False


@app.websocket('/ws/live')
async def live_socket(ws: WebSocket):
    """Live camera loop for one device (browser or glasses). Binary messages
    are frames (4-byte big-endian id + JPEG), answered one-to-one, so a client
    that waits for each reply never builds a queue. Text messages are JSON
    commands (scan, check, accept, track, save). See docs/PROTOCOL.md."""
    from vision.live_session import LiveClient, ProtocolError

    await ws.accept()
    name = f'{ws.client.host}:{ws.client.port}' if ws.client else 'client'
    sid = ws.query_params.get('session')
    client, resumed = _session_for(sid, lambda: LiveClient(name=name))
    log.info('%s %s', client.name, 'reconnected: carrying on' if resumed else 'connected')
    sending = asyncio.Lock()   # the assistant's answers are sent from their own tasks

    async def send(reply):
        async with sending:
            await ws.send_json(reply)

    async def answer(kind, command):
        """A question or a report (vision/assistant.py: a second or more): answered beside the frame
        loop, so the camera never waits for the model."""
        try:
            await send(await run_in_threadpool(client.ask if kind == 'ask' else client.report, command))
        except ProtocolError as e:
            await send({'type': 'error', 'code': 'BAD_REQUEST', 'message': str(e)})
        except Exception:
            log.exception('%s: assistant failed', client.name)
            await send({'type': 'answer', 'text': "Sorry, I can't answer that right now."})

    try:
        while True:
            message = await ws.receive()
            if message['type'] == 'websocket.disconnect':
                break
            try:
                if message.get('bytes') is not None:
                    reply = await run_in_threadpool(client.handle_frame, message['bytes'])
                elif message.get('text'):
                    command = json.loads(message['text'])
                    if isinstance(command, dict) and command.get('type') in ('ask', 'report'):
                        asyncio.create_task(answer(command['type'], command))
                        continue
                    reply = await run_in_threadpool(client.handle_command, command)
                else:
                    continue
            except (ProtocolError, ValueError) as e:  # bad input: tell the client, keep the connection
                reply = {'type': 'error', 'code': 'BAD_REQUEST', 'message': str(e)}
            except Exception:  # a bug: log it, tell the client, keep the connection
                log.exception('%s: error handling a message', client.name)
                reply = {'type': 'error', 'code': 'SERVER', 'message': 'internal error, see server log'}
            await send(reply)
    except WebSocketDisconnect:
        pass
    if sid in _sessions:
        _sessions[sid] = (client, time.monotonic())
    log.info('%s disconnected', client.name)


@app.get('/health')
def health():
    """For the glasses app and monitoring: is the server up and the model loaded?"""
    from vision import hands
    from vision.detector import MODEL_PATH, _detector
    return {'ok': True, 'model': os.path.basename(MODEL_PATH), 'model_loaded': _detector is not None,
            'hands_loaded': hands._tracker is not None}


@app.get('/label')
def label_page():
    return FileResponse(os.path.join(STATIC_DIR, 'label.html'))


@app.get('/api/captures')
def captures_list():
    from vision.captures import list_captures
    items = list_captures()
    return {'captures': items, 'reviewed': sum(c['reviewed'] for c in items)}


@app.get('/api/captures/{day}/{stem}/image')
def capture_image(day: str, stem: str):
    from vision.captures import _paths
    try:
        return FileResponse(_paths(f'{day}/{stem}') + '.jpg', media_type='image/jpeg')
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, 'no such capture')


@app.get('/api/captures/{day}/{stem}/label')
def capture_label(day: str, stem: str):
    from vision.captures import read_label
    from vision.detector import get_detector
    try:
        return read_label(f'{day}/{stem}', predict=lambda frame: get_detector().detect(frame))
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, 'no such capture')


@app.post('/api/captures/{day}/{stem}/label')
def capture_label_save(day: str, stem: str, req: LabelRequest):
    from vision.captures import write_label
    try:
        return write_label(f'{day}/{stem}', req.keypoints)
    except FileNotFoundError:
        raise HTTPException(404, 'no such capture')
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete('/api/captures/{day}/{stem}')
def capture_delete(day: str, stem: str):
    from vision.captures import delete_capture
    try:
        return delete_capture(f'{day}/{stem}')
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, 'no such capture')


@app.get('/api/state')
def get_state():
    """Lets the page restore the sides captured so far after a reload."""
    return {'confirmed': SESSION['confirmed']}


@app.post('/api/scan-face')
def scan_face(req: ScanFaceRequest):
    _require_face(req.face)
    try:
        colors, rgbs = detect_face_samples_from_base64(req.image)
    except Exception as e:
        raise HTTPException(400, f"Couldn't read that image: {e}")
    SESSION['scans'][req.face] = {'colors': colors, 'rgbs': rgbs}
    return {'face': req.face, 'colors': colors}


@app.post('/api/confirm-face')
def confirm_face(req: ConfirmFaceRequest):
    _require_face(req.face)
    if len(req.colors) != 9:
        raise HTTPException(400, f"Expected 9 colors, got {len(req.colors)}")
    for c in req.colors:
        if c not in COLOR_NAMES:
            raise HTTPException(400, f"Unknown color '{c}', expected one of {COLOR_NAMES}")
    dup = _duplicate_of(req.face, req.colors)
    if dup:
        raise HTTPException(409, f"This looks like the {FACE_NAMES[dup]} ({dup}) side again -- both have a "
                                 f"{req.colors[4]} center. Show the {FACE_NAMES[req.face]} ({req.face}) side "
                                 f"and capture again. If the center isn't actually {req.colors[4]}, tap it "
                                 f"and correct it.")
    SESSION['confirmed'][req.face] = req.colors
    remaining = [f for f in FACES if f not in SESSION['confirmed']]
    return {'ok': True, 'confirmed_faces': list(SESSION['confirmed'].keys()), 'remaining_faces': remaining}


@app.post('/api/build-and-solve')
def build_and_solve():
    missing = [f for f in FACES if f not in SESSION['confirmed']]
    if missing:
        raise HTTPException(400, f"Still need to scan: {missing}")

    state, result = validate_scan(SESSION['confirmed'])
    if not result.ok:
        for candidate in _recovered_scans():
            retry_state, retry = validate_scan(candidate)
            if retry.ok:
                SESSION['confirmed'] = candidate
                state, result = retry_state, retry
                break
    if not result.ok:
        raise HTTPException(422, {'error_code': result.error_code, 'message': result.message})

    try:
        moves, stage_bounds = solve(state)
    except SolverError as e:
        raise HTTPException(500, f"Solver error: {e}")

    instructions = enrich(moves, stage_bounds)
    SESSION['instructions'] = [instr.__dict__ for instr in instructions]
    SESSION['step_index'] = 0
    return {'total_steps': len(instructions), 'step': _current_step()}


def _recovered_scans():
    """Fallbacks for a scan that fails validation, best first (per our colour
    benchmark): centre-based rebalance, then rubiks-color-resolver."""
    rebalanced = _rebalanced_scan()
    if rebalanced is not None:
        yield rebalanced
    if all(f in SESSION['scans'] for f in FACES):
        resolved = resolver_colors({f: SESSION['scans'][f]['rgbs'] for f in FACES}, SESSION['confirmed'])
        if resolved is not None:
            yield resolved


def _rebalanced_scan():
    """Threshold-based detection drifts with lighting (e.g. washed-out blue
    reading as white), so retry by matching every sticker to the scanned
    centers instead. Cells the user changed by hand stay as they set them."""
    scans = SESSION['scans']
    if any(f not in scans for f in FACES):
        return None
    locked = {f: [i for i, (c, d) in enumerate(zip(SESSION['confirmed'][f], scans[f]['colors'])) if c != d]
              for f in FACES}
    rgbs = {f: scans[f]['rgbs'] for f in FACES}
    return rebalance_colors(SESSION['confirmed'], rgbs, locked)


def _current_step():
    instructions = SESSION['instructions']
    index = SESSION['step_index']
    if not instructions:
        return None
    if index >= len(instructions):
        return {'done': True, 'total_steps': len(instructions)}
    return {'done': False, **instructions[index]}


@app.get('/api/step')
def get_step():
    if not SESSION['instructions']:
        raise HTTPException(400, "No solution yet -- call /api/build-and-solve first")
    return _current_step()


@app.post('/api/step/next')
def next_step():
    if not SESSION['instructions']:
        raise HTTPException(400, "No solution yet -- call /api/build-and-solve first")
    SESSION['step_index'] = min(SESSION['step_index'] + 1, len(SESSION['instructions']))
    return _current_step()


@app.post('/api/step/back')
def back_step():
    if not SESSION['instructions']:
        raise HTTPException(400, "No solution yet -- call /api/build-and-solve first")
    SESSION['step_index'] = max(SESSION['step_index'] - 1, 0)
    return _current_step()


@app.post('/api/reset')
def reset():
    SESSION['scans'] = {}
    SESSION['confirmed'] = {}
    SESSION['instructions'] = []
    SESSION['step_index'] = 0
    return {'ok': True}
